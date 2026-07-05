"""Forward-chaining: given an inventory, find what quantities of each
resource kind are attainable via some integer combination of process runs.

This is the inverse of orchestration.py's plan(): instead of searching for a
tree of processes that hits an exact desired yield, it takes a fixed starting
inventory and asks, for each resource kind, "what's the most of this you
could end up with?" via a single MILP maximization rather than repeated
simulated crafting.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

from .process import Ingredients


@dataclass(frozen=True)
class AttainmentResult:
    kind: str
    quantity: float  # max final quantity attainable
    starting: float  # quantity already in the inventory
    process_counts: list  # [(count, description)], nonzero runs only


def library_kinds(library):
    """All resource kinds (inputs or outputs) appearing anywhere in the library."""
    kinds = set()
    for proc in library.recipes.values():
        kinds.update(proc.outputs.nonzero_components)
        kinds.update(proc.inputs.nonzero_components)
    return sorted(kinds)


def _exchange_matrix(library, kinds, names):
    procs = [library.recipes[n] for n in names]
    return np.array([[proc.exchange[k] for proc in procs] for k in kinds], dtype=float)


def attainable(library, inventory, targets=None, *, skip_processes=None):
    """Return AttainmentResults describing what's reachable from `inventory`.

    inventory can be a string ("10 iron + 5 copper") or an Ingredients.
    targets restricts the report to these kinds (default: every kind produced
    by some process in the library). skip_processes excludes processes by
    their `.process` name, same semantics as production_graphs.
    """
    inventory = (
        inventory if isinstance(inventory, Ingredients) else Ingredients.parse(inventory)
    )
    skip = set(skip_processes or [])
    names = [
        n for n, p in library.recipes.items() if p.process not in skip
    ]
    if not names:
        return []

    kinds = library_kinds(library)
    if not kinds:
        return []

    M = _exchange_matrix(library, kinds, names)
    b0 = np.array([inventory[k] for k in kinds], dtype=float)
    n = len(names)
    kind_index = {k: i for i, k in enumerate(kinds)}

    # Upper bound on process runs: scaled from the matrix/inventory so a
    # genuinely unbounded chain (e.g. a process with no inputs) settles at a
    # large-but-finite cap instead of failing, same tradeoff solve_milp makes.
    scale = max(1.0, float(np.max(np.abs(M))) if M.size else 1.0, float(np.max(np.abs(b0))) if b0.size else 1.0)
    ub = max(10_000, int(scale) * 10)
    bounds = Bounds(lb=np.zeros(n), ub=ub * np.ones(n))
    integrality = np.ones(n)
    # b0 + M @ x >= 0  <=>  M @ x >= -b0
    constraints = LinearConstraint(M, -b0, np.inf)

    target_kinds = (
        list(targets)
        if targets is not None
        else [k for k in kinds if any(library.recipes[n].outputs[k] > 0 for n in names)]
    )

    results = []
    for k in target_kinds:
        i = kind_index.get(k)
        if i is None:
            continue
        starting = float(b0[i])

        # Phase 1: maximize net production of the target kind.
        res = milp(c=-M[i], constraints=constraints, integrality=integrality, bounds=bounds)

        if not res.success:
            continue

        net = float(M[i] @ res.x)
        quantity = starting + net
        if quantity <= starting + 1e-9:
            continue

        # Phase 2: among solutions achieving that same max, minimize total
        # process runs — phase 1 alone leaves unrelated processes free to
        # take on arbitrary nonzero values since they don't affect its
        # objective.
        hits_max = LinearConstraint(M[i : i + 1], net - 1e-6, np.inf)
        res2 = milp(
            c=np.ones(n),
            constraints=[constraints, hits_max],
            integrality=integrality,
            bounds=bounds,
        )
        counts = res2.x if res2.success else res.x

        process_counts = [
            (round(count), library.recipes[names[j]].describe())
            for j, count in enumerate(counts)
            if count > 1e-6
        ]
        results.append(
            AttainmentResult(kind=k, quantity=quantity, starting=starting, process_counts=process_counts)
        )

    results.sort(key=lambda r: (-r.quantity, r.kind))
    return results
