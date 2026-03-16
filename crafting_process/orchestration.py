import itertools
from pprint import pprint
from math import ceil

from cytoolz import unique
from cytoolz import interleave

from .graph import GraphBuilder
from .process import Process
from .library import Ingredients
from .solver import best_milp_sequence
from .utils import only as _only


def analyze_graphs(graphs, num_keep=4):
    return interleave(analyze_graph(g, num_keep=num_keep) for g in graphs)


def analyze_graph(graph, num_keep=4):
    # Get the output node so we can figure out what was being asked for
    output_process_name = _only(
        name for (name, kind) in graph.open_outputs if kind == "_"
    )
    output_process = graph.processes[output_process_name]
    desired = output_process.inputs

    # FIXME: This is batch specific
    milps = batch_milps(graph)

    output_depths = graph.output_depths()

    if len(milps) > num_keep:
        head = num_keep - 2
        relevant = milps[:head] + milps[-2:]
    else:
        relevant = milps

    for m in relevant:
        result = {}
        result["desired"] = desired

        total_processes = sum(c for (c, _, _) in m["counts"])
        count_by_process = {name: count for (count, _, name) in m["counts"]}
        dangling = graph.open_outputs + graph.open_inputs
        transfer = Ingredients.sum(
            # FIXME: This is batch specific
            count_by_process[name] *
            graph.processes[name].transfer_quantity(True).project(kind)
            for (name, kind) in dangling
        )

        result["total_processes"] = total_processes
        result["leak"] = m["leakage"]
        result["transfer"] = transfer
        result["inputs"] = sorted(
            [
                (-amt, kind) for (kind, amt, _) in transfer.triples()
                if kind != "_"
            ],
            reverse=True,
        )

        counts_by_product = sorted(
            m["counts"],
            # x = (count, product description, process name)
            key=lambda x: (output_depths[x[1]], x[1]),
            reverse=True,
        )

        result["sorted_process_counts"] = counts_by_product

        yield result


def show_graph(graph):
    pprint(list(analyze_graph(graph)))


def batch_milps(graph):
    m = graph.build_batch_matrix()
    seq = best_milp_sequence(m["matrix"], m["processes"])
    return [
        {
            "leakage": leak,
            "counts": [
                (count, graph.processes[name].describe(), name)
                for (name, count) in counts.items()
            ],
        }
        for (leak, counts) in seq
    ]


def input_combinations(input_kinds, kind_providers, max_overlap=2):
    if max_overlap < 1:
        raise ValueError("max_overlap must be >= 1")

    if not input_kinds:
        return

    # dest: abcde
    # inputs: abx cde a b c d e
    providing = {
        kind: [
            i for (i, provider) in enumerate(kind_providers)
            if kind in provider
        ]
        for kind in input_kinds
    }

    def _c(kind, i):
        # a, 1 = [(abx,), (a,)]
        # a, 2 = [(abx, a)]
        # a, 3 = []
        return itertools.combinations(providing[kind], i)

    def _flatten_tup_of_tups(tot):
        # ((0,), (1,), (1,), (2,)) -> (0, 1, 2)
        return tuple(set(sum((list(t) for t in tot), [])))

    yield from unique(
        itertools.chain.from_iterable(
            (
                _flatten_tup_of_tups(prod) for prod in
                itertools.product(*[_c(kind, i) for kind in providing])
            )
            for i in range(1, min(max_overlap, len(providing))+1)
        )
    )


def production_graphs(
    recipes,
    transfer,
    max_overlap=2,
    stop_kinds=None,
    skip_processes=None,
):
    new_transfer = Ingredients.parse("_") - transfer
    g = GraphBuilder.from_process(Process.from_transfer(new_transfer))
    yield from _production_graphs(
        recipes,
        g,
        max_overlap=max_overlap,
        stop_kinds=stop_kinds,
        skip_processes=skip_processes,
    )


def _production_graphs(
    recipes,
    consuming_graph,
    max_overlap=2,
    stop_kinds=None,
    skip_processes=None,
):
    skip_processes = skip_processes or []
    stop_kinds = stop_kinds or []
    desired_kinds = set(
        kind for (name, kind) in consuming_graph.open_inputs
        if kind not in stop_kinds
    )

    input_recipes = []
    recursable_kinds = []
    for kind in desired_kinds:
        producers = [
            (name, proc) for (name, proc) in recipes.producing(kind)
            if proc.process not in skip_processes
        ]
        if producers:
            input_recipes.extend(producers)
            recursable_kinds.append(kind)

    if not input_recipes:
        yield consuming_graph
        return

    indexed = dict(enumerate(input_recipes))
    kinds_produced = [
        tuple(process.outputs.nonzero_components)
        for (_, process) in input_recipes
    ]
    combos = input_combinations(
        recursable_kinds,
        kinds_produced,
        max_overlap=max_overlap,
    )
    sufficient_input_combos = (
        # indexed[0] = ("process_name", Process[-A + B])
        tuple(GraphBuilder.from_process(indexed[i][1]) for i in combo)
        for combo in combos
    )
    for graphs in sufficient_input_combos:
        upstream_graph = GraphBuilder()
        for g in graphs:
            upstream_graph.unify(g)

        total_graph = upstream_graph.output_into(consuming_graph)
        yield from _production_graphs(
            recipes,
            total_graph,
            max_overlap=max_overlap,
            stop_kinds=stop_kinds,
            skip_processes=skip_processes,
        )


def printable_analysis(aly):
    out_lines = []

    first = next(aly)
    desired = first["desired"]
    w = len(str(desired))
    out_lines.append("#"*(10 + w))
    out_lines.append(f"#    {desired}    #")
    out_lines.append("#"*(10 + w))
    out_lines.append("")

    for (i, a) in enumerate(itertools.chain([first], aly), start=1):
        tot = a["total_processes"] - 1
        tot_s = f"1 process" if tot == 1 else f"{tot} processes"
        out_lines.append(f"{i}) {tot_s}, {a['leak']} leak")
        out_lines.append("")

        for (amt, inp) in a["inputs"]:
            if int(amt) == amt:
                amt_str = str(ceil(amt))
            else:
                amt_str = f"{amt:0.2f}"
            out_lines.append(f"    {amt_str} {inp}")

        out_lines.append("")

        for (count, desc, procname) in a["sorted_process_counts"]:
            if desc == "_":
                continue
            out_lines.append(f"    {count}x {desc}")

        out_lines.append("")

    return "\n".join(out_lines)
