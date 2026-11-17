from __future__ import annotations

import torch
import torch.nn.functional as F

from .constants import STRIDES
from .losses import boxes_from_ltrb, grid_locations


def box_iou(boxes1: torch.Tensor, boxes2: torch.Tensor) -> torch.Tensor:
    if boxes1.numel() == 0 or boxes2.numel() == 0:
        return boxes1.new_zeros((boxes1.shape[0], boxes2.shape[0]))
    lt = torch.maximum(boxes1[:, None, :2], boxes2[None, :, :2])
    rb = torch.minimum(boxes1[:, None, 2:], boxes2[None, :, 2:])
    intersection = (rb - lt).clamp_min(0).prod(2)
    area1 = (boxes1[:, 2:] - boxes1[:, :2]).clamp_min(0).prod(1)
    area2 = (boxes2[:, 2:] - boxes2[:, :2]).clamp_min(0).prod(1)
    return intersection / (area1[:, None] + area2[None, :] - intersection).clamp_min(1e-7)


def nms(boxes: torch.Tensor, scores: torch.Tensor, threshold: float) -> torch.Tensor:
    order = scores.argsort(descending=True)
    keep: list[torch.Tensor] = []
    while order.numel():
        current = order[0]
        keep.append(current)
        if order.numel() == 1:
            break
        remaining = order[1:]
        order = remaining[box_iou(boxes[current : current + 1], boxes[remaining])[0] <= threshold]
    return torch.stack(keep) if keep else torch.empty(0, dtype=torch.long, device=boxes.device)


def decode_detections(
    outputs: tuple[torch.Tensor, torch.Tensor],
    score_threshold: float = 0.25,
    nms_iou_threshold: float = 0.45,
    top_k: int = 100,
    image_size: int = 160,
) -> list[dict[str, torch.Tensor]]:
    results = []
    for batch in range(outputs[0].shape[0]):
        boxes_all, scores_all, labels_all = [], [], []
        for head, stride in zip(outputs, STRIDES):
            prediction = head[batch].permute(1, 2, 0).reshape(-1, 11)
            locations = grid_locations(head.shape[2], head.shape[3], stride, head.device)
            class_prob = prediction[:, :6].sigmoid()
            centerness = prediction[:, 6].sigmoid().unsqueeze(1)
            score_matrix = torch.sqrt(class_prob * centerness)
            selected_cells, selected_classes = torch.where(score_matrix >= score_threshold)
            if selected_cells.numel():
                distances = F.softplus(prediction[selected_cells, 7:11]) * stride
                boxes = boxes_from_ltrb(locations[selected_cells], distances).clamp(0, image_size)
                boxes_all.append(boxes)
                scores_all.append(score_matrix[selected_cells, selected_classes])
                labels_all.append(selected_classes)
        if not boxes_all:
            empty = outputs[0].new_empty((0,))
            results.append({"boxes": empty.reshape(0, 4), "scores": empty, "labels": empty.to(torch.long)})
            continue
        boxes = torch.cat(boxes_all)
        scores = torch.cat(scores_all)
        labels = torch.cat(labels_all)
        pre_top = min(top_k, scores.numel())
        selection = scores.topk(pre_top).indices
        boxes, scores, labels = boxes[selection], scores[selection], labels[selection]
        keep_parts = []
        for class_id in range(6):
            class_indices = torch.where(labels == class_id)[0]
            if class_indices.numel():
                keep_parts.append(class_indices[nms(boxes[class_indices], scores[class_indices], nms_iou_threshold)])
        keep = torch.cat(keep_parts) if keep_parts else torch.empty(0, dtype=torch.long, device=boxes.device)
        keep = keep[scores[keep].argsort(descending=True)[:top_k]]
        results.append({"boxes": boxes[keep], "scores": scores[keep], "labels": labels[keep]})
    return results
