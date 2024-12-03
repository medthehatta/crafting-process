from pprint import pprint
import json

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


augment_text = """
assembler-1
mul_speed 0.5
add_input_rate 75.5 kWe

assembler-2
mul_speed 0.75
add_input_rate 150 kWe

assembler-3
mul_speed 1.25
add_input_rate 375 kWe

chemical-plant
add_input_rate 217 kWe

burner-mining-drill
mul_speed 0.25

electric-mining-drill
mul_speed 0.5
add_input_rate 90 kWe

stone-furnace
add_input_rate 0.0225 coal

steel-furnace
mul_speed 2
add_input_rate 0.0225 coal

"""


rec = cc.add_recipes_from_text(sample)
cc.add_augments_from_text(augment_text)

# Add assembler variants
for recipe in cc.find_recipe_using("character"):
    cc.apply_augment_to_recipe(recipe, "assembler-1", "assembler-1")
    cc.apply_augment_to_recipe(recipe, "assembler-2", "assembler-2")
    cc.apply_augment_to_recipe(recipe, "assembler-3", "assembler-3")

for recipe in cc.find_recipe_using("chemical-plant"):
    cc.apply_augment_to_recipe(recipe, "chemical-plant", replace=True)

for recipe in cc.find_recipe_using("burner-mining-drill"):
    # We do the electric one first because once we do the burner ones the speed
    # will be set to 0.25 and the electric multiplier will be wrong
    cc.apply_augment_to_recipe(recipe, "electric-mining-drill", "electric-mining-drill")
    cc.apply_augment_to_recipe(recipe, "burner-mining-drill", replace=True)

for recipe in cc.find_recipe_using("furnace"):
    cc.apply_augment_to_recipe(recipe, "stone-furnace", "stone-furnace")
    cc.apply_augment_to_recipe(recipe, "steel-furnace", "steel-furnace")


def get_procedure(output, skip_pred=None, stop_pred=None, num_keep=4):
    procedures = cc.find_procedures(
        output,
        limit=1,
        skip_pred=skip_pred,
        stop_pred=stop_pred,
    )

    # Print these for debug purposes
    for p in procedures:
        print(cc.pull_recipes(p, flat=False))

    graph_name = output

    res = only(procedures)
    cc.procedure_to_graph(res, graph_name)
    resolve_graph(cc, graph_name, num_keep=num_keep)


def resolve_graph(cc, graph_name, num_keep=4):
    g = cc.get_graph(graph_name)
    milps = cc.milps(graph_name)

    if len(milps) > num_keep:
        head = num_keep - 2
        relevant = milps[:head] + milps[-2:]
    else:
        relevant = milps

    # Print out the list of the two tightest and two loosest ratio sets
    for (i, m) in enumerate(relevant, start=1):
        total_processes = sum(c for (c, _, _) in m["counts"])
        count_by_process = {name: count for (count, _, name) in m["counts"]}
        dangling = g.open_outputs + g.open_inputs
        transfer = Ingredients.sum(
            count_by_process[name] * g.processes[name].transfer_rate.project(kind)
            for (name, kind) in dangling
        )
        print(
            f"{i}) {total_processes} processes, {m['leakage']} leak\n"
            f"    {transfer}"
        )
        for c in m["counts"]:
            print(f"    {c}")

    # Print the procedure overview
    procedure = cc.graph_to_procedure(graph_name)
    print(json.dumps(procedure))


def get_batch_procedure(output, skip_pred=None, stop_pred=None, num_keep=4):
    procedures = cc.find_procedures(
        output,
        limit=1,
        skip_pred=skip_pred,
        stop_pred=stop_pred,
    )

    # Print these for debug purposes
    for p in procedures:
        print(cc.pull_recipes(p, flat=False))

    graph_name = output

    res = only(procedures)
    cc.procedure_to_graph(res, graph_name)
    resolve_batch_graph(cc, graph_name, num_keep=num_keep)


def resolve_batch_graph(cc, graph_name, num_keep=4):
    g = cc.get_graph(graph_name)
    milps = cc.batch_milps(graph_name)

    if len(milps) > num_keep:
        head = num_keep - 2
        relevant = milps[:head] + milps[-2:]
    else:
        relevant = milps

    # Print out the list of the two tightest and two loosest ratio sets
    for (i, m) in enumerate(relevant, start=1):
        total_processes = sum(c for (c, _, _) in m["counts"])
        count_by_process = {name: count for (count, _, name) in m["counts"]}
        dangling = g.open_outputs + g.open_inputs
        transfer = Ingredients.sum(
            count_by_process[name] * g.processes[name].transfer.project(kind)
            for (name, kind) in dangling
        )
        print(
            f"{i}) {total_processes} processes, {m['leakage']} leak\n"
            f"    {transfer}"
        )
        for c in m["counts"]:
            print(f"    {c}")

    # Print the procedure overview
    procedure = cc.graph_to_procedure(graph_name)
    print(json.dumps(procedure))


def main():
    while inp := input(":: "):
        if inp.startswith(".show"):
            spl = inp.strip().split(" ", 1)
            if len(spl) > 1:
                (_, num) = spl
            else:
                num = 4
            resolve_graph(cc, cc.focused_graph, int(num))
        elif inp.startswith(".consolidate"):
            processes = inp.strip().split()[1:]
            a = processes[0]
            for b in processes[1:]:
                cc.consolidate(cc.focused_graph, a, b)
            resolve_graph(cc, cc.focused_graph)
        elif inp.startswith(".rates"):
            print(cc.transfer_rates(cc.focused_graph))
        elif inp.startswith(".graphs"):
            print(list(cc.graphs.keys()))
        elif inp.startswith(".focus"):
            (_, what) = inp.strip().split(" ", 1)
            cc.focused_graph = what
            print(what)
        elif inp.startswith(".recipes"):
            print(list(cc.recipes))
        else:
            try:
                get_procedure(inp)
            except ValueError as err:
                print(err)
                pass


if __name__ == "__main__":
    get_batch_procedure(
        "red circuit",
        skip_pred=Predicates.uses_any_of_processes([
            "character-mine",
            "character",
            #"assembler-1",
            "assembler-2",
            "assembler-3",
            "burner-mining-drill",
            "furnace",
            "stone-furnace",
        ]),
        stop_pred=Predicates.outputs_any_of([
            "coal",
            "oil",
            "kWe",
            "iron plate",
            "copper plate",
        ]),
        num_keep=4,
    )

