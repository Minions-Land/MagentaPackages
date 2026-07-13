from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import nbformat
import pytest

from magenta_with_pantheon_runtime import notebook as notebook_module
from magenta_with_pantheon_runtime.notebook import add_cell, create_notebook


def read_valid(path: Path):
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook, version=4)
    assert notebook.nbformat == 4
    assert notebook.nbformat_minor == 5
    return notebook


def test_create_and_add_cells_produce_valid_nbformat_45(tmp_path: Path) -> None:
    path = tmp_path / "analysis.ipynb"
    created = create_notebook(str(path), kernel="python3", title="Analysis")
    assert created["created"] == str(path)
    assert created["kernel"] == "python3"
    assert created["cellCount"] == 1
    notebook = read_valid(path)
    assert notebook.metadata.title == "Analysis"
    assert notebook.metadata.kernelspec.name == "python3"
    assert notebook.cells[0].cell_type == "markdown"
    assert notebook.cells[0].source == "# Analysis"

    first = add_cell(str(path), "# Heading", cell_type="markdown")
    stable_id = first["cellId"]
    second = add_cell(str(path), "print('ok')", position=0)
    notebook = read_valid(path)
    assert [cell.cell_type for cell in notebook.cells] == ["code", "markdown", "markdown"]
    assert notebook.cells[2].id == stable_id
    assert notebook.cells[0].id == second["cellId"]
    assert second["cellIndex"] == 0
    assert second["totalCells"] == 3
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))
    assert (tmp_path / ".analysis.ipynb.lock").is_file()


def test_cell_ids_are_deterministic_and_stable(tmp_path: Path) -> None:
    paths = [tmp_path / "a.ipynb", tmp_path / "b.ipynb"]
    ids = []
    for path in paths:
        create_notebook(str(path))
        ids.append(add_cell(str(path), "x = 1")["cellId"])
    assert ids[0] == ids[1]
    add_cell(str(paths[0]), "y = 2")
    assert read_valid(paths[0]).cells[0].id == ids[0]


def test_position_can_insert_after_a_cell_id(tmp_path: Path) -> None:
    path = tmp_path / "positions.ipynb"
    create_notebook(str(path))
    first = add_cell(str(path), "first")
    add_cell(str(path), "third")
    middle = add_cell(str(path), "second", position=str(first["cellId"]))
    notebook = read_valid(path)
    assert [cell.source for cell in notebook.cells] == ["first", "second", "third"]
    assert notebook.cells[1].id == middle["cellId"]


def test_create_refuses_overwrite_and_bad_extension(tmp_path: Path) -> None:
    path = tmp_path / "existing.ipynb"
    create_notebook(str(path))
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        create_notebook(str(path))
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match=".ipynb"):
        create_notebook(str(tmp_path / "wrong.json"))


def test_notebook_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.ipynb"
    link = tmp_path / "link.ipynb"
    create_notebook(str(target))
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink"):
        add_cell(str(link), "unsafe")


def test_create_publish_does_not_clobber_external_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "raced.ipynb"
    real_link = os.link

    def racing_link(source, destination):
        Path(destination).write_text("external writer", encoding="utf-8")
        return real_link(source, destination)

    monkeypatch.setattr(notebook_module.os, "link", racing_link)
    with pytest.raises(FileExistsError, match="already exists"):
        create_notebook(str(path))
    assert path.read_text(encoding="utf-8") == "external writer"
    assert not list(tmp_path.glob(".*.tmp"))


def test_concurrent_processes_do_not_lose_notebook_cells(tmp_path: Path) -> None:
    path = tmp_path / "concurrent.ipynb"
    create_notebook(str(path))
    python_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(python_root), environment.get("PYTHONPATH", "")) if part
    )
    script = (
        "import sys; "
        "from magenta_with_pantheon_runtime.notebook import add_cell; "
        "add_cell(sys.argv[1], sys.argv[2])"
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(path), f"value_{index} = {index}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        for index in range(6)
    ]
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, (stdout, stderr)

    notebook = read_valid(path)
    assert len(notebook.cells) == 6
    assert {cell.source for cell in notebook.cells} == {f"value_{index} = {index}" for index in range(6)}
    assert len({cell.id for cell in notebook.cells}) == 6
    assert (tmp_path / ".concurrent.ipynb.lock").is_file()
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))
