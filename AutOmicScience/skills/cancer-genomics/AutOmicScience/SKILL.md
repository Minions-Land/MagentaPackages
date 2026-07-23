---
name: cancer-genomics
description: Tabular cancer genomics analysis — MAF/CNA somatic mutation and copy-number alteration parsing, variant classification (pathogenic/LoF vs benign), per-patient gene recurrence, tumor mutational burden (TMB), copy-number burden, pathway-alteration gene-set analysis, hotspot/protein-domain filtering, mutation×phenotype association (Fisher exact + FDR), oncoplots (maftools-style). Use when the user has MAF files, CNA segment files, or asks to analyze somatic mutations, identify recurrently altered genes, compute TMB, test mutation-phenotype associations, or generate oncoplots.
requiredTools: [run_python, bash, read, write, observe_figure, omics_preflight, omics_compute]
tags: [omics, cancer, genomics, maf, cna, somatic-mutations, tmb, oncoplot, variant-classification, fisher-test]
---

# Cancer Genomics — Tabular Somatic Mutation & CNA Analysis

Tabular cancer genomics: parse MAF (Mutation Annotation Format) and CNA (copy-number alteration) files, classify variants by pathogenicity, compute per-patient gene recurrence and TMB, identify hotspots and protein-domain enrichments, test mutation×phenotype associations with Fisher exact + FDR, and generate oncoplots. Builds on `omics-shared` (loaded automatically — its evidence/grounding rules apply).

This is **NOT** germline GWAS, **NOT** WGS/WES alignment/calling (assumes MAF already generated), **NOT** ML training on mutation features.

---

## Prerequisites

1. **Data format**: MAF file (tab-delimited, standard TCGA/GDC columns) or CNA segment file
2. **Context**: `omics_compute summarize` on the MAF to thread sample counts + cancer types forward
3. **Clinical annotation**: patient metadata table (response, stage, survival) if testing associations

Common MAF columns: `Hugo_Symbol`, `Chromosome`, `Start_Position`, `End_Position`,
`Variant_Classification`, `Variant_Type`, `Tumor_Sample_Barcode`, `HGVSp_Short`, `Protein_position`.

**Read the header; do not index by position or assume a column exists.** "MAF" is a family, not a
format. Exports differ by the pipeline that wrote them: some carry `Protein_Change` (an
Oncotator/Firehose column, absent elsewhere), and many insert `Consequence` ahead of
`Variant_Classification`, shifting every later column by one against the GDC spec. Two files from the
same portal can disagree on both.

> **The cohort is not "the samples in the MAF".** Filtering to pathogenic variants drops every patient
> whose calls were all silent, and a tumour with zero calls never appears in the MAF at all. Pin
> `cohort` **before** filtering and reindex onto it — otherwise recurrence frequencies, TMB medians and
> Fisher tables are all computed over "mutated patients" instead of the cohort. See `recurrence.md`.

---

## Capability Menu

