from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageEnhance, ImageFilter
from torch.utils.data import Dataset

from .constants import BDD_CLASS_MAP, BDD_IMAGE_HEIGHT, BDD_IMAGE_WIDTH, CLASS_TO_ID, NETWORK_SIZE
from .preprocess import preprocess_rgb


def sequence_id(filename: str) -> str:
    """BDD frame names encode the source clip before the final dash."""
    stem = Path(filename).stem
    return stem.rsplit("-", 1)[0] if "-" in stem else stem


def convert_bdd_record(record: dict[str, Any], image_root: str | Path) -> dict[str, Any]:
    image_root = Path(image_root)
    name = str(record["name"])
    boxes: list[list[float]] = []
    labels: list[int] = []
    for annotation in record.get("labels", []):
        mapped = BDD_CLASS_MAP.get(str(annotation.get("category", "")))
        box = annotation.get("box2d")
        if mapped is None or not isinstance(box, dict):
            continue
        x1, y1 = float(box["x1"]), float(box["y1"])
        x2, y2 = float(box["x2"]), float(box["y2"])
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        x1, x2 = max(0.0, x1), min(float(BDD_IMAGE_WIDTH), x2)
        y1, y2 = max(0.0, y1), min(float(BDD_IMAGE_HEIGHT), y2)
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append([x1, y1, x2, y2])
        labels.append(CLASS_TO_ID[mapped])
    return {
        "image": str((image_root / name).resolve()),
        "name": name,
        "sequence": sequence_id(name),
        "boxes": boxes,
        "labels": labels,
    }


