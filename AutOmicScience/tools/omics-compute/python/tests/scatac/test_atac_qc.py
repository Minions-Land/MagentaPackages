"""Tests for the scATAC atac_qc wrapper.

TSSe, FRiP and the fragment-size distribution come from snapATAC2, so these tests
cover the wiring, the fail-loud guards, the filter/report layer, and the one metric
we still own (per-cell nucleosome signal) — not snapATAC2's numerics.
"""

import inspect
import json
import types

import anndata as ad
import numpy as np
import pytest
import snapatac2 as snap

from aose_omics_runtime.scatac.atac_qc import run_atac_qc

CHROM = "chr1"


def _args(tmp_path, adata, gtf=None, **overrides):
    params = dict(
        adata=str(adata), output=str(tmp_path / "qc.h5ad"),
        gtf_file=str(gtf) if gtf else None,
        compute_tsse=False, compute_fragment_size=False, compute_frip=False,
        max_fragment_size=1000, peak_bed=None, filter=False,
        min_fragments=1, max_fragments=1_000_000, min_tsse=None,
        max_nucleosome_signal=None, min_frip=None,
    )
    params.update(overrides)
    return types.SimpleNamespace(**params)


def test_atac_qc_contract(fragments_h5ad, gtf_file, tmp_path):
    result = run_atac_qc(_args(tmp_path, fragments_h5ad, gtf_file,
                               compute_tsse=True, compute_fragment_size=True, compute_frip=True))
    assert result["success"] is True
    assert set(result["qc_metrics"]) == {
        "tss_enrichment", "fragment_size", "n_fragment", "frip", "n_peaks"
    }
    out = ad.read_h5ad(result["output"])
    assert {"tsse", "nucleosome_signal", "frip", "n_peaks", "n_fragment"} <= set(out.obs.columns)
    assert "frag_size_distr" in out.uns


def test_atac_qc_provenance_names_snapatac2(fragments_h5ad, gtf_file, tmp_path):
    """Each metric must name the implementation that produced it."""
    result = run_atac_qc(_args(tmp_path, fragments_h5ad, gtf_file,
                               compute_tsse=True, compute_fragment_size=True, compute_frip=True))
    metrics = result["qc_metrics"]
    assert metrics["tss_enrichment"]["method"] == "snapatac2.metrics.tsse"
    assert metrics["frip"]["method"] == "snapatac2.metrics.frip"
    assert metrics["fragment_size"]["distribution_method"] == "snapatac2.metrics.frag_size_distr"
    assert metrics["n_fragment"]["method"] == "import_fragments"
    assert result["snapatac2_version"] == snap.__version__


def test_atac_qc_rejects_plain_feature_matrix(plain_feature_matrix, tmp_path):
    with pytest.raises(ValueError, match="import_fragments"):
        run_atac_qc(_args(tmp_path, plain_feature_matrix))


def test_atac_qc_tsse_chromosome_mismatch_fails_loud(fragments_h5ad, gtf_writer, tmp_path):
    bad = gtf_writer(tmp_path / "bad.gtf", chrom="1")
    with pytest.raises(ValueError, match="Chromosome naming mismatch"):
        run_atac_qc(_args(tmp_path, fragments_h5ad, bad, compute_tsse=True))


def test_atac_qc_n_fragment_is_always_a_true_count(fragments_h5ad, tmp_path):
    """import_fragments writes n_fragment, so there is no proxy to mistake for a count."""
    result = run_atac_qc(_args(tmp_path, fragments_h5ad))
    assert result["qc_metrics"]["n_fragment"]["method"] == "import_fragments"
    out = ad.read_h5ad(result["output"])
    assert "n_fragment_proxy" not in out.obs.columns


def test_atac_qc_fragment_thresholds_always_apply(fragments_h5ad, tmp_path):
    result = run_atac_qc(_args(tmp_path, fragments_h5ad, filter=True, min_fragments=10_000))
    assert result["n_cells_after"] == 0
    report = ad.read_h5ad(result["output"]).uns["atac_qc"]
    assert "n_fragment" in report["filter_report"]["applied"]
    assert report["filters_applied"] is True


def test_atac_qc_filters_requested_but_none_ran_is_reported(fragments_h5ad, tmp_path):
    """Requesting a threshold whose column was never computed must be reported as skipped."""
    result = run_atac_qc(_args(tmp_path, fragments_h5ad, filter=True,
                               min_tsse=5.0, min_frip=0.15))
    report = ad.read_h5ad(result["output"]).uns["atac_qc"]
    assert report["filters_requested"] is True
    assert set(report["filter_report"]["skipped"]) == {"tsse", "frip"}


def test_atac_qc_skip_reason_names_a_real_flag(fragments_h5ad, tmp_path):
    """The remedy in a skip message must be a flag the CLI actually accepts."""
    import aose_omics_runtime.__main__ as cli

    result = run_atac_qc(_args(tmp_path, fragments_h5ad, filter=True, min_tsse=5.0,
                               max_nucleosome_signal=2.0, min_frip=0.15))
    skipped = ad.read_h5ad(result["output"]).uns["atac_qc"]["filter_report"]["skipped"]
    assert set(skipped) == {"tsse", "nucleosome_signal", "frip"}

    source = inspect.getsource(cli.main)
    for name, reason in skipped.items():
        flag = reason.rsplit("pass ", 1)[1].rstrip(")")
        assert f'"{flag}"' in source, f"{name} points at {flag}, which the CLI does not define"


def test_nucleosome_signal_is_per_cell_and_undefined_without_nfr(fragments_from_rows, tmp_path):
    """snapATAC2 has no per-cell nucleosome signal, so this metric is ours to get right.

    A cell with only mononucleosomal fragments has no nucleosome-free denominator: it
    must be NaN and counted, never a fabricated ratio.
    """
    rows = []
    for pos in range(1000, 1000 + 20 * 500, 500):
        rows.append(f"{CHROM}\t{pos}\t{pos + 200}\tc_mono\t1")            # mononucleosomal only
    for i, pos in enumerate(range(1000, 1000 + 20 * 500, 500)):
        rows.append(f"{CHROM}\t{pos}\t{pos + (80 if i % 2 else 200)}\tc_mixed\t1")
    path = fragments_from_rows(rows)

    result = run_atac_qc(_args(tmp_path, path, compute_fragment_size=True))
    signal = ad.read_h5ad(result["output"]).obs["nucleosome_signal"]
    assert np.isnan(signal["c_mono"])
    assert signal["c_mixed"] > 0
    assert result["qc_metrics"]["fragment_size"]["nucleosome_signal"]["n_cells_undefined"] == 1


def test_atac_qc_frip_is_within_zero_and_one(fragments_h5ad, tmp_path):
    result = run_atac_qc(_args(tmp_path, fragments_h5ad, compute_frip=True))
    frip = ad.read_h5ad(result["output"]).obs["frip"].to_numpy()
    assert ((frip >= 0) & (frip <= 1)).all()


def test_atac_qc_report_is_strict_json(fragments_h5ad, gtf_file, tmp_path):
    result = run_atac_qc(_args(tmp_path, fragments_h5ad, gtf_file,
                               compute_tsse=True, compute_fragment_size=True, compute_frip=True))
    json.dumps(result, allow_nan=False)


def test_atac_qc_fails_on_missing_input(tmp_path):
    with pytest.raises((FileNotFoundError, OSError)):
        run_atac_qc(_args(tmp_path, tmp_path / "nope.h5ad"))
