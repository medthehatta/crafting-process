from coolname import generate_slug

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


class CraftingContext:

    def __init__(self):
        self.graphs = {}
        self.recipes = {}
        self.augments = {}
        self.recipe_tags = {}
        self.process_tags = {}

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

    def milps(self, graph):
        m = self.get_graph(graph).build_matrix()
        # FIXME: Make output serializable
        return best_milp_sequence(m["matrix"], m["processes"])

    def set_graph(self, graph_name, graph):
        self.graphs[graph_name] = graph
        return graph_name
