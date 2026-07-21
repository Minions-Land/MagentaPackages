#!/usr/bin/env python3

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
USES_PATTERN = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
PINNED_ACTION_PATTERN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def main() -> None:
    failures: list[str] = []
    workflows = sorted((*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")))
    if not workflows:
        raise SystemExit("no GitHub Actions workflows found")

    for workflow in workflows:
        contents = workflow.read_text(encoding="utf-8")
        for action in USES_PATTERN.findall(contents):
            if action.startswith("./"):
                continue
            if not PINNED_ACTION_PATTERN.fullmatch(action):
                failures.append(f"{workflow.relative_to(ROOT)}: unpinned action {action}")

    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Verified immutable action pins in {len(workflows)} workflow(s).")


if __name__ == "__main__":
    main()
