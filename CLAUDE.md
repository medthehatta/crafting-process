# CLAUDE.md

## Project

Production tree planner for video games. Given a desired output resource, builds
process graphs and solves for optimal integer repeat-counts via MILP.

See `summary.md` for full architecture reference, DSL syntax, and notes on
upcoming test work.

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
augment.py        Augments, AugmentedProcess
utils.py          only(), curry re-export
tests/            pytest suite — function style, no test classes
```

## Key Conventions

- **Tests**: `uv run pytest`, function style (no classes), one file per module.
  Helper factories at module level (e.g. `make_process()`). `pytest.approx` for
  floats. `pytest.raises(ValueError, match=...)` for errors.
- **Ingredient construction**: always via `Ingredients.parse("3 iron + 2 copper")`,
  never manual. The `parse` override normalises horizontal whitespace so `"iron  ore"`
  and `"iron ore"` intern to the same name.
- **Process names**: via `describe_process(output_names, process)` in `process.py` —
  shared by `Process.describe()` and `ProcessLibrary.mkname()`.
- **No dummy instances** just to call instance methods — extract a function instead.

## Critical Gotchas

### Pool naming is inverted from process perspective
`pool["inputs"]` = processes that **produce** into the pool (sources).
`pool["outputs"]` = processes that **consume** from the pool (sinks).
Confusing but intentional: inputs/outputs describe flow *relative to the pool*.

### FormalVector registry is global / class-level
`Ingredients._registry` and `_norm_lookup` are shared across all test runs in a
session. Names are interned on first use. Bypass via `Ingredients.parse` (which
normalises) not `Ingredients.named` directly.

### `best_milp_sequence` yield semantics
Yields `(actual_leak, answer_dict)` where `actual_leak = max(M @ x)` — the
worst-case pool imbalance of the **current** solution. The next round's tighter
constraint is `0.9 * actual_leak` (internal, not yielded). Final result has leak=0.

### `analyze_graph` expects a `"_"` sentinel
`production_graphs` injects a sink process with output kind `"_"`. `analyze_graph`
looks for this sentinel to identify the desired output. Manually constructed test
graphs must include it or use `batch_milps` directly.

### `output_into` is non-mutating; `unify` mutates in-place
`output_into(other)` returns a new `GraphBuilder`. `unify(other)` mutates `self`.

## Completed Cleanup

- Fixed 5 bugs: `__repr__` pluralization, `union()` double-assign, `unify()` wrong
  dict, regex `0-0`→`0-9`, `analyze_graphs` dropped `num_keep`
- Deleted `ops.py` (deprecated)
- Removed `consolidate_processes` (dead code behind `raise NotImplementedError`)
- Extracted `describe_process()` to deduplicate name-building logic
- `Ingredients.parse` normalises horizontal whitespace
- Fixed `best_milp_sequence` off-by-one: yielded `next_max_leak` instead of
  `actual_leak`

## Remaining Cleanup (post-tests)

- `build_matrix` / `build_batch_matrix`: nearly identical, differ only in
  `transfer_rate` vs `transfer` — unify with a `batch=False` param
- `orchestration._only`: duplicates `utils.only` — remove and import
- `find_pools_by_kind_and_process_name` / `find_pools_by_process_name_and_kind`:
  identical methods — remove one
- `augment.increase_energy_pct`: hardcoded to `"kWe"` (FIXME in source)
- `ProcessLibrary`: FIXME about not supporting `AugmentedProcess`

## Test Suite Status

```
test_utils.py          4  done
test_process.py       34  done
test_library.py       51  done
test_solver.py        18  done
test_graph.py         42  done
test_augment.py        0  TODO
test_orchestration.py 42  done
```

## Notes for test_graph.py

- Construct graphs directly: `GraphBuilder.from_process(p)` or `GraphBuilder()` +
  `add_process()`
- Cover: `add_process` populates open lists; `output_into` connects and removes from
  open lists; `unify` merges without connecting; `coalesce_pools` merges same-kind
- **Most important**: `build_batch_matrix` produces correct signed entries (positive
  for producers, negative for consumers) — the correctness of everything downstream
  depends on this
- `process_depths` / `output_depths` — secondary but worth covering
- `pool_aliases` is populated by `coalesce_pools` but unclear if anything reads it —
  investigate before writing tests for it

## Notes for test_orchestration.py

- `input_combinations` is a pure function — good unit test target, no fixtures needed
- `production_graphs` + `analyze_graph` are integration-level; a small ProcessLibrary
  fixture (3-4 processes, linear chain) is sufficient
- `_only` duplicates `utils.only` — clean up before or alongside adding tests
- `printable_analysis` consumes a generator — caller must not have advanced it first
