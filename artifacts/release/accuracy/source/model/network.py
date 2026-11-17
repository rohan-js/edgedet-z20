from __future__ import annotations

from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F

from .constants import HEAD_CHANNELS, INPUT_QUANT_SCALE
from .quantization import PROFILES, fake_quantize, symmetric_quantize


class ConvBNReLU6(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, stride: int, *, role: str = "interior"):
        super().__init__()
        padding = kernel_size // 2
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)
        self.role = role
        self.qat_profile: str | None = None

    def enable_qat(self, profile: str) -> None:
        if profile not in PROFILES:
            raise ValueError(f"unknown quantization profile: {profile}")
        self.qat_profile = profile

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        weight = self.conv.weight
        if self.qat_profile is not None:
            profile = PROFILES[self.qat_profile]
            bits = profile.first_last_weight_bits if self.role == "first" else profile.interior_weight_bits
            quantized, scale = symmetric_quantize(weight, bits, per_channel=True)
            shape = [-1] + [1] * (weight.ndim - 1)
            dequantized = quantized.to(weight.dtype) * scale.reshape(shape)
            weight = weight + (dequantized - weight).detach()
        x = F.conv2d(x, weight, None, self.conv.stride, self.conv.padding)
        x = F.relu6(self.bn(x))
        if self.qat_profile is not None:
            profile = PROFILES[self.qat_profile]
            bits = profile.first_activation_bits if self.role == "first" else profile.interior_activation_bits
            x = fake_quantize(x, bits, signed=False, scale=6.0 / ((1 << bits) - 1))
        return x


class DetectionHead(nn.Module):
    def __init__(self, in_channels: int):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, HEAD_CHANNELS, 1)
        self.qat_profile: str | None = None

    def enable_qat(self, profile: str) -> None:
        if profile not in PROFILES:
            raise ValueError(f"unknown quantization profile: {profile}")
        self.qat_profile = profile

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        weight = self.conv.weight
        if self.qat_profile is not None:
            bits = PROFILES[self.qat_profile].first_last_weight_bits
            quantized, scale = symmetric_quantize(weight, bits, per_channel=True)
            dequantized = quantized.to(weight.dtype) * scale[:, None, None, None]
            weight = weight + (dequantized - weight).detach()
        return F.conv2d(x, weight, self.conv.bias)


class EdgeDetZ20(nn.Module):
    """Hardware-shaped two-scale, anchor-free EdgeDet student network."""

    def __init__(self, num_classes: int = 6):
        super().__init__()
        if num_classes != 6:
            raise ValueError("the hardware ABI fixes the detector to six classes")
        self.num_classes = num_classes
        self.stem = ConvBNReLU6(3, 16, 3, 2, role="first")
        self.block2_down = ConvBNReLU6(16, 24, 3, 2)
        self.block2_same = ConvBNReLU6(24, 24, 3, 1)
        self.block3_down = ConvBNReLU6(24, 48, 3, 2)
        self.block3_same = ConvBNReLU6(48, 48, 3, 1)
        self.block4_down = ConvBNReLU6(48, 96, 3, 2)
        self.block4_same = ConvBNReLU6(96, 96, 3, 1)
        self.lateral = ConvBNReLU6(96, 48, 1, 1)
        self.fuse = ConvBNReLU6(48, 48, 3, 1)
        self.head20 = DetectionHead(48)
        self.head10 = DetectionHead(96)
        self.qat_profile: str | None = None
        self._initialize()

    def _initialize(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
        # Start classification and centerness with a conservative prior.
        prior = -4.595
        for head in (self.head20.conv, self.head10.conv):
            with torch.no_grad():
                head.bias[:7].fill_(prior)

    def enable_qat(self, profile: str) -> None:
        if profile not in PROFILES:
            raise ValueError(f"unknown quantization profile: {profile}")
        self.qat_profile = profile
        for module in self.modules():
            if isinstance(module, (ConvBNReLU6, DetectionHead)):
                module.enable_qat(profile)

    def disable_qat(self) -> None:
        self.qat_profile = None
        for module in self.modules():
            if isinstance(module, (ConvBNReLU6, DetectionHead)):
                module.qat_profile = None

    def forward_features(self, x: torch.Tensor) -> OrderedDict[str, torch.Tensor]:
        if tuple(x.shape[-2:]) != (160, 160):
            raise ValueError("EdgeDet-Z20 expects a 160x160 network tensor")
        if self.qat_profile is not None:
            x = fake_quantize(x, 8, signed=True, scale=INPUT_QUANT_SCALE)
        values: OrderedDict[str, torch.Tensor] = OrderedDict()
        values["stem"] = self.stem(x)
        values["block2_down"] = self.block2_down(values["stem"])
        values["block2_same"] = self.block2_same(values["block2_down"])
        values["block3_down"] = self.block3_down(values["block2_same"])
        values["p3"] = self.block3_same(values["block3_down"])
        values["block4_down"] = self.block4_down(values["p3"])
        values["p4"] = self.block4_same(values["block4_down"])
        values["lateral"] = self.lateral(values["p4"])
        upsampled = F.interpolate(values["lateral"], scale_factor=2.0, mode="nearest")
        fused_input = values["p3"] + upsampled
        if self.qat_profile is not None:
            bits = PROFILES[self.qat_profile].interior_activation_bits
            fused_input = fake_quantize(torch.clamp(fused_input, 0, 6), bits, signed=False, scale=6 / ((1 << bits) - 1))
        values["fused"] = self.fuse(fused_input)
        return values

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.forward_features(x)
        return self.head20(features["fused"]), self.head10(features["p4"])

    @staticmethod
    def flatten_outputs(outputs: tuple[torch.Tensor, torch.Tensor]) -> torch.Tensor:
        return torch.cat([head.permute(0, 2, 3, 1).reshape(head.shape[0], -1) for head in outputs], dim=1)

