# CLAUDE.md

## Project

Production tree planner for video games. Given a desired output resource, builds
process graphs and solves for optimal integer repeat-counts via MILP.

See **[DEVELOPMENT.md](DEVELOPMENT.md)** for the full technical reference: module
map, data model, DSL syntax, library management, orchestration flow, MILP
formulation, key conventions, test suite status, ergonomics changelog, and feature
roadmap.

## Memory

Project memory lives in `.memory/` (hidden to avoid interfering with Python package discovery). Read and write it there.

## Quick start

```bash
uv run pytest                    # run all tests (347, all passing)
uv run python check_samples_v2.py  # end-to-end demo using the new API
```

```python
import crafting_process as cp

lib = cp.ProcessLibrary(path="recipes.txt", augments={"mk3": mk3_fn})
results = cp.plan(lib, "10 computer", n=3, only_augments=["mk3"])
print(cp.printable_analysis(results))
```
