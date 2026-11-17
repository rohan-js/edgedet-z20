"""Select the fastest folding candidate that passes the XC7Z020 report gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


LIMITS = {"lut": 39_900, "bram18k": 224, "dsp": 154, "latency_cycles": 6_670_000}


def select(records: list[dict], profile: str) -> tuple[dict | None, list[dict]]:
    audited: list[dict] = []
    for source in records:
        if source.get("profile") != profile:
            continue
        failures: list[str] = []
        if float(source.get("wns_ns", float("-inf"))) < 0:
            failures.append("WNS < 0 ns")
        for resource in ("lut", "bram18k", "dsp"):
            if int(source.get(resource, 1 << 60)) >= LIMITS[resource]:
                failures.append(f"{resource} >= {LIMITS[resource]}")
        if int(source.get("latency_cycles", 1 << 60)) > LIMITS["latency_cycles"]:
            failures.append("latency cycle budget exceeded")
        audited.append({**source, "eligible": not failures, "failures": failures})
    eligible = [item for item in audited if item["eligible"]]
    selected = min(eligible, key=lambda item: (int(item["latency_cycles"]), -float(item["wns_ns"]))) if eligible else None
    return selected, audited


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path, help="normalized candidate JSON files")
    parser.add_argument("--profile", choices=("accuracy", "eco"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [json.loads(path.read_text(encoding="utf-8")) for path in args.reports]
    selected, audited = select(records, args.profile)
    result = {
        "evidence": "selection_from_post_route_reports",
        "hardware_measured": False,
        "profile": args.profile,
        "limits": LIMITS,
        "selected": selected,
        "candidates": audited,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
