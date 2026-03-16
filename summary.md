# Codebase Summary

## Purpose

Solves "production tree" planning problems from video games: given a desired output,
find all the processes needed to produce it and determine how many times each process
must run (the "repeat counts") to minimize waste (resource mismatch between process
inputs and outputs).

## Stack

- Python 3.10+, uv for package management
- `formal_vector` (git dep): symbolic vector arithmetic — underpins `Ingredients`
- `scipy.optimize.milp`: mixed-integer linear programming solver
- `cytoolz`: functional utilities (`curry`, `unique`, `interleave`, etc.)
- `coolname`: random slug generation for internal node/pool names
- `fastapi`, `requests`, `pyyaml` in deps but no obvious usage in source — likely
  leftover or used by client code outside the repo

## Module Map

```
process.py        Core data model
library.py        DSL parsing + ProcessLibrary (storage/search) + Predicates
graph.py          GraphBuilder: assembles process graphs, builds MILP matrices
solver.py         MILP solving (scipy wrapper), iterative tightening
orchestration.py  High-level: auto-build graphs from a desired output, analyze, display
augment.py        Augments (process transformations) + AugmentedProcess wrapper
ops.py            DEPRECATED — CraftingContext, now unused
utils.py          only(), re-exports curry
```

## Data Model

```
Ingredients (FormalVector subclass)
  symbolic vector of (resource_name -> quantity)
  supports arithmetic: addition, scalar multiplication, projection

Process
  .outputs: Ingredients
  .inputs:  Ingredients
  .duration: float | None   (None = batch-only process)
  .process:  str | None     (process type name, metadata)
  .transfer  = outputs - inputs
  .transfer_rate = transfer / duration  (continuous mode)
  .transfer_quantity(batch=False)  dispatches to rate or raw transfer

AugmentedProcess (augment.py)
  wraps a Process, applies a chain of Augments lazily via __getattr__
```

## Graph Model

`GraphBuilder` is both a graph and a builder (acknowledged misnomer in overview.txt).

- **processes**: `{name -> Process}`  (names are random coolname slugs)
- **pools**: `{name -> {kind, inputs: [process_name], outputs: [process_name]}}`
  A pool is a resource buffer between processes.  "inputs" to the pool = processes
  that _produce_ this resource; "outputs" from the pool = processes that _consume_ it.
- **open_inputs**: `[(process_name, kind)]` — unsatisfied inputs (raw materials)
- **open_outputs**: `[(process_name, kind)]` — unsatisfied outputs (end products)

Key operations:
- `add_process(process)` — registers process, populates open_inputs/open_outputs
- `output_into(other)` — connects self's open_outputs to other's matching open_inputs
- `unify(other)` — in-place union (no connections made)
- `coalesce_pools(p1, p2)` — merges two pools of same kind into one
- `build_matrix()` — continuous mode matrix (uses transfer_rate)
- `build_batch_matrix()` — batch mode matrix (uses transfer)

## MILP Formulation

Matrix `M` is (pools × processes).  Each entry `M[pool][process]` is the signed
transfer quantity of `pool.kind` for that process (positive = output, negative = input,
0 = unrelated).

Solve `M x = b` where `x` is integer repeat-counts (≥1) and `b` is the "leak" vector
(resource imbalance, ideally zero).

`best_milp_sequence` iteratively tightens `max_leak` starting from 10000, yielding
progressively better solutions until no improvement.

## Orchestration Flow

```
production_graphs(recipes, transfer)
  creates a "sink" process that consumes the desired output
  -> _production_graphs(recipes, consuming_graph)
       finds all producers for each open input
       enumerates input_combinations (which producers to use)
       for each combo: unify into upstream_graph, output_into consuming_graph
       recurse on the new graph until all inputs are satisfied or are stop_kinds
       yields complete GraphBuilder objects

analyze_graph(graph)  ->  generator of result dicts
  finds batch MILP solutions, formats process counts, computes dangling transfers

printable_analysis(aly)  ->  formatted string
  renders the analysis generator for human reading
```

## Known Bugs

### `graph.py:18` — `__repr__` pluralization inverted
```python
# BUG: condition is backwards
node_s = "node" if len(self.processes) > 1 else "nodes"
# Should be:
node_s = "nodes" if len(self.processes) > 1 else "node"
```

### `graph.py:33+36` — `union()` double-assigns `processes`
```python
new.processes = {**left.processes, **right.processes}  # line 33
new.pools = ...
new.pool_aliases = ...
new.processes = {**left.processes, **right.processes}  # line 36, dead duplicate
```

### `graph.py:44` — `unify()` updates pool_aliases with processes dict
```python
# BUG: should be other.pool_aliases, not other.processes
self.pool_aliases.update(other.processes)
```

### `library.py:80` — regex character class typo `0-0` should be `0-9`
```python
r"([A-Za-z_][A-Za-z_0-0]*)="   # 0-0 matches only '0'
# Should be:
r"([A-Za-z_][A-Za-z_0-9]*)="
```

### `graph.py:315` vs `graph.py:322` — duplicate methods
`find_pools_by_kind_and_process_name` and `find_pools_by_process_name_and_kind`
are identical in implementation.

### `orchestration.py:14-21` — `_only` duplicates `utils.only`
Should import and use `only` from utils.

### `orchestration.py:25` — `analyze_graphs` ignores `num_keep` param
```python
def analyze_graphs(graphs, num_keep=4):
    return interleave(analyze_graph(g) for g in graphs)
    # num_keep is never passed to analyze_graph
```

### `solver.py` — potential infinite loop / zero-division in `best_milp_sequence`
If `max(leaks)` is 0 on first solution, `0.9 * 0 = 0` and subsequent solves with
`max_leak=0` may keep returning the same solution (same-solution guard should catch
it but worth verifying).

## Areas for Cleanup

- **ops.py**: Can likely be deleted entirely. Confirm no external callers first.
- **`build_matrix` / `build_batch_matrix`**: Nearly identical — differ only in
  `transfer_rate` vs `transfer`. Could unify with a `batch=False` param.
- **Continuous vs batch coexistence**: Noted as a known limitation in overview.txt.
  Processes currently must all be one mode per graph.
- **`augment.py:increase_energy_pct`**: Hardcoded to `"kWe"` — FIXME in source.
- **`library.py:ProcessLibrary`**: FIXME comment about not supporting AugmentedProcess.
- **`graph.py:consolidate_processes`**: Raises NotImplementedError immediately but
  has dead code body. Should either be removed or implemented.
- **No test suite**: There are no tests at all. This is a significant gap.
- **`Process.describe()` and `ProcessLibrary.mkname()`**: Both implement the same
  name-construction logic (`" + ".join(output_names) + f" via {process_name}"`).
  Should deduplicate by having `mkname` call `process.describe()`.
