import numpy as np
import pytest

from crafting_process.graph import GraphBuilder
from crafting_process.process import Ingredients, Process

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ore_smelter():
    """3 ore -> 2 iron  (no duration — batch only)"""
    return Process(
        outputs=Ingredients.parse("2 iron"),
        inputs=Ingredients.parse("3 ore"),
    )


def make_widget_press():
    """2 iron -> 1 widget"""
    return Process(
        outputs=Ingredients.parse("1 widget"),
        inputs=Ingredients.parse("2 iron"),
    )


def make_widget_packager():
    """1 widget -> 1 package"""
    return Process(
        outputs=Ingredients.parse("1 package"),
        inputs=Ingredients.parse("1 widget"),
    )


def make_ore_smelter_timed():
    """3 ore -> 2 iron, duration=2.0  →  transfer_rate[iron] = +1.0"""
    return Process(
        outputs=Ingredients.parse("2 iron"),
        inputs=Ingredients.parse("3 ore"),
        duration=2.0,
    )


def make_widget_press_timed():
    """2 iron -> 1 widget, duration=1.0  →  transfer_rate[iron] = -2.0"""
    return Process(
        outputs=Ingredients.parse("1 widget"),
        inputs=Ingredients.parse("2 iron"),
        duration=1.0,
    )


def make_widget_packager_timed():
    """1 widget -> 1 package, duration=4.0"""
    return Process(
        outputs=Ingredients.parse("1 package"),
        inputs=Ingredients.parse("1 widget"),
        duration=4.0,
    )


def two_process_graph_timed():
    """timed smelter -> iron pool -> timed press; returns (graph, smelter_name, press_name)"""
    g_up = GraphBuilder.from_process(make_ore_smelter_timed(), name="smelter")
    g_down = GraphBuilder.from_process(make_widget_press_timed(), name="press")
    g = g_up.output_into(g_down)
    return g, "smelter", "press"


def two_process_graph():
    """ore_smelter -> iron pool -> widget_press; returns (graph, smelter_name, press_name)"""
    smelter = make_ore_smelter()
    press = make_widget_press()
    g_up = GraphBuilder.from_process(smelter, name="smelter")
    g_down = GraphBuilder.from_process(press, name="press")
    g = g_up.output_into(g_down)
    return g, "smelter", "press"


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


def test_repr_zero_processes():
    # pluralization uses > 1, so 0 counts as singular (existing behaviour)
    g = GraphBuilder()
    assert repr(g) == "<GraphBuilder [0 node]>"


def test_repr_one_process():
    g = GraphBuilder.from_process(make_ore_smelter(), name="s")
    assert repr(g) == "<GraphBuilder [1 node]>"


def test_repr_two_processes():
    g, _, _ = two_process_graph()
    assert repr(g) == "<GraphBuilder [2 nodes]>"


# ---------------------------------------------------------------------------
# add_process / from_process
# ---------------------------------------------------------------------------


def test_add_process_registers_process():
    g = GraphBuilder()
    g.add_process(make_ore_smelter(), name="s")
    assert "s" in g.processes


def test_add_process_populates_open_outputs():
    g = GraphBuilder()
    g.add_process(make_ore_smelter(), name="s")
    assert ("s", "iron") in g.open_outputs


def test_add_process_populates_open_inputs():
    g = GraphBuilder()
    g.add_process(make_ore_smelter(), name="s")
    assert ("s", "ore") in g.open_inputs


def test_add_process_multiple_outputs():
    p = Process(
        outputs=Ingredients.parse("1 widget + 2 scrap"),
        inputs=Ingredients.parse("3 iron"),
    )
    g = GraphBuilder()
    g.add_process(p, name="p")
    assert ("p", "widget") in g.open_outputs
    assert ("p", "scrap") in g.open_outputs


def test_from_process_returns_graph_with_one_process():
    g = GraphBuilder.from_process(make_ore_smelter(), name="s")
    assert "s" in g.processes
    assert len(g.processes) == 1


def test_add_process_returns_metadata():
    g = GraphBuilder()
    result = g.add_process(make_ore_smelter(), name="s")
    assert result["name"] == "s"
    assert "iron" in result["outputs"]
    assert "ore" in result["inputs"]


# ---------------------------------------------------------------------------
# output_into
# ---------------------------------------------------------------------------


def test_output_into_creates_pool_for_shared_kind():
    g, _, _ = two_process_graph()
    iron_pools = g.find_pools_by_kind("iron")
    assert len(iron_pools) == 1


def test_output_into_pool_has_producer_in_inputs():
    # pool["inputs"] = processes that produce INTO the pool
    g, smelter, _ = two_process_graph()
    iron_pool = g.find_pools_by_kind("iron")[0]
    assert smelter in iron_pool["inputs"]


