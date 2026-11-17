from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

from .constants import STRIDES


def grid_locations(height: int, width: int, stride: int, device=None) -> torch.Tensor:
    y, x = torch.meshgrid(
        torch.arange(height, device=device, dtype=torch.float32),
        torch.arange(width, device=device, dtype=torch.float32),
        indexing="ij",
    )
    return torch.stack(((x + 0.5) * stride, (y + 0.5) * stride), dim=-1).reshape(-1, 2)


def assign_fcos_targets(
    locations: torch.Tensor,
    boxes: torch.Tensor,
    labels: torch.Tensor,
    stride: int,
    regression_range: tuple[float, float],
    center_radius: float = 1.5,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    count = locations.shape[0]
    assigned_labels = torch.full((count,), -1, dtype=torch.long, device=locations.device)
    assigned_ltrb = torch.zeros((count, 4), dtype=torch.float32, device=locations.device)
    assigned_centerness = torch.zeros((count,), dtype=torch.float32, device=locations.device)
    if boxes.numel() == 0:
        return assigned_labels, assigned_ltrb, assigned_centerness
    boxes = boxes.to(locations.device)
    labels = labels.to(locations.device)
    x, y = locations[:, 0:1], locations[:, 1:2]
    l = x - boxes[None, :, 0]
    t = y - boxes[None, :, 1]
    r = boxes[None, :, 2] - x
    b = boxes[None, :, 3] - y
    distances = torch.stack((l, t, r, b), dim=2)
    inside = distances.amin(dim=2) > 0
    maximum = distances.amax(dim=2)
    in_range = (maximum >= regression_range[0]) & (maximum < regression_range[1])
    center_x = (boxes[:, 0] + boxes[:, 2]) * 0.5
    center_y = (boxes[:, 1] + boxes[:, 3]) * 0.5
    radius = stride * center_radius
    center_ok = (torch.abs(x - center_x) <= radius) & (torch.abs(y - center_y) <= radius)
    valid = inside & in_range & center_ok
    areas = ((boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])).expand(count, -1).clone()
    areas[~valid] = math.inf
    smallest, indices = areas.min(dim=1)
    positive = torch.isfinite(smallest)
    if positive.any():
        chosen = distances[torch.arange(count, device=locations.device), indices]
        assigned_ltrb[positive] = chosen[positive]
        assigned_labels[positive] = labels[indices[positive]]
        pos = chosen[positive]
        lr = pos[:, [0, 2]]
        tb = pos[:, [1, 3]]
        assigned_centerness[positive] = torch.sqrt(
            (lr.min(1).values / lr.max(1).values.clamp_min(1e-6))
            * (tb.min(1).values / tb.max(1).values.clamp_min(1e-6))
        )
    return assigned_labels, assigned_ltrb, assigned_centerness


def sigmoid_focal_loss(logits: torch.Tensor, targets: torch.Tensor, alpha: float, gamma: float) -> torch.Tensor:
    probability = logits.sigmoid()
    bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    p_t = probability * targets + (1 - probability) * (1 - targets)
    alpha_t = alpha * targets + (1 - alpha) * (1 - targets)
    return alpha_t * (1 - p_t).pow(gamma) * bce


def boxes_from_ltrb(locations: torch.Tensor, ltrb: torch.Tensor) -> torch.Tensor:
    return torch.stack(
        (locations[:, 0] - ltrb[:, 0], locations[:, 1] - ltrb[:, 1], locations[:, 0] + ltrb[:, 2], locations[:, 1] + ltrb[:, 3]),
        dim=1,
    )


def aligned_giou_loss(predicted: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    intersect_lt = torch.maximum(predicted[:, :2], target[:, :2])
    intersect_rb = torch.minimum(predicted[:, 2:], target[:, 2:])
    intersection = (intersect_rb - intersect_lt).clamp_min(0).prod(1)
    pred_area = (predicted[:, 2:] - predicted[:, :2]).clamp_min(0).prod(1)
    target_area = (target[:, 2:] - target[:, :2]).clamp_min(0).prod(1)
    union = pred_area + target_area - intersection
    iou = intersection / union.clamp_min(1e-7)
    cover_lt = torch.minimum(predicted[:, :2], target[:, :2])
    cover_rb = torch.maximum(predicted[:, 2:], target[:, 2:])
    cover_area = (cover_rb - cover_lt).clamp_min(0).prod(1)
    giou = iou - (cover_area - union) / cover_area.clamp_min(1e-7)
    return 1 - giou


@dataclass
class LossResult:
    total: torch.Tensor
    classification: torch.Tensor
    centerness: torch.Tensor
    regression: torch.Tensor
    positives: int


class EdgeDetLoss(nn.Module):
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, giou_weight: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.giou_weight = giou_weight
        self.ranges = ((0.0, 64.0), (64.0, float("inf")))

    def forward(self, outputs: tuple[torch.Tensor, torch.Tensor], targets: list[dict]) -> LossResult:
        classification_loss = outputs[0].new_zeros(())
        centerness_loss = outputs[0].new_zeros(())
        regression_loss = outputs[0].new_zeros(())
        positive_total = 0
        for batch_index, target in enumerate(targets):
            for level, (head, stride) in enumerate(zip(outputs, STRIDES)):
                prediction = head[batch_index].permute(1, 2, 0).reshape(-1, 11)
                locations = grid_locations(head.shape[2], head.shape[3], stride, head.device)
                labels, target_ltrb, target_center = assign_fcos_targets(
                    locations, target["boxes"], target["labels"], stride, self.ranges[level]
                )
                positive = labels >= 0
                positive_total += int(positive.sum())
                class_target = torch.zeros_like(prediction[:, :6])
                if positive.any():
                    class_target[positive, labels[positive]] = 1
                classification_loss = classification_loss + sigmoid_focal_loss(
                    prediction[:, :6], class_target, self.alpha, self.gamma
                ).sum()
                if positive.any():
                    centerness_loss = centerness_loss + F.binary_cross_entropy_with_logits(
                        prediction[positive, 6], target_center[positive], reduction="sum"
                    )
                    predicted_ltrb = F.softplus(prediction[positive, 7:11]) * stride
                    pred_boxes = boxes_from_ltrb(locations[positive], predicted_ltrb)
                    target_boxes = boxes_from_ltrb(locations[positive], target_ltrb[positive])
                    regression_loss = regression_loss + (
                        aligned_giou_loss(pred_boxes, target_boxes) * target_center[positive]
                    ).sum()
        normalizer = max(positive_total, 1)
        classification_loss = classification_loss / normalizer
        centerness_loss = centerness_loss / normalizer
        regression_loss = regression_loss / normalizer
        total = classification_loss + centerness_loss + self.giou_weight * regression_loss
        return LossResult(total, classification_loss, centerness_loss, regression_loss, positive_total)

