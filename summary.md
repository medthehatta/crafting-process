# Codebase Summary

## Purpose

Solves "production tree" planning problems from video games: given a desired output,
find all the processes needed to produce it and determine how many times each process
must run (the "repeat counts") to minimize waste (resource mismatch between process
inputs and outputs).

## Stack

- Python 3.10+, uv for package management (`uv run pytest`, `uv add --editable .`)
- `formal_vector` (git dep): symbolic vector arithmetic — underpins `Ingredients`
- `scipy.optimize.milp`: mixed-integer linear programming solver
- `cytoolz`: functional utilities (`curry`, `unique`, `interleave`, etc.)
- `coolname`: random slug generation for internal node/pool names
- `fastapi`, `requests`, `pyyaml` in deps but no obvious usage in source — likely
  leftover or used by client code outside the repo

## Module Map

```
process.py        Core data model (Ingredients, Process, describe_process)
library.py        DSL parsing + ProcessLibrary (storage/search) + Predicates
graph.py          GraphBuilder: assembles process graphs, builds MILP matrices
solver.py         MILP solving (scipy wrapper), iterative tightening
orchestration.py  High-level: auto-build graphs from a desired output, analyze, display
augment.py        Augments (process transformations) + AugmentedProcess wrapper
utils.py          only(), re-exports curry
tests/            pytest test suite (function style, no classes)
```

`ops.py` has been deleted — it was a deprecated API layer superseded by orchestration.py.

## Data Model

```
Ingredients (FormalVector subclass)
  symbolic vector of (resource_name -> quantity)
  supports arithmetic: addition, scalar multiplication, projection
  Ingredients.parse() normalizes horizontal whitespace before parsing,
  so "iron  ore" and "iron ore" are the same ingredient.

describe_process(output_names, process=None) -> str
  module-level function in process.py; shared by Process.describe()
  and ProcessLibrary.mkname() to avoid duplicated logic.

Process
  .outputs: Ingredients
  .inputs:  Ingredients
  .duration: float | None   (None = batch-only process)
  .process:  str | None     (process type name, metadata)
  .transfer  = outputs - inputs
  .transfer_rate = transfer / duration  (continuous mode; raises if no duration)
  .transfer_quantity(batch=False)  dispatches to rate or raw transfer

AugmentedProcess (augment.py)
  wraps a Process, applies a chain of Augments lazily via __getattr__
  NOTE: ProcessLibrary has a FIXME about not supporting AugmentedProcess
```

## Graph Model

`GraphBuilder` is both a graph and a builder (acknowledged misnomer in overview.txt).

- **processes**: `{name -> Process}`  (names are random coolname slugs)
- **pools**: `{name -> {kind, inputs: [process_name], outputs: [process_name]}}`
  Pool terminology is counter-intuitive: `inputs` = processes that *produce* into the
  pool; `outputs` = processes that *consume* from the pool.
- **open_inputs**: `[(process_name, kind)]` — unsatisfied inputs (raw materials needed)
- **open_outputs**: `[(process_name, kind)]` — unsatisfied outputs (end products)

Key operations:
- `add_process(process)` — registers process, populates open_inputs/open_outputs
- `output_into(other)` — connects self's open_outputs to other's matching open_inputs,
  returns new combined graph (does not mutate either operand)
- `unify(other)` — in-place union (no connections made)
- `union(left, right)` — classmethod, non-mutating version of unify
- `coalesce_pools(p1, p2)` — merges two pools of same kind into one
- `build_matrix()` — continuous mode matrix (uses transfer_rate)
- `build_batch_matrix()` — batch mode matrix (uses transfer quantities)

`build_matrix` and `build_batch_matrix` are nearly identical — a cleanup opportunity.

`find_pools_by_kind_and_process_name` and `find_pools_by_process_name_and_kind` are
duplicate methods — a cleanup opportunity.

## MILP Formulation

Matrix `M` is (pools × processes).  Each entry `M[pool][process]` is the signed
transfer quantity of `pool.kind` for that process (positive = produces into pool,
negative = consumes from pool, 0 = unrelated).

Constraint: `0 ≤ M @ x ≤ max_leak` with integer `x ≥ 1`, minimising `sum(x)`.

`best_milp_sequence` starts with max_leak=10000, yields the solution, then tightens
to `0.9 * max(current_leaks)` and repeats until the solution stops changing.  The
yielded tuple is `(next_max_leak, answer_dict)` — the leak value is the *next*
constraint, not the leak of the current solution.  The final answer typically has
zero actual leak.

Confirmed via tests: infeasible matrices (e.g. all-negative rows) yield empty sequence.

## Orchestration Flow

