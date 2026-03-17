#!/usr/bin/env python
"""
check_batch.py — end-to-end demo of crafting-process with batch recipes.

Loads batch_recipes.txt, registers a journeyman_tools augment (doubles
output per craft), then runs production_graphs + MILP analysis for several
WoW-inspired crafting targets, demonstrating:
  * Batch MILP (no duration — integer craft counts, not rates)
  * Multi-output dependency resolution (trim_leather → trimmed + scraps)
  * Shared intermediate (iron_buckle needed by three different recipes)
  * journeyman_tools augment: mul_outputs(2) halves upstream craft counts
  * stop_kinds to treat a material as bought rather than crafted
  * Cross-profession chains (blacksmithing + leatherworking + jewelcrafting)
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

RECIPE_FILE = pathlib.Path(__file__).parent / "batch_recipes.txt"

lib = ProcessLibrary()

# journeyman_tools: doubles output per craft run.
# Same materials in, twice as many items out — MILP will
# prefer these variants since fewer runs are needed.
lib.register_augment(
    "journeyman_tools",
    Augments.mul_outputs(2),
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
            scored.append((r["leak"], r["total_processes"] - 1, g))
            break
    scored.sort(key=lambda x: (x[0], x[1]))
    return [g for (_, _, g) in scored[:n]]


def run_analysis(label, transfer, num_show=4, **pg_kwargs):
    print(f"\n{DIVIDER}")
    print(f"  {label}")
    graphs = list(production_graphs(lib, transfer, **pg_kwargs))
    print(f"  {len(graphs)} candidate graph(s)")
    print(DIVIDER)
    if not graphs:
        print("  (no solution found)\n")
        return
    best = top_graphs(graphs, n=num_show)
    print(printable_analysis(analyze_graphs(best, num_keep=2)))


# ----------------------------------------------------------------
# Analysis runs
# ----------------------------------------------------------------

# 1. Two iron swords, base crafting only — simple linear chain.
#    ore → bar → (grinding_stone from rough_stone) → sword.
#    Needs 2 forge_sword runs → 96 iron_ore total.
run_analysis(
    "2 iron_sword  [base only, no journeyman]",
    Ingredients.parse("2 iron_sword"),
    skip_augments=["journeyman_tools"],
)

# 2. Same target with journeyman_tools — doubled sword yield means
#    1 forge_sword run covers both swords → only 48 iron_ore needed.
#    Demonstrates how mul_outputs(2) halves upstream craft counts.
run_analysis(
    "2 iron_sword  [journeyman_tools only]",
    Ingredients.parse("2 iron_sword"),
    only_augments=["journeyman_tools"],
)

# 3. Iron shield — exercises shared iron_buckle.
#    shield needs iron_bar directly AND iron_buckle (also from iron_bar),
#    so smelt_iron must balance both demands.  MILP finds the minimal
#    integer split.
run_analysis(
    "1 iron_shield  [journeyman_tools only]",
    Ingredients.parse("1 iron_shield"),
    only_augments=["journeyman_tools"],
)

# 4. Light leather armor — most complex graph.
#    * trim_leather is multi-output: produces trimmed_leather AND
#      leather_scrap simultaneously.
#    * craft_padding consumes BOTH trim_leather outputs (trimmed +
#      scraps), while craft_armor also needs trimmed_leather directly.
#    * iron_buckle (blacksmithing) is shared with leatherworking here.
#    MILP must balance trim_leather runs so the multi-output byproducts
#    don't overflow.
run_analysis(
    "1 light_leather_armor  [journeyman_tools only]",
    Ingredients.parse("1 light_leather_armor"),
    only_augments=["journeyman_tools"],
    max_overlap=1,
)

# 5. Copper amulet — cross-profession chain.
#    Jewelcrafting (copper_ring) + blacksmithing (iron_buckle) converge.
#    stop_kinds=["iron_bar"] treats bars as purchased: skips smelt_iron,
#    leaving iron_bar as a raw input and simplifying the graph.
run_analysis(
    "1 copper_amulet  [journeyman_tools only, iron_bar is raw]",
    Ingredients.parse("1 copper_amulet"),
    only_augments=["journeyman_tools"],
    stop_kinds=["iron_bar"],
)

# 6. Compare: same copper_amulet but crafting bars from ore.
run_analysis(
    "1 copper_amulet  [journeyman_tools only, full chain]",
    Ingredients.parse("1 copper_amulet"),
    only_augments=["journeyman_tools"],
)
