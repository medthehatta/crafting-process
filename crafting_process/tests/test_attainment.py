import pytest

from crafting_process.library import ProcessLibrary
from crafting_process.attainment import attainable, library_kinds

# ---------------------------------------------------------------------------
# attainable() is the inverse of plan(): given a starting inventory, it
# reports the max quantity of each resource kind reachable via some integer
# combination of process runs, found by MILP maximization (not simulated
# repeated crafting).
# ---------------------------------------------------------------------------


def widget_lib():
    return ProcessLibrary(
        "batch",
        text="""
        1 widget | make
        2 iron
        """,
    )


def chain_lib():
    return ProcessLibrary(
        "batch",
        text="""
        1 bar | smelt
        2 ore

        1 buckle | craft
        3 bar
        """,
    )


def test_attainable_simple_gain():
    results = attainable(widget_lib(), "10 iron")
    by_kind = {r.kind: r for r in results}
    assert by_kind["widget"].quantity == pytest.approx(5)
    assert by_kind["widget"].starting == pytest.approx(0)


def test_attainable_process_counts_are_minimal():
    results = attainable(widget_lib(), "10 iron")
    by_kind = {r.kind: r for r in results}
    assert by_kind["widget"].process_counts == [(5, "widget via make")]


def test_attainable_starting_inventory_carries_through():
    lib = widget_lib()
    results = attainable(lib, "10 iron + 3 widget")
    by_kind = {r.kind: r for r in results}
    assert by_kind["widget"].starting == pytest.approx(3)
    assert by_kind["widget"].quantity == pytest.approx(8)


def test_attainable_no_gain_is_excluded():
    # No iron at all: widget can't be made beyond what's already on hand.
    results = attainable(widget_lib(), "0 iron")
    assert all(r.kind != "widget" for r in results)


def test_attainable_chain_uses_full_conversion():
    results = attainable(chain_lib(), "30 ore")
    by_kind = {r.kind: r for r in results}
    assert by_kind["bar"].quantity == pytest.approx(15)
    assert by_kind["buckle"].quantity == pytest.approx(5)


def test_attainable_chain_process_counts_for_intermediate():
    # Maximizing "bar" alone must not drag in the unrelated "craft" process.
    results = attainable(chain_lib(), "30 ore")
    by_kind = {r.kind: r for r in results}
    assert by_kind["bar"].process_counts == [(15, "bar via smelt")]


def test_attainable_chain_process_counts_for_final_product():
    results = attainable(chain_lib(), "30 ore")
    by_kind = {r.kind: r for r in results}
    counts = dict(
        (desc, count) for (count, desc) in by_kind["buckle"].process_counts
    )
    assert counts["bar via smelt"] == 15
    assert counts["buckle via craft"] == 5


def test_attainable_targets_filter_restricts_report():
    results = attainable(chain_lib(), "30 ore", targets=["buckle"])
    assert [r.kind for r in results] == ["buckle"]


def test_attainable_unknown_target_is_silently_skipped():
    results = attainable(chain_lib(), "30 ore", targets=["nonexistent_kind"])
    assert results == []


def test_attainable_skip_processes_removes_a_recipe():
    results = attainable(chain_lib(), "30 ore", skip_processes=["craft"])
    assert all(r.kind != "buckle" for r in results)
    by_kind = {r.kind: r for r in results}
    assert by_kind["bar"].quantity == pytest.approx(15)


def test_attainable_unbounded_source_settles_at_a_large_finite_cap():
    # A process with no inputs is an unbounded source; rather than reporting
    # infinity, it settles at solve_milp's large-but-finite bound convention.
    lib = ProcessLibrary("batch", text="1 gold | mint\n")
    results = attainable(lib, "0 gold")
    by_kind = {r.kind: r for r in results}
    assert by_kind["gold"].quantity >= 10_000
    assert by_kind["gold"].process_counts == [(int(by_kind["gold"].quantity), "gold via mint")]


def test_attainable_results_sorted_descending_by_quantity():
    results = attainable(chain_lib(), "30 ore")
    quantities = [r.quantity for r in results]
    assert quantities == sorted(quantities, reverse=True)


def test_attainable_empty_library_returns_empty():
    lib = ProcessLibrary("batch", recipes={})
    assert attainable(lib, "10 iron") == []


def test_library_kinds_collects_inputs_and_outputs():
    kinds = library_kinds(chain_lib())
    assert set(kinds) == {"ore", "bar", "buckle"}
