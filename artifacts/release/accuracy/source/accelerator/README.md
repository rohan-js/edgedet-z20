# EdgeDet-Z20 accelerator

This directory defines the hardware-facing ABI and an HLS interface scaffold:

- 64-bit AXI4-Stream input, with two packed RGB888 pixels in bits `[47:0]`.
- Exactly 51,200 input words for one 320x320 frame; `TLAST` is required on the
  final word.
- Exact 2x2 area reduction to 160x160 and signed INT8 normalization.
- Fine (20x20) then coarse (10x10) tensors, 11 values per cell.
- Exactly 5,500 signed INT16 values packed four per 64-bit output word, with
  `TLAST` on output word 1,375.
- AXI4-Lite registers for frame ID, status, word/saturation counters, and an
  algorithmic work counter. `work_count` is not a physical cycle measurement.

## Honesty boundary

`include/model_config.hpp` has `EDZ_MODEL_WEIGHTS_PRESENT=0`. The checked-in
detector pools RGB cells and applies a tiny deterministic projection solely to
test preprocessing, DMA framing, decoding, and control software. It does **not**
execute the final trained network in `layer_schedule.hpp` and it must not be
reported as a road-safety model or as representative resource/performance data.
Status bit 31 remains set for every invocation.

The production path in `src/detector_full.cpp` executes the complete scheduled
3x3/1x1 backbone, requantized ReLU6 layers, lateral upsample-add, fine head, and
coarse head. The model export stage supplies `generated_model.hpp` using the
checked-in accessor contract (weights, biases, per-channel multiplier/shift,
activation limits, residual scaling), sets `EDZ_MODEL_WEIGHTS_PRESENT=1`, and
passes bit-exact layer-vector tests before release synthesis. Point
`EDZ_GENERATED_INCLUDE_DIR` at that package so its header precedes the checked-in
zero-valued contract stub. The HLS Tcl script stops after C simulation unless
`EDZ_ALLOW_PLACEHOLDER=1` is explicitly set for platform bring-up.

## HLS build

From a normal PowerShell prompt (the wrapper discovers Vitis 2025.2):

```powershell
.\accelerator\scripts\run_variants.ps1
```

That runs C simulation for all six profile/folding combinations. Interface-only
synthesis and IP export require the visibly unsafe opt-in:

```powershell
.\accelerator\scripts\run_variants.ps1 -Profile accuracy -AllowPlaceholder
```

Do not compare the resulting placeholder utilization reports to the project
acceptance thresholds. RTL co-simulation can be enabled with `-RunCosim`.
