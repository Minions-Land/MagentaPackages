"""Modality-score scorer (Phase 0, spec 02-phase0-rust.md §5.9 / §0.9).

The single scoring capability every benchmark suite references (ARI / NMI /
deconvolution-correlation / domain-ARI vs a GOLD reference labeling). Owned here
in Phase 0 so all five suites read one implementation across the process
boundary. Pure and deterministic: no network, no LLM.

The benchmark harness invokes this via `run_omics_module(root, "score", ...)`,
reads the trailing-JSON `report`, and threshold-checks `value` inline.
"""

from typing import Literal

import numpy as np
import pandas as pd


Metric = Literal["ari", "nmi", "ami", "deconv_corr", "domain_ari"]


def _to_dense_float(m):
    """Coerce an obsm matrix (dense ndarray or scipy sparse) to a dense float array."""
    if hasattr(m, "toarray"):  # scipy sparse
        m = m.toarray()
    return np.asarray(m, dtype=float)


def _categorical_agreement(adata, pred_key: str, ref_key: str, metric: str) -> tuple[float, int, int]:
    """ARI / NMI / AMI / domain_ARI over two categorical obs labelings.

    Observations missing either label are dropped before scoring — coercing a
    missing value with ``.astype(str)`` would fabricate a shared ``"nan"`` class
    that the metric counts as perfect agreement. Returns
    ``(value, n_scored, n_dropped)`` so the caller can report exactly how many
    observations were used.
    """
    from sklearn import metrics as skm

    if pred_key not in adata.obs:
        raise KeyError(f"pred_key '{pred_key}' not in adata.obs (have: {list(adata.obs.columns)})")
    if ref_key not in adata.obs:
        raise KeyError(f"ref_key '{ref_key}' not in adata.obs (have: {list(adata.obs.columns)})")

    pred = adata.obs[pred_key]
    ref = adata.obs[ref_key]
    if len(pred) != len(ref):
        raise ValueError(f"label length mismatch: pred={len(pred)} ref={len(ref)}")
    if len(pred) == 0:
        raise ValueError("empty labeling: 0 observations to score")

    both_present = (pred.notna() & ref.notna()).to_numpy()
    n_dropped = int((~both_present).sum())
    pred = pred[both_present].astype(str).to_numpy()
    ref = ref[both_present].astype(str).to_numpy()
    if len(pred) == 0:
        raise ValueError("no observations with both labels present; nothing to score")

    # domain_ari is ARI applied to spatial-domain labels — same computation.
    fn = {
        "ari": skm.adjusted_rand_score,
        "domain_ari": skm.adjusted_rand_score,
        "nmi": skm.normalized_mutual_info_score,
        "ami": skm.adjusted_mutual_info_score,
    }[metric]
    return float(fn(ref, pred)), len(pred), n_dropped


def _deconv_corr(adata, pred_key: str, ref_key: str) -> float:
    """Correlate predicted vs reference cell-type proportions.

    pred_key / ref_key name matrices in adata.obsm (e.g. 'proportions' and a gold
    proportions matrix); returns the mean per-spot Pearson correlation.
    """
    if pred_key not in adata.obsm:
        raise KeyError(f"pred_key '{pred_key}' not in adata.obsm (have: {list(adata.obsm.keys())})")
    if ref_key not in adata.obsm:
        raise KeyError(f"ref_key '{ref_key}' not in adata.obsm (have: {list(adata.obsm.keys())})")

    pred_raw = adata.obsm[pred_key]
    ref_raw = adata.obsm[ref_key]

    # Labeled proportions (DataFrame) are aligned by cell-type name — column
    # order is not assumed to match. Plain arrays are compared positionally.
    pred_is_df = isinstance(pred_raw, pd.DataFrame)
    ref_is_df = isinstance(ref_raw, pd.DataFrame)
    if pred_is_df or ref_is_df:
        if not (pred_is_df and ref_is_df):
            raise ValueError(
                "deconv_corr: one of pred/ref is a labeled DataFrame and the other is not; "
                "cannot align cell types by name"
            )
        if pred_raw.columns.duplicated().any() or ref_raw.columns.duplicated().any():
            raise ValueError("deconv_corr: duplicate cell-type columns in proportions")
        if set(pred_raw.columns) != set(ref_raw.columns):
            raise ValueError(
                f"deconv_corr: cell-type columns differ: "
                f"pred={list(pred_raw.columns)} ref={list(ref_raw.columns)}"
            )
        pred = pred_raw.to_numpy(dtype=float)
        ref = ref_raw[pred_raw.columns].to_numpy(dtype=float)  # align ref to pred order
    else:
        pred = _to_dense_float(pred_raw)
        ref = _to_dense_float(ref_raw)

    if pred.shape != ref.shape:
        raise ValueError(f"proportion shape mismatch: pred={pred.shape} ref={ref.shape}")
    if pred.size == 0:
        raise ValueError("empty proportions: nothing to correlate")
    if not np.all(np.isfinite(pred)) or not np.all(np.isfinite(ref)):
        raise ValueError("deconv_corr: proportions contain non-finite values (NaN/Inf); cannot score")

    # Per-row (per-spot) Pearson correlation, averaged. Rows with zero variance
    # contribute 0 (no signal) rather than NaN.
    corrs = []
    for p_row, r_row in zip(pred, ref):
        if p_row.std() == 0 or r_row.std() == 0:
            corrs.append(0.0)
        else:
            corrs.append(float(np.corrcoef(p_row, r_row)[0, 1]))
    return float(np.mean(corrs))


