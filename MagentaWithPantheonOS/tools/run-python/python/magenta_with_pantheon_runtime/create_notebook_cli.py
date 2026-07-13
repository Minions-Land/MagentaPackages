"""CLI entry point for the create_notebook tool."""

from __future__ import annotations

import argparse

from .cli import emit
from .notebook import create_notebook


def main() -> None:
    parser = argparse.ArgumentParser(prog="create_notebook")
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--kernel")
    parser.add_argument("--title")
    args = parser.parse_args()
    emit(lambda: create_notebook(args.file_path, kernel=args.kernel, title=args.title))


if __name__ == "__main__":
    main()
