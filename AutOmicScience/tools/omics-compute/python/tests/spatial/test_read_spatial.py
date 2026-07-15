"""
Tests for the read_spatial frozen helper.

The platform loaders (Visium/Xenium/MERFISH) need real on-disk datasets, so the
data-loading paths are covered only by their fail-loud error contracts here; the
no-real-data logic in validate_spatial_adata is tested directly. Exercised
through the flat re-export shim (the analyst-kernel import pattern).
"""

import pytest
import numpy as np
from anndata import AnnData
from scipy.sparse import csr_matrix
import sys
import os as _os


from aose_omics_runtime.spatial.read_spatial import (
    load_visium,
    load_xenium,
    load_merfish,
    validate_spatial_adata,
)
from aose_omics_runtime.shared.conventions import OBSM_SPATIAL, LAYER_COUNTS


def _spatial_adata(*, with_counts=True, n_dims=2) -> AnnData:
    rng = np.random.default_rng(0)
    n = 10
    adata = AnnData(rng.poisson(1.0, size=(n, 6)).astype(float))
    adata.obsm[OBSM_SPATIAL] = rng.random((n, n_dims))
    if with_counts:
        adata.layers[LAYER_COUNTS] = csr_matrix(adata.X)
    return adata


def test_validate_spatial_adata_valid():
    report = validate_spatial_adata(_spatial_adata())
    assert report["valid"] is True
    assert report["errors"] == []
    assert report["has_spatial_coords"] is True
    assert report["has_counts"] is True
    assert report["coordinate_shape"] == (10, 2)
    assert set(report["coordinate_range"]) == {"x_min", "x_max", "y_min", "y_max"}


def test_validate_spatial_adata_missing_coords():
    adata = AnnData(np.ones((5, 3)))
    report = validate_spatial_adata(adata)
    assert report["valid"] is False
    assert report["has_spatial_coords"] is False
    assert any("spatial coordinates" in e.lower() for e in report["errors"])


def test_validate_spatial_adata_missing_counts():
    report = validate_spatial_adata(_spatial_adata(with_counts=False), require_counts=True)
    assert report["valid"] is False
    assert report["has_counts"] is False
    assert any(LAYER_COUNTS in e for e in report["errors"])


def test_validate_spatial_adata_counts_not_required():
    report = validate_spatial_adata(_spatial_adata(with_counts=False), require_counts=False)
    assert report["valid"] is True


def test_validate_spatial_adata_wrong_dims():
    report = validate_spatial_adata(_spatial_adata(n_dims=3))
    assert report["valid"] is False
    assert any("(n_obs, 2)" in e for e in report["errors"])


def test_validate_spatial_adata_visium_warnings():
    # No in_tissue / images -> platform warnings, but still structurally valid.
    report = validate_spatial_adata(_spatial_adata(), platform="visium")
    assert report["valid"] is True
    assert len(report["warnings"]) >= 1


def test_load_visium_missing_path():
    with pytest.raises(FileNotFoundError, match="Visium data directory not found"):
        load_visium(path="/nonexistent/spaceranger/output/abc123")


def test_load_xenium_missing_path():
    with pytest.raises(FileNotFoundError):
        load_xenium(path="/nonexistent/xenium/output/abc123")


def test_load_merfish_missing_path():
    with pytest.raises(FileNotFoundError):
        load_merfish(
            path="/nonexistent/merfish/output/abc123",
            counts_file="counts.csv",
            metadata_file="cell_metadata.csv",
        )


# --- Regressions for audited defects (X02 finite, X03 overlap, X04 validator, X05 images) ---

def _write_merfish(tmp_path, counts_index, meta_ids, xs, ys):
    import pandas as pd
    counts = pd.DataFrame(
        np.arange(len(counts_index) * 3).reshape(len(counts_index), 3),
        index=counts_index, columns=["g0", "g1", "g2"],
    )
    counts.to_csv(tmp_path / "counts.csv")
    pd.DataFrame({"cell_id": meta_ids, "x": xs, "y": ys}).to_csv(tmp_path / "meta.csv", index=False)


