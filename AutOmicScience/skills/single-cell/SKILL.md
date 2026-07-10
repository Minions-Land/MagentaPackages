---
name: single-cell
description: Single-cell omics analysis (RNA-seq, ATAC-seq, multiome) — QC, preprocessing, integration, clustering, annotation, trajectory, cell-cell communication, chromatin accessibility, joint embeddings. Use when the user asks to analyze single-cell RNA-seq data (scRNA-seq, 10x), single-cell ATAC-seq (scATAC-seq, chromatin accessibility), or paired multiome (RNA+ATAC) datasets.
requiredTools: [run_python, create_notebook, add_cell, observe_figure, omics_preflight, omics_compute]
tags: [omics, single-cell, scrna, scatac, multiome, scanpy, scverse, muon, snapatac2]
extends: omics-shared
---

# Single-Cell Omics Analysis

Single-cell work routes to a **modality subskill**. This parent only does routing plus the single-cell-wide notes; the shared compute/evidence/grounding contract lives in `omics-shared` (loaded automatically — don't restate it), and the step-by-step recipes live in each subskill.

## Routing: which subskill?

| Your data | Subskill | When |
|-----------|----------|------|
| **scRNA-seq** — gene expression (10x, Drop-seq, SMART-seq; `.h5ad`/`.h5` counts) | `rna/SKILL.md` | Count matrices of gene expression |
| **scATAC-seq** — chromatin accessibility (`fragments.tsv.gz`, peak/tile matrices) | `atac/SKILL.md` | Accessibility data |
| **Multiome** — paired RNA+ATAC from the same nuclei (`.h5mu`) | `multiome/SKILL.md` | Simultaneously measured RNA+ATAC |

**Don't guess the modality** — infer from the data (`.h5ad` gene counts → scRNA; `fragments.tsv.gz` → scATAC; `.h5mu` or "paired"/"multiome" → multiome) or ask. The subskills are chapters of this skill and cannot be invoked independently; after identifying the modality, read the matching one.

## Single-cell-wide notes (details in `omics-shared` + the subskill)

- **Workflow shape** — preflight → load → `summarize` → thread context → QC → cluster → annotate → visualize & ground. The `omics_compute` call pattern, AnnData conventions, and the evidence/grounding rules all come from `omics-shared`.
- **Container** — AnnData (scRNA/scATAC) or MuData (multiome); raw counts in `layers["counts"]`, never overwritten.
- **Integration** — only when a batch effect is visible; validate with ARI/NMI and keep the unintegrated space if biology degrades. Method differs by modality (Harmony/scVI for scRNA, SnapATAC2 for scATAC, WNN/MultiVI for multiome) — see the subskill.
- **Annotation** — abstain over guess; treat any pre-existing `cell_type` column as prior annotation (compare with ARI/NMI, never copy). Marker+LLM vs reference-pipeline routes are detailed in `rna/`.
- **Troubleshooting** — QC over-drop, clusters tracking technical variables, non-specific markers, integration hurting biology, ambiguous labels: each subskill has the modality-specific failure table.

## Next

Read the matching subskill — `rna/SKILL.md`, `atac/SKILL.md`, or `multiome/SKILL.md` — for its capability menu (with maturity), the exact `omics_compute` calls, method-doc references, and modality-specific rules and troubleshooting.
