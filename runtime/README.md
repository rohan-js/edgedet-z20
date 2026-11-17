# EdgeDet-Z20 runtime

This directory owns the portable wire protocol, CRC32, detector postprocessing,
and the standalone Cortex-A9 integration scaffold. The host library has no OS or
Xilinx dependency and is the executable specification for protocol v1.

Wire values are big-endian. A request header is 36 bytes, a response header is
44 bytes, and each detection record is 24 bytes. CRC32 is the standard IEEE
polynomial and covers the encoded header excluding its final CRC field followed
by the payload.

Build the portable library and tests:

```powershell
cmake -S runtime -B D:\fpga_build\edgedet_z20\runtime-host -DBUILD_TESTING=ON
cmake --build D:\fpga_build\edgedet_z20\runtime-host
ctest --test-dir D:\fpga_build\edgedet_z20\runtime-host --output-on-failure
```

`baremetal/` is deliberately isolated from the host build. Import its sources,
the portable `include/` and `src/` files into a Vitis 2025.2 standalone
application after generating the BSP from the final XSA.
