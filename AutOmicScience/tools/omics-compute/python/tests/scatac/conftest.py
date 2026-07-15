"""Shared fixtures for the snapATAC2-backed scatac subcommands.

The subcommands read insertions from obsm, so the fixtures build a real
import_fragments object rather than a hand-assembled feature matrix — a mock would
not exercise the contract these wrappers actually depend on.
"""

import gzip

import anndata as ad
import numpy as np
import pytest
import snapatac2 as snap

CHROM = "chr1"
CHROM_LEN = 300_000
TSS = 50_000


def write_fragment_file(path, n_cells=60, n_tss=40, n_background=20, seed=0):
    """Write a gzipped fragment file with insertions enriched around a single TSS."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_cells):
        centers = np.concatenate([
            rng.normal(TSS, 300, n_tss),
            rng.integers(1, CHROM_LEN, n_background),
        ])
        for center in np.clip(centers.astype(int), 100, CHROM_LEN - 200):
            rows.append(f"{CHROM}\t{center - 40}\t{center + 40}\tc{i}\t1")
    with gzip.open(path, "wt") as handle:
        handle.write("\n".join(rows) + "\n")
    return path


def write_gtf(path, chrom=CHROM):
    """Write a minimal GTF with one gene whose TSS matches the fragment enrichment."""
    path.write_text(
        f'{chrom}\ts\tgene\t{TSS}\t{TSS + 2000}\t.\t+\t.\tgene_id "G1"; gene_name "G1";\n'
        f'{chrom}\ts\ttranscript\t{TSS}\t{TSS + 2000}\t.\t+\t.\t'
        'gene_id "G1"; transcript_id "T1"; gene_name "G1";\n'
    )
    return path


def build_fragments_h5ad(tmp_path, name="input.h5ad", clusters=False):
    """An import_fragments product saved as a plain h5ad, as the skill's step 1 produces."""
    frag = write_fragment_file(tmp_path / "fragments.tsv.gz")
    data = snap.pp.import_fragments(
        str(frag), chrom_sizes={CHROM: CHROM_LEN},
        file=str(tmp_path / "backed.h5ad"), sorted_by_barcode=False, min_num_fragments=10,
    )
    snap.pp.add_tile_matrix(data, bin_size=5000)
    if clusters:
        half = data.n_obs // 2
        data.obs["cluster"] = ["a"] * half + ["b"] * (data.n_obs - half)
    path = tmp_path / name
    data.to_memory().write_h5ad(path)
    data.close()
    return path


@pytest.fixture
def fragments_h5ad(tmp_path):
    return build_fragments_h5ad(tmp_path)


@pytest.fixture
def fragments_h5ad_clustered(tmp_path):
    return build_fragments_h5ad(tmp_path, clusters=True)


@pytest.fixture
def gtf_file(tmp_path):
    return write_gtf(tmp_path / "anno.gtf")


@pytest.fixture
def gtf_writer():
    """write_gtf itself, for tests that need a deliberately mismatched annotation."""
    return write_gtf


@pytest.fixture
def fragments_from_rows(tmp_path):
    """Build an import_fragments h5ad from explicit fragment rows (chrom/start/end/barcode/count)."""
    def build(rows, name="custom.h5ad"):
        frag = tmp_path / f"{name}.tsv.gz"
        with gzip.open(frag, "wt") as handle:
            handle.write("\n".join(rows) + "\n")
        data = snap.pp.import_fragments(
            str(frag), chrom_sizes={CHROM: CHROM_LEN}, file=str(tmp_path / f"b_{name}"),
            sorted_by_barcode=False, min_num_fragments=1,
        )
        snap.pp.add_tile_matrix(data, bin_size=5000)
        path = tmp_path / name
        data.to_memory().write_h5ad(path)
        data.close()
        return path
    return build


@pytest.fixture
def genome_chrom():
    """The chromosome name and length the fragment fixtures use."""
    return CHROM, CHROM_LEN


@pytest.fixture
def plain_feature_matrix(tmp_path):
    """A peak matrix with no obsm fragments — what the wrappers must reject."""
    plain = ad.AnnData(np.ones((5, 3), dtype=np.float32))
    plain.var_names = ["chr1:100-200", "chr1:300-400", "chr1:500-600"]
    path = tmp_path / "plain.h5ad"
    plain.write_h5ad(path)
    return path
