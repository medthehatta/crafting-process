# Development Reference

This file consolidates all development notes for `crafting-process`: technical
reference, ergonomics decisions, and the feature roadmap.

---

## Overview

This repository models **processes** — operations that consume inputs and produce
outputs. Processes are assembled into graphs, and the library solves for the
integer repeat-count of each process required to produce a desired output with
as little waste as possible (fewest processes, minimal mismatch between outputs
and inputs).

### Module narratives

**`solver.py`** — Solves the mixed-integer linear program `M x = b`, where each
component of `b` is the resource imbalance ("leak") at a pool. `best_milp_sequence`
runs the solver with progressively tighter leak bounds: early solutions are
wasteful but use low process counts; later solutions are better balanced but
require more processes.

**`process.py`** — The `Process` class: an operation with `inputs`, `outputs`,
optional `duration`, optional `process` type name, freeform `annotations`, and
an `applied_augments` list. Thin and mostly convenience methods; processes are
assembled into graphs by `graph.py`.

**`library.py`** — Parses the recipe DSL into `Process` objects and stores them
in a `ProcessLibrary` that can be searched by output kind, input kind, process
type, augment, or annotation. Also provides the `P` predicate namespace and
`Pred` wrapper for composable filtering.

**`graph.py`** — `GraphBuilder` represents both the graph structure and the
operations for joining graphs. Introduces *kind* (resource type on a graph edge)
and *pool* (a source/sink node for one kind, lying between processes). Pools are
inverted from the process perspective: `pool["inputs"]` are the processes that
produce *into* the pool, and `pool["outputs"]` are the processes that consume
*from* it. `build_matrix()` uses transfer rates (continuous mode);
`build_batch_matrix()` uses absolute counts (batch mode). Mixing modes in one
graph is a known limitation tracked in the roadmap.

**`orchestration.py`** — Builds production graphs when an output is requested.
Iteratively finds processes that produce desired outputs, then finds processes
that feed those processes' inputs, building multiple graphs (one per covering
combination of providers). Finds providers layer-by-layer rather than
resource-by-resource to avoid exponential blowup from multi-output processes.
`plan()` is the high-level entry point; `production_graphs` and `analyze_graph`
are the lower-level building blocks.

**`augment.py`** — `Augments` factory methods for common `Process -> Process`
transforms (`mul_speed`, `mul_outputs`, `add_input_rate`, etc.). Augment
functions are registered with the library by name and applied via `@name` syntax
in the DSL, producing new named library entries alongside the originals.

**`utils.py`** — `only(seq)`: asserts a sequence has exactly one element and
returns it.

**`__init__.py`** — Public API surface; re-exports all primary symbols so
consumers can import directly from `crafting_process`.

`ops.py` was deleted — it was an earlier attempt at an API layer, superseded by
`orchestration.py`.

---

## Stack

- Python 3.10+, **uv** for package management
- `formal_vector` (git dep): symbolic vector arithmetic — underpins `Ingredients`
- `scipy.optimize.milp`: mixed-integer linear programming solver
- `cytoolz`: functional utilities (`curry`, `unique`, `interleave`, etc.)
- `coolname`: random slug generation for internal node/pool names
- `fastapi`, `requests`, `pyyaml` in deps but unused in source — likely client-side

## Dev Workflow

```bash
uv run pytest                    # run all tests
uv run pytest path/to/test.py -v # single file, verbose
uv add --dev <pkg>               # add dev dependency (never uv pip ...)
uv add --editable .              # install this package editable (needed once)
```

## Module Map

```
__init__.py       Public API surface — re-exports all primary symbols
process.py        Ingredients (FormalVector), Process, describe_process()
library.py        DSL parsing, ProcessLibrary, ProcessPredicates, Pred, P
graph.py          GraphBuilder — process graphs + MILP matrix building
solver.py         solve_milp(), best_milp_sequence() — scipy MILP wrapper
orchestration.py  plan(), production_graphs(), analyze_graph(), PlanResult, ProcessCount
augment.py        Augments — Process -> Process transform factories
utils.py          only(), curry re-export
tests/            pytest suite — function style, no test classes
```

