# Spatial QC

**Maturity: REFERENCE** — hand-rolled in Python with scanpy + squidpy, both pinned in `task2`. Verified against squidpy 1.8.1.

**Be precise about what is spatial here.** Most metrics below are the **scRNA count metrics applied to spatial data** — `total_counts`, `n_genes_by_counts`, a control-probe fraction. Only two things use the coordinates: **Moran's I on the QC metrics themselves** (§3 — catches technical gradients no histogram can show) and **inspecting every metric on the tissue**. Do not describe the count thresholds as "spatial QC"; they are ordinary QC that happens to run on spatial data.

## Goal / When to Use

Detect technical failure before it becomes biology: low-quality regions, tissue folds, capture gradients, segmentation problems. Use right after loading spatial data, before any feature matrices or clustering.

## Decision Criteria

**The judgment this guides:**

- **For spot data** (Visium, Slide-seq) — standard counts/genes thresholds plus **spatial sanity**: are low-count spots off-tissue (expected) or on-tissue (problem)? Visualize QC metrics **in space** to catch regional artifacts a histogram would hide.

- **For imaging/single-cell data** (Xenium, MERFISH, CosMx) — additionally **segmentation quality**:
  - Cell area — too small = over-segmentation (fragments), too large = under-segmentation (merged cells). **Area is not computed here** — scanpy has no such metric. It comes from the segmentation pipeline: Xenium ships `cell_area` / `nucleus_area` in `adata.obs`. If those columns are absent, say the segmentation-quality check was not possible rather than skipping it silently.
  - Transcripts per cell — `total_counts`, below
  - Negative/blank-probe fraction — §2 below
  - Whether segmentation boundaries match the image — a visual check (`viz_2d_3d.md`), not a metric

- **Decide thresholds from the data distribution and the platform**, not fixed numbers. What's "low" for Visium (500 UMI/spot) is normal for MERFISH (10-50 transcripts/cell if it's a small panel).

## Method Menu

- **Compute per-obs QC** — `sc.pp.calculate_qc_metrics`, sized to the panel (§1)
- **Control-probe fraction** (imaging) — prefix-matched (§2)
- **Moran's I on the QC metrics** — `sq.gr.spatial_autocorr(attr="obs")` (§3). The only metric here that uses the coordinates; it separates a technical gradient from random noise.
- **Visualize QC *in space*** — `sq.pl.spatial_scatter` for every QC metric, not just histograms (§4). Regional artifacts (damaged tissue, edge effects, uneven capture) are invisible in a histogram.
- **On-tissue vs off-tissue** (spots) — `adata.obs['in_tissue']` from spaceranger when present
- **Segmentation area** (imaging) — platform-provided (`cell_area`), not computed here

## How-to

### 1. Per-obs count metrics

```python
import numpy as np
import scanpy as sc
import squidpy as sq

# percent_top MUST be sized to the panel. The default (50, 100, 200, 500) raises
#   IndexError: Positions outside range of features.
# on any panel with <500 genes — i.e. on every Xenium/MERFISH panel. None skips those metrics.
# qc_vars defaults to () and scanpy does NOT auto-detect mito genes: to get pct_counts_mt you
# must flag them yourself AND name the flag here. (Imaging panels usually carry no mito probes,
# so expect an all-False flag and a pct_counts_mt of 0 — that is honest, not a bug.)
adata.var["mt"] = adata.var_names.str.upper().str.startswith(("MT-", "MT_"))
sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], percent_top=None, inplace=True)
# writes: total_counts, n_genes_by_counts, log1p_*, pct_counts_mt
```

### 2. Control-probe fraction (imaging platforms)

```python
# Match by PREFIX. Real probe names are `NegControlProbe_00042`, `NegControlCodeword_0500`,
# `BLANK_0001` — no gene is literally named "NegControl", so an exact
#   if 'NegControl' in adata.var_names
# test is always False and silently skips this whole block.
CONTROL_PREFIXES = ("NegControl", "NegPrb", "BLANK", "Blank", "antisense", "UnassignedCodeword")
control_genes = [g for g in adata.var_names if g.startswith(CONTROL_PREFIXES)]

if control_genes:
    counts = adata[:, control_genes].X.sum(axis=1)
    # np.ravel handles dense ndarray, csr_matrix and csr_array alike. `.A1` exists only on
    # legacy np.matrix and raises AttributeError on the other two — small panels are often dense.
    adata.obs["pct_counts_control"] = 100 * np.ravel(counts) / adata.obs["total_counts"].to_numpy()
```

