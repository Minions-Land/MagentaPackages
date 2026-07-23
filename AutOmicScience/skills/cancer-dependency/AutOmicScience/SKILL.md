---
name: cancer-dependency
description: Cancer functional genomics & dependency analysis — DepMap/CCLE CRISPR gene-effect screens (dependency scoring, normLRT selective-dependency test), Pharos druggability annotations (Tclin/Tchem/Tbio/Tdark tiers), therapeutic-window prioritization, synthetic lethality discovery (mutual-exclusivity Fisher test, paralog/PPI priors, BRCA-PARP canonical pairs), multi-omic integration (dependency + phosphoproteomics/expression/MAF). Use when the user has DepMap data, asks to identify druggable dependencies, selective vulnerabilities, synthetic-lethal gene pairs, or integrate dependency screens with other omics.
requiredTools: [run_python, bash, read, write]
tags: [omics, cancer, dependency, depmap, ccle, crispr, druggability, pharos, synthetic-lethality, normLRT]
---

# Cancer Dependency — DepMap & Druggability Analysis

Cancer dependency analysis: parse DepMap/CCLE CRISPR gene-effect screens, identify selective dependencies vs pan-essential genes, test selective-dependency with normLRT, annotate druggability (Pharos/TTD), apply therapeutic-window prioritization, discover synthetic-lethal pairs via mutual-exclusivity + paralog/PPI priors, and integrate with phosphoproteomics/expression/MAF. Builds on `omics-shared` (loaded automatically — its evidence/grounding rules apply).

This is **NOT** GWAS, **NOT** germline genetics, **NOT** ML training on dependency features.

---

## Prerequisites

1. **Data format**: DepMap CRISPR gene-effect matrix (**cell lines × genes**, Chronos scores), or pre-computed dependency calls
2. **Context**: cell-line metadata (cancer type, lineage, mutation status) if testing selective dependencies
3. **Druggability sources**: Pharos (GraphQL API or TCRD download), Therapeutic Target Database (TTD), or DrugBank

DepMap releases quarterly. The current file is **`CRISPRGeneEffect.csv`**: rows = `ModelID`
(`ACH-######`), columns = `SYMBOL (EntrezID)` (e.g. `A1BG (1)`), values ≈ −2 to +0.5.

> **Two things break every script written from memory.** The matrix is **cell lines × genes**, not
> genes × cell lines. And the names changed: `CRISPR_gene_effect.csv` → `CRISPRGeneEffect.csv`,
> `sample_info.csv` → `Model.csv`, `DepMap_ID` → `ModelID` (at 23Q2), `lineage` → `OncotreeLineage`.
> Scripting depmap.org does not work either — it is behind a browser challenge that answers HTTP 200
> with an HTML page. `assets/references/depmap_loading.md` has the current names and the figshare
> route.

---

## Capability Menu

| Capability | Maturity | Tool/Method | Reference Doc |
|------------|----------|-------------|---------------|
| **Dependency scoring** | | | |
| Load DepMap gene-effect matrix | **REFERENCE** | `pandas` | `assets/references/depmap_loading.md` |
| Binary dependency call (< −0.5 threshold) | **REFERENCE** | Python | `assets/references/dependency_analysis.md` |
| Common-essential filtering | **REFERENCE** | DepMap's own `CRISPRInferredCommonEssentials.csv` | `assets/references/dependency_analysis.md` |
| **Selective dependency** | | | |
| normLRT score (published, skew-t vs normal) | **PARTIAL** | R `sn::st.mple` + `MASS::fitdistr` — not pinned, no Python equivalent | `assets/references/dependency_analysis.md` |
| Group-comparison selective dependency | **REFERENCE** | `scipy.stats.mannwhitneyu` — pinned | `assets/references/dependency_analysis.md` |
| SSD selectivity proxy (Python, no R) | **REFERENCE** | Python (`((x - x.mean())**2).sum()` per gene) | `assets/references/dependency_analysis.md` |
| Per-cancer-type dependency frequency | **REFERENCE** | Python | `assets/references/dependency_analysis.md` |
| **Druggability** | | | |
| Pharos target annotation (Tclin/Tchem/Tbio/Tdark) | **REFERENCE** | Pharos API / download | `assets/references/druggability.md` |
| Therapeutic-window prioritization (dependent + druggable) | **REFERENCE** | Python | `assets/references/druggability.md` |
| **Synthetic lethality** | | | |
| Mutual-exclusivity Fisher test (one-sided) | **REFERENCE** | `scipy.stats.fisher_exact` | `assets/references/synthetic_lethality.md` |
| Paralog prior (Ensembl BioMart) | **REFERENCE** | BioMart API / download | `assets/references/synthetic_lethality.md` |
| PPI prior (STRING) | **REFERENCE** | STRING API / download | `assets/references/synthetic_lethality.md` |
| Canonical BRCA-PARP pairs | **REFERENCE** | literature / curated list | `assets/references/synthetic_lethality.md` |
| **Multi-omic integration** | | | |
| Dependency + phosphoproteomics (activating-site upregulated + dependent) | **REFERENCE** | Python | `assets/references/integration.md` |
| Dependency + expression (overexpressed + dependent) | **REFERENCE** | Python | `assets/references/integration.md` |
| Dependency + MAF (mutated + paralog-dependent) | **REFERENCE** | Python | `assets/references/integration.md` |