`ops.py` was deleted — deprecated API layer superseded by `orchestration.py`.

Demo scripts at repo root: `check_samples.py` (continuous/rate-based, Factorio-style,
uses `sample_recipes.txt`), `check_samples_v2.py` (same but uses the new ergonomic API),
and `check_batch.py` (batch, WoW-style, uses `batch_recipes.txt`).

---

## Data Model

### Ingredients

`Ingredients` is a `FormalVector` subclass: a symbolic vector of
`(resource_name → quantity)` supporting arithmetic and scalar multiplication.

- `Ingredients.parse("3 iron + 2 copper")` — always use this; normalises
  horizontal whitespace so `"iron  ore"` and `"iron ore"` intern identically.
- `Ingredients[key]` returns `0` (not `KeyError`) for absent components.
- `_registry` and `_norm_lookup` are **class-level** (shared across all tests in
  a session). Names are interned on first use. Always go through `parse`, never
  `Ingredients.named(...)` directly.
- `_norm_name` lowercases and strips apostrophes — used for fuzzy lookup.

### Process

```
Process
  .outputs:           Ingredients
  .inputs:            Ingredients
  .duration:          float | None        (None = batch-only)
  .process:           str | None          (process type name — metadata, used by skip_processes)
  .annotations       dict[str, int|float|str]  (freeform metadata; empty dict by default)
  .applied_augments  list[str]           (augment names applied in order; [] for originals)
  .transfer        = outputs - inputs
  .transfer_rate   = transfer / duration  (raises if no duration)
  .transfer_quantity(batch=False) dispatches to rate or raw transfer

Process.from_transfer(transfer, **kwargs)
  splits a signed-transfer Ingredients into outputs (positive) and inputs (negative)

describe_process(output_names, process=None) -> str
  module-level in process.py; shared by Process.describe() and ProcessLibrary.mkname()
```

