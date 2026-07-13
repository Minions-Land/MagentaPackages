"""One-shot Python execution in the package or a selected project Pixi env."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import tomllib
from pathlib import Path

_DEFAULT_TIMEOUT_MS = 60_000
_MAX_TIMEOUT_MS = 300_000
_SAFE_ENVIRONMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_ENVIRONMENT_ALIASES = {
    "sc-rna": "task1",
    "spatial": "task2",
    "sc-multiome": "task3",
    "sc-atac": "task4",
}


def _find_project_manifest(workspace: Path) -> Path:
    manifest = workspace / "pixi.toml"
    if manifest.is_file():
        return manifest
    raise ValueError(f"named env requires a project pixi.toml at workspace root {workspace}")


def _project_python_command(environment: str, workspace: Path | None = None) -> list[str]:
    if _SAFE_ENVIRONMENT.fullmatch(environment) is None:
        raise ValueError(f"invalid Pixi environment selector: {environment!r}")
    manifest = _find_project_manifest((workspace or Path.cwd()).resolve())
    lock = manifest.with_name("pixi.lock")
    if not lock.is_file():
        raise ValueError(f"named env requires a locked project Pixi workspace; missing {lock}")
    try:
        with manifest.open("rb") as handle:
            document = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"unable to read project Pixi manifest {manifest}: {error}") from error
    environments = document.get("environments", {})
    if not isinstance(environments, dict):
        raise ValueError(f"project Pixi manifest has no valid [environments] table: {manifest}")
    resolved = environment if environment in environments else _ENVIRONMENT_ALIASES.get(environment, environment)
    if resolved not in environments:
        choices = ", ".join(sorted(str(name) for name in environments)) or "none"
        raise ValueError(
            f"unknown project Pixi environment {environment!r} in {manifest}; available environments: {choices}"
        )
    return [
        "pixi",
        "run",
        "--manifest-path",
        str(manifest),
        "--frozen",
        "--environment",
        resolved,
        "--executable",
        "python",
    ]


def _python_command(environment: str, workspace: Path | None = None) -> list[str]:
    if environment == "default":
        # The host already launched this wrapper in the package's locked default env.
        return [sys.executable]
    return _project_python_command(environment, workspace)


def _start_process(command: list[str]) -> subprocess.Popen[str]:
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )


def _kill_process_tree(process: subprocess.Popen[str]) -> tuple[str, str]:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            process.kill()
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return process.communicate()


def run_python(code: str, env: str | None = None, timeout_ms: int | None = None) -> dict[str, object]:
    """Execute *code* in a new subprocess in the requested Pixi environment."""
    if not isinstance(code, str):
        raise ValueError("code must be a string")
    environment = "default" if env is None else env
    if not isinstance(environment, str) or not environment:
        raise ValueError("env must be a non-empty Pixi environment name")
    timeout = _DEFAULT_TIMEOUT_MS if timeout_ms is None else timeout_ms
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= _MAX_TIMEOUT_MS:
        raise ValueError(f"timeoutMs must be an integer from 1 to {_MAX_TIMEOUT_MS}")

    command = [*_python_command(environment), "-c", code]
    try:
        process = _start_process(command)
    except OSError as error:
        return {"stdout": "", "stderr": f"Unable to start Python subprocess: {error}\n", "exitCode": -1}

    try:
        stdout, stderr = process.communicate(timeout=timeout / 1000)
    except subprocess.TimeoutExpired:
        stdout, stderr = _kill_process_tree(process)
        timeout_message = f"[Process killed: timeout after {timeout}ms]"
        separator = "" if not stderr or stderr.endswith("\n") else "\n"
        return {"stdout": stdout, "stderr": f"{stderr}{separator}{timeout_message}\n", "exitCode": -1}
    return {"stdout": stdout, "stderr": stderr, "exitCode": process.returncode}