Everything except normLRT is **REFERENCE** — the libraries are pinned, but dependency analysis
requires study-specific judgment: the threshold (−0.5 vs −0.6), which cancer types to test, which
druggability tier counts as "actionable", which priors to apply for synthetic lethality. These are
design decisions, not a missing tool.

**normLRT is PARTIAL** for a different reason: the published score is a normal-vs-**skew-t**
likelihood ratio, and no Python package fits Azzalini's skew-t (`scipy.stats.skewnorm` is a different
family; `scipy.stats.jf_skew_t` is Jones–Faddy; PyPI's `SkewT` is a meteorology plotting tool). It
needs R (`sn`, `MASS`) provisioned per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` —
cheap where the environment already ships `r-base`, which many analysis containers do. The
group-comparison test is not a substitute for it; it answers a different question (see §4).

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step.

### 1. Load DepMap gene-effect

Read `CRISPRGeneEffect.csv` and build a symbol→column map.

- **Rows are cell lines, columns are genes.** Not the other way round. A transposed `.loc` that lands
  on a valid label fails *silently*
- Every column is `SYMBOL (EntrezID)`, so a bare `gene_effect["EGFR"]` raises `KeyError`
- Get the file from figshare — scripting depmap.org returns HTTP 200 and an HTML challenge page

→ `assets/references/depmap_loading.md`

### 2. Binary dependency calls

Threshold at −0.5 (the conventional "likely essential"), then take the per-gene frequency.

- State the threshold; −0.6 is more conservative, −0.3 inflates false positives
- **`axis=0`, not `axis=1`.** Rows are cell lines, so `axis=1` averages each *line* across 18k genes
  and returns one number per `ACH-######` — a Series, so it fails downstream rather than here

→ `assets/references/dependency_analysis.md`

### 3. Common-essential filter

Drop the genes that are essential everywhere — ribosome, proteasome, RNA Pol. They kill normal cells
too, so they have no therapeutic window.

- **DepMap ships the call** (`CRISPRInferredCommonEssentials.csv`, ~1,537 genes). Use it
- A hand-rolled `frequency >= 0.9` gate is a *different* set: it drifts with which lines you subset
  and knows nothing about screen quality. If you want that, say so and call it something else

→ `assets/references/dependency_analysis.md`

### 4. Selective-dependency test — two different questions

Pick the one you are actually asking; they are not interchangeable.

- **"Selective in *some* unnamed subset?"** → the published **normLRT**: normal vs **skew-t**, ≥100,
  *plus* `mean < median` (without it you rank growth-suppressors as vulnerabilities), *plus* excluding
  common/non-essentials. **PARTIAL** — needs R (`sn`); no Python package fits Azzalini's skew-t, and
  `skewnorm` is a different family that the ≥100 threshold is not calibrated to
- **"More essential in cancer type A than elsewhere?"** → a directional Mann-Whitney (`alternative
  ="less"`), in the pinned stack. FDR-correct, and report group sizes — a "significant" delta over six
  lines is noise
- **"A dependency in one screen modality / cohort but not another?"** (e.g. patient-level predicted
  scores vs cell-line screens) → characterize
  each gene's dependency-score **distribution separately in each cohort** — normLRT where R is
  available, or the **SSD** dispersion proxy in the pinned Python stack — classify each distribution
  (single-normal vs heavy-tailed / selective), contrast the cohorts, then keep only druggable
  survivors. A cross-cohort *expression* correlation answers a different, weaker question.
  **Order it cheap-first for tractability:** compute the per-gene selectivity statistic and druggability
  filter *first*, reducing to a small candidate set, and only then run the cross-cohort comparison on
  that set — an all-pairs biomarker×target matrix (every gene × every gene) is quadratic and overruns
  the time budget; the per-gene stats are linear and do the discriminating work

