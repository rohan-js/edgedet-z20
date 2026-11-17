from model.check_acceptance import check


def test_model_acceptance_gates_and_fallback_signal():
    passed = check(0.35, 0.33, 0.30)
    assert passed["float_floor_pass"]
    assert passed["accuracy_qat_pass"]
    assert passed["eco_qat_pass"]
    assert not passed["fallback_192_required"]
    fallback = check(0.29, 0.28, 0.27)
    assert fallback["fallback_192_required"] and not fallback["float_floor_pass"]
