from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import (
    CANVAS_SIZE, CLASSES, HEAD_CHANNELS, INPUT_QUANT_SCALE, NETWORK_SIZE,
    NORMALIZE_MEAN, NORMALIZE_STD, OUTPUT_SCALE,
)


def _validate_contract(result: dict[str, Any]) -> None:
    if tuple(result.get("project", {}).get("classes", ())) != CLASSES:
        raise ValueError("configuration classes do not match the fixed six-class ABI")
    data = result.get("data", {})
    if data.get("canvas_size") != CANVAS_SIZE or data.get("network_size") != NETWORK_SIZE:
        raise ValueError("configuration input sizes do not match the active accelerator ABI")
    if float(data.get("input_quant_scale", -1)) != INPUT_QUANT_SCALE:
        raise ValueError("configuration input scale does not match fixed-point preprocessing")
    if tuple(data.get("normalize_mean", ())) != NORMALIZE_MEAN or tuple(data.get("normalize_std", ())) != NORMALIZE_STD:
        raise ValueError("configuration normalization does not match fixed-point preprocessing")
    model = result.get("model", {})
    if model.get("num_classes") != len(CLASSES) or model.get("head_values_per_cell") != HEAD_CHANNELS:
        raise ValueError("configuration head shape does not match the detector ABI")
    if float(result.get("quantization", {}).get("output_scale", -1)) != OUTPUT_SCALE:
        raise ValueError("configuration output scale does not match portable postprocessing")


def load_config(path: str | Path) -> dict[str, Any]:
    """Load YAML when available, with JSON accepted for minimal environments."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        result = json.loads(text)
        _validate_contract(result)
        return result
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised only in minimal installs
        raise RuntimeError("PyYAML is required for YAML configs; use JSON instead") from exc
    result = yaml.safe_load(text)
    if not isinstance(result, dict):
        raise ValueError("configuration root must be a mapping")
    _validate_contract(result)
    return result
