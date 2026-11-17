# EdgeDet-Z20 client and virtual board

Install the protocol/server package alone:

```powershell
py -3.10 -m pip install -e client
python -m client.virtual_board --fragment-size 7
```

In another terminal, install dashboard extras and run the camera client:

```powershell
py -3.10 -m pip install -e "client[dashboard]"
python -m client.dashboard --host 127.0.0.1 --source 0
```

If PySide6 is unavailable, add `--cli`; the program also falls back to CLI
automatically. Switching to a physical board only changes `--host`; add
`--hardware-target` so the truth label reflects the target.

The default virtual backend is a deterministic integer-only transport smoke
model, not a trained detector. It marks diagnostic records with flag `0x8000`.
Use `--backend package.module:factory` to load the exported trained integer
reference once that package is available. The factory result must expose
`name` and `infer(rgb_bytes)` and return `ReferenceResult`.
The dashboard accepts the same interface through `--float-backend` and renders
the local float result beside the remote quantized result; without one it states
that comparison is unconfigured rather than fabricating output.
The repository supplies `model.virtual_backend:create_backend` for an exported
integer package and `model.float_backend:create_backend` for a float checkpoint;
set `EDGEDET_MODEL_PACKAGE` and `EDGEDET_FLOAT_CHECKPOINT`, respectively.

Fault-injection options include response fragmentation, fixed latency,
periodic disconnect, periodic CRC corruption, and periodic timeout. They are
intended for client recovery and soak tests.

Every virtual screen and console says **VIRTUAL BOARD — NOT HARDWARE
MEASUREMENT**. The cycle values from the virtual server are host elapsed time
scaled as a simulated 100 MHz counter; they are never FPGA or ARM measurements.
