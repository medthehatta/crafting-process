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


sample = """
cookies | bake: duration=5
milk + eggs + butter + sugar

butter | churn: duration=20
milk

milk | duration=1

butter | purchase: duration=10
money

"""

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
augs = parse_augments(augs_sample.splitlines())
