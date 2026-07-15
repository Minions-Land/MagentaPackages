---
name: microbiome
description: Microbiome analysis — 16S rRNA amplicon (OTU/ASV tables) and shotgun metagenomic taxonomic/functional abundance profiles, CLR transformation, alpha/beta diversity, differential abundance (DESeq2/ANCOM/ALDEx2), taxonomy filtering, survival integration. Use when the user has microbial abundance tables (taxa × samples), asks for diversity analysis, taxon differential abundance, or microbiome-phenotype association.
requiredTools: [run_python, bash, read, write, observe_figure]
tags: [omics, microbiome, 16S, metagenomics, taxonomy, diversity, clr, differential-abundance, ancom, aldex2]
---

# Microbiome Analysis — 16S & Metagenomics

Microbiome analysis: parse 16S OTU/ASV or metagenomic taxonomic abundance tables, apply CLR transformation, compute alpha/beta diversity, test differential abundance (DESeq2/ANCOM/ALDEx2), integrate with clinical phenotypes (Cox survival, correlation). Builds on `omics-shared` (loaded automatically — its evidence/grounding rules apply).

This is **NOT** assembly/binning, **NOT** functional annotation (KEGG/MetaCyc pathways are out of scope for this lightweight skill).

---

## Prerequisites

1. **Data format**: taxa × samples abundance matrix (counts or relative abundance), taxonomy table (Kingdom→Species)
2. **Context**: sample metadata (condition, patient ID, clinical covariates) for differential/association tests
3. **Library**: `scikit-bio` (diversity), `pydeseq2` (DE), or R via rpy2 (`DESeq2`, `ALDEx2`, `ANCOM`)

---

## Capability Menu

| Capability | Maturity | Tool/Method | Reference Doc |
|------------|----------|-------------|---------------|
| Load abundance table, taxonomy filtering | **REFERENCE** | Python | `assets/references/abundance_loading.md` |
| CLR transformation | **REFERENCE** | `scipy` `gmean` (pinned) — or `scikit-bio` `clr`+`multi_replace` if provisioned | `assets/references/abundance_loading.md` |
| Alpha diversity (Shannon, Chao1, Faith PD) | **PARTIAL** | `scikit-bio` — not pinned, provision first | `assets/references/diversity.md` |
| Beta diversity (Bray-Curtis, UniFrac) + PCoA + PERMANOVA | **PARTIAL** | `scikit-bio` — not pinned, provision first | `assets/references/diversity.md` |
| Differential abundance — DESeq2 | **REFERENCE** | `pydeseq2` — **pinned** | `assets/references/differential_abundance.md` |
| Differential abundance — ANCOM-BC / ANCOM | **PARTIAL** | `scikit-bio` — not pinned, provision first | `assets/references/differential_abundance.md` |
| Differential abundance — ALDEx2 | **PARTIAL** | R + Bioconductor + `rpy2`; expensive to provision — prefer ANCOM-BC | `assets/references/differential_abundance.md` |
| Taxon-phenotype association (Cox survival) | **PARTIAL** | `lifelines` — not pinned, provision first | `../../clinical-survival/AutOmicScience/assets/references/cox_ph.md` |

## Provision one environment for the whole workflow

A real microbiome analysis crosses the pinned/PARTIAL line in a single run: loading + CLR on pinned
`scipy`/`pandas`, DESeq2 on pinned `pydeseq2`, but diversity on `scikit-bio` and per-taxon Cox on
`lifelines` — neither of which `task1–4` has. **Do not split it across two interpreters**; provision
one env that composes the pinned stack plus the extras, and run every step there:

```toml
# tools/omics-environment/pixi.toml
[feature.microbiome.dependencies]
scikit-bio = "*"
lifelines = "*"

[environments]
microbiome = { features = ["core", "singlecell", "microbiome"], solve-group = "microbiome" }
```

```bash
pixi install --manifest-path tools/omics-environment/pixi.toml -e microbiome
pixi lock    --manifest-path tools/omics-environment/pixi.toml
```

**`["core", "singlecell", ...]`, not `["core", ...]`** — `core` is only jupyterlab/h5py/mudata; the
stack you import (scanpy, and through it pandas/numpy/scipy, plus `pydeseq2`) lives in `singlecell`,
which is why every `task1–4` composes both. The separate `solve-group` keeps these pins away from
`task1–4`. Full protocol: `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`.

`omics_preflight` does not cover this env — check the imports yourself and record the env + versions
in the `report`.

