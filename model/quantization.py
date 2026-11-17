from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import torch


def round_away_from_zero(value: torch.Tensor | np.ndarray | float):
    """Round to nearest, resolving exact half ties away from zero."""
    if isinstance(value, torch.Tensor):
        return torch.sign(value) * torch.floor(torch.abs(value) + 0.5)
    array = np.asarray(value)
    result = np.sign(array) * np.floor(np.abs(array) + 0.5)
    return result.item() if np.isscalar(value) else result


def saturate(value, bits: int, signed: bool = True):
    low = -(1 << (bits - 1)) if signed else 0
    high = (1 << (bits - (1 if signed else 0))) - 1
    if isinstance(value, torch.Tensor):
        return torch.clamp(value, low, high)
    return np.clip(value, low, high)


def symmetric_quantize(tensor: torch.Tensor, bits: int, *, per_channel: bool = False, axis: int = 0):
    qmax = (1 << (bits - 1)) - 1
    if per_channel:
        reduce_dims = tuple(i for i in range(tensor.ndim) if i != axis)
        maximum = tensor.detach().abs().amax(dim=reduce_dims, keepdim=True)
    else:
        maximum = tensor.detach().abs().amax()
    scale = torch.clamp(maximum / qmax, min=torch.finfo(torch.float32).eps)
    quantized = saturate(round_away_from_zero(tensor / scale), bits, True).to(torch.int8)
    return quantized, scale.squeeze()


def fake_quantize(tensor: torch.Tensor, bits: int, *, signed: bool, scale: float | None = None) -> torch.Tensor:
    qmin = -(1 << (bits - 1)) if signed else 0
    qmax = (1 << (bits - (1 if signed else 0))) - 1
    if scale is None:
        maximum = tensor.detach().abs().amax() if signed else tensor.detach().amax()
        scale_tensor = torch.clamp(maximum / max(qmax, 1), min=torch.finfo(torch.float32).eps)
    else:
        scale_tensor = tensor.new_tensor(scale)
    quant = torch.clamp(round_away_from_zero(tensor / scale_tensor), qmin, qmax)
    dequant = quant * scale_tensor
    return tensor + (dequant - tensor).detach()


def quantized_multiplier(real_multiplier: float, fractional_bits: int = 24) -> tuple[int, int]:
    if not math.isfinite(real_multiplier) or real_multiplier < 0:
        raise ValueError("multiplier must be finite and non-negative")
    multiplier = int(round_away_from_zero(real_multiplier * (1 << fractional_bits)))
    shift = fractional_bits
    while multiplier > 0x7FFFFFFF:
        multiplier = (multiplier + 1) // 2
        shift -= 1
    return multiplier, shift


def divide_round_away(numerator: np.ndarray, shift: int) -> np.ndarray:
    numerator = np.asarray(numerator, dtype=np.int64)
    if shift <= 0:
        return numerator << (-shift)
    offset = 1 << (shift - 1)
    return np.sign(numerator) * ((np.abs(numerator) + offset) >> shift)


def requantize(accumulator: np.ndarray, multiplier: np.ndarray | int, shift: np.ndarray | int, bits: int, signed: bool):
    product = np.asarray(accumulator, dtype=np.int64) * np.asarray(multiplier, dtype=np.int64)
    shifts = np.asarray(shift)
    if shifts.ndim == 0:
        rounded = divide_round_away(product, int(shifts))
    else:
        rounded = np.empty_like(product)
        for channel in range(product.shape[0]):
            rounded[channel] = divide_round_away(product[channel], int(shifts[channel]))
    return saturate(rounded, bits, signed)


def pack_int4(values: np.ndarray) -> np.ndarray:
    flat = np.asarray(values, dtype=np.int8).reshape(-1)
    if np.any(flat < -8) or np.any(flat > 7):
        raise ValueError("INT4 values must be in [-8, 7]")
    if flat.size % 2:
        flat = np.concatenate([flat, np.zeros(1, dtype=np.int8)])
    low = flat[0::2].astype(np.uint8) & 0x0F
    high = (flat[1::2].astype(np.uint8) & 0x0F) << 4
    return low | high


def unpack_int4(packed: np.ndarray, count: int) -> np.ndarray:
    packed = np.asarray(packed, dtype=np.uint8).reshape(-1)
    result = np.empty(packed.size * 2, dtype=np.int8)
    result[0::2] = (packed & 0x0F).astype(np.int8)
    result[1::2] = ((packed >> 4) & 0x0F).astype(np.int8)
    result[result >= 8] -= 16
    return result[:count]


@dataclass(frozen=True)
class QuantProfile:
    name: str
    interior_weight_bits: int
    interior_activation_bits: int
    first_last_weight_bits: int = 8
    first_activation_bits: int = 8
    output_bits: int = 16


PROFILES = {
    "accuracy": QuantProfile("accuracy", 8, 8),
    "eco": QuantProfile("eco", 4, 4),
}