| Capability | Maturity | Tool/Method | Reference Doc |
|------------|----------|-------------|---------------|
| **Data loading & context** | | | |
| Load MAF → count variants, samples, genes | **READY** | `omics_compute load_dataset` | `assets/references/file_formats.md` |
| Summarize dataset (n_samples, n_variants, cancer distribution) | **READY** | `omics_compute summarize` | `../../omics-shared/AutOmicScience/assets/references/data_context.md` |
| **Variant classification** | | | |
| Pathogenic variant filtering (CGC tiers 1/2, LoF, activating-mut) | **REFERENCE** | Python | `assets/references/variant_classification.md` |
| Silent/benign exclusion | **REFERENCE** | Python | `assets/references/variant_classification.md` |
| **Gene-level recurrence** | | | |
| Per-patient gene alteration (any pathogenic mut) | **REFERENCE** | Python | `assets/references/recurrence.md` |
| Recurrence frequency ranking | **REFERENCE** | Python | `assets/references/recurrence.md` |
| Minimum-support filtering (≥5 patients) | **REFERENCE** | Python | `assets/references/recurrence.md` |
| **Mutation burden** | | | |
| TMB (tumor mutational burden: variants/Mb) | **REFERENCE** | Python | `assets/references/tmb.md` |
| TMB distribution (median + IQR, not mean±SD) | **REFERENCE** | Python | `assets/references/tmb.md` |
| **Copy-number analysis** | | | |
| CNA segment loading (chrom, start, end, log2ratio) | **REFERENCE** | Python | `assets/references/cna.md` |
| Gene-level CN call (amp/gain/neutral/loss/del) | **REFERENCE** | Python | `assets/references/cna.md` |
| CNA burden (fraction of genome altered) | **REFERENCE** | Python | `assets/references/cna.md` |
| **Pathway & hotspot** | | | |
| Pathway-alteration frequency (gene-set any-hit) | **REFERENCE** | Python | `assets/references/pathway_alteration.md` |
| Hotspot identification (recurrent protein position) | **REFERENCE** | Python | `assets/references/hotspots.md` |
| Protein-domain filtering (e.g., ESR1 LBD 300–550) | **REFERENCE** | Python | `assets/references/hotspots.md` |
| **Association testing** | | | |
| Mutation×phenotype Fisher exact + FDR | **REFERENCE** | Python | `assets/references/association.md` |
| One-sided vs two-sided test selection | **REFERENCE** | Python | `assets/references/association.md` |
| Minimum-support gate (drop singleton-mutated genes) | **REFERENCE** | Python | `assets/references/association.md` |
| **Visualization** | | | |
| Oncoplot — via `comut` | **PARTIAL** | `comut` — **not pinned**, provision first | `assets/references/oncoplot.md` |
| Oncoplot — hand-rolled matplotlib | **REFERENCE** | `matplotlib` — pinned | `assets/references/oncoplot.md` |
| TMB distribution histogram | **REFERENCE** | Python | `../../omics-shared/AutOmicScience/assets/references/visualization.md` |

Everything except the `comut` oncoplot is **REFERENCE** (hand-rolled Python on the pinned stack)
because mutation analysis requires study-specific judgment: which variants are pathogenic (CGC tiers,
LoF rules), which genes belong to a pathway, which protein domains matter, Fisher sidedness, FDR
method. These are deliberate design decisions (like DE contrasts in bulk-RNA), not black-box
automation.

**`comut` is PARTIAL** — it is in no `task1–4` env, so provision it per `omics-shared`'s
`assets/references/AOSE_nonStandard_env.md` before use, or take the matplotlib route in
`oncoplot.md`. (Its API is verified against v0.0.3: import the **submodule**, `from comut import
comut` — `comut/__init__.py` is empty, so `from comut import CoMut` raises `ImportError`.)

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step.

### 1. Load & pin the cohort

Read the MAF, then capture the sample list **before any filtering**. Everything downstream divides by
it. `omics_compute summarize` threads the counts forward.

- The cohort is *not* "the samples left after filtering" — see the callout in Prerequisites
- A tumour with zero calls is absent from the MAF entirely; take the cohort from the sample manifest
  or clinical table when one exists

→ `assets/references/file_formats.md`, and `assets/references/recurrence.md` for the cohort rule

### 2. Variant classification

Filter to pathogenic mutations. **This is a design decision, not a default** — state which rule you used.

- Baseline: keep the protein-altering classes, drop Silent / Intron / UTR / IGR
- Grounded: CGC tier 1/2 gene-context rules — any LoF in a TSG, but only *hotspot* missense in an
  oncogene. "All missense is pathogenic" inflates every oncogene's recurrence
- Sources: Cancer Gene Census, COSMIC hotspots, ClinVar — name the one you used
- **Prefer the file's own annotation columns.** Many MAFs carry curated driver flags — Cancer-Gene-Census
  membership, OncoKB / hotspot annotations, or any curated driver flag the file already carries. Define
  the oncogenic set by **unioning** the non-silent functional classes with those columns, not a
  hand-curated literature gene list, which silently drops drivers the file already flags
