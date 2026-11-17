"""Run the configured three-seed float and QAT experiment matrix."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/edgedet_z20.yaml")
    parser.add_argument("--train-manifest", required=True)
    parser.add_argument("--validation-manifest", required=True)
    parser.add_argument("--final-test-manifest", default="")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--teacher-torchscript", default="")
    parser.add_argument("--device", default="")
    parser.add_argument("--profiles", nargs="+", choices=("accuracy", "eco"), default=("accuracy", "eco"))
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    args.output.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    for seed in config["training"]["seeds"]:
        float_output = args.output / f"float-seed-{seed}"
        command = [
            sys.executable, "-m", "model.train", "--config", args.config,
            "--train-manifest", args.train_manifest,
            "--validation-manifest", args.validation_manifest,
            "--output", str(float_output), "--seed", str(seed),
        ]
        if args.teacher_torchscript:
            command += ["--teacher-torchscript", args.teacher_torchscript]
        if args.device:
            command += ["--device", args.device]
        commands.append(command)
        if args.final_test_manifest:
            commands.append([
                sys.executable, "-m", "model.evaluate", "--config", args.config,
                "--checkpoint", str(float_output / "best.pt"),
                "--manifest", args.final_test_manifest,
                "--output", str(float_output / "final-test-metrics.json"),
                *(["--device", args.device] if args.device else []),
            ])
        for profile in args.profiles:
            qat_output = args.output / f"qat-{profile}-seed-{seed}"
            qat = [
                sys.executable, "-m", "model.train", "--config", args.config,
                "--train-manifest", args.train_manifest,
                "--validation-manifest", args.validation_manifest,
                "--output", str(qat_output), "--seed", str(seed),
                "--phase", "qat", "--profile", profile,
                "--resume", str(float_output / "best.pt"),
            ]
            if args.device:
                qat += ["--device", args.device]
            commands.append(qat)
            if args.final_test_manifest:
                commands.append([
                    sys.executable, "-m", "model.evaluate", "--config", args.config,
                    "--checkpoint", str(qat_output / "best.pt"),
                    "--manifest", args.final_test_manifest,
                    "--output", str(qat_output / "final-test-metrics.json"),
                    *(["--device", args.device] if args.device else []),
                ])
    manifest = {"seeds": config["training"]["seeds"], "commands": commands}
    (args.output / "experiment_plan.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if args.plan_only:
        print(args.output / "experiment_plan.json")
        return 0
    for command in commands:
        subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
