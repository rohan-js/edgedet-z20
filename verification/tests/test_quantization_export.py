import zipfile

import numpy as np
import torch

from model.export import build_export, default_golden_inputs, write_hls_header, write_package, write_runtime_header
from model.integer_reference import IntegerReference, run_integer_graph
from model.network import EdgeDetZ20
from model.quantization import divide_round_away, pack_int4, requantize, round_away_from_zero, unpack_int4
from model.virtual_backend import create_backend


def test_rounding_saturation_and_int4_pack():
    values = np.array([-2.5, -1.5, -0.5, 0.5, 1.5, 2.5])
    np.testing.assert_array_equal(round_away_from_zero(values), [-3, -2, -1, 1, 2, 3])
    raw = np.array([-8, -7, -1, 0, 1, 7, 3], dtype=np.int8)
    np.testing.assert_array_equal(unpack_int4(pack_int4(raw), raw.size), raw)
    np.testing.assert_array_equal(divide_round_away(np.array([-3, -1, 1, 3]), 1), [-2, -1, 1, 2])
    result = requantize(np.array([[-1000, 1000]]), 1, 0, 8, True)
    np.testing.assert_array_equal(result, [[-128, 127]])
    golden = default_golden_inputs()
    assert golden.shape == (3, 3, 160, 160) and golden.dtype == np.int8
    assert golden.min() == -128 and golden.max() == 127


def test_export_is_deterministic_header_has_hardware_contract_and_reference_runs(tmp_path):
    torch.manual_seed(7)
    model = EdgeDetZ20().eval()
    manifest, arrays = build_export(model, "eco", b"fixed-config")
    input_tensor = np.zeros((3, 160, 160), dtype=np.int8)
    expected = run_integer_graph(manifest, arrays, input_tensor)
    assert expected.shape == (5500,) and expected.dtype == np.int16
    first, second = tmp_path / "a.edz", tmp_path / "b.edz"
    write_package(first, manifest, arrays, input_tensor)
    write_package(second, manifest, arrays, input_tensor)
    assert first.read_bytes() == second.read_bytes()
    reference = IntegerReference.load(first)
    np.testing.assert_array_equal(reference.run(input_tensor), expected)
    with zipfile.ZipFile(first) as archive:
        assert {"manifest.json", "golden/inputs.npy", "golden/outputs.npy"}.issubset(archive.namelist())
    header = tmp_path / "generated_model.hpp"
    write_hls_header(header, manifest, arrays)
    text = header.read_text(encoding="utf-8")
    assert "#define EDZ_MODEL_WEIGHTS_PRESENT 1" in text
    assert "EDZ_MODEL_CRC32" in text and "stem_bias" in text and "head10_multiplier" in text
    assert "namespace edgedet { namespace generated" in text
    assert "inline weight8_t weight" in text and "kLayers[11]" in text
    assert manifest["preprocessing"]["integer_right_shift"] == 20
    runtime_header = tmp_path / "edz_model_runtime.h"
    write_runtime_header(runtime_header, manifest)
    runtime_text = runtime_header.read_text(encoding="utf-8")
    assert "EDZ_MODEL_PARAMETERS_PRESENT 1" in runtime_text
    assert f"0x{manifest['model_crc32']:08X}u" in runtime_text
    backend = create_backend(first)
    backend_result = backend.infer(bytes(320 * 320 * 3))
    assert "integer package" in backend.name and backend_result.elapsed_ns > 0
