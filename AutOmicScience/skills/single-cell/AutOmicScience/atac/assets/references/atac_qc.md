# ATAC-Specific QC

**Maturity: READY** — `omics_compute(subcommand="atac_qc", modality="scatac", ...)` runs snapATAC2's metrics (`metrics.tsse`, `metrics.frip`, `metrics.frag_size_distr`) and adds the filter + evidence layer. Its `--adata` must come from `snapatac2.pp.import_fragments`: the insertions live in `obsm`, so there is **no `--fragment-file`** and a plain feature matrix is rejected. TSSE needs a **`gtf-file`**; FRiP takes its regions from `var_names` (or `peak-bed`).

> **Per-cell nucleosome signal is ours, not snapATAC2's.** snapATAC2 reports only a dataset-wide `frag_size_distr`; the per-cell mononucleosomal/nucleosome-free ratio that `--max-nucleosome-signal` gates on is computed from the paired fragments in `obsm`. Cells with no nucleosome-free fragment are NaN and counted, never given a fabricated ratio.

## Goal / When to Use

Apply scATAC-specific quality control metrics before feature matrix generation. Use immediately after loading fragment data, before any analysis.

## Decision Criteria

QC thresholds are **dataset-dependent** and set from observed distributions:

- **TSS Enrichment (TSSE)** ≥ 5 (stringent: ≥ 8, permissive: ≥ 2) - measures signal at transcription start sites
- **Unique Fragments** ≥ 1,000 (≥ 500 floor for nuclei)
- **Fragment Size Distribution** - nucleosome banding pattern indicates quality
- **Mitochondrial Fraction** ≤ 0.10
- **Doublet Probability** ≤ 0.5

Frozen/snATAC often shows lower TSSE - adjust thresholds based on technology and tissue.

## Method Menu

Hand-rolled equivalents (snapATAC2), for steps you drive yourself:

- **TSS Enrichment**: `snap.metrics.tsse(adata, genome)`
- **Fragment Size**: `snap.metrics.frag_size_distr(adata)` + PEAKQC periodicity score
- **FRiP**: `snap.metrics.frip(adata, regions)` (requires peak/region set)
- **Doublets**: `snap.pp.scrublet` + `snap.pp.filter_doublets`

Grounded path: `omics_compute(subcommand="atac_qc", ...)` runs snapATAC2's metrics and adds the
filter + evidence layer:

- **TSSE** — `snap.metrics.tsse(adata, gene_anno)`, the standard insertion-based definition, so
  an unenriched cell scores ~1 and the ≥5 / ≥8 thresholds below apply. TSS positions come from
  `gtf-file`; a chromosome-naming mismatch (`chr1` vs `1`) is rejected up front rather than
  surfacing as snapATAC2's opaque numpy error.
- **FRiP** — `snap.metrics.frip(adata, regions, normalized=True)`. Numerator and denominator are
  both fragment counts from the same object, so it is in [0, 1] by construction.
- **Fragment counts** — `n_fragment` is written by `import_fragments` itself, so it is always a
  true count and the thresholds always apply. There is no proxy path.
- **Nucleosome signal** — computed here, per cell, from the paired fragments in `obsm`; snapATAC2
  only reports a dataset-wide `frag_size_distr` (stored in `uns`). A cell with no nucleosome-free
  fragment is undefined (counted in `n_cells_undefined`), never a fabricated ratio.

## How-to

```python
# Grounded path — the omics_compute atac_qc subcommand (records evidence).
# adata comes from import_fragments (+ a tile/peak matrix); the insertions ride along in obsm.
omics_compute(subcommand="atac_qc", modality="scatac", args={
    "adata": "tiles.h5ad", "output": "qc.h5ad", "gtf-file": "genes.gtf",
    "compute-tsse": "true", "compute-fragment-size": "true", "compute-frip": "true",
    "min-tsse": "5.0", "min-fragments": "1000", "filter": "true",
})

# Or compute directly with snapATAC2 in a Python script:
import snapatac2 as snap
snap.metrics.tsse(adata, snap.genome.hg38)              # -> obs["tsse"]
snap.metrics.frag_size_distr(adata)
snap.pp.scrublet(adata); snap.pp.filter_doublets(adata)
adata = adata[(adata.obs["tsse"] >= 5.0) & (adata.obs["n_fragment"] >= 1000)].copy()
```

## Pitfalls & Quality Checks

- **No nucleosome banding** → tagmentation failure (stop, don't proceed)
- **Observe fragment-size plot**: Clear ~147bp peak (mononucleosome) + ~300bp (dinucleosome)
- **TSSE distribution with no high-quality mode** → red flag
- Over-filtering removes rare types; under-filtering injects debris

## Grounding

Record: pre/post cell counts, thresholds used, median TSSE/fragments, doublet rate → the `report` dict

## Honesty

If QC reveals broken library (no banding, uniformly low TSSE), **state data is unusable** - don't push through to pretty UMAP.
