from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F


@dataclass
class DistillationResult:
    total: torch.Tensor
    response: torch.Tensor
    feature: torch.Tensor


def _attention_map(feature: torch.Tensor) -> torch.Tensor:
    attention = feature.square().mean(dim=1).flatten(1)
    return F.normalize(attention, p=2, dim=1)


def distillation_loss(
    student_outputs: tuple[torch.Tensor, torch.Tensor],
    student_features: dict[str, torch.Tensor],
    teacher: dict[str, torch.Tensor],
    *,
    temperature: float = 2.0,
    response_weight: float = 1.0,
    feature_weight: float = 0.25,
) -> DistillationResult:
    """Response and spatial-attention distillation from an adapted YOLOX-S.

    The exported teacher adapter contract has `head20`, `head10`, `feature20`,
    and `feature10`. Heads use the EdgeDet 11-channel ABI; teacher feature channel
    counts are unrestricted because attention transfer removes that dimension.
    """
    response = student_outputs[0].new_zeros(())
    for student, key in zip(student_outputs, ("head20", "head10")):
        target = teacher[key].detach()
        if target.shape != student.shape:
            raise ValueError(f"teacher {key} shape {tuple(target.shape)} != {tuple(student.shape)}")
        soft = torch.sigmoid(target[:, :7] / temperature)
        response = response + F.binary_cross_entropy_with_logits(student[:, :7] / temperature, soft) * temperature**2
        response = response + F.smooth_l1_loss(student[:, 7:11], target[:, 7:11])
    feature = F.mse_loss(_attention_map(student_features["fused"]), _attention_map(teacher["feature20"].detach()))
    feature = feature + F.mse_loss(_attention_map(student_features["p4"]), _attention_map(teacher["feature10"].detach()))
    total = response_weight * response + feature_weight * feature
    return DistillationResult(total, response, feature)

