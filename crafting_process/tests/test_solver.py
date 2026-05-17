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
# The constraint is  -max_leak ≤ A @ x ≤ max_leak  with integer x ≥ 1,
# minimising sum(x).  Leak is max(|A @ x|); a zero-leak solution means
# perfect balance.  Negative net flow means downstream processes are waiting
# for upstream output; it is physically valid, just suboptimal.
#
# Hand-worked reference cases used throughout:
#
#   BALANCED_1TO1      [[1, -1]]           A:B = 1:1  →  A=1, B=1
#   RATIO_2TO3         [[2, -3]]           P1:P2 = 3:2  →  P1=3, P2=2
#   CHAIN              [[2,-3,0],[0,1,-1]] two-pool chain  →  A=3, B=2, C=2
#   INFEASIBLE         [[-1, -1]]          both consume; feasible with max_leak>0
#   NEGATIVE_DOMINANT  [[2,-1],[-4,1]]     all solutions negative-dominant leak


BALANCED_1TO1 = [[1, -1]]
RATIO_2TO3 = [[2, -3]]
CHAIN = [[2, -3, 0], [0, 1, -1]]
INFEASIBLE = [[-1, -1]]
# NEGATIVE_DOMINANT: two pools, all reachable solutions have a negative-dominant
# leak (max-abs leak is always negative).  Hand-worked sequence:
#   x=(1,1): leaks=[1,-3], max(|.|)=-3   x=(1,2): leaks=[0,-2], max(|.|)=-2
#   x=(1,3): leaks=[-1,-1], max(|.|)=-1  then infeasible → 3 results total.
# This matrix specifically detects if the while-loop uses max(leaks) instead of
# max(leaks, key=abs) (which reports 0.0 for x=(1,2)) or omits abs() on max_leak
# (which makes max_leak negative, causing premature termination after 2 results).
NEGATIVE_DOMINANT = [[2, -1], [-4, 1]]


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
    # With max_leak=1, P1=1 P2=1 satisfies |2*1-3*1| = 1 ≤ 1 and has lower total
    result = solve_milp(RATIO_2TO3, ["P1", "P2"], max_leak=1)
    assert result["answer"] == {"P1": 1, "P2": 1}


def test_solve_milp_each_process_runs_at_least_once():
    result = solve_milp(RATIO_2TO3, ["P1", "P2"], max_leak=0)
    assert all(v >= 1 for v in result["answer"].values())


def test_solve_milp_raises_on_infeasible():
    with pytest.raises(ValueError, match="No solution"):
        solve_milp(INFEASIBLE, ["A", "B"], max_leak=0)


def test_solve_milp_infeasible_is_feasible_with_nonzero_leak():
    # INFEASIBLE: A@x = -A-B = -2 for x=(1,1); satisfies -10000 ≤ -2 ≤ 10000
    result = solve_milp(INFEASIBLE, ["A", "B"], max_leak=10000)
    assert result["answer"] == {"A": 1, "B": 1}


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
    final_leak, final_answer = results[-1]
    assert final_answer == {"P1": 3, "P2": 2}
    assert final_leak == pytest.approx(0.0)


def test_best_milp_sequence_leak_is_non_increasing():
    results = list(best_milp_sequence(RATIO_2TO3, ["P1", "P2"]))
    abs_leaks = [abs(leak) for (leak, _) in results]
    assert abs_leaks == sorted(abs_leaks, reverse=True)


def test_best_milp_sequence_all_results_are_tuples_of_leak_and_dict():
    for leak, answer in best_milp_sequence(RATIO_2TO3, ["P1", "P2"]):
        assert isinstance(leak, float)
        assert isinstance(answer, dict)


def test_best_milp_sequence_infeasible_yields_one_then_stops():
    # First solve: A=B=1, net=-2, leak=-2 (signed). Tightening to abs=1.8 then
    # makes it infeasible (net=-2 < -1.8), so the sequence stops after one.
    results = list(best_milp_sequence(INFEASIBLE, ["A", "B"]))
    assert len(results) == 1
    leak, answer = results[0]
    assert answer == {"A": 1, "B": 1}
    assert leak == pytest.approx(-2.0)


def test_best_milp_sequence_balanced_yields_one_result():
    # 1:1 is already optimal on first solve; sequence has exactly one entry
    results = list(best_milp_sequence(BALANCED_1TO1, ["A", "B"]))
    assert len(results) == 1
    leak, answer = results[0]
    assert answer == {"A": 1, "B": 1}
    assert leak == pytest.approx(0.0)


def test_best_milp_sequence_leak_matches_solution():
    import numpy as np

    # The yielded leak must equal the actual max pool imbalance for that solution,
    # not some derived constraint value
    matrix = np.array(RATIO_2TO3, dtype=float)
    for leak, answer in best_milp_sequence(RATIO_2TO3, ["P1", "P2"]):
        x = np.array([answer["P1"], answer["P2"]])
        assert leak == pytest.approx(float(max(matrix @ x, key=abs)))


# ---------------------------------------------------------------------------
# Regression tests: correct abs() handling in the while loop
#
# NEGATIVE_DOMINANT produces a sequence where every intermediate solution has a
# negative-dominant leak.  Two past bugs only manifested inside the while loop:
#   Bug A — max(leaks) instead of max(leaks, key=abs): x=(1,2) has leaks [0,-2]
#            so max(leaks)=0 → reported leak is 0.0 instead of -2.0.
#   Bug B — 0.9 * actual_leak without abs: when actual_leak=-2, max_leak becomes
#            -1.8, making b_l > b_u in the next solve → premature termination
#            after 2 results instead of the correct 3.
# ---------------------------------------------------------------------------


def test_best_milp_sequence_negative_dominant_correct_leak_value():
    # Catch Bug A: x=(1,2) must report leak=-2.0, not 0.0
    results = list(best_milp_sequence(NEGATIVE_DOMINANT, ["P1", "P2"]))
    leaks_by_answer = {(a["P1"], a["P2"]): leak for leak, a in results}
    assert leaks_by_answer[(1, 2)] == pytest.approx(-2.0)


def test_best_milp_sequence_negative_dominant_finds_all_solutions():
    # Catch Bug B: premature termination yields 2 results; correct code yields 3
    results = list(best_milp_sequence(NEGATIVE_DOMINANT, ["P1", "P2"]))
    assert len(results) == 3
    answers = [a for _, a in results]
    assert {"P1": 1, "P2": 1} in answers
    assert {"P1": 1, "P2": 2} in answers
    assert {"P1": 1, "P2": 3} in answers


def test_best_milp_sequence_no_duplicate_answers():
    # Any matrix: the same integer answer must never appear twice in a sequence
    for matrix, keys in [
        (RATIO_2TO3, ["P1", "P2"]),
        (NEGATIVE_DOMINANT, ["P1", "P2"]),
        (CHAIN, ["A", "B", "C"]),
    ]:
        answers = [a for _, a in best_milp_sequence(matrix, keys)]
        assert len(answers) == len({tuple(sorted(a.items())) for a in answers})
