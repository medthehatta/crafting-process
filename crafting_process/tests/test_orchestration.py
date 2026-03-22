import types

import pytest

from crafting_process.orchestration import (
    input_combinations,
    batch_milps,
    production_graphs,
    analyze_graph,
    analyze_graphs,
    printable_analysis,
)
from crafting_process.graph import GraphBuilder
from crafting_process.library import ProcessLibrary
from crafting_process.process import Ingredients, Process

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def linear_library():
    """Two-process linear chain: 3 ore -> 2 iron -> 1 widget"""
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron | smelt
        3 ore

        1 widget | press
        2 iron
    """)
    return lib


# ---------------------------------------------------------------------------
# input_combinations
# ---------------------------------------------------------------------------


def test_input_combinations_single_kind_single_provider():
    result = list(input_combinations(["iron"], [("iron",)]))
    assert result == [(0,)]


def test_input_combinations_single_kind_two_providers():
    result = list(input_combinations(["iron"], [("iron",), ("iron",)]))
    assert set(result) == {(0,), (1,)}


def test_input_combinations_two_kinds_one_provider_each():
    result = list(input_combinations(["iron", "copper"], [("iron",), ("copper",)]))
    assert len(result) == 1
    combo = result[0]
    assert 0 in combo and 1 in combo


def test_input_combinations_provider_covers_multiple_kinds():
    # Provider 0 produces both iron and copper → single combo containing just 0
    result = list(input_combinations(["iron", "copper"], [("iron", "copper")]))
    assert result == [(0,)]


def test_input_combinations_results_are_unique():
    result = list(input_combinations(["iron"], [("iron",), ("iron",)]))
    assert len(result) == len(set(result))


def test_input_combinations_max_overlap_1_works():
    # Before the range fix, max_overlap=1 yielded nothing
    result = list(input_combinations(["iron"], [("iron",)], max_overlap=1))
    assert result == [(0,)]


def test_input_combinations_max_overlap_1_two_providers():
    result = list(input_combinations(["iron"], [("iron",), ("iron",)], max_overlap=1))
    assert set(result) == {(0,), (1,)}


def test_input_combinations_max_overlap_0_raises():
    with pytest.raises(ValueError, match="max_overlap"):
        list(input_combinations(["iron"], [("iron",)], max_overlap=0))


def test_input_combinations_empty_kinds_yields_nothing():
    result = list(input_combinations([], [("iron",)]))
    assert result == []


def test_input_combinations_kind_with_no_provider_yields_nothing():
    # "widget" has no provider in the list
    result = list(input_combinations(["widget"], [("iron",)]))
    assert result == []


def test_input_combinations_returns_iterable():
    result = input_combinations(["iron"], [("iron",)])
    assert hasattr(result, "__iter__")


# ---------------------------------------------------------------------------
# batch_milps
# ---------------------------------------------------------------------------


def _make_connected_graph():
    """3 ore -> 2 iron -> 1 widget; hand-built batch graph."""
    g = GraphBuilder()
    g.add_process(
        Process(outputs=Ingredients.parse("2 iron"), inputs=Ingredients.parse("3 ore")),
        name="smelter",
    )
    g.add_process(
        Process(
            outputs=Ingredients.parse("1 widget"), inputs=Ingredients.parse("2 iron")
        ),
        name="press",
    )
    g._connect_process_to_process("smelter", "press", kind="iron")
    return g


def test_batch_milps_returns_list():
    assert isinstance(batch_milps(_make_connected_graph()), list)


def test_batch_milps_nonempty_for_feasible_graph():
    assert len(batch_milps(_make_connected_graph())) >= 1


def test_batch_milps_each_entry_has_leakage_and_counts():
    for entry in batch_milps(_make_connected_graph()):
        assert "leakage" in entry
        assert "counts" in entry


def test_batch_milps_leakage_is_float():
    for entry in batch_milps(_make_connected_graph()):
        assert isinstance(entry["leakage"], float)


def test_batch_milps_counts_are_triples():
    # Each count entry: (repeat_count, process_description, process_name)
    for entry in batch_milps(_make_connected_graph()):
        for count, desc, name in entry["counts"]:
            assert isinstance(count, int)
            assert isinstance(desc, str)
            assert isinstance(name, str)


def test_batch_milps_final_leakage_zero_for_balanced_graph():
    # 2 iron produced == 2 iron consumed: perfectly balanced
    assert batch_milps(_make_connected_graph())[-1]["leakage"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# production_graphs
# ---------------------------------------------------------------------------


def test_production_graphs_yields_graphs(linear_library):
    graphs = list(production_graphs(linear_library, Ingredients.parse("1 widget")))
    assert len(graphs) >= 1


def test_production_graphs_yields_graph_builders(linear_library):
    for g in production_graphs(linear_library, Ingredients.parse("1 widget")):
        assert isinstance(g, GraphBuilder)


def test_production_graphs_each_graph_has_sentinel(linear_library):
    for g in production_graphs(linear_library, Ingredients.parse("1 widget")):
        kinds = {kind for (_, kind) in g.open_outputs}
        assert "_" in kinds


def test_production_graphs_graph_contains_producers(linear_library):
    g = next(production_graphs(linear_library, Ingredients.parse("1 widget")))
    descriptions = {p.describe() for p in g.processes.values()}
    assert any("widget" in d for d in descriptions)
    assert any("iron" in d for d in descriptions)


def test_production_graphs_stop_kinds_limits_recursion(linear_library):
    # stop_kinds=["iron"] halts before adding the smelter
    g = next(
        production_graphs(
            linear_library, Ingredients.parse("1 widget"), stop_kinds=["iron"]
        )
    )
    descriptions = {p.describe() for p in g.processes.values()}
    assert any("widget" in d for d in descriptions)
    assert not any("iron" in d for d in descriptions)


def test_production_graphs_skip_processes_excludes_process(linear_library):
    # skip_processes=["smelt"] removes the smelter; no producers for iron remain
    g = next(
        production_graphs(
            linear_library, Ingredients.parse("1 widget"), skip_processes=["smelt"]
        )
    )
    descriptions = {p.describe() for p in g.processes.values()}
    assert not any("iron" in d for d in descriptions)


# ---------------------------------------------------------------------------
# analyze_graph
# ---------------------------------------------------------------------------


def _first_result(library, transfer_str):
    g = next(production_graphs(library, Ingredients.parse(transfer_str)))
    return next(analyze_graph(g))


def test_analyze_graph_desired_matches_requested(linear_library):
    result = _first_result(linear_library, "1 widget")
    assert result.desired["widget"] == 1


def test_analyze_graph_leak_is_float(linear_library):
    assert isinstance(_first_result(linear_library, "1 widget").leak, float)


def test_analyze_graph_leak_is_zero_for_balanced(linear_library):
    assert _first_result(linear_library, "1 widget").leak == pytest.approx(0.0)


def test_analyze_graph_total_processes_includes_sentinel(linear_library):
    # smelter=1, press=1, sink=1 → total_processes=3 (sentinel counted)
    assert _first_result(linear_library, "1 widget").total_processes == 3


def test_analyze_graph_inputs_lists_ore(linear_library):
    result = _first_result(linear_library, "1 widget")
    kinds = [kind for (_, kind) in result.inputs]
    assert "ore" in kinds


def test_analyze_graph_inputs_excludes_sentinel(linear_library):
    result = _first_result(linear_library, "1 widget")
    kinds = [kind for (_, kind) in result.inputs]
    assert "_" not in kinds


def test_analyze_graph_ore_amount_correct(linear_library):
    result = _first_result(linear_library, "1 widget")
    ore_entries = [(amt, kind) for (amt, kind) in result.inputs if kind == "ore"]
    assert ore_entries == [(3, "ore")]


def test_analyze_graph_sorted_process_counts_is_list(linear_library):
    result = _first_result(linear_library, "1 widget")
    assert isinstance(result.process_counts, list)


def test_analyze_graph_sorted_process_counts_are_triples(linear_library):
    result = _first_result(linear_library, "1 widget")
    for pc in result.process_counts:
        assert isinstance(pc.count, int)
        assert isinstance(pc.description, str)
        assert isinstance(pc.slug, str)


def test_analyze_graph_sorted_process_counts_deepest_first(linear_library):
    # smelter is deeper (upstream) than press → its entry comes first
    result = _first_result(linear_library, "1 widget")
    descs = [pc.description for pc in result.process_counts]
    iron_idx = next(i for i, d in enumerate(descs) if "iron" in d)
    widget_idx = next(i for i, d in enumerate(descs) if "widget" in d)
    assert iron_idx < widget_idx


def test_analyze_graph_yield_present(linear_library):
    result = _first_result(linear_library, "1 widget")
    assert result.output_quantities is not None


def test_analyze_graph_yield_matches_request_when_balanced(linear_library):
    # 1x press → 1 widget per run; no leak on balanced graph
    result = _first_result(linear_library, "1 widget")
    assert result.output_quantities["widget"] == pytest.approx(1.0)


def test_analyze_graph_yield_reflects_mul_outputs():
    # Process produces 2 widgets per run; requesting 1 → yield == 2
    lib = ProcessLibrary()
    from crafting_process.augment import Augments

    lib.register_augment("double", Augments.mul_outputs(2))
    lib.add_from_text(
        "1 widget | press\n2 iron\n\n@double\n\n2 iron | smelt\n3 ore\n"
    )
    # Use the un-augmented press so yield == 1, as a baseline sanity check
    g = next(
        production_graphs(lib, Ingredients.parse("1 widget"), skip_augments=["double"])
    )
    r = next(analyze_graph(g))
    assert r.output_quantities["widget"] == pytest.approx(1.0)


def test_analyze_graph_process_augments_present(linear_library):
    result = _first_result(linear_library, "1 widget")
    assert result.process_augments is not None


def test_analyze_graph_process_augments_originals_empty(linear_library):
    result = _first_result(linear_library, "1 widget")
    for slug, augs in result.process_augments.items():
        assert augs == []


def test_analyze_graph_is_generator(linear_library):
    g = next(production_graphs(linear_library, Ingredients.parse("1 widget")))
    assert isinstance(analyze_graph(g), types.GeneratorType)


# ---------------------------------------------------------------------------
# analyze_graphs
# ---------------------------------------------------------------------------


def test_analyze_graphs_yields_results(linear_library):
    graphs = list(production_graphs(linear_library, Ingredients.parse("1 widget")))
    assert len(list(analyze_graphs(graphs))) >= 1


def test_analyze_graphs_single_graph_same_count_as_analyze_graph(linear_library):
    g1 = next(production_graphs(linear_library, Ingredients.parse("1 widget")))
    g2 = next(production_graphs(linear_library, Ingredients.parse("1 widget")))
    assert len(list(analyze_graph(g1))) == len(list(analyze_graphs([g2])))


# ---------------------------------------------------------------------------
# printable_analysis
# ---------------------------------------------------------------------------


def _make_analysis(library, transfer_str):
    g = next(production_graphs(library, Ingredients.parse(transfer_str)))
    return analyze_graph(g)


def test_printable_analysis_returns_string(linear_library):
    assert isinstance(
        printable_analysis(_make_analysis(linear_library, "1 widget")), str
    )


def test_printable_analysis_contains_desired_resource(linear_library):
    result = printable_analysis(_make_analysis(linear_library, "1 widget"))
    assert "widget" in result


def test_printable_analysis_contains_process_counts(linear_library):
    result = printable_analysis(_make_analysis(linear_library, "1 widget"))
    assert "1x" in result


def test_printable_analysis_contains_raw_material(linear_library):
    result = printable_analysis(_make_analysis(linear_library, "1 widget"))
    assert "ore" in result


def test_printable_analysis_excludes_sentinel(linear_library):
    result = printable_analysis(_make_analysis(linear_library, "1 widget"))
    process_lines = [
        l.strip()
        for l in result.splitlines()
        if l.strip().startswith(tuple("0123456789"))
    ]
    assert not any(l.endswith("_") or "x _" in l for l in process_lines)


def test_printable_analysis_consumes_generator(linear_library):
    # Documents the known behaviour: once consumed, the generator is exhausted
    aly = _make_analysis(linear_library, "1 widget")
    printable_analysis(aly)
    with pytest.raises(StopIteration):
        next(aly)


def test_printable_analysis_contains_makes_line(linear_library):
    result = printable_analysis(_make_analysis(linear_library, "1 widget"))
    assert "makes:" in result


def test_printable_analysis_makes_line_shows_yield(linear_library):
    result = printable_analysis(_make_analysis(linear_library, "1 widget"))
    assert "1 widget" in result


def test_printable_analysis_show_augments_false_no_at_signs(linear_library):
    # Default: no @augment suffixes on process lines
    result = printable_analysis(
        _make_analysis(linear_library, "1 widget"), show_augments=False
    )
    process_lines = [
        l
        for l in result.splitlines()
        if "x " in l and l.strip().startswith(tuple("0123456789"))
    ]
    assert not any("@" in l for l in process_lines)


def test_printable_analysis_show_augments_true_appends_augments():
    from crafting_process.augment import Augments

    lib = ProcessLibrary()
    lib.register_augment("mk2", Augments.mul_outputs(2))
    lib.add_from_text("""
        1 widget | press
        2 iron

        @mk2

        1 iron | smelt
        3 ore
    """)
    # Both base and mk2 smelt variants are in the library; analyze all graphs
    # so at least one result comes from the mk2-augmented smelt.
    graphs = list(production_graphs(lib, Ingredients.parse("1 widget")))
    result = printable_analysis(analyze_graphs(graphs), show_augments=True)
    assert "@mk2" in result


# ---------------------------------------------------------------------------
# Multi-output processes — baseline
# ---------------------------------------------------------------------------
# Simpler cases that establish correct behaviour before the more complex
# bug-revealing scenarios (cases 1-5 below).


@pytest.fixture
def single_multi_output_provider():
    """One upstream process with two outputs; consumer needs only one.
    smelt: 3 ore -> 2 iron + 1 slag   (slag is an unwanted byproduct)
    press: 2 iron -> 1 widget
    """
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron + 1 slag | smelt
        3 ore

        1 widget | press
        2 iron
    """)
    return lib


