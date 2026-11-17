from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from .config import load_config
from .dataset import BDDDetectionDataset, detection_collate
from .distillation import distillation_loss
from .losses import EdgeDetLoss
from .metrics import evaluate_detections
from .network import EdgeDetZ20
from .postprocess import decode_detections


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def _to_device(targets: list[dict], device: torch.device) -> list[dict]:
    return [{key: value.to(device) if isinstance(value, torch.Tensor) else value for key, value in item.items()} for item in targets]


@torch.no_grad()
def validate(model, loader, criterion, device) -> tuple[float, dict]:
    model.eval()
    loss_sum = 0.0
    predictions, targets_all = [], []
    for images, targets in loader:
        images, targets_device = images.to(device), _to_device(targets, device)
        outputs = model(images)
        loss_sum += float(criterion(outputs, targets_device).total)
        predictions.extend({key: value.cpu() for key, value in item.items()} for item in decode_detections(outputs))
        targets_all.extend({key: value.cpu() if isinstance(value, torch.Tensor) else value for key, value in item.items()} for item in targets)
    metrics = evaluate_detections(predictions, targets_all)
    return loss_sum / max(len(loader), 1), metrics.__dict__


def train(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    seed_everything(args.seed)
    device = torch.device(args.device if args.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    training = config["training"]
    phase = args.phase
    epochs = training["qat_epochs"] if phase == "qat" else training["student_epochs"]
    train_data = BDDDetectionDataset(
        args.train_manifest,
        augment=True,
        mosaic_probability=training["mosaic_probability"],
        seed=args.seed,
    )
    validation_data = BDDDetectionDataset(args.validation_manifest)
    loader_args = dict(batch_size=training["batch_size"], num_workers=training["workers"], collate_fn=detection_collate)
    train_loader = DataLoader(train_data, shuffle=True, **loader_args)
    validation_loader = DataLoader(validation_data, shuffle=False, **loader_args)
    model = EdgeDetZ20().to(device)
    teacher = None
    if args.teacher_torchscript:
        teacher = torch.jit.load(args.teacher_torchscript, map_location=device).eval()
        for parameter in teacher.parameters():
            parameter.requires_grad_(False)
    if args.resume:
        checkpoint = torch.load(args.resume, map_location="cpu", weights_only=True)
        model.load_state_dict(checkpoint["model"] if "model" in checkpoint else checkpoint)
    if phase == "qat":
        model.enable_qat(args.profile)
    criterion = EdgeDetLoss(
        alpha=config["loss"]["focal_alpha"],
        gamma=config["loss"]["focal_gamma"],
        giou_weight=config["loss"]["giou_weight"],
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=training["learning_rate"], weight_decay=training["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    best_map, stale = -1.0, 0
    history = []
    for epoch in range(epochs):
        model.train()
        mosaic_enabled = epoch < epochs - training["mosaic_disable_last_epochs"]
        train_data.set_epoch(epoch, mosaic_enabled=mosaic_enabled)
        running = 0.0
        for images, targets in train_loader:
            images, targets = images.to(device), _to_device(targets, device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                if teacher is None:
                    outputs = model(images)
                    result = criterion(outputs, targets)
                    total_loss = result.total
                else:
                    student_features = model.forward_features(images)
                    outputs = (model.head20(student_features["fused"]), model.head10(student_features["p4"]))
                    result = criterion(outputs, targets)
                    with torch.no_grad():
                        teacher_result = teacher(images)
                    distilled = distillation_loss(outputs, student_features, teacher_result)
                    total_loss = result.total + distilled.total
            scaler.scale(total_loss).backward()
            scaler.step(optimizer)
            scaler.update()
            running += float(total_loss.detach())
        scheduler.step()
        validation_loss, metrics = validate(model, validation_loader, criterion, device)
        row = {"epoch": epoch + 1, "train_loss": running / max(len(train_loader), 1), "validation_loss": validation_loss, **metrics}
        history.append(row)
        (output / "history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        state = {"model": model.state_dict(), "epoch": epoch + 1, "seed": args.seed, "phase": phase, "profile": args.profile}
        torch.save(state, output / "last.pt")
        if metrics["map50"] > best_map:
            best_map, stale = metrics["map50"], 0
            torch.save(state, output / "best.pt")
        else:
            stale += 1
            if stale >= training["early_stopping_patience"]:
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="Train or QAT-fine-tune EdgeDet-Z20")
    parser.add_argument("--config", default="config/edgedet_z20.yaml")
    parser.add_argument("--train-manifest", required=True)
    parser.add_argument("--validation-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", choices=("student", "qat"), default="student")
    parser.add_argument("--profile", choices=("accuracy", "eco"), default="accuracy")
    parser.add_argument("--resume")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--device")
    parser.add_argument(
        "--teacher-torchscript",
        help="optional fine-tuned YOLOX-S adapter returning head20/head10/feature20/feature10",
    )
    train(parser.parse_args())


if __name__ == "__main__":
    main()
