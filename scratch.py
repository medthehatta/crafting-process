from pprint import pprint

from graph import GraphBuilder
from process import Ingredients
from process import Process
from solver import solve_milp
from solver import best_milp_sequence
from library import parse_augments
from library import parse_processes
from library import Predicates
from ops import CraftingContext
from utils import only


with open("spaceage-recipes.txt") as f:
    sample = f.read()


cc = CraftingContext()


assembler_augments = """
assembler-1
mul_speed 0.5
add_input 75.5 kW

assembler-2
mul_speed 0.75
add_input 150 kW

assembler-3
mul_speed 1.25
add_input 375 kW

"""


rec = cc.add_recipes_from_text(sample)
cc.add_augments_from_text(assembler_augments)

# Add assembler variants
for recipe in cc.find_recipe_using("character"):
    cc.apply_augment_to_recipe(recipe, "assembler-1", "assembler-1")
    cc.apply_augment_to_recipe(recipe, "assembler-2", "assembler-2")
    cc.apply_augment_to_recipe(recipe, "assembler-3", "assembler-3")


def s(output):
    procedures = cc.find_procedures(
        output,
        limit=1,
        skip_pred=Predicates.uses_any_of_processes([
            "character-mine",
            "character",
            #"assembler-1",
            "assembler-2",
            "assembler-3",
        ]),
        stop_pred=Predicates.outputs_any_of([
            "iron plate",
            "copper plate",
        ]),
    )

    for p in procedures:
        print(cc.pull_recipes(p, flat=False))

    res = only(procedures)
    cc.procedure_to_graph(res, "a")
    milps = cc.milps("a")

    if len(milps) > 4:
        relevant = milps[:2] + milps[-2:]
    else:
        relevant = milps

    for (i, m) in enumerate(relevant, start=1):
        total_processes = sum(c for (c, _, _) in m["counts"])
        print(f"{i}) {total_processes} processes, {m['leakage']} leak")
        for c in m["counts"]:
            print(f"    {c}")


def main():
    while inp := input(":: "):
        try:
            s(inp)
        except ValueError:
            pass


if __name__ == "__main__":
    main()