@pytest.fixture
def two_direct_providers():
    """Two processes each directly producing the desired output; no further
    recursion needed (no providers for iron or copper exist in this library).
    make_a: 3 iron -> 1 widget
    make_b: 3 copper -> 1 widget
    """
    lib = ProcessLibrary()
    lib.add_from_text("""
        1 widget | make_a
        3 iron

        1 widget | make_b
        3 copper
    """)
    return lib


@pytest.fixture
def two_providers_one_with_byproduct():
    """Two iron providers: one clean, one with a byproduct.
    The byproduct distinguishes the two graphs.
    """
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron | smelt_clean
        3 ore

        2 iron + 1 slag | smelt_messy
        3 ore

        1 widget | press
        2 iron
    """)
    return lib


def test_single_multi_output_provider_yields_one_graph(single_multi_output_provider):
    graphs = list(
        production_graphs(single_multi_output_provider, Ingredients.parse("1 widget"))
    )
    assert len(graphs) == 1


def test_single_multi_output_byproduct_in_open_outputs(single_multi_output_provider):
    g = next(
        production_graphs(single_multi_output_provider, Ingredients.parse("1 widget"))
    )
    open_output_kinds = {kind for (_, kind) in g.open_outputs}
    assert "slag" in open_output_kinds


def test_single_multi_output_needed_output_is_connected(single_multi_output_provider):
    # iron is consumed by press; it should NOT be in open_outputs
    g = next(
        production_graphs(single_multi_output_provider, Ingredients.parse("1 widget"))
    )
    open_output_kinds = {kind for (_, kind) in g.open_outputs}
    assert "iron" not in open_output_kinds


def test_single_multi_output_raw_material_in_open_inputs(single_multi_output_provider):
    g = next(
        production_graphs(single_multi_output_provider, Ingredients.parse("1 widget"))
    )
    open_input_kinds = {kind for (_, kind) in g.open_inputs}
    assert "ore" in open_input_kinds


def test_single_multi_output_iron_pool_exists(single_multi_output_provider):
    g = next(
        production_graphs(single_multi_output_provider, Ingredients.parse("1 widget"))
    )
    assert len(g.find_pools_by_kind("iron")) == 1


def test_two_direct_providers_yields_two_graphs(two_direct_providers):
    graphs = list(
        production_graphs(two_direct_providers, Ingredients.parse("1 widget"))
    )
    assert len(graphs) == 2


def test_two_direct_providers_each_graph_has_one_upstream_process(two_direct_providers):
    # Each graph: sink + exactly one widget-producer (no further upstream)
    graphs = list(
        production_graphs(two_direct_providers, Ingredients.parse("1 widget"))
    )
    for g in graphs:
        widget_producers = [p for p in g.processes.values() if p.outputs["widget"] > 0]
        assert len(widget_producers) == 1


def test_two_direct_providers_cover_both_raw_materials(two_direct_providers):
    graphs = list(
        production_graphs(two_direct_providers, Ingredients.parse("1 widget"))
    )
    all_open_input_kinds = {kind for g in graphs for (_, kind) in g.open_inputs}
    assert "iron" in all_open_input_kinds
    assert "copper" in all_open_input_kinds


def test_two_direct_providers_graphs_use_different_inputs(two_direct_providers):
    graphs = list(
        production_graphs(two_direct_providers, Ingredients.parse("1 widget"))
    )
    input_sets = [frozenset(k for (_, k) in g.open_inputs) for g in graphs]
    assert input_sets[0] != input_sets[1]


def test_two_providers_one_with_byproduct_yields_two_graphs(
    two_providers_one_with_byproduct,
):
    graphs = list(
        production_graphs(
            two_providers_one_with_byproduct, Ingredients.parse("1 widget")
        )
    )
    assert len(graphs) == 2


def test_two_providers_one_graph_has_no_slag(two_providers_one_with_byproduct):
    graphs = list(
        production_graphs(
            two_providers_one_with_byproduct, Ingredients.parse("1 widget")
        )
    )
    slag_counts = [sum(1 for (_, k) in g.open_outputs if k == "slag") for g in graphs]
    assert 0 in slag_counts


def test_two_providers_one_graph_has_slag(two_providers_one_with_byproduct):
    graphs = list(
        production_graphs(
            two_providers_one_with_byproduct, Ingredients.parse("1 widget")
        )
    )
    slag_counts = [sum(1 for (_, k) in g.open_outputs if k == "slag") for g in graphs]
    assert 1 in slag_counts


# ---------------------------------------------------------------------------
# Fixtures for production_graphs branching cases
# ---------------------------------------------------------------------------


@pytest.fixture
def two_single_output_providers():
    """Two independent single-output iron providers feeding a press."""
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron | smelt_a
        3 ore_a

        2 iron | smelt_b
        3 ore_b

        1 widget | press
        2 iron
    """)
    return lib


