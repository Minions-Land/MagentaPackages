---
name: proteomics
description: Proteomics analysis — plasma Olink targeted panels (NPX QC, paired within-subject differential expression), mass-spectrometry shotgun proteomics (MaxQuant/Perseus, log2-ratio tables), phosphoproteomics (activating-site filtering, occupancy), cross-cohort hypergeometric enrichment with correct universe, directional concordance, effect-size ranking. Use when the user has Olink NPX files, MaxQuant output, phosphoproteomics data, or asks to test differential protein expression, identify enriched pathways, or integrate proteomics with dependency/transcriptomics.
requiredTools: [run_python, bash, read, write, observe_figure]
tags: [omics, proteomics, olink, npx, mass-spec, maxquant, phosphoproteomics, differential-expression, hypergeometric, effect-size]
---

# Proteomics — Olink & Mass-Spec Differential Expression

Proteomics analysis: parse Olink NPX (Normalized Protein eXpression) with QC flags, test paired within-subject differential expression, load MaxQuant/Perseus Excel outputs (multi-header parsing), run cross-cohort hypergeometric enrichment with explicitly-defined universes, assess directional concordance, and analyze phosphoproteomics (ActivatingSite filtering, occupancy). Builds on `omics-shared` (loaded automatically — its evidence/grounding rules apply).

This is **NOT** single-cell CyTOF, **NOT** immunoassays (ELISA/Luminex raw OD), **NOT** ML training on protein features.

---

## Prerequisites

1. **Data format**: Olink NPX file (sample × protein, with QC columns), MaxQuant `proteinGroups.txt` or Perseus-exported Excel, or phosphoproteomics table
2. **Context**: sample metadata (timepoint, treatment, response) if testing paired or cross-cohort comparisons
3. **Universe definition**: for hypergeometric tests, the denominator (all proteins measured, or a biologically-defined background)

---

## Capability Menu

| Capability | Maturity | Tool/Method | Reference Doc |
|------------|----------|-------------|---------------|
| **Olink NPX** | | | |
| Load Olink NPX, parse QC flags (PASS/WARN/FAIL) | **REFERENCE** | Python | `assets/references/olink_qc_de.md` |
| Handle LOD (limit of detection) values | **REFERENCE** | Python | `assets/references/olink_qc_de.md` |
| Paired within-subject differential expression (t-test) | **REFERENCE** | `scipy.stats.ttest_rel` | `assets/references/olink_qc_de.md` |
| Effect-size ranking (by log2FC or t-statistic) | **REFERENCE** | Python | `assets/references/effect_size.md` |
| **Mass-spec (MaxQuant/Perseus)** | | | |
| Load MaxQuant proteinGroups.txt | **REFERENCE** | `pandas` | `assets/references/mass_spec_de.md` |
| Parse Perseus multi-header Excel (skip metadata rows) | **REFERENCE** | `pandas.read_excel(header=[0,1])` | `assets/references/mass_spec_de.md` |
| Log2-ratio differential expression | **REFERENCE** | Python | `assets/references/mass_spec_de.md` |
| **Phosphoproteomics** | | | |
| ActivatingSite filtering (PSP `Regulatory_sites`) | **REFERENCE** | Python (manual PSP download) | `assets/references/phosphoproteomics.md` |
| Phosphosite occupancy (phospho / total protein) | **REFERENCE** | Python | `assets/references/phosphoproteomics.md` |
| Kinase activity from phosphosites | **REFERENCE** | `decoupler` (pinned) + OmniPath `Enzsub` (`pip install omnipath`) | `assets/references/phosphoproteomics.md` |
| **Cross-cohort enrichment** | | | |
| Hypergeometric enrichment with correct universe | **REFERENCE** | `scipy.stats.hypergeom` | `assets/references/cross_cohort.md` |
| Directional concordance (upregulated in both) | **REFERENCE** | Python | `assets/references/cross_cohort.md` |
| **Visualization** | | | |
| Volcano plot (log2FC vs -log10 p) | **REFERENCE** | `matplotlib` | `../../omics-shared/AutOmicScience/assets/references/visualization.md` |

