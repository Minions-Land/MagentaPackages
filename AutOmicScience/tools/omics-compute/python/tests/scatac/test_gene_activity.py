"""Tests for the scATAC gene_activity wrapper.

gene_activity is a thin wrapper over snapatac2.pp.make_gene_matrix, so these tests
cover the wiring, the fail-loud guards, and the recorded provenance — not the gene
matrix's numerics, which are snapATAC2's contract and are tested upstream.
"""

import json
import types

import anndata as ad
import pytest
import snapatac2 as snap

from aose_omics_runtime.scatac.gene_activity import run_gene_activity


def _args(tmp_path, adata, gtf, **overrides):
    params = dict(
        adata=str(adata), output=str(tmp_path / "genes.h5ad"), gtf_file=str(gtf),
        upstream=2000, downstream=0, include_gene_body=True,
        id_type="gene", counting_strategy="paired-insertion",
    )
    params.update(overrides)
    return types.SimpleNamespace(**params)


def test_gene_activity_contract(fragments_h5ad, gtf_file, tmp_path):
    result = run_gene_activity(_args(tmp_path, fragments_h5ad, gtf_file))
    assert result["success"] is True
    assert result["n_genes"] == 1
    assert result["n_cells"] > 0
    out = ad.read_h5ad(result["output"])
    assert list(out.var_names) == ["G1"]
    assert out.X.nnz > 0


def test_gene_activity_provenance_names_snapatac2(fragments_h5ad, gtf_file, tmp_path):
    """The algorithm must be named honestly: this is snapATAC2's, not a look-alike."""
    result = run_gene_activity(_args(tmp_path, fragments_h5ad, gtf_file))
    assert result["algorithm"] == "snapatac2.pp.make_gene_matrix"
    assert result["snapatac2_version"] == snap.__version__
    uns = ad.read_h5ad(result["output"]).uns["gene_activity"]
    assert uns["algorithm"] == "snapatac2.pp.make_gene_matrix"
    assert uns["snapatac2_version"] == snap.__version__
    assert uns["parameters"]["counting_strategy"] == "paired-insertion"


def test_gene_activity_rejects_plain_feature_matrix(plain_feature_matrix, gtf_file, tmp_path):
    """A peak/tile matrix without obsm fragments cannot be scored — name the missing step."""
    with pytest.raises(ValueError, match="import_fragments"):
        run_gene_activity(_args(tmp_path, plain_feature_matrix, gtf_file))


def test_gene_activity_chromosome_mismatch_fails_loud(fragments_h5ad, gtf_writer, tmp_path):
    """'1' vs 'chr1' must name both namespaces, not surface snapATAC2's numpy error."""
    bad = gtf_writer(tmp_path / 'bad.gtf', chrom='1')
    with pytest.raises(ValueError, match="Chromosome naming mismatch"):
        run_gene_activity(_args(tmp_path, fragments_h5ad, bad))


def test_gene_activity_report_is_strict_json(fragments_h5ad, gtf_file, tmp_path):
    result = run_gene_activity(_args(tmp_path, fragments_h5ad, gtf_file))
    json.dumps(result, allow_nan=False)


def test_gene_activity_fails_on_missing_input(gtf_file, tmp_path):
    with pytest.raises((FileNotFoundError, OSError)):
        run_gene_activity(_args(tmp_path, tmp_path / "nope.h5ad", gtf_file))
