"""Tests for the scATAC peak_calling wrapper.

peak_calling is a thin wrapper over snapatac2.tl.macs3 (+ merge_peaks for the
pseudobulk union), so these tests cover the wiring, the fail-loud guards, the BED
contract and the recorded provenance — not MACS3's peak numerics.
"""

import json
import tempfile
import types

import anndata as ad
import pandas as pd
import polars as pl
import pytest
import snapatac2 as snap

from aose_omics_runtime.scatac.peak_calling import run_peak_calling


def _args(tmp_path, adata, **overrides):
    params = dict(
        adata=str(adata), output=str(tmp_path / "peaks.bed"), mode="bulk",
        cluster_column=None, qvalue=0.05, min_length=None, half_width=250,
        n_jobs=1, counting_strategy="paired-insertion", create_matrix=False,
    )
    params.update(overrides)
    return types.SimpleNamespace(**params)


def _read_bed(path):
    return pd.read_csv(path, sep="\t", header=None,
                       names=["chr", "start", "end", "name", "score"])


def test_peak_calling_bulk_contract(fragments_h5ad, tmp_path):
    result = run_peak_calling(_args(tmp_path, fragments_h5ad))
    assert result["success"] is True
    assert result["n_peaks"] > 0
    bed = _read_bed(result["peak_file"])
    assert len(bed) == result["n_peaks"]
    assert (bed["end"] > bed["start"]).all()


def test_peak_calling_provenance_names_snapatac2(fragments_h5ad, tmp_path):
    result = run_peak_calling(_args(tmp_path, fragments_h5ad))
    assert result["algorithm"] == "snapatac2.tl.macs3"
    assert result["snapatac2_version"] == snap.__version__


def test_peak_calling_pseudobulk_merges_to_fixed_width(fragments_h5ad_clustered, tmp_path):
    """merge_peaks re-centres each peak on its summit at half_width, so the union is fixed-width."""
    result = run_peak_calling(_args(
        tmp_path, fragments_h5ad_clustered, mode="pseudobulk",
        cluster_column="cluster", half_width=250,
    ))
    assert result["n_peaks"] > 0
    assert result["missing_clusters"] == []
    bed = _read_bed(result["peak_file"])
    assert set(bed["end"] - bed["start"]) == {501}


def test_peak_calling_pseudobulk_matrix_records_cluster_membership(
    fragments_h5ad_clustered, tmp_path
):
    """merge_peaks reports which cluster contributed each peak — keep that in var."""
    result = run_peak_calling(_args(
        tmp_path, fragments_h5ad_clustered, mode="pseudobulk",
        cluster_column="cluster", create_matrix=True,
    ))
    out = ad.read_h5ad(result["output"])
    assert {"a", "b"} <= set(out.var.columns)
    assert out.uns["peak_calling"]["algorithm"] == "snapatac2.tl.macs3"


def test_peak_calling_rejects_plain_feature_matrix(plain_feature_matrix, tmp_path):
    with pytest.raises(ValueError, match="import_fragments"):
        run_peak_calling(_args(tmp_path, plain_feature_matrix))


def test_peak_calling_pseudobulk_requires_cluster_column(fragments_h5ad, tmp_path):
    with pytest.raises(ValueError, match="requires --cluster-column"):
        run_peak_calling(_args(tmp_path, fragments_h5ad, mode="pseudobulk"))


def test_peak_calling_rejects_unknown_cluster_column(fragments_h5ad_clustered, tmp_path):
    with pytest.raises(ValueError, match="not in obs"):
        run_peak_calling(_args(tmp_path, fragments_h5ad_clustered, mode="pseudobulk",
                               cluster_column="no_such_column"))


def test_peak_calling_zero_peaks_fails_loud(fragments_h5ad, tmp_path, monkeypatch):
    """An empty peak set is a failure, not a successful empty BED."""
    empty = pl.DataFrame({"chrom": [], "start": [], "end": [], "name": [], "score": []})
    monkeypatch.setattr(snap.tl, "macs3", lambda *a, **k: empty)
    with pytest.raises(RuntimeError, match="zero peaks"):
        run_peak_calling(_args(tmp_path, fragments_h5ad))


def test_peak_calling_report_is_strict_json(fragments_h5ad, tmp_path):
    result = run_peak_calling(_args(tmp_path, fragments_h5ad))
    json.dumps(result, allow_nan=False)


def test_peak_calling_does_not_leak_tempdir(fragments_h5ad_clustered, tmp_path):
    """snapATAC2 2.9.0 points the global tempfile.tempdir at scratch it then deletes.

    With n_jobs=1 that assignment runs in this process (`tools/_call_peaks.py:175`),
    so without the guard every later tempfile user — a second peak_calling, any other
    library — dies on a FileNotFoundError naming an unrelated path.
    """
    before = tempfile.tempdir
    run_peak_calling(_args(tmp_path, fragments_h5ad_clustered, mode="pseudobulk",
                           cluster_column="cluster", n_jobs=1))
    assert tempfile.tempdir == before
    with tempfile.NamedTemporaryFile() as handle:      # would raise if tempdir were poisoned
        assert handle.name
