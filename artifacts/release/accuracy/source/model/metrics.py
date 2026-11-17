from __future__ import annotations

from dataclasses import dataclass

import torch

from .constants import CLASSES
from .postprocess import box_iou


def _average_precision(recall: torch.Tensor, precision: torch.Tensor) -> float:
    mrec = torch.cat((recall.new_tensor([0.0]), recall, recall.new_tensor([1.0])))
    mpre = torch.cat((precision.new_tensor([0.0]), precision, precision.new_tensor([0.0])))
    for index in range(mpre.numel() - 2, -1, -1):
        mpre[index] = torch.maximum(mpre[index], mpre[index + 1])
    points = torch.where(mrec[1:] != mrec[:-1])[0]
    return float(torch.sum((mrec[points + 1] - mrec[points]) * mpre[points + 1]))


@dataclass
class DetectionMetrics:
    map50: float
    map50_95: float
    precision: float
    recall: float
    f1: float
    per_class_ap50: dict[str, float]


def evaluate_detections(predictions: list[dict], targets: list[dict]) -> DetectionMetrics:
    if len(predictions) != len(targets):
        raise ValueError("predictions and targets must have the same length")
    thresholds = torch.arange(0.5, 0.951, 0.05)
    ap_table = torch.full((len(CLASSES), len(thresholds)), float("nan"))
    total_tp50 = total_fp50 = total_gt = 0
    for class_id, class_name in enumerate(CLASSES):
        gt_by_image: dict[int, torch.Tensor] = {}
        total_class_gt = 0
        candidates = []
        for image_id, (prediction, target) in enumerate(zip(predictions, targets)):
            gt = target["boxes"][target["labels"] == class_id].cpu()
            gt_by_image[image_id] = gt
            total_class_gt += gt.shape[0]
            selected = prediction["labels"] == class_id
            for box, score in zip(prediction["boxes"][selected].cpu(), prediction["scores"][selected].cpu()):
                candidates.append((float(score), image_id, box))
        total_gt += total_class_gt
        candidates.sort(key=lambda item: item[0], reverse=True)
        if total_class_gt == 0:
            continue
        for threshold_index, threshold in enumerate(thresholds):
            matched = {image_id: torch.zeros(len(boxes), dtype=torch.bool) for image_id, boxes in gt_by_image.items()}
            tp = torch.zeros(len(candidates))
            fp = torch.zeros(len(candidates))
            for candidate_index, (_, image_id, box) in enumerate(candidates):
                gt = gt_by_image[image_id]
                if gt.numel() == 0:
                    fp[candidate_index] = 1
                    continue
                ious = box_iou(box.unsqueeze(0), gt)[0]
                value, match = ious.max(0)
                if value >= threshold and not matched[image_id][match]:
                    tp[candidate_index] = 1
                    matched[image_id][match] = True
                else:
                    fp[candidate_index] = 1
            tp_cumulative = tp.cumsum(0)
            fp_cumulative = fp.cumsum(0)
            recall = tp_cumulative / max(total_class_gt, 1)
            precision = tp_cumulative / (tp_cumulative + fp_cumulative).clamp_min(1e-9)
            ap_table[class_id, threshold_index] = _average_precision(recall, precision)
            if threshold_index == 0:
                total_tp50 += int(tp.sum())
                total_fp50 += int(fp.sum())
    valid50 = ap_table[:, 0][~torch.isnan(ap_table[:, 0])]
    valid_all = ap_table[~torch.isnan(ap_table)]
    precision = total_tp50 / max(total_tp50 + total_fp50, 1)
    recall = total_tp50 / max(total_gt, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return DetectionMetrics(
        map50=float(valid50.mean()) if valid50.numel() else 0.0,
        map50_95=float(valid_all.mean()) if valid_all.numel() else 0.0,
        precision=precision,
        recall=recall,
        f1=f1,
        per_class_ap50={name: (0.0 if torch.isnan(ap_table[i, 0]) else float(ap_table[i, 0])) for i, name in enumerate(CLASSES)},
    )

