# EdgeDet-Z20 ML stack

The package implements the six-class BDD100K student model and its canonical
integer contract. Run commands from the repository root so `model` resolves as
a Python package.

```powershell
python -m model.prepare_bdd100k --train-labels <train.json> --train-images <train-images> `
  --final-test-labels <val.json> --final-test-images <val-images> --output data/manifests

python -m model.train --train-manifest data/manifests/train.jsonl `
  --validation-manifest data/manifests/validation.jsonl --output artifacts/student/seed-2026

python -m model.train --phase qat --profile accuracy --resume artifacts/student/seed-2026/best.pt `
  --train-manifest data/manifests/train.jsonl --validation-manifest data/manifests/validation.jsonl `
  --output artifacts/qat/accuracy-seed-2026

python -m model.export --checkpoint artifacts/qat/accuracy-seed-2026/best.pt --profile accuracy `
  --package artifacts/models/edgedet-accuracy.edz `
  --hls-header artifacts/models/generated_model.hpp

python -m model.evaluate --checkpoint artifacts/qat/accuracy-seed-2026/best.pt `
  --manifest data/manifests/final_test.jsonl --output artifacts/models/final-test-metrics.json
```

Kaggle should use a GPU notebook, install `requirements/train.txt`, attach
BDD100K as a private dataset, and persist each seed's `best.pt`, `history.json`,
and final-test metrics as notebook outputs. The official 10,000-image validation
partition is only used for the final test.

For teacher distillation, fine-tune a COCO-pretrained YOLOX-S on the same six
mapped classes and export a TorchScript adapter returning a dictionary with
`head20` (N×11×20×20), `head10` (N×11×10×10), and unrestricted-channel
`feature20`/`feature10` maps. Pass it with `--teacher-torchscript`; training then
applies both response and spatial-attention feature distillation. Keeping this
adapter contract explicit prevents the student/export stack from depending on a
particular YOLOX repository revision.

`generated_model.hpp` is the accelerator hand-off contract. It defines
`EDZ_MODEL_WEIGHTS_PRESENT=1`, format/profile/version CRC macros, a `LayerDesc`,
and flattened weight, bias, multiplier, and shift arrays for every convolution.
INT4 weight arrays contain two signed nibbles per byte (low nibble first).

The repository cannot ship trained parameters without the BDD100K data and GPU
training run. An export from an untrained checkpoint is structurally valid but
must never be presented as an accuracy result.

`python -m model.run_experiments ...` executes every seed from the YAML and both
QAT profiles, while writing the exact command matrix to `experiment_plan.json`.
`python -m model.check_acceptance ...` enforces the 30% float mAP@0.5 floor and
the three-/five-point Accuracy/Eco QAT-loss limits; it emits an explicit
`fallback_192_required` signal instead of silently accepting a weak model.
