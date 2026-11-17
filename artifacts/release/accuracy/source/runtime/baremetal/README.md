# Cortex-A9 standalone integration

This is the hardware-facing scaffold, not evidence of execution on a ZedBoard.
Create a Vitis 2025.2 standalone application from the final XSA, enable lwIP's
socket API, and import:

- `runtime/include` and `runtime/src`
- `runtime/baremetal/include` and `runtime/baremetal/src`

The model exporter also generates `edz_model_runtime.h`. The software build
stages it over the checked-in host-test fallback, binding output scale, profile,
and model CRC to the same package used by HLS. Bare-metal compilation stops if
that generated metadata is absent.

Define `EDZ_XILINX_BAREMETAL`. `edz_board.c` intentionally stops compilation if
the generated BSP interrupt names do not match the expected block-design names;
map those macros after the XSA is final instead of silently using a wrong IRQ.
The adapter uses the fixed plan addresses, simple-mode AXI DMA, cache maintenance,
GIC interrupts, and a bounded timeout with DMA recovery.

`edz_tcp_server.c` implements a raw-lwIP protocol server, fragmented-request state
machine, two-frame DDR ring, CRC validation, accelerator timeout/error response,
postprocessing, and response serialization. `edz_platform_network.c` supplies
the standard standalone-lwIP/xadapter glue with static IP `192.168.1.10`; the
four `EDZ_IP_*` compiler definitions can override it. It deliberately shares
AMD's `xInterruptController` GIC instance so GEM, DMA, and accelerator handlers
remain installed together. If AMD changes that BSP symbol, compilation fails
until the adapter is mapped explicitly rather than silently creating a second
interrupt controller. The Python virtual board is the byte-level oracle.

No FPGA timing, ARM timing, power, temperature, or sustained FPS claim may be
derived from this scaffold.
