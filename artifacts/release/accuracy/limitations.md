# Limitations and evidence policy

This project has no physical ZedBoard available during development.

## Valid evidence

- Dataset metrics produced from committed evaluation code and named model
  checkpoints.
- Bit-exact Python/C/HLS results for committed golden vectors.
- HLS latency and initiation-interval estimates, labeled as estimates.
- C/RTL co-simulation pass/fail results.
- Vivado post-route timing and utilization reports.
- Vivado power estimates only when their switching-activity coverage and
  confidence are reported.
- Host-reference and virtual-server timing, labeled with the host CPU.

## Unavailable evidence

- Measured FPGA or end-to-end board FPS.
- Cortex-A9 runtime or CPU-versus-FPGA speedup.
- Real DMA/cache-coherency behaviour.
- Ethernet throughput on the ZedBoard.
- Board temperature, total power, or energy per frame.
- Long-duration hardware stability.

QEMU or the virtual-board server cannot validate custom PL timing or DMA
coherency. No report, dashboard, slide, or README may silently substitute
host-reference data for hardware measurements.

