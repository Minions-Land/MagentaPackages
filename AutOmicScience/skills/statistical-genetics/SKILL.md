---
name: statistical-genetics
description: Statistical genetics on GWAS / molecular-QTL summary statistics using gwaslab (Python) and coloc (R) — summary-statistics ingestion (60+ formats), QC, effect-allele/strand harmonization, statistic completion, genome-build liftover, fixed/random-effects inverse-variance meta-analysis across cohorts, lead-variant / locus extraction, and Bayesian colocalization (coloc.abf single-causal + coloc.susie multi-signal → posterior probabilities PP.H0–H4). Use when you have GWAS or eQTL/pQTL summary statistics (beta/SE or p-values, effect allele, allele frequency, sample size) and need to harmonize/QC them, meta-analyze cohorts, call loci, or test whether two traits (or a GWAS and a QTL) share a causal variant.
requiredTools: [run_python, bash, read, write, observe_figure]
evidencePolicy: required
outputSchema: grounded_response
minConfidence: medium
tags: [statistical-genetics, gwas, eqtl, qtl, meta-analysis, colocalization, coloc, fine-mapping, summary-statistics, gwaslab]
extends: omics-shared
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
2. **Python** `gwaslab`; **R** with `coloc` (+ `susieR`) for colocalization.

```bash
pip install gwaslab                                  

conda install -c conda-forge r-coloc r-susier
# or, inside R:  install.packages("coloc")
```
---

## Capability Menu

| Capability | Tool | Method / function | Reference Doc |
|------------|------|-------------------|---------------|
| Load 60+ sumstats formats, column mapping | gwaslab | `gl.Sumstats(...)` | `assets/references/gwaslab_sumstats.md` |
| QC / sanity / harmonize / fill / liftover | gwaslab | `.basic_check` `.harmonize` `.fill_data` `.liftover` | `assets/references/gwaslab_sumstats.md` |
| Lead variants / loci / clumping / plots | gwaslab | `.get_lead` `.clump` `.plot_mqq` `.plot_region` | `assets/references/gwaslab_sumstats.md` |
| Fixed/random-effects IV meta-analysis | gwaslab | `SumstatsPair/Multi.run_meta_analysis` | `assets/references/meta_analysis.md` |
| Colocalization (single-causal) | coloc (R) | `coloc.abf(dataset1, dataset2)` | `assets/references/colocalization.md` |
| Colocalization (multi-signal) | coloc (R) | `runsusie()` + `coloc.susie()` | `assets/references/colocalization.md` |

Read the method doc before running each capability.

---

## Standard Workflow

### 1. Load & QC & harmonize (gwaslab)

```python
import gwaslab as gl
ss = gl.Sumstats("study.tsv.gz", fmt="auto",              # or an explicit format preset
                 snpid="SNP", chrom="CHR", pos="POS",
                 ea="ALT", nea="REF", eaf="EAF",
                 beta="BETA", se="SE", p="P", n="N")
ss.basic_check()                                          # standardize, sanity-check, dedup
ss.harmonize(basic_check=False, ref_seq="/path/genome.fa",# align EA/NEA to reference; flag palindromes
             ref_infer="/path/1kg.vcf.gz", ref_alt_freq="AF")
ss.fill_data(to_fill=["BETA","SE","P","Z","MAF"])         # complete missing statistics
# ss.liftover(from_build="19", to_build="38")             # if builds differ
```

See `assets/references/gwaslab_sumstats.md`.

### 2. Meta-analysis across cohorts (gwaslab)

```python
pair = gl.SumstatsPair(ss_discovery, ss_replication)      # merge + allele-align two studies
meta = pair.run_meta_analysis(random_effects=False)       # fixed-effects IVW; returns a Sumstats
# many cohorts: gl.SumstatsMulti([ss1, ss2, ss3, ...]).run_meta_analysis()
```

`run_meta_analysis` gives combined BETA/SE/Z/P, sample-size-weighted allele frequency, a per-study
effect-direction string, and heterogeneity (Q, I², P_HET). See `assets/references/meta_analysis.md`.

### 3. Lead variants / loci

```python
leads = ss.get_lead(sig_level=5e-8, windowsizekb=500)     # independent lead SNPs / loci
```

### 4. Colocalization (R coloc)

At a locus where two traits both associate, build one `list` per trait over the **shared** SNPs
(`beta`, `varbeta = SE²`, `snp`, `type`, and `sdY` or `MAF`+`N`) and call R `coloc.abf` — the
reference implementation — through a small `Rscript`:

```python
import subprocess, pandas as pd
subprocess.run(["Rscript", "run_coloc.R", "trait1.tsv", "trait2.tsv", "out.tsv"], check=True)
pp = pd.read_csv("out.tsv", sep="\t")     # PP.H0..PP.H4 (+ top shared SNP)
```

`$summary` holds PP.H0–H4; PP.H4 high (commonly > 0.8, and > PP.H3) ⇒ a shared causal variant. See
`assets/references/colocalization.md` for the dataset spec and the R script. When a locus has
multiple signals and an LD matrix is available, use `coloc.susie` instead (same doc; gwaslab's
`SumstatsPair.run_coloc_susie` can orchestrate that LD-based path).

### 5. Visualize & ground

```python
ss.plot_mqq()                 # Manhattan + QQ
ss.plot_region(region=...)    # regional/locuszoom-style
```

Inspect any plot before it backs a claim; cite gwaslab and coloc (Giambartolomei 2014;
Wallace 2020/2021).

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
