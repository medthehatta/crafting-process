import pytest

from crafting_process.augment import Augments
from crafting_process.process import Ingredients, Process


def make_process(outputs="2 widget", inputs="3 iron", duration=4.0, process="stamping"):
    return Process(
        outputs=Ingredients.parse(outputs),
        inputs=Ingredients.parse(inputs),
        duration=duration,
        process=process,
    )


def make_annotated(annotations, applied_augments=None):
    return Process(
        outputs=Ingredients.parse("2 widget"),
        inputs=Ingredients.parse("3 iron"),
        duration=4.0,
        process="stamping",
        annotations=annotations,
        applied_augments=applied_augments or [],
    )


# ---------------------------------------------------------------------------
# Augments.mul_duration
# ---------------------------------------------------------------------------

def test_mul_duration_halves():
    p = make_process(duration=4.0)
    result = Augments.mul_duration(0.5)(p)
    assert result.duration == pytest.approx(2.0)


def test_mul_duration_preserves_io():
    p = make_process()
    result = Augments.mul_duration(2.0)(p)
    assert result.outputs["widget"] == 2
    assert result.inputs["iron"] == 3


# ---------------------------------------------------------------------------
# Augments.mul_speed
# ---------------------------------------------------------------------------

def test_mul_speed_doubles_speed():
    # double speed = half duration
    p = make_process(duration=4.0)
    result = Augments.mul_speed(2.0)(p)
    assert result.duration == pytest.approx(2.0)


def test_mul_speed_preserves_io():
    p = make_process()
    result = Augments.mul_speed(2.0)(p)
    assert result.outputs["widget"] == 2
    assert result.inputs["iron"] == 3


# ---------------------------------------------------------------------------
# Augments.mul_inputs / mul_outputs
# ---------------------------------------------------------------------------

def test_mul_inputs_scales_inputs():
    p = make_process(inputs="4 iron")
    result = Augments.mul_inputs(0.5)(p)
    assert result.inputs["iron"] == pytest.approx(2.0)


def test_mul_outputs_scales_outputs():
    p = make_process(outputs="2 widget")
    result = Augments.mul_outputs(3.0)(p)
    assert result.outputs["widget"] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Augments.add_input / add_output
# ---------------------------------------------------------------------------

def test_add_input_appends():
    p = make_process(inputs="3 iron")
    more = Ingredients.parse("1 kWe")
    result = Augments.add_input(more)(p)
    assert result.inputs["iron"] == 3
    assert result.inputs["kWe"] == 1


def test_add_output_appends():
    p = make_process(outputs="2 widget")
    more = Ingredients.parse("1 scrap")
    result = Augments.add_output(more)(p)
    assert result.outputs["widget"] == 2
    assert result.outputs["scrap"] == 1


# ---------------------------------------------------------------------------
# Augments.add_input_rate / add_output_rate
# ---------------------------------------------------------------------------

def test_add_input_rate_scales_by_duration():
    # duration=4, rate=1 kWe/s → 4 kWe added
    p = make_process(duration=4.0, inputs="3 iron")
    rate = Ingredients.parse("1 kWe")
    result = Augments.add_input_rate(rate)(p)
    assert result.inputs["kWe"] == pytest.approx(4.0)
    assert result.inputs["iron"] == 3


def test_add_output_rate_scales_by_duration():
    p = make_process(duration=2.0, outputs="2 widget")
    rate = Ingredients.parse("3 scrap")
    result = Augments.add_output_rate(rate)(p)
    assert result.outputs["scrap"] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Augments.increase_energy_pct
# ---------------------------------------------------------------------------

def test_increase_energy_pct_adds_energy():
    p = make_process(inputs="3 iron + 100 kWe", duration=1.0)
    result = Augments.increase_energy_pct("kWe", 10)(p)
    assert result.inputs["kWe"] == pytest.approx(110.0)
    assert result.inputs["iron"] == 3


def test_increase_energy_pct_no_energy_kind_unchanged():
    p = make_process(inputs="3 iron", duration=1.0)
    result = Augments.increase_energy_pct("kWe", 10)(p)
    assert result.inputs["kWe"] == 0
    assert result.inputs["iron"] == 3


def test_increase_energy_pct_parameterized_kind():
    p = make_process(inputs="3 iron + 50 MW", duration=1.0)
    result = Augments.increase_energy_pct("MW", 20)(p)
    assert result.inputs["MW"] == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# Augments.composed
# ---------------------------------------------------------------------------

def test_composed_chains_left_to_right():
    # mul_speed(2) halves duration; mul_outputs(3) triples outputs
    p = make_process(duration=4.0, outputs="2 widget")
    aug = Augments.composed([Augments.mul_speed(2.0), Augments.mul_outputs(3.0)])
    result = aug(p)
    assert result.duration == pytest.approx(2.0)
    assert result.outputs["widget"] == pytest.approx(6.0)


def test_composed_single():
    p = make_process(duration=4.0)
    aug = Augments.composed([Augments.mul_speed(2.0)])
    result = aug(p)
    assert result.duration == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Annotations and applied_augments preserved through augmentation
# ---------------------------------------------------------------------------

def test_augment_preserves_annotations():
    p = make_annotated({"tier": 2})
    result = Augments.mul_speed(2.0)(p)
    assert result.annotations == {"tier": 2}


def test_augment_preserves_applied_augments():
    p = make_annotated({}, applied_augments=["mk1"])
    result = Augments.mul_speed(2.0)(p)
    assert result.applied_augments == ["mk1"]


def test_augment_annotations_independent():
    p = make_annotated({"tier": 2})
    result = Augments.mul_speed(2.0)(p)
    result.annotations["tier"] = 99
    assert p.annotations["tier"] == 2