@pytest.fixture
def two_non_overlapping_multi_output_providers():
    """Two iron providers each with a unique byproduct (no output-kind overlap)."""
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron + 1 slag_a | smelt_a
        3 ore_a

        2 iron + 1 slag_b | smelt_b
        3 ore_b

        1 widget | press
        2 iron
    """)
    return lib


@pytest.fixture
def overlapping_multi_output_providers():
    """Two providers each producing iron + copper + a unique slag.
    Widget assembly needs both iron and copper.
    Bug: _production_graphs appends each provider once per desired kind it
    satisfies, so proc_a appears at index 0 (for iron) AND index 2 (for copper),
    producing degenerate combos that instantiate the same process twice."""
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron + 1 copper + 3 slag_a | process_a
        5 ore_a

        2 iron + 1 copper + 3 slag_b | process_b
        5 ore_b

        1 widget | assemble
        2 iron + 1 copper
    """)
    return lib


@pytest.fixture
def loop_library():
    """Circular dependency: widget → iron → copper → iron.
    No loop detection exists, so production_graphs recurses infinitely."""
    lib = ProcessLibrary()
    lib.add_from_text("""
        1 iron | smelt
        1 copper

        1 copper | refine
        1 iron

        1 widget | assemble
        1 iron
    """)
    return lib


