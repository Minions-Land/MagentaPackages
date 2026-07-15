"""
Plain-text dataset summary for LLM context.

Provides summarize_adata() which returns a human-readable text description
of an AnnData object's structure and contents, suitable for including in
LLM prompts to provide dataset context.
"""

import re

import numpy as np
import pandas as pd

from .conventions import CATEGORICAL_OBS_KEYS


# Every character Python's splitlines() / text renderers treat as a line break or
# control code: C0, DEL+C1 (incl. NEL \x85), and the Unicode LINE/PARAGRAPH separators.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")


def _safe(value) -> str:
    """Stringify and neutralize control chars so a value cannot inject summary
    lines (this text is fed to LLM prompts)."""
    return _CONTROL_CHARS.sub(" ", str(value))


def summarize_adata(adata, *, top_k: int = 20) -> str:
    """
    Generate a plain-text summary of an AnnData object.

    Returns a string describing:
    - Shape (n_obs × n_vars)
    - Layers present
    - Each obs column with value ranges (numeric) or top-k categories
    - obsm keys present

    This summary is meant to be inserted into LLM prompts to provide
    dataset context for analysis decisions.

    Parameters
    ----------
    adata : AnnData
        The dataset to summarize
    top_k : int, default=20
        Maximum number of categories to show for categorical columns

    Returns
    -------
    str
        Plain text summary
    """
    lines = []

    # Shape
    lines.append(f"Shape: {adata.n_obs} cells × {adata.n_vars} genes")
    lines.append("")

    # Layers
    if adata.layers:
        layer_names = ", ".join(_safe(k) for k in sorted(adata.layers.keys()))
        lines.append(f"Layers: {layer_names}")
    else:
        lines.append("Layers: (none)")
    lines.append("")

    # Observations (cell metadata)
    lines.append("Cell metadata (obs):")
    if adata.obs.shape[1] > 0:
        for col in adata.obs.columns:
            col_data = adata.obs[col]

            # Check if numeric
            if col not in CATEGORICAL_OBS_KEYS and pd.api.types.is_numeric_dtype(col_data):
                min_val = col_data.min()
                max_val = col_data.max()
                mean_val = col_data.mean()
                lines.append(f"  {_safe(col)} (numeric): range [{min_val:.3g}, {max_val:.3g}], mean={mean_val:.3g}")
            else:
                # Categorical or object. dropna=False so missing values are counted
                # and the totals reconcile with n_obs; values escaped to prevent
                # a newline-bearing category from injecting a fake summary line.
                value_counts = col_data.value_counts(dropna=False)
                n_unique = len(value_counts)

                if n_unique <= top_k:
                    items = [f"{_safe(val)}({count})" for val, count in value_counts.items()]
                    lines.append(f"  {_safe(col)} (categorical, {n_unique} unique): {', '.join(items)}")
                else:
                    top_items = [f"{_safe(val)}({count})" for val, count in value_counts.head(top_k).items()]
                    n_more = n_unique - top_k
                    lines.append(f"  {_safe(col)} (categorical, {n_unique} unique): {', '.join(top_items)}, +{n_more} more")
    else:
        lines.append("  (none)")
    lines.append("")

    # Embeddings and other obsm
    lines.append("Embeddings/matrices (obsm):")
    if adata.obsm:
        obsm_keys = ", ".join(_safe(k) for k in sorted(adata.obsm.keys()))
        lines.append(f"  {obsm_keys}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def main(args):
    """CLI entry for the `summarize` subcommand: load the dataset and emit the
    plain-text summary produced by `summarize_adata`. Fails loud — the previous
    version called a nonexistent `io.read_h5ad_or_mudata` and would NameError."""
    import json
    from . import io

    # Branch by file type, mirroring validate_layout's loader handling.
    if str(args.input).endswith(".h5mu"):
        mdata, _ = io.load_h5mu(path=args.input)
        sections = [f"MuData summary: {args.input}", f"Modalities: {list(mdata.mod.keys())}", ""]
        for mod_name, mod_data in mdata.mod.items():
            sections.append(f"=== modality: {mod_name} ===")
            sections.append(summarize_adata(mod_data))
            sections.append("")
        summary = "\n".join(sections)
        report = {
            "operation": "summarize",
            "input": str(args.input),
            "modalities": list(mdata.mod.keys()),
            "n_obs": int(mdata.n_obs),
        }
    else:
        adata, _ = io.load_h5ad(path=args.input)
        summary = summarize_adata(adata)
        report = {
            "operation": "summarize",
            "input": str(args.input),
            "n_obs": int(adata.n_obs),
            "n_vars": int(adata.n_vars),
            "obs_keys": list(adata.obs.columns),
            "obsm_keys": list(adata.obsm.keys()),
        }

    if args.output:
        with open(args.output, "w") as f:
            f.write(summary)
    report["summary"] = summary
    # Human-readable text first, then a trailing JSON report so the typed
    # omics_compute tool can parse it (extract_trailing_json) and record
    # evidence — consistent with marker_table / preprocess.
    print(summary)
    print(json.dumps(report, default=str))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output')
    main(parser.parse_args())