def test_output_into_pool_has_consumer_in_outputs():
    # pool["outputs"] = processes that consume FROM the pool
    g, _, press = two_process_graph()
    iron_pool = g.find_pools_by_kind("iron")[0]
    assert press in iron_pool["outputs"]


def test_output_into_removes_connected_kind_from_open_outputs():
    g, smelter, _ = two_process_graph()
    assert (smelter, "iron") not in g.open_outputs


def test_output_into_removes_connected_kind_from_open_inputs():
    g, _, press = two_process_graph()
    assert (press, "iron") not in g.open_inputs


def test_output_into_leaves_unconnected_open_outputs():
    g, _, press = two_process_graph()
    # widget is produced by press and not consumed by anything
    assert (press, "widget") in g.open_outputs


def test_output_into_leaves_unconnected_open_inputs():
    g, smelter, _ = two_process_graph()
    # ore is consumed by smelter and not produced by anything
    assert (smelter, "ore") in g.open_inputs


def test_output_into_is_non_mutating():
    smelter = make_ore_smelter()
    press = make_widget_press()
    g_up = GraphBuilder.from_process(smelter, name="smelter")
    g_down = GraphBuilder.from_process(press, name="press")
    _ = g_up.output_into(g_down)
    # originals should be unchanged
    assert ("smelter", "iron") in g_up.open_outputs
    assert ("press", "iron") in g_down.open_inputs


def test_output_into_contains_all_processes():
    g, _, _ = two_process_graph()
    assert "smelter" in g.processes
    assert "press" in g.processes


# ---------------------------------------------------------------------------
# unify
# ---------------------------------------------------------------------------


def test_unify_merges_processes():
    g1 = GraphBuilder.from_process(make_ore_smelter(), name="s")
    g2 = GraphBuilder.from_process(make_widget_press(), name="p")
    g1.unify(g2)
    assert "s" in g1.processes
    assert "p" in g1.processes


def test_unify_extends_open_inputs():
    g1 = GraphBuilder.from_process(make_ore_smelter(), name="s")
    g2 = GraphBuilder.from_process(make_widget_press(), name="p")
    g1.unify(g2)
    assert ("s", "ore") in g1.open_inputs
    assert ("p", "iron") in g1.open_inputs


def test_unify_extends_open_outputs():
    g1 = GraphBuilder.from_process(make_ore_smelter(), name="s")
    g2 = GraphBuilder.from_process(make_widget_press(), name="p")
    g1.unify(g2)
    assert ("s", "iron") in g1.open_outputs
    assert ("p", "widget") in g1.open_outputs


def test_unify_does_not_create_pools():
    g1 = GraphBuilder.from_process(make_ore_smelter(), name="s")
    g2 = GraphBuilder.from_process(make_widget_press(), name="p")
    g1.unify(g2)
    assert len(g1.pools) == 0


def test_unify_mutates_self():
    g1 = GraphBuilder.from_process(make_ore_smelter(), name="s")
    g2 = GraphBuilder.from_process(make_widget_press(), name="p")
    result = g1.unify(g2)
    assert result is g1


# ---------------------------------------------------------------------------
# union (classmethod)
# ---------------------------------------------------------------------------


def test_union_returns_new_graph():
    g1 = GraphBuilder.from_process(make_ore_smelter(), name="s")
    g2 = GraphBuilder.from_process(make_widget_press(), name="p")
    g3 = GraphBuilder.union(g1, g2)
    assert g3 is not g1
    assert g3 is not g2


def test_union_does_not_mutate_operands():
    g1 = GraphBuilder.from_process(make_ore_smelter(), name="s")
    g2 = GraphBuilder.from_process(make_widget_press(), name="p")
    _ = GraphBuilder.union(g1, g2)
    assert len(g1.processes) == 1
    assert len(g2.processes) == 1


def test_union_contains_all_processes():
    g1 = GraphBuilder.from_process(make_ore_smelter(), name="s")
    g2 = GraphBuilder.from_process(make_widget_press(), name="p")
    g3 = GraphBuilder.union(g1, g2)
    assert "s" in g3.processes
    assert "p" in g3.processes


# ---------------------------------------------------------------------------
# coalesce_pools
# ---------------------------------------------------------------------------


def test_coalesce_pools_merges_two_pools_of_same_kind():
    g = GraphBuilder()
    g.add_pool("iron", name="pool1")
    g.add_pool("iron", name="pool2")
    merged = g.coalesce_pools("pool1", "pool2")
    assert merged["kind"] == "iron"
    assert "pool1" not in g.pools
    assert "pool2" not in g.pools


