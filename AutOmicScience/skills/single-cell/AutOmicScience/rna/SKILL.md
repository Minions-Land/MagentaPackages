---
name: single-cell-rna
disable-model-invocation: true
---

# scRNA-seq Analysis

> Subskill of `single-cell`. Enter here from the parent skill when the data is single-cell RNA-seq. Read the parent (`../SKILL.md`) and the always-loaded `omics-shared` skill first — their shared workflow, `omics_compute` conventions, and evidence rules apply here.

Run compute through the **`omics_compute`** tool with `modality="scrna"`; it dispatches into the pinned `task1` env and records evidence automatically.

## Prerequisites

1. `omics_preflight(modality="scrna")` passes (provisions/validates `task1`).
2. AnnData with raw counts in `layers["counts"]`.
3. A `summarize` report + free-text study description threaded into every biological decision.

## Capability menu (with maturity)

| Capability | Maturity | How | Method doc |
|------------|----------|-----|------------|
| QC → norm → HVG → PCA → neighbors → UMAP → Leiden | **READY** | `omics_compute preprocess` | `assets/references/qc.md` |
| Dataset summary for context | **READY** | `omics_compute summarize` | `../../../omics-shared/AutOmicScience/assets/references/data_context.md` |
| Batch integration (Harmony) | **READY** | `omics_compute integrate` | `assets/references/integration.md` |
| Batch integration (scVI / scANVI) | **PARTIAL** | needs GPU; verify preflight | `assets/references/integration.md` |
| Per-cluster marker genes | **READY** | `omics_compute marker_table` | `assets/references/markers_de.md` |
| Cell-type annotation (marker + LLM) | **READY** | markers → LLM labeling | `assets/references/annotation.md` |
| Gene programs / meta-programs (continuous, not labels) | **REFERENCE** | hand-rolled `cnmf` — install for the task | `assets/references/consensus_nmf.md` |
| Pathway / TF activity, gene-set enrichment | **READY** | `omics_compute pathway_activity` / `enrichment` | `assets/references/functional.md` |
| Perturbation response (cell types / CRISPR screen / effect size) | **REFERENCE** | hand-rolled `pertpy` — install for the task (Augur / Mixscape / Distance) | `assets/references/functional.md` |
| Cross-condition DE (pseudobulk DESeq2) | **REFERENCE** | hand-rolled `pydeseq2` — already in the pinned env | `assets/references/markers_de.md` |
| Compositional analysis (did cell-type abundance shift?) | **REFERENCE** | hand-rolled `pertpy` (scCODA / Milo) — install for the task | `assets/references/composition.md` |
| Tissue enrichment / TME composition (Ro/e — describes, does not test) | **REFERENCE** | hand-rolled Ro/e — pandas + scipy, already in the pinned env | `assets/references/composition.md` |
| Trajectory / RNA velocity / fate | **REFERENCE** | hand-rolled — scVelo/CellRank pinned; Monocle3 / tradeSeq / Monocle2 install for the task | `assets/references/trajectory.md` |
| Cell-cell communication | **REFERENCE** | hand-rolled `liana` — already in the pinned env | `assets/references/ccc.md` |

Read the method doc before running a capability — each gives the opinionated default, exact parameters, failure modes, and grounding.

## Standard workflow

Run each step through `omics_compute`; read the per-step method doc for parameters and decisions.

1. **Preflight & load** — `omics_preflight(modality="scrna")`; load the h5ad; `omics_compute(subcommand="summarize", modality="scrna", args={"input":"data.h5ad"})`. Thread the summary + study description forward.
2. **QC & preprocess** — `omics_compute(subcommand="preprocess", modality="scrna", args={"input":"raw.h5ad","output":"processed.h5ad"})`. See `assets/references/qc.md` for MAD-vs-fixed thresholds, doublets, normalization.
3. **Integration (if multi-batch)** — only if a batch effect is visible. `omics_compute(subcommand="integrate", modality="scrna", args={"input":"processed.h5ad","output":"integrated.h5ad","batch-key":"batch","method":"harmony"})`. Validate with ARI/NMI (`assets/references/integration.md`).
4. **Marker genes** — `omics_compute(subcommand="marker_table", modality="scrna", args={"input":"processed.h5ad","output":"markers.csv","groupby":"leiden","min-logfc":"0.5","min-pct":"0.25"})`. See `assets/references/markers_de.md` Part A for the parameters and what `specificity` means; Part B covers cross-condition DE, which is a different question.
5. **Annotation** — thread the marker table + summary + study description into a labeling decision (`assets/references/annotation.md`); abstain to "unknown" when ambiguous.
6. **Visualize & ground** — plot UMAP colored by `cell_type`/`leiden`/QC; inspect each before it backs a claim; cite the `omics_compute` reports as evidence.

## Marker table schema (read before using markers)

`omics_compute marker_table` writes a CSV with columns: **`group`** (cluster id), **`names`** (gene), `scores`, `logfoldchanges`, `pvals`, `pvals_adj`, `pct_nz_group`, `pct_nz_reference`, `pts`, `pts_rest`, `specificity`. Group and rank with these column names — **`group`/`names`, never `cluster`/`gene`**; the wrong name is a `KeyError`, which is the good outcome.

Ribosomal / mito / MALAT1 / hemoglobin noise genes are already excluded by the subcommand.

The ranking recipe is in `assets/references/markers_de.md`.

## Annotation discipline

Cluster → marker table → label clusters from marker patterns + tissue/study context; abstain ("unknown") when markers are ambiguous. Treat any pre-existing `cell_type` column as prior annotation (compare with ARI/NMI; never copy it).

## scRNA-specific rules (on top of omics-shared)

- **Counts in `layers["counts"]`** before preprocess; the subcommand normalizes from there.
- **Integration must earn its place** — compare ARI/NMI vs known labels before/after; if biology degrades, keep the unintegrated space and say so.
- **QC removing >30% of cells** → investigate thresholds vs genuine low quality; document which (`assets/references/qc.md`).
- **Non-specific markers** → likely over-clustering; lower resolution and re-run before annotating.
- **Abstain over guess** — an ambiguous cluster is "unknown", not an invented label.

## When things go wrong

- **>50% cells dropped in QC** — thresholds too strict or low-quality data; re-run adaptive QC, document.
- **Markers non-specific** — over-clustering; reduce resolution / adjust `n_neighbors`, re-run markers.
- **Integration hurts biology** — ARI/NMI drops after integration; use unintegrated space downstream, document.
- **Ambiguous annotation** — label "unknown", record which markers were present and why ambiguous.
