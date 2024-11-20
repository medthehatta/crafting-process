from coolname import generate_slug

from graph import GraphBuilder
from process import Ingredients
from process import Process
from solver import best_milp_sequence
from library import parse_processes
from library import process_from_spec_dict
from library import Predicates


class CraftingContext:

    def __init__(self):
        self.graphs = {}
        self.recipes = {}

    def get_graph(self, graph):
        if graph not in self.graphs:
            self.graphs[graph] = GraphBuilder()

        return self.graphs[graph]

    def get_recipe(self, recipe):
        return self.recipes[recipe]

    def name_recipe(self, recipe):
        # For now just generate a random slug
        return generate_slug(2)

    def add_recipes_from_text(self, text):
        found = parse_processes(text)
        for f in found:
            self.recipes[self.name_recipe(f)] = f

    def add_recipe_from_dict(self, data):
        recipe = process_from_spec_dict(data)
        name = self.name_recipe(recipe)
        self.recipes[name] = recipe
        return name

    def add_recipes_from_dicts(self, data):
        return [
            self.add_recipe_from_dict(datum)
            for datum in data
        ]

    def add_recipe_to_graph(self, graph, recipe):
        g = self.get_graph(graph)
        new = g.add_process(self.get_recipe(recipe))
        return new["name"]

    def find_recipe_producing(self, resource):
        return {
            n: r for (n, r) in self.recipes.items()
            if Predicates.outputs_part(resource, r)
        }

    def find_recipe_consuming(self, resource):
        return {
            n: r for (n, r) in self.recipes.items()
            if Predicates.requires_part(resource, r)
        }

    def add_resource_pool_to_graph(self, graph, pool_kind):
        g = self.get_graph(graph)
        new = g.add_pool(pool_kind)
        return new["name"]

    def connect(self, graph, source, dest):
        g = self.get_graph(graph)
        pool = g.connect_named(source, dest)
        return pool["name"]

    def milps(self, graph):
        m = self.get_graph(graph).build_matrix()
        # FIXME: Make output serializable
        return best_milp_sequence(m["matrix"], m["processes"])
