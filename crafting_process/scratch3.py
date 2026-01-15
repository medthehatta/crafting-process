import itertools
from functools import reduce
from pprint import pprint

from cytoolz import unique

from .graph import GraphBuilder
from .process import Process
from .library import ProcessLibrary
from .library import Ingredients
from .utils import only
from .solver import best_milp_sequence


recipes = ProcessLibrary()
recipes.add_from_text(open("abiotic.txt", "r").read())


def input_combinations(input_kinds, kind_providers, max_overlap=2):
    pass
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
        # a, 1 = [abx, a]
        # a, 2 = [(abx, a)]
        # a, 3 = []
        return itertools.combinations(providing[kind], i)

    def _flatten_tup_of_tups(tot):
        # ((0,), (1,), (1,), (2,)) -> (0, 1, 2)
        return tuple(set(sum((list(t) for t in tot), [])))

    return unique(
        itertools.chain.from_iterable(
            (
                _flatten_tup_of_tups(prod) for prod in
                itertools.product(*[_c(kind, i) for kind in providing])
            )
            for i in range(1, min(max_overlap, len(providing)+1))
        )
    )


def production_graphs(
    recipes,
    transfer,
    max_overlap=2,
    stop_kinds=None,
):
    new_transfer = Ingredients.parse("_") - transfer
    g = GraphBuilder.from_process(Process.from_transfer(new_transfer))
    yield from _production_graphs(
        recipes,
        g,
        max_overlap=max_overlap,
        stop_kinds=stop_kinds,
    )


def _production_graphs(
    recipes,
    consuming_graph,
    max_overlap=2,
    stop_kinds=None,
):
    stop_kinds = stop_kinds or []
    desired_kinds = set(
        kind for (name, kind) in consuming_graph.open_inputs
        if kind not in stop_kinds
    )

    input_recipes = []
    recursable_kinds = []
    for kind in desired_kinds:
        producers = recipes.producing(kind)
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
        )


def process_depths_from_graph(graph):
    terminal_edges = graph.open_outputs
    input_processes = [process_name for (process_name, _) in terminal_edges]
    other = itertools.chain.from_iterable(
        _process_depths_from_graph(graph, inp, depth=0)
        for inp in input_processes
    )
    return dict(other)


def _process_depths_from_graph(graph, process_name, depth=0):
    input_pools = [
        pool for pool in graph.pools.values()
        if process_name in pool.get("outputs", [])
    ]
    input_processes = list(
        itertools.chain.from_iterable(pool["inputs"] for pool in input_pools)
    )
    other = list(
        itertools.chain.from_iterable(
            _process_depths_from_graph(graph, inp, depth=depth+1)
            for inp in input_processes
        )
    )
    max_depth = max([depth for (p, depth) in other if p == process_name] + [depth])
    return (
        [(process_name, max_depth)]
        + [(p, d) for (p, d) in other if p != process_name]
    )


def output_depths_from_graph(graph):
    depths = process_depths_from_graph(graph)

    # FIXME: This finds the deepest output process per pool, but do we want the
    # deepest input process?  If an output is just going nowhere and not being
    # consumed, that output doesn't need to be "ready" for anybody.
    out = {}
    for (process_name, process) in graph.processes.items():
        output_desc = describe_recipe(process)
        out[output_desc] = max(out.get(output_desc, -1), depths[process_name])

    return out


def describe_recipe(recipe):
    process_name = recipe.process
    output_names = recipe.outputs.nonzero_components
    if process_name:
        name = " + ".join(output_names) + f" via {process_name}"
    else:
        name = " + ".join(output_names)

    return name


def batch_milps(graph):
    m = graph.build_batch_matrix()
    seq = best_milp_sequence(m["matrix"], m["processes"])
    return [
        {
            "leakage": leak,
            "counts": [
                (count, describe_recipe(graph.processes[name]), name)
                for (name, count) in counts.items()
            ],
        }
        for (leak, counts) in seq
    ]


def analyze_graph(graph, num_keep=4):
    # FIXME: This is batch specific
    milps = batch_milps(graph)

    output_depths = output_depths_from_graph(graph)

    if len(milps) > num_keep:
        head = num_keep - 2
        relevant = milps[:head] + milps[-2:]
    else:
        relevant = milps

    for m in relevant:
        result = {}

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

