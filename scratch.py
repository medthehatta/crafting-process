from graph import GraphBuilder
from process import Ingredients
from process import Process
from solver import solve_milp
from solver import best_milp_sequence
from library import parse_to_registry
from library import Predicates


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
reg = parse_to_registry(sample.splitlines())


gb = GraphBuilder()

for p in reg:
    print(gb.add_process(p))

res = milps_graph(gb)
print(list(res))
