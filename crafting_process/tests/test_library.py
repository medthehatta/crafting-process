import pytest

from crafting_process.library import (
    _parse_process_header,
    parse_process,
    specs_from_lines,
    process_from_spec_dict,
    parse_processes,
    ProcessPredicates,
    ProcessLibrary,
)
from crafting_process.process import Ingredients, Process


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def library():
    lib = ProcessLibrary()
    lib.add_from_text("""
        widget | stamping: duration=4
        3 iron + 1 copper

        widget | forging: duration=8
        5 iron

        gear | machining: duration=2
        2 widget

        scrap | stamping:
        1 iron
    """)
    return lib


# ---------------------------------------------------------------------------
# _parse_process_header — DSL syntax variants
# ---------------------------------------------------------------------------

def test_header_outputs_only():
    result = _parse_process_header("widget")
    assert result["outputs"] == "widget"
    assert "inputs" not in result


def test_header_inline_inputs_with_equals():
    result = _parse_process_header("widget = 3 iron + 1 copper")
    assert result["outputs"] == "widget"
    assert result["inputs"] == "3 iron + 1 copper"


def test_header_multiple_outputs_inline_inputs():
    result = _parse_process_header("output1 + 2 output2 = 10 single input")
    assert result["outputs"] == "output1 + 2 output2"
    assert result["inputs"] == "10 single input"


def test_header_trailing_equals_stripped():
    # Trailing = means inputs come on the next line; the = itself is dropped.
    result = _parse_process_header("widget =")
    assert result["outputs"] == "widget"
    assert "inputs" not in result


def test_header_pipe_sets_process_name():
    result = _parse_process_header("widget | stamping:")
    assert result["outputs"] == "widget"
    assert result["process"] == "stamping"


def test_header_pipe_with_numeric_attribute():
    result = _parse_process_header("widget | stamping: duration=4")
    assert result["process"] == "stamping"
    assert result["duration"] == 4


def test_header_numeric_attribute_parsed_as_number():
    result = _parse_process_header("widget | stamping: duration=4")
    assert isinstance(result["duration"], (int, float))


def test_header_string_attribute_kept_as_string():
    result = _parse_process_header("widget | stamping: tier=advanced")
    assert result["tier"] == "advanced"


def test_header_multiple_pipe_segments_joined():
    # Extra | separators are cosmetic; attributes still parsed correctly
    result = _parse_process_header("widget | stamping: duration=4 | tier=2")
    assert result["process"] == "stamping"
    assert result["duration"] == 4
    assert result["tier"] == 2


def test_header_pipe_with_inline_inputs():
    result = _parse_process_header("widget | stamping: = 3 iron + 1 copper")
    assert result["outputs"] == "widget"
    assert result["process"] == "stamping"
    assert result["inputs"] == "3 iron + 1 copper"


def test_header_attribute_with_digit_in_name():
    # Regression: the 0-0 typo fix — attribute names with digits should parse
    result = _parse_process_header("widget | stamping: tier2=advanced")
    assert result["tier2"] == "advanced"


def test_header_leading_trailing_whitespace_on_product_stripped():
    result = _parse_process_header("  widget  ")
    assert result["outputs"] == "widget"


def test_header_multiword_product_whitespace_stripped():
    result = _parse_process_header("  iron gear  =")
    assert result["outputs"] == "iron gear"


# ---------------------------------------------------------------------------
# parse_process — 1-line, 2-line, and error cases
# ---------------------------------------------------------------------------

def test_parse_process_single_line():
    result = parse_process("widget = 3 iron")
    assert result["outputs"] == "widget"
    assert result["inputs"] == "3 iron"


def test_parse_process_two_lines():
    result = parse_process("widget | stamping:\n3 iron + 1 copper")
    assert result["outputs"] == "widget"
    assert result["inputs"] == "3 iron + 1 copper"
    assert result["process"] == "stamping"


def test_parse_process_strips_blank_lines_and_comments():
    result = parse_process("# a comment\n\nwidget = 3 iron\n")
    assert result["outputs"] == "widget"
    assert result["inputs"] == "3 iron"


def test_parse_process_raises_on_empty():
    with pytest.raises(ValueError, match="No substantive"):
        parse_process("# just a comment\n\n")