@pytest.fixture
def branching_library():
    """Two paths to widget: a direct one-step process and a two-step chain."""
    lib = ProcessLibrary()
    lib.add_from_text("""
        1 widget | direct
        2 raw

        2 iron | smelt
        3 ore

        1 widget | press
        2 iron
    """)
    return lib


# ---------------------------------------------------------------------------
# Case 1: Two single-output processes for the same kind
# ---------------------------------------------------------------------------


def test_two_single_output_providers_yields_two_graphs(two_single_output_providers):
    graphs = list(
        production_graphs(two_single_output_providers, Ingredients.parse("1 widget"))
    )
    assert len(graphs) == 2


def test_two_single_output_providers_graphs_use_different_smelters(
    two_single_output_providers,
):
    graphs = list(
        production_graphs(two_single_output_providers, Ingredients.parse("1 widget"))
    )
    # Each graph should leave a different raw-material open_input (ore_a vs ore_b)
    open_input_kinds = [frozenset(kind for (_, kind) in g.open_inputs) for g in graphs]
    assert open_input_kinds[0] != open_input_kinds[1]


def test_two_single_output_providers_cover_ore_a_and_ore_b(two_single_output_providers):
    graphs = list(
        production_graphs(two_single_output_providers, Ingredients.parse("1 widget"))
    )
    all_open_input_kinds = set()
    for g in graphs:
        for _, kind in g.open_inputs:
            all_open_input_kinds.add(kind)
    assert "ore_a" in all_open_input_kinds
    assert "ore_b" in all_open_input_kinds


