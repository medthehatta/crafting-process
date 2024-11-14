import numpy as np
from scipy.optimize import milp
from scipy.optimize import LinearConstraint
from scipy.optimize import Bounds


def solve_milp(dense, keys, max_leak=0, max_repeat=180):
    c = np.ones(len(keys))
    A = np.array(dense)
    b_u = max_leak * np.ones(len(dense))
    b_l = np.zeros(len(dense))

    constraints = LinearConstraint(A, b_l, b_u)
    integrality = np.ones_like(c)
    bounds = Bounds(lb=np.ones_like(c), ub=max_repeat * np.ones_like(c))

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
    max_repeat = 500
    last = None

    try:
        soln = solve_milp(
            matrix, keys, max_leak=max_leak, max_repeat=max_repeat
        )
    except ValueError:
        return
    else:
        last = soln["result"].x
        leaks = matrix @ soln["result"].x
        max_leak = 0.9 * max(leaks)
        yield (max_leak, soln["answer"])

    while True:
        try:
            soln = solve_milp(
                matrix,
                keys,
                max_leak=max_leak,
                max_repeat=max_repeat,
            )
        except ValueError:
            return
        else:
            if (soln["result"].x == last).all():
                return
            last = soln["result"].x
            leaks = matrix @ soln["result"].x
            max_leak = 0.9 * max(leaks)
            yield (max_leak, soln["answer"])
