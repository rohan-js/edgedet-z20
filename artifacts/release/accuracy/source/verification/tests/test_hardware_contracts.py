import re
from pathlib import Path

from model.constants import PREPROCESS_BIAS, PREPROCESS_FRACTION_BITS, PREPROCESS_MULTIPLIER


ROOT = Path(__file__).resolve().parents[2]


def test_hls_preprocessing_constants_match_python_contract():
    text = (ROOT / "accelerator/include/model_config.hpp").read_text(encoding="utf-8")
    multipliers = tuple(map(int, re.search(r"kInputMultiplier\[3\] = \{([^}]+)\}", text).group(1).split(",")))
    biases = tuple(map(int, re.search(r"kInputBias\[3\] = \{([^}]+)\}", text).group(1).split(",")))
    shift = int(re.search(r"kInputRightShift = (\d+)", text).group(1))
    assert multipliers == PREPROCESS_MULTIPLIER
    assert biases == PREPROCESS_BIAS
    assert shift == PREPROCESS_FRACTION_BITS


def test_fixed_address_and_stream_abi_are_consistent():
    address = (ROOT / "platform/include/edgedet_address_map.h").read_text(encoding="utf-8")
    assert "0x43C00000U" in address and "0x40400000U" in address
    assert "0x10000000U" in address and "0x10100000U" in address
    assert "0x00064000U" in address and "0x00002AF8U" in address
    types = (ROOT / "accelerator/include/edgedet_types.hpp").read_text(encoding="utf-8")
    assert "kOutputValues == 5500" in types
    assert "kPixelsPerInputWord = 2" in types
    block_design = (ROOT / "platform/tcl/create_block_design.tcl").read_text(encoding="utf-8")
    assert "CONFIG.C_EXT_RESET_HIGH {0}" in block_design
    assert "CONFIG.NUM_PORTS {3}" in block_design


def test_deferred_tool_entrypoints_exist_and_never_substitute_artifacts():
    expected = (
        "accelerator/run_hls.tcl",
        "platform/tcl/build_platform.tcl",
        "platform/vitis/build_software.tcl",
        "platform/vitis/build_software.py",
    )
    assert all((ROOT / item).is_file() for item in expected)
    package_script = (ROOT / "scripts/package_release.py").read_text(encoding="utf-8")
    assert '"physical_board_tested": False' in package_script
    assert 'manifest["missing"]' in package_script
