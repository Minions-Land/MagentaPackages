# Bayesian colocalization with R `coloc`

**Maturity: REFERENCE (domain knowledge — no code dependency).** Nothing here can go stale against a library version; it is the interpretive layer the runnable docs feed into.

Test whether two association signals at a locus (GWAS×GWAS, or GWAS×molecular-QTL such as
eQTL/pQTL) are driven by the **same** causal variant. Use the R `coloc` package (Wallace lab) — the
reference implementation of `coloc.abf` (Giambartolomei 2014) and `coloc.susie` (Wallace 2021).
Do not reimplement the Bayes factors by hand.

## 1. Pick the region and SNPs

Each dataset is the association stats for **one trait in one genomic region** (a locus, typically
±0.5–1 Mb around a signal — NOT a whole chromosome). Include **all** SNPs in the region with data
in **both** studies; **do not** threshold on p-value or MAF (coloc enumerates configurations and
needs the full set). SNPs are matched between the two datasets by the `snp` id, so use a consistent,
allele-aware id and make sure `beta` is on the same effect allele in both (and, for `coloc.susie`,
that the LD matrix is aligned the same way).

## 2. The dataset (an R `list`, not a data.frame)

Per trait, a list mixing per-SNP vectors and scalars. From `?check_dataset`:

- **Vectors** (equal length): `beta`, `varbeta` (**= SE², not SE**), `snp` (unique ids, used to
  merge), optional `pvalues`, `MAF`, `position` (for plots), and `LD` (a square matrix, dimnames =
  snp ids) for `coloc.susie`.
- **Scalars:** `type` (`"quant"` or `"cc"`), `N`, `s` (case fraction, cc only), `sdY` (trait SD, quant).
- **Which combination:** always `type`. Then: `cc` → `s`; `quant` with known sdY → `sdY`; if
  `beta`/`varbeta` absent → give `pvalues` + `MAF` + `N` (+ `s` for cc); `quant` with unknown sdY →
  give `beta`, `varbeta`, `N`, `MAF` and coloc estimates sdY. Prefer supplying `beta`/`varbeta`.

`check_dataset(d)` returns `NULL` when the list is valid; run it while debugging. A "minimum p value
exceeds warn.minp" warning most often means `varbeta` was given as SE instead of SE².

## 3. Single-causal-variant coloc — `coloc.abf`

```r
library(coloc)
res <- coloc.abf(dataset1 = D1, dataset2 = D2,
                 p1 = 1e-4, p2 = 1e-4, p12 = 1e-5)   # default priors
res$summary     # named vector: nsnps, PP.H0.abf, PP.H1.abf, PP.H2.abf, PP.H3.abf, PP.H4.abf
res$results     # per-SNP table incl. SNP.PP.H4 (prob each SNP is THE shared causal, given H4)
```

- **Hypotheses:** H0 no causal in either; H1/H2 causal in trait 1 / trait 2 only; **H3** distinct
  causals; **H4** one **shared** causal.
- **Call it colocalized** when `PP.H4` is high (a common threshold is `> 0.8`) **and** clearly
  exceeds `PP.H3`. The top shared variant = the SNP with the largest `SNP.PP.H4`.
- `coloc.abf` assumes ≤1 causal variant per region and needs no LD. Priors are auto-clamped for very
  large regions (`adjust_prior`).

## 4. Multiple signals — `coloc.susie`

When a locus may have >1 causal variant, first fine-map each trait with SuSiE (needs an LD matrix),
then colocalize signal-by-signal:

```r
library(coloc)
s1 <- runsusie(D1)          # D1 must include an LD matrix aligned to beta
s2 <- runsusie(D2)
res <- coloc.susie(s1, s2)  # PP.H0–H4 per pair of credible sets
res$summary
```

## 5. Sensitivity to priors

```r
sensitivity(res, rule = "H4 > 0.8")   # shows how PP.H4 depends on p12 and the data; plots regions
```

Always sanity-check alignment before trusting a result: `check_alignment(D1)` should be skewed
positive (Z-score products vs LD correlations); a bad alignment flags a sign/strand error.

## 6. Running coloc from a Python workflow

Write each trait's locus sumstats to disk and drive R via `subprocess`:

```python
import subprocess, pandas as pd
subprocess.run(["Rscript", "run_coloc.R", "trait1.tsv", "trait2.tsv", "out.tsv"], check=True)
pp = pd.read_csv("out.tsv", sep="\t")
```

`run_coloc.R` reads each TSV, builds the `list` (§2), calls `coloc.abf`, and writes
`as.data.frame(t(res$summary))`. For many trait pairs, loop loci → shared SNPs → `coloc.abf`, and
rank pairs by `PP.H4`. (For the LD-based `coloc.susie` path, gwaslab's
`SumstatsPair.to_coloc()` + `run_coloc_susie()` prepares the reference LD and drives the same R
package.)

## Reporting

- Per pair: PP.H0–H4, n shared SNPs, top shared variant (max SNP.PP.H4), priors, each trait's
  `type`/sdY, and whether `coloc.abf` (single) or `coloc.susie` (multi-signal) was used.
- The colocalization call (H4 vs H3) with the locus/lead-variant context; a `sensitivity` plot when
  H4 is borderline.
