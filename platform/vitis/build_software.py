"""Stage portable/bare-metal sources and invoke the XSCT application build."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xsa", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--xsct", default="xsct")
    parser.add_argument("--runtime-header", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    xsa = args.xsa.resolve()
    workspace = args.workspace.resolve()
    if not xsa.is_file():
        raise SystemExit(f"XSA not found: {xsa}")
    source_roots = (
        repo / "runtime/include",
        repo / "runtime/src",
        repo / "runtime/baremetal/include",
        repo / "runtime/baremetal/src",
    )
    stage = workspace / "staged_sources"
    stage.mkdir(parents=True, exist_ok=True)
    staged: list[dict[str, object]] = []
    for root in source_roots:
        if not root.is_dir():
            raise SystemExit(f"source directory missing: {root}")
        for source in sorted(path for path in root.rglob("*") if path.suffix.lower() in {".c", ".h"}):
            if source.name == "edz_model_runtime.h" and args.runtime_header:
                continue
            destination = stage / source.name
            if destination.exists() and destination.read_bytes() != source.read_bytes():
                raise SystemExit(f"staged filename collision: {source.name}")
            shutil.copy2(source, destination)
            staged.append({"source": str(source.relative_to(repo)), "sha256": _sha256(destination)})
    if args.runtime_header:
        runtime_header = args.runtime_header.resolve()
        if not runtime_header.is_file():
            raise SystemExit(f"generated runtime model header missing: {runtime_header}")
        destination = stage / "edz_model_runtime.h"
        shutil.copy2(runtime_header, destination)
        staged.append({"source": str(runtime_header), "sha256": _sha256(destination), "generated_model_metadata": True})
    manifest = {
        "xsa": str(xsa),
        "xsa_sha256": _sha256(xsa),
        "workspace": str(workspace),
        "physical_board_tested": False,
        "sources": staged,
    }
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "software_build_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if args.prepare_only:
        print(stage)
        return 0
    xsct = shutil.which(args.xsct) or (args.xsct if Path(args.xsct).is_file() else None)
    if not xsct:
        raise SystemExit("xsct is not available; activate the Vitis 2025.2 environment")
    tcl = Path(__file__).with_name("build_software.tcl")
    subprocess.run([str(xsct), str(tcl), str(xsa), str(workspace), str(stage)], check=True)
    elf_files = sorted(workspace.rglob("edgedet_app.elf"))
    if not elf_files:
        raise SystemExit("XSCT completed but edgedet_app.elf was not found")
    print(elf_files[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
