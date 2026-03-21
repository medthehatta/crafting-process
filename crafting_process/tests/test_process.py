import pytest

from crafting_process.process import describe_process, Ingredients, Process

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_process(
    outputs="2 widget", inputs="3 iron + 1 copper", duration=4.0, process="stamping"
):
    return Process(
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
    # Both spellings must resolve to the same ingredient so arithmetic works
    a = Ingredients.parse("3  iron  ore")
    b = Ingredients.parse("2 iron ore")
    assert (a + b)["iron ore"] == 5


def test_ingredients_tabs_treated_as_spaces():
    ing = Ingredients.parse("3\tiron\tore")
    assert ing["iron ore"] == 3


# ---------------------------------------------------------------------------
# Process construction
# ---------------------------------------------------------------------------


def test_process_stores_outputs_and_inputs():
    p = make_process()
    assert p.outputs["widget"] == 2
    assert p.inputs["iron"] == 3
    assert p.inputs["copper"] == 1


def test_process_no_inputs_defaults_to_zero():
    p = Process(outputs=Ingredients.parse("1 widget"))
    assert p.inputs == Ingredients.zero()


def test_process_duration_stored():
    p = make_process(duration=10.0)
    assert p.duration == 10.0


def test_process_name_stored():
    p = make_process(process="forging")
    assert p.process == "forging"


# ---------------------------------------------------------------------------
# Process.transfer
# ---------------------------------------------------------------------------


def test_transfer_is_outputs_minus_inputs():
    p = make_process(outputs="2 widget", inputs="3 iron", duration=1.0, process="x")
    t = p.transfer
    assert t["widget"] == 2
    assert t["iron"] == -3


# ---------------------------------------------------------------------------
# Process.transfer_rate
# ---------------------------------------------------------------------------


def test_transfer_rate_divides_by_duration():
    p = make_process(outputs="4 widget", inputs="2 iron", duration=2.0, process="x")
    r = p.transfer_rate
    assert r["widget"] == pytest.approx(2.0)
    assert r["iron"] == pytest.approx(-1.0)


def test_transfer_rate_raises_without_duration():
    p = Process(outputs=Ingredients.parse("1 widget"))
    with pytest.raises(ValueError, match="no duration"):
        _ = p.transfer_rate


# ---------------------------------------------------------------------------
# Process.transfer_quantity
# ---------------------------------------------------------------------------


def test_transfer_quantity_batch_true_returns_transfer():
    p = make_process(outputs="4 widget", inputs="2 iron", duration=2.0, process="x")
    q = p.transfer_quantity(batch=True)
    assert q["widget"] == 4
    assert q["iron"] == -2


def test_transfer_quantity_batch_false_returns_rate():
    p = make_process(outputs="4 widget", inputs="2 iron", duration=2.0, process="x")
    q = p.transfer_quantity(batch=False)
    assert q["widget"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Process.describe
# ---------------------------------------------------------------------------


def test_describe_uses_outputs_and_process_name():
    p = make_process(outputs="2 widget", process="stamping")
    assert p.describe() == "widget via stamping"


def test_describe_no_process_name():
    p = Process(outputs=Ingredients.parse("1 widget"))
    assert p.describe() == "widget"


# ---------------------------------------------------------------------------
# Process.from_transfer
# ---------------------------------------------------------------------------


def test_from_transfer_splits_positive_and_negative():
    transfer = Ingredients.parse("2 widget") - Ingredients.parse("3 iron")
    p = Process.from_transfer(transfer)
    assert p.outputs["widget"] == 2
    assert p.inputs["iron"] == 3


# ---------------------------------------------------------------------------
# Process.copy
# ---------------------------------------------------------------------------


def test_copy_produces_equal_process():
    p = make_process()
    c = p.copy()
    assert c.outputs["widget"] == p.outputs["widget"]
    assert c.inputs["iron"] == p.inputs["iron"]
    assert c.duration == p.duration
    assert c.process == p.process


def test_copy_with_new_name():
    p = make_process(process="stamping")
    c = p.copy(new_name="forging")
    assert c.process == "forging"
    assert p.process == "stamping"


# ---------------------------------------------------------------------------
# Process.__repr__
# ---------------------------------------------------------------------------


def test_repr_includes_process_name_and_duration():
    p = make_process(process="stamping", duration=4.0)
    r = repr(p)
    assert "stamping" in r
    assert "4.0" in r


def test_repr_no_process_name_uses_fallback():
    p = Process(outputs=Ingredients.parse("1 widget"))
    assert "Process" in repr(p)


# ---------------------------------------------------------------------------
# Process.annotations
# ---------------------------------------------------------------------------


def test_annotations_default_empty():
    p = Process(outputs=Ingredients.parse("1 widget"))
    assert p.annotations == {}


def test_annotations_stored():
    p = Process(
        outputs=Ingredients.parse("1 widget"), annotations={"tier": 2, "energy": 150.0}
    )
    assert p.annotations["tier"] == 2
    assert p.annotations["energy"] == 150.0


def test_annotations_copy_preserved():
    p = Process(outputs=Ingredients.parse("1 widget"), annotations={"tier": 2})
    c = p.copy()
    assert c.annotations == {"tier": 2}


def test_annotations_copy_is_independent():
    p = Process(outputs=Ingredients.parse("1 widget"), annotations={"tier": 2})
    c = p.copy()
    c.annotations["tier"] = 99
    assert p.annotations["tier"] == 2


def test_annotations_in_to_dict():
    p = Process(outputs=Ingredients.parse("1 widget"), annotations={"tier": 2})
    assert p.to_dict()["annotations"] == {"tier": 2}


def test_annotations_from_transfer():
    transfer = Ingredients.parse("2 widget") - Ingredients.parse("3 iron")
    p = Process.from_transfer(transfer, annotations={"tier": 1})
    assert p.annotations == {"tier": 1}


# ---------------------------------------------------------------------------
# Process.applied_augments
# ---------------------------------------------------------------------------


def test_applied_augments_default_empty():
    p = Process(outputs=Ingredients.parse("1 widget"))
    assert p.applied_augments == []


def test_applied_augments_stored():
    p = Process(
        outputs=Ingredients.parse("1 widget"), applied_augments=["mk2", "speed"]
    )
    assert p.applied_augments == ["mk2", "speed"]


def test_applied_augments_copy_preserved():
    p = Process(outputs=Ingredients.parse("1 widget"), applied_augments=["mk2"])
    c = p.copy()
    assert c.applied_augments == ["mk2"]


def test_applied_augments_copy_is_independent():
    p = Process(outputs=Ingredients.parse("1 widget"), applied_augments=["mk2"])
    c = p.copy()
    c.applied_augments.append("extra")
    assert p.applied_augments == ["mk2"]


def test_applied_augments_in_to_dict():
    p = Process(outputs=Ingredients.parse("1 widget"), applied_augments=["mk2"])
    assert p.to_dict()["applied_augments"] == ["mk2"]


# ---------------------------------------------------------------------------
# Process.copy with field overrides
# ---------------------------------------------------------------------------


def test_copy_override_duration():
    p = make_process(duration=4.0)
    c = p.copy(duration=2.0)
    assert c.duration == pytest.approx(2.0)
    assert p.duration == pytest.approx(4.0)


def test_copy_override_preserves_annotations():
    p = make_process(duration=4.0)
    p2 = Process(
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
    p = Process(
        outputs=Ingredients.parse("1 widget"),
        applied_augments=["mk2"],
    )
    c = p.copy(duration=1.0)
    assert c.applied_augments == ["mk2"]


def test_copy_override_applied_augments():
    p = Process(outputs=Ingredients.parse("1 widget"), applied_augments=["mk2"])
    c = p.copy(applied_augments=["mk2", "speed"])
    assert c.applied_augments == ["mk2", "speed"]
    assert p.applied_augments == ["mk2"]