def score_against_reference(adata, *, pred_key: str, ref_key: str, metric: str) -> dict:
    """Score a predicted labeling against a GOLD reference labeling.

    Args:
        adata: AnnData opened from the task's output container.
        pred_key: predicted labeling — an obs column (clustering metrics) or an
            obsm key (deconv_corr).
        ref_key: GOLD reference labeling carried by the benchmark task — an obs
            column or obsm key. This is task data, not produced by the run.
        metric: one of ari | nmi | ami | deconv_corr | domain_ari.

    Returns:
        report dict: {metric, value, n_obs, pred_key, ref_key,
                      n_pred_labels, n_ref_labels, n_obs_scored, n_obs_dropped}

    Raises:
        KeyError / ValueError on missing keys, length/shape mismatch, empty
        labeling, or an unknown metric — never a fabricated score.
    """
    valid = {"ari", "nmi", "ami", "deconv_corr", "domain_ari"}
    if metric not in valid:
        raise ValueError(f"unknown metric '{metric}'; expected one of {sorted(valid)}")

    report = {
        "metric": metric,
        "n_obs": int(adata.n_obs),
        "pred_key": pred_key,
        "ref_key": ref_key,
    }

    if metric == "deconv_corr":
        report["value"] = _deconv_corr(adata, pred_key, ref_key)
        report["n_pred_labels"] = int(adata.obsm[pred_key].shape[1])
        report["n_ref_labels"] = int(adata.obsm[ref_key].shape[1])
        report["n_obs_scored"] = int(adata.n_obs)
        report["n_obs_dropped"] = 0
    else:
        value, n_scored, n_dropped = _categorical_agreement(adata, pred_key, ref_key, metric)
        report["value"] = value
        report["n_pred_labels"] = int(adata.obs[pred_key].dropna().astype(str).nunique())
        report["n_ref_labels"] = int(adata.obs[ref_key].dropna().astype(str).nunique())
        report["n_obs_scored"] = n_scored
        report["n_obs_dropped"] = n_dropped

    return report


def main(args):
    """CLI entry for the `score` subcommand. Opens --input, scores --pred-key vs
    --ref-key with --metric, prints the trailing-JSON report. Fails loud."""
    import json

    from . import io

    adata, _load_meta = io.load_h5ad(path=args.input)
    report = score_against_reference(
        adata,
        pred_key=args.pred_key,
        ref_key=args.ref_key,
        metric=args.metric,
    )
    print(json.dumps(report, indent=2, default=str, allow_nan=False))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Score predictions vs a GOLD reference labeling")
    parser.add_argument("--input", required=True, help="AnnData path (.h5ad) with both labelings")
    parser.add_argument("--pred-key", required=True, help="predicted labeling (obs column or obsm key)")
    parser.add_argument("--ref-key", required=True, help="GOLD reference labeling (obs column or obsm key)")
    parser.add_argument(
        "--metric", default="ari",
        choices=["ari", "nmi", "ami", "deconv_corr", "domain_ari"],
    )
    main(parser.parse_args())
