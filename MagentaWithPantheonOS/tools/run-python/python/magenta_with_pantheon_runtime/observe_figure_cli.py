"""CLI entry point for the observe_figure tool."""

from __future__ import annotations

import argparse
import json
import sys

from .figure import VisionUnavailableError, observe_figure


def main() -> None:
    parser = argparse.ArgumentParser(prog="observe_figure")
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--expectation")
    args = parser.parse_args()
    try:
        result = observe_figure(args.file_path, args.question, expectation=args.expectation)
    except VisionUnavailableError as error:
        print(f"VISION_UNAVAILABLE: {error}", file=sys.stderr)
        raise SystemExit(3) from error
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    json.dump(result, sys.stdout, ensure_ascii=True, separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
