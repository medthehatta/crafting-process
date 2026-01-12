from pprint import pprint
import json
from math import ceil

import requests

from .graph import GraphBuilder
from .process import Ingredients
from .process import Process
from .solver import solve_milp
from .solver import best_milp_sequence
from .library import parse_augments
from .library import parse_processes
from .library import Predicates
from .ops import CraftingContext
from .utils import only


def cc_from_file(path):
    with open(path) as f:
        sample = f.read()
    cc = CraftingContext()
    cc.add_recipes_from_text(sample)
    return cc


cc = cc_from_file("abiotic.txt")


def reload_cc():
    global cc
    cc = cc_from_file("abiotic.txt")


def hedge_cc():
    global cc
    docid = "3HlY2E-rQSic13_63mXx7A"
    cc = CraftingContext()
    cc.add_recipes_from_text(requests.get(f"http://pad.mancer.in/{docid}/download").text)
    return cc


def display_graph_summary(cc, graph_name, num_keep=4):
    g = cc.get_graph(graph_name)

    # Print the procedure overview
    try:
        procedure = cc.graph_to_procedure(graph_name)
        pprint(procedure, indent=2)
    except ValueError:
        print("[suppressed tree view due to multi-output process]")

    # If the graph has just a single process, there's nothing to optimize.
    # Simply emit the process data.
    if len(g.processes) == 1:
        process = only(g.processes.values())
        # FIXME: This is batch specific
        transfer = process.transfer_quantity(True)
        print(f"{transfer}")
        return

    print("")

    # Otherwise, optimize and emit the process multiplicities
    # FIXME: This is batch specific
    milps = cc.batch_milps(graph_name)

    if len(milps) > num_keep:
        head = num_keep - 2
        relevant = milps[:head] + milps[-2:]
    else:
        relevant = milps

    # Get a dictionary of the process depths for sorting purposes
    depths = cc.process_depths_from_graph(graph_name)

    # Print out the list of the two tightest and two loosest ratio sets
    for (i, m) in enumerate(relevant, start=1):
        total_processes = sum(c for (c, _, _) in m["counts"])
        count_by_process = {name: count for (count, _, name) in m["counts"]}
        dangling = g.open_outputs + g.open_inputs
        transfer = Ingredients.sum(
            # FIXME: This is batch specific
            count_by_process[name] * g.processes[name].transfer_quantity(True).project(kind)
            for (name, kind) in dangling
        )

        print(f"{i}) {total_processes-1} processes, {m['leakage']} leak\n")
        for (component, amt, _) in sorted(transfer.triples(), key=lambda x: x[1]):
            if component == "_":
                continue
            # FIXME: This is batch specific
            print(f"    {ceil(-amt)} {component}")

        print("")

        decorated = [(a, b, c, depths[c]) for (a, b, c) in m["counts"]]
        output_depths = {
            output: max(depth for (_, o, process_name, depth) in decorated if o == output)
            for (_, output, _, _) in decorated
        }
        counts_by_product = sorted(m["counts"], key=lambda x: (output_depths[x[1]], x[1]), reverse=True)
        for c in counts_by_product:
            if c[1] == "_":
                continue
            print(f"    {c}")

        print("")


def rv(graph_names, num_keep=4):
    if not isinstance(graph_names, (list, tuple)):
        graph_names = [graph_names]

    for graph_name in graph_names:
        display_graph_summary(cc, graph_name, num_keep=num_keep)


def uni(output, stop_outputs=None):
    stop_outputs = stop_outputs or []

    olen = len(output)
    print("#"*(olen + 2*4 + 2))
    print(f"#    {output}    #")
    print("#"*(olen + 2*4 + 2))
    print("")

    rv(cc.find_unique_procedure_graph(output, stop_pred=Predicates.outputs_any_of(stop_outputs)))