→ `assets/references/dependency_analysis.md`

### 5. Druggability annotation

Pharos TDL tier per gene. **GraphQL only** — `GET /targets/{gene}` 404s.

- Query on **HGNC approved symbols**; an alias returns `None` indistinguishably from a real miss
  (`GLUT1` → use `SLC2A1`). Strip the Entrez suffix first
- `raise_for_status()`, then check for `errors` — a 400 body still parses as JSON, so without it a
  failed query yields `None`, the same value as "Pharos has never heard of this gene"
- Batch via the bulk TCRD dump, not per-gene calls

> **Never default a failed lookup to `Tdark`.** `Tdark` is the substantive conclusion "nothing is
> known to bind this target", so swallowing a 404 into `Tdark` turns every network failure into
> "no druggable targets" — a plausible-looking result that is entirely an artifact. Let the lookup
> fail, and report how many genes went unannotated.

→ `assets/references/druggability.md`

### 6. Therapeutic-window prioritization

Selectively dependent + Tclin/Tchem + not common-essential, ranked by effect.

- `isin(["Tclin","Tchem"])` silently drops the unannotated rows — **report `n_unannotated`** beside
  the list, or a shrunken candidate set reads as a clean negative
- DepMap screens **cancer lines only**. "Not common-essential" *infers* a window; it does not measure
  one. Say which it is

→ `assets/references/druggability.md`

### 7. Synthetic lethality (mutual exclusivity)

Fisher exact on the 2×2, one-sided for depletion of the double-altered cell, then FDR across pairs.

- `alternative="less"` — SL predicts depletion; a two-sided test dilutes the directional signal
- Priors are what separate signal from thousands of pairs — but a prior that outlives its evidence
  *creates* confident false positives. `KRAS`–`STK33` was refuted in 2011; `VHL`–`CDK6` needs CDK4
  *and* CDK6, which no pairwise prior can express
- STRING's `limit` defaults to **10** — BRCA1 has 373 partners at score > 700 and PARP1 is not in the
  top 10, so the default call misses the canonical pair
- **Go beyond a single flat pairwise Fisher.** Report **observed-vs-expected co-occurrence** per pair
  (and per sample / cell line where resolution allows), not just the 2×2 counts; assess significance by
  **permutation** as well as analytic Fisher (state the permutation count and threshold); and use a
  **greedy / iterative set-cover** (UNCOVER-style) to surface mutually-exclusive *modules* a flat
  pairwise ranking misses

→ `assets/references/synthetic_lethality.md`

---

## Cancer-Dependency Best Practice (on top of omics-shared)

### 0. The matrix is cell lines × genes

Rows are `ModelID`, columns are `SYMBOL (EntrezID)`. This is the single most common way the analysis
goes wrong, and a transposed `.loc` that happens to hit a valid label fails *silently*.

### 1. Gene-effect sign convention

Chronos: **negative = lethal** (knockout reduces fitness); 0 ≈ no effect; positive = knockout enhances
growth (rare). −1.0 is not "complete lethality" in the abstract — Chronos *scales* scores so the
median common-essential sits near −1 and non-essentials near 0. That is why DepMap's control lists are
the right reference point. Don't flip signs.

### 2. Dependency threshold = −0.5

The conventional cutoff. Lower (−0.6) is more conservative; higher (−0.3) inflates false positives.
State the threshold.

### 3. Common-essentiality gate — use DepMap's list

Common-essential genes (ribosome, proteasome, RNA Pol) are not therapeutic targets; filter them before
druggability prioritization. Take `CRISPRInferredCommonEssentials.csv` rather than re-deriving with a
≥90% frequency cutoff: the cutoff drifts with which lines are in your subset and has no notion of
screen quality, so it is not the same set and not what "common essential" means.

### 4. normLRT and the group test answer different questions

**normLRT** asks "is this gene selective in *some* subset?" — it fits the gene's distribution across
*all* lines (skew-t vs normal) and never sees a group label. The **group comparison** asks "is this
gene more essential in cancer type A?" — you supply the subset.

Neither is the other's fallback. A gene can be strongly selective with no signal in the lineage you
happened to name, and vice versa. Pick on the question; then price it — R is absent from `task1–4` but
present in many analysis containers, and you can see which you are in.