def grouped_train_validation_split(
    records: Iterable[dict[str, Any]], validation_count: int = 7000, seed: int = 2026
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create an exact deterministic split without putting a sequence in both sets."""
    records = list(records)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record["sequence"])].append(record)
    ordered = sorted(groups, key=lambda key: hashlib.sha256(f"{seed}:{key}".encode()).digest())
    # Bounded subset-sum finds an exact group combination and is cheap at the 7k target.
    previous: dict[int, tuple[int, str]] = {0: (-1, "")}
    for key in ordered:
        size = len(groups[key])
        for total in sorted(tuple(previous), reverse=True):
            candidate = total + size
            if candidate <= validation_count and candidate not in previous:
                previous[candidate] = (total, key)
        if validation_count in previous:
            break
    if validation_count not in previous:
        raise ValueError(f"cannot form an exact {validation_count}-image validation set without splitting sequences")
    selected: set[str] = set()
    total = validation_count
    while total:
        prior, key = previous[total]
        selected.add(key)
        total = prior
    train = [record for record in records if str(record["sequence"]) not in selected]
    validation = [record for record in records if str(record["sequence"]) in selected]
    train.sort(key=lambda item: item["name"])
    validation.sort(key=lambda item: item["name"])
    return train, validation


def write_jsonl(records: Iterable[dict[str, Any]], destination: str | Path) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _augment_rgb(image: np.ndarray, boxes: torch.Tensor, rng: random.Random):
    pil = Image.fromarray(image.astype(np.uint8), mode="RGB")
    # Colour/exposure jitter and blur are host-training only; canonical preprocessing follows.
    pil = ImageEnhance.Brightness(pil).enhance(rng.uniform(0.8, 1.2))
    pil = ImageEnhance.Contrast(pil).enhance(rng.uniform(0.8, 1.2))
    pil = ImageEnhance.Color(pil).enhance(rng.uniform(0.8, 1.2))
    if rng.random() < 0.15:
        pil = pil.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.1, 1.2)))
    image = np.asarray(pil)
    if rng.random() < 0.5:
        image = np.ascontiguousarray(image[:, ::-1])
        width = image.shape[1]
        if boxes.numel():
            old_x1 = boxes[:, 0].clone()
            boxes[:, 0] = width - boxes[:, 2]
            boxes[:, 2] = width - old_x1
    # Bounded scale/translation affine, applied with PIL and mirrored in boxes.
    if rng.random() < 0.5:
        scale = rng.uniform(0.9, 1.1)
        tx = rng.uniform(-0.05, 0.05) * image.shape[1]
        ty = rng.uniform(-0.05, 0.05) * image.shape[0]
        pil = Image.fromarray(image).transform(
            (image.shape[1], image.shape[0]),
            Image.Transform.AFFINE,
            (1.0 / scale, 0.0, -tx / scale, 0.0, 1.0 / scale, -ty / scale),
            resample=Image.Resampling.BILINEAR,
            fillcolor=(114, 114, 114),
        )
        image = np.asarray(pil)
        if boxes.numel():
            boxes[:, 0::2] = boxes[:, 0::2] * scale + tx
            boxes[:, 1::2] = boxes[:, 1::2] * scale + ty
            boxes[:, 0::2].clamp_(0, image.shape[1])
            boxes[:, 1::2].clamp_(0, image.shape[0])
    return image, boxes


class BDDDetectionDataset(Dataset):
    def __init__(
        self,
        manifest: str | Path,
        *,
        augment: bool = False,
        mosaic_probability: float = 0.0,
        seed: int = 2026,
    ) -> None:
        self.records = read_jsonl(manifest)
        self.augment = augment
        self.mosaic_probability = mosaic_probability
        self.seed = seed
        self.epoch = 0

    def __len__(self) -> int:
        return len(self.records)

    def set_epoch(self, epoch: int, *, mosaic_enabled: bool = True) -> None:
        self.epoch = epoch
        if not mosaic_enabled:
            self.mosaic_probability = 0.0

    def _load_one(self, index: int, rng: random.Random):
        record = self.records[index]
        with Image.open(record["image"]) as source:
            image = np.asarray(source.convert("RGB"))
        boxes = torch.tensor(record["boxes"], dtype=torch.float32).reshape(-1, 4)
        labels = torch.tensor(record["labels"], dtype=torch.long)
        if self.augment:
            image, boxes = _augment_rgb(image, boxes, rng)
        tensor, boxes, info = preprocess_rgb(image, boxes)
        keep = torch.ones(labels.shape[0], dtype=torch.bool)
        if boxes is not None and boxes.numel():
            keep = (boxes[:, 2] - boxes[:, 0] >= 1) & (boxes[:, 3] - boxes[:, 1] >= 1)
        return tensor, boxes[keep] if boxes is not None else torch.empty((0, 4)), labels[keep], info

    def __getitem__(self, index: int):
        rng = random.Random(self.seed + self.epoch * max(len(self), 1) + index)
        if self.augment and len(self) >= 4 and rng.random() < self.mosaic_probability:
            indices = [index] + rng.sample(range(len(self)), 3)
            canvas = torch.zeros((3, NETWORK_SIZE, NETWORK_SIZE), dtype=torch.float32)
            all_boxes, all_labels = [], []
            for slot, sample_index in enumerate(indices):
                image, boxes, labels, _ = self._load_one(sample_index, rng)
                small = F.interpolate(image.unsqueeze(0), size=(NETWORK_SIZE // 2, NETWORK_SIZE // 2), mode="bilinear", align_corners=False)[0]
                x = (slot % 2) * (NETWORK_SIZE // 2)
                y = (slot // 2) * (NETWORK_SIZE // 2)
                canvas[:, y : y + NETWORK_SIZE // 2, x : x + NETWORK_SIZE // 2] = small
                boxes = boxes * 0.5
                boxes[:, 0::2] += x
                boxes[:, 1::2] += y
                all_boxes.append(boxes)
                all_labels.append(labels)
            return canvas, {"boxes": torch.cat(all_boxes), "labels": torch.cat(all_labels), "image_id": index}
        image, boxes, labels, _ = self._load_one(index, rng)
        return image, {"boxes": boxes, "labels": labels, "image_id": index}


def detection_collate(batch):
    return torch.stack([item[0] for item in batch]), [item[1] for item in batch]