- **Activating / resistance-mutation questions** → make the **domain- or hotspot-restricted rate the
  primary definition** (activating and resistance mutations cluster in a functional domain or hotspot);
  report the whole-gene alteration rate only as a secondary / sensitivity check, because a whole-gene
  rate dilutes the driver signal. Take domain coordinates from UniProt / Pfam and cite them

→ `assets/references/variant_classification.md`

### 3. Gene recurrence

Collapse to a **per-patient binary** alteration matrix, then reindex onto the cohort.

- Per-patient, not per-mutation: one hypermutator otherwise dominates every gene's frequency
- **Reindex, or every frequency is inflated by the same factor.** `groupby` emits no row for a
  mutation-free patient, so `len(altered)` counts *mutated* patients. The ranking still looks right —
  that is what makes it survive review. Measured: TP53 reads 66.7% where the truth is 40%
- Report `n_altered/n_total`, never the percentage alone

→ `assets/references/recurrence.md`

### 4. TMB

Count **non-synonymous** variants per sample, normalise per Mb.

- The class set is *broader* than step 2's pathogenic filter — it adds `Nonstop_Mutation` and
  `Translation_Start_Site`. Two different questions, two different sets
- Panel size is yours to state: MSK-IMPACT ≈ 1.2 Mb, WES ≈ 30–50 Mb
- **Median + IQR, never mean±SD** — hypermutators make the distribution right-skewed
- Same reindex trap as step 3: a zero-TMB tumour is a data point, not a gap. Dropped, the median
  reads 1.4× high and the IQR loses its lower tail — exactly the tail a TMB-high split turns on

→ `assets/references/tmb.md`

### 5. Association testing

Fisher exact per recurrent gene, then BH-FDR.

- Sidedness is a choice: two-sided for "is it associated", one-sided `less` for mutual exclusivity
- Gate on **minimum support** (≥5 altered patients) *before* FDR — it shrinks the family and buys power
- **The 2×2 must sum to the cohort.** `is_altered & pheno` aligns and fills, so `a`/`b` come out right;
  `~is_altered` does *not* align, so `c`/`d` quietly lose every mutation-free patient. Measured: a
  table summing to 80 instead of 120 turned p = 0.0001 into p = 0.078. `assert` the total — the bug
  has no other symptom

→ `assets/references/association.md`

### 6. Oncoplot

Genes × patients, coloured by alteration type, memo-sorted.

- `comut` is **not pinned** — provision it, or take the matplotlib route in the ref doc
- It wants **tidy long** data (one row per sample × gene × alteration type). A binarised 0/1 matrix
  cannot make an oncoplot at all: there is no alteration type to colour
- Import the **submodule** (`from comut import comut`) — `comut/__init__.py` is empty
- Render and **inspect** it before it backs any claim

→ `assets/references/oncoplot.md`

---

## Cancer Genomics Best Practice (on top of omics-shared)

### 1. Variant classification must be grounded

Don't invent pathogenicity rules — use CGC (Cancer Gene Census) tiers 1/2 for oncogenes/TSGs, or COSMIC hotspots, or ClinVar pathogenic. Document which classification you used.

### 2. TMB = median + IQR, not mean ± SD

TMB distribution is right-skewed (hypermutators). Report median and interquartile range.

### 3. Pathway alteration = any-hit gene-set

A pathway is "altered" if ≥1 gene in the set has a pathogenic mutation. Don't sum mutation counts — that double-counts patients with multiple hits.

When a question names a signaling pathway, **define its gene set from a named curated source** (MSigDB
Hallmark / KEGG / Reactome, or an established pathway paper) and use the **full membership** — do not
hand-pick a few "canonical" genes or narrow the set to sharpen the story. A hand-drawn subset changes
the reported frequency and cannot be audited. Apply the per-member event rule (LoF / deletion for
tumour suppressors; hotspot-missense / amplification for oncogenes), not a blanket "any protein-altering".

### 4. Fisher test sidedness matters

- **Two-sided**: enrichment or depletion (most associations)
- **One-sided (`alternative="less"`)**: mutual exclusivity (e.g., KRAS/BRAF in melanoma)

Document which you used and why.

