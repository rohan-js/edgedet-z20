import numpy as np
import torch

from model.constants import PREPROCESS_BIAS, PREPROCESS_FRACTION_BITS, PREPROCESS_MULTIPLIER
from model.preprocess import exact_area_downsample_2x, preprocess_rgb, quantize_reduced_rgb, undo_letterbox_boxes


def test_exact_area_round_half_up():
    image = torch.zeros((3, 320, 320), dtype=torch.uint8)
    image[:, :2, :2] = torch.tensor([[0, 0], [1, 1]], dtype=torch.uint8)
    reduced = exact_area_downsample_2x(image)
    assert reduced[:, 0, 0].tolist() == [1, 1, 1]


def test_preprocess_shapes_quantization_and_box_roundtrip():
    image = np.full((100, 200, 3), 127, dtype=np.uint8)
    boxes = torch.tensor([[20.0, 10.0, 180.0, 90.0]])
    tensor, transformed, info = preprocess_rgb(image, boxes, quantized=True)
    assert tensor.shape == (3, 160, 160) and tensor.dtype == torch.int8
    restored = undo_letterbox_boxes(transformed, info)
    torch.testing.assert_close(restored, boxes, atol=1e-4, rtol=0)


def test_fixed_point_normalization_contract_for_all_u8_values():
    ramp = torch.arange(256, dtype=torch.uint8).view(1, 1, 256).expand(3, 160, 256)
    reduced = ramp[:, :, :160].contiguous()
    actual = quantize_reduced_rgb(reduced)
    for channel in range(3):
        scaled = reduced[channel].to(torch.int64) * PREPROCESS_MULTIPLIER[channel] + PREPROCESS_BIAS[channel]
        half = 1 << (PREPROCESS_FRACTION_BITS - 1)
        expected = torch.sign(scaled) * ((torch.abs(scaled) + half) >> PREPROCESS_FRACTION_BITS)
        torch.testing.assert_close(actual[channel], expected.clamp(-128, 127).to(torch.int8))