### 3. The spatial-aware check — is a QC metric spatially structured?

This is the part a histogram cannot do. A capture gradient, a fold, or a bubble makes `total_counts`
**spatially autocorrelated**; healthy technical noise is spatially random.

```python
sq.gr.spatial_neighbors(adata)     # squidpy 1.8.x API — see the pin note below

qc_cols = [c for c in ["total_counts", "n_genes_by_counts", "pct_counts_control"] if c in adata.obs]
mi = sq.gr.spatial_autocorr(adata, attr="obs", genes=qc_cols, mode="moran", copy=True)
# -> columns: I, pval_norm, var_norm, pval_norm_fdr_bh   (corr_method="fdr_bh" is squidpy's default)
print(mi[["I", "pval_norm_fdr_bh"]])
```

`attr="obs"` makes `genes=` a list of **obs columns**, not var_names. Read `I`: a QC metric with
high, significant Moran's I is a **technical gradient** — do not filter on it before you understand
it, because you would be filtering a region, not bad cells. Some autocorrelation is expected
(cellularity genuinely varies across tissue); the figure in §4 tells you which it is.

> **Pin note.** `sq.gr.spatial_neighbors` is the graph builder in the pinned squidpy 1.8.1. Upstream
> deprecates it and removes it in **1.9.0**, where it splits into `spatial_neighbors_knn` /
> `_radius` / `_delaunay` / `_grid`. **Those names do not exist in 1.8.1** — do not "modernise" this
> call. `pixi.toml` pins `squidpy = ">=1.8,<1.9"` precisely so the migration is a deliberate act.

### 4. Inspect every metric on the tissue

```python
# For imaging AnnData carrying only obsm["spatial"] (no uns["spatial"] image metadata), the
# defaults img=True + shape=CIRCLE force a uns lookup and raise
#   KeyError: "Spatial key 'spatial' not found in `adata.uns`."
# BOTH img=False and shape=None are required — img=False alone still raises.
sq.pl.spatial_scatter(adata, color="total_counts",       img=False, shape=None, size=8, save="_qc_counts.png")
sq.pl.spatial_scatter(adata, color="n_genes_by_counts",  img=False, shape=None, size=8, save="_qc_genes.png")
if "pct_counts_control" in adata.obs:
    sq.pl.spatial_scatter(adata, color="pct_counts_control", img=False, shape=None, size=8, save="_qc_control.png")
# For Visium read via sq.read.visium (uns["spatial"] present), drop img=False/shape=None to get the H&E.
# save= is a literal path under scanpy.settings.figdir -> figures/_qc_counts.png
```

### Filter (after inspecting the spatial QC plots)

```python
# Choose thresholds from the distribution + spatial view
min_counts = 200  # adapt per platform
min_genes = 100
max_control_pct = 10.0  # for imaging

pre_filter = adata.n_obs
adata = adata[
    (adata.obs['total_counts'] >= min_counts) &
    (adata.obs['n_genes_by_counts'] >= min_genes),
    :
].copy()

if 'pct_counts_control' in adata.obs:
    adata = adata[adata.obs['pct_counts_control'] <= max_control_pct, :].copy()

print(f"Filtered {pre_filter} → {adata.n_obs} obs")
```

## Pitfalls & Quality Checks

- **A uniform histogram can hide a damaged tissue region** — always inspect the QC-on-space plots, and read §3's Moran's I. A histogram showing "reasonable" values can mask a large dead zone or a folded tissue edge; the histogram cannot see position, so it cannot see the artifact.

- **`percent_top` left at its default on a targeted panel** — *symptom:* `IndexError: Positions outside range of features.` *Diagnosis:* the default `(50, 100, 200, 500)` indexes ranks that a 313-gene panel does not have. *Fix:* `percent_top=None`, or a tuple below the panel size.

