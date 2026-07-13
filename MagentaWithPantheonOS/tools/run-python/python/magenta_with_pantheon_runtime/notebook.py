"""Small, concurrency-safe nbformat 4.5 notebook editor."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import nbformat
from nbformat import NotebookNode

_VALID_CELL_TYPES = {"code", "markdown", "raw"}
_LOCK_TIMEOUT_SECONDS = 15.0


def _notebook_path(file_path: str) -> Path:
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("filePath must be a non-empty string")
    path = Path(file_path).expanduser()
    if path.suffix.lower() != ".ipynb":
        raise ValueError("filePath must end in .ipynb")
    return path.absolute()


def _try_os_lock(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_os_lock(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_UN)


@contextlib.contextmanager
def _adjacent_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
    locked = False
    try:
        while not locked:
            try:
                _try_os_lock(descriptor)
                locked = True
            except OSError as error:
                if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out waiting for notebook lock: {lock_path}") from error
                time.sleep(0.05)
        yield
    finally:
        if locked:
            _release_os_lock(descriptor)
        os.close(descriptor)


def _atomic_write(path: Path, notebook: NotebookNode, *, create_only: bool) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing to write notebook symlink: {path}")
    if create_only and path.exists():
        raise FileExistsError(f"notebook already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise ValueError(f"refusing to write through a symlinked parent: {path.parent}")

    notebook["nbformat"] = 4
    notebook["nbformat_minor"] = 5
    nbformat.validate(notebook, version=4)
    payload = nbformat.writes(notebook, version=4)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink() or (create_only and path.exists()):
            raise FileExistsError(f"notebook already exists or became a symlink: {path}")
        if create_only:
            try:
                os.link(temporary_path, path)
            except FileExistsError as error:
                raise FileExistsError(f"notebook already exists: {path}") from error
            temporary_path.unlink()
        else:
            os.replace(temporary_path, path)
        temporary_path = None
        try:
            parent_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        except OSError:
            pass
    finally:
        if temporary_path is not None:
            with contextlib.suppress(FileNotFoundError):
                temporary_path.unlink()


def _kernel_metadata(kernel: str | None) -> tuple[dict[str, str], dict[str, str]]:
    name = (kernel or "python3").strip()
    if not name:
        raise ValueError("kernel must not be empty")
    lowered = name.lower()
    if lowered in {"ir", "r"}:
        return (
            {"display_name": "R", "language": "R", "name": "ir"},
            {"name": "R", "file_extension": ".r", "mimetype": "text/x-r-source"},
        )
    if lowered.startswith("julia"):
        return (
            {"display_name": name, "language": "julia", "name": name},
            {"name": "julia", "file_extension": ".jl", "mimetype": "text/x-julia"},
        )
    return (
        {"display_name": "Python 3" if lowered == "python3" else name, "language": "python", "name": name},
        {"name": "python", "file_extension": ".py", "mimetype": "text/x-python"},
    )


def create_notebook(file_path: str, kernel: str | None = None, title: str | None = None) -> dict[str, object]:
    path = _notebook_path(file_path)
    if title is not None and not isinstance(title, str):
        raise ValueError("title must be a string")
    kernelspec, language_info = _kernel_metadata(kernel)
    metadata: dict[str, object] = {"kernelspec": kernelspec, "language_info": language_info}
    cells: list[NotebookNode] = []
    if title is not None:
        metadata["title"] = title
    if title:
        source = f"# {title}"
        cells.append(
            nbformat.v4.new_markdown_cell(
                source=source,
                id=_stable_cell_id("markdown", source, cells),
            )
        )
    notebook = nbformat.v4.new_notebook(cells=cells, metadata=metadata)
    notebook["nbformat_minor"] = 5

    path.parent.mkdir(parents=True, exist_ok=True)
    with _adjacent_lock(path):
        _atomic_write(path, notebook, create_only=True)
    return {
        "created": str(path),
        "kernel": kernelspec["name"],
        "success": True,
        "filePath": str(path),
        "nbformat": 4,
        "nbformatMinor": 5,
        "cellCount": len(cells),
    }


def _stable_cell_id(cell_type: str, source: str, cells: list[NotebookNode]) -> str:
    existing = {cell.get("id") for cell in cells}
    ordinal = len(cells)
    attempt = 0
    while True:
        material = f"{cell_type}\0{source}\0{ordinal}\0{attempt}".encode("utf-8")
        candidate = hashlib.sha256(material).hexdigest()[:16]
        if candidate not in existing:
            return candidate
        attempt += 1


def _ensure_existing_ids(cells: list[NotebookNode]) -> None:
    seen: set[str] = set()
    for index, cell in enumerate(cells):
        cell_id = cell.get("id")
        if not isinstance(cell_id, str) or not cell_id or cell_id in seen:
            source = cell.get("source", "")
            if isinstance(source, list):
                source = "".join(str(line) for line in source)
            attempt = 0
            while True:
                material = f"existing\0{index}\0{cell.get('cell_type')}\0{source}\0{attempt}".encode("utf-8")
                cell_id = hashlib.sha256(material).hexdigest()[:16]
                if cell_id not in seen:
                    cell["id"] = cell_id
                    break
                attempt += 1
        seen.add(cell_id)


def _insert_index(cells: list[NotebookNode], position: int | str | None) -> int:
    if position is None:
        return len(cells)
    if isinstance(position, bool):
        raise ValueError("position must be an integer index or existing cell id")
    if isinstance(position, int) or (isinstance(position, str) and position.lstrip("-").isdigit()):
        index = int(position)
        if index < 0:
            index = len(cells) + index + 1
        if not 0 <= index <= len(cells):
            raise ValueError(f"position index must resolve between 0 and {len(cells)}")
        return index
    if isinstance(position, str):
        for index, cell in enumerate(cells):
            if cell.get("id") == position:
                return index + 1
        raise ValueError(f"position cell id not found: {position}")
    raise ValueError("position must be an integer index or existing cell id")


def add_cell(
    file_path: str,
    source: str,
    cell_type: str = "code",
    position: int | str | None = None,
) -> dict[str, object]:
    path = _notebook_path(file_path)
    if path.is_symlink():
        raise ValueError(f"refusing to edit notebook symlink: {path}")
    if cell_type not in _VALID_CELL_TYPES:
        raise ValueError("cellType must be one of: code, markdown, raw")
    if not isinstance(source, str):
        raise ValueError("source must be a string")

    with _adjacent_lock(path):
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"notebook does not exist or is not a regular file: {path}")
        with path.open("r", encoding="utf-8") as handle:
            notebook = nbformat.read(handle, as_version=4)
        cells = notebook.cells
        _ensure_existing_ids(cells)
        cell_id = _stable_cell_id(cell_type, source, cells)
        if cell_type == "code":
            cell = nbformat.v4.new_code_cell(source=source, id=cell_id)
        elif cell_type == "markdown":
            cell = nbformat.v4.new_markdown_cell(source=source, id=cell_id)
        else:
            cell = nbformat.v4.new_raw_cell(source=source, id=cell_id)
        index = _insert_index(cells, position)
        cells.insert(index, cell)
        _atomic_write(path, notebook, create_only=False)

    return {
        "cellIndex": index,
        "totalCells": len(cells),
        "success": True,
        "filePath": str(path),
        "cellId": cell_id,
        "cellType": cell_type,
        "position": index,
        "cellCount": len(cells),
    }
