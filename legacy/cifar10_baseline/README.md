# Real-Time Object Detection Using Hardware-Accelerated CNN on Xilinx Zynq FPGA with Arm Processor

A hardware/software co-design project implementing real-time CNN inference on the ZedBoard (Zynq XC7Z020), using Vitis HLS for FPGA acceleration with performance comparison against CPU-only execution on the ARM Cortex-A9.

## System Architecture

```
┌──────────────┐    Ethernet    ┌─────────────────────────────────────────────┐
│   Laptop     │◄──────────────►│              ZedBoard                      │
│  ┌────────┐  │                │  ┌──────────────┐  ┌────────────────────┐  │
│  │ Webcam │  │                │  │ ARM Cortex-A9│  │   FPGA Fabric      │  │
│  │ Client │  │                │  │  (PS)        │  │   (PL)             │  │
│  │        │  │   Frame data   │  │ ┌──────────┐ │  │ ┌────────────────┐ │  │
│  │ OpenCV │──┼───────────────►│  │ │Preprocess│─┼──►─│ Conv1+ReLU     │ │  │
│  │ Display│◄─┼────────────────│  │ │          │ │  │ │ MaxPool1       │ │  │
│  └────────┘  │   Results      │  │ │Postproc  │◄┼──┤ │ Conv2+ReLU     │ │  │
└──────────────┘                │  │ └──────────┘ │  │ │ MaxPool2       │ │  │
                                │  └──────────────┘  │ │ FC Layer       │ │  │
                                │                    │ └────────────────┘ │  │
                                │                    └────────────────────┘  │
                                └─────────────────────────────────────────────┘
```

## Project Structure

```
├── hls/                          # Vitis HLS CNN Accelerator
│   ├── src/
│   │   ├── cnn_types.h           # Fixed-point types & constants
│   │   ├── conv2d.cpp            # Conv2D layers with fused ReLU
│   │   ├── maxpool.cpp           # 2×2 MaxPool layers
│   │   ├── fc_layer.cpp          # Fully connected + argmax
│   │   └── cnn_top.cpp           # Top-level accelerator (synthesis target)
│   ├── tb/
│   │   └── test_cnn.cpp          # HLS testbench
│   └── run_hls.tcl               # HLS build automation script
│
├── vivado/                       # FPGA Design
│   ├── create_block_design.tcl   # Vivado block design automation
│   └── zedboard_constraints.xdc  # Pin assignments from datasheet
│
├── sw/                           # ARM Bare-Metal Software
│   ├── src/
│   │   ├── main.c                # Main app + CPU baseline + benchmarks
│   │   └── weights.h             # CNN weight loader
│   └── weights/                  # Exported weight files (.inc)
│
├── training/                     # Model Training (Host PC)
│   └── train_model.py            # PyTorch CIFAR-10 training + weight export
│
├── laptop/                       # Laptop Client
│   ├── camera_client.py          # Webcam capture + display
│   └── dataset_test.py           # CIFAR-10/COCO evaluation
│
└── docs/                         # Documentation
    ├── architecture.md
    └── performance_report.md
```

## CNN Architecture

| Layer | Type | Input | Output | Parameters |
|-------|------|-------|--------|------------|
| 1 | Conv2D 3×3 + ReLU | 3×32×32 | 16×30×30 | 448 |
| 2 | MaxPool 2×2 | 16×30×30 | 16×15×15 | 0 |
| 3 | Conv2D 3×3 + ReLU | 16×15×15 | 32×13×13 | 4,640 |
| 4 | MaxPool 2×2 | 32×13×13 | 32×6×6 | 0 |
| 5 | Fully Connected | 1,152 | 10 | 11,530 |
| **Total** | | | | **16,618** |

- **Precision**: 16-bit fixed-point (`ap_fixed<16,6>`) — 4× less resources than float32
- **Dataset**: CIFAR-10 (10 classes: airplane, automobile, bird, cat, deer, dog, frog, horse, ship, truck)

## Hardware Platform

- **Board**: ZedBoard (Avnet)
- **SoC**: Xilinx Zynq XC7Z020-1CLG484
- **PS**: Dual ARM Cortex-A9 @ 667 MHz
- **PL**: 85K logic cells, 140 BRAM (36Kb), 220 DSP48
- **Memory**: 512 MB DDR3
- **Clock**: 100 MHz (PL), 33.33 MHz (PS)

## Quick Start

### 1. Train the Model (on laptop with GPU)
```bash
cd training
pip install torch torchvision
python train_model.py
```

### 2. Build HLS IP (requires Vitis HLS)
```bash
cd hls
vitis_hls -f run_hls.tcl
```

### 3. Build FPGA Design (requires Vivado)
```bash
cd vivado
vivado -mode batch -source create_block_design.tcl
```

### 4. Build ARM Application (requires Vitis SDK)
Open Vitis → Import XSA → Create bare-metal app → Add `sw/src/` files

### 5. Run Demo
```bash
# On laptop
cd laptop
python camera_client.py --ip <ZEDBOARD_IP>
```

## Performance Targets

| Metric | Target | Measured |
|--------|--------|----------|
| Inference Latency | <100 ms | TBD |
| Throughput | >10 FPS | TBD |
| Speedup vs CPU | ≥2× | TBD |
| Accuracy (CIFAR-10) | >60% | TBD |
| Power | Documented | TBD |

## Tools Required

| Tool | Version | Purpose |
|------|---------|---------|
| Vivado ML Edition | 2022.1+ | FPGA synthesis |
| Vitis HLS | 2022.1+ | C++ → RTL |
| Vitis SDK | 2022.1+ | ARM software |
| Python | 3.8+ | Training & client |
| PyTorch | 1.12+ | CNN training |
| OpenCV | 4.5+ | Image processing |

## License

This project is developed for the Arm Bharat AI SoC Student Challenge.