def test_coalesce_pools_records_aliases():
    g = GraphBuilder()
    g.add_pool("iron", name="pool1")
    g.add_pool("iron", name="pool2")
    merged = g.coalesce_pools("pool1", "pool2")
    assert g.pool_aliases["pool1"] == merged["name"]
    assert g.pool_aliases["pool2"] == merged["name"]


def test_coalesce_pools_combines_members():
    g = GraphBuilder()
    smelter = make_ore_smelter()
    press = make_widget_press()
    g.add_process(smelter, name="s")
    g.add_process(press, name="p")
    pool1 = g.add_pool("iron", name="pool1")
    pool2 = g.add_pool("iron", name="pool2")
    pool1["inputs"].append("s")
    pool2["outputs"].append("p")
    merged = g.coalesce_pools("pool1", "pool2")
    assert "s" in merged["inputs"]
    assert "p" in merged["outputs"]


def test_coalesce_pools_raises_on_mismatched_kinds():
    g = GraphBuilder()
    g.add_pool("iron", name="pool1")
    g.add_pool("copper", name="pool2")
    with pytest.raises(ValueError, match="Cannot coalesce"):
        g.coalesce_pools("pool1", "pool2")


def test_coalesce_pools_noop_on_same_pool():
    g = GraphBuilder()
    pool = g.add_pool("iron", name="pool1")
    result = g.coalesce_pools("pool1", "pool1")
    assert result is pool


# ---------------------------------------------------------------------------
# build_batch_matrix — most important correctness test
# ---------------------------------------------------------------------------


def test_build_batch_matrix_producer_is_positive():
    g, smelter, _ = two_process_graph()
    result = g.build_batch_matrix()
    matrix = result["matrix"]
    processes = result["processes"]
    smelter_col = processes.index(smelter)
    iron_row = [
        i for i, p in enumerate(result["pools"]) if g.pools[p]["kind"] == "iron"
    ][0]
    assert matrix[iron_row][smelter_col] > 0


def test_build_batch_matrix_consumer_is_negative():
    g, _, press = two_process_graph()
    result = g.build_batch_matrix()
    matrix = result["matrix"]
    processes = result["processes"]
    press_col = processes.index(press)
    iron_row = [
        i for i, p in enumerate(result["pools"]) if g.pools[p]["kind"] == "iron"
    ][0]
    assert matrix[iron_row][press_col] < 0


def test_build_batch_matrix_correct_values():
    # smelter: 3 ore -> 2 iron  → transfer[iron] = +2
    # press:   2 iron -> 1 widget → transfer[iron] = -2
    g, smelter, press = two_process_graph()
    result = g.build_batch_matrix()
    matrix = result["matrix"]
    processes = result["processes"]
    pools = result["pools"]
    smelter_col = processes.index(smelter)
    press_col = processes.index(press)
    iron_pool_name = next(p for p in pools if g.pools[p]["kind"] == "iron")
    iron_row = pools.index(iron_pool_name)
    assert matrix[iron_row][smelter_col] == pytest.approx(2.0)
    assert matrix[iron_row][press_col] == pytest.approx(-2.0)


def test_build_batch_matrix_unrelated_process_is_zero():
    # Add a third process that doesn't touch iron at all
    g, smelter, press = two_process_graph()
    packager = make_widget_packager()
    # Connect press -> widget pool -> packager
    GraphBuilder.from_process(packager, name="packager")
    GraphBuilder.from_process(g.processes[press], name=press)
    # Build a fresh 3-process graph
    g3 = GraphBuilder()
    g3.add_process(make_ore_smelter(), name="smelter2")
    g3.add_process(make_widget_press(), name="press2")
    g3.add_process(make_widget_packager(), name="packager2")
    # manually connect smelter2 -> press2 via iron, press2 -> packager2 via widget
    g3._connect_process_to_process("smelter2", "press2", kind="iron")
    g3._connect_process_to_process("press2", "packager2", kind="widget")

    result = g3.build_batch_matrix()
    matrix = result["matrix"]
    processes = result["processes"]
    pools = result["pools"]

    # find iron pool row and packager2 column
    iron_pool_name = next(p for p in pools if g3.pools[p]["kind"] == "iron")
    iron_row = pools.index(iron_pool_name)
    packager2_col = processes.index("packager2")
    assert matrix[iron_row][packager2_col] == 0


def test_build_batch_matrix_shape():
    g, _, _ = two_process_graph()
    result = g.build_batch_matrix()
    matrix = np.array(result["matrix"])
    assert matrix.shape == (len(result["pools"]), len(result["processes"]))


def test_build_batch_matrix_keys():
    g, _, _ = two_process_graph()
    result = g.build_batch_matrix()
    assert "matrix" in result
    assert "processes" in result
    assert "pools" in result