def test_parse_process_raises_on_too_many_lines():
    with pytest.raises(ValueError, match="too many"):
        parse_process("widget\n3 iron\nextra line")


# ---------------------------------------------------------------------------
# specs_from_lines
# ---------------------------------------------------------------------------

def test_specs_from_lines_separates_on_blank_line():
    lines = [
        "widget = 3 iron",
        "",
        "gear = 2 widget",
    ]
    specs = list(specs_from_lines(lines))
    assert len(specs) == 2
    assert specs[0]["outputs"] == "widget"
    assert specs[1]["outputs"] == "gear"


def test_specs_from_lines_two_line_recipe():
    lines = [
        "widget | stamping:",
        "3 iron + 1 copper",
        "",
        "gear = 2 widget",
    ]
    specs = list(specs_from_lines(lines))
    assert len(specs) == 2
    assert specs[0]["inputs"] == "3 iron + 1 copper"


def test_specs_from_lines_skips_comment_lines():
    lines = [
        "# this is a comment",
        "widget = 3 iron",
    ]
    specs = list(specs_from_lines(lines))
    assert len(specs) == 1
    assert specs[0]["outputs"] == "widget"


def test_specs_from_lines_no_trailing_blank_required():
    # File that ends without a trailing blank line should still yield the last recipe
    lines = ["widget = 3 iron"]
    specs = list(specs_from_lines(lines))
    assert len(specs) == 1


# ---------------------------------------------------------------------------
# process_from_spec_dict
# ---------------------------------------------------------------------------

def test_process_from_spec_dict_basic():
    spec = {"outputs": "2 widget", "inputs": "3 iron", "duration": 4.0, "process": "stamping"}
    p = process_from_spec_dict(spec)
    assert p.outputs["widget"] == 2
    assert p.inputs["iron"] == 3
    assert p.duration == 4.0
    assert p.process == "stamping"


def test_process_from_spec_dict_no_inputs():
    spec = {"outputs": "1 widget"}
    p = process_from_spec_dict(spec)
    assert p.inputs == Ingredients.zero()


def test_process_from_spec_dict_no_outputs():
    spec = {"inputs": "1 iron"}
    p = process_from_spec_dict(spec)
    assert p.outputs == Ingredients.zero()


# ---------------------------------------------------------------------------
# parse_processes — end-to-end
# ---------------------------------------------------------------------------

def test_parse_processes_returns_list_of_processes():
    lines = [
        "widget | stamping: duration=4",
        "3 iron + 1 copper",
        "",
        "gear | machining: duration=2",
        "2 widget",
    ]
    processes = parse_processes(lines)
    assert len(processes) == 2
    assert all(isinstance(p, Process) for p in processes)


def test_parse_processes_preserves_attributes():
    lines = ["widget | stamping: duration=4", "3 iron"]
    (p,) = parse_processes(lines)
    assert p.process == "stamping"
    assert p.duration == 4
    assert p.outputs["widget"] == 1
    assert p.inputs["iron"] == 3


# ---------------------------------------------------------------------------
# Whitespace tolerance — end-to-end
# ---------------------------------------------------------------------------

def test_extra_spaces_in_output_name_normalized():
    lines = ["iron  gear | stamping: duration=4", "3  iron"]
    (p,) = parse_processes(lines)
    assert p.outputs["iron gear"] == 1


def test_extra_spaces_in_input_name_normalized():
    lines = ["widget | stamping: duration=4", "3  iron  ore + 2 copper"]
    (p,) = parse_processes(lines)
    assert p.inputs["iron ore"] == 3
    assert p.inputs["copper"] == 2


def test_extra_spaces_around_plus_in_inputs_normalized():
    lines = ["widget | stamping: duration=4", "3 iron  +  2 copper"]
    (p,) = parse_processes(lines)
    assert p.inputs["iron"] == 3
    assert p.inputs["copper"] == 2


def test_ingredient_used_with_inconsistent_spacing_is_unified():
    # Two recipes referencing the same ingredient via different whitespace
    # must produce the same ingredient key so they can be composed correctly.
    lines = [
        "widget | stamping: duration=4",
        "3  iron  ore",
        "",
        "gear | machining: duration=2",
        "2 iron ore",
    ]
    (stamping, machining) = parse_processes(lines)
    # Both should reference "iron ore" (single space), allowing arithmetic
    combined = stamping.inputs + machining.inputs
    assert combined["iron ore"] == 5


