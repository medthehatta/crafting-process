#!/usr/bin/env python
"""Command-line interface for crafting-process plan()."""

import argparse
import importlib.util
import inspect
import sys
import crafting_process as cp


def _load_augments(path):
    spec = importlib.util.spec_from_file_location("_augments", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {
        name: val
        for name, val in vars(mod).items()
        if not name.startswith("_")
        and callable(val)
        and not inspect.ismodule(val)
        and not inspect.isclass(val)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Find production plans for a desired yield."
    )
    parser.add_argument("yield_", metavar="yield", help='Desired yield, e.g. "10 computer"')
    parser.add_argument(
        "-r", "--recipes", default="recipes.txt", metavar="FILE",
        help="Recipe document to load (default: recipes.txt)"
    )
    parser.add_argument(
        "-a", "--augment-file", metavar="FILE",
        help="Python file whose public functions are loaded as augments"
    )
    parser.add_argument(
        "-m", "--mode", choices=["batch", "continuous"], default="batch",
        help="Process mode: batch (default) or continuous"
    )
    parser.add_argument(
        "-n", "--num-keep", type=int, default=5, metavar="N",
        help="Number of plans to return (default: 5)"
    )
    parser.add_argument(
        "-P", "--skip-process", dest="skip_processes", action="append",
        default=[], metavar="PROCESS",
        help="Skip a process by name (repeatable)"
    )
    parser.add_argument(
        "--skip-augment", dest="skip_augments", action="append",
        default=[], metavar="AUGMENT",
        help="Skip an augment by name (repeatable)"
    )
    parser.add_argument(
        "--only-augment", dest="only_augments", action="append",
        default=[], metavar="AUGMENT",
        help="Restrict to this augment (repeatable)"
    )
    parser.add_argument(
        "--max-overlap", type=int, default=2, metavar="N",
        help="Maximum process overlap in graph expansion (default: 2)"
    )
    parser.add_argument(
        "--stop-kind", dest="stop_kinds", action="append",
        default=[], metavar="KIND",
        help="Treat this resource kind as a terminal input (repeatable)"
    )
    parser.add_argument(
        "--show-augments", action="store_true",
        help="Show applied augments next to each process"
    )
    parser.add_argument(
        "--show-type", action="store_true",
        help="Show process type (batch/continuous) next to each process"
    )
    args = parser.parse_args()

    augments = _load_augments(args.augment_file) if args.augment_file else {}
    lib = cp.ProcessLibrary(args.mode, path=args.recipes, augments=augments)
    results = cp.plan(
        lib,
        args.yield_,
        num_keep=args.num_keep,
        skip_processes=args.skip_processes or None,
        skip_augments=args.skip_augments or None,
        only_augments=args.only_augments or None,
        max_overlap=args.max_overlap,
        stop_kinds=args.stop_kinds or None,
    )

    if not results:
        print("No plans found.", file=sys.stderr)
        sys.exit(1)

    print(cp.printable_analysis(
        iter(results),
        show_augments=args.show_augments,
        show_type=args.show_type,
    ))


if __name__ == "__main__":
    main()
