#!/usr/bin/env python
"""
check_samples_v2.py — demo using the new ergonomic library interface.

Demonstrates:
  * ProcessLibrary constructed in one expression with augments + path
  * plan() as a drop-in for the production_graphs → analyze → rank loop
  * printable_analysis() on plan() results for human-readable output
  * PlanResult attributes for programmatic inspection (no dict access)
  * P predicates and lib.filtered() for pre-filtered library queries
  * lib | lib merge
"""

import crafting_process as cp
from crafting_process import Augments

DIVIDER = "=" * 66
RECIPE_FILE = "sample_recipes.txt"

# ----------------------------------------------------------------
# Build the library in one expression
# ----------------------------------------------------------------

lib = cp.ProcessLibrary(
    path=RECIPE_FILE,
    augments={
        "assembler_mk1": Augments.add_input_rate(cp.Ingredients.parse("50 kWe")),
        "assembler_mk2": Augments.composed(
            [
                Augments.mul_speed(1.5),
                Augments.add_input_rate(cp.Ingredients.parse("150 kWe")),
            ]
        ),
        "assembler_mk3": Augments.composed(
            [
                Augments.mul_speed(2.5),
                Augments.add_input_rate(cp.Ingredients.parse("375 kWe")),
            ]
        ),
    },
)

print(
    f"Library loaded: {len(lib.recipes)} entries "
    f"({sum(1 for p in lib.recipes.values() if not p.applied_augments)} base, "
    f"{sum(1 for p in lib.recipes.values() if p.applied_augments)} augmented)"
)


# ----------------------------------------------------------------
# Part 1: end-to-end with printable_analysis
# ----------------------------------------------------------------

print(f"\n{'#'*66}")
print("  PART 1 — printable_analysis output")
print(f"{'#'*66}")

# 1a. Computer, mk3 assemblers only — deepest chain in the file.
print(f"\n{DIVIDER}")
print("  1 computer  [assembler_mk3 only]")
print(DIVIDER)
results = cp.plan(
    lib, "1 computer", n=3, only_augments=["assembler_mk3"], max_overlap=1
)
print(cp.printable_analysis(iter(results), show_augments=True))

# 1b. 2 battery, mk2 assemblers — medium chain; battery_assembly produces 2
#     per run so requesting 2 gives a perfectly balanced solution.
print(f"\n{DIVIDER}")
print("  2 battery  [assembler_mk2 only]")
print(DIVIDER)
results = cp.plan(lib, "2 battery", n=3, only_augments=["assembler_mk2"])
print(cp.printable_analysis(iter(results)))

# 1c. Rocket part treating petroleum_gas as a raw material (bought externally).
print(f"\n{DIVIDER}")
print("  1 rocket_part  [assembler_mk3 only, petroleum_gas is raw]")
print(DIVIDER)
results = cp.plan(
    lib,
    "1 rocket_part",
    n=3,
    only_augments=["assembler_mk3"],
    stop_kinds=["petroleum_gas"],
    max_overlap=1,
)
print(cp.printable_analysis(iter(results)))


# ----------------------------------------------------------------
# Part 2: programmatic use of PlanResult
# ----------------------------------------------------------------

print(f"\n{'#'*66}")
print("  PART 2 — programmatic PlanResult inspection")
print(f"{'#'*66}")

# 2a. Show raw material requirements for the best computer plan.
print("\n--- Best plan for 1 computer (mk3): raw inputs ---")
results = cp.plan(
    lib, "1 computer", n=1, only_augments=["assembler_mk3"], max_overlap=1
)
best = results[0]
print(f"  Leak: {best.leak}  |  Processes: {best.total_processes - 1}")
for amt, kind in best.inputs:
    print(f"    {int(amt) if int(amt) == amt else f'{amt:.2f}':>6}  {kind}")

# 2b. Compare leak and process count across assembler tiers for solar_panel.
print("\n--- solar_panel: compare tiers by leak + process count ---")
for tier in ["assembler_mk1", "assembler_mk2", "assembler_mk3"]:
    results = cp.plan(lib, "1 solar_panel", n=1, only_augments=[tier])
    if results:
        r = results[0]
        print(f"  {tier:20s}  leak={r.leak:.1f}  processes={r.total_processes - 1}")
    else:
        print(f"  {tier:20s}  (no solution)")

# 2c. Inspect per-process repeat counts from ProcessCount objects.
print("\n--- Process breakdown for best 2 battery plan (mk2) ---")
results = cp.plan(lib, "2 battery", n=1, only_augments=["assembler_mk2"])
best = results[0]
for pc in best.process_counts:
    if pc.description == "_":
        continue
    augs = best.process_augments.get(pc.slug, [])
    aug_str = "  @" + " @".join(augs) if augs else ""
    print(f"  {pc.count:3d}x  {pc.description}{aug_str}")

# 2d. Find all plans for rocket_part and sort by total raw ore needed.
#     Demonstrates using PlanResult.inputs for custom ranking logic.
print("\n--- rocket_part plans ranked by total raw inputs (mk3, petroleum_gas raw) ---")
results = cp.plan(
    lib,
    "1 rocket_part",
    n=5,
    only_augments=["assembler_mk3"],
    stop_kinds=["petroleum_gas"],
    max_overlap=1,
)
ranked = sorted(results, key=lambda r: sum(amt for amt, _ in r.inputs), reverse=True)
for r in ranked:
    total = sum(amt for amt, _ in r.inputs)
    kinds = ", ".join(f"{int(amt)}{k}" for amt, k in r.inputs)
    print(f"  total_raw={int(total):4d}  leak={r.leak}  [{kinds}]")


# ----------------------------------------------------------------
# Part 3: filtered library + merge
# ----------------------------------------------------------------

print(f"\n{'#'*66}")
print("  PART 3 — filtered libraries and merge")
print(f"{'#'*66}")

# 3a. Build a smelting-only library and a chemistry-only library,
#     merge them, then plan something that needs both.
smelting_lib = lib.filtered(cp.P.annotation("category", lambda v: v == "smelting"))
chemistry_lib = lib.filtered(cp.P.annotation("category", lambda v: v == "chemistry"))
combined = smelting_lib | chemistry_lib
print(f"\n--- Merged smelting+chemistry library: {len(combined.recipes)} recipes ---")
for name in sorted(combined.recipes):
    print(f"  {name}")

# 3b. Use P predicates to find every recipe that produces something
#     that is also consumed by another recipe in the same library
#     (i.e., genuine intermediates, not raw inputs or final outputs).
all_inputs = set()
all_outputs = set()
for proc in lib.recipes.values():
    all_inputs |= set(proc.inputs.nonzero_components)
    all_outputs |= set(proc.outputs.nonzero_components)
intermediates = (all_inputs & all_outputs) - {"_"}

print(
    f"\n--- Recipes producing intermediates (not finals): {len(intermediates)} kinds ---"
)
pred = cp.Pred(lambda p: bool(set(p.outputs.nonzero_components) & intermediates))
intermediate_lib = lib.filtered(pred)
# Count only base (non-augmented) recipes for clarity
base_intermediates = [
    (name, proc)
    for name, proc in intermediate_lib.recipes.items()
    if not proc.applied_augments
]
print(f"  {len(base_intermediates)} base recipes produce intermediates")
for name, proc in sorted(base_intermediates):
    outputs = ", ".join(proc.outputs.nonzero_components)
    print(f"    {name}  →  {outputs}")
