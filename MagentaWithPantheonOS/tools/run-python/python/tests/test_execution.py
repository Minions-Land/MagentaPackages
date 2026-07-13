from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from magenta_with_pantheon_runtime.execution import _python_command, run_python


def test_run_python_captures_streams_and_exit_code() -> None:
    result = run_python("import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)")
    assert result == {"stdout": "out\n", "stderr": "err\n", "exitCode": 7}


def test_run_python_uses_a_fresh_subprocess_every_time() -> None:
    first = run_python("global_value = 41; print(global_value)")
    second = run_python("print('global_value' in globals())")
    assert first["stdout"] == "41\n"
    assert second["stdout"] == "False\n"
    assert first["exitCode"] == second["exitCode"] == 0


def test_run_python_timeout_is_reported_in_contract() -> None:
    result = run_python("import time; time.sleep(1)", timeout_ms=20)
    assert result["exitCode"] == -1
    assert result["stderr"] == "[Process killed: timeout after 20ms]\n"


def test_run_python_timeout_kills_descendant_processes(tmp_path: Path) -> None:
    marker = tmp_path / "descendant-survived"
    child_code = (
        "import pathlib, sys, time; "
        "time.sleep(0.8); pathlib.Path(sys.argv[1]).write_text('alive', encoding='utf-8')"
    )
    parent_code = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}, {str(marker)!r}]); "
        "print('spawned', flush=True); time.sleep(30)"
    )
    result = run_python(parent_code, timeout_ms=300)
    assert result["exitCode"] == -1
    assert result["stdout"] == "spawned\n"
    time.sleep(1.0)
    assert not marker.exists()


def test_environment_is_a_controlled_project_pixi_selector(tmp_path: Path) -> None:
    assert _python_command("default") == [sys.executable]
    (tmp_path / "pixi.toml").write_text(
        '[workspace]\nname="fixture"\nchannels=["conda-forge"]\nplatforms=["linux-64"]\n'
        '[environments]\ntask1 = { solve-group = "omics" }\n'
        'task2 = { solve-group = "omics" }\n'
        'task3 = { solve-group = "omics" }\n'
        'task4 = { solve-group = "omics" }\n',
        encoding="utf-8",
    )
    (tmp_path / "pixi.lock").write_text("version = 6\nenvironments = {}\npackages = []\n", encoding="utf-8")
    task_command = _python_command("task1", workspace=tmp_path)
    aliases = {
        "sc-rna": "task1",
        "spatial": "task2",
        "sc-multiome": "task3",
        "sc-atac": "task4",
    }
    alias_commands = {
        selector: _python_command(selector, workspace=tmp_path)
        for selector in aliases
    }
    assert task_command[:2] == ["pixi", "run"]
    assert "--frozen" in task_command
    assert task_command[-2:] == ["--executable", "python"]
    for selector, resolved in aliases.items():
        command = alias_commands[selector]
        assert command[command.index("--environment") + 1] == resolved
    with pytest.raises(ValueError, match="unknown project Pixi environment"):
        _python_command("arbitrary-env", workspace=tmp_path)


def test_named_environment_requires_project_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a project pixi.toml"):
        _python_command("task1", workspace=tmp_path)
