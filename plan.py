#!/usr/bin/env python
"""Command-line interface for crafting-process plan()."""

import argparse
import sys
import crafting_process as cp


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
        "-n", "--num-keep", type=int, default=5, metavar="N",
        help="Number of plans to return (default: 5)"
    )
    parser.add_argument(
        "-P", "--skip-process", dest="skip_processes", action="append",
        default=[], metavar="PROCESS",
        help="Skip a process by name (repeatable)"
    )
    args = parser.parse_args()

    lib = cp.ProcessLibrary(path=args.recipes)
    results = cp.plan(lib, args.yield_, num_keep=args.num_keep,
                      skip_processes=args.skip_processes or None)

    if not results:
        print("No plans found.", file=sys.stderr)
        sys.exit(1)

    print(cp.printable_analysis(iter(results)))


if __name__ == "__main__":
    main()