- **Expecting `pct_counts_mt` for free** — *symptom:* the column is absent. *Diagnosis:* `qc_vars` defaults to `()` and scanpy never auto-detects mito genes. *Fix:* flag `adata.var["mt"]` yourself and pass `qc_vars=["mt"]`.

- **Exact-matching control-probe names** — *symptom:* the control block silently never runs and every `pct_counts_control` branch downstream is dead. *Diagnosis:* probes are `NegControlProbe_00042`, not `NegControl`. *Fix:* prefix match (§2).

- **Do not blanket-filter "low-count" spots that are genuinely low-cellularity tissue** — some tissue regions (e.g., extracellular matrix, lumen) have low RNA capture by biology, not by technical failure. Inspect the spatial plot: if low counts cluster off-tissue or at folds, filter them; if they're in a known low-signal region, keep them.

- **Over-segmentation (imaging)** — inflates cell count and dilutes signal (one real cell split into 2-3 fragments). Signals: many cells with tiny area, very low transcripts/cell. Flag and consider re-segmentation.

- **Under-segmentation (imaging)** — merges multiple cells into one. Signals: huge cell area, high transcripts/cell, marker co-expression that should be mutually exclusive (e.g., epithelial + immune markers in one "cell"). Flag and consider re-segmentation.

- **Off-tissue spots (Visium)** — should be filtered. If spaceranger provided a tissue mask (`adata.obs['in_tissue']`), use it; otherwise infer from the spatial count plot (a clear tissue outline vs. background).

- **Inspect the figures** — every QC metric on space. Red flags:
  - A streak/band of low counts (technical artifact, maybe a fold or bubble)
  - High control-probe fraction in one region (local technical failure)
  - Cell-area distribution with a long tail (segmentation issue)

## Grounding

**What to record in the `report` dict:**

```python
{
  "n_obs_pre_filter": 4500,
  "n_obs_post_filter": 3800,
  "thresholds": {
    "min_counts": 200,
    "min_genes": 100,
    "max_control_pct": 10.0
  },
  "median_counts": 1200,
  "median_genes": 850,
  "median_control_pct": 2.5,   # if applicable
  "off_tissue_removed": 700,   # if applicable
  "platform": "visium",
  # the spatial part: Moran's I per QC metric + its FDR-corrected p (from `mi`, not typed by hand)
  "qc_moran_I": {"total_counts": 0.31, "n_genes_by_counts": 0.28},
  "qc_moran_padj": {"total_counts": 1e-12, "n_genes_by_counts": 3e-11},
  "segmentation_area_available": False,   # True only if the platform shipped cell_area
  "spatial_qc_figures": ["figures/_qc_counts.png", "figures/_qc_genes.png", "figures/_qc_control.png"]
}
```

Ground: pre/post cell counts, thresholds applied, median QC values, fraction off-tissue removed, and the **Moran's I per QC metric** — that last one is what distinguishes "I looked at the counts" from "I checked whether the counts have spatial structure". Read the I values off `mi`; never hardcode them.

## Honesty

- **Do not call the count thresholds "spatial QC".** `total_counts >= 200` is ordinary scRNA QC that happens to run on spatial data. The spatial content of this recipe is §3's Moran's I and the on-tissue figures — cite those when you claim the QC was spatially aware, and say plainly when you only did the count filter.

- If QC removes a **large fraction** (>30-40%), say so and consider whether the threshold (not the data) is wrong. Inspect the spatial plots — is the filtered set biologically sensible?

- If one region is systematically low-quality, **flag it** — a damaged tissue region or a segmentation failure. Don't silently filter it and proceed as if the whole sample is uniform.

- **Abstain from strong conclusions on a heavily filtered sample** — if you removed half the cells, the spatial structure you're left with may not represent the original tissue.

- For imaging data, **segmentation quality is upstream of this QC** — if segmentation is broken (massive over/under-segmentation), no threshold here will fix it. Surface the segmentation issue and recommend re-running the segmentation pipeline, not just filtering the results.
