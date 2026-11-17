import json
from argparse import Namespace

import numpy as np
import torch
from PIL import Image

from model.dataset import BDDDetectionDataset, convert_bdd_record, grouped_train_validation_split, write_jsonl
from model.prepare_bdd100k import prepare


def test_bdd_mapping_clipping_and_grouped_split(tmp_path):
    record = {
        "name": "abcd1234-00000001.jpg",
        "labels": [
            {"category": "rider", "box2d": {"x1": 20, "y1": 10, "x2": 5, "y2": 30}},
            {"category": "bike", "box2d": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}},
            {"category": "car", "box2d": {"x1": -10, "y1": -20, "x2": 1400, "y2": 800}},
            {"category": "traffic light", "box2d": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}},
        ],
    }
    converted = convert_bdd_record(record, tmp_path)
    assert converted["labels"] == [0, 1, 3]
    assert converted["boxes"][0] == [5.0, 10.0, 20.0, 30.0]
    assert converted["boxes"][2] == [0.0, 0.0, 1280.0, 720.0]
    records = [
        {"name": f"{group}-{index}.jpg", "sequence": group, "boxes": [], "labels": []}
        for group in ("a", "b", "c", "d")
        for index in range(2)
    ]
    train1, val1 = grouped_train_validation_split(records, 4, seed=10)
    train2, val2 = grouped_train_validation_split(records, 4, seed=10)
    assert [item["name"] for item in val1] == [item["name"] for item in val2]
    assert len(train1) == len(val1) == 4
    assert {item["sequence"] for item in train1}.isdisjoint({item["sequence"] for item in val1})


def test_dataset_augmentation_and_mosaic_boxes_stay_bounded(tmp_path):
    records = []
    for index in range(4):
        path = tmp_path / f"seq-{index}.jpg"
        Image.fromarray(np.full((40, 80, 3), 80 + index, np.uint8)).save(path)
        records.append({"image": str(path), "name": path.name, "sequence": "seq", "boxes": [[4, 5, 30, 35]], "labels": [3]})
    manifest = tmp_path / "manifest.jsonl"
    write_jsonl(records, manifest)
    dataset = BDDDetectionDataset(manifest, augment=True, mosaic_probability=1.0, seed=1)
    image, target = dataset[0]
    assert image.shape == (3, 160, 160)
    assert target["boxes"].shape == (4, 4)
    assert torch.all(target["boxes"] >= 0) and torch.all(target["boxes"] <= 160)


def test_prepare_writes_hashed_disjoint_manifests(tmp_path):
    train_labels = [{"name": f"seq{index // 2}-{index}.jpg", "labels": []} for index in range(6)]
    final_labels = [{"name": f"final-{index}.jpg", "labels": []} for index in range(2)]
    train_json, final_json = tmp_path / "train.json", tmp_path / "final.json"
    train_json.write_text(json.dumps(train_labels), encoding="utf-8")
    final_json.write_text(json.dumps(final_labels), encoding="utf-8")
    output = tmp_path / "manifests"
    prepare(Namespace(
        output=str(output), train_labels=str(train_json), train_images=str(tmp_path),
        final_test_labels=str(final_json), final_test_images=str(tmp_path),
        train_count=4, validation_count=2, final_test_count=2, seed=2026,
    ))
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert set(metadata["manifest_sha256"]) == {"train", "validation", "final_test"}
    names = []
    for split in ("train", "validation", "final_test"):
        names.append({json.loads(line)["name"] for line in (output / f"{split}.jsonl").read_text().splitlines()})
    assert not (names[0] & names[1] or names[0] & names[2] or names[1] & names[2])
