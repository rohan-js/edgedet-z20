# ML verification

Run `python -m pytest verification/tests -q`. The suite covers BDD conversion
and grouped splitting, canonical preprocessing, model/loss/postprocessing,
quantization edge cases, deterministic packages, the generated HLS header, and
full integer-reference inference through all 11 convolution layers.

