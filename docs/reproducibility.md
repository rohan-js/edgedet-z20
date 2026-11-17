# Reproducibility

## Host setup

- Windows host, Python 3.10, Git, Vivado/Vitis 2025.2.
- AMD builds run with one worker under `D:\fpga_build\edgedet_z20`.
- Keep source data and tool installations on D:; the repository ignores raw
  datasets, checkpoints, generated projects, and logs.
- Configure a 32 GB Windows page file before Vivado implementation on the
  8 GB development host.

Run `scripts/check_environment.ps1 -FailOnError` before any AMD build. It
records versions, volume health, memory, resolved tool locations, Vivado/XSCT
startup, and the required HLS task library without changing the machine. The
machine-specific recovery steps are in `docs/toolchain_recovery.md`.

## Training

Training is run on Kaggle/Colab using `requirements/train.txt`, the canonical
YAML configuration, and explicit seeds. BDD100K is obtained from its official
portal and mounted read-only. Export checkpoints, metrics JSON, the generated
parameter package, and golden vectors as notebook outputs.

## Evidence chain

1. Float PyTorch checkpoint and metrics.
2. QAT checkpoint and metrics for each profile.
3. Versioned generated parameters plus CRC/hash.
4. Python integer-reference vectors.
5. Portable C comparison.
6. HLS C simulation and C/RTL co-simulation.
7. Vivado implementation reports and optional activity-aware power report.
8. Cross-compiled ELF and host-tested shared runtime code.

`scripts/package_release.py` refuses to describe a missing artifact as
successful and writes SHA-256 hashes for every included file.