# ---------------------------------------------------------------------------
# Case 2: Two multi-output providers with no output-kind overlap
# ---------------------------------------------------------------------------


def test_non_overlapping_multi_output_providers_yields_two_graphs(
    two_non_overlapping_multi_output_providers,
):
    graphs = list(
        production_graphs(
            two_non_overlapping_multi_output_providers, Ingredients.parse("1 widget")
        )
    )
    assert len(graphs) == 2


def test_non_overlapping_multi_output_providers_byproduct_in_open_outputs(
    two_non_overlapping_multi_output_providers,
):
    # Each graph has exactly one slag byproduct as an open_output
    graphs = list(
        production_graphs(
            two_non_overlapping_multi_output_providers, Ingredients.parse("1 widget")
        )
    )
    for g in graphs:
        slag_outputs = [kind for (_, kind) in g.open_outputs if "slag" in kind]
        assert (
            len(slag_outputs) == 1
        ), f"Expected exactly 1 slag open_output, got {slag_outputs}"


def test_non_overlapping_multi_output_providers_both_slags_represented(
    two_non_overlapping_multi_output_providers,
):
    graphs = list(
        production_graphs(
            two_non_overlapping_multi_output_providers, Ingredients.parse("1 widget")
        )
    )
    all_slag_kinds = {
        kind for g in graphs for (_, kind) in g.open_outputs if "slag" in kind
    }
    assert "slag_a" in all_slag_kinds
    assert "slag_b" in all_slag_kinds


# ---------------------------------------------------------------------------
# Case 3: Two multi-output providers where 2 of 3 outputs overlap
# ---------------------------------------------------------------------------


def test_overlapping_providers_yields_graphs(overlapping_multi_output_providers):
    graphs = list(
        production_graphs(
            overlapping_multi_output_providers, Ingredients.parse("1 widget")
        )
    )
    assert len(graphs) >= 1


def test_overlapping_providers_single_process_sufficient(
    overlapping_multi_output_providers,
):
    # A single upstream provider (process_a or process_b) covers both iron and
    # copper.  At least one yielded graph should have exactly one iron-producing
    # process (not two copies of the same provider).
    graphs = list(
        production_graphs(
            overlapping_multi_output_providers, Ingredients.parse("1 widget")
        )
    )
    iron_producer_counts = [
        sum(1 for p in g.processes.values() if p.outputs["iron"] > 0) for g in graphs
    ]
    assert (
        1 in iron_producer_counts
    ), f"No graph with a single iron provider found; counts were {iron_producer_counts}"


def test_overlapping_providers_no_duplicate_processes(
    overlapping_multi_output_providers,
):
    # Bug: _production_graphs adds each provider once per desired kind it
    # satisfies, so process_a ends up at two indices and can be instantiated
    # twice in the same graph.  Each graph should contain at most one instance
    # of any given process (unique describe() strings).
    graphs = list(
        production_graphs(
            overlapping_multi_output_providers, Ingredients.parse("1 widget")
        )
    )
    for g in graphs:
        describes = [p.describe() for p in g.processes.values()]
        assert len(describes) == len(
            set(describes)
        ), f"Duplicate processes in graph: {describes}"