`copy(**overrides)` accepts any field as a keyword override. Always returns a new
object — never mutates the original. `annotations` is shallow-merged (`{**self.annotations,
**overrides.get("annotations", {})}`). Use `copy(applied_augments=...)` after calling an
augment fn to stamp names onto the result (augment fns themselves don't know their names).

### GraphBuilder

`GraphBuilder` is both a graph container and the builder that assembles it.
Process names are random coolname slugs — never rely on them; identify processes
by their `describe()` string or by inspecting `outputs`/`inputs` directly.

```
.processes   {slug -> Process}
.pools       {slug -> {kind, inputs: [slug], outputs: [slug]}}
.pool_aliases {old_slug -> merged_slug}   — populated by coalesce_pools
.open_inputs  [(slug, kind)]  — unsatisfied inputs (raw materials)
.open_outputs [(slug, kind)]  — unsatisfied outputs (end products or "_" sentinel)
```

**Pool naming is inverted from process perspective** (critical gotcha):
- `pool["inputs"]`  = process slugs that **produce into** the pool (sources)
- `pool["outputs"]` = process slugs that **consume from** the pool (sinks)

Key operations:
| Method | Mutating? | Effect |
|---|---|---|
| `add_process(p, name=None)` | yes | registers process, extends open lists |
| `from_process(p, name=None)` | — | classmethod; creates single-process graph |
| `output_into(other)` | **no** | returns new graph with matching kinds connected |
| `unify(other)` | **yes** | merges processes+pools+open lists, no connections |
| `union(left, right)` | — | classmethod non-mutating version of unify |
| `coalesce_pools(p1, p2)` | yes | merges two same-kind pools; records aliases |
| `build_matrix()` | — | continuous mode (uses `transfer_rate`) |
| `build_batch_matrix()` | — | batch mode (uses `transfer`) |

`build_matrix` and `build_batch_matrix` are nearly identical — a cleanup
opportunity (unify with `batch=False` param).

`find_pools_by_kind_and_process_name` and `find_pools_by_process_name_and_kind`
are duplicate methods — a cleanup opportunity.

`pool_aliases` is populated by `coalesce_pools` but nothing in the codebase
currently reads it.

---

## DSL Quick Reference

```
# Two-line (header + inputs):
some output | process name duration=1
2 some input + 3 another input

# Process names may contain spaces — no underscores required.
# "smelt iron" and "smelt_iron" are different names; pick one convention per file.

# Inline inputs (= on header line):
another output | different process = another input + 6 input3

# Multiple outputs:
2 iron + 1 slag | smelt = 3 ore

# Minimal (no process name, no attributes):
foo = 2 bar

# Attribute parsing: key=value pairs after |; numeric values parsed as numbers
widget | stamping duration=4 | tier=2

# Freeform annotations: [key=val | key2=val2] bracket block, after initializer params
# Values: int/float auto-detected via JSON; strings as fallback; bare true/false stay as str
2 iron | smelt duration=2 [tier=2 | energy=150]
1 widget | assemble [assembler=mk2 | tier=2] = 2 iron + 1 copper
```

**Parsing order gotcha**: the `[...]` annotation block is extracted from the header
string *before* the outer `|` split, because `|` inside brackets would otherwise be
consumed as a segment separator. Inline `@` tokens are stripped from `attributes_raw`
*after* the `|` split but *before* the process-name prefix is identified, so they
don't bleed into the process name value.

**Process name detection**: the process name is the leading text in the attribute
section (after `|`) that precedes the first `key=` pair. No special delimiter is
required — `| iron smelting duration=3` and `| iron smelting` are both valid.
A colon may appear freely within a process name (e.g. `| smelting: high temp`).

`ProcessPredicates.annotation_matches(key, pred)` — filters library by annotation value;
`pred` is any callable `value -> bool`. Composes with `and_`/`or_`/`not_` as usual.

For ergonomic predicate use, prefer the `P` namespace and `Pred` wrapper (see
Library Management below).

### Augmentation DSL

Augments are `Process -> Process` callables registered with `lib.register_augment(name, fn)`.
`augment.py` provides `Augments` factory methods (`mul_speed`, `mul_outputs`, `add_input`,
`add_input_rate`, `add_output_rate`, `mul_inputs`, `mul_duration`, `increase_energy_pct(kind, pct)`).
`mul_speed`/`mul_duration` pass through unchanged when `duration=None`.

```
# Block augments — one @-line = one augmented variant per recipe below it
@assembler_mk1
@assembler_mk2
@assembler_mk3 @speed_mod    ← multiple on one line are composed left-to-right

2 iron | smelt duration=4
3 ore

# New @-block after recipes resets; only @prod applies to press
@prod

1 widget | press duration=2
2 iron

# Inline @-augment on a recipe overrides the current block for that recipe only
1 gear | mill @assembler_mk2 duration=3
4 iron
```

Augmented entry name: `"<base_name> @aug1 @aug2"` (application order, space-delimited).
Original (un-augmented) recipe is always added alongside augmented variants.

`lib.with_augment_filter(skip_augments=None, only_augments=None)` — returns a filtered
library view; thread into `production_graphs` via its `skip_augments`/`only_augments` params.

`only_augments` uses **subset semantics**: a process is kept when
`applied_augments ⊆ only_augments`. This means originals (`applied_augments=[]`) always
pass through. `only_augments=[]` gives originals only; `only_augments=["mk3"]` gives
originals + mk3 variants.

`process_name` in the header sets `proc.process` — used by `skip_processes` in
`production_graphs`. `ProcessLibrary.mkname()` builds the library key from
`describe_process(output_names, process)`, disambiguating with a counter if needed.

---

## Library Management

### `ProcessLibrary` constructor

```python
ProcessLibrary(recipes=None, text=None, path=None, augments=None)
```

- `text` — parse DSL text immediately on construction
- `path` — read and parse a recipe file (accepts a plain string path)
- `augments` — dict of `{name: fn}` registered before text/path is parsed
- Raises `ValueError` if both `text` and `path` are given
- `add_from_text(text)` returns `self` for chaining

```python
# All equivalent:
lib = ProcessLibrary(path="recipes.txt", augments={"mk3": mk3_fn})
lib = ProcessLibrary().add_from_text(text_a).add_from_text(text_b)
```

### `lib.filtered(pred)` → `ProcessLibrary`

Returns a new library containing only recipes where `pred(process)` is true.
The augment registry is preserved. `pred` can be any callable or a `Pred`
built from the `P` namespace.

### `lib | other` → `ProcessLibrary`

Merges two libraries. On name collision the right-hand library wins. Both
augment registries are merged (right wins).

### Predicate system `P` and `Pred`

`P` provides named predicate factories. Each returns a `Pred`, which supports
`&`, `|`, `~` operators for composition

```python
from crafting_process import P

mk3_iron = lib.filtered(P.produces("iron") & P.has_augment("mk3"))
no_furnace = lib.filtered(~P.process_is("furnace"))
```

Available predicates:

| Factory | Matches |
|---|---|
| `P.produces(kind)` | process outputs include `kind` |
| `P.consumes(kind)` | process inputs include `kind` |
| `P.process_is(name)` | `proc.process == name` |
| `P.has_augment(name)` | `name` in `proc.applied_augments` |
| `P.annotation(key, pred)` | annotation value at `key` satisfies `pred` |

---

## MILP Formulation

Matrix `M` is `(pools × processes)`. Entry `M[pool][process]` is the signed
transfer quantity of `pool.kind` for that process run:
- positive = process produces into pool
- negative = process consumes from pool
- 0 = unrelated

Constraint: `0 ≤ M @ x ≤ max_leak`, integer `x ≥ 1`, minimise `sum(x)`.

`best_milp_sequence` starts at `max_leak=10000`, yields `(actual_leak, answer_dict)`
where `actual_leak = max(M @ x_current)`, then tightens to `0.9 * actual_leak` and
repeats until the solution stops changing. Final answer has `leak=0.0` for any
perfectly balanced integer solution. Infeasible matrices yield an empty sequence.

`solve_milp` upper-bounds each `x` at `max(10_000, max(|M|) × 10)` so that
recipes with large coefficients (e.g. currency conversion chains like
`10000 c | copper_to_gold = 1 g` combined with `1877900 c` AH prices) are never
artificially made infeasible. A fixed `max_repeat` cap caused silent infeasibility
for such chains — do not reintroduce it.

---

## Orchestration Flow

### `production_graphs(recipes, transfer, ...)`

Creates a **sink process**: `outputs={"_": 1}`, `inputs=transfer` (the desired
resource). The sink is the anchor of the graph. Then calls `_production_graphs`.

### `_production_graphs(recipes, consuming_graph, ..., visited=None)`

Recursive graph builder. For each open input kind not in `stop_kinds`:
1. Finds all producers via `recipes.producing(kind)`, filtering by `skip_processes`
   and the `visited` set of already-committed library names (loop detection).
2. **Deduplicates** `input_recipes` by library name before indexing — a process
   that satisfies multiple desired kinds would otherwise appear once per kind,
   generating degenerate combos that instantiate the same process twice.
3. Calls `input_combinations` to enumerate covering subsets.
4. For each combo: builds `upstream_graph`, calls `output_into(consuming_graph)`,
   passes `visited | {combo's library names}` to the recursive call.
5. When no producers remain (all consumed or blocked by `visited`), yields the
   current graph — possibly with unsatisfied open inputs (raw materials).

### `input_combinations(input_kinds, kind_providers, max_overlap=2)`

Pure function. Returns an iterable of index tuples, each tuple identifying a
sufficient set of providers to cover all `input_kinds`.

- `max_overlap` controls the max number of providers per kind considered in a
  single combo. Must be `≥ 1`; raises `ValueError` on `max_overlap=0`.
- Empty `input_kinds` → yields nothing (not an empty tuple).
- Range is `range(1, min(max_overlap, len(providing))+1)` — `i` iterates over
  provider-subset sizes.

### `plan(library, transfer, *, n=5, num_keep=4, **production_graphs_kwargs)` → `list[PlanResult]`

High-level convenience entry point. Accepts a string or `Ingredients` for
`transfer`. Runs `production_graphs`, solves MILP on each, ranks by
`(leak, total_processes)` ascending, and returns the top `n` results as a
concrete list. All `production_graphs` kwargs (`stop_kinds`, `skip_processes`,
`only_augments`, etc.) are forwarded.

```python
import crafting_process as cp
lib = cp.ProcessLibrary(path="recipes.txt", augments={"mk3": mk3_fn})
results = cp.plan(lib, "10 computer", n=3, only_augments=["mk3"])
print(cp.printable_analysis(results))
```

### `analyze_graph(graph, num_keep=4)` → generator of `PlanResult`

Requires a `"_"` sentinel open_output in the graph (injected by
`production_graphs`). Uses `_only` to find the sentinel process.

Each yielded `PlanResult` (frozen dataclass):

```
.desired               Ingredients — what was requested
.total_processes       int — sum of all repeat counts INCLUDING the sentinel (sink=1)
.leak                  float — worst-case pool imbalance (0.0 = perfectly balanced)
.transfer              Ingredients — scaled dangling transfers (open inputs/outputs)
.inputs                [(amount, kind)] — raw material requirements; "_" excluded
.process_counts        [ProcessCount] — sorted deepest-first by output_depths
.output_quantities     {kind: float} — actual output qty per desired kind (may exceed
                       requested when mul_outputs causes overproduction)
.process_augments      {slug: list[str]} — applied_augments per process slug
```

`ProcessCount` is a frozen dataclass with fields `count`, `description`, `slug`.

`printable_analysis(aly, show_augments=False)` accepts an iterable of `PlanResult`
(e.g. `list[PlanResult]` from `plan()`, or a generator from `analyze_graphs`).
Subtracts 1 from `total_processes` for display. With `show_augments=True`, appends
`@name` suffixes to process count lines. Always prints a `makes:` line showing
actual yield; annotates with `(want: N)` when yield differs from what was requested.

### `batch_milps(graph)` → list of `{leakage, counts}` dicts

Intermediate function; calls `build_batch_matrix` then `best_milp_sequence`.
Each `counts` entry: `(repeat_count, process.describe(), process_slug)`.

---

## Key Conventions

- **Tests**: `uv run pytest`, function style (no classes), one file per module.
  Helper factories at module level (e.g. `make_process()`). `pytest.approx` for
  floats. `pytest.raises(ValueError, match=...)` for errors.
- **Ingredient construction**: always via `Ingredients.parse(...)`, never manual.
- **Process names**: via `describe_process(output_names, process)` — shared by
  `Process.describe()` and `ProcessLibrary.mkname()`.
- **No dummy instances** just to call instance methods — extract a function instead.
- **Graph process identification in tests**: use `p.outputs["kind"] > 0` or
  `p.describe()` — never rely on random coolname slugs.
- **Type annotations**: use where they genuinely clarify (non-obvious return types,
  complex arguments like `Callable` or `Ingredients`). Omit for primitives and
  self-evident names. Do not annotate exhaustively.

## Remaining Cleanup

- **`build_matrix` / `build_batch_matrix`**: nearly identical — unify with `batch=False`
- **`find_pools_by_kind_and_process_name` / `find_pools_by_process_name_and_kind`**:
  identical methods — remove one
- **`pool_aliases`**: populated by `coalesce_pools` but never read — dead code
- **Continuous vs batch coexistence**: processes in a graph must all be one mode —
  known limitation, tracked in roadmap item 2

## Test Suite Status

```
test_utils.py            4  done
test_process.py         44  done
test_library.py        108  done
test_solver.py          17  done
test_graph.py           49  done  (build_matrix and build_batch_matrix both covered)
test_augment.py         18  done
test_orchestration.py  107  done
```

Total: 347 tests, all passing (`uv run pytest`).

---

## Ergonomics Improvements (completed)

These improvements were implemented on the `ergonomics` branch.

### Public API surface (`__init__.py`)

All primary symbols are now re-exported from the package root:

```python
from crafting_process import (
    Ingredients, Process, describe_process,
    ProcessLibrary, P, Pred, Augments,
    plan, production_graphs, analyze_graph, analyze_graphs,
    printable_analysis, PlanResult, ProcessCount,
)
```

### `plan()` entry point

`plan(library, transfer, *, n=5, num_keep=4, **kwargs) -> list[PlanResult]` — runs
the full pipeline (graph search → MILP → ranking) in one call. Returns a concrete
sorted list, not a generator. `transfer` accepts a string or `Ingredients`.

### `PlanResult` and `ProcessCount` dataclasses

`analyze_graph` now yields `PlanResult` frozen dataclasses instead of raw dicts.
`process_counts` is a list of `ProcessCount(count, description, slug)` objects.
Access via attributes (`result.leak`, `result.process_counts`) not dict keys.

### `ProcessLibrary` constructor

```python
ProcessLibrary(text=None, path=None, augments=None)
```

Augments are registered before text/path is parsed. Raises if both `text` and
`path` are given.

### `lib.filtered(pred)` and `lib | other`

`filtered(pred)` returns a new library keeping only recipes where `pred(process)`
is true; augment registry is preserved. `|` merges two libraries (right wins on
name collision).

### `P` and `Pred` predicate system

`Pred` wraps any callable and supports `&`, `|`, `~` for composition. `P` provides
named factories (`P.produces`, `P.consumes`, `P.process_is`, `P.has_augment`,
`P.annotation`). Both are exported from `__init__.py`.

---

## Feature Roadmap

### Item 0 — Freeform process annotations ✅ DONE

Adds `[key=val | key2=val2]` bracket syntax to the DSL header line. Values are
auto-detected as int/float/string. Annotations live on `Process.annotations` and
survive augmentation (inherited, overridable). `ProcessPredicates.annotation_matches`
enables library filtering by annotation value.

### Item 1 — Augmentation system ✅ DONE

Augments are `Process -> Process` callables registered with `lib.register_augment(name, fn)`.
Applied via `@name` blocks in the DSL (block augments apply to all following recipes;
inline `@name` on a recipe overrides the block for that recipe only). Composable
left-to-right when multiple augments appear on one line. Augmented variants are added
as new library entries alongside originals; `applied_augments` list records what was
applied. `lib.with_augment_filter(skip_augments, only_augments)` pre-filters before
graph search.

Key design decisions:
- Augment functions are Python callables registered by name — no fixed vocabulary
- Augmented entries are new library names, not replacements
- `only_augments` uses subset semantics (originals always pass through)
- Augments registered before `add_from_text` is called

### Item 2 — Mix batch and continuous processes in one graph

Currently all processes in a graph must be the same mode (batch or continuous).
Goal: model continuous processes grouped into batches, with batch processes
supplying the continuous groups. A mode field (not duration as proxy) would
distinguish them. The MILP would become a proper mixed-integer program.

Design notes (from Q&A):
- Use an explicit mode field rather than inferring from presence of `duration`
- Continuous processes balance rates within a "concurrent group"; batch processes
  run N integer times to supply the group's input volume
- Nesting is likely recursive (not just two levels)
- User requests either an output rate (+ duration) or an output quantity
- This is the most complex remaining item; deferred until after item 3

### Item 3 — Sort results by an arbitrary cost function

Goal: provide a callable `cost_fn(result: PlanResult) -> float` and return the
top-k graphs by cost. Primary use case: cheapest raw ingredients given a price
table.

Design notes (from Q&A):
- Cost operates on solved graphs (post-MILP), so all candidate graphs must be
  evaluated before ranking — brute-force for now, lazy top-k is aspirational
- `cost_fn` receives a `PlanResult` (already contains `inputs`, `process_counts`,
  `transfer`, `output_quantities`); also expose the raw `GraphBuilder` for
  consumers that need pool structure
- New entry point `best_k_plans(plans, cost_fn, k)` — does not change generator
  semantics of `production_graphs` or `analyze_graphs`

### Item 4 — Frontend integration review

The `crafting_frontend` web app wraps this library. Re-evaluate its integration
surface once items 2 and 3 are settled, since both affect the result shape.
Deferred until then.
