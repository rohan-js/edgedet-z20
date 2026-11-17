"""Create a hash-addressed release without inventing unavailable evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("accuracy", "eco"), default="accuracy")
    parser.add_argument("--build-root", type=Path, default=Path(r"D:\fpga_build\edgedet_z20"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/release"))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    release = (repo / args.output / args.profile).resolve()
    release.mkdir(parents=True, exist_ok=True)

    candidates = {
        "bitstream": args.build_root / f"vivado_{args.profile}/artifacts/edgedet_z20.bit",
        "xsa": args.build_root / f"vivado_{args.profile}/artifacts/edgedet_z20.xsa",
        "elf": args.build_root / f"vitis_{args.profile}/edgedet_app/Debug/edgedet_app.elf",
        "model_package": repo / f"artifacts/work/{args.profile}/edgedet-{args.profile}.edz",
        "hls_model_header": repo / f"artifacts/work/{args.profile}/generated_model.hpp",
        "runtime_model_header": repo / f"artifacts/work/{args.profile}/edz_model_runtime.h",
        "metrics": repo / f"artifacts/work/{args.profile}/metrics.json",
        "virtual_board_soak": repo / "artifacts/work/verification/virtual_board_soak.json",
        "toolchain_preflight": repo / "artifacts/work/toolchain_preflight.json",
    }
    manifest: dict[str, object] = {
        "project": "EdgeDet-Z20",
        "profile": args.profile,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "physical_board_tested": False,
        "files": {},
        "missing": [],
    }
    for label, source in candidates.items():
        if source.is_file():
            destination = release / source.name
            shutil.copy2(source, destination)
            manifest["files"][label] = {
                "file": destination.name,
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
            }
        else:
            manifest["missing"].append({"artifact": label, "expected": str(source)})

    for document in (
        "README.md", "pyproject.toml", "docs/architecture.md",
        "docs/dataset_card.md", "docs/final_report_template.md",
        "docs/limitations.md", "docs/model_card.md",
        "docs/reproducibility.md", "docs/third_party.md",
        "docs/toolchain_recovery.md", "docs/verification.md",
    ):
        source = repo / document
        destination = release / source.name
        shutil.copy2(source, destination)
        manifest["files"][document] = {
            "file": destination.name,
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
        }

    report_roots = {
        "vivado_reports": args.build_root / f"vivado_{args.profile}/reports",
        "hls_reports": args.build_root / f"hls_{args.profile}_pe8_simd8/build/hls",
    }
    for group, root in report_roots.items():
        copied = 0
        if root.is_dir():
            for source in sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in {".rpt", ".xml", ".log"}):
                relative = source.relative_to(root)
                destination = release / "reports" / group / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                label = f"{group}/{relative.as_posix()}"
                manifest["files"][label] = {
                    "file": destination.relative_to(release).as_posix(),
                    "sha256": sha256(destination),
                    "bytes": destination.stat().st_size,
                    "evidence": "tool_report_not_physical_measurement",
                }
                copied += 1
        if copied == 0:
            manifest["missing"].append({"artifact": group, "expected": str(root)})

    source_roots = (
        repo / "config",
        repo / "model",
        repo / "accelerator",
        repo / "platform",
        repo / "runtime",
        repo / "client/edgedet",
        repo / "verification",
        repo / "scripts",
        repo / "requirements",
    )
    allowed_suffixes = {".py", ".c", ".h", ".hpp", ".cpp", ".tcl", ".ps1", ".yaml", ".md", ".txt", ".toml"}
    for root in source_roots:
        for source in sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in allowed_suffixes):
            if "__pycache__" in source.parts:
                continue
            relative = source.relative_to(repo)
            destination = release / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            label = f"source/{relative.as_posix()}"
            manifest["files"][label] = {
                "file": destination.relative_to(release).as_posix(),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
                "evidence": "reproducibility_source",
            }
    (release / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(release / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
