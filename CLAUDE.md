# CLAUDE.md

## Project

Production tree planner for video games. Given a desired output resource, builds
process graphs and solves for optimal integer repeat-counts via MILP.

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
process.py        Ingredients (FormalVector), Process, describe_process()
library.py        DSL parsing, ProcessLibrary, ProcessPredicates
graph.py          GraphBuilder — process graphs + MILP matrix building
solver.py         solve_milp(), best_milp_sequence() — scipy MILP wrapper
orchestration.py  production_graphs(), analyze_graph(), printable_analysis()
augment.py        Augments — Process -> Process transform factories
utils.py          only(), curry re-export
tests/            pytest suite — function style, no test classes
```

`ops.py` was deleted — deprecated API layer superseded by `orchestration.py`.

Demo scripts at repo root: `check_samples.py` (continuous/rate-based, Factorio-style,
uses `sample_recipes.txt`) and `check_batch.py` (batch, WoW-style, uses `batch_recipes.txt`).

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
  .annotations:       dict[str, int|float|str]  (freeform metadata; empty dict by default)
  .applied_augments:  list[str]           (augment names applied in order; [] for originals)
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

## DSL Quick Reference

```
# Two-line (header + inputs):
some output | process name: duration=1
2 some input + 3 another input

# Process names may contain spaces — no underscores required.
# "smelt iron" and "smelt_iron" are different names; pick one convention per file.

# Inline inputs (= on header line):
another output | different process: = another input + 6 input3

# Multiple outputs:
2 iron + 1 slag | smelt: = 3 ore

# Minimal (no process name, no attributes):
foo = 2 bar

# Attribute parsing: key=value pairs after |; numeric values parsed as numbers
widget | stamping: duration=4 | tier=2

# Freeform annotations: [key=val | key2=val2] bracket block, after initializer params
# Values: int/float auto-detected via JSON; strings as fallback; bare true/false stay as str
2 iron | smelt: duration=2 [tier=2 | energy=150]
1 widget | assemble: [assembler=mk2 | tier=2] = 2 iron + 1 copper
```

**Parsing order gotcha**: the `[...]` annotation block is extracted from the header
string *before* the outer `|` split, because `|` inside brackets would otherwise be
consumed as a segment separator. Inline `@` tokens are stripped from `attributes_raw`
*after* the `|` split but *before* the `process=name:` substitution regex, so they
don't bleed into the process name value.

`ProcessPredicates.annotation_matches(key, pred)` — filters library by annotation value;
`pred` is any callable `value -> bool`. Composes with `and_`/`or_`/`not_` as usual.

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

2 iron | smelt: duration=4
3 ore

# New @-block after recipes resets; only @prod applies to press
@prod

1 widget | press: duration=2
2 iron

# Inline @-augment on a recipe overrides the current block for that recipe only
1 gear | mill: @assembler_mk2 duration=3
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

### `analyze_graph(graph, num_keep=4)` → generator of result dicts

Requires a `"_"` sentinel open_output in the graph (injected by
`production_graphs`). Uses `_only` to find the sentinel process.

Each yielded dict:
```
"desired"               Ingredients — what was requested
"total_processes"       int — sum of all repeat counts INCLUDING the sentinel (sink=1)
"leak"                  float — worst-case pool imbalance (0.0 = perfectly balanced)
"transfer"              Ingredients — scaled dangling transfers (open inputs/outputs)
"inputs"                [(amount, kind)] — raw material requirements; "_" excluded
"sorted_process_counts" [(count, desc, slug)] — sorted deepest-first by output_depths
"yield"                 {kind: float} — actual output qty per desired kind (may exceed
                        requested when mul_outputs causes overproduction)
"process_augments"      {slug: list[str]} — applied_augments per process slug
```

`printable_analysis(aly, show_augments=False)` subtracts 1 from `total_processes`
for display. With `show_augments=True`, appends `@name` suffixes to process count
lines. Always prints a `makes:` line showing actual yield; annotates with
`(want: N)` when yield differs from what was requested.

### `batch_milps(graph)` → list of `{leakage, counts}` dicts

Intermediate function; calls `build_batch_matrix` then `best_milp_sequence`.
Each `counts` entry: `(repeat_count, process.describe(), process_slug)`.

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

## Remaining Cleanup

- **`build_matrix` / `build_batch_matrix`**: nearly identical — unify with `batch=False`
- **`find_pools_by_kind_and_process_name` / `find_pools_by_process_name_and_kind`**:
  identical methods — remove one
- **`pool_aliases`**: populated by `coalesce_pools` but never read — dead code
- **Continuous vs batch coexistence**: processes in a graph must all be one mode —
  known limitation, noted as a future goal

## Test Suite Status

```
test_utils.py          4  done
test_process.py       44  done
test_library.py       91  done
test_solver.py        18  done
test_graph.py         49  done  (build_matrix and build_batch_matrix both covered)
test_augment.py       18  done
test_orchestration.py 99  done
```

Total: 323 tests, all passing (`uv run pytest`).
