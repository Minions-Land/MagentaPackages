---
name: spatial
description: Spatial transcriptomics (Visium / Xenium / MERFISH / …) — loading, spatial QC, spatial statistics + SVGs (squidpy), spatial domains (SpaGCN), deconvolution & mapping (cell2location / Tangram), spatial cell-cell communication (squidpy / COMMOT), gene imputation (Tangram), 2D/3D visualization.
requiredTools: [run_python, create_notebook, add_cell, observe_figure, omics_preflight, omics_compute]
tags: [omics, spatial, spatial-transcriptomics, squidpy, spatialdata, visium, xenium, merfish]
---

# Spatial Transcriptomics Analysis

Builds on `omics-shared` (loaded automatically — its rules apply here). Load spatial data through the **`omics_compute`** tool (`read_spatial`, returns a `report` dict — cite its numbers); the analysis itself is **squidpy** run in Python for the statistics / CCC, with heavier methods (cell2location, SpaGCN, COMMOT) run in isolated envs. Read the method doc before running a capability.

## Prerequisites

1. `omics_preflight(modality="spatial")` passes (validates `task2`: squidpy + spatialdata).
2. An AnnData with `obsm["spatial"]` coordinates, or a SpatialData object.
3. A `summarize` report + free-text study description threaded into every biological decision.

## Capability menu (with maturity)

| Capability | Maturity | How | Method doc |
|------------|----------|-----|------------|
| Load spatial data (Visium / Xenium / MERFISH / …) | **READY** | `omics_compute read_spatial` | `assets/references/read_spatial.md` |
| Spatial QC (on-tissue, segmentation, control probes) | **REFERENCE** | scanpy + squidpy | `assets/references/spatial_qc.md` |
| Spatial statistics + SVGs (Moran's I / Ripley / nhood / co-occ) | **REFERENCE** | squidpy | `assets/references/spatial_stats.md` |
| Spatial domains (expression + position) | **PARTIAL** | SpaGCN — install; Leiden + spatial smoothing baseline runs on the pinned stack | `assets/references/domains.md` |
| Cellular neighborhoods / niches (who is next to whom) | **REFERENCE** | `squidpy gr.calculate_niche` — pinned; Nolan CN k-means hand-rolled; CytoCommunity external+GPU | `assets/references/neighborhood_detection.md` |
| Mapping & deconvolution | **PARTIAL** | cell2location / Tangram | `assets/references/mapping_deconv.md` |
| Spatial cell-cell communication | **REFERENCE** | squidpy `gr.ligrec` (COMMOT) | `assets/references/spatial_ccc.md` |
| Gene imputation (targeted panels) | **PARTIAL** | Tangram | `assets/references/imputation.md` |
| 2D / 3D visualization | **REFERENCE** | squidpy / spatialdata-plot | `assets/references/viz_2d_3d.md` |

Read the method doc before running a capability — each gives the opinionated default, exact parameters, failure modes, and grounding. **squidpy** is the pinned workhorse (stats, niches, CCC-ligrec, plotting); **cell2location / SpaGCN / COMMOT / Tangram / CytoCommunity** are not in `task2` — install / isolated env per the doc.

> **SpatialDE is not an option and is deliberately absent.** Its `base.py` imports `scipy.misc.derivative` at module level, which SciPy removed in **1.12**, so `import SpatialDE` raises `ImportError` on any modern stack — installing it does not help, and upstream has been unmaintained since 2022-10. If you need a GP length-scale, surface it as a blocker; do not substitute a number you cannot compute.

> **squidpy is pinned `>=1.8,<1.9`, and both bounds are load-bearing.** 1.9 removes `gr.spatial_neighbors` (which `spatial_stats` / `domains` / `neighborhood_detection` all build their graph with); `gr.calculate_niche` does not exist before 1.8. The replacement names (`spatial_neighbors_knn` etc.) exist **only** in ≥1.9 — do not "modernise" those calls against the current pin.

## Standard workflow

1. **Preflight & load** — `omics_preflight(modality="spatial")`; `omics_compute(subcommand="read_spatial", modality="spatial", args={"input":"<path>","output":"spatial.h5ad","platform":"visium"})`. Thread the summary + study description forward.
2. **Spatial QC** — scanpy QC + squidpy spatial views; filter off-tissue / low-segmentation cells (`assets/references/spatial_qc.md`).
3. **Cluster / annotate** — reuse the scRNA recipes (see `../../single-cell/AutOmicScience/rna/SKILL.md`: preprocess → markers → annotation) on the expression, then validate **in space**.
4. **Spatial structure** — SVGs + neighborhood enrichment + co-occurrence via squidpy (`assets/references/spatial_stats.md`); spatial domains (`assets/references/domains.md`).
5. **Composition** — spot deconvolution / reference mapping (`assets/references/mapping_deconv.md`); gene imputation for targeted panels (`assets/references/imputation.md`).
6. **Interactions** — spatial cell-cell communication (`assets/references/spatial_ccc.md`).
7. **Visualize & ground** — every figure via `sq.pl.spatial_scatter` / spatialdata-plot, inspect the figure before it backs a claim (`assets/references/viz_2d_3d.md`); cite the reports as evidence.

## Spatial-specific rules (on top of omics-shared)

- **Always look in space, not just histograms** — QC, SVGs, domains, and CCC are validated by plotting on `obsm["spatial"]` and inspecting the figure; a histogram hides regional artifacts.
- **Match the method to the resolution** — spot data (Visium) → deconvolution (proportions per spot); single-cell (Xenium/MERFISH) → direct stats / CCC. Don't deconvolve single-cell data or annotate 2 µm bins as cells.
- **Filter control / blank probes** (imaging) before QC — `NegControl*` / `BLANK*` are not genes.
- **Proximity ≠ interaction; autocorrelation ≠ importance** — spatial stats and CCC are hypotheses; ground them and validate against markers / histology.
- **Heavy methods run in isolated envs** — cell2location (GPU), COMMOT (old pins) don't share `task2`; say when a method was not run rather than substituting a weaker one.

## When things go wrong

- **Empty / garbled spatial plot** — wrong platform, missing / wrong-unit coords, or load failure; re-check `read_spatial` + `obsm["spatial"]`.
- **No SVGs / no neighborhood structure** — wrong spatial graph (`coord_type`) or noisy labels; fix the graph / validate annotation (`assets/references/spatial_stats.md`).
- **Speckled, non-contiguous domains** — expression clustering without a spatial term; use SpaGCN or smooth over the spatial graph (`assets/references/domains.md`).
- **Deconvolution flat / one type everywhere** — reference missing cell types or gene-name mismatch (`assets/references/mapping_deconv.md`).
