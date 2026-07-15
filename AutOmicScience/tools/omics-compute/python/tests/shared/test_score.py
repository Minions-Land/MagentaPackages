"""Regression tests for shared/score.py.

Covers the audited defects: missing-label accounting (S10), sparse obsm (S11),
DataFrame column alignment (S12), and non-finite fail-loud (S13).
"""

import numpy as np
import pandas as pd
import pytest
import anndata as ad
from scipy.sparse import csr_matrix

from aose_omics_runtime.shared import score


def _obs_adata(pred, ref):
    a = ad.AnnData(np.zeros((len(pred), 2)))
    a.obs["pred"] = pd.Categorical(pred)
    a.obs["ref"] = pd.Categorical(ref)
    return a


def test_missing_labels_dropped_not_counted_as_class():
    # 4 real disagreeing labels (ARI -0.5) + 996 double-missing pairs.
    pred = ["P0", "P0", "P1", "P1"] + [np.nan] * 996
    ref = ["R0", "R1", "R0", "R1"] + [np.nan] * 996
    r = score.score_against_reference(_obs_adata(pred, ref), pred_key="pred", ref_key="ref", metric="ari")
    assert r["n_obs_scored"] == 4
    assert r["n_obs_dropped"] == 996
    assert r["value"] == pytest.approx(-0.5)  # NOT inflated toward 1


def test_all_missing_fails_loud():
    a = _obs_adata([np.nan, np.nan], ["A", np.nan])
    with pytest.raises(ValueError, match="both labels present"):
        score.score_against_reference(a, pred_key="pred", ref_key="ref", metric="ari")


def test_deconv_sparse_obsm_does_not_crash():
    a = ad.AnnData(np.zeros((4, 2)))
    m = np.random.default_rng(0).random((4, 3))
    a.obsm["pred"] = csr_matrix(m)
    a.obsm["ref"] = csr_matrix(m)
    r = score.score_against_reference(a, pred_key="pred", ref_key="ref", metric="deconv_corr")
    assert r["value"] == pytest.approx(1.0)  # identical matrices -> perfect


def test_deconv_dataframe_aligned_by_name():
    props = pd.DataFrame(
        {"T": [0.6, 0.1, 0.3], "B": [0.3, 0.6, 0.1], "NK": [0.1, 0.3, 0.6]},
        index=[f"s{i}" for i in range(3)],
    )
    a = ad.AnnData(np.zeros((3, 2)), obs=pd.DataFrame(index=props.index))
    a.obsm["pred"] = props.copy()
    a.obsm["ref"] = props[["NK", "T", "B"]].copy()  # same content, reordered columns
    r = score.score_against_reference(a, pred_key="pred", ref_key="ref", metric="deconv_corr")
    assert r["value"] == pytest.approx(1.0)


def test_deconv_mismatched_columns_fail_loud():
    idx = [f"s{i}" for i in range(3)]
    a = ad.AnnData(np.zeros((3, 2)), obs=pd.DataFrame(index=idx))
    a.obsm["pred"] = pd.DataFrame({"T": [0.5, 0.5, 0.5], "B": [0.5, 0.5, 0.5]}, index=idx)
    a.obsm["ref"] = pd.DataFrame({"T": [0.5, 0.5, 0.5], "X": [0.5, 0.5, 0.5]}, index=idx)
    with pytest.raises(ValueError, match="columns differ"):
        score.score_against_reference(a, pred_key="pred", ref_key="ref", metric="deconv_corr")


def test_deconv_nonfinite_fails_loud():
    a = ad.AnnData(np.zeros((3, 2)))
    a.obsm["pred"] = np.array([[0.5, 0.5, 0.0], [np.nan, 0.5, 0.5], [0.3, 0.3, 0.4]])
    a.obsm["ref"] = np.array([[0.5, 0.5, 0.0], [0.2, 0.4, 0.4], [0.3, 0.3, 0.4]])
    with pytest.raises(ValueError, match="non-finite"):
        score.score_against_reference(a, pred_key="pred", ref_key="ref", metric="deconv_corr")
