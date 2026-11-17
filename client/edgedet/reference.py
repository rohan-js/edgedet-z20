"""Reference backends used by the virtual board.

The built-in backend is an integer-only transport smoke model. It is deliberately
not presented as trained detector accuracy. A trained integer reference can be
plugged in with ``--backend package.module:factory`` without changing protocol or
dashboard code; the factory must return an object with ``infer(rgb)``.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import time
from typing import Protocol

from .protocol import Detection


@dataclass(frozen=True)
class ReferenceResult:
    detections: tuple[Detection, ...]
    elapsed_ns: int


class ReferenceBackend(Protocol):
    name: str

    def infer(self, rgb: bytes) -> ReferenceResult: ...


class BuiltinIntegerReference:
    """Deterministic integer preprocessing/transport smoke backend.

    It finds a high-luma diagnostic region and marks records with flag 0x8000.
    This verifies framing and box rendering only; it is not an ML accuracy result.
    """

    name = "builtin-integer-smoke (not trained model accuracy)"

    def infer(self, rgb: bytes) -> ReferenceResult:
        if len(rgb) != 320 * 320 * 3:
            raise ValueError("reference expects a 320x320 RGB888 frame")
        start = time.perf_counter_ns()
        # Process 8x8 blocks with integer BT.601 luma. No floating-point inference.
        min_x, min_y, max_x, max_y = 320, 320, -1, -1
        bright_blocks = 0
        for by in range(0, 320, 8):
            for bx in range(0, 320, 8):
                total = 0
                for y in range(by, by + 8, 2):
                    row = y * 960
                    for x in range(bx, bx + 8, 2):
                        offset = row + x * 3
                        total += 77 * rgb[offset] + 150 * rgb[offset + 1] + 29 * rgb[offset + 2]
                mean_luma = (total + 2048) >> 12  # 16 samples and Q8 coefficients.
                if mean_luma >= 210:
                    bright_blocks += 1
                    min_x, min_y = min(min_x, bx), min(min_y, by)
                    max_x, max_y = max(max_x, bx + 8), max(max_y, by + 8)
        detections: tuple[Detection, ...] = ()
        if bright_blocks >= 4:
            score = min(0.99, 0.50 + bright_blocks / 3200.0)
            detections = (Detection(3, 0x8000, score, min_x / 320.0,
                                    min_y / 320.0, max_x / 320.0, max_y / 320.0),)
        return ReferenceResult(detections, time.perf_counter_ns() - start)


def load_backend(spec: str) -> ReferenceBackend:
    if spec in {"builtin", "builtin-integer-smoke"}:
        return BuiltinIntegerReference()
    if ":" not in spec:
        raise ValueError("backend must be 'builtin' or 'package.module:factory'")
    module_name, factory_name = spec.rsplit(":", 1)
    factory = getattr(importlib.import_module(module_name), factory_name)
    backend = factory()
    if not callable(getattr(backend, "infer", None)):
        raise TypeError("backend factory result must provide infer(rgb)")
    return backend
