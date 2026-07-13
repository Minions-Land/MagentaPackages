"""CLI entry point for the run_python tool."""

from __future__ import annotations

import argparse

from .cli import emit
from .execution import run_python


def main() -> None:
    parser = argparse.ArgumentParser(prog="run_python")
    parser.add_argument("--code", required=True)
    parser.add_argument("--env")
    parser.add_argument("--timeout-ms", type=int)
    args = parser.parse_args()
    emit(lambda: run_python(args.code, env=args.env, timeout_ms=args.timeout_ms), execution_contract=True)


if __name__ == "__main__":
    main()
