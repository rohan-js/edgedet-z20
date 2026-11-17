"""Apply the model accuracy and QAT-loss release gates to metrics JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def check(float_map: float, accuracy_map: float, eco_map: float) -> dict:
    accuracy_loss = float_map - accuracy_map
    eco_loss = float_map - eco_map
    return {
        "float_map50": float_map,
        "accuracy_map50": accuracy_map,
        "eco_map50": eco_map,
        "float_floor_pass": float_map >= 0.30,
        "accuracy_qat_loss": accuracy_loss,
        "accuracy_qat_pass": accuracy_loss <= 0.03,
        "eco_qat_loss": eco_loss,
        "eco_qat_pass": eco_loss <= 0.05,
        "fallback_192_required": float_map < 0.30,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--float", dest="float_metrics", type=Path, required=True)
    parser.add_argument("--accuracy", type=Path, required=True)
    parser.add_argument("--eco", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in (args.float_metrics, args.accuracy, args.eco)]
    result = check(*(float(item["map50"]) for item in reports))
    result["evidence"] = "checkpoint_metrics_gate"
    result["hardware_measured"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    passed = result["float_floor_pass"] and result["accuracy_qat_pass"] and result["eco_qat_pass"]
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