# ---------------------------------------------------------------------------
# ProcessLibrary — naming and disambiguation
# ---------------------------------------------------------------------------

def test_library_add_from_text_stores_recipes(library):
    assert len(library.recipes) == 4


def test_library_recipe_names_include_process(library):
    assert "widget via stamping" in library.recipes
    assert "widget via forging" in library.recipes


def test_mkname_disambiguates_duplicate_names():
    lib = ProcessLibrary()
    # Two processes with identical outputs and no process name get disambiguated
    lib.add_from_text("widget\n3 iron\n\nwidget\n5 iron")
    assert "widget" in lib.recipes
    assert "widget 2" in lib.recipes


def test_mkname_disambiguates_sequentially():
    lib = ProcessLibrary()
    lib.add_from_text("widget\n3 iron\n\nwidget\n5 iron\n\nwidget\n7 iron")
    assert "widget" in lib.recipes
    assert "widget 2" in lib.recipes
    assert "widget 3" in lib.recipes


# ---------------------------------------------------------------------------
# ProcessLibrary — search methods
# ---------------------------------------------------------------------------

def test_producing_returns_matching_recipes(library):
    results = library.producing("widget")
    names = [n for (n, _) in results]
    assert "widget via stamping" in names
    assert "widget via forging" in names
    assert "gear via machining" not in names


def test_producing_returns_empty_for_unknown(library):
    assert library.producing("unobtanium") == []


def test_consuming_returns_recipes_that_use_resource(library):
    results = library.consuming("widget")
    names = [n for (n, _) in results]
    assert "gear via machining" in names


def test_consuming_excludes_recipes_that_dont_use_resource(library):
    results = library.consuming("widget")
    names = [n for (n, _) in results]
    assert "widget via stamping" not in names


def test_using_returns_recipes_with_that_process_name(library):
    results = library.using("stamping")
    names = [n for (n, _) in results]
    assert "widget via stamping" in names
    assert "scrap via stamping" in names
    assert "widget via forging" not in names


def test_filter_with_custom_predicate(library):
    # Recipes whose inputs include iron
    results = library.filter(ProcessPredicates.requires_part("iron"))
    names = [n for (n, _) in results]
    assert "widget via stamping" in names
    assert "widget via forging" in names
    assert "gear via machining" not in names


# ---------------------------------------------------------------------------
# ProcessPredicates
# ---------------------------------------------------------------------------

def make_process(outputs, inputs="", process=None, annotations=None):
    return Process(
        outputs=Ingredients.parse(outputs),
        inputs=Ingredients.parse(inputs) if inputs else Ingredients.zero(),
        process=process,
        annotations=annotations or {},
    )


def test_outputs_part_true():
    p = make_process("2 widget")
    assert ProcessPredicates.outputs_part("widget")(p) is True


def test_outputs_part_false():
    p = make_process("2 widget")
    assert ProcessPredicates.outputs_part("gear")(p) is False


def test_requires_part_true():
    p = make_process("1 widget", inputs="3 iron")
    assert ProcessPredicates.requires_part("iron")(p) is True


def test_requires_part_false():
    p = make_process("1 widget", inputs="3 iron")
    assert ProcessPredicates.requires_part("copper")(p) is False


def test_uses_process_true():
    p = make_process("1 widget", process="stamping")
    assert ProcessPredicates.uses_process("stamping")(p) is True


def test_uses_process_false():
    p = make_process("1 widget", process="stamping")
    assert ProcessPredicates.uses_process("forging")(p) is False


def test_and_combinator():
    p = make_process("1 widget", inputs="3 iron", process="stamping")
    pred = ProcessPredicates.and_(
        ProcessPredicates.outputs_part("widget"),
        ProcessPredicates.uses_process("stamping"),
    )
    assert pred(p) is True
    assert pred(make_process("1 widget", process="forging")) is False


def test_or_combinator():
    pred = ProcessPredicates.or_(
        ProcessPredicates.outputs_part("widget"),
        ProcessPredicates.outputs_part("gear"),
    )
    assert pred(make_process("1 widget")) is True
    assert pred(make_process("1 gear")) is True
    assert pred(make_process("1 scrap")) is False


