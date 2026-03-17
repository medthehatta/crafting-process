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

        # Actual yield of each desired kind: sum outputs across all producers.
        result["yield"] = {
            kind: sum(
                count_by_process.get(name, 0) * proc.outputs[kind]
                for (name, proc) in graph.processes.items()
                if kind in proc.outputs.nonzero_components
            )
            for kind in desired.nonzero_components
        }

        # Applied augments keyed by process slug, for optional display.
        result["process_augments"] = {
            name: proc.applied_augments
            for (name, proc) in graph.processes.items()
        }

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
    skip_augments=None,
    only_augments=None,
):
    if skip_augments or only_augments is not None:
        recipes = recipes.with_augment_filter(
            skip_augments=skip_augments,
            only_augments=only_augments,
        )
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
    visited=None,
):
    skip_processes = skip_processes or []
    stop_kinds = stop_kinds or []
    visited = visited if visited is not None else set()

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
            and name not in visited
        ]
        if producers:
            input_recipes.extend(producers)
            recursable_kinds.append(kind)

    # Deduplicate: a process that satisfies multiple desired kinds would
    # otherwise appear once per kind, producing degenerate combos that
    # instantiate the same process more than once in a single graph.
    seen_names = set()
    deduped = []
    for item in input_recipes:
        if item[0] not in seen_names:
            seen_names.add(item[0])
            deduped.append(item)
    input_recipes = deduped

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
    for combo in combos:
        combo_graphs = tuple(GraphBuilder.from_process(indexed[i][1]) for i in combo)
        upstream_graph = GraphBuilder()
        for g in combo_graphs:
            upstream_graph.unify(g)

        total_graph = upstream_graph.output_into(consuming_graph)
        new_visited = visited | {indexed[i][0] for i in combo}

        yield from _production_graphs(
            recipes,
            total_graph,
            max_overlap=max_overlap,
            stop_kinds=stop_kinds,
            skip_processes=skip_processes,
            visited=new_visited,
        )


def printable_analysis(aly, show_augments=False):
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

        # Yield line: actual output quantity of each desired kind.
        yield_dict = a.get("yield", {})
        if yield_dict:
            desired_obj = a["desired"]
            yield_parts = []
            want_parts = []
            for kind in sorted(yield_dict):
                actual = yield_dict[kind]
                amt_str = str(int(actual)) if int(actual) == actual else f"{actual:.2f}"
                yield_parts.append(f"{amt_str} {kind}")
                wanted = desired_obj[kind]
                if actual != wanted:
                    w_str = str(int(wanted)) if int(wanted) == wanted else f"{wanted:.2f}"
                    want_parts.append(f"{w_str} {kind}")
            makes_line = f"   makes: {' + '.join(yield_parts)}"
            if want_parts:
                makes_line += f"  (want: {' + '.join(want_parts)})"
            out_lines.append(makes_line)

        out_lines.append("")

        for (amt, inp) in a["inputs"]:
            if int(amt) == amt:
                amt_str = str(ceil(amt))
            else:
                amt_str = f"{amt:0.2f}"
            out_lines.append(f"    {amt_str} {inp}")

        out_lines.append("")

        augments_map = a.get("process_augments", {}) if show_augments else {}
        for (count, desc, procname) in a["sorted_process_counts"]:
            if desc == "_":
                continue
            label = desc
            augs = augments_map.get(procname, [])
            if augs:
                label += " " + " ".join(f"@{aug}" for aug in augs)
            out_lines.append(f"    {count}x {label}")

        out_lines.append("")

    return "\n".join(out_lines)
