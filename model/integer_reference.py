from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np

from .constants import OUTPUT_VALUES
from .quantization import requantize, unpack_int4


def _conv2d_integer(source: np.ndarray, weight: np.ndarray, bias: np.ndarray, stride: int, padding: int) -> np.ndarray:
    source = np.asarray(source, dtype=np.int32)
    weight = np.asarray(weight, dtype=np.int32)
    padded = np.pad(source, ((0, 0), (padding, padding), (padding, padding)))
    kernel_h, kernel_w = weight.shape[2:]
    windows = np.lib.stride_tricks.sliding_window_view(padded, (kernel_h, kernel_w), axis=(1, 2))
    windows = windows[:, ::stride, ::stride, :, :]
    accumulator = np.tensordot(weight.astype(np.int64), windows.astype(np.int64), axes=((1, 2, 3), (0, 3, 4)))
    accumulator += bias.astype(np.int64)[:, None, None]
    return accumulator


def run_integer_graph(manifest: dict, arrays: dict[str, np.ndarray], input_tensor: np.ndarray, return_intermediates=False):
    if input_tensor.shape != (3, 160, 160) or input_tensor.dtype != np.int8:
        raise ValueError("integer reference input must be int8 CHW 3x160x160")
    values: dict[str, np.ndarray] = {"input": input_tensor}
    for operation in manifest["graph"]:
        if operation["type"] == "upsample_add":
            lateral = np.repeat(np.repeat(values[operation["inputs"][1]], 2, axis=1), 2, axis=2)
            summed = values[operation["inputs"][0]].astype(np.int16) + lateral.astype(np.int16)
            qmax = (1 << operation["activation_bits"]) - 1
            values[operation["output"]] = np.clip(summed, 0, qmax).astype(np.uint8)
            continue
        weight_record = operation["weight"]
        if weight_record["packed_int4"]:
            weight = unpack_int4(arrays[weight_record["key"]], weight_record["count"]).reshape(weight_record["shape"])
        else:
            weight = arrays[weight_record["key"]].astype(np.int8).reshape(weight_record["shape"])
        accumulator = _conv2d_integer(
            values[operation["input"]], weight, arrays[operation["bias_key"]], operation["stride"], operation["padding"]
        )
        multiplier = arrays[operation["multiplier_key"]]
        shift = arrays[operation["shift_key"]]
        # Requantizer uses channel-first per-output-channel parameters.
        quantized = requantize(accumulator, multiplier[:, None, None], shift, operation["output_bits"], operation["signed"])
        dtype = np.int16 if operation["output_bits"] == 16 else (np.int8 if operation["signed"] else np.uint8)
        values[operation["output"]] = quantized.astype(dtype)
    head20, head10 = values["head20"], values["head10"]
    flat = np.concatenate((head20.transpose(1, 2, 0).reshape(-1), head10.transpose(1, 2, 0).reshape(-1))).astype(np.int16)
    if flat.size != OUTPUT_VALUES:
        raise AssertionError(f"model ABI requires {OUTPUT_VALUES} outputs, got {flat.size}")
    if return_intermediates:
        return flat, values
    return flat


@dataclass
class IntegerReference:
    manifest: dict
    arrays: dict[str, np.ndarray]

    @classmethod
    def load(cls, package: str | Path) -> "IntegerReference":
        arrays: dict[str, np.ndarray] = {}
        with zipfile.ZipFile(package, "r") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            for name in archive.namelist():
                if name.startswith("arrays/") and name.endswith(".npy"):
                    arrays[name[7:-4]] = np.load(BytesIO(archive.read(name)), allow_pickle=False)
        return cls(manifest, arrays)

    def run(self, input_tensor: np.ndarray, return_intermediates: bool = False):
        return run_integer_graph(self.manifest, self.arrays, input_tensor, return_intermediates)

    def dequantized_heads(self, input_tensor: np.ndarray):
        _, values = self.run(input_tensor, True)
        scale = float(self.manifest["quantization"]["output_scale"])
        head20 = values["head20"].astype(np.float32) * scale
        head10 = values["head10"].astype(np.float32) * scale
        return head20[None], head10[None]

