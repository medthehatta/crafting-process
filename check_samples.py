#!/usr/bin/env python
"""
check_samples.py — end-to-end demo of crafting-process.

Loads sample_recipes.txt, registers three assembler-tier augments,
then runs production_graphs + MILP analysis for several products,
demonstrating:
  * Augment-filtered graph search (only_augments / skip_augments)
  * Multi-output dependency resolution (oil refining → plastic)
  * Shared-intermediate graphs (copper_wire used at multiple levels)
  * MILP integer optimisation across deep process chains
  * stop_kinds to treat a resource as a raw material boundary
"""

import pathlib

from crafting_process.augment import Augments
from crafting_process.library import ProcessLibrary
from crafting_process.process import Ingredients
from crafting_process.orchestration import (
    production_graphs,
    analyze_graph,
    analyze_graphs,
    printable_analysis,
)

# ----------------------------------------------------------------
# Build the library
# ----------------------------------------------------------------

RECIPE_FILE = pathlib.Path(__file__).parent / "sample_recipes.txt"

lib = ProcessLibrary()

# Assembler mk1: adds fixed energy overhead per run (no speed bonus)
lib.register_augment(
    "assembler_mk1",
    Augments.add_input_rate(Ingredients.parse("50 kWe")),
)

# Assembler mk2: 1.5× speed, higher energy draw
lib.register_augment(
    "assembler_mk2",
    Augments.composed([
        Augments.mul_speed(1.5),
        Augments.add_input_rate(Ingredients.parse("150 kWe")),
    ]),
)

# Assembler mk3: 2.5× speed, substantial energy draw
lib.register_augment(
    "assembler_mk3",
    Augments.composed([
        Augments.mul_speed(2.5),
        Augments.add_input_rate(Ingredients.parse("375 kWe")),
    ]),
)

lib.add_from_text(RECIPE_FILE.read_text())

print(f"Library loaded: {len(lib.recipes)} entries "
      f"({sum(1 for p in lib.recipes.values() if not p.applied_augments)} base, "
      f"{sum(1 for p in lib.recipes.values() if p.applied_augments)} augmented)")


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

DIVIDER = "=" * 66


def top_graphs(graphs, n=5):
    """Return the n graphs with the lowest (leak, total_processes)."""
    scored = []
    for g in graphs:
        for r in analyze_graph(g, num_keep=1):
            scored.append((r.leak, r.total_processes - 1, g))
            break
    scored.sort(key=lambda x: (x[0], x[1]))
    return [g for (_, _, g) in scored[:n]]


def run_analysis(label, transfer, num_show=4, show_augments=True, **pg_kwargs):
    print(f"\n{DIVIDER}")
    print(f"  {label}")
    graphs = list(production_graphs(lib, transfer, **pg_kwargs))
    print(f"  {len(graphs)} candidate graph(s)")
    print(DIVIDER)
    if not graphs:
        print("  (no solution found)\n")
        return
    best = top_graphs(graphs, n=num_show)
    print(printable_analysis(analyze_graphs(best, num_keep=2), show_augments=show_augments))


# ----------------------------------------------------------------
# Analysis runs
# ----------------------------------------------------------------

# 1. Computer — deepest chain in the file.
#    mk3 assemblers only.  Exercises:
#      - shared copper_wire used by wire_drawing, circuit_assembly,
#        adv_circuit_assembly, and proc_assembly simultaneously
#      - petroleum_gas from multi-output oil_refining → plastic
#      - MILP must balance integer run-counts across ~8 process types
run_analysis(
    "1 computer  [assembler_mk3 only]",
    Ingredients.parse("1 computer"),
    only_augments=["assembler_mk3"],
    max_overlap=1,
)

# 2. Battery — medium chain, mk2 assemblers.
#    sulfuric_acid from acid_plant; iron + copper from smelting.
#    battery_assembly produces 2 per run, so requesting 2 gives
#    a perfectly balanced solution.
run_analysis(
    "2 battery  [assembler_mk2 only]",
    Ingredients.parse("2 battery"),
    only_augments=["assembler_mk2"],
)

# 3. Solar panel — exercises steel (deep iron chain) and silicon
#    paths converging on one assembler.  mk3 only.
run_analysis(
    "1 solar_panel  [assembler_mk3 only]",
    Ingredients.parse("1 solar_panel"),
    only_augments=["assembler_mk3"],
)

# 4. Rocket part — uses stop_kinds to treat petroleum_gas as a raw
#    material (buy it externally rather than building an oil refinery).
#    Demonstrates stop_kinds while still showing the steel + processor
#    dependency chains.  Also shows skip_augments: exclude mk2 variants
#    to compare pure-mk3 solutions only.
run_analysis(
    "1 rocket_part  [assembler_mk3 only, petroleum_gas is raw]",
    Ingredients.parse("1 rocket_part"),
    only_augments=["assembler_mk3"],
    stop_kinds=["petroleum_gas"],
    max_overlap=1,
)

# 5. Compare: same rocket_part but with the full oil refining chain
#    included, so we can see how the MILP resolves the multi-output
#    byproducts (heavy_oil, light_oil appear as open outputs).
run_analysis(
    "1 rocket_part  [assembler_mk3 only, full oil chain]",
    Ingredients.parse("1 rocket_part"),
    only_augments=["assembler_mk3"],
    max_overlap=1,
)