# ---------------------------------------------------------------------------
# Case 4: Dependency loop detection
# ---------------------------------------------------------------------------


def test_production_graphs_terminates_on_dependency_loop(loop_library):
    # widget → iron (via smelt, needs copper) → copper (via refine, needs iron) → loop
    # Expected with loop detection: terminates (yields nothing or partial graphs).
    # Bug: no loop detection → RecursionError.
    try:
        list(production_graphs(loop_library, Ingredients.parse("1 widget")))
    except RecursionError:
        pytest.fail(
            "production_graphs hit RecursionError — no dependency loop detection"
        )


# ---------------------------------------------------------------------------
# Case 5: Both a direct (depth=1) and a chained (depth>1) path available
# ---------------------------------------------------------------------------


def test_branching_library_yields_two_graphs(branching_library):
    graphs = list(production_graphs(branching_library, Ingredients.parse("1 widget")))
    assert len(graphs) == 2


def test_branching_library_graphs_have_different_process_counts(branching_library):
    graphs = list(production_graphs(branching_library, Ingredients.parse("1 widget")))
    counts = sorted(len(g.processes) for g in graphs)
    # direct path: [direct, sink] = 2; chain path: [smelt, press, sink] = 3
    assert counts[0] < counts[1]


def test_branching_library_direct_path_exists(branching_library):
    # One graph has "raw" as its only open_input (the direct process)
    graphs = list(production_graphs(branching_library, Ingredients.parse("1 widget")))
    open_input_sets = [frozenset(k for (_, k) in g.open_inputs) for g in graphs]
    assert frozenset(["raw"]) in open_input_sets


def test_branching_library_chain_path_exists(branching_library):
    # One graph has "ore" as its only open_input (the smelt+press chain)
    graphs = list(production_graphs(branching_library, Ingredients.parse("1 widget")))
    open_input_sets = [frozenset(k for (_, k) in g.open_inputs) for g in graphs]
    assert frozenset(["ore"]) in open_input_sets


def test_branching_library_direct_path_has_shallower_depth(branching_library):
    graphs = list(production_graphs(branching_library, Ingredients.parse("1 widget")))
    # Identify direct vs chain by their open_input kind
    direct_graph = next(
        g for g in graphs if any(kind == "raw" for (_, kind) in g.open_inputs)
    )
    chain_graph = next(
        g for g in graphs if any(kind == "ore" for (_, kind) in g.open_inputs)
    )
    direct_depths = direct_graph.process_depths()
    chain_depths = chain_graph.process_depths()
    assert max(direct_depths.values()) < max(chain_depths.values())


# ---------------------------------------------------------------------------
# Case 6: Single multi-output process covering all consumer needs
# ---------------------------------------------------------------------------


@pytest.fixture
def combo_provider_library():
    """One process producing both iron and copper; consumer needs both.
    Tests that a multi-output provider is not indexed twice (dedup fix)."""
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron + 1 copper | mine_combo
        5 ore

        1 widget | assemble
        2 iron + 1 copper
    """)
    return lib


def test_combo_provider_yields_one_graph(combo_provider_library):
    graphs = list(
        production_graphs(combo_provider_library, Ingredients.parse("1 widget"))
    )
    assert len(graphs) == 1


def test_combo_provider_graph_has_no_duplicate_processes(combo_provider_library):
    graphs = list(
        production_graphs(combo_provider_library, Ingredients.parse("1 widget"))
    )
    g = graphs[0]
    # Only mine_combo, assemble, and the sink "_" process
    assert len(g.processes) == 3


def test_combo_provider_both_kinds_present(combo_provider_library):
    graphs = list(
        production_graphs(combo_provider_library, Ingredients.parse("1 widget"))
    )
    g = graphs[0]
    pool_kinds = {pool["kind"] for pool in g.pools.values()}
    assert "iron" in pool_kinds
    assert "copper" in pool_kinds


def test_combo_provider_mine_combo_connected_to_both_pools(combo_provider_library):
    graphs = list(
        production_graphs(combo_provider_library, Ingredients.parse("1 widget"))
    )
    g = graphs[0]
    # mine_combo should be a source in both the iron pool and the copper pool
    mine_name = next(
        n for n in g.processes if "mine_combo" in g.processes[n].describe()
    )
    iron_pool = next(p for p in g.pools.values() if p["kind"] == "iron")
    copper_pool = next(p for p in g.pools.values() if p["kind"] == "copper")
    assert mine_name in iron_pool["inputs"]
    assert mine_name in copper_pool["inputs"]


def test_combo_provider_ore_is_open_input(combo_provider_library):
    graphs = list(
        production_graphs(combo_provider_library, Ingredients.parse("1 widget"))
    )
    g = graphs[0]
    open_input_kinds = {kind for (_, kind) in g.open_inputs}
    assert "ore" in open_input_kinds


def test_combo_provider_analyze_graph_runs(combo_provider_library):
    graphs = list(
        production_graphs(combo_provider_library, Ingredients.parse("1 widget"))
    )
    results = list(analyze_graph(graphs[0]))
    assert len(results) >= 1
    assert results[0].leak == 0.0


# ---------------------------------------------------------------------------
# Case 7: Shared intermediate / diamond dependency
# ---------------------------------------------------------------------------


@pytest.fixture
def shared_intermediate_library():
    """make_x (produces 2X) feeds both make_y (needs 1X) and make_z (needs 1X).
    Tests that a single upstream process connects to multiple consumers."""
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 X | make_x
        3 ore_a

        1 Y | make_y
        1 X + 2 ore_b

        1 Z | make_z
        1 X + 3 ore_c

        1 final | combine
        1 Y + 1 Z
    """)
    return lib


