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


def debug(x, msg=None):
    if msg:
        print(f"{msg}: {x}")
    else:
        print(x)
    return x