### 5. Therapeutic window = dependent in cancer, tolerated in normal

A perfect target is lethal in the tumour and spares healthy tissue. DepMap screens **cancer lines
only** — it never measures normal-cell toxicity. "Not common-essential" is an *inference* that a
window exists, not a measurement of one. Say which it is in the `report`.

### 6. Synthetic lethality priors

Not all gene pairs are plausible SL candidates. Apply priors:
- **Paralog pairs** (duplicate genes, one compensates for the other)
- **PPI neighbors** (proteins in the same complex)
- **Canonical pairs** (BRCA1/2–PARP1, ATM–ATR, MTAP–PRMT5, …)

Raw mutual-exclusivity without priors gives thousands of false positives. But a prior that outlives
its evidence *creates* false positives with a confident label on them — `KRAS`–`STK33` was refuted in
2011, and `VHL`–`CDK6` requires losing CDK4 *and* CDK6, which no pairwise prior can express. Curate
the list against replication, and use **HGNC approved symbols** so entries actually match.

Derive the paralog prior **programmatically** from a curated ortholog / paralog resource (Ensembl /
biomaRt, HCOP) with a stated **sequence-identity threshold**, and **enumerate the paralog space to
test each pair directly** — do not hardcode a remembered shortlist or confine the screen to a
hand-picked target list. A curated-target-only screen makes high-identity paralog pairs — which are
prime synthetic-lethal candidates — structurally invisible. Enumerate paralogs **genome-wide, not only
paralogs of the mutated / altered genes**: paralog buffering does not require the compensated loss to
be a coding mutation (it can be low expression or copy loss), so keying the enumeration on a
mutation list hides exactly the highest-identity essential pairs the analysis is looking for.

### 7. Multi-omic integration amplifies candidates

Dependency alone: "this gene is essential in cancer X." Dependency + phospho upregulation: "this kinase is *both* essential *and* hyperactivated" → stronger therapeutic rationale.

---

## Pitfalls & fixes

| Symptom / mistake | Cause | Fix |
|-------------------|-------|-----|
| `KeyError` on a gene symbol | Columns are `SYMBOL (EntrezID)`; or the matrix was read as genes × lines | Build `symbol_to_col`; rows are `ModelID` |
| Dependency frequency is one number per `ACH-######` | `mean(axis=1)` — averaged each line over 18k genes | `axis=0`: rows are cell lines |
| `read_csv` chokes on HTML from depmap.org | The portal is challenge-gated; it answers 200 with a challenge page | Use the figshare release (`depmap_loading.md`) |
| Everything is `Tdark`, or no druggable targets | A failed Pharos lookup defaulted to `Tdark` | Let it fail; `Tdark` is a conclusion, not a null |
| Pharos returns `None` for a real gene | Alias, not an HGNC symbol (`GLUT1` vs `SLC2A1`) | Standardize to HGNC; strip the Entrez suffix before querying |
| All genes look "dependent" | Threshold too high, or sign flipped | Use −0.5; negative = lethal, keep the sign |
| Inconsistent dependency calls | Threshold switched mid-analysis (−0.5 vs −0.3) | Fix one threshold and state it |
| normLRT ranks growth-suppressors as targets | No left-skew check (`mean < median`) | normLRT is two-sided non-normality; add the check |
| Therapeutic-window list is housekeeping genes | No common-essential gate | Filter with `CRISPRInferredCommonEssentials.csv` |
| SL pairs look random | No priors + two-sided test + no FDR | Paralog / PPI / canonical priors, one-sided Fisher, FDR |
| PPI prior misses the obvious partner | STRING's `limit` defaults to 10 | Pass `limit` explicitly (`synthetic_lethality.md`) |

---

## Evidence & Reporting

Every analysis emits:
- **Quantitative claims** → trailing JSON `report` with exact scores/p-values
- **Dependency calls**: gene, mean gene-effect in target cancer, threshold used, n lines
- **Druggability**: Pharos tier, evidence (TTD phase, DrugBank count)
- **SL pairs**: mutual-exclusivity odds ratio, p-value, prior applied (paralog/PPI/canonical)
- **Per prioritized target** (a ranked list is not yet a prioritization): its pathway / mechanism in the
  disease context; a named approved drug or clinical-trial precedent where one exists; what its tier
  means (approved-class vs clinical-stage vs novel-chemistry — and which tiers form the repurposing
  pool); and a concrete experimental-validation next step

See reference docs for per-analysis reporting templates.
