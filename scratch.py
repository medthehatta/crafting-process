from graph import GraphBuilder
from process import Ingredients
from process import Process
from solver import solve_milp
from solver import best_milp_sequence


def px(outs=None, ins=None, duration=1, **kwargs):
    outs = Ingredients.parse(outs) if outs else Ingredients.zero()
    ins = Ingredients.parse(ins) if ins else Ingredients.zero()
    return Process(outputs=outs, inputs=ins, duration=duration, **kwargs)


A = px("a")
B = px("c", "a + 2 b")
C = px("b")
D = px("2 b")
E = px("d", "b")

gb = GraphBuilder()
A1 = gb.add_process(A, "A1")
B1 = gb.add_process(B, "B1")
C1 = gb.add_process(C, "C1")
D1 = gb.add_process(D, "D1")
E1 = gb.add_process(E, "E1")

gb.connect("a", A1, B1)
gb.connect("b", C1, B1)
gb.connect("b", D1, B1)
gb.connect("b", D1, E1)

mr = gb.build_matrix()
result = solve_milp(mr["matrix"], mr["processes"], max_leak=1)


gb2 = GraphBuilder()
gb2.add_process(px("green chip", "3 wire + iron plate", duration=0.5), "green chip")
gb2.add_process(px("2 wire", "copper plate", duration=0.5), "wire")
gb2.add_process(px("copper plate"), "copper plate")

gb2.connect_named("wire", "wire", "green chip")
gb2.connect_named("copper plate", "copper plate", "wire")

mr2 = gb2.build_matrix()
result2 = solve_milp(mr2["matrix"], mr2["processes"], max_leak=1)


gb3 = GraphBuilder()
gb3.add_process(px("red chip", "4 wire + 2 green chip + 2 plastic", duration=6), "red chip")
gb3.add_process(px("green chip", "3 wire + iron plate", duration=0.5), "green chip")
gb3.add_process(px("2 wire", "copper plate", duration=0.5), "wire")
gb3.add_process(px("2 plastic", "coal + 20 petrol"), "plastic (chemplant)")

gb3.connect_named("wire", "wire", "green chip")
gb3.connect_named("wire", "wire", "red chip")
gb3.connect_named("green chip", "green chip", "red chip")
gb3.connect_named("plastic", "plastic (chemplant)", "red chip")

gb3.add_process(px("copper plate"), "copper plate src")
gb3.connect_named("copper plate", "copper plate src", "wire")

gb3.add_process(px("petrol"), "petrol src")
gb3.connect_named("petrol", "petrol src", "plastic (chemplant)")

gb3.add_process(px("coal"), "coal src")
gb3.connect_named("coal", "coal src", "plastic (chemplant)")

gb3.add_process(px(None, "10 red chip"), "red chip sink")
gb3.connect_named("red chip", "red chip", "red chip sink")

mr3 = gb3.build_matrix()
result3 = list(best_milp_sequence(mr3["matrix"], mr3["processes"]))
