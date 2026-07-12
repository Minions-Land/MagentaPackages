#!/usr/bin/env python3
"""Validate package manifests and repository hygiene."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path, PureWindowsPath
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
HcpClientsafeidpattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
HcpClientwindowsreservednamepattern = re.compile(
    r"^(?:aux|con|nul|prn|com[1-9]|lpt[1-9])(?:\..*)?$", re.IGNORECASE
)
HcpClientprereleaseidentifier = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
HcpClientsemverpattern = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    rf"(?:-{HcpClientprereleaseidentifier}(?:\.{HcpClientprereleaseidentifier})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
HcpClientmodulesourcekinds = {
    "skill",
    "tool",
    "brand",
    "system-prompt",
    "append-system-prompt",
    "theme",
    "prompt-template",
}
HcpClientinfrastructurekinds = {"env", "env-lock", "python-runtime", "runtime-tests"}
HcpClientproductmethods = {"toCapability", "toResource", "toTool"}


def HcpClientisportablepackageid(value: object) -> bool:
    return (
        isinstance(value, str)
        and HcpClientsafeidpattern.fullmatch(value) is not None
        and value not in {".", ".."}
        and not value.endswith((".", " "))
        and HcpClientwindowsreservednamepattern.fullmatch(value) is None
    )


def HcpClientisstrictsemver(value: object) -> bool:
    return isinstance(value, str) and HcpClientsemverpattern.fullmatch(value) is not None


def HcpClientvalidatestringarray(
    value: object,
    field: str,
    errors: list[str],
    *,
    item_name: str = "name",
) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{field} must be an array of names")
        return []

    names: list[str] = []
    seen: set[str] = set()
    for name in value:
        if not name:
            errors.append(f"{field} must not contain an empty {item_name}")
            continue
        if name in seen:
            errors.append(f"{field} contains duplicate {item_name} {name}")
            continue
        seen.add(name)
        names.append(name)
    return names


def HcpClientmasktypescript(text: str, *, strings: bool) -> str:
    """Mask comments and optionally strings while preserving offsets/newlines."""
    output = list(text)
    index = 0
    state = "code"
    quote = ""
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and next_char == "/":
                output[index] = output[index + 1] = " "
                index += 2
                state = "line-comment"
                continue
            if char == "/" and next_char == "*":
                output[index] = output[index + 1] = " "
                index += 2
                state = "block-comment"
                continue
            if char in {'"', "'", "`"}:
                quote = char
                if strings:
                    output[index] = " "
                index += 1
                state = "string"
                continue
        elif state == "line-comment":
            if char == "\n":
                state = "code"
            else:
                output[index] = " "
            index += 1
            continue
        elif state == "block-comment":
            if char == "*" and next_char == "/":
                output[index] = output[index + 1] = " "
                index += 2
                state = "code"
                continue
            if char != "\n":
                output[index] = " "
            index += 1
            continue
        elif state == "string":
            if strings and char != "\n":
                output[index] = " "
            if char == "\\":
                if index + 1 < len(text):
                    if strings and text[index + 1] != "\n":
                        output[index + 1] = " "
                    index += 2
                    continue
            elif char == quote:
                state = "code"
                quote = ""
            index += 1
            continue
        index += 1
    return "".join(output)


def HcpClienttypescriptclassmembers(
    text: str,
    class_name: str,
) -> tuple[bool, list[tuple[str, bool]], list[str], str]:
    comments_removed = HcpClientmasktypescript(text, strings=False)
    structural = HcpClientmasktypescript(text, strings=True)
    bare_pattern = re.compile(rf"\bexport\s+class\s+{re.escape(class_name)}\s*\{{")
    matches = list(bare_pattern.finditer(structural))
    invalid_structure = (
        len(matches) != 1
        or len(re.findall(r"\bclass\s+[A-Za-z_$][\w$]*", structural)) != 1
        or re.search(r"\b(?:interface|implements|extends)\b", structural) is not None
    )
    if len(matches) != 1:
        return False, [], [], structural

    body_start = structural.find("{", matches[0].start())
    depth = 1
    members: list[tuple[str, bool]] = []
    top_level_lines: list[str] = []
    offset = body_start + 1
    for structural_line in structural[offset:].splitlines(keepends=True):
        original_line = comments_removed[offset : offset + len(structural_line)]
        if depth == 1:
            top_level_lines.append(original_line)
        depth += structural_line.count("{") - structural_line.count("}")
        offset += len(structural_line)
        if depth == 0:
            break
    if depth != 0:
        invalid_structure = True

    method_pattern = re.compile(
        r"\s*(?:(?:public|private|protected|override|abstract|declare)\s+)*"
        r"(?:(static)\s+)?(?:async\s+)?([A-Za-z_$][\w$]*)\s*(?:<[^>{}]*>)?\s*\(",
    )
    depth = 1
    index = body_start + 1
    while index < len(structural) and depth > 0:
        if depth == 1:
            method_match = method_pattern.match(structural, index)
            if method_match:
                members.append((method_match.group(2), method_match.group(1) is not None))
                index = method_match.end()
                continue
        if structural[index] == "{":
            depth += 1
        elif structural[index] == "}":
            depth -= 1
        index += 1
    return not invalid_structure, members, top_level_lines, structural


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def git_visible_files() -> list[Path]:
    """Return existing tracked and unignored untracked files.

    The content checks below read each file's bytes, so index entries whose
    working-tree file was deleted but not yet staged are filtered out here
    rather than crashing every downstream reader. Deleting a file a package
    still declares is caught separately by check_packages' component-path check.
    """
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

    return [
        path
        for line in result.stdout.splitlines()
        if line and (path := ROOT / line).exists()
    ]


def check_repo_hygiene(files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.is_symlink():
            errors.append(f"{rel(path)} is a symlink; package releases must contain regular files only")
            continue
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
    schema_version: str,
    errors: list[str],
    *,
    package_version: str | None = None,
) -> None:
    kind = component.get("kind")
    name = component.get("name")
    path_value = component.get("path")
    is_v2 = schema_version == "magenta.package.v2"

    if not isinstance(kind, str) or not kind:
        errors.append(f"{package_id}: component missing kind")
    if not isinstance(name, str) or not name:
        errors.append(f"{package_id}: component missing name")
    elif is_v2 and not HcpClientisportablepackageid(name):
        errors.append(f"{package_id}:{name}: v2 component name must be a portable identifier")
    if not isinstance(path_value, str) or not path_value:
        errors.append(f"{package_id}:{name}: component missing path")
        return

    component_path = package_root / path_value
    try:
        component_path.resolve().relative_to(package_root.resolve())
    except ValueError:
        errors.append(f"{package_id}:{name}: component path escapes package root: {path_value}")
        return
    if not component_path.exists():
        errors.append(f"{package_id}:{name}: missing path {path_value}")
        return

    component_profiles = HcpClientvalidatestringarray(
        component.get("profiles", []),
        f"{package_id}:{name}: component profiles",
        errors,
    )
    for profile in component_profiles:
        if profile not in profile_names:
            errors.append(f"{package_id}:{name}: unknown profile {profile}")

    # v2 (HCP-isomorphic) module/source components: <module>/<source>/ dir must
    # carry a real HcpMagnet.ts beside its descriptor/content, and the component
    # must declare its source.
    if is_v2 and kind not in HcpClientmodulesourcekinds | HcpClientinfrastructurekinds:
        errors.append(f"{package_id}:{name}: unsupported v2 component kind {kind!r}")
        return

    if is_v2 and kind in HcpClientmodulesourcekinds:
        source = component.get("source")
        if not isinstance(source, str) or not source:
            errors.append(f"{package_id}:{name}: v2 component missing source")
        elif not HcpClientisportablepackageid(source):
            errors.append(f"{package_id}:{name}: v2 component source must be a portable identifier")
        elif component_path.name != source:
            errors.append(
                f"{package_id}:{name}: source directory {component_path.name!r} must match source {source!r}"
            )
        if not component_path.is_dir():
            errors.append(f"{package_id}:{name}: v2 component path must be a <module>/<source> directory")
            return
        if not (component_path / "HcpMagnet.ts").is_file():
            errors.append(f"{package_id}:{name}: v2 component lacks HcpMagnet.ts")
        else:
            HcpClientvalidatepackagemagnet(
                package_root,
                package_id,
                str(name),
                str(kind),
                str(source),
                component_path,
                errors,
            )

        module_path = component_path.parent
        server_path = module_path / "HcpServer.ts"
        if not server_path.is_file():
            errors.append(
                f"{package_id}:{name}: module {module_path.relative_to(package_root).as_posix()} lacks HcpServer.ts"
            )
        else:
            HcpClientvalidatepackageserver(package_root, package_id, str(name), server_path, errors)
        if kind == "skill" and not (component_path / "SKILL.md").is_file():
            errors.append(f"{package_id}:{name}: skill source lacks SKILL.md")
        if kind == "brand" and not (component_path / "brand.toml").is_file():
            errors.append(f"{package_id}:{name}: brand source lacks brand.toml")
        elif kind == "brand":
            try:
                descriptor = load_toml(component_path / "brand.toml")
            except tomllib.TOMLDecodeError:
                descriptor = {}
            config_path = descriptor.get("config_path")
            if isinstance(config_path, str):
                resolved_config = (component_path / config_path).resolve()
                try:
                    resolved_config.relative_to(package_root.resolve())
                except ValueError:
                    errors.append(f"{package_id}:{name}: brand config_path escapes package root")
                else:
                    if not resolved_config.is_file():
                        errors.append(f"{package_id}:{name}: missing brand config_path {config_path}")
                    elif resolved_config.suffix == ".ts":
                        config_text = HcpClientmasktypescript(
                            resolved_config.read_text(encoding="utf-8"),
                            strings=False,
                        )
                        version_match = re.search(
                            r"\bversion\s*:\s*['\"]([^'\"]+)['\"]",
                            config_text,
                        )
                        if version_match is None and package_version is not None:
                            errors.append(f"{package_id}:{name}: brand config must declare package version {package_version!r}")
                        elif version_match and package_version is not None and version_match.group(1) != package_version:
                            errors.append(
                                f"{package_id}:{name}: brand config version {version_match.group(1)!r} "
                                f"must match package version {package_version!r}"
                            )
        if kind == "tool":
            tomls = [p for p in component_path.glob("*.toml")]
            if not tomls:
                errors.append(f"{package_id}:{name}: tool source lacks a descriptor .toml")
            elif len(tomls) > 1:
                errors.append(f"{package_id}:{name}: tool source has multiple descriptor .toml files")
            else:
                HcpClientvalidatepackagetooldescriptor(package_root, package_id, str(name), tomls[0], errors)
        if kind in {"system-prompt", "append-system-prompt"}:
            prompt_descriptor = component_path / "system-prompt.toml"
            if not prompt_descriptor.is_file():
                errors.append(f"{package_id}:{name}: system-prompt source lacks system-prompt.toml")
            else:
                try:
                    descriptor = load_toml(prompt_descriptor)
                except tomllib.TOMLDecodeError:
                    descriptor = {}
                content_path = descriptor.get("content_path")
                if not isinstance(content_path, str) or not content_path:
                    errors.append(f"{package_id}:{name}: system-prompt descriptor lacks content_path")
                else:
                    resolved_content = (component_path / content_path).resolve()
                    try:
                        resolved_content.relative_to(package_root.resolve())
                    except ValueError:
                        errors.append(f"{package_id}:{name}: system-prompt content_path escapes package root")
                    else:
                        if not resolved_content.is_file():
                            errors.append(f"{package_id}:{name}: missing system-prompt content {content_path}")
        return

    # v1 (flat) legacy validation, kept while other packages migrate.
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


def HcpClientvalidatepackagemagnet(
    package_root: Path,
    package_id: str,
    component_name: str,
    kind: str,
    source: str,
    component_path: Path,
    errors: list[str],
) -> None:
    magnet_path = component_path / "HcpMagnet.ts"
    text = magnet_path.read_text(encoding="utf-8")
    expected_module = component_path.parent.relative_to(package_root).as_posix()
    bare, members, top_level_lines, structural = HcpClienttypescriptclassmembers(text, "HcpMagnet")
    if not bare:
        errors.append(
            f"{package_id}:{component_name}: HcpMagnet.ts must contain one bare export class HcpMagnet"
        )

    top_level = "".join(top_level_lines)
    required_literals = {
        "module": expected_module,
        "kind": kind,
        "source": source,
    }
    for field, value in required_literals.items():
        pattern = re.compile(
            rf"^\s*static\s+readonly\s+{field}\s*=\s*['\"]{re.escape(value)}['\"]\s*;\s*$",
            re.MULTILINE,
        )
        if pattern.search(top_level) is None:
            errors.append(f"{package_id}:{component_name}: HcpMagnet has invalid {field} shape")

    static_builds = [name for name, is_static in members if name == "build" and is_static]
    if len(static_builds) != 1:
        errors.append(f"{package_id}:{component_name}: HcpMagnet must define one static build()")

    product_members = [name for name, _ in members if name in HcpClientproductmethods]
    expected_product = "toTool" if kind == "tool" else "toResource"
    if product_members != [expected_product]:
        errors.append(
            f"{package_id}:{component_name}: HcpMagnet must define exactly {expected_product}(); "
            f"found {product_members or ['none']}"
        )

    if kind in {"system-prompt", "brand"} and re.search(
        r"\b(?:contentPath|content)\s*:", structural
    ) is None:
        errors.append(
            f"{package_id}:{component_name}: {kind} Resource must expose contentPath/content"
        )


def HcpClientvalidatepackageserver(
    package_root: Path,
    package_id: str,
    component_name: str,
    server_path: Path,
    errors: list[str],
) -> None:
    text = server_path.read_text(encoding="utf-8")
    expected_module = server_path.parent.relative_to(package_root).as_posix()
    bare, _members, top_level_lines, _structural = HcpClienttypescriptclassmembers(text, "HcpServer")
    if not bare:
        errors.append(f"{package_id}:{component_name}: HcpServer.ts must export bare class HcpServer")
    if re.search(
        rf"^\s*readonly\s+moduleName\s*=\s*['\"]{re.escape(expected_module)}['\"]\s*;\s*$",
        "".join(top_level_lines),
        re.MULTILINE,
    ) is None:
        errors.append(
            f"{package_id}:{component_name}: HcpServer moduleName must be {expected_module!r}"
        )


def HcpClientvalidatepackagetooldescriptor(
    package_root: Path,
    package_id: str,
    component_name: str,
    descriptor_path: Path,
    errors: list[str],
) -> None:
    try:
        descriptor = load_toml(descriptor_path)
    except tomllib.TOMLDecodeError:
        return  # check_toml reports the precise parse error.
    for field in (
        "command",
        "command_windows",
        "command_macos",
        "command_linux",
        "commandWindows",
        "commandMacos",
        "commandLinux",
    ):
        command = descriptor.get(field)
        if command is None:
            continue
        if not isinstance(command, str) or not command:
            errors.append(f"{package_id}:{component_name}: {field} must be a non-empty string")
            continue
        if not ("/" in command or "\\" in command):
            continue
        if Path(command).is_absolute() or PureWindowsPath(command).is_absolute():
            errors.append(f"{package_id}:{component_name}: {field} must be package-local: {command}")
            continue
        command_path = (descriptor_path.parent / command.replace("\\", "/")).resolve()
        try:
            command_path.relative_to(package_root.resolve())
        except ValueError:
            errors.append(
                f"{package_id}:{component_name}: {field} escapes package root: {command}"
            )


def check_packages(errors: list[str], only_package: str | None = None) -> None:
    package_files = sorted(
        path for path in ROOT.glob("*/package.toml") if path.parent.is_dir()
    )
    if only_package is not None:
        package_files = [p for p in package_files if p.parent.name == only_package]
        if not package_files:
            errors.append(f"package {only_package} not found")
            return
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
        if not HcpClientisportablepackageid(package_id):
            errors.append(f"{rel(package_file)} id must be one portable path segment")
        if package_id in package_ids:
            errors.append(f"duplicate package id {package_id}")
        if isinstance(package_id, str):
            package_ids.add(package_id)
        else:
            package_id = package_root.name

        schema_version = manifest.get("schema_version")
        if schema_version not in {"magenta.package.v1", "magenta.package.v2"}:
            errors.append(f"{package_id}: unsupported schema_version")
        schema_version = schema_version if isinstance(schema_version, str) else ""

        # v2 packages must declare a version (release tags derive from it).
        if schema_version == "magenta.package.v2":
            version = manifest.get("version")
            if not HcpClientisstrictsemver(version):
                errors.append(f"{package_id}: v2 package must declare a strict semantic version")
            for field in ("name", "source"):
                if not isinstance(manifest.get(field), str) or not manifest[field]:
                    errors.append(f"{package_id}: v2 package must declare a non-empty {field}")
                elif not HcpClientisportablepackageid(manifest[field]):
                    errors.append(f"{package_id}: v2 package {field} must be a portable identifier")

        profiles = manifest.get("profiles", [])
        if not isinstance(profiles, list):
            errors.append(f"{package_id}: profiles must be an array of tables")
            profiles = []
        profile_names: set[str] = set()
        for profile in profiles:
            if not isinstance(profile, dict):
                errors.append(f"{package_id}: profile entry is not a table")
                continue
            profile_name = profile.get("name")
            if not isinstance(profile_name, str) or not profile_name:
                errors.append(f"{package_id}: profile name must be a non-empty string")
                continue
            if not HcpClientisportablepackageid(profile_name):
                errors.append(f"{package_id}: profile name must be a portable identifier: {profile_name}")
            if profile_name in profile_names:
                errors.append(f"{package_id}: duplicate profile {profile_name}")
            profile_names.add(profile_name)
            HcpClientvalidatestringarray(
                profile.get("extends", []),
                f"{package_id}: profile {profile_name} extends",
                errors,
                item_name="parent",
            )
        for profile in profiles:
            if not isinstance(profile, dict) or not isinstance(profile.get("name"), str):
                continue
            for parent in HcpClientvalidatestringarray(
                profile.get("extends", []),
                f"{package_id}: profile {profile['name']} extends",
                [],
                item_name="parent",
            ):
                if parent not in profile_names:
                    errors.append(f"{package_id}: profile extends unknown {parent}")
        HcpClientcheckpackageprofilecycles(str(package_id), profiles, errors)
        default_profiles = HcpClientvalidatestringarray(
            manifest.get("default_profiles", []),
            f"{package_id}: default_profiles",
            errors,
        )
        for default_profile in default_profiles:
            if default_profile not in profile_names:
                errors.append(f"{package_id}: default profile {default_profile} is unknown")

        seen_components: set[tuple[str, str, str | None]] = set()
        components = manifest.get("components", [])
        if not isinstance(components, list) or not components:
            errors.append(f"{package_id}: no components declared")
            continue
        for component in components:
            if not isinstance(component, dict):
                errors.append(f"{package_id}: component entry is not a table")
                continue
            source = component.get("source") if schema_version == "magenta.package.v2" else None
            key = (
                str(component.get("kind")),
                str(component.get("name")),
                str(source) if source is not None else None,
            )
            if key in seen_components:
                suffix = f":{key[2]}" if key[2] is not None else ""
                errors.append(f"{package_id}: duplicate component {key[0]}:{key[1]}{suffix}")
            seen_components.add(key)
            validate_component(
                package_root,
                str(package_id),
                component,
                profile_names,
                schema_version,
                errors,
                package_version=manifest.get("version") if isinstance(manifest.get("version"), str) else None,
            )


def HcpClientcheckpackageprofilecycles(
    package_id: str,
    profiles: list[Any],
    errors: list[str],
) -> None:
    parents: dict[str, list[str]] = {}
    for profile in profiles:
        if not isinstance(profile, dict) or not isinstance(profile.get("name"), str):
            continue
        extends = profile.get("extends", [])
        if not isinstance(extends, list) or not all(isinstance(item, str) for item in extends):
            errors.append(f"{package_id}: profile {profile['name']} extends must be an array of names")
            continue
        parents[profile["name"]] = extends

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, chain: list[str]) -> None:
        if name in visited:
            return
        if name in visiting:
            start = chain.index(name) if name in chain else 0
            errors.append(
                f"{package_id}: profile inheritance cycle {' -> '.join(chain[start:] + [name])}"
            )
            return
        visiting.add(name)
        for parent in parents.get(name, []):
            if parent in parents:
                visit(parent, [*chain, name])
        visiting.remove(name)
        visited.add(name)

    for profile_name in parents:
        visit(profile_name, [])


def main() -> int:
    only_package: str | None = None
    args = sys.argv[1:]
    if args and args[0] == "--package":
        if len(args) < 2:
            print("--package requires a package name", file=sys.stderr)
            return 2
        only_package = args[1]

    errors: list[str] = []
    files = git_visible_files()
    check_repo_hygiene(files, errors)
    check_toml(files, errors)
    check_python_syntax(files, errors)
    check_packages(errors, only_package)

    if errors:
        print("Package validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if only_package is not None:
        print(f"Validated package {only_package}.")
        return 0

    package_count = len(list(ROOT.glob("*/package.toml")))
    skill_count = len(list(ROOT.glob("*/skills/**/SKILL.md")))
    print(f"Validated {package_count} packages and {skill_count} skill entrypoints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
