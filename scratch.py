from itertools import product
from pprint import pprint

from cytoolz import curry
from cytoolz import take

from graph import GraphBuilder
from process import Ingredients
from process import Process
from solver import solve_milp
from solver import best_milp_sequence
from library import parse_augments
from library import parse_processes
from library import Predicates
from ops import CraftingContext


def milps_graph(graph):
    m = graph.build_matrix()
    return best_milp_sequence(m["matrix"], m["processes"])


with open("krastorio-recipes.txt") as f:
    sample = f.read()

augs_sample = """
assembler 1
mul_speed 0.5
add_input 75.5 kWe

"""

#reg = parse_processes(sample.splitlines())
#
#
#gb = GraphBuilder()
#
#for p in reg:
#    print(gb.add_process(p))
#
#res = milps_graph(gb)
#print(list(res))


# Add recipe
# Add recipe to graph
# Add resource pool to graph
# Connect processes or resource pools in graph
# Compute MILP for the graph


cc = CraftingContext()


rec = cc.add_recipes_from_text(sample)
augs = cc.add_augments_from_text(augs_sample)


def _join_dicts(dicts):
    acc = {}
    for dic in dicts:
        acc.update(dic)
    return acc


def iterate_possible_recipes(
    ctx,
    output,
    stop_pred=None,
    skip_pred=None,
):
    stop_pred = stop_pred or (lambda x: False)
    skip_pred = skip_pred or (lambda x: False)

    found = ctx.find_recipe_producing(output)
    if not found:
        return {output: {}}

    for (name, recipe) in found.items():
        if stop_pred(ctx.recipes[name]):
            yield {output: {}}
            return

        elif skip_pred(ctx.recipes[name]):
            continue

        else:
            inputs = [name for (name, _) in recipe["inputs"]]
            constituent_itr = [
                iterate_possible_recipes(ctx, inp, stop_pred=stop_pred, skip_pred=skip_pred)
                for inp in inputs
            ]
            for recipe_combo in product(*constituent_itr):
                yield {
                    output: {
                        "recipe": name,
                        "inputs": _join_dicts(recipe_combo),
                    }
                }


def find_recipes(
    ctx,
    output,
    stop_pred=None,
    skip_pred=None,
    limit=10,
    hard_limit=1000,
):
    itr = iterate_possible_recipes(
        ctx,
        output,
        stop_pred=stop_pred,
        skip_pred=skip_pred,
    )

    lst = list(take(hard_limit, itr))

    try:
        next(itr)
        raise ValueError(
            f"Resultset is larger than {limit}, and is even larger than "
            f"{hard_limit}, so not counting the size!  Apply filters."
        )
    except StopIteration:
        pass

    if len(lst) > limit:
        raise ValueError(
            f"Resultset is larger than {limit}!  "
            f"Found {len(lst)} entries instead.  Apply filters."
        )

    return lst


g = find_recipes(
    cc,
    "medium electric pole",
    limit=5,
)


pprint(list(g))
