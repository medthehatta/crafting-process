import itertools
from functools import reduce

from cytoolz import unique

from .graph import GraphBuilder
from .process import Process
from .library import ProcessLibrary
from .library import Ingredients
from .utils import only


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


def production_graphs(recipes, transfer, max_overlap=2):
    new_transfer = Ingredients.parse("_") - transfer
    g = GraphBuilder.from_process(Process.from_transfer(new_transfer))
    yield from _production_graphs(recipes, g, max_overlap=max_overlap)


def _production_graphs(recipes, consuming_graph, max_overlap=2):
    desired_kinds = [kind for (name, kind) in consuming_graph.open_inputs]

    input_recipes = []
    for kind in desired_kinds:
        producers = recipes.producing(kind) + [
            (
                f"{kind} default",
                GraphBuilder.from_process(
                    Process.from_transfer(Ingredients.parse(kind))
                ),
            )
        ]
        input_recipes.extend(producers)

    if not input_recipes:
        yield consuming_graph
        return

    indexed = dict(enumerate(input_recipes))
    kinds_produced = [
        tuple(kind for (_, kind) in graph.open_outputs)
        for (_, graph) in input_recipes
    ]
    combos = input_combinations(
        desired_kinds,
        kinds_produced,
        max_overlap=max_overlap,
    )
    sufficient_input_combos = (
        tuple(indexed[i] for i in combo)
        for combo in combos
    )
    for combo in sufficient_input_combos:
        graphs = [g for (n, g) in combo]

        upstream_graph = GraphBuilder()
        for g in graphs:
            upstream_graph.unify(g)

        total_graph = upstream_graph.output_into(consuming_graph)
        yield from _production_graphs(recipes, total_graph, max_overlap=max_overlap)


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
