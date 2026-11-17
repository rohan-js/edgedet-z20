from benchmarks.select_variant import select


def test_selects_fastest_candidate_passing_every_gate():
    records = [
        {"variant": "4x8", "profile": "accuracy", "wns_ns": 0.5, "lut": 20000, "bram18k": 180, "dsp": 80, "latency_cycles": 2_000_000},
        {"variant": "8x8", "profile": "accuracy", "wns_ns": 0.1, "lut": 30000, "bram18k": 200, "dsp": 120, "latency_cycles": 1_000_000},
        {"variant": "8x16", "profile": "accuracy", "wns_ns": -0.1, "lut": 30000, "bram18k": 200, "dsp": 140, "latency_cycles": 700_000},
    ]
    selected, audited = select(records, "accuracy")
    assert selected["variant"] == "8x8"
    assert not audited[2]["eligible"] and "WNS < 0 ns" in audited[2]["failures"]


def test_returns_none_when_resource_limits_fail():
    selected, audited = select([
        {"variant": "bad", "profile": "eco", "wns_ns": 0, "lut": 39900, "bram18k": 1, "dsp": 1, "latency_cycles": 1}
    ], "eco")
    assert selected is None
    assert audited[0]["failures"] == ["lut >= 39900"]
