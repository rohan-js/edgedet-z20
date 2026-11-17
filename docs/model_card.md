# EdgeDet-Z20 model card

## Intended use

EdgeDet-Z20 is a research detector for six road-user classes on 320x320
letterboxed RGB frames, with a 160x160 quantized inference tensor. It is
designed to study FPGA hardware/model co-design on XC7Z020. It is not a
safety-certified driving system and must not control a vehicle.

## Variants

| Variant | Precision | Status |
|---|---|---|
| Float student | FP32 | Training required |
| Accuracy | W8A8 / INT32 accumulation | Training and export required |
| Eco | W8 first/head, W4A4 interior | Training and export required |

No accuracy value belongs in this table until it is produced by the committed
evaluation command and associated with a checkpoint hash.

## Evaluation

Report mAP@0.5, mAP@0.5:0.95, precision, recall, F1, per-class AP, size-based
AP, parameter count, operation count, and quantization loss. Use the held-out
official BDD100K validation images only for final evaluation.

## Risks

- 160x160 input can miss small or distant road users.
- BDD100K is not representative of every geography, climate, camera, or road.
- Combining `rider` with `person` creates overlapping semantic targets.
- Quantization and fixed-point box decoding can change low-confidence results.
- No physical-board execution has been validated.
