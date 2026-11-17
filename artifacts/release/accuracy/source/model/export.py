from __future__ import annotations

import argparse
import hashlib
import json
import re
import zlib
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .config import load_config

from .constants import (
    CLASSES,
    HEAD_CHANNELS,
    INPUT_QUANT_SCALE,
    NORMALIZE_MEAN,
    NORMALIZE_STD,
    OUTPUT_SCALE,
    OUTPUT_VALUES,
    PAD_RGB,
    PREPROCESS_BIAS,
    PREPROCESS_FRACTION_BITS,
    PREPROCESS_MULTIPLIER,
)
from .integer_reference import run_integer_graph
from .network import ConvBNReLU6, DetectionHead, EdgeDetZ20
from .quantization import PROFILES, pack_int4, quantized_multiplier, round_away_from_zero, symmetric_quantize


FORMAT_VERSION = 1
MODEL_VERSION = "edgedet-z20-v1"


def default_golden_inputs() -> np.ndarray:
    """Deterministic zero, extrema, and pseudo-random integer network inputs."""
    zero = np.zeros((3, 160, 160), dtype=np.int8)
    y, x = np.indices((160, 160))
    checker = np.empty_like(zero)
    for channel in range(3):
        checker[channel] = np.where(((x + y + channel) & 1) == 0, -128, 127)
    random = np.random.default_rng(2026).integers(-128, 128, size=zero.shape, dtype=np.int16).astype(np.int8)
    return np.stack((zero, checker, random))


def _npy_bytes(array: np.ndarray) -> bytes:
    stream = BytesIO()
    np.save(stream, array, allow_pickle=False)
    return stream.getvalue()


def _fold_conv_bn(module: ConvBNReLU6) -> tuple[torch.Tensor, torch.Tensor]:
    conv, bn = module.conv, module.bn
    factor = bn.weight / torch.sqrt(bn.running_var + bn.eps)
    weight = conv.weight * factor[:, None, None, None]
    bias = bn.bias - bn.running_mean * factor
    return weight.detach().cpu(), bias.detach().cpu()


def _layer_specs(model: EdgeDetZ20):
    return [
        ("stem", model.stem, "input", "stem", 2, 1, "first"),
        ("block2_down", model.block2_down, "stem", "block2_down", 2, 1, "interior"),
        ("block2_same", model.block2_same, "block2_down", "block2_same", 1, 1, "interior"),
        ("block3_down", model.block3_down, "block2_same", "block3_down", 2, 1, "interior"),
        ("block3_same", model.block3_same, "block3_down", "p3", 1, 1, "interior"),
        ("block4_down", model.block4_down, "p3", "block4_down", 2, 1, "interior"),
        ("block4_same", model.block4_same, "block4_down", "p4", 1, 1, "interior"),
        ("lateral", model.lateral, "p4", "lateral", 1, 0, "interior"),
        ("fuse", model.fuse, "fused_input", "fused", 1, 1, "interior"),
        ("head20", model.head20, "fused", "head20", 1, 0, "last"),
        ("head10", model.head10, "p4", "head10", 1, 0, "last"),
    ]


