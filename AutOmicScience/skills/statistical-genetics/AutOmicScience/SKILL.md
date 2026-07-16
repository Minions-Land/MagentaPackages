---
name: statistical-genetics
description: Statistical genetics on GWAS / molecular-QTL summary statistics using gwaslab (Python) and coloc (R) — summary-statistics ingestion (60+ formats), QC, effect-allele/strand harmonization, statistic completion, genome-build liftover, fixed/random-effects inverse-variance meta-analysis across cohorts, lead-variant / locus extraction, and Bayesian colocalization (coloc.abf single-causal + coloc.susie multi-signal → posterior probabilities PP.H0–H4). Use when you have GWAS or eQTL/pQTL summary statistics (beta/SE or p-values, effect allele, allele frequency, sample size) and need to harmonize/QC them, meta-analyze cohorts, call loci, or test whether two traits (or a GWAS and a QTL) share a causal variant.
requiredTools: [run_python, bash, read, write, observe_figure]
tags: [statistical-genetics, gwas, eqtl, qtl, meta-analysis, colocalization, coloc, fine-mapping, summary-statistics, gwaslab]
---

# Statistical Genetics — gwaslab (Python) + coloc (R)

Work with GWAS / molecular-QTL **summary statistics** using the two field-standard tools:

- **`gwaslab`** (Python) — the summary-statistics engine: load 60+ formats, QC, harmonize to a
  reference genome (allele/strand/palindrome), complete statistics (BETA/SE/Z/P/MAF), meta-analyze
  cohorts, and extract lead variants/loci. It also *orchestrates* the R `coloc` calls below.
- **`coloc`** (R, Wallace lab) — the reference implementation of Bayesian **colocalization**:
  `coloc.abf` (one-causal-variant Approximate Bayes Factors) and `coloc.susie` (multiple signals),
  returning posterior probabilities PP.H0–H4.

Builds on skill `omics-shared` (loaded automatically — its evidence/grounding rules apply). This is
summary-statistic level: no raw-genotype calling/imputation.

---

## Domain background (read once)

- **Summary statistics** = per-variant `chr, pos, effect_allele (EA), other_allele (NEA), EAF,
  beta` (or OR), `SE`, `p`, `N`. `varbeta = SE²`. Effect is of EA vs NEA; **allele order matters**.
