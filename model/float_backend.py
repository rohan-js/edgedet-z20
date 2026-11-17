"""Float-checkpoint adapter for side-by-side virtual dashboard comparison."""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import torch

from .network import EdgeDetZ20
from .postprocess import decode_detections
from .preprocess import preprocess_rgb


class FloatCheckpointBackend:
    def __init__(self, checkpoint: str | Path, device: str = "cpu"):
        self.device = torch.device(device)
        self.model = EdgeDetZ20().to(self.device)
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.model.load_state_dict(state["model"] if "model" in state else state)
        self.model.eval()
        self.name = f"float checkpoint ({Path(checkpoint).name}, {self.device})"

    @torch.inference_mode()
    def infer(self, rgb: bytes):
        from client.edgedet.protocol import Detection
        from client.edgedet.reference import ReferenceResult

        if len(rgb) != 320 * 320 * 3:
            raise ValueError("reference expects a 320x320 RGB888 frame")
        start = time.perf_counter_ns()
        image = np.frombuffer(rgb, dtype=np.uint8).reshape(320, 320, 3)
        tensor, _, _ = preprocess_rgb(image)
        outputs = self.model(tensor.unsqueeze(0).to(self.device))
        decoded = decode_detections(outputs, 0.25, 0.45, 100)[0]
        records = tuple(
            Detection(
                int(class_id), 0, float(score),
                float(box[0] / 160.0), float(box[1] / 160.0),
                float(box[2] / 160.0), float(box[3] / 160.0),
            )
            for box, score, class_id in zip(
                decoded["boxes"].cpu(), decoded["scores"].cpu(), decoded["labels"].cpu()
            )
        )
        return ReferenceResult(records, time.perf_counter_ns() - start)


def create_backend(checkpoint: str | Path | None = None) -> FloatCheckpointBackend:
    selected = checkpoint or os.environ.get("EDGEDET_FLOAT_CHECKPOINT")
    if not selected:
        raise RuntimeError("set EDGEDET_FLOAT_CHECKPOINT to a trained float checkpoint")
    return FloatCheckpointBackend(selected, os.environ.get("EDGEDET_FLOAT_DEVICE", "cpu"))
