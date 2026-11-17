# Architecture

## Functional path

```text
BDD100K -> float student -> QAT profiles -> generated parameter package
                                                    |
RGB 320x320 -> AXI DMA -> HLS preprocess -> quantized detector -> AXI DMA
                                                    |
                                         INT16 P3/P4 tensors
                                                    |
                              Cortex-A9 decode + class-wise NMS
                                                    |
                                      EDZ2 protocol response
```

The deployed student uses only 3x3 and 1x1 dense convolutions, ReLU6,
nearest-neighbour upsampling, addition, and two anchor-free heads. The head
layout is six class logits, centerness, and four box distances at 20x20 and
10x10, producing exactly 5,500 INT16 values.

## Hardware partition

The laptop letterboxes input to 320x320 RGB. The PL performs exact 2x2 area
reduction, normalization, quantized convolution, feature fusion, and head
generation. The ARM performs sigmoid conversion, thresholding, top-K
selection, box decoding, and NMS. This keeps irregular control flow in
software while preserving the dominant convolution work in PL.

Intermediate feature maps and the selected profile's weights are packed into
on-chip memories whenever the resource gates permit. One reusable
output-stationary PE/SIMD engine processes layers sequentially; dataflow is
used inside load/compute/store regions instead of instantiating a full engine
per layer.

## Build profiles

- `accuracy`: W8A8 layers, INT32 accumulators, INT16 heads.
- `eco`: W8A8 first/head layers and W4A4 interior layers.

The profile, input resolution, layer shapes, scales, CRC, and model hash are
generated from a single configuration and must agree across Python, C, HLS,
Vivado metadata, and the network protocol.

