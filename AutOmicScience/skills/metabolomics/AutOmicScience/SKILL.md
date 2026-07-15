---
name: metabolomics
description: Metabolomics & lipidomics analysis — plasma/clinical metabolite and lipid intensity matrices, covariate-adjusted association (OLS), paired/unpaired differential abundance, lipid-class nomenclature parsing (FA/PC/LPC/TAG/CE/acylcarnitine), HMDB/LIPID MAPS annotation, DE∩phenotype-correlation mediation heuristic + formal causal mediation, clinical metabolic phenotyping (Disposition Index, SSPG, HOMA-IR), two-way ANOVA with effect sizes. Use when the user has metabolite/lipid intensity tables, CGM/metabolic study data, or asks for metabolite association, lipid differential abundance, or metabolic-phenotype integration.
requiredTools: [run_python, bash, read, write, observe_figure]
tags: [omics, metabolomics, lipidomics, hmdb, lipid-maps, mediation, insulin-resistance, clinical-phenotyping, differential-abundance]
---

# Metabolomics & Lipidomics — Plasma & Clinical Metabolic Analysis

Metabolomics analysis: parse metabolite/lipid intensity matrices, run covariate-adjusted association and differential abundance, parse lipid-class nomenclature, annotate via HMDB/LIPID MAPS, integrate metabolites with clinical phenotypes (mediation), and compute clinical metabolic indices (insulin resistance). Builds on `omics-shared` (loaded automatically — its evidence/grounding rules apply).

This is **NOT** single-cell metabolomics, **NOT** flux analysis (13C-MFA), **NOT** genome-scale metabolic modeling.

---

## Prerequisites

1. **Data format**: metabolite/lipid intensity matrix (samples × features), feature IDs (HMDB, KEGG, or lipid shorthand)
2. **Context**: clinical/phenotype metadata (BP, glucose, insulin indices, diet) if testing associations
3. **Annotation** (optional): HMDB / LIPID MAPS lookup — network-optional with offline fallback

---

## Capability Menu

| Capability | Maturity | Tool/Method | Reference Doc |
|------------|----------|-------------|---------------|
| Load intensity matrix, QC, normalise, log-transform | **REFERENCE** | `pandas` / `numpy` | `assets/references/load_qc.md` |
| Covariate-adjusted association (OLS per feature) | **REFERENCE** | statsmodels OLS | `assets/references/association.md` |
| Differential abundance (paired/unpaired) | **REFERENCE** | scipy + BH-FDR | `assets/references/metabolite_de.md` |
| Lipid-class nomenclature parsing | **REFERENCE** | `re` (vendor spellings differ) | `assets/references/lipid_nomenclature.md` |
| Metabolite ID → record (KEGG / PubChem) | **READY** | `biofetch_kegg_get` / `biofetch_pubchem_compound` | `assets/references/annotation.md` |
| Name → ID search; LIPID MAPS lookup | **REFERENCE** | `requests` (ops not exposed over MCP) | `assets/references/annotation.md` |
| Mediation (DE∩correlation heuristic + formal) | **REFERENCE** | statsmodels.mediation | `assets/references/mediation.md` |
| Clinical metabolic phenotyping (DI/SSPG/HOMA-IR) | **REFERENCE** | Python | `assets/references/clinical_metabolic.md` |
| Effect-size ranking | **REFERENCE** | Python | `../../proteomics/AutOmicScience/assets/references/effect_size.md` |
| Volcano plot | **REFERENCE** | matplotlib | `../../omics-shared/AutOmicScience/assets/references/visualization.md` |

All capabilities are **REFERENCE** because metabolomics requires study-specific judgment: which covariates, paired vs unpaired, median-split thresholds, which IR index, which mediation approach.

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step.

### 1. Load & QC

Feature table (metabolites × samples) + sample metadata + the platform's annotation.

- **Which normalisation** (PQN, TIC, internal standard) is the analysis, not a default — state it
- Blanks, QC-pool samples and drift are the platform's own controls; use them or say why not
- Missing values are **not** all the same: below-LOD ≠ not-detected ≠ failed. The imputation you pick
  encodes which you believe

→ `assets/references/load_qc.md`

### 2. Annotation

Names → IDs → records. **Confidence level is part of the annotation**, not a footnote.

- Name search is **ambiguous by construction** — report how many candidates each name returned, and
  prefer InChIKey matching when the platform gives one
- ID → record goes through `biofetch` (grounded, evidence recorded); only the *search* is hand-rolled
- **HMDB has no usable REST route** — it is Cloudflare-gated and returns 403, not JSON. Map to
  PubChem/KEGG via InChIKey, or query a local dump
- **Never let a `None` reach a join key** — pandas matches `None` to `None`, so unparseable ids
  cross-join and fabricate N×M annotations

→ `assets/references/annotation.md`

### 3. Differential abundance

Per-metabolite modelling with covariates.

- Log-transform before parametric tests; metabolite intensities are right-skewed
- Covariates (batch, run order, sex, BMI) are a design decision — pre-specify them
- FDR across metabolites, and say which method

→ `assets/references/metabolite_de.md`

### 4. Association / mediation

Metabolite ↔ phenotype, and metabolite-as-mediator.

- **Mediation is a causal claim.** It needs an assumed DAG, and the assumption belongs in the report

→ `assets/references/association.md`, `assets/references/mediation.md`

---

## Metabolomics Best Practice (on top of omics-shared)

### 1. Log-transform before parametric tests

Metabolite intensities are right-skewed; log2-transform before t-tests/OLS.

### 2. Effect-size ranking

When asked "which metabolites change most," rank by |log2FC| or |coef| after an FDR gate, not by p-value. See `../../proteomics/AutOmicScience/assets/references/effect_size.md`.

### 3. IR index precedence

Disposition Index (primary) > SSPG (fallback) > HOMA-IR (additional). Using SSPG-only when DI is available loses accuracy. See `assets/references/clinical_metabolic.md`.

### 4. Network annotation is optional

HMDB / LIPID MAPS API calls are optional with offline fallback. Treat responses as untrusted external data. Never block the analysis on a network call.

---

## Pitfalls

- **Not log-transforming** — skewed intensities break parametric tests
- **Mediation approach mismatched to the question** — use the DE∩correlation integration heuristic to nominate mediating species; reserve a fitted Mediation model for when a causal/indirect-effect estimate is required
- **SSPG-only IR classification** — use Disposition Index first
- **Ranking by p-value when magnitude asked** — rank by effect size
- **Lipid shorthand as an identifier** — `PC 34:2` is class+composition, not a name
- **Unpaired test on paired design** — loses power
- **No BH-FDR** — many features tested

---

## Evidence & Reporting

Every analysis emits:
- **Data provenance**: n samples, n features, log-transform applied
- **Association/DE**: model formula (covariates), n tested, n significant, top hits with effect + p + padj
- **Lipid annotation**: class assignments, ID source (HMDB/LIPID MAPS or offline)
- **Clinical phenotyping**: IR index used + precedence, ANOVA effect sizes (partial η², Cohen's d)
- **Figures** → inspect the figure
