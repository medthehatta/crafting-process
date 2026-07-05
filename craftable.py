#!/usr/bin/env python
"""Command-line interface for crafting-process attainable() — the inverse of
plan.py: given an inventory of items you have, report what you can make."""

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


def _fmt(n):
    return f"{n:g}"


def main():
    parser = argparse.ArgumentParser(
        description="Find what can be made from a given inventory."
    )
    parser.add_argument(
        "inventory", help='Items you have, e.g. "10 iron + 5 copper"'
    )
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
        "-t", "--target", dest="targets", action="append", default=[], metavar="KIND",
        help="Only report this output kind (repeatable); default: every producible kind"
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
        "--show-processes", action="store_true",
        help="Show the process run-counts used to reach each max quantity"
    )
    args = parser.parse_args()

    augments = _load_augments(args.augment_file) if args.augment_file else {}
    lib = cp.ProcessLibrary(args.mode, path=args.recipes, augments=augments)
    lib = lib.with_augment_filter(
        skip_augments=args.skip_augments or None,
        only_augments=args.only_augments or None,
    )

    results = cp.attainable(
        lib,
        args.inventory,
        targets=args.targets or None,
        skip_processes=args.skip_processes or None,
    )

    if not results:
        print("Nothing craftable beyond what you already have.", file=sys.stderr)
        sys.exit(1)

    for r in results:
        gain = r.quantity - r.starting
        print(f"{_fmt(r.quantity)} {r.kind}  (have {_fmt(r.starting)}, +{_fmt(gain)})")
        if args.show_processes:
            for count, description in r.process_counts:
                print(f"    {count}x {description}")


if __name__ == "__main__":
    main()
