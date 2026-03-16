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
        2 iron | smelt:
        3 ore

        1 widget | press:
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
        Process(outputs=Ingredients.parse("1 widget"), inputs=Ingredients.parse("2 iron")),
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
    g = next(production_graphs(
        linear_library, Ingredients.parse("1 widget"), stop_kinds=["iron"]
    ))
    descriptions = {p.describe() for p in g.processes.values()}
    assert any("widget" in d for d in descriptions)
    assert not any("iron" in d for d in descriptions)


def test_production_graphs_skip_processes_excludes_process(linear_library):
    # skip_processes=["smelt"] removes the smelter; no producers for iron remain
    g = next(production_graphs(
        linear_library, Ingredients.parse("1 widget"), skip_processes=["smelt"]
    ))
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
    assert result["desired"]["widget"] == 1


def test_analyze_graph_leak_is_float(linear_library):
    assert isinstance(_first_result(linear_library, "1 widget")["leak"], float)


def test_analyze_graph_leak_is_zero_for_balanced(linear_library):
    assert _first_result(linear_library, "1 widget")["leak"] == pytest.approx(0.0)


def test_analyze_graph_total_processes_includes_sentinel(linear_library):
    # smelter=1, press=1, sink=1 → total_processes=3 (sentinel counted)
    assert _first_result(linear_library, "1 widget")["total_processes"] == 3


def test_analyze_graph_inputs_lists_ore(linear_library):
    result = _first_result(linear_library, "1 widget")
    kinds = [kind for (_, kind) in result["inputs"]]
    assert "ore" in kinds


def test_analyze_graph_inputs_excludes_sentinel(linear_library):
    result = _first_result(linear_library, "1 widget")
    kinds = [kind for (_, kind) in result["inputs"]]
    assert "_" not in kinds


def test_analyze_graph_ore_amount_correct(linear_library):
    result = _first_result(linear_library, "1 widget")
    ore_entries = [(amt, kind) for (amt, kind) in result["inputs"] if kind == "ore"]
    assert ore_entries == [(3, "ore")]


def test_analyze_graph_sorted_process_counts_is_list(linear_library):
    result = _first_result(linear_library, "1 widget")
    assert isinstance(result["sorted_process_counts"], list)


def test_analyze_graph_sorted_process_counts_are_triples(linear_library):
    result = _first_result(linear_library, "1 widget")
    for count, desc, name in result["sorted_process_counts"]:
        assert isinstance(count, int)
        assert isinstance(desc, str)
        assert isinstance(name, str)


def test_analyze_graph_sorted_process_counts_deepest_first(linear_library):
    # smelter is deeper (upstream) than press → its entry comes first
    result = _first_result(linear_library, "1 widget")
    descs = [desc for (_, desc, _) in result["sorted_process_counts"]]
    iron_idx = next(i for i, d in enumerate(descs) if "iron" in d)
    widget_idx = next(i for i, d in enumerate(descs) if "widget" in d)
    assert iron_idx < widget_idx


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
    assert isinstance(printable_analysis(_make_analysis(linear_library, "1 widget")), str)


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
        l.strip() for l in result.splitlines()
        if l.strip().startswith(tuple("0123456789"))
    ]
    assert not any(l.endswith("_") or "x _" in l for l in process_lines)


def test_printable_analysis_consumes_generator(linear_library):
    # Documents the known behaviour: once consumed, the generator is exhausted
    aly = _make_analysis(linear_library, "1 widget")
    printable_analysis(aly)
    with pytest.raises(StopIteration):
        next(aly)
