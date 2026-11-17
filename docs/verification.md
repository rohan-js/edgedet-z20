# Verification matrix

| Layer | Required checks |
|---|---|
| Dataset | mapping, clipping, deterministic split, no train/test overlap |
| Float model | shapes, assignment, losses, decode, NMS, metrics |
| Quantization | rounding ties, saturation, overflow, INT4 packing, residual scales |
| Integer reference | deterministic intermediate and final tensors |
| Portable C | protocol, CRC, decode/NMS parity |
| HLS C | stream framing, preprocessing, layer/tensor parity |
| RTL co-sim | golden output, backpressure, TLAST and deadlock tests |
| Vivado | address map, DRC, timing, utilization, artifact hashes |
| Bare metal | cross-build, driver symbols, timeout/error paths |
| Virtual system | fragmentation, corrupt CRC, reconnect, 10k-frame soak |

The release gate is automated by `scripts/test_host.ps1` plus the AMD build
scripts. Hardware-only claims remain blocked until real board evidence exists.

Run the required transport soak independently of model speed:

```powershell
python -m verification.soak_virtual_board --frames 10000 --fragment-size 7
```

Its throughput is labeled host transport only and is not an FPGA or ARM result.