```
production_graphs(recipes, transfer)
  creates a "sink" process that consumes the desired output
  -> _production_graphs(recipes, consuming_graph)
       finds all producers for each open input kind
       enumerates input_combinations() — which subset of producers to use
       for each combo: unify into upstream_graph, output_into consuming_graph
       recurse until all inputs satisfied or in stop_kinds
       yields complete GraphBuilder objects

input_combinations(input_kinds, kind_providers, max_overlap)
  finds combinations of provider indices that collectively cover all input_kinds
  itertools-heavy; max_overlap controls how many providers per kind are considered

analyze_graph(graph)  ->  generator of result dicts
  requires graph to have a "_" sentinel process (sink node from production_graphs)
  finds batch MILP solutions, formats process counts, computes dangling transfers
  each yielded dict has: desired, total_processes, leak, transfer, inputs,
  sorted_process_counts

analyze_graphs(graphs, num_keep)  ->  interleaved generator across multiple graphs

printable_analysis(aly)  ->  formatted string
  renders the analysis generator for human reading
  consumes a generator — caller must not have already advanced it
```

## FormalVector / Ingredients Notes

- `FormalVector._registry` and `_norm_lookup` are **class-level** (shared across all
  instances and all tests in a session). Ingredient names are interned on first use.
- `_norm_name` lowercases and strips apostrophes — used for fuzzy lookup.
- `Ingredients.parse` overrides `FormalVector.parse` to collapse horizontal whitespace
  before parsing, ensuring consistent interning.
- If code calls `Ingredients.named("iron  ore")` directly (bypassing parse), it would
  create a separate registry entry from `"iron ore"`. All DSL-path creation goes
  through `Ingredients.parse`, so this is safe in practice.
- `Ingredients[key]` returns 0 (not KeyError) for absent components — safe to index.

## DSL Quick Reference

```
# Single-line, inline inputs:
output1 + 2 output2 = 10 single input

# Two-line (header + inputs):
some output | process_name: duration=1
2 some input + 3 another input

# Inline inputs with process attribute:
another output | different_process: = another input + 6 input3

# Minimal (no process name, no attributes):
foo = 2 bar

# Attribute parsing: key=value pairs after |
# Numeric values parsed as numbers, others kept as strings
# Extra | separators are cosmetic
widget | stamping: duration=4 | tier=2
```

## Remaining Cleanup Opportunities

- **`build_matrix` / `build_batch_matrix`**: Nearly identical — differ only in
  `transfer_rate` vs `transfer`. Could unify with a `batch=False` param.
- **`orchestration.py:_only`**: Duplicates `utils.only` — should import from utils.
- **`augment.py:increase_energy_pct`**: Hardcoded to `"kWe"` — FIXME in source.
- **`library.py:ProcessLibrary`**: FIXME comment about not supporting AugmentedProcess.
- **Continuous vs batch coexistence**: Known limitation — processes in a graph must
  all be one mode. Noted in overview.txt as a future goal.
- **`_parse_process_header` outputs string**: Has a minor trailing-space wart when
  the line ends with ` =`; fixed by `.strip()` on `product_raw`. Internal whitespace
  within the outputs string is handled downstream by `Ingredients.parse`.

## Test Suite Status

```
tests/test_utils.py         4 tests   — only(), iterable handling
tests/test_process.py      34 tests   — Ingredients (incl. whitespace), Process API
tests/test_library.py      51 tests   — DSL parsing, ProcessLibrary, ProcessPredicates
tests/test_solver.py       17 tests   — solve_milp, best_milp_sequence
tests/test_graph.py         0 tests   — TODO (next)
tests/test_augment.py       0 tests   — TODO
tests/test_orchestration.py 0 tests   — TODO (hardest; depends on graph)
```

Run all tests: `uv run pytest`

## Notes for test_graph.py

GraphBuilder state is easy to construct directly — no fixtures needed beyond
`GraphBuilder.from_process(p)`.  Key things to cover:

- `add_process` populates open_inputs/open_outputs correctly
- `output_into` connects matching kinds and removes them from open lists
- `unify` merges without connecting (open lists grow)
- `coalesce_pools` merges pools of same kind
- `build_batch_matrix` produces correct signed entries (positive for producers,
  negative for consumers) — this is the most important correctness test
- `process_depths` / `output_depths` — useful but secondary
- Pool "inputs"/"outputs" naming convention is inverted from intuition; tests
  should be explicit about which side is producer vs consumer

The `pool_aliases` dict is populated by `coalesce_pools` but it's unclear whether
anything reads it — worth investigating before writing tests for it.

## Notes for test_orchestration.py

The main public surface is `production_graphs` + `analyze_graph` + `printable_analysis`.
These are integration-level tests; a small ProcessLibrary fixture (3-4 processes in a
linear chain) is sufficient to exercise the full flow.

`input_combinations` is a pure function with no dependencies — good unit test target.

`analyze_graph` expects a graph with a `"_"` sentinel open_output (the sink process
injected by `production_graphs`) — this is easy to forget when constructing test graphs
manually.

`_only` in orchestration.py is a duplicate of `utils.only` — a cleanup to make before
or alongside adding tests.
