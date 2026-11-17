"""Adapter from a trained EDZ package to the virtual-board backend protocol."""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import torch

from .integer_reference import IntegerReference
from .postprocess import decode_detections
from .preprocess import preprocess_rgb


class PackageIntegerBackend:
    def __init__(self, package: str | Path):
        self.reference = IntegerReference.load(package)
        profile = self.reference.manifest["profile"]
        version = self.reference.manifest["model_version"]
        self.name = f"{version} integer package ({profile})"

    def infer(self, rgb: bytes):
        # Import the transport records lazily: model export and verification remain
        # usable without putting the client package on PYTHONPATH.
        from client.edgedet.protocol import Detection
        from client.edgedet.reference import ReferenceResult

        if len(rgb) != 320 * 320 * 3:
            raise ValueError("reference expects a 320x320 RGB888 frame")
        start = time.perf_counter_ns()
        image = np.frombuffer(rgb, dtype=np.uint8).reshape(320, 320, 3)
        network_input, _, _ = preprocess_rgb(image, quantized=True)
        head20, head10 = self.reference.dequantized_heads(network_input.numpy())
        decoded = decode_detections(
            (torch.from_numpy(head20), torch.from_numpy(head10)),
            score_threshold=0.25,
            nms_iou_threshold=0.45,
            top_k=100,
        )[0]
        records = tuple(
            Detection(
                int(class_id),
                0,
                float(score),
                float(box[0] / 160.0),
                float(box[1] / 160.0),
                float(box[2] / 160.0),
                float(box[3] / 160.0),
            )
            for box, score, class_id in zip(decoded["boxes"], decoded["scores"], decoded["labels"])
        )
        return ReferenceResult(records, time.perf_counter_ns() - start)


def create_backend(package: str | Path | None = None) -> PackageIntegerBackend:
    """Factory compatible with ``--backend model.virtual_backend:create_backend``.

    The no-argument transport factory reads ``EDGEDET_MODEL_PACKAGE``. Direct
    callers may pass a package path explicitly for tests or embedded launchers.
    """
    selected = package or os.environ.get("EDGEDET_MODEL_PACKAGE")
    if not selected:
        raise RuntimeError("set EDGEDET_MODEL_PACKAGE to a trained .edz package")
    return PackageIntegerBackend(selected)

