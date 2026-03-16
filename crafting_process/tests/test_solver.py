import pytest

from crafting_process.solver import solve_milp, best_milp_sequence


# ---------------------------------------------------------------------------
# Notation
# ---------------------------------------------------------------------------
# Matrices are (pools × processes).  Each entry is the signed transfer
# quantity of pool.kind per run of that process:
#   positive  = process produces into the pool
#   negative  = process consumes from the pool
#
# The constraint is  0 ≤ A @ x ≤ max_leak  with integer x ≥ 1,
# minimising sum(x).  A zero-leak solution means perfect balance.
#
# Hand-worked reference cases used throughout:
#
#   BALANCED_1TO1  [[1, -1]]             A:B = 1:1  →  A=1, B=1
#   RATIO_2TO3     [[2, -3]]             P1:P2 = 3:2  →  P1=3, P2=2
#   CHAIN          [[2,-3,0],[0,1,-1]]   two-pool chain  →  A=3, B=2, C=2
#   INFEASIBLE     [[-1, -1]]            both processes consume; always < 0


BALANCED_1TO1 = [[1, -1]]
RATIO_2TO3    = [[2, -3]]
CHAIN         = [[2, -3, 0], [0, 1, -1]]
INFEASIBLE    = [[-1, -1]]


# ---------------------------------------------------------------------------
# solve_milp
# ---------------------------------------------------------------------------

def test_solve_milp_balanced_ratio():
    result = solve_milp(BALANCED_1TO1, ["A", "B"], max_leak=0)
    assert result["answer"] == {"A": 1, "B": 1}


def test_solve_milp_unbalanced_ratio_zero_leak():
    result = solve_milp(RATIO_2TO3, ["P1", "P2"], max_leak=0)
    assert result["answer"] == {"P1": 3, "P2": 2}


def test_solve_milp_production_chain():
    result = solve_milp(CHAIN, ["A", "B", "C"], max_leak=0)
    assert result["answer"] == {"A": 3, "B": 2, "C": 2}


def test_solve_milp_answer_keys_match_input_keys():
    result = solve_milp(RATIO_2TO3, ["proc_x", "proc_y"], max_leak=0)
    assert set(result["answer"].keys()) == {"proc_x", "proc_y"}


def test_solve_milp_answer_values_are_integers():
    result = solve_milp(RATIO_2TO3, ["P1", "P2"], max_leak=0)
    assert all(isinstance(v, int) for v in result["answer"].values())


def test_solve_milp_nonzero_leak_allows_smaller_counts():
    # With max_leak=1, P1=2 P2=1 satisfies 2*2-3*1 = 1 ≤ 1 and has lower total
    result = solve_milp(RATIO_2TO3, ["P1", "P2"], max_leak=1)
    assert result["answer"] == {"P1": 2, "P2": 1}


def test_solve_milp_each_process_runs_at_least_once():
    result = solve_milp(RATIO_2TO3, ["P1", "P2"], max_leak=0)
    assert all(v >= 1 for v in result["answer"].values())


def test_solve_milp_respects_max_repeat():
    # Zero-leak solution requires P1=3 which exceeds max_repeat=2
    with pytest.raises(ValueError, match="No solution"):
        solve_milp(RATIO_2TO3, ["P1", "P2"], max_leak=0, max_repeat=2)


def test_solve_milp_raises_on_infeasible():
    with pytest.raises(ValueError, match="No solution"):
        solve_milp(INFEASIBLE, ["A", "B"], max_leak=0)


def test_solve_milp_raises_on_infeasible_even_with_high_leak():
    # INFEASIBLE makes A@x negative for all x≥1 regardless of max_leak
    with pytest.raises(ValueError, match="No solution"):
        solve_milp(INFEASIBLE, ["A", "B"], max_leak=10000)


# ---------------------------------------------------------------------------
# best_milp_sequence
# ---------------------------------------------------------------------------

def test_best_milp_sequence_yields_at_least_one_result():
    results = list(best_milp_sequence(RATIO_2TO3, ["P1", "P2"]))
    assert len(results) >= 1


def test_best_milp_sequence_terminates():
    # Collect the full sequence — must not loop forever
    results = list(best_milp_sequence(RATIO_2TO3, ["P1", "P2"]))
    assert results is not None


def test_best_milp_sequence_final_answer_is_zero_leak():
    results = list(best_milp_sequence(RATIO_2TO3, ["P1", "P2"]))
    (_, final_answer) = results[-1]
    assert final_answer == {"P1": 3, "P2": 2}


def test_best_milp_sequence_leak_is_non_increasing():
    results = list(best_milp_sequence(RATIO_2TO3, ["P1", "P2"]))
    leaks = [leak for (leak, _) in results]
    assert leaks == sorted(leaks, reverse=True)


def test_best_milp_sequence_all_results_are_tuples_of_leak_and_dict():
    for (leak, answer) in best_milp_sequence(RATIO_2TO3, ["P1", "P2"]):
        assert isinstance(leak, float)
        assert isinstance(answer, dict)


def test_best_milp_sequence_infeasible_yields_nothing():
    results = list(best_milp_sequence(INFEASIBLE, ["A", "B"]))
    assert results == []


def test_best_milp_sequence_balanced_yields_one_result():
    # 1:1 is already optimal on first solve; sequence has exactly one entry
    results = list(best_milp_sequence(BALANCED_1TO1, ["A", "B"]))
    assert len(results) == 1
    (_, answer) = results[0]
    assert answer == {"A": 1, "B": 1}
