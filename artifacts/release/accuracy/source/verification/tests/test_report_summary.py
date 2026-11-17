from benchmarks.summarize_reports import parse_hls, parse_timing, parse_utilization


def test_hls_summary_is_explicitly_an_estimate() -> None:
    report = """
|ap_clk  |  10.00 ns|  7.535 ns| 2.70 ns|
|  100000|  100000|  1.000 ms| 1.000 ms| 100001| 100001| no|
|Total            |       20|    30|    4000|   5000|    0|
"""
    result = parse_hls(report)
    assert result["evidence"] == "hls_estimate"
    assert result["latency_cycles"] == 100000
    assert result["estimated_fps"] == 1000.0
    assert result["resources"]["dsp"] == 30


def test_timing_summary_is_not_hardware_measurement() -> None:
    result = parse_timing("WNS(ns) TNS(ns)\n------- -------\n 0.125 0.000\n")
    assert result == {"evidence": "post_route_static_timing", "wns_ns": 0.125}


def test_vivado_resource_table_is_normalized_to_bram18k() -> None:
    report = """
| Slice LUTs*       | 12345 | 0 | 53200 | 23.2 |
| Block RAM Tile    | 80.5  | 0 | 140   | 57.5 |
| DSPs              | 100   | 0 | 220   | 45.4 |
"""
    assert parse_utilization(report) == {"lut": 12345, "bram18k": 161, "dsp": 100}