- **Meta-analysis** (fixed-effects inverse-variance) combines the same variant across cohorts,
  weighting by `1/SE²`; needs all cohorts on one effect allele. Random effects (DerSimonian-Laird)
  and heterogeneity (Cochran's Q, I²) handle between-cohort variability.
- **Colocalization** asks, at a locus where two traits both associate, whether they share a causal
  variant (H4) vs two distinct causals (H3). `coloc.abf` assumes ≤1 causal per region (no LD
  needed); `coloc.susie` allows multiple (needs an LD matrix per trait).
- **sdY** (quantitative-trait SD) scales the ABF prior; if unknown, coloc estimates it from
  `varbeta`, `MAF`, `N`.

---

## Prerequisites

1. **Summary statistics** with, per variant: an id (`chr:pos:ref:alt` or rsID), EA + NEA,
   `beta`+`SE` (preferred) or `p`, `EAF`/MAF, `N`.
2. **Python** `gwaslab`; **R** with `coloc` (+ `susieR`) for colocalization. **Neither is pinned** —
   this whole skill is PARTIAL on provisioning (see the Capability Menu).

Provision both into **one** env per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` — the
workflow crosses the Python/R line in a single run (gwaslab harmonises, then orchestrates `coloc`), so
splitting it across two envs means round-tripping through disk:

```toml
# pixi.toml, at your analysis root
[workspace]
name = "statgen"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
r-base = "*"
r-coloc = "*"
r-susier = "*"
rpy2 = "*"
pandas = "*"

[pypi-dependencies]
gwaslab = "*"
```

```bash
pixi lock && pixi install --locked
pixi run --frozen python -c "import gwaslab"
```

Build it here rather than in the package — `tools/omics-environment/pixi.toml` is a
checksum-verified artifact the host may delete and re-fetch, taking the edit with it.

> **Never `pip install gwaslab` or `conda install` without `-n`.** A bare `pip` resolves against
> whatever `python` leads `$PATH` — often conda `base` — and `conda install -c conda-forge r-coloc`
> with no `-n <env>` installs into the **currently active** environment, which is `base` unless you
> arranged otherwise. Both are the exact failure `AOSE_nonStandard_env.md` exists to prevent. If Pixi
> cannot solve the R stack, fall back to a **named** conda env (`conda create -n aose-statgen ...`),
> never `base`.

`omics_preflight` does not cover this env; check the imports yourself and record the env + the
`gwaslab`/`coloc` versions in the `report`.

---

---

## Capability Menu

| Capability | Maturity | Tool | Method / function | Reference Doc |
|------------|----------|------|-------------------|---------------|
| Load 60+ sumstats formats, column mapping | **PARTIAL** | gwaslab | `gl.Sumstats(...)` | `assets/references/gwaslab_sumstats.md` |
| QC / sanity / harmonize / fill / liftover | **PARTIAL** | gwaslab | `.basic_check` `.harmonize` `.fill_data` `.liftover` | `assets/references/gwaslab_sumstats.md` |
| Genomic inflation (λ GC) | **PARTIAL** | gwaslab | `.get_gc()` → also `meta["Genomic inflation factor"]` | `assets/references/gwaslab_sumstats.md` |
| Lead variants / loci / clumping / plots | **PARTIAL** | gwaslab | `.get_lead` `.clump` `.plot_mqq` `.plot_region` | `assets/references/gwaslab_sumstats.md` |
| Fixed/random-effects IV meta-analysis | **PARTIAL** | gwaslab | `SumstatsMulti.run_meta_analysis` (**not** `SumstatsPair` — it has no such method) | `assets/references/meta_analysis.md` |
| Colocalization (single-causal) | **PARTIAL** | coloc (R) | `coloc.abf(dataset1, dataset2)` | `assets/references/colocalization.md` |
| Colocalization (multi-signal) | **PARTIAL** | coloc (R) | `runsusie()` + `coloc.susie()` | `assets/references/colocalization.md` |
| Interpreting PP.H0–H4, choosing abf vs susie | **REFERENCE** | — | domain knowledge — no dependency | `assets/references/colocalization.md` |

Every computational capability is **PARTIAL** for one reason: neither `gwaslab` nor R `coloc` is in
`task1–4`. Provision them first (Prerequisites). If they can be neither imported nor provisioned, that
is a **blocker with the install command** — not a cue to hand-roll a weaker colocalization.

Read the method doc before running each capability.

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step.

### 1. Load & QC & harmonize (gwaslab)

Load the sumstats, standardise, align alleles to a reference, fill missing statistics.

- **Allele order is the analysis.** Effect is of EA vs NEA; harmonising against a reference is what
  makes two cohorts comparable, and palindromic SNPs are where it goes wrong
- `varbeta = SE²` — coloc wants the *variance*, not the SE
- Liftover only if builds differ; state the build either way
- **Compute λ GC explicitly and gate on it.** Not as a side effect of `plot_mqq()`. Every downstream
  p-value, lead variant and meta-analysis weight inherits the inflation, so λ decides whether anything
  below means anything. An inflated λ is a **finding to surface**, not a nuisance to correct away

→ `assets/references/gwaslab_sumstats.md`

### 2. Meta-analysis across cohorts (gwaslab)

Fixed- or random-effects inverse-variance, plus heterogeneity.

- Fixed vs random effects is your call — state it, and report Q / I² / P_HET beside the combined P
- All cohorts must be on **one effect allele** first (`match_allele=True`)
- **Meta-analysis lives on `SumstatsMulti`, not `SumstatsPair`** — the latter has no
  `run_meta_analysis` and no base class to inherit one; it is for clump/coloc/MR. "Two studies" is
  just a list of two

→ `assets/references/meta_analysis.md`

### 3. Lead variants / loci

Independent lead SNPs at a significance threshold and window.

- Both the threshold (5e-8 conventional) and the window (500 kb) are choices — state them

→ `assets/references/gwaslab_sumstats.md`

### 4. Colocalization (R coloc)

At a locus where two traits both associate, build one dataset `list` per trait over the **shared** SNPs
and call R `coloc` — the reference implementation — via `rpy2` or a small `Rscript`.

- **`coloc.abf` vs `coloc.susie` is the modelling decision.** `abf` assumes **≤1 causal variant** per
  region and needs no LD; `susie` allows multiple signals but needs an **LD matrix per trait**. Using
  `abf` where two independent causals exist is how a real H4 gets read as H3, and vice versa
- The dataset spec is exact: `beta`, `varbeta = SE²`, `snp`, `type`, plus `sdY` (quantitative) or
  `MAF`+`N`. Wrong `varbeta` silently rescales every Bayes factor
- **PP.H4 high (commonly > 0.8) *and* > PP.H3** ⇒ shared causal. Reporting PP.H4 alone hides the
  case where both are middling and the locus is simply underpowered

→ `assets/references/colocalization.md`

### 5. Visualize & ground

Manhattan/QQ and regional plots.

- The QQ plot is where λ becomes visible — read it against the λ you computed in step 1
- Inspect any plot before it backs a claim
- Cite gwaslab and coloc (Giambartolomei 2014; Wallace 2020/2021)

→ `assets/references/gwaslab_sumstats.md`

---

## Best Practice (on top of omics-shared)

- **Use the packages** — gwaslab for sumstats/meta/fine-map/plots; R `coloc` for colocalization.
- **Harmonize before combining** — one effect allele across cohorts/traits; let gwaslab flag/flip
  palindromes and align to a reference.
- **`varbeta = SE²`** — coloc takes the variance of beta, not the SE.
- **Provide sdY (or MAF+N)** for quantitative traits so coloc scales the prior correctly.
- **Dense, single-region datasets for coloc** — one locus, all SNPs (no p/MAF thresholding); only
  SNPs shared by both traits contribute.
- **`coloc.susie` needs an LD matrix** aligned to the same effect allele as beta.
- **Report heterogeneity** (Q, I²) from meta; a large I² undermines a fixed-effects pooled estimate.

---

## Pitfalls

- **Hand-rolling coloc/meta** instead of the validated packages — drops edge cases and multi-signal
  support; use gwaslab + coloc.
- **`SE` where `varbeta` is expected** — passing SE instead of SE² corrupts every posterior (a
  minimum-p warning from `check_dataset` is the usual symptom).
- **Un-harmonized alleles / mis-aligned LD** — opposite effect alleles across cohorts cancel signal;
  an LD matrix not aligned to beta breaks `coloc.susie`. Use gwaslab harmonize + coloc's
  `check_alignment`.
- **coloc over a whole chromosome or p-thresholded SNPs** — coloc needs one region, densely covered.
- **Missing sdY for a quant trait without MAF+N** — coloc cannot scale the prior; supply one or the other.
- **Reading PP.H4 without PP.H3** — low H4 + high H3 = distinct causals, not "no signal".

---

## Evidence & Reporting

Every analysis emits:
- **Inputs**: per study, n variants, build, effect allele; QC/harmonization actions taken.
- **Meta**: n cohorts, per-locus combined beta/SE/Z/P, Q/I²/P_HET, effect-direction string.
- **Loci**: lead variants, windows, significance threshold.
- **Colocalization**: per trait-pair PP.H0–H4, top shared variant (max SNP.PP.H4), n shared SNPs,
  priors, each trait's `type`/sdY; single-causal (`coloc.abf`) vs multi-signal (`coloc.susie`).
- **Figures** → inspect before citing. Cite gwaslab + coloc.

See the reference docs for per-capability templates.
