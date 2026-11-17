# Benchmark evidence

Place generated reports under `artifacts/work/<profile>/reports`. Run
`python benchmarks/summarize_reports.py` to create a machine-readable summary.

Static cycle estimates are converted to an **estimated** FPS at the declared
clock. They are never labeled measured throughput. Power is included only when
the Vivado report identifies switching activity and confidence.

`select_variant.py` applies the fixed WNS, LUT, BRAM, DSP, and cycle gates to
normalized post-route candidate JSON and selects the lowest-latency eligible
variant.
