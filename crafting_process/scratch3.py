import itertools
from functools import reduce
from pprint import pprint

from cytoolz import unique

from .library import ProcessLibrary
from .library import Ingredients
from .orchestration import analyze_graph
from .orchestration import analyze_graphs
from .orchestration import show_graph
from .orchestration import production_graphs
from .orchestration import printable_analysis


recipes = ProcessLibrary()
recipes.add_from_text(open("abiotic.txt", "r").read())


def p(desired_str, stop_kinds=None, skip_processes=None):
    result = list(
        production_graphs(
            recipes,
            Ingredients.parse(desired_str),
            stop_kinds=stop_kinds,
            skip_processes=skip_processes,
        )
    )
    print(f"Found {len(result)} procedures for: {desired_str}")
    return result


def pa(desired_str, stop_kinds=None, skip_processes=None):
    result = production_graphs(
        recipes,
        Ingredients.parse(desired_str),
        stop_kinds=stop_kinds,
        skip_processes=skip_processes,
    )
    pprint(analyze_graphs(result))


def pr(desired_str, stop_kinds=None, skip_processes=None):
    result = production_graphs(
        recipes,
        Ingredients.parse(desired_str),
        stop_kinds=stop_kinds,
        skip_processes=skip_processes,
    )
    print(printable_analysis(analyze_graphs(result)))


def debug(x, msg=None):
    if msg:
        print(f"{msg}: {x}")
    else:
        print(x)
    return x
