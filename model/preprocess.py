from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import torch
import torch.nn.functional as F

from .constants import (
    CANVAS_SIZE,
    INPUT_QUANT_SCALE,
    NETWORK_SIZE,
    NORMALIZE_MEAN,
    NORMALIZE_STD,
    PAD_RGB,
    PREPROCESS_BIAS,
    PREPROCESS_FRACTION_BITS,
    PREPROCESS_MULTIPLIER,
)
from .quantization import round_away_from_zero


@dataclass(frozen=True)
class LetterboxInfo:
    original_width: int
    original_height: int
    scale: float
    left: int
    top: int
    resized_width: int
    resized_height: int


def _as_chw_float(image: np.ndarray | torch.Tensor) -> torch.Tensor:
    if isinstance(image, np.ndarray) and not image.flags.writeable:
        image = image.copy()
    tensor = torch.as_tensor(image)
    if tensor.ndim != 3:
        raise ValueError("RGB image must have three dimensions")
    if tensor.shape[-1] == 3:
        tensor = tensor.permute(2, 0, 1)
    if tensor.shape[0] != 3:
        raise ValueError("RGB image must have exactly three channels")
    return tensor.to(torch.float32)


def letterbox_rgb(
    image: np.ndarray | torch.Tensor,
    boxes: np.ndarray | torch.Tensor | None = None,
    size: int = CANVAS_SIZE,
    pad_rgb: Iterable[int] = PAD_RGB,
) -> tuple[torch.Tensor, torch.Tensor | None, LetterboxInfo]:
    """Bilinearly resize RGB to a square canvas while retaining box geometry."""
    chw = _as_chw_float(image)
    height, width = int(chw.shape[1]), int(chw.shape[2])
    scale = min(size / width, size / height)
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    left = (size - resized_width) // 2
    top = (size - resized_height) // 2
    resized = F.interpolate(
        chw.unsqueeze(0), size=(resized_height, resized_width), mode="bilinear", align_corners=False
    ).squeeze(0)
    canvas = torch.empty((3, size, size), dtype=torch.float32)
    for channel, value in enumerate(pad_rgb):
        canvas[channel].fill_(float(value))
    canvas[:, top : top + resized_height, left : left + resized_width] = resized
    out_boxes = None
    if boxes is not None:
        out_boxes = torch.as_tensor(boxes, dtype=torch.float32).reshape(-1, 4).clone()
        if out_boxes.numel():
            out_boxes[:, 0::2] = out_boxes[:, 0::2] * scale + left
            out_boxes[:, 1::2] = out_boxes[:, 1::2] * scale + top
            out_boxes[:, 0::2].clamp_(0, size)
            out_boxes[:, 1::2].clamp_(0, size)
    info = LetterboxInfo(width, height, scale, left, top, resized_width, resized_height)
    return canvas, out_boxes, info


def exact_area_downsample_2x(image_320: torch.Tensor) -> torch.Tensor:
    """Exact 2x2 area reduction; uint8 inputs use round-half-up integer division."""
    if tuple(image_320.shape) != (3, CANVAS_SIZE, CANVAS_SIZE):
        raise ValueError(f"expected CHW RGB {CANVAS_SIZE}x{CANVAS_SIZE}")
    if image_320.dtype == torch.uint8:
        x = image_320.to(torch.int32)
        summed = x[:, 0::2, 0::2] + x[:, 0::2, 1::2] + x[:, 1::2, 0::2] + x[:, 1::2, 1::2]
        return ((summed + 2) // 4).to(torch.uint8)
    x = image_320.to(torch.float32)
    return (x[:, 0::2, 0::2] + x[:, 0::2, 1::2] + x[:, 1::2, 0::2] + x[:, 1::2, 1::2]) * 0.25


def quantize_reduced_rgb(reduced_u8: torch.Tensor) -> torch.Tensor:
    """Apply the canonical bit-exact fixed-point normalization to 160x160 RGB."""
    if tuple(reduced_u8.shape) != (3, NETWORK_SIZE, NETWORK_SIZE):
        raise ValueError(f"expected CHW RGB {NETWORK_SIZE}x{NETWORK_SIZE}")
    values = reduced_u8.to(torch.int64)
    multiplier = torch.tensor(PREPROCESS_MULTIPLIER, dtype=torch.int64).view(3, 1, 1)
    bias = torch.tensor(PREPROCESS_BIAS, dtype=torch.int64).view(3, 1, 1)
    scaled = values * multiplier + bias
    half = 1 << (PREPROCESS_FRACTION_BITS - 1)
    rounded = torch.sign(scaled) * ((torch.abs(scaled) + half) >> PREPROCESS_FRACTION_BITS)
    return torch.clamp(rounded, -128, 127).to(torch.int8)


def preprocess_rgb(
    image: np.ndarray | torch.Tensor,
    boxes: np.ndarray | torch.Tensor | None = None,
    *,
    quantized: bool = False,
) -> tuple[torch.Tensor, torch.Tensor | None, LetterboxInfo]:
    canvas, transformed_boxes, info = letterbox_rgb(image, boxes)
    # Freeze the hardware boundary to integer RGB before exact 2x2 reduction.
    canvas_u8 = torch.clamp(round_away_from_zero(canvas), 0, 255).to(torch.uint8)
    reduced_u8 = exact_area_downsample_2x(canvas_u8)
    reduced = reduced_u8.to(torch.float32) / 255.0
    mean = torch.tensor(NORMALIZE_MEAN, dtype=torch.float32).view(3, 1, 1)
    std = torch.tensor(NORMALIZE_STD, dtype=torch.float32).view(3, 1, 1)
    normalized = (reduced - mean) / std
    if quantized:
        normalized = quantize_reduced_rgb(reduced_u8)
    if transformed_boxes is not None:
        transformed_boxes = transformed_boxes * (NETWORK_SIZE / CANVAS_SIZE)
    return normalized, transformed_boxes, info


def undo_letterbox_boxes(boxes: torch.Tensor, info: LetterboxInfo) -> torch.Tensor:
    result = boxes.clone().to(torch.float32) * (CANVAS_SIZE / NETWORK_SIZE)
    result[:, 0::2] = (result[:, 0::2] - info.left) / info.scale
    result[:, 1::2] = (result[:, 1::2] - info.top) / info.scale
    result[:, 0::2].clamp_(0, info.original_width)
    result[:, 1::2].clamp_(0, info.original_height)
    return result
