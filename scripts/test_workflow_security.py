#!/usr/bin/env python3

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
USES_PATTERN = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
PINNED_ACTION_PATTERN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
CHECKOUT_STEP_PATTERN = re.compile(r"^\s*-\s*uses:\s*actions/checkout@[^\s#]+", re.MULTILINE)
NEXT_STEP_PATTERN = re.compile(r"^\s*-\s+", re.MULTILINE)


def check_checkout_credentials(contents: str, workflow: Path, failures: list[str]) -> None:
    """Require every checkout to leave the runner token out of git config."""
    for match in CHECKOUT_STEP_PATTERN.finditer(contents):
        next_step = NEXT_STEP_PATTERN.search(contents, match.end())
        block = contents[match.end() : next_step.start() if next_step else len(contents)]
        if not re.search(r"^\s+persist-credentials:\s*false\s*$", block, re.MULTILINE):
            failures.append(f"{workflow.relative_to(ROOT)}: checkout must set persist-credentials: false")


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
        check_checkout_credentials(contents, workflow, failures)

    release_workflow = WORKFLOW_DIR / "release.yml"
    if release_workflow.exists():
        contents = release_workflow.read_text(encoding="utf-8")
        if not re.search(r"^permissions:\s*\n\s+contents:\s*read\s*$", contents, re.MULTILINE):
            failures.append(".github/workflows/release.yml: default contents permission must be read")
        publish_match = re.search(r"^  publish:\s*$([\s\S]*?)(?=^  [A-Za-z0-9_-]+:\s*$|\Z)", contents, re.MULTILINE)
        if publish_match is None or not re.search(
            r"^\s+permissions:\s*\n\s+contents:\s*write\s*$", publish_match.group(1), re.MULTILINE
        ):
            failures.append(".github/workflows/release.yml: publish job must explicitly request contents: write")
        if "compare/${GITHUB_SHA}...main" not in contents:
            failures.append(".github/workflows/release.yml: release tags must be proven on main")
        if "python scripts/test_validate_packages.py" not in contents:
            failures.append(".github/workflows/release.yml: validator regression tests must run before release")
        if publish_match is not None:
            publish = publish_match.group(1)
            required_publish_patterns = {
                "unused destination gate": r"Require an unused package Release destination",
                "draft staging": r"draft:\s*true",
                "overwrite refusal": r"overwrite_files:\s*false",
                "latest refusal": r"make_latest:\s*false",
                "remote exact asset check": r"\.assets\[\]\.name",
                "remote digest check": r"\.assets\[\].*\.digest|remote_digest",
                "explicit finalization": r"--method PATCH[\s\S]*-F draft=false",
            }
            for label, pattern in required_publish_patterns.items():
                if not re.search(pattern, publish, re.MULTILINE):
                    failures.append(f".github/workflows/release.yml: publish job is missing {label}")
            order = [
                publish.find("Require an unused package Release destination"),
                publish.find("Stage private draft release"),
                publish.find("Verify and publish the exact draft"),
            ]
            if any(index < 0 for index in order) or order != sorted(order):
                failures.append(".github/workflows/release.yml: package publication order is unsafe")

    validate_workflow = WORKFLOW_DIR / "validate.yml"
    if validate_workflow.exists():
        contents = validate_workflow.read_text(encoding="utf-8")
        if "Cardiomni/tools/cardio-imaging-tools/python/test-requirements.txt" not in contents:
            failures.append(".github/workflows/validate.yml: Cardiomni test dependencies are not installed")
        if "python -m pytest Cardiomni/tools/cardio-imaging-tools/python/tests" not in contents:
            failures.append(".github/workflows/validate.yml: Cardiomni runtime tests are missing")

    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Verified immutable action pins in {len(workflows)} workflow(s).")


if __name__ == "__main__":
    main()