def test_not_combinator():
    pred = ProcessPredicates.not_(ProcessPredicates.outputs_part("widget"))
    assert pred(make_process("1 gear")) is True
    assert pred(make_process("1 widget")) is False


def test_any_combinator():
    pred = ProcessPredicates.any_([
        ProcessPredicates.outputs_part("widget"),
        ProcessPredicates.outputs_part("gear"),
    ])
    assert pred(make_process("1 widget")) is True
    assert pred(make_process("1 scrap")) is False


def test_all_combinator():
    pred = ProcessPredicates.all_([
        ProcessPredicates.outputs_part("widget"),
        ProcessPredicates.requires_part("iron"),
    ])
    assert pred(make_process("1 widget", inputs="3 iron")) is True
    assert pred(make_process("1 widget", inputs="3 copper")) is False


def test_outputs_any_of():
    pred = ProcessPredicates.outputs_any_of(["widget", "gear"])
    assert pred(make_process("1 widget")) is True
    assert pred(make_process("1 gear")) is True
    assert pred(make_process("1 scrap")) is False


# ---------------------------------------------------------------------------
# _parse_process_header — annotation block parsing
# ---------------------------------------------------------------------------

def test_header_annotation_single():
    result = _parse_process_header("2 iron | smelt: [tier=2]")
    assert result["annotations"] == {"tier": 2}


def test_header_annotation_multiple():
    result = _parse_process_header("2 iron | smelt: [tier=2 | energy=150]")
    assert result["annotations"] == {"tier": 2, "energy": 150}


def test_header_annotation_string_value():
    result = _parse_process_header("1 widget | assemble: [assembler=mk2]")
    assert result["annotations"] == {"assembler": "mk2"}


def test_header_annotation_float_value():
    result = _parse_process_header("2 iron | smelt: [efficiency=1.5]")
    assert result["annotations"]["efficiency"] == pytest.approx(1.5)


def test_header_annotation_bare_true_stays_string():
    result = _parse_process_header("2 iron | smelt: [fast=true]")
    assert result["annotations"]["fast"] == "true"


def test_header_no_annotation_block():
    result = _parse_process_header("2 iron | smelt: duration=2")
    assert result["annotations"] == {}


def test_header_annotation_with_duration():
    result = _parse_process_header("2 iron | smelt: duration=2 [tier=2]")
    assert result["duration"] == 2
    assert result["annotations"] == {"tier": 2}


def test_header_annotation_with_inline_inputs():
    result = _parse_process_header("2 iron | smelt: [tier=2] = 3 ore")
    assert result["annotations"] == {"tier": 2}
    assert result["inputs"] == "3 ore"


def test_header_annotation_outputs_unaffected():
    result = _parse_process_header("2 iron + 1 copper | mine: [tier=1]")
    assert result["outputs"] == "2 iron + 1 copper"


# ---------------------------------------------------------------------------
# process_from_spec_dict — annotations routed correctly
# ---------------------------------------------------------------------------

def test_spec_dict_annotations_on_process():
    spec = {"outputs": "1 widget", "inputs": "2 iron", "annotations": {"tier": 2}}
    p = process_from_spec_dict(spec)
    assert p.annotations == {"tier": 2}


def test_spec_dict_no_annotations_key_defaults_empty():
    spec = {"outputs": "1 widget", "inputs": "2 iron"}
    p = process_from_spec_dict(spec)
    assert p.annotations == {}


# ---------------------------------------------------------------------------
# ProcessPredicates.annotation_matches
# ---------------------------------------------------------------------------

def test_annotation_matches_eq():
    p = make_process("1 widget", annotations={"tier": 2})
    assert ProcessPredicates.annotation_matches("tier", lambda v: v == 2)(p) is True


def test_annotation_matches_miss():
    p = make_process("1 widget", annotations={"tier": 2})
    assert ProcessPredicates.annotation_matches("tier", lambda v: v == 3)(p) is False


def test_annotation_matches_absent_key_returns_false():
    p = make_process("1 widget", annotations={})
    assert ProcessPredicates.annotation_matches("tier", lambda v: v == 2)(p) is False


def test_annotation_matches_lt():
    p = make_process("1 widget", annotations={"tier": 2})
    assert ProcessPredicates.annotation_matches("tier", lambda v: v < 3)(p) is True
    assert ProcessPredicates.annotation_matches("tier", lambda v: v < 2)(p) is False


