import numpy as np
from scipy.optimize import milp
from scipy.optimize import LinearConstraint
from scipy.optimize import Bounds


def solve_milp(dense, keys, max_leak=0):
    c = np.ones(len(keys))
    A = np.array(dense)
    b_u = max_leak * np.ones(len(dense))
    b_l = np.zeros(len(dense))

    constraints = LinearConstraint(A, b_l, b_u)
    integrality = np.ones_like(c)
    # Upper bound: large enough to never artificially constrain a solution.
    # Scaled from the matrix so recipes with large coefficients (e.g. currency
    # chains like 10000c = 1g alongside 1877900c prices) don't hit the ceiling.
    matrix_scale = max(abs(v) for row in dense for v in row) if dense else 1
    ub = max(10_000, int(matrix_scale) * 10) * np.ones_like(c)
    bounds = Bounds(lb=np.ones_like(c), ub=ub)

    res = milp(
        c=c,
        constraints=constraints,
        integrality=integrality,
        bounds=bounds,
    )

    if res.success:
        return {
            "answer": dict(zip(keys, map(int, res.x))),
            "result": res,
        }
    else:
        raise ValueError("No solution found")


def best_milp_sequence(matrix, keys):
    max_leak = 10000
    last = None

    try:
        soln = solve_milp(matrix, keys, max_leak=max_leak)
    except ValueError:
        return
    else:
        last = soln["result"].x
        leaks = matrix @ soln["result"].x
        actual_leak = max(leaks)
        max_leak = 0.9 * actual_leak
        yield (actual_leak, soln["answer"])

    while True:
        try:
            soln = solve_milp(matrix, keys, max_leak=max_leak)
        except ValueError:
            return
        else:
            if (soln["result"].x == last).all():
                return
            last = soln["result"].x
            leaks = matrix @ soln["result"].x
            actual_leak = max(leaks)
            max_leak = 0.9 * actual_leak
            yield (actual_leak, soln["answer"])
