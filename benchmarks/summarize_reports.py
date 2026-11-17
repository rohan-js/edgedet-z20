"""Summarize HLS/Vivado reports without presenting estimates as measurements."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_hls(text: str) -> dict[str, object]:
    out: dict[str, object] = {"evidence": "hls_estimate"}
    latency = re.search(r"\|\s*(\d+)\|\s*\d+\|\s*[\d.]+\s*(?:ms|us|ns)", text)
    clock = re.search(r"\|ap_clk\s*\|\s*([\d.]+)\s*ns", text)
    util = re.search(
        r"\|Total\s*\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|",
        text,
    )
    if latency:
        out["latency_cycles"] = int(latency.group(1))
    if clock:
        out["clock_period_ns"] = float(clock.group(1))
    if util:
        out["resources"] = {
            "bram18k": int(util.group(1)),
            "dsp": int(util.group(2)),
            "ff": int(util.group(3)),
            "lut": int(util.group(4)),
        }
    if "latency_cycles" in out and "clock_period_ns" in out:
        seconds = out["latency_cycles"] * out["clock_period_ns"] * 1e-9
        out["estimated_fps"] = 1.0 / seconds
    return out


def parse_timing(text: str) -> dict[str, object]:
    out: dict[str, object] = {"evidence": "post_route_static_timing"}
    wns = re.search(r"WNS\(ns\).*?\n[-\s]+\n\s*(-?[\d.]+)", text, re.S)
    if wns:
        out["wns_ns"] = float(wns.group(1))
    return out


def parse_utilization(text: str) -> dict[str, int]:
    def used(label: str) -> float | None:
        match = re.search(rf"\|\s*{label}\*?\s*\|\s*([\d.]+)\s*\|", text, re.I)
        return float(match.group(1)) if match else None

    result: dict[str, int] = {}
    lut = used("Slice LUTs")
    dsp = used("DSPs")
    bram_tiles = used("Block RAM Tile")
    if lut is not None:
        result["lut"] = round(lut)
    if dsp is not None:
        result["dsp"] = round(dsp)
    if bram_tiles is not None:
        result["bram18k"] = round(bram_tiles * 2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("benchmark_summary.json"))
    parser.add_argument("--variant", default="unknown")
    parser.add_argument("--profile", choices=("accuracy", "eco", "unknown"), default="unknown")
    args = parser.parse_args()
    summary: dict[str, object] = {
        "hardware_measured": False,
        "warning": "No physical-board measurements are available.",
        "variant": args.variant,
        "profile": args.profile,
    }
    hls_reports = list(args.report_dir.rglob("*csynth*.rpt"))
    timing_reports = list(args.report_dir.rglob("*timing*.rpt"))
    utilization_reports = list(args.report_dir.rglob("*utilization*.rpt"))
    if hls_reports:
        summary["hls"] = parse_hls(hls_reports[0].read_text(errors="replace"))
    if timing_reports:
        summary["timing"] = parse_timing(timing_reports[0].read_text(errors="replace"))
        summary.update({key: value for key, value in summary["timing"].items() if key == "wns_ns"})
    if utilization_reports:
        summary["post_route_resources"] = parse_utilization(utilization_reports[0].read_text(errors="replace"))
        summary.update(summary["post_route_resources"])
    if "hls" in summary and "latency_cycles" in summary["hls"]:
        summary["latency_cycles"] = summary["hls"]["latency_cycles"]
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
