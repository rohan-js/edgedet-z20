# Host verification log

Running record of host-side verification evidence. Every entry here is
host/virtual evidence; no entry in this file may be quoted as a hardware
measurement (see `limitations.md`).

## 2026-11-17 — host test suite

- Environment: Windows 10.0.19045 x64, Python 3.13 (host suite only; the
  pinned reproducibility target remains Python 3.10 per `README.md`).
- Command: `python -m pytest`
- Result: **31 passed** in 22.24 s — client protocol / virtual-board suites
  and verification dataset / model / quantization / variant suites.
- Prior state: `.pytest_cache` held 31 cached nodeids with no `lastfailed`
  entries, i.e. no previously recorded failures.

## 2026-11-17 — 10,000-frame transport soak

- Command: `python -m verification.soak_virtual_board --frames 10000 --fragment-size 7`
- Result: PASSED — frames = 10000, elapsed 16.31 s, **613.24 FPS host
  transport only**, RSS growth 106,496 B, dropped frames 0.
- Output: `artifacts/work/verification/virtual_board_soak.json`
  (packaged copy + SHA-256 recorded in
  `artifacts/release/accuracy/manifest.json`).
- Labels in the artifact: `evidence: host_virtual_transport`,
  `hardware_measured: false`. This throughput is a host-socket transport
  figure and must never be presented as an FPGA or ARM result.

## 2026-11-17 — release repackage

- Command: `python scripts/package_release.py --profile accuracy`
- `artifacts/release/accuracy/manifest.json` regenerated with the fresh soak
  and preflight records.
- Honest missing list: bitstream, xsa, elf, model_package, hls_model_header,
  runtime_model_header, metrics, vivado_reports, hls_reports.
- `physical_board_tested: false` recorded in the manifest.

## Host environment status

- AMD 2025.2 toolchain preflight: `ready: false` — D: volume health warning
  and Zynq-7000 device-library initialization failure; recovery procedure in
  `docs/toolchain_recovery.md`.
- `chkdsk D: /scan` (2026-11-17): metadata-only NTFS damage, **0 KB bad
  sectors, 0 orphaned files**; Windows requires an offline repair
  (`chkdsk /f`). Recovery sequence before any HLS/Vivado run: healthy volume
  → repair/modify the 2025.2 installation (Zynq-7000 device support) →
  `scripts/check_environment.ps1 -FailOnError` until `ready: true`.