def test_x03_partial_overlap_fails_loud(tmp_path):
    _write_merfish(tmp_path, ["shared", "c1", "c2"], ["shared", "m1", "m2"], [1.0, 2, 3], [4.0, 5, 6])
    with pytest.raises(ValueError, match="overlap"):
        load_merfish(path=str(tmp_path), counts_file="counts.csv", metadata_file="meta.csv")


def test_x02_nonfinite_coords_fail_loud(tmp_path):
    _write_merfish(tmp_path, ["a", "b", "c"], ["a", "b", "c"], [np.nan, np.inf, 3.0], [4.0, 5, 6])
    with pytest.raises(ValueError, match="non-finite"):
        load_merfish(path=str(tmp_path), counts_file="counts.csv", metadata_file="meta.csv")


def test_x02_validator_flags_nonfinite():
    a = AnnData(np.zeros((2, 2)))
    a.obsm["spatial"] = np.array([[np.nan, 1.0], [np.inf, 2.0]])
    r = validate_spatial_adata(a, require_counts=False)
    assert r["valid"] is False
    assert any("non-finite" in e for e in r["errors"])


def test_x04_validator_no_crash_on_bad_shapes():
    a1 = AnnData(np.zeros((2, 2)))
    a1.obsm["spatial"] = np.array([[1.0], [2.0]])  # (2, 1)
    r1 = validate_spatial_adata(a1, require_counts=False)
    assert r1["valid"] is False and r1["coordinate_range"] is None

    a0 = AnnData(np.zeros((0, 2)))
    a0.obsm["spatial"] = np.zeros((0, 2))  # empty
    r0 = validate_spatial_adata(a0, require_counts=False)
    assert r0["valid"] is False  # did not raise


def test_x05_empty_spatial_uns_has_no_images():
    a = AnnData(np.zeros((2, 2)))
    a.obsm["spatial"] = np.array([[1.0, 2.0], [3.0, 4.0]])
    a.uns["spatial"] = {}
    r = validate_spatial_adata(a, require_counts=False, require_images=True)
    assert r["has_images"] is False and r["valid"] is False


def test_x03_align_by_ids_reports_both_sides_and_rejects_duplicates():
    # Direct test of the shared aligner used by BOTH the xenium and merfish loaders:
    # duplicate IDs fail loud, and a partial overlap reports both sides' losses.
    import pandas as pd
    from anndata import AnnData
    from aose_omics_runtime.spatial.read_spatial import _align_by_ids

    counts = AnnData(np.zeros((3, 2)))
    counts.obs_names = ["a", "b", "c"]
    meta = pd.DataFrame({"x": [1.0, 2.0]}, index=["a", "b"])
    aligned, meta_aligned, rep = _align_by_ids(counts, meta, "xenium", min_overlap=0.5)
    assert rep["n_counts_cells"] == 3 and rep["n_metadata_cells"] == 2
    assert rep["n_common_cells"] == 2
    assert rep["n_dropped_counts"] == 1 and rep["n_dropped_metadata"] == 0
    assert rep["overlap_rate"] == pytest.approx(2 / 3, abs=1e-4)  # reported rounded to 4dp
    assert list(aligned.obs_names) == ["a", "b"]

    dup = AnnData(np.zeros((2, 2)))
    dup.obs_names = ["a", "a"]
    with pytest.raises(ValueError, match="duplicate cell IDs"):
        _align_by_ids(dup, pd.DataFrame({"x": [1.0]}, index=["a"]), "xenium")

    dup_meta = pd.DataFrame({"x": [1.0, 2.0]}, index=["a", "a"])
    with pytest.raises(ValueError, match="duplicate cell IDs"):
        _align_by_ids(counts, dup_meta, "xenium")
