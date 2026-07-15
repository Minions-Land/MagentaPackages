"""
Evidence record shaping for omics analysis.

Converts a helper/analysis report dict into the exact trailing-JSON row
that a host analyst harness can harvest into an EvidenceRecord.

Current status (verified against Magenta core): the host runs each omics_compute
subcommand as a process and returns its stdout verbatim to the agent (see
ProcessToolMagnet — "read stdout as the tool result"). There is no
evidence-harvesting step yet; the agent reads the printed report dict directly
with its own reasoning. These helpers therefore define the canonical evidence-row
format for a *future* host harvester — subcommands currently print their report
dict as-is. Treat the lack of callers as an as-yet-unconnected contract (like the
assumed host tools), not dead code.

Functions:
- shape_row(): Canonicalize report dict into evidence JSON structure
- emit(): Returns JSON string for print() as cell's last line

Constants:
- EVIDENCE_KIND: "computation"
- SCHEMA_VERSION: 1
"""

import json
import math
from datetime import datetime, timezone
from typing import Any


def _find_non_finite(obj: Any, path: str = "") -> str | None:
    """Dotted path of the first NaN/Inf float in a nested report, else None."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return path or "<root>"
    if isinstance(obj, dict):
        for key, value in obj.items():
            found = _find_non_finite(value, f"{path}.{key}" if path else str(key))
            if found:
                return found
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            found = _find_non_finite(value, f"{path}[{i}]")
            if found:
                return found
    return None


# Constants (single source of truth for evidence format)
EVIDENCE_KIND = "computation"
SCHEMA_VERSION = 1


def shape_row(
    report: dict[str, Any],
    *,
    analysis: str,
    identifier: str,
    summary: str | None = None,
) -> dict[str, Any]:
    """
    Shape a report dict into an evidence record structure.

    The Rust side harvests this JSON from the cell's trailing output
    and converts it into an EvidenceRecord::from_computation + TraceStep
    appended to runs/omics/<id>/evidence.jsonl.

    Parameters
    ----------
    report : dict
        The computation output (parameters, results, metrics)
    analysis : str
        Analysis type (e.g., "preprocess", "cluster", "rank_genes")
    identifier : str
        Unique identifier (e.g., run_id, step_name)
    summary : str, optional
        Human-readable summary (if not provided, derived from analysis)

    Returns
    -------
    dict
        Evidence record structure ready for JSON serialization

    Raises
    ------
    ValueError
        If report is not JSON-serializable, or analysis/identifier are empty
    """
    if not isinstance(report, dict):
        raise ValueError(f"report must be a dict, got {type(report)}")

    if not analysis or not analysis.strip():
        raise ValueError("analysis must be a non-empty string")

    if not identifier or not identifier.strip():
        raise ValueError("identifier must be a non-empty string")

    # Test strict JSON serializability (allow_nan=False rejects NaN/Infinity, which
    # a spec-strict consumer — Rust serde_json / JS JSON.parse — cannot read).
    try:
        json.dumps(report, allow_nan=False)
    except (TypeError, ValueError) as e:
        field = _find_non_finite(report)
        where = f" at field '{field}'" if field else ""
        raise ValueError(f"report must be strict-JSON-serializable (no NaN/Inf){where}: {e}")

    # Generate summary if not provided
    if summary is None:
        summary = f"{analysis} [{identifier}]"

    # Build evidence row
    row = {
        "schema": SCHEMA_VERSION,
        "kind": EVIDENCE_KIND,
        "analysis": analysis.strip(),
        "identifier": identifier.strip(),
        "summary": summary,
        "report": report,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return row


def emit(
    report: dict[str, Any],
    *,
    analysis: str,
    identifier: str,
    summary: str | None = None,
) -> str:
    """
    Convert report dict to JSON string for printing as cell's last line.

    Usage in notebook cell:
    ```python
    # ... run computation ...
    report = {"n_clusters": 12, "resolution": 1.0, "n_obs": 5000}
    print(emit(report, analysis="cluster", identifier="leiden_r1.0"))
    ```

    The Rust analyst tool will parse this JSON and create an EvidenceRecord.

    Parameters
    ----------
    report : dict
        The computation output
    analysis : str
        Analysis type
    identifier : str
        Unique identifier
    summary : str, optional
        Human-readable summary

    Returns
    -------
    str
        JSON string ready to print()
    """
    row = shape_row(report, analysis=analysis, identifier=identifier, summary=summary)
    return json.dumps(row, ensure_ascii=False, allow_nan=False)


def emit_compact(
    report: dict[str, Any],
    *,
    analysis: str,
    identifier: str,
    summary: str | None = None,
) -> str:
    """
    Like emit(), but with compact JSON (no extra whitespace).

    Useful for large reports to reduce output size.
    """
    row = shape_row(report, analysis=analysis, identifier=identifier, summary=summary)
    return json.dumps(row, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
