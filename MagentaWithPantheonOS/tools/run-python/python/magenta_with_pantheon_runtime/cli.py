"""Shared JSON output helpers for runtime CLI modules."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any


def emit(call: Callable[[], dict[str, object]], *, execution_contract: bool = False) -> None:
    try:
        result = call()
    except Exception as error:
        if execution_contract:
            result = {"stdout": "", "stderr": f"{type(error).__name__}: {error}\n", "exitCode": 2}
        else:
            result = {"success": False, "error": f"{type(error).__name__}: {error}"}
    json.dump(result, sys.stdout, ensure_ascii=True, separators=(",", ":"))
    sys.stdout.write("\n")
