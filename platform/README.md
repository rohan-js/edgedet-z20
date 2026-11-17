# ZedBoard platform

The platform is a 100 MHz Zynq-7000 design with AXI DMA in simple mode:

```text
DDR --MM2S--> EdgeDet AXI stream --S2MM--> DDR
             + AXI-Lite control
```

PS `M_AXI_GP0` controls the DMA at `0x40400000` and detector at `0x43C00000`.
Both DMA memory masters share `S_AXI_HP0`. Runtime-reserved DDR buffers are
`0x10000000` (input, 409,600 bytes) and `0x10100000` (output, 11,000 bytes).
The TCP payload remains tightly packed 307,200-byte RGB888; portable runtime
code repacks each two pixels into one padded 64-bit accelerator word.
The linker script must not allocate program, heap, or stack over these buffers.

DMA MM2S, DMA S2MM, and accelerator-done interrupts occupy `IRQ_F2P[2:0]`.

## Prerequisites and build

Install the official Digilent ZedBoard board files before building. The Tcl flow
fails rather than silently using generic PS7 DDR/MIO settings when the board
preset is absent.

After exporting and expanding an HLS IP repository:

```powershell
.\platform\scripts\build_platform.ps1 `
  -Vivado D:\AMD\2025.2\Vivado\bin\vivado.bat `
  -IpRepository D:\fpga_build\edgedet_z20\ip_repo\accuracy_pe8_simd8
```

The flow uses one Vivado job and emits bitstream, XSA, post-route checkpoint,
timing/utilization/DRC reports, and a power estimate. A vectorless power report
is explicitly low-confidence. Even a SAIF-assisted report remains an estimate,
not measured ZedBoard power.

The repository-level build wrappers stage sources under the short build path.
Placeholder synthesis is never selected implicitly; it requires the explicit
`-AllowPlaceholder` switch and is suitable only for interface bring-up.

After all HLS variants have been exported, `run_platform_variants.ps1` builds
each available candidate independently. Normalize its reports and use
`benchmarks/select_variant.py`; do not select from HLS estimates alone.