**All capabilities are REFERENCE** — but for two different reasons, and it matters which:

- **No library to defer to.** Olink's `OlinkAnalyze` is R-only with no Python port; the hypergeometric
  universe and the effect-size gate are study decisions no package can make for you. Here "hand-rolled"
  *is* the method.
- **A library exists and you should use it.** Kinase activity runs on pinned `decoupler` with an
  OmniPath network — do not hand-roll substrate aggregation. `alphastats` covers the mass-spec loader
  layer but does not install in this environment (see `mass_spec_de.md`), so that one stays hand-rolled
  by necessity, not by design.

REFERENCE means *you write the calls*, not *you reimplement the algorithm*.

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step.

### 1. Load & QC (Olink)

Read the long-format NPX table, gate on QC, pivot to samples × proteins.

- Olink ships **long**: `SampleID, Assay, NPX, QC_Warning, LOD`. Pivot before anything else
- NPX is **already log2** — do not log it again
- Gate on `QC_Warning == "PASS"`, and state how many samples that dropped

→ `assets/references/olink_qc_de.md`

### 2. Paired differential expression (Olink)

Paired t-test per protein, within subject, then BH-FDR.

- **Paired (`ttest_rel`), not independent (`ttest_ind`)** — the within-subject design removes
  between-subject variance and buys real power
- **Pair on SUBJECT, never on SampleID.** The matrix is indexed by SampleID, so two timepoint slices
  hold *disjoint* indices; pandas aligns on index and every `log2FC` becomes `NaN` — while
  `ttest_rel` still returns a t and a p, because numpy pairs positionally. The table looks like it
  ran, and `de[de.log2FC > 0.5]` then quietly returns nothing
- Argument order sets the sign of `t` — keep it matching `log2FC`
- Too few pairs is a **skip you report**, not a number you fake

→ `assets/references/olink_qc_de.md`

### 3. MaxQuant/Perseus loading

Multi-header Excel, contaminant/reverse filtering, LFQ columns.

→ `assets/references/mass_spec_de.md`

### 4. Cross-cohort hypergeometric

Test whether two cohorts' upregulated sets overlap more than chance.

- **The universe is the whole analysis** — proteins measured in *both* cohorts, not the human proteome
- **Intersect with the universe before counting.** `N = len(up_A)` counts proteins cohort B never
  measured; they are not in the urn. On a whole-proteome cohort vs an Olink panel it makes `N > M`,
  and `hypergeom.sf` then returns **`nan` without raising** — which prints as a p-value
- `sf(k-1, ...)` for P(X ≥ k), not `sf(k, ...)`

→ `assets/references/cross_cohort.md`

### 5. Effect-size ranking

- "Which changed **most**" → FDR gate first, then rank by **|effect size|**
- "Which are **most significant**" → rank by p-value; that is the right axis for *that* question
- Same analysis, different ranking axis — read the question before choosing
- **Supported across multiple modalities** → the ranking axis **is** a single combined effect-size
  score: compute the **product** (or minimum) of the per-modality effect sizes — standardizing within
  each modality first **only if** their scales differ widely enough that one would otherwise dominate —
  then **sort the candidates by it and present the ranked table**. A qualitative summary, an unranked
  list, a mean-magnitude, or alphabetical order is *not* the ranking. State the combination rule and
  whether you standardized
- **A semicolon-delimited protein/gene-ID field is a protein *group*** (multiple identifiers for one
  measurement). For cross-modality gene matching, **drop** the multi-gene (`;`) entries — do not expand
  them into separate genes; expansion fabricates matches from an ambiguous group

→ `assets/references/effect_size.md`

See `assets/references/effect_size.md`.

---

## Proteomics Best Practice (on top of omics-shared)

### 1. QC flags must be honored

Olink NPX with `QC_Warning != "PASS"` should be excluded or flagged. A WARN might be acceptable if the study tolerates it, but state the decision.

### 2. LOD (limit of detection) handling

Values below LOD are sometimes reported as `LOD - epsilon` or imputed. Document how you handle them (exclude, impute, or keep as-is with a note).