def test_annotation_matches_composed_with_outputs_part():
    p = make_process("1 widget", inputs="2 iron", annotations={"tier": 2})
    pred = ProcessPredicates.and_(
        ProcessPredicates.annotation_matches("tier", lambda v: v == 2),
        ProcessPredicates.outputs_part("widget"),
    )
    assert pred(p) is True
    assert pred(make_process("1 gear", annotations={"tier": 2})) is False
    assert pred(make_process("1 widget", annotations={"tier": 1})) is False


def test_lib_filter_by_annotation(library):
    # library fixture has no annotations, so build a fresh one
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron | smelt_a: [tier=1]
        3 ore_a

        2 iron | smelt_b: [tier=2]
        3 ore_b

        1 widget | assemble: [tier=2]
        2 iron
    """)
    tier2 = lib.filter(ProcessPredicates.annotation_matches("tier", lambda v: v == 2))
    assert len(tier2) == 2
    assert all(proc.annotations["tier"] == 2 for (_, proc) in tier2)


def test_lib_filter_annotation_and_output():
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron | smelt_a: [tier=1]
        3 ore_a

        2 iron | smelt_b: [tier=2]
        3 ore_b

        1 widget | assemble: [tier=2]
        2 iron
    """)
    pred = ProcessPredicates.and_(
        ProcessPredicates.annotation_matches("tier", lambda v: v == 2),
        ProcessPredicates.outputs_part("iron"),
    )
    results = lib.filter(pred)
    assert len(results) == 1
    assert results[0][1].annotations["tier"] == 2
    assert results[0][1].outputs["iron"] == 2


# ---------------------------------------------------------------------------
# register_augment
# ---------------------------------------------------------------------------

def test_register_augment_stored():
    from crafting_process.augment import Augments
    lib = ProcessLibrary()
    fn = Augments.mul_speed(2.0)
    lib.register_augment("fast", fn)
    assert "fast" in lib._augments
    assert lib._augments["fast"] is fn


# ---------------------------------------------------------------------------
# @-block augment syntax
# ---------------------------------------------------------------------------

def _aug_lib():
    """Library with a registered augment for use in augment tests."""
    from crafting_process.augment import Augments
    lib = ProcessLibrary()
    lib.register_augment("mk2", Augments.mul_speed(2.0))
    lib.register_augment("mk3", Augments.mul_speed(3.0))
    lib.register_augment("prod", Augments.mul_outputs(1.1))
    return lib


def test_block_augment_original_always_added():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2

        2 iron | smelt: duration=4
        3 ore
    """)
    # original + 1 augmented variant
    iron_entries = lib.filter(ProcessPredicates.outputs_part("iron"))
    assert len(iron_entries) == 2


def test_block_augment_creates_augmented_entry():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2

        2 iron | smelt: duration=4
        3 ore
    """)
    augmented = [(n, p) for (n, p) in lib.recipes.items() if p.applied_augments]
    assert len(augmented) == 1
    name, proc = augmented[0]
    assert "@mk2" in name
    assert proc.duration == pytest.approx(2.0)   # mk2 = mul_speed(2) → half duration


def test_block_augment_multiple_lines_yields_one_variant_each():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2
        @mk3

        2 iron | smelt: duration=6
        3 ore
    """)
    # original + mk2 variant + mk3 variant
    iron_entries = lib.filter(ProcessPredicates.outputs_part("iron"))
    assert len(iron_entries) == 3


def test_block_augment_multi_token_line_composed():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2 @prod

        2 iron | smelt: duration=4
        3 ore
    """)
    augmented = [(n, p) for (n, p) in lib.recipes.items() if p.applied_augments]
    assert len(augmented) == 1
    name, proc = augmented[0]
    assert "@mk2" in name and "@prod" in name
    assert proc.duration == pytest.approx(2.0)          # mk2: duration halved
    assert proc.outputs["iron"] == pytest.approx(2.2)   # prod: outputs * 1.1