def test_shared_intermediate_yields_one_graph(shared_intermediate_library):
    graphs = list(
        production_graphs(shared_intermediate_library, Ingredients.parse("1 final"))
    )
    assert len(graphs) == 1


def test_shared_intermediate_process_count(shared_intermediate_library):
    graphs = list(
        production_graphs(shared_intermediate_library, Ingredients.parse("1 final"))
    )
    g = graphs[0]
    # make_x, make_y, make_z, combine, sink "_"
    assert len(g.processes) == 5


def test_shared_intermediate_x_pool_has_one_producer(shared_intermediate_library):
    graphs = list(
        production_graphs(shared_intermediate_library, Ingredients.parse("1 final"))
    )
    g = graphs[0]
    x_pools = [p for p in g.pools.values() if p["kind"] == "X"]
    assert len(x_pools) == 1
    assert len(x_pools[0]["inputs"]) == 1


def test_shared_intermediate_x_pool_has_two_consumers(shared_intermediate_library):
    graphs = list(
        production_graphs(shared_intermediate_library, Ingredients.parse("1 final"))
    )
    g = graphs[0]
    x_pools = [p for p in g.pools.values() if p["kind"] == "X"]
    assert len(x_pools[0]["outputs"]) == 2


def test_shared_intermediate_raw_inputs(shared_intermediate_library):
    graphs = list(
        production_graphs(shared_intermediate_library, Ingredients.parse("1 final"))
    )
    g = graphs[0]
    open_input_kinds = {kind for (_, kind) in g.open_inputs}
    assert open_input_kinds == {"ore_a", "ore_b", "ore_c"}


def test_shared_intermediate_analyze_graph_runs(shared_intermediate_library):
    graphs = list(
        production_graphs(shared_intermediate_library, Ingredients.parse("1 final"))
    )
    results = list(analyze_graph(graphs[0]))
    assert len(results) >= 1
    assert results[0].total_processes == 5  # make_x, make_y, make_z, combine, sink "_"


def test_shared_intermediate_analyze_graph_zero_leak(shared_intermediate_library):
    graphs = list(
        production_graphs(shared_intermediate_library, Ingredients.parse("1 final"))
    )
    results = list(analyze_graph(graphs[0]))
    assert results[0].leak == 0.0


# ---------------------------------------------------------------------------
# Case 8: max_overlap=3 with 3 kinds × 3 providers
# ---------------------------------------------------------------------------


@pytest.fixture
def gadget_library():
    """3 independent providers per kind (iron/copper/glass), 1 assembler.
    At max_overlap=2: one provider per kind, all combos of 2 providers per kind.
    At max_overlap=3: adds the combo using all 3 providers for every kind."""
    lib = ProcessLibrary()
    lib.add_from_text("""
        2 iron | smelt_a
        3 ore_a

        2 iron | smelt_b
        3 ore_b

        2 iron | smelt_c
        3 ore_c

        1 copper | mine_a
        2 coal_a

        1 copper | mine_b
        2 coal_b

        1 copper | mine_c
        2 coal_c

        1 glass | forge_a
        3 sand_a

        1 glass | forge_b
        3 sand_b

        1 glass | forge_c
        3 sand_c

        1 gadget | assemble
        2 iron + 1 copper + 1 glass
    """)
    return lib


def test_gadget_max_overlap_2_graph_count(gadget_library):
    graphs = list(
        production_graphs(gadget_library, Ingredients.parse("1 gadget"), max_overlap=2)
    )
    # input_combinations iterates i in range(1, min(max_overlap, len(kinds))+1).
    # len(kinds)=3, max_overlap=2 → i in [1, 2].
    # For each i, it forms one combo-tuple per unique flattening of
    # product(*[C(providers_for_kind, i) for kind in kinds]).
    # unique() deduplicates across i values. Empirical result: 54 graphs.
    assert len(graphs) == 54


def test_gadget_max_overlap_3_graph_count(gadget_library):
    graphs = list(
        production_graphs(gadget_library, Ingredients.parse("1 gadget"), max_overlap=3)
    )
    # max_overlap=3 adds i=3: C(3,3)=1 per kind → 1 extra combo (all 9 providers).
    # Total: 54 + 1 = 55 graphs.
    assert len(graphs) == 55