def build_export(model: EdgeDetZ20, profile_name: str, config_bytes: bytes = b"") -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    profile = PROFILES[profile_name]
    activation_bits = profile.interior_activation_bits
    activation_scale = 6.0 / ((1 << activation_bits) - 1)
    first_scale = 6.0 / 255.0
    tensor_scales = {"input": INPUT_QUANT_SCALE, "stem": first_scale}
    for name in ("block2_down", "block2_same", "block3_down", "p3", "block4_down", "p4", "lateral", "fused_input", "fused"):
        tensor_scales[name] = activation_scale
    arrays: dict[str, np.ndarray] = {}
    graph: list[dict[str, Any]] = []
    for name, module, input_name, output_name, stride, padding, role in _layer_specs(model):
        if name == "fuse":
            graph.append({"type": "upsample_add", "inputs": ["p3", "lateral"], "output": "fused_input", "activation_bits": activation_bits})
        if isinstance(module, ConvBNReLU6):
            weight, bias = _fold_conv_bn(module)
            out_bits = profile.first_activation_bits if role == "first" else profile.interior_activation_bits
            signed = False
            output_scale = first_scale if role == "first" else activation_scale
            weight_bits = profile.first_last_weight_bits if role == "first" else profile.interior_weight_bits
        elif isinstance(module, DetectionHead):
            weight = module.conv.weight.detach().cpu()
            bias = module.conv.bias.detach().cpu()
            out_bits, signed, output_scale, weight_bits = 16, True, OUTPUT_SCALE, profile.first_last_weight_bits
        else:  # pragma: no cover
            raise TypeError(module)
        qweight, weight_scale = symmetric_quantize(weight, weight_bits, per_channel=True)
        weight_scale_np = weight_scale.numpy().astype(np.float64)
        bias_q = round_away_from_zero(bias.numpy() / (tensor_scales[input_name] * weight_scale_np)).astype(np.int32)
        real_multipliers = tensor_scales[input_name] * weight_scale_np / output_scale
        multiplier_shift = [quantized_multiplier(float(value)) for value in real_multipliers]
        multipliers = np.array([item[0] for item in multiplier_shift], dtype=np.int32)
        shifts = np.array([item[1] for item in multiplier_shift], dtype=np.int8)
        raw_weight = qweight.numpy().astype(np.int8)
        weight_key = f"{name}_weights"
        packed = weight_bits == 4
        arrays[weight_key] = pack_int4(raw_weight) if packed else raw_weight.reshape(-1)
        arrays[f"{name}_bias"] = bias_q
        arrays[f"{name}_weight_scale"] = weight_scale.numpy().astype(np.float32)
        arrays[f"{name}_multiplier"] = multipliers
        arrays[f"{name}_shift"] = shifts
        tensor_scales[output_name] = output_scale
        graph.append(
            {
                "type": "conv2d",
                "name": name,
                "input": input_name,
                "output": output_name,
                "stride": stride,
                "padding": padding,
                "input_scale": tensor_scales[input_name],
                "output_scale": output_scale,
                "output_bits": out_bits,
                "signed": signed,
                "weight_bits": weight_bits,
                "weight": {"key": weight_key, "shape": list(raw_weight.shape), "count": raw_weight.size, "packed_int4": packed},
                "bias_key": f"{name}_bias",
                "weight_scale_key": f"{name}_weight_scale",
                "multiplier_key": f"{name}_multiplier",
                "shift_key": f"{name}_shift",
            }
        )
    manifest: dict[str, Any] = {
        "format": "EdgeDet-Z20 model package",
        "format_version": FORMAT_VERSION,
        "model_version": MODEL_VERSION,
        "profile": profile_name,
        "classes": list(CLASSES),
        "input": {"shape": [3, 160, 160], "dtype": "int8", "scale": INPUT_QUANT_SCALE},
        "output": {"values": OUTPUT_VALUES, "dtype": "int16", "scale": OUTPUT_SCALE, "order": "20x20x11 NHWC, then 10x10x11 NHWC"},
        "head": {"channels": HEAD_CHANNELS, "layout": ["class_logits[6]", "centerness", "ltrb[4]"]},
        "preprocessing": {
            "canvas": 320,
            "network": 160,
            "pad_rgb": list(PAD_RGB),
            "mean": list(NORMALIZE_MEAN),
            "std": list(NORMALIZE_STD),
            "area_downsample": "2x2 round-half-up",
            "integer_multiplier": list(PREPROCESS_MULTIPLIER),
            "integer_bias": list(PREPROCESS_BIAS),
            "integer_right_shift": PREPROCESS_FRACTION_BITS,
        },
        "quantization": {"rounding": "nearest, ties away from zero", "saturation": True, "output_scale": OUTPUT_SCALE},
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "graph": graph,
    }
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    for key in sorted(arrays):
        digest.update(key.encode())
        digest.update(_npy_bytes(arrays[key]))
    manifest["model_sha256"] = digest.hexdigest()
    manifest["model_crc32"] = zlib.crc32(digest.digest()) & 0xFFFFFFFF
    return manifest, arrays