All capabilities are **REFERENCE** because microbiome analysis requires study-specific judgment: taxonomy filtering (prevalence thresholds, low-count taxa), rarefaction vs CLR, which diversity metric, which DA method (compositional vs count-based).

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step.

### 1. Load abundance table

Taxa × samples counts, plus a taxonomy table.

- Analyse at the **finest reliable level** (Genus/Species for 16S, Species for shotgun). Phylum-level
  DE discards the signal
- Deduplicate multi-sample subjects before anything downstream

→ `assets/references/abundance_loading.md`

### 2. Prevalence filtering

Drop taxa present in <10% of samples.

- The threshold is a **choice** — state it, and report n taxa before/after. It sets the FDR family size

→ `assets/references/abundance_loading.md`

### 3. CLR transformation

Microbiome counts are compositional; CLR removes the sum-to-constant constraint.

- **Zeros are the whole problem.** CLR takes a log ratio, so every zero must be replaced first — and
  *how* changes the answer
- `multi_replace` (multiplicative) swaps zeros for a small δ **and rescales each sample back to sum 1**,
  keeping the object a composition. A `+1` pseudocount also yields a valid CLR — but of a *shifted*
  composition. The two differ by up to ~1 natural-log unit on sparse tables, most for the low-count
  taxa a microbiome study is about
- If you take the `+1` route, **say so** — don't call it "CLR" unqualified

→ `assets/references/abundance_loading.md`

### 4. Diversity — PARTIAL

Alpha (Shannon, Chao1, Faith PD) and beta (Bray-Curtis, UniFrac) + PCoA + PERMANOVA.

- `scikit-bio` takes **samples in rows** — transpose the taxa × samples table
- Non-parametric group comparison (Mann-Whitney / Kruskal); diversity is not normal
- PERMANOVA needs a **distance matrix**, and its p-value is permutation-based — report the n_perm

→ `assets/references/diversity.md`

### 5. Differential abundance

DESeq2 (pinned) is the one path that runs today; ANCOM-BC is the compositional cross-check.

- **DESeq2 wants raw counts** — never feed it CLR-transformed data
- Include batch (sequencing run, extraction kit) as a covariate; microbiome data is batch-dominated
- Validate with **ANCOM-BC** if compositionality is a concern — same rigour, and it takes covariates,
  unlike original ANCOM (whose `W` is a rank statistic, not a p-value)

→ `assets/references/differential_abundance.md`

---

## Microbiome Best Practice (on top of omics-shared)

### 1. Compositional data requires CLR

Microbiome counts are compositional (sum-to-1 constraint). Raw counts violate independence assumptions. **CLR transformation** (centered log-ratio) is the standard for parametric tests. Rarefaction (subsampling to even depth) is deprecated for DE.

### 2. Prevalence filtering

Low-prevalence taxa (present in <10% of samples) are noise. Filter before DE to reduce multiple-testing burden.

### 3. Taxonomy level matters

Analyze at the finest reliable level (usually Genus or Species for 16S; Species for shotgun). Aggregating to Phylum loses signal.

### 4. Zero-inflation

Many taxa are absent (true zeros) or undetected (sampling zeros). DESeq2 handles this via negative-binomial. ANCOM/ALDEx2 are compositionally-aware alternatives.

### 5. Batch effects (sequencing run, DNA extraction kit)

Microbiome data is highly batch-sensitive. Include `batch` as a covariate in the design, or use ComBat-seq for correction.

---

## Pitfalls

- **Not CLR-transforming for parametric tests** — raw counts violate assumptions
- **No prevalence filter** — testing thousands of rare taxa inflates FDR
- **Wrong taxonomy level** — Phylum-level DE loses Genus/Species signal
- **Rarefaction for DE** — deprecated; loses information
- **Ignoring batch effects** — sequencing run dominates biological signal
- **Treating absence as zero abundance** — absence may be biological or technical

---

## Evidence & Reporting

Every analysis emits:
- **Data**: n samples, n taxa (before/after filtering), taxonomy level, sequencing depth per sample
- **Transformation**: CLR / log+pseudocount / raw counts (state which)
- **Diversity**: alpha metric + group comparison (stat + p), beta metric + PERMANOVA
- **DA**: method (DESeq2/ANCOM/ALDEx2), n tested, n significant (padj<0.05), top taxa with log2FC + padj
- **Figures** → inspect the figure

See reference docs for per-analysis reporting templates.
