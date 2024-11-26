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
from utils import only


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


procedures = cc.find_procedures(
    "red circuit",
    limit=1,
    skip_pred=Predicates.uses_any_of_processes([
        "character",
        "burnerminer",
        "stonefurnace",
    ]),
    stop_pred=Predicates.outputs_any_of([
        "copper plate",
        "iron plate",
        "iron ore",
        "copper ore",
    ]),
)


pprint(res := list(procedures))
(_, g) = cc.procedure_to_graph(res[0])
cc.set_graph("a", g)