def test_block_augment_applied_augments_set():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2

        2 iron | smelt: duration=4
        3 ore
    """)
    augmented = next(p for p in lib.recipes.values() if p.applied_augments)
    assert augmented.applied_augments == ["mk2"]


def test_block_augment_reset_after_recipes():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2

        2 iron | smelt: duration=4
        3 ore

        @mk3

        1 widget | press: duration=2
        2 iron
    """)
    # smelt: original + mk2; press: original + mk3
    iron_entries = lib.filter(ProcessPredicates.outputs_part("iron"))
    widget_entries = lib.filter(ProcessPredicates.outputs_part("widget"))
    assert len(iron_entries) == 2
    assert len(widget_entries) == 2
    assert any("@mk2" in n for (n, _) in iron_entries)
    assert any("@mk3" in n for (n, _) in widget_entries)
    # smelt should NOT have an @mk3 variant
    assert not any("@mk3" in n for (n, _) in iron_entries)


def test_block_augment_applies_to_multiple_recipes():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2

        2 iron | smelt: duration=4
        3 ore

        1 widget | press: duration=2
        2 iron
    """)
    iron_entries = lib.filter(ProcessPredicates.outputs_part("iron"))
    widget_entries = lib.filter(ProcessPredicates.outputs_part("widget"))
    assert len(iron_entries) == 2
    assert len(widget_entries) == 2


# ---------------------------------------------------------------------------
# Inline @-augment syntax
# ---------------------------------------------------------------------------

def test_inline_augment_creates_augmented_entry():
    lib = _aug_lib()
    lib.add_from_text("""
        2 iron | smelt: @mk2 duration=4
        3 ore
    """)
    # original + 1 inline-augmented variant
    iron_entries = lib.filter(ProcessPredicates.outputs_part("iron"))
    assert len(iron_entries) == 2
    augmented = next(p for p in lib.recipes.values() if p.applied_augments)
    assert augmented.duration == pytest.approx(2.0)


def test_inline_augment_replaces_block():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk3

        2 iron | smelt: @mk2 duration=4
        3 ore
    """)
    # block is @mk3 but recipe has inline @mk2 — inline wins
    iron_entries = lib.filter(ProcessPredicates.outputs_part("iron"))
    assert len(iron_entries) == 2  # original + mk2 only, not mk3
    augmented = next(p for p in lib.recipes.values() if p.applied_augments)
    assert "mk2" in augmented.applied_augments
    assert "mk3" not in augmented.applied_augments


# ---------------------------------------------------------------------------
# Augmented entry naming
# ---------------------------------------------------------------------------

def test_augmented_entry_name_contains_at_tag():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2

        2 iron | smelt: duration=4
        3 ore
    """)
    augmented_names = [n for n in lib.recipes if "@mk2" in n]
    assert len(augmented_names) == 1


def test_augmented_entry_name_multi_tag_application_order():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2 @prod

        2 iron | smelt: duration=4
        3 ore
    """)
    # application order: mk2 first, then prod
    augmented_names = [n for n in lib.recipes if "@mk2" in n]
    assert len(augmented_names) == 1
    name = augmented_names[0]
    assert name.index("@mk2") < name.index("@prod")


# ---------------------------------------------------------------------------
# with_augment_filter / skip_augments / only_augments
# ---------------------------------------------------------------------------

def _augmented_lib():
    lib = _aug_lib()
    lib.add_from_text("""
        @mk2
        @mk3

        2 iron | smelt: duration=6
        3 ore
    """)
    return lib


def test_with_augment_filter_skip_excludes():
    lib = _augmented_lib()
    filtered = lib.with_augment_filter(skip_augments=["mk2"])
    names = list(filtered.recipes.keys())
    assert not any("@mk2" in n for n in names)
    assert any("@mk3" in n for n in names)
    # original retained
    assert any(not filtered.recipes[n].applied_augments for n in names)


def test_with_augment_filter_only_includes_originals_and_specified():
    lib = _augmented_lib()
    filtered = lib.with_augment_filter(only_augments=["mk2"])
    names = list(filtered.recipes.keys())
    assert any("@mk2" in n for n in names)
    assert not any("@mk3" in n for n in names)
    assert any(not filtered.recipes[n].applied_augments for n in names)


def test_with_augment_filter_only_empty_list_originals_only():
    lib = _augmented_lib()
    filtered = lib.with_augment_filter(only_augments=[])
    for proc in filtered.recipes.values():
        assert proc.applied_augments == []


def test_with_augment_filter_preserves_augments_registry():
    lib = _augmented_lib()
    filtered = lib.with_augment_filter(skip_augments=["mk2"])
    assert filtered._augments is lib._augments