### 3. Paired tests for within-subject comparisons

Use `scipy.stats.ttest_rel` (paired t-test), not `ttest_ind` (independent). Within-subject comparisons (pre/post treatment, tumor/normal matched) have correlation.

### 4. Hypergeometric universe = proteins measured

The denominator is **all proteins measured in both cohorts**, not the full human proteome. A wrong universe inflates the enrichment p-value.

### 5. Directional concordance matters

Cross-cohort "overlap" means **directionally concordant** (both up or both down), not just significant in both. A protein up in cohort A and down in cohort B is a discordance, not a replicate.

The concordance **denominator is a decision**: features significant in *both* datasets, or the
discovery-significant features scored by the comparator's effect **sign regardless of the comparator's
own significance**. For "is signature X consistent with condition Y" questions the latter is usually
intended — restricting to doubly-significant features shrinks the denominator and silently drops
sign-flippers; state which convention you used. Report concordance by **naming the specific concordant
and discordant features**, not counts/percentages alone.

### 6. Effect-size ranking before pathway interpretation

Rank by effect size (log2FC, t-statistic), not by p-value. A protein with log2FC=0.1 and p<1e-10 (from huge sample size) is less biologically interesting than log2FC=2.0 with p=0.01.

### 7. Phosphoproteomics = site-specific

Phosphoproteomics measures **phosphosites** (e.g., `TP53_S15`), not total protein. Activating sites (kinase substrates) are a small functional subset — filter before interpretation.

### 8. Multi-arm / multi-treatment designs

Test each treatment arm **separately** and report the per-arm significant counts, then form the
cross-arm sets — **shared** (significant in all arms) vs **arm-unique**. An interaction or contrast
model across arms is a valid complement but does **not** replace the per-arm significant-set comparison
a "which features differ, and in which arm" question asks for.

### 9. Target-prioritization questions ship their own annotation table

When the objective is druggable / therapeutic-target prioritization and the data ships a companion
drug-target or annotation table, **join it to your final candidate list** and report the concrete
annotations (drug names, approval / clinical status) for the top hits. Loading the table without
surfacing its contents does not answer a prioritization question.

### 10. "Top / most X-associated" is a ranked top-N, not a threshold

When a question refers to the "top" or "most [X]-associated" features without stating a size, define that
set as a **ranked top-N small subset** (tens to low hundreds) on the association-strength metric (−log10
p or effect size), **not** a significance threshold. A p/FDR cutoff can admit most of the tested universe
— that is not a "top" set, and every overlap / hypergeometric test against it is inflated toward triviality.

---

## Pitfalls & fixes

| Symptom / mistake | Cause | Fix |
|-------------------|-------|-----|
| Hypergeometric p=1.0 or inflated enrichment | Universe too large (full proteome, not measured proteins) | Restrict the universe to proteins measured in both cohorts |
| t-test results underpowered / wrong | Unpaired `ttest_ind` on within-subject data | Use paired `ttest_rel` |
| MaxQuant columns scrambled | Multi-header Excel not parsed | `pd.read_excel(header=[0,1])` or skip metadata rows |
| Weak phosphosite enrichment | No ActivatingSite filter | Filter to kinase substrates before interpretation |
| Low cross-cohort overlap | Mismatched effect-size / FDR cutoffs, or ignoring direction | Align cutoffs; require directional concordance |
| Noisy / degraded results | WARN/FAIL QC values kept, or ranked by p-value | Filter by QC flag; rank by effect size (log2FC/t), not p |

---

## Evidence & Reporting

Every analysis emits:
- **Quantitative claims** → trailing JSON `report` with exact counts/p-values
- **Figures** → inspect the figure before citing
- **Data provenance**: Olink panel name, MaxQuant version, n_samples, n_proteins measured
- **QC decision**: which flags accepted (PASS only vs PASS+WARN)
- **Test choice**: paired vs independent, one-sided vs two-sided
- **Universe definition**: for hypergeometric, the exact denominator

See reference docs for per-analysis reporting templates.
