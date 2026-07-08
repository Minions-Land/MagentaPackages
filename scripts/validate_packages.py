#!/usr/bin/env python3
"""Validate package manifests and repository hygiene."""

from __future__ import annotations

import subprocess
import sys
import ast
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - version guard
    print("Python 3.11+ is required for tomllib.", file=sys.stderr)
    sys.exit(2)


ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {
    ".git",
    ".pixi",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "tmp",
    "scratch",
}
IGNORED_NAMES = {".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".log"}
MAX_FILE_SIZE = 100 * 1024 * 1024


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def git_visible_files() -> list[Path]:
    """Return tracked and unignored untracked files, relative to repo policy."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [
            path
            for path in ROOT.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(ROOT).parts
        ]

    return [ROOT / line for line in result.stdout.splitlines() if line]


def check_repo_hygiene(files: list[Path], errors: list[str]) -> None:
    for path in files:
        parts = set(path.relative_to(ROOT).parts)
        if parts & IGNORED_DIRS:
            errors.append(f"{rel(path)} is a generated/local artifact")
        if path.name in IGNORED_NAMES or path.suffix in IGNORED_SUFFIXES:
            errors.append(f"{rel(path)} is ignored by repository policy")
        if path.exists() and path.stat().st_size > MAX_FILE_SIZE:
            errors.append(f"{rel(path)} exceeds 100 MB")


def check_toml(files: list[Path], errors: list[str]) -> None:
    for path in sorted(p for p in files if p.suffix == ".toml"):
        try:
            load_toml(path)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{rel(path)} is invalid TOML: {exc}")


def check_python_syntax(files: list[Path], errors: list[str]) -> None:
    for path in sorted(p for p in files if p.suffix == ".py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=rel(path))
        except SyntaxError as exc:
            errors.append(f"{rel(path)} is invalid Python: {exc.msg} at line {exc.lineno}")


def validate_component(
    package_root: Path,
    package_id: str,
    component: dict[str, Any],
    profile_names: set[str],
    errors: list[str],
) -> None:
    kind = component.get("kind")
    name = component.get("name")
    path_value = component.get("path")

    if not isinstance(kind, str) or not kind:
        errors.append(f"{package_id}: component missing kind")
    if not isinstance(name, str) or not name:
        errors.append(f"{package_id}: component missing name")
    if not isinstance(path_value, str) or not path_value:
        errors.append(f"{package_id}:{name}: component missing path")
        return

    component_path = package_root / path_value
    if not component_path.exists():
        errors.append(f"{package_id}:{name}: missing path {path_value}")
        return

    for profile in component.get("profiles", []):
        if profile not in profile_names:
            errors.append(f"{package_id}:{name}: unknown profile {profile}")

    if kind == "skill" and not (component_path / "SKILL.md").is_file():
        errors.append(f"{package_id}:{name}: skill path lacks SKILL.md")

    if kind in {"tool", "append-system-prompt"}:
        if not component_path.is_file():
            errors.append(f"{package_id}:{name}: descriptor path is not a file")
            return
        try:
            descriptor = load_toml(component_path)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{rel(component_path)} is invalid TOML: {exc}")
            return

        descriptor_kind = descriptor.get("kind")
        if kind == "tool" and descriptor_kind not in {"tool", "process"}:
            errors.append(
                f"{package_id}:{name}: tool descriptor has unexpected kind {descriptor_kind!r}"
            )
        if kind == "append-system-prompt":
            content_path = descriptor.get("content_path")
            if isinstance(content_path, str) and not (component_path.parent / content_path).is_file():
                errors.append(
                    f"{package_id}:{name}: missing system prompt content {content_path}"
                )

    if kind == "brand":
        brand_toml = component_path / "brand.toml"
        if not brand_toml.is_file():
            errors.append(f"{package_id}:{name}: brand path lacks brand.toml")


def check_packages(errors: list[str]) -> None:
    package_files = sorted(
        path for path in ROOT.glob("*/package.toml") if path.parent.is_dir()
    )
    if not package_files:
        errors.append("no package.toml files found")
        return

    package_ids: set[str] = set()
    for package_file in package_files:
        package_root = package_file.parent
        try:
            manifest = load_toml(package_file)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{rel(package_file)} is invalid TOML: {exc}")
            continue

        package_id = manifest.get("id")
        if package_id != package_root.name:
            errors.append(f"{rel(package_file)} id must match directory name")
        if package_id in package_ids:
            errors.append(f"duplicate package id {package_id}")
        if isinstance(package_id, str):
            package_ids.add(package_id)
        else:
            package_id = package_root.name

        if manifest.get("schema_version") != "magenta.package.v1":
            errors.append(f"{package_id}: unsupported schema_version")

        profiles = manifest.get("profiles", [])
        profile_names = {
            profile.get("name")
            for profile in profiles
            if isinstance(profile, dict) and isinstance(profile.get("name"), str)
        }
        for profile in profiles:
            for parent in profile.get("extends", []):
                if parent not in profile_names:
                    errors.append(f"{package_id}: profile extends unknown {parent}")
        for default_profile in manifest.get("default_profiles", []):
            if default_profile not in profile_names:
                errors.append(f"{package_id}: default profile {default_profile} is unknown")

        seen_components: set[tuple[str, str]] = set()
        components = manifest.get("components", [])
        if not isinstance(components, list) or not components:
            errors.append(f"{package_id}: no components declared")
            continue
        for component in components:
            if not isinstance(component, dict):
                errors.append(f"{package_id}: component entry is not a table")
                continue
            key = (str(component.get("kind")), str(component.get("name")))
            if key in seen_components:
                errors.append(f"{package_id}: duplicate component {key[0]}:{key[1]}")
            seen_components.add(key)
            validate_component(package_root, str(package_id), component, profile_names, errors)


def main() -> int:
    errors: list[str] = []
    files = git_visible_files()
    check_repo_hygiene(files, errors)
    check_toml(files, errors)
    check_python_syntax(files, errors)
    check_packages(errors)

    if errors:
        print("Package validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    package_count = len(list(ROOT.glob("*/package.toml")))
    skill_count = len(list(ROOT.glob("*/skills/**/SKILL.md")))
    print(f"Validated {package_count} packages and {skill_count} skill entrypoints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
