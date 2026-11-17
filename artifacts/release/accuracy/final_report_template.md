# EdgeDet-Z20 final report

## Reproducibility identifiers

- Source commit:
- Configuration hash:
- Dataset manifest hash:
- Float checkpoint SHA-256:
- QAT checkpoint SHA-256:
- Model-package CRC/SHA-256:
- Vivado/Vitis version:

## Accuracy

Populate only from `metrics.json`; include float, Accuracy, and Eco profiles
for three seeds.

## Verification

Record Python/C parity, HLS C simulation, RTL co-simulation, DRC, timing, and
software-build results with direct report paths.

## Implementation estimates

Report post-route resources, WNS/TNS, HLS cycles, and any activity-aware power
estimate. Every table must say `ESTIMATED — NO PHYSICAL BOARD`.

## Unavailable hardware measurements

Board FPS, p95 board latency, Cortex-A9 speedup, board power, temperature,
Ethernet throughput, DMA coherency, and soak stability are unavailable.

## Failure analysis

Include false positives, false negatives, small-object failures, night/weather
breakdowns, quantization disagreements, and implementation constraints.
