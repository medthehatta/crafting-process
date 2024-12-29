from collections import Counter
from itertools import product

from coolname import generate_slug
from cytoolz import take

from graph import GraphBuilder
from process import Ingredients
from augment import AugmentedProcess
from solver import best_milp_sequence
from library import parse_processes
from library import parse_augments
from library import augments_from_records
from library import process_from_spec_dict
from library import Predicates
from utils import only


#
# Helpers
#


def _join_dicts(dicts):
    acc = {}
    for dic in dicts:
        acc.update(dic)
    return acc


def flatten(lst):
    return sum(list(lst), [])


#
# Classes
#


class CraftingContext:

    def __init__(self):
        self.graphs = {}
        self.recipes = {}
        self.augments = {}
        self.recipe_tags = {}
        self.process_tags = {}
        self.focused_graph = None

    #
    # Serialization
    #

    def get_graph(self, graph):
        if graph not in self.graphs:
            self.graphs[graph] = GraphBuilder()

        return self.graphs[graph]

    def get_augment(self, augment):
        return self.augments[augment]

    def get_recipe(self, recipe):
        return self.recipes[recipe]

    def describe_recipe(self, recipe):
        process_name = recipe.process
        output_names = recipe.outputs.nonzero_components
        if process_name:
            name = " + ".join(output_names) + f" via {process_name}"
        else:
            name = " + ".join(output_names)

        return name

    def name_recipe(self, recipe):
        process_name = recipe.process
        output_names = recipe.outputs.nonzero_components
        if process_name:
            name = " + ".join(output_names) + f" via {process_name}"
        else:
            name = " + ".join(output_names)

        if name in self.recipes:
            disambiguator = 2
            while f"{name} {disambiguator}" in self.recipes:
                disambiguator += 1
            name = f"{name} {disambiguator}"

        return name

    def recipes_to_dict(self, recipe_dict):
        # Convert the recipes in the recipe dict to dicts themselves
        return {k: v.to_dict() for (k, v) in recipe_dict.items()}

    def pull_recipes(self, procedure, flat=True):
        if not isinstance(procedure, dict):
            return []

        value = only(procedure.values())
        if "recipe" not in value:
            return []

        if flat:
            return flatten(
                [[value["recipe"]]] +
                [
                    self.pull_recipes({k: x})
                    for (k, x) in value.get("inputs", {}).items()
                ]
            )
        else:
            return (
                [value["recipe"]] +
                [
                    self.pull_recipes({k: x})
                    for (k, x) in value.get("inputs", {}).items()
                ]
            )

    #
    # Searching
    #

    def find_recipe_producing(self, resource):
        return {
            n: r.to_dict() for (n, r) in self.recipes.items()
            if Predicates.outputs_part(resource, r)
        }

    def find_recipe_consuming(self, resource):
        return {
            n: r.to_dict() for (n, r) in self.recipes.items()
            if Predicates.requires_part(resource, r)
        }

    def find_recipe_using(self, process):
        return {
            n: r.to_dict() for (n, r) in self.recipes.items()
            if Predicates.uses_process(process, r)
        }

    #
    # Inspection
    #

    def get_open_inputs(self, graph):
        g = self.get_graph(graph)
        return g.open_inputs

    def get_open_outputs(self, graph):
        g = self.get_graph(graph)
        return g.open_outputs

    #
    # Operations
    #

    def add_recipes_from_text(self, text):
        found = parse_processes(text.splitlines())
        staged = {self.name_recipe(f): AugmentedProcess(f) for f in found}
        self.recipes.update(staged)
        return self.recipes_to_dict(staged)

    def add_recipe_from_dict(self, data):
        recipe = process_from_spec_dict(data)
        name = self.name_recipe(recipe)
        self.recipes[name] = AugmentedProcess(recipe)
        return name

    def add_recipes_from_dicts(self, data):
        names = [
            self.add_recipe_from_dict(datum)
            for datum in data
        ]
        return self.recipes_to_dict({n: self.recipes[n] for n in names})

    def add_augments_from_text(self, text):
        found = parse_augments(text.splitlines())
        self.augments.update(found)
        return list(found.keys())

    def add_augment_from_dict(self, data):
        return only(self.add_augments_from_dicts([data]))

    def add_augments_from_dicts(self, data):
        found = augments_from_records(data)
        self.augments.update(found)
        return list(found.keys())

    def add_recipe_to_graph(self, graph, recipe):
        g = self.get_graph(graph)
        new = g.add_process(self.get_recipe(recipe))
        return new["name"]

    def add_resource_pool_to_graph(self, graph, pool_kind):
        g = self.get_graph(graph)
        new = g.add_pool(pool_kind)
        return new["name"]

    def apply_augment_to_recipe(
        self,
        recipe,
        augment,
        new_recipe_name=None,
        replace=False,
    ):
        r = self.get_recipe(recipe)
        a = self.get_augment(augment)
        new_recipe = r.with_augment(a)
        if new_recipe_name:
            new_recipe._process.process = new_recipe_name
        if replace:
            name = recipe
        else:
            name = self.name_recipe(new_recipe)
        self.recipes[name] = new_recipe
        return name

    def apply_augment_to_process(self, graph, augment_name, process_name):
        g = self.get_graph(graph)
        augment = self.get_augment(augment_name)
        g.processes[process_name].augments.append(augment)
        return g.processes[process_name]

    def remove_augment_from_process(self, graph, augment_name, process_name):
        g = self.get_graph(graph)
        augment = self.get_augment(augment_name)
        if augment in g.processes[process_name].augments:
            g.processes[process_name].augments.remove(augment)
        return g.processes[process_name]

    def connect(self, graph, source, dest):
        g = self.get_graph(graph)
        pool = g.connect_named(source, dest)
        return pool["name"]

    def consolidate(self, graph, process1, process2):
        g = self.get_graph(graph)
        g.consolidate_processes(process1, process2)

    def transfer_rates(self, graph):
        g = self.get_graph(graph)
        dangling = g.open_outputs + g.open_inputs
        return Ingredients.sum(
            g.processes[name].transfer_rate.project(kind)
            for (name, kind) in dangling
        )

    def milps(self, graph):
        g = self.get_graph(graph)
        self.focused_graph = graph
        m = g.build_matrix()
        seq = best_milp_sequence(m["matrix"], m["processes"])
        return [
            {
                "leakage": leak,
                "counts": [
                    (count, self.describe_recipe(g.processes[name]), name)
                    for (name, count) in counts.items()
                ],
            }
            for (leak, counts) in seq
        ]

    def batch_milps(self, graph):
        g = self.get_graph(graph)
        self.focused_graph = graph
        m = g.build_batch_matrix()
        seq = best_milp_sequence(m["matrix"], m["processes"])
        return [
            {
                "leakage": leak,
                "counts": [
                    (count, self.describe_recipe(g.processes[name]), name)
                    for (name, count) in counts.items()
                ],
            }
            for (leak, counts) in seq
        ]

    def set_graph(self, graph_name, graph):
        self.graphs[graph_name] = graph
        return graph_name

    def iterate_possible_procedures(
        self,
        output,
        stop_pred=None,
        skip_pred=None,
    ):
        stop_pred = stop_pred or (lambda x: False)
        skip_pred = skip_pred or (lambda x: False)

        found = self.find_recipe_producing(output)
        if not found:
            print(f"WARN: No recipe found for {output}")
            return {output: {}}

        for (name, recipe) in found.items():
            if stop_pred(self.recipes[name]):
                yield {output: {}}
                return

            elif skip_pred(self.recipes[name]):
                continue

            else:
                inputs = [name for (name, _) in recipe["inputs"]]
                constituent_itr = [
                    self.iterate_possible_procedures(
                        inp,
                        stop_pred=stop_pred,
                        skip_pred=skip_pred,
                    )
                    for inp in inputs
                ]
                for recipe_combo in product(*constituent_itr):
                    yield {
                        output: {
                            "recipe": name,
                            "inputs": _join_dicts(recipe_combo),
                        }
                    }

    def find_procedures(
        self,
        output,
        stop_pred=None,
        skip_pred=None,
        limit=10,
        hard_limit=1000,
    ):
        itr = self.iterate_possible_procedures(
            output,
            stop_pred=stop_pred,
            skip_pred=skip_pred,
        )

        lst = list(take(hard_limit, itr))

        recipe_histogram = dict(
            Counter(
                flatten(self.pull_recipes(procedure) for procedure in lst)
            )
        )

        try:
            next(itr)
            raise ValueError(
                f"Resultset is larger than {limit}, and is even larger than "
                f"{hard_limit}, so not counting the size!  "
                f"Recipe histogram (next line):\n {recipe_histogram}"
            )
        except StopIteration:
            pass

        if len(lst) > limit:
            raise ValueError(
                f"Resultset is larger than {limit}!  "
                f"Found {len(lst)} entries instead.  Apply filters.  "
                f"Recipe histogram (next line):\n {recipe_histogram}"
            )

        elif len(lst) == 0:
            raise ValueError("Resultset is empty!")

        return lst

    def procedure_to_graph(self, procedure, graph):
        (_, g) = self._procedure_to_graph(procedure)
        self.set_graph(graph, g)
        return g

    def _procedure_to_graph(self, procedure):
        g = GraphBuilder()

        # {"iron gear": {"recipe": "iron gear", "inputs": [...]}}
        spec = only(procedure.values())

        # This will just have one value
        recipe_name = spec.get("recipe")
        if not recipe_name:
            return (None, None)
        recipe = self.get_recipe(recipe_name)
        if not recipe:
            return (None, None)

        p = g.add_process(recipe)

        inputs = spec.get("inputs", {})

        for (k, inp) in inputs.items():
            (i_process, i_graph) = self._procedure_to_graph({k: inp})
            if i_process:
                g.unify(i_graph)
                g.connect(i_process, p)

        return (p, g)

    def graph_to_procedure(self, graph):
        g = self.get_graph(graph)
        # Currently we only support finding a procedure that produces a single
        # output because I haven't decided what it means for a procedure to
        # produce multiple yet
        (proc, res) = only(g.open_outputs)
        return self._graph_to_procedure(graph, proc)

    def _graph_to_procedure(self, graph, process_name):
        g = self.get_graph(graph)
        proc = g.processes[process_name]
        desired_inputs = list(proc.inputs.nonzero_components)
        output_names = proc.outputs.nonzero_components
        proc_desc = " + ".join(output_names) + f" v. {process_name}"

        input_pools = [
            pool for pool in g.pools.values()
            if process_name in pool.get("outputs", [])
        ]
        input_kinds = [pool["kind"] for pool in input_pools]
        input_processes = flatten([
            pool["inputs"] for pool in input_pools
        ])

        unspecified = [
            [inp] for inp in desired_inputs
            if inp not in input_kinds
        ]

        return [proc_desc] + [
            self._graph_to_procedure(graph, inp)
            for inp in input_processes
        ] + unspecified

    def join_graphs(self, graph1, graph2, new_name=None):
        if new_name is None:
            slug = generate_slug(2)
            new_name = f"{graph1} and {graph2} {slug}"
        self.graphs[new_name] = (
            self.get_graph(graph1).unify(self.get_graph(graph2))
        )
        return new_name
