---
name: bulk
description: Bulk RNA & epigenomics analysis — normalization (TMM / VST / logCPM), count-based differential expression (DESeq2 / edgeR / limma-voom) including continuous-trait designs, pathway enrichment (GSEA / ORA on a gene list), co-expression networks (WGCNA) and gene-set coherence; ChIP-seq / bulk ATAC-seq peak files (narrowPeak / BED / BAM) — differential occupancy, TSS annotation, chromatin accessibility. Use when the user has a bulk or pseudobulk gene-count matrix with sample metadata, a peak/BAM set from ChIP-seq or bulk ATAC-seq, a bare gene list, or a pre-computed differential-expression table (DESeq2 / edgeR / Cuffdiff `gene_exp.diff`) to interpret. Not single-cell data.
requiredTools: [run_python, bash, read, write, omics_preflight, omics_compute]
tags: [omics, bulk, bulk-rna, rna-seq, differential-expression, deseq2, gsea, wgcna]
---

# Bulk Omics Analysis

Bulk work routes to a **subskill** by data type. This parent does routing plus the bulk-wide statistical notes; the shared compute/evidence/grounding contract lives in `omics-shared` (loaded automatically — don't restate it), and the recipes live in each subskill.

## Routing: which subskill?

| Your data | Subskill | When |
|-----------|----------|------|
| **Bulk RNA-seq** (gene-count matrix) | `rna/SKILL.md` | Bulk/pseudobulk gene counts + sample metadata: count-based DE, normalization, GSEA/ORA, WGCNA |
| **ChIP-seq / bulk ATAC-seq** (peak files) | `epigenomics/SKILL.md` | Peak BED files: differential occupancy/accessibility, TSS annotation, histone marks, TF footprinting |

**Bulk vs single-cell:** a gene × sample count matrix (dozens of samples) is bulk; cells × genes with per-cell resolution is the `single-cell` skill. Single-cell summed to donor/group level (**pseudobulk**) is analyzed here with bulk methods. The subskills are chapters of this skill and cannot be invoked independently.

## Bulk-wide notes (details in `omics-shared` + the subskill)

- **Tabular, counts-first** — a gene × sample **raw integer count** matrix + a sample metadata table; never start DE from TPM/FPKM/normalized values. You may `omics_compute load_dataset` a count matrix into AnnData to reuse the grounded `enrichment`/`pathway_activity` subcommands, but the count-model steps (DE, normalization, WGCNA) are hand-written Python/`Rscript`.
- **Know what is installed before you plan.** There is no `bulk` modality — pass **`modality="scrna"`**, the
  environment selector for `task1`, where the bulk Python stack lives (`pydeseq2`, `decoupler`, `scipy`,
  `statsmodels`). **The R stack is absent** (`DESeq2`/`edgeR`/`limma`/`WGCNA`), and so is most of the
  epigenomics toolchain (`pyranges`/`gtfparse`/`bedtools`/`TOBIAS`/`ChIPseeker`/`DiffBind`). Each subskill's
  menu marks what runs today (**READY** = `omics_compute` subcommand; **REFERENCE** = library present, you
  write the script) vs what must be **provisioned first** (**PARTIAL** = not in any env). For PARTIAL,
  follow `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` — a Pixi env of your own beside the
  analysis outputs, or a named conda env; never `base`, never a bare `pip install`, never new pins in `task1–4`.
- **Count-based models** — raw counts → DESeq2/edgeR/limma-voom (negative-binomial / voom); a Welch t-test or OLS on log-CPM is statistically weaker. Normalize by goal: VST/rlog for clustering/PCA, TMM+logCPM or size-factors for the DE model input; never z-score raw counts.
- **Effect size ≠ significance** — shrink fold changes (apeglm/ashr) before ranking or GSEA; rank by shrunken |log2FC| with an FDR gate, and report both axes.
- **Model covariates in the design** — batch/sex/age/RIN/library-prep/site when present; an unmodeled confound is the most common silent error. State the design formula.
- **State your conventions** — normalization, shrinkage estimator, ranking metric, FDR method, background universe: a result is only reproducible alongside its method. (Evidence/grounding rules and figure inspection: `omics-shared`.)

## Next

Read the subskill matching your data (`rna/` for bulk RNA-seq, `epigenomics/` for ChIP-seq / bulk ATAC-seq) for its capability menu, method docs, opinionated defaults, exact parameters, and failure modes.
