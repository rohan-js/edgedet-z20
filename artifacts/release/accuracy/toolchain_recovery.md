# AMD toolchain recovery on this host

The repository preflight discovered two host conditions on 2026-07-14 that
must be corrected before long HLS/Vivado runs are trustworthy:

1. Windows reports drive `D:` as `HealthStatus=Warning` and
   `OperationalStatus=Full Repair Needed`.
2. The modular installation omitted the product-local `data`, `tps`, and
   `win64` directory links expected by the Windows launchers. The repository
   can construct a reversible overlay under `C:\fpga_build\edgedet_z20\amd_shim`,
   but the AMD installation should still be repaired after the volume is
   healthy.
3. The Zynq part name is present in the catalog, but both HLS `set_part` and a
   minimal Vivado project fail while initializing the device library. Repair
   **Zynq-7000 device support** in the AMD installer; a catalog-name match alone
   is not sufficient.

From an **Administrator** terminal, first run:

```powershell
chkdsk D: /scan
```

Follow the command's repair recommendation. If it requires an offline repair,
close applications using `D:` and run the recommended `chkdsk D: /f` operation;
Windows may schedule it for restart. Do not start a multi-hour implementation
while the volume reports `Full Repair Needed`.

After the filesystem is healthy, open the AMD installer in modify/repair mode
and repair the 2025.2 installation. Ensure **Vivado**, **Vitis HLS**, **Vitis
Embedded Development**, **Zynq-7000 device support**, and **cable drivers** are
selected.

Then validate from the repository root:

```powershell
.\scripts\check_environment.ps1 -FailOnError
```

The generated diagnostic is written to
`artifacts/work/toolchain_preflight.json`. Only begin HLS synthesis after it
reports `ready: true`.
