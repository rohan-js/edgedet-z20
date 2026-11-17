import torch

from model.distillation import distillation_loss
from model.losses import EdgeDetLoss, assign_fcos_targets, grid_locations
from model.metrics import evaluate_detections
from model.network import EdgeDetZ20
from model.postprocess import decode_detections, nms


def test_network_shapes_flatten_and_reproducibility():
    torch.manual_seed(42)
    first = EdgeDetZ20().eval()
    torch.manual_seed(42)
    second = EdgeDetZ20().eval()
    for left, right in zip(first.state_dict().values(), second.state_dict().values()):
        torch.testing.assert_close(left, right)
    outputs = first(torch.zeros((1, 3, 160, 160)))
    assert [tuple(item.shape) for item in outputs] == [(1, 11, 20, 20), (1, 11, 10, 10)]
    assert first.flatten_outputs(outputs).shape == (1, 5500)


def test_assignment_loss_decode_nms_and_metrics():
    locations = grid_locations(20, 20, 8)
    labels, distances, center = assign_fcos_targets(
        locations, torch.tensor([[40.0, 40.0, 100.0, 100.0]]), torch.tensor([3]), 8, (0, 64)
    )
    assert (labels == 3).any() and torch.all(distances[labels >= 0] > 0) and torch.all(center[labels >= 0] <= 1)
    model = EdgeDetZ20().eval()
    outputs = model(torch.zeros((1, 3, 160, 160)))
    target = [{"boxes": torch.tensor([[40.0, 40.0, 100.0, 100.0]]), "labels": torch.tensor([3])}]
    loss = EdgeDetLoss()(outputs, target)
    assert torch.isfinite(loss.total) and loss.positives > 0
    assert len(decode_detections(outputs, score_threshold=0.999)) == 1
    keep = nms(torch.tensor([[0.0, 0.0, 10.0, 10.0], [1.0, 1.0, 9.0, 9.0]]), torch.tensor([0.9, 0.8]), 0.5)
    assert keep.tolist() == [0]
    prediction = [{"boxes": target[0]["boxes"].clone(), "labels": torch.tensor([3]), "scores": torch.tensor([0.9])}]
    metrics = evaluate_detections(prediction, target)
    assert metrics.map50 == 1.0 and metrics.precision == 1.0 and metrics.recall == 1.0


def test_qat_profiles_execute():
    for profile in ("accuracy", "eco"):
        model = EdgeDetZ20().eval()
        model.enable_qat(profile)
        outputs = model(torch.zeros((1, 3, 160, 160)))
        assert outputs[0].shape[-2:] == (20, 20)


def test_distillation_contract():
    model = EdgeDetZ20().eval()
    image = torch.zeros((1, 3, 160, 160))
    features = model.forward_features(image)
    outputs = (model.head20(features["fused"]), model.head10(features["p4"]))
    teacher = {
        "head20": outputs[0].detach().clone(),
        "head10": outputs[1].detach().clone(),
        "feature20": torch.randn(1, 128, 20, 20),
        "feature10": torch.randn(1, 256, 10, 10),
    }
    result = distillation_loss(outputs, features, teacher)
    assert torch.isfinite(result.total)