def write_package(path: str | Path, manifest: dict, arrays: dict[str, np.ndarray], golden_inputs: np.ndarray | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = {"manifest.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()}
    for key, array in arrays.items():
        entries[f"arrays/{key}.npy"] = _npy_bytes(array)
    if golden_inputs is not None:
        golden_inputs = np.asarray(golden_inputs, dtype=np.int8)
        if golden_inputs.ndim == 3:
            golden_inputs = golden_inputs[None]
        outputs = np.stack([run_integer_graph(manifest, arrays, sample) for sample in golden_inputs])
        entries["golden/inputs.npy"] = _npy_bytes(golden_inputs)
        entries["golden/outputs.npy"] = _npy_bytes(outputs)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name])


def _cpp_array(name: str, array: np.ndarray, ctype: str) -> str:
    flat = array.reshape(-1)
    values = ",".join(str(int(value)) for value in flat)
    return f"static const {ctype} {name}[{flat.size}] = {{{values}}};\n"


def write_hls_header(path: str | Path, manifest: dict, arrays: dict[str, np.ndarray]) -> None:
    """Emit the generated_model.hpp ABI consumed by the accelerator build."""
    guard = "EDGEDET_Z20_GENERATED_MODEL_HPP"
    conv_operations = [item for item in manifest["graph"] if item["type"] == "conv2d"]
    config_hash_low = int(manifest["config_sha256"][:8], 16)
    lines = [
        f"#ifndef {guard}\n#define {guard}\n",
        "#include <stdint.h>\n#include <stddef.h>\n#include \"edgedet_types.hpp\"\n",
        "#define EDZ_MODEL_WEIGHTS_PRESENT 1\n",
        f"#define EDZ_MODEL_FORMAT_VERSION {manifest['format_version']}\n",
        f"#define EDZ_MODEL_VERSION \"{manifest['model_version']}\"\n",
        f"#define EDZ_MODEL_CRC32 0x{manifest['model_crc32']:08X}u\n",
        f"#define EDZ_MODEL_OUTPUT_VALUES {OUTPUT_VALUES}\n",
        f"#define EDZ_MODEL_PROFILE_{manifest['profile'].upper()} 1\n",
        "namespace edgedet_model {\n",
        "struct LayerDesc { const int8_t *w8; const uint8_t *w4; const int32_t *bias; const int32_t *multiplier; const int8_t *shift; uint32_t weight_count; uint16_t out_channels; uint16_t in_channels; uint8_t kernel; uint8_t weight_bits; uint8_t activation_max; };\n",
    ]
    descriptor_names: list[str] = []
    for operation in conv_operations:
        name = re.sub(r"\W", "_", operation["name"])
        descriptor_names.append(f"{name}_desc")
        weight = arrays[operation["weight"]["key"]]
        lines.append(_cpp_array(f"{name}_weights", weight, "uint8_t" if operation["weight_bits"] == 4 else "int8_t"))
        lines.append(_cpp_array(f"{name}_bias", arrays[operation["bias_key"]], "int32_t"))
        lines.append(_cpp_array(f"{name}_multiplier", arrays[operation["multiplier_key"]], "int32_t"))
        lines.append(_cpp_array(f"{name}_shift", arrays[operation["shift_key"]], "int8_t"))
        out_channels, in_channels, kernel, _ = operation["weight"]["shape"]
        pointer8 = f"{name}_weights" if operation["weight_bits"] == 8 else "nullptr"
        pointer4 = f"{name}_weights" if operation["weight_bits"] == 4 else "nullptr"
        activation_max = 0 if operation["signed"] else (1 << operation["output_bits"]) - 1
        lines.append(
            f"static const LayerDesc {name}_desc = "
            f"{{{pointer8},{pointer4},{name}_bias,{name}_multiplier,{name}_shift,"
            f"{operation['weight']['count']}u,{out_channels},{in_channels},{kernel},"
            f"{operation['weight_bits']},{activation_max}}};\n"
        )
    lines.append(
        f"static const LayerDesc kLayers[{len(descriptor_names)}] = "
        "{" + ",".join(descriptor_names) + "};\n"
        "} // namespace edgedet_model\n"
        "namespace edgedet { namespace generated {\n"
        f"constexpr unsigned kModelCrc = 0x{manifest['model_crc32']:08X}u;\n"
        f"constexpr unsigned kConfigHashLow = 0x{config_hash_low:08X}u;\n"
        "inline weight8_t weight(int layer, int oc, int ic, int ky, int kx) {\n"
        "  const edgedet_model::LayerDesc &d = edgedet_model::kLayers[layer];\n"
        "  const uint32_t index = (((static_cast<uint32_t>(oc) * d.in_channels + ic) * d.kernel + ky) * d.kernel + kx);\n"
        "  if (d.weight_bits == 8) return static_cast<weight8_t>(d.w8[index]);\n"
        "  const uint8_t packed = d.w4[index >> 1];\n"
        "  int8_t nibble = static_cast<int8_t>((index & 1u) ? (packed >> 4) : (packed & 0x0Fu));\n"
        "  if (nibble >= 8) nibble = static_cast<int8_t>(nibble - 16);\n"
        "  return static_cast<weight8_t>(nibble);\n"
        "}\n"
        "inline accumulator_t bias(int layer, int oc) { return static_cast<accumulator_t>(edgedet_model::kLayers[layer].bias[oc]); }\n"
        "inline ap_int<32> multiplier(int layer, int oc) { return static_cast<ap_int<32> >(edgedet_model::kLayers[layer].multiplier[oc]); }\n"
        "inline ap_uint<6> right_shift(int layer, int oc) { return static_cast<ap_uint<6> >(edgedet_model::kLayers[layer].shift[oc]); }\n"
        "inline feature_t activation_max(int layer, int oc) { (void)oc; return static_cast<feature_t>(edgedet_model::kLayers[layer].activation_max); }\n"
        "inline ap_int<32> residual_multiplier(int branch, int channel) { (void)branch; (void)channel; return 1; }\n"
        "inline ap_uint<6> residual_right_shift(int branch, int channel) { (void)branch; (void)channel; return 0; }\n"
        "} } // namespace edgedet::generated\n#endif\n"
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8", newline="\n")


def write_runtime_header(path: str | Path, manifest: dict) -> None:
    """Emit the small model metadata contract used by portable C and ARM."""
    profile = manifest["profile"]
    text = (
        "#ifndef EDZ_MODEL_RUNTIME_H\n#define EDZ_MODEL_RUNTIME_H\n\n"
        "#define EDZ_MODEL_PARAMETERS_PRESENT 1\n"
        f"#define EDZ_MODEL_CRC32 0x{manifest['model_crc32']:08X}u\n"
        f"#define EDZ_MODEL_PROFILE \"{profile}\"\n"
        f"#define EDZ_MODEL_OUTPUT_SCALE {float(manifest['output']['scale']):.9g}f\n"
        f"#define EDZ_MODEL_OUTPUT_VALUES {int(manifest['output']['values'])}u\n"
        "\n#endif\n"
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a QAT checkpoint to deterministic EDZ and HLS formats")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--hls-header", required=True, help="destination generated_model.hpp")
    parser.add_argument("--runtime-header", help="destination edz_model_runtime.h; defaults beside HLS header")
    parser.add_argument("--config", default="config/edgedet_z20.yaml")
    parser.add_argument("--golden-inputs", help="optional .npy int8 NCHW vectors")
    args = parser.parse_args()
    model = EdgeDetZ20()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model"] if "model" in checkpoint else checkpoint)
    model.eval()
    load_config(args.config)
    config_bytes = Path(args.config).read_bytes()
    manifest, arrays = build_export(model, args.profile, config_bytes)
    golden = np.load(args.golden_inputs, allow_pickle=False) if args.golden_inputs else default_golden_inputs()
    write_package(args.package, manifest, arrays, golden)
    write_hls_header(args.hls_header, manifest, arrays)
    runtime_header = args.runtime_header or str(Path(args.hls_header).with_name("edz_model_runtime.h"))
    write_runtime_header(runtime_header, manifest)


if __name__ == "__main__":
    main()
