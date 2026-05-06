import pytest

from crafting_process.process import (
    describe_process,
    Ingredients,
    Process,
    BatchProcess,
    ContinuousProcess,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_batch(
    outputs="2 widget", inputs="3 iron + 1 copper", duration=4.0, process="stamping"
):
    return BatchProcess(
        outputs=Ingredients.parse(outputs),
        inputs=Ingredients.parse(inputs),
        duration=duration,
        process=process,
    )


def make_continuous(
    outputs="2 widget", inputs="3 iron + 1 copper", duration=4.0, process="stamping"
):
    return ContinuousProcess(
        outputs=Ingredients.parse(outputs),
        inputs=Ingredients.parse(inputs),
        duration=duration,
        process=process,
    )


# ---------------------------------------------------------------------------
# describe_process
# ---------------------------------------------------------------------------


def test_describe_process_with_process_name():
    assert describe_process(["widget"], "stamping") == "widget via stamping"


def test_describe_process_multiple_outputs():
    assert (
        describe_process(["widget", "scrap"], "stamping")
        == "widget + scrap via stamping"
    )


def test_describe_process_no_process_name():
    assert describe_process(["widget"]) == "widget"


def test_describe_process_no_process_name_explicit_none():
    assert describe_process(["widget"], None) == "widget"


# ---------------------------------------------------------------------------
# Ingredients
# ---------------------------------------------------------------------------


def test_ingredients_parse_single():
    ing = Ingredients.parse("3 iron")
    assert ing["iron"] == 3


def test_ingredients_parse_multiple():
    ing = Ingredients.parse("3 iron + 1 copper")
    assert ing["iron"] == 3
    assert ing["copper"] == 1


def test_ingredients_nonzero_components():
    ing = Ingredients.parse("3 iron + 1 copper")
    assert set(ing.nonzero_components.keys()) == {"iron", "copper"}


def test_ingredients_arithmetic():
    a = Ingredients.parse("3 iron")
    b = Ingredients.parse("2 iron")
    assert (a + b)["iron"] == 5
    assert (a - b)["iron"] == 1
    assert (2 * a)["iron"] == 6


def test_ingredients_parse_normalizes_internal_spaces():
    ing = Ingredients.parse("3  iron  ore")
    assert ing["iron ore"] == 3


def test_ingredients_parse_normalizes_leading_trailing_whitespace():
    ing = Ingredients.parse("  3 iron  ")
    assert ing["iron"] == 3


def test_ingredients_parse_normalizes_spaces_around_plus():
    ing = Ingredients.parse("3 iron  +  2 copper")
    assert ing["iron"] == 3
    assert ing["copper"] == 2


def test_ingredients_double_space_same_as_single_space():
    a = Ingredients.parse("3  iron  ore")
    b = Ingredients.parse("2 iron ore")
    assert (a + b)["iron ore"] == 5


def test_ingredients_tabs_treated_as_spaces():
    ing = Ingredients.parse("3\tiron\tore")
    assert ing["iron ore"] == 3


# ---------------------------------------------------------------------------
# Process base class — cannot be instantiated directly
# ---------------------------------------------------------------------------


def test_process_direct_instantiation_raises():
    with pytest.raises(TypeError, match="cannot be instantiated directly"):
        Process(outputs=Ingredients.parse("1 widget"))


# ---------------------------------------------------------------------------
# BatchProcess construction
# ---------------------------------------------------------------------------


def test_batch_process_stores_outputs_and_inputs():
    p = make_batch()
    assert p.outputs["widget"] == 2
    assert p.inputs["iron"] == 3
    assert p.inputs["copper"] == 1


def test_batch_process_no_inputs_defaults_to_zero():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"))
    assert p.inputs == Ingredients.zero()


def test_batch_process_duration_stored():
    p = make_batch(duration=10.0)
    assert p.duration == 10.0


def test_batch_process_duration_optional():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"))
    assert p.duration is None


def test_batch_process_name_stored():
    p = make_batch(process="forging")
    assert p.process == "forging"


# ---------------------------------------------------------------------------
# ContinuousProcess construction
# ---------------------------------------------------------------------------


def test_continuous_process_stores_outputs_and_inputs():
    p = make_continuous()
    assert p.outputs["widget"] == 2
    assert p.inputs["iron"] == 3


def test_continuous_process_duration_stored():
    p = make_continuous(duration=8.0)
    assert p.duration == 8.0


def test_continuous_process_requires_duration():
    with pytest.raises(ValueError, match="requires a duration"):
        ContinuousProcess(outputs=Ingredients.parse("1 widget"))


def test_continuous_process_requires_duration_none_explicit():
    with pytest.raises(ValueError, match="requires a duration"):
        ContinuousProcess(outputs=Ingredients.parse("1 widget"), duration=None)


# ---------------------------------------------------------------------------
# BatchProcess.exchange
# ---------------------------------------------------------------------------


def test_batch_exchange_equals_transfer():
    p = make_batch(outputs="4 widget", inputs="2 iron", duration=2.0)
    assert p.exchange["widget"] == pytest.approx(4.0)
    assert p.exchange["iron"] == pytest.approx(-2.0)


def test_batch_exchange_no_duration():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"), inputs=Ingredients.parse("2 iron"))
    assert p.exchange["widget"] == 1
    assert p.exchange["iron"] == -2


# ---------------------------------------------------------------------------
# ContinuousProcess.exchange
# ---------------------------------------------------------------------------


def test_continuous_exchange_equals_transfer_rate():
    p = make_continuous(outputs="4 widget", inputs="2 iron", duration=2.0)
    assert p.exchange["widget"] == pytest.approx(2.0)
    assert p.exchange["iron"] == pytest.approx(-1.0)


def test_continuous_exchange_duration_one():
    p = make_continuous(outputs="4 widget", inputs="2 iron", duration=1.0)
    assert p.exchange["widget"] == pytest.approx(4.0)
    assert p.exchange["iron"] == pytest.approx(-2.0)


# ---------------------------------------------------------------------------
# Process.transfer (deprecated but retained)
# ---------------------------------------------------------------------------


def test_transfer_is_outputs_minus_inputs():
    p = make_batch(outputs="2 widget", inputs="3 iron", duration=1.0, process="x")
    t = p.transfer
    assert t["widget"] == 2
    assert t["iron"] == -3


# ---------------------------------------------------------------------------
# Process.transfer_rate (deprecated but retained)
# ---------------------------------------------------------------------------


def test_transfer_rate_divides_by_duration():
    p = make_batch(outputs="4 widget", inputs="2 iron", duration=2.0, process="x")
    r = p.transfer_rate
    assert r["widget"] == pytest.approx(2.0)
    assert r["iron"] == pytest.approx(-1.0)


def test_transfer_rate_raises_without_duration():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"))
    with pytest.raises(ValueError, match="no duration"):
        _ = p.transfer_rate


# ---------------------------------------------------------------------------
# Process.transfer_quantity (deprecated but retained)
# ---------------------------------------------------------------------------


def test_transfer_quantity_batch_true_returns_transfer():
    p = make_batch(outputs="4 widget", inputs="2 iron", duration=2.0, process="x")
    q = p.transfer_quantity(batch=True)
    assert q["widget"] == 4
    assert q["iron"] == -2


def test_transfer_quantity_batch_false_returns_rate():
    p = make_batch(outputs="4 widget", inputs="2 iron", duration=2.0, process="x")
    q = p.transfer_quantity(batch=False)
    assert q["widget"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Process.describe
# ---------------------------------------------------------------------------


def test_describe_uses_outputs_and_process_name():
    p = make_batch(outputs="2 widget", process="stamping")
    assert p.describe() == "widget via stamping"


def test_describe_no_process_name():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"))
    assert p.describe() == "widget"


# ---------------------------------------------------------------------------
# Process.from_transfer
# ---------------------------------------------------------------------------


def test_batch_from_transfer_splits_positive_and_negative():
    transfer = Ingredients.parse("2 widget") - Ingredients.parse("3 iron")
    p = BatchProcess.from_transfer(transfer)
    assert p.outputs["widget"] == 2
    assert p.inputs["iron"] == 3
    assert isinstance(p, BatchProcess)


def test_continuous_from_transfer_splits_positive_and_negative():
    transfer = Ingredients.parse("2 widget") - Ingredients.parse("3 iron")
    p = ContinuousProcess.from_transfer(transfer, duration=2.0)
    assert p.outputs["widget"] == 2
    assert p.inputs["iron"] == 3
    assert isinstance(p, ContinuousProcess)


def test_process_from_transfer_raises():
    transfer = Ingredients.parse("2 widget") - Ingredients.parse("3 iron")
    with pytest.raises(TypeError, match="cannot be instantiated directly"):
        Process.from_transfer(transfer)


# ---------------------------------------------------------------------------
# Process.copy
# ---------------------------------------------------------------------------


def test_copy_produces_equal_process():
    p = make_batch()
    c = p.copy()
    assert c.outputs["widget"] == p.outputs["widget"]
    assert c.inputs["iron"] == p.inputs["iron"]
    assert c.duration == p.duration
    assert c.process == p.process


def test_copy_preserves_subclass_batch():
    p = make_batch()
    c = p.copy()
    assert isinstance(c, BatchProcess)


def test_copy_preserves_subclass_continuous():
    p = make_continuous()
    c = p.copy()
    assert isinstance(c, ContinuousProcess)


def test_copy_with_new_name():
    p = make_batch(process="stamping")
    c = p.copy(new_name="forging")
    assert c.process == "forging"
    assert p.process == "stamping"


# ---------------------------------------------------------------------------
# Process.__repr__
# ---------------------------------------------------------------------------


def test_repr_includes_process_name_and_duration():
    p = make_batch(process="stamping", duration=4.0)
    r = repr(p)
    assert "stamping" in r
    assert "4.0" in r


def test_repr_no_process_name_uses_fallback():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"))
    assert "Process" in repr(p)


# ---------------------------------------------------------------------------
# Process.annotations
# ---------------------------------------------------------------------------


def test_annotations_default_empty():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"))
    assert p.annotations == {}


def test_annotations_stored():
    p = BatchProcess(
        outputs=Ingredients.parse("1 widget"), annotations={"tier": 2, "energy": 150.0}
    )
    assert p.annotations["tier"] == 2
    assert p.annotations["energy"] == 150.0


def test_annotations_copy_preserved():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"), annotations={"tier": 2})
    c = p.copy()
    assert c.annotations == {"tier": 2}


def test_annotations_copy_is_independent():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"), annotations={"tier": 2})
    c = p.copy()
    c.annotations["tier"] = 99
    assert p.annotations["tier"] == 2


def test_annotations_in_to_dict():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"), annotations={"tier": 2})
    assert p.to_dict()["annotations"] == {"tier": 2}


def test_annotations_from_transfer():
    transfer = Ingredients.parse("2 widget") - Ingredients.parse("3 iron")
    p = BatchProcess.from_transfer(transfer, annotations={"tier": 1})
    assert p.annotations == {"tier": 1}


# ---------------------------------------------------------------------------
# Process.applied_augments
# ---------------------------------------------------------------------------


def test_applied_augments_default_empty():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"))
    assert p.applied_augments == []


def test_applied_augments_stored():
    p = BatchProcess(
        outputs=Ingredients.parse("1 widget"), applied_augments=["mk2", "speed"]
    )
    assert p.applied_augments == ["mk2", "speed"]


def test_applied_augments_copy_preserved():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"), applied_augments=["mk2"])
    c = p.copy()
    assert c.applied_augments == ["mk2"]


def test_applied_augments_copy_is_independent():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"), applied_augments=["mk2"])
    c = p.copy()
    c.applied_augments.append("extra")
    assert p.applied_augments == ["mk2"]


def test_applied_augments_in_to_dict():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"), applied_augments=["mk2"])
    assert p.to_dict()["applied_augments"] == ["mk2"]


# ---------------------------------------------------------------------------
# Process.copy with field overrides
# ---------------------------------------------------------------------------


def test_copy_override_duration():
    p = make_batch(duration=4.0)
    c = p.copy(duration=2.0)
    assert c.duration == pytest.approx(2.0)
    assert p.duration == pytest.approx(4.0)


def test_copy_override_preserves_annotations():
    p = make_batch(duration=4.0)
    p2 = BatchProcess(
        outputs=p.outputs,
        inputs=p.inputs,
        duration=p.duration,
        process=p.process,
        annotations={"tier": 2},
    )
    c = p2.copy(duration=1.0)
    assert c.annotations == {"tier": 2}
    assert c.duration == pytest.approx(1.0)


def test_copy_override_preserves_applied_augments():
    p = BatchProcess(
        outputs=Ingredients.parse("1 widget"),
        applied_augments=["mk2"],
    )
    c = p.copy(duration=1.0)
    assert c.applied_augments == ["mk2"]


def test_copy_override_applied_augments():
    p = BatchProcess(outputs=Ingredients.parse("1 widget"), applied_augments=["mk2"])
    c = p.copy(applied_augments=["mk2", "speed"])
    assert c.applied_augments == ["mk2", "speed"]
    assert p.applied_augments == ["mk2"]
