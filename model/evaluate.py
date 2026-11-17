"""Evaluate a float or QAT checkpoint and write an evidence-labeled metrics file."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from .config import load_config
from .dataset import BDDDetectionDataset, detection_collate
from .losses import EdgeDetLoss
from .network import EdgeDetZ20
from .train import seed_everything, validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/edgedet_z20.yaml")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    config = load_config(args.config)
    seed_everything(int(config["project"]["seed"]))
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = EdgeDetZ20()
    model.load_state_dict(checkpoint["model"] if "model" in checkpoint else checkpoint)
    phase = checkpoint.get("phase", "float") if isinstance(checkpoint, dict) else "float"
    profile = checkpoint.get("profile", "none") if isinstance(checkpoint, dict) else "none"
    if phase == "qat":
        model.enable_qat(profile)
    model.to(device)
    dataset = BDDDetectionDataset(args.manifest)
    loader = DataLoader(
        dataset, batch_size=args.batch_size, num_workers=args.workers,
        shuffle=False, collate_fn=detection_collate,
    )
    criterion = EdgeDetLoss(
        alpha=config["loss"]["focal_alpha"],
        gamma=config["loss"]["focal_gamma"],
        giou_weight=config["loss"]["giou_weight"],
    )
    loss, metrics = validate(model, loader, criterion, device)
    digest = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    report = {
        "evidence": "host_model_evaluation",
        "hardware_measured": False,
        "checkpoint_sha256": digest,
        "phase": phase,
        "profile": profile,
        "images": len(dataset),
        "validation_loss": loss,
        **metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