### 5. Minimum cell count for Fisher

Expected count ≥5 in all 2×2 cells, or use Fisher exact (not chi-squared). Filter out singleton-mutated genes before FDR correction.

### 6. Clinical variable normalization

- Collapse T1/T1a/T1b → T1; N0/Nx → N0. Use the coarsest available stage.
- Prefer pathologic (PATH_) over clinical (CLIN_) when both exist.
- Drop "Discrepancy" rows.

### 7. Every oncoplot → inspect it

Never cite an oncoplot you didn't render and inspect.

---

## Pitfalls & fixes

| Symptom / mistake | Cause | Fix |
|-------------------|-------------------|-----|
| Every gene's frequency looks high (ranking still plausible) | Denominator is mutated patients, not the cohort — `groupby` never emits a row for a mutation-free patient | Pin `cohort` before filtering; `.reindex(cohort, fill_value=False)`; divide by `len(cohort)` |
| TMB median too high, IQR has no low tail | Zero-TMB samples dropped by `groupby().size()` | `.reindex(cohort, fill_value=0)`; report `n` beside the median |
| `KeyError: "[...] not in index"` on `tmb[sample_list]` | A sequenced sample had zero non-syn calls | `.reindex(...)` — and note this is the *loud* version of the bug above |
| Fisher 2×2 doesn't sum to the cohort | `~is_altered` evaluated on an unaligned Series — `a`/`b` align, `c`/`d` don't | Reindex `is_altered` onto the phenotype index, then `assert` the total |
| `ImportError: cannot import name 'CoMut'` | `comut/__init__.py` is empty | `from comut import comut` (the submodule), then `comut.CoMut()` |
| Recurrence / TMB looks wrong | Silent variants counted | Count only non-silent; filter to pathogenic (`variant_classification.md`) |
| Ungrounded pathogenicity | All Missense treated pathogenic, or Nonsense excluded | Use CGC / COSMIC / ClinVar tiers; document the rule |
| TMB outliers dominate | Mean ± SD on a right-skewed distribution | Report median + IQR |
| Pathway frequency > 100% | Summing hits instead of any-hit | `.any()` per gene set, not `.sum()` (one patient counts once) |
| Fisher p-values all 1.0, or exclusivity missed | Wrong contingency orientation, or two-sided test for exclusivity | Check crosstab / binary `gene_mut`; use `alternative="less"` for exclusivity |
| Inflated FDR family | No minimum-support gate (singleton-mutated genes) | Require a stated **minimum support** (e.g. ≥5 mutated samples) and drop singletons **before** FDR. Do *not* gate on "expected ≥5 per cell" — that is the **chi-squared** validity rule; Fisher exact is valid at small counts, which is exactly why it's the test here, so that gate would discard valid tests |
| Lost power / leakage in clinical association | Uncollapsed substages, or "Discrepancy" / mixed PATH+CLIN rows | Collapse T1a/b→T1, N0/Nx→N0; prefer PATH_; drop Discrepancy |
| Oncoplot shows "?" or is uncited | Gene-name mismatch (HGNC vs alias), or figure not inspected | Standardize to HGNC; render + inspect before citing |

---

## Evidence & Reporting

Every analysis emits:
- **Quantitative claims** → trailing JSON `report` with exact counts/p-values
- **Figures** → inspect before citing
- **MAF provenance**: source (TCGA/GDC/local), n_samples, n_variants, cancer types
- **Variant-classification rule**: which pathogenicity criteria (CGC/COSMIC/ClinVar)
- **Association test**: Fisher sidedness, FDR method, minimum-support gate
- **Recurrence vs association contrast**: when both are computed, state them side by side — name the
  most-frequent genes that are **not** outcome-associated, and the associated genes that are not the most
  frequent; the two lists are rarely identical, and reporting both distinguishes recurrence from
  outcome-association
- **Biological consequence of each key gene**: for an outcome-associated driver, state its known
  functional consequence and therapeutic implication with a citation — a bare gene name and a p-value is
  a result, not an interpretation

See reference docs for per-analysis reporting templates.
