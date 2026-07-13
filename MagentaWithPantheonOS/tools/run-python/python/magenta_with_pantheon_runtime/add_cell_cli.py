"""CLI entry point for the add_cell tool."""

from __future__ import annotations

import argparse

from .cli import emit
from .notebook import add_cell


def main() -> None:
    parser = argparse.ArgumentParser(prog="add_cell")
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--cell-type", default="code", choices=("code", "markdown", "raw"))
    parser.add_argument("--source", required=True)
    parser.add_argument("--position")
    args = parser.parse_args()
    emit(lambda: add_cell(args.file_path, args.source, cell_type=args.cell_type, position=args.position))


if __name__ == "__main__":
    main()