# ---------------------------------------------------------------------------
# process_depths / output_depths
# ---------------------------------------------------------------------------


def test_process_depths_terminal_process_is_zero():
    # In a two-process chain, press produces the final open_output (widget)
    g, smelter, press = two_process_graph()
    depths = g.process_depths()
    assert depths[press] == 0


def test_process_depths_upstream_process_is_deeper():
    # smelter feeds into press, so smelter is deeper
    g, smelter, press = two_process_graph()
    depths = g.process_depths()
    assert depths[smelter] > depths[press]


def test_process_depths_all_processes_present():
    g, smelter, press = two_process_graph()
    depths = g.process_depths()
    assert smelter in depths
    assert press in depths


def test_output_depths_returns_dict():
    g, _, _ = two_process_graph()
    depths = g.output_depths()
    assert isinstance(depths, dict)


def test_output_depths_keys_are_process_descriptions():
    g, smelter, press = two_process_graph()
    depths = g.output_depths()
    # process descriptions for our two processes
    expected_descs = {g.processes[p].describe() for p in [smelter, press]}
    assert set(depths.keys()) == expected_descs


# ---------------------------------------------------------------------------
# build_matrix (continuous / rate-based) — analogous to build_batch_matrix
# ---------------------------------------------------------------------------


def test_build_matrix_producer_is_positive():
    g, smelter, _ = two_process_graph_timed()
    result = g.build_matrix()
    matrix = result["matrix"]
    processes = result["processes"]
    smelter_col = processes.index(smelter)
    iron_row = [
        i for i, p in enumerate(result["pools"]) if g.pools[p]["kind"] == "iron"
    ][0]
    assert matrix[iron_row][smelter_col] > 0


def test_build_matrix_consumer_is_negative():
    g, _, press = two_process_graph_timed()
    result = g.build_matrix()
    matrix = result["matrix"]
    processes = result["processes"]
    press_col = processes.index(press)
    iron_row = [
        i for i, p in enumerate(result["pools"]) if g.pools[p]["kind"] == "iron"
    ][0]
    assert matrix[iron_row][press_col] < 0


def test_build_matrix_correct_values():
    # smelter: 2 iron / 2.0 s  → transfer_rate[iron] = +1.0
    # press:   2 iron / 1.0 s  → transfer_rate[iron] = -2.0
    g, smelter, press = two_process_graph_timed()
    result = g.build_matrix()
    matrix = result["matrix"]
    processes = result["processes"]
    pools = result["pools"]
    smelter_col = processes.index(smelter)
    press_col = processes.index(press)
    iron_pool_name = next(p for p in pools if g.pools[p]["kind"] == "iron")
    iron_row = pools.index(iron_pool_name)
    assert matrix[iron_row][smelter_col] == pytest.approx(1.0)
    assert matrix[iron_row][press_col] == pytest.approx(-2.0)


def test_build_matrix_differs_from_batch_when_durations_differ():
    # With duration=2 on smelter, rate is half of raw transfer —
    # confirms build_matrix uses transfer_rate, not transfer
    g, smelter, press = two_process_graph_timed()
    batch = g.build_batch_matrix()
    cont = g.build_matrix()
    processes = batch["processes"]
    smelter_col = processes.index(smelter)
    iron_row = 0  # only one pool
    batch_val = batch["matrix"][iron_row][smelter_col]
    cont_val = cont["matrix"][iron_row][smelter_col]
    assert batch_val != pytest.approx(cont_val)


def test_build_matrix_unrelated_process_is_zero():
    g3 = GraphBuilder()
    g3.add_process(make_ore_smelter_timed(), name="smelter2")
    g3.add_process(make_widget_press_timed(), name="press2")
    g3.add_process(make_widget_packager_timed(), name="packager2")
    g3._connect_process_to_process("smelter2", "press2", kind="iron")
    g3._connect_process_to_process("press2", "packager2", kind="widget")

    result = g3.build_matrix()
    matrix = result["matrix"]
    processes = result["processes"]
    pools = result["pools"]

    iron_pool_name = next(p for p in pools if g3.pools[p]["kind"] == "iron")
    iron_row = pools.index(iron_pool_name)
    packager2_col = processes.index("packager2")
    assert matrix[iron_row][packager2_col] == 0


def test_build_matrix_shape():
    g, _, _ = two_process_graph_timed()
    result = g.build_matrix()
    matrix = np.array(result["matrix"])
    assert matrix.shape == (len(result["pools"]), len(result["processes"]))


def test_build_matrix_keys():
    g, _, _ = two_process_graph_timed()
    result = g.build_matrix()
    assert "matrix" in result
    assert "processes" in result
    assert "pools" in result
