# EdgeDet-Z20

EdgeDet-Z20 is a hardware-ready, six-class road-safety detector for the
ZedBoard's XC7Z020 SoC. It replaces the original CIFAR-10 classifier with a
quantized anchor-free detector, a custom Vitis HLS accelerator, a bare-metal
runtime contract, and a virtual-board demonstration that can be exercised
without physical FPGA hardware.

Detected classes are `person`, `bicycle`, `motorcycle`, `car`, `bus`, and
`truck`.

> **Evidence boundary:** this repository is developed without a physical
> ZedBoard. C simulation, RTL co-simulation, synthesis, implementation, and
> host-reference timings are valid within their stated scope. Board FPS,
> Cortex-A9 speedup, temperature, and board power are **not measured** and must
> not be presented as such.

## Repository layout

| Directory | Purpose |
|---|---|
| `model/` | BDD100K conversion, model, training, QAT/export and integer reference |
| `accelerator/` | Vitis HLS AXI-stream accelerator and C/RTL verification |
| `platform/` | Vivado Zynq PS + AXI DMA design and Vitis application build |
| `runtime/` | Portable protocol/post-processing code and bare-metal runtime |
| `client/` | Virtual-board server and desktop dashboard |
| `verification/` | Cross-layer golden vectors and regression tests |
| `benchmarks/` | Parsers and report summaries; estimates remain labeled |
| `docs/` | Architecture, verification, reproduction and limitations |
| `legacy/cifar10_baseline/` | Preserved original classifier prototype |

## Original résumé project — CIFAR-10 classifier (complete artifacts)

The published résumé bullet **"Hardware-Accelerated CNN Inference on Xilinx Zynq
SoC (HW/SW Co-Design)"** refers to the original classifier phase, preserved
complete under [`legacy/cifar10_baseline/`](legacy/cifar10_baseline/README.md):
the Vitis HLS C synth report and exported IP (`hls_output/`, incl.
`cnn_top_csynth.rpt` and `hdl/verilog/cnn_top.v`), the Vivado bitstream and XSA
(`vivado_output/cnn_system_wrapper.bit` + `.xsa`), Arm bare-metal software and
weights, training code, and the laptop camera client. Its claims, numbers, and a
written interview guide are documented in
[`docs/resume_project_context.md`](docs/resume_project_context.md). All latency
and resource figures there are HLS synthesis estimates — no physical board was
measured (`docs/limitations.md`).

## Quick start without AMD tools

Use Python 3.10 for the pinned environment. Python 3.11–3.13 may work for the
lightweight host tests but are not the reproducibility target.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\base.txt
python -m pip install -r requirements\train.txt
python -m pip install -r requirements\client.txt
python -m pytest
```

Run the functional virtual-board demonstration in two terminals:

```powershell
python -m client.edgedet.virtual_board --host 127.0.0.1 --port 5001
python -m client.edgedet.dashboard --host 127.0.0.1 --port 5001 --source 0
```

The dashboard must display `VIRTUAL BOARD — NOT HARDWARE MEASUREMENT`.

After training/export, run the actual integer package and float comparison:

```powershell
$env:EDGEDET_MODEL_PACKAGE = 'artifacts\work\accuracy\edgedet-accuracy.edz'
$env:EDGEDET_FLOAT_CHECKPOINT = 'checkpoints\student\best.pt'
python -m client.edgedet.virtual_board --backend model.virtual_backend:create_backend
python -m client.edgedet.dashboard --float-backend model.float_backend:create_backend --profile accuracy --source 0
```

## Dataset and training

Download the official BDD100K detection images and labels separately. No
dataset is committed to this repository.

```powershell
python -m model.prepare_bdd100k --train-labels D:\datasets\bdd100k\labels\train.json --train-images D:\datasets\bdd100k\images\train --final-test-labels D:\datasets\bdd100k\labels\val.json --final-test-images D:\datasets\bdd100k\images\val --output D:\datasets\edgedet_z20
python -m model.train --config config\edgedet_z20.yaml --train-manifest D:\datasets\edgedet_z20\train.jsonl --validation-manifest D:\datasets\edgedet_z20\validation.jsonl --output checkpoints\student
python -m model.export --config config\edgedet_z20.yaml --checkpoint checkpoints\student\best.pt --profile accuracy --package artifacts\work\accuracy\edgedet-accuracy.edz --hls-header artifacts\work\accuracy\generated_model.hpp
```

GPU training is intended for Kaggle or Colab. See
[`docs/reproducibility.md`](docs/reproducibility.md).

## AMD tool flow

Vivado/Vitis 2025.2 is required. Builds are staged outside the long repository
path under `D:\fpga_build\edgedet_z20`.

```powershell
.\scripts\check_environment.ps1 -FailOnError
.\scripts\build_hls.ps1 -Profile accuracy -PE 8 -SIMD 8
.\scripts\build_vivado.ps1 -Profile accuracy
.\scripts\build_software.ps1 -Profile accuracy
```

The wrappers discover both the classic and the 2025.2 modular Windows install
layouts; the tools do not need to be manually added to `PATH`. If the tools,
device files, HLS task library, or target volume are unhealthy, the commands
stop with a clear diagnostic and never fabricate artifacts. See
[`docs/toolchain_recovery.md`](docs/toolchain_recovery.md) for the recovery
procedure used on this host.

## Release package

```powershell
python scripts\package_release.py --profile accuracy
```

The release manifest records SHA-256 hashes and distinguishes generated,
estimated, simulated, and unavailable evidence.
