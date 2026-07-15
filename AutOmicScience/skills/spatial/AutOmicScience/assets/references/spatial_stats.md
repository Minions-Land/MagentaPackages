# Spatial Statistics & Spatially-Variable Genes

**Maturity: REFERENCE** — hand-rolled in Python with **squidpy**, pinned in `task2` (verified against squidpy 1.8.1). Everything here runs on the pinned stack; there is no separate-install path in this doc, and the reason is in "Model-based SVGs" below.

## Goal / When to Use

Quantify spatial structure: which genes are **spatially variable** (SVGs), whether cell types are **spatially co-located or segregated** (neighborhood enrichment, co-occurrence), and the **scale** of spatial patterns (Ripley). Run after QC + clustering/annotation, on a graph built from `obsm["spatial"]`.

## Decision Criteria — pick one default

- **Default: squidpy.** Covers the whole spatial-stats menu on the pinned stack: spatial autocorrelation (**Moran's I** / Geary's C) for SVGs, **neighborhood enrichment** + **co-occurrence** for cell-type spatial relationships, **Ripley's F/G/L** for point-pattern scale. One graph, one library, fast.
- **Model-based SVGs (GP length-scale): no supported option here.** SpatialDE is the classic choice and it is **unusable**, not merely uninstalled: its `SpatialDE/base.py` does `from scipy.misc import derivative` at module level, and `scipy.misc.derivative` was removed in **SciPy 1.12**. `import SpatialDE` therefore raises `ImportError` on any modern stack, installed or not (its own `setup.py` pins `scipy >= 1.0` with no upper bound, so `pip install SpatialDE` cheerfully resolves a SciPy that breaks it). Upstream's last commit is **2022-10-18**. Do not add it, and do not present a length-scale you cannot compute — if a GP length-scale is genuinely required, that is a blocker to surface, not a step to fake.

## How-to (default — squidpy)

Build the spatial graph once, then run the statistics on it.

```python
import squidpy as sq

# 1. Spatial neighbor graph from obsm["spatial"]
sq.gr.spatial_neighbors(adata, coord_type="grid", n_neighs=6)   # Visium hex; coord_type="generic" for imaging

# 2. Spatially variable genes — Moran's I.
#    Pass `genes=` EXPLICITLY: with genes=None and attr="X" (the default), squidpy silently
#    restricts the scan to adata.var["highly_variable"] when that column exists — so a standard
#    scanpy pipeline makes every non-HVG SVG invisible without saying so.
sq.gr.spatial_autocorr(adata, mode="moran", genes=adata.var_names.tolist(), n_jobs=4)
moran = adata.uns["moranI"]
# columns: I, pval_norm, var_norm, pval_norm_fdr_bh  <- corr_method="fdr_bh" is squidpy's DEFAULT
svgs = moran.query("pval_norm_fdr_bh < 0.05").sort_values("I", ascending=False)

# 3. Cell-type spatial relationships (needs a cluster/cell_type label)
sq.gr.nhood_enrichment(adata, cluster_key="cell_type")          # which types neighbor which (z-scores in uns)
sq.gr.co_occurrence(adata, cluster_key="cell_type")             # co-occurrence vs distance

# 4. Point-pattern scale
sq.gr.ripley(adata, cluster_key="cell_type", mode="L")          # mode is one of "F", "G", "L"
```

Parameter rationale:
- `coord_type="grid", n_neighs=6` — Visium spots are a hexagonal lattice (6 neighbors). For **imaging/single-cell** (Xenium/MERFISH) use `coord_type="generic"` with `delaunay=True` or `n_neighs=6`.
- `mode="moran"` — Moran's I is the standard, interpretable autocorrelation index (−1…+1; >0 = clustered).
- **Threshold `pval_norm_fdr_bh`, not `pval_norm`.** squidpy already applies BH-FDR (`corr_method="fdr_bh"` by default) and hands you the corrected column. Thresholding the raw `pval_norm` across thousands of genes throws away a correction you already paid for.
- **No `n_perms`.** `pval_norm` is the *analytic* p under normality and is computed regardless of `n_perms`; permutations only add `pval_sim` / `pval_z_sim` (and their `_fdr_bh` twins). Passing `n_perms=100` and then thresholding `pval_norm` buys nothing. If you want the permutation null, pass `n_perms` **and** threshold `pval_sim_fdr_bh` — but note 100 permutations quantise p to 0.01 steps, too coarse for FDR over thousands of genes, so the analytic p is the better default here.

> **Pin note.** `sq.gr.spatial_neighbors` is the graph builder in the pinned squidpy 1.8.1. Upstream deprecates it and removes it in **1.9.0**, splitting it into `spatial_neighbors_knn` / `_radius` / `_delaunay` / `_grid`. **Those names do not exist in 1.8.1** — do not "modernise" this call. `pixi.toml` pins `squidpy = ">=1.8,<1.9"` so the migration stays a deliberate act. Every statistic in this doc rides on this one graph.

## Failure Modes

- **Moran's I ≈ 0 for everything** — *symptom:* no SVGs. *Diagnosis:* the spatial graph is wrong (wrong `coord_type`, coords in wrong units). *Fix:* check `obsm["spatial"]` scale + plot the graph; use `coord_type="generic"` for imaging.
- **nhood_enrichment all near zero** — *symptom:* no cell-type structure. *Diagnosis:* labels are noisy (over-clustering) or the tissue genuinely has no segregation. *Fix:* validate `cell_type` first — this stat is only as good as the annotation.
- **Far fewer SVGs than genes tested** — *symptom:* `adata.uns["moranI"]` has ~2000 rows on a 20k-gene dataset. *Diagnosis:* `genes=None` fell back to `var["highly_variable"]`. *Fix:* pass `genes=` explicitly, and report how many genes were actually scanned.
- **Thousands of "significant" SVGs** — *symptom:* half the transcriptome passes. *Diagnosis:* thresholding the uncorrected `pval_norm`. *Fix:* use `pval_norm_fdr_bh`, which squidpy already computed.

## Figure checkpoints

1. **Top SVGs in space** (`sq.pl.spatial_scatter(adata, color=svgs.index[:4].tolist())`) — does the high-Moran's-I gene show a real pattern, or salt-and-pepper noise? (`color=` needs gene names; `svgs` is a DataFrame, so index it.)
2. **Neighborhood-enrichment heatmap** (`sq.pl.nhood_enrichment`) — do enriched/depleted pairs match known tissue architecture?
3. **Co-occurrence / Ripley curves** — do they plateau at a sensible distance, or look flat (no structure)?

## Grounding

Record: graph params (`coord_type`, `n_neighs`), **`n_genes_scanned`** (`len(adata.uns["moranI"])` — proves you did not silently scan HVGs only), n SVGs at **`pval_norm_fdr_bh < 0.05`** with the threshold column named, top genes with their I, nhood-enrichment z-scores for key pairs, and the Ripley mode → put these in a `report` dict and cite its numbers. "n SVGs" without naming the p-column and the gene universe is not a reportable number.

## Honesty

- **Spatial autocorrelation ≠ biological importance** — a high-Moran's-I gene is spatially structured, not necessarily functionally relevant; interpret with markers.
- **Every stat depends on the graph** — state `coord_type`/`n_neighs`; a different graph gives different numbers.
- nhood / co-occurrence / Ripley are **only as good as the cell-type labels** — if annotation is shaky, say so and treat the relationships as tentative.