def test_gadget_max_overlap_3_has_all_nine_providers(gadget_library):
    """The max_overlap=3 combo that uses all 3 providers per kind should exist."""
    graphs = list(
        production_graphs(gadget_library, Ingredients.parse("1 gadget"), max_overlap=3)
    )
    # Largest graph: 9 upstream + assemble + sink = 11 processes
    largest = max(graphs, key=lambda g: len(g.processes))
    assert len(largest.processes) == 11


def test_gadget_max_overlap_1_graph_count(gadget_library):
    # Only one provider per kind: 3^3 = 27 graphs
    graphs = list(
        production_graphs(gadget_library, Ingredients.parse("1 gadget"), max_overlap=1)
    )
    assert len(graphs) == 27


# ---------------------------------------------------------------------------
# skip_augments / only_augments in production_graphs
# ---------------------------------------------------------------------------


@pytest.fixture
def augmented_iron_library():
    """smelt (original), smelt @mk2, smelt @mk3; press to widget (no augments)."""
    from crafting_process.augment import Augments

    lib = ProcessLibrary()
    lib.register_augment("mk2", Augments.mul_speed(2.0))
    lib.register_augment("mk3", Augments.mul_speed(3.0))
    # press comes before the @-block so it is not augmented
    lib.add_from_text("""
        1 widget | press
        2 iron

        @mk2
        @mk3

        2 iron | smelt duration=6
        3 ore
    """)
    return lib


def test_skip_augments_excludes_augmented_graphs(augmented_iron_library):
    # Without skip: 3 smelt variants × 1 press = 3 graphs
    # With skip_augments=[mk2, mk3]: only original smelt → 1 graph
    graphs = list(
        production_graphs(
            augmented_iron_library,
            Ingredients.parse("1 widget"),
            skip_augments=["mk2", "mk3"],
        )
    )
    assert len(graphs) == 1
    # Confirm the graph uses the original smelt (no applied_augments)
    procs = list(graphs[0].processes.values())
    assert all(p.applied_augments == [] for p in procs)


def test_only_augments_restricts_to_specified(augmented_iron_library):
    # only_augments=["mk2"]: originals + mk2 variants → 2 smelt candidates → 2 graphs
    graphs = list(
        production_graphs(
            augmented_iron_library,
            Ingredients.parse("1 widget"),
            only_augments=["mk2"],
        )
    )
    assert len(graphs) == 2


def test_only_augments_empty_list_originals_only(augmented_iron_library):
    graphs = list(
        production_graphs(
            augmented_iron_library,
            Ingredients.parse("1 widget"),
            only_augments=[],
        )
    )
    assert len(graphs) == 1
    procs = list(graphs[0].processes.values())
    assert all(p.applied_augments == [] for p in procs)


def test_no_augment_filter_sees_all_variants(augmented_iron_library):
    graphs = list(
        production_graphs(
            augmented_iron_library,
            Ingredients.parse("1 widget"),
        )
    )
    assert len(graphs) == 3


# ---------------------------------------------------------------------------
# PlanResult / ProcessCount dataclasses
# ---------------------------------------------------------------------------


def test_analyze_graph_returns_plan_result(linear_library):
    from crafting_process.orchestration import PlanResult

    result = _first_result(linear_library, "1 widget")
    assert isinstance(result, PlanResult)


def test_plan_result_process_counts_are_process_count(linear_library):
    from crafting_process.orchestration import ProcessCount

    result = _first_result(linear_library, "1 widget")
    assert all(isinstance(pc, ProcessCount) for pc in result.process_counts)


def test_process_count_fields(linear_library):
    result = _first_result(linear_library, "1 widget")
    pc = result.process_counts[0]
    assert hasattr(pc, "count")
    assert hasattr(pc, "description")
    assert hasattr(pc, "slug")


# ---------------------------------------------------------------------------
# plan()
# ---------------------------------------------------------------------------


def test_plan_returns_list(linear_library):
    from crafting_process.orchestration import plan, PlanResult

    results = plan(linear_library, "1 widget")
    assert isinstance(results, list)
    assert all(isinstance(r, PlanResult) for r in results)


def test_plan_accepts_string_transfer(linear_library):
    from crafting_process.orchestration import plan

    results = plan(linear_library, "1 widget")
    assert len(results) >= 1


def test_plan_accepts_ingredients_transfer(linear_library):
    from crafting_process.orchestration import plan

    results = plan(linear_library, Ingredients.parse("1 widget"))
    assert len(results) >= 1


def test_plan_n_limits_results(linear_library):
    from crafting_process.orchestration import plan

    results = plan(linear_library, "1 widget", n=1)
    assert len(results) <= 1


def test_plan_sorted_by_leak_then_total_processes(linear_library):
    from crafting_process.orchestration import plan

    results = plan(linear_library, "1 widget", n=10)
    for a, b in zip(results, results[1:]):
        assert (a.leak, a.total_processes) <= (b.leak, b.total_processes)
