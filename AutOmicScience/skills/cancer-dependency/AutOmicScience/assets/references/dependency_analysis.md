# Reference — Dependency Classification & normLRT

**Maturity: mixed.** Binary calls, essentiality classification and the group-comparison test are
**REFERENCE** — the libraries are in the pinned `task1` env (select it with `modality="scrna"` — an
environment selector, not a claim about your data) and you hand-write the script. The published
**normLRT score is PARTIAL**: it needs R's `sn` package, which `task1–4` do not have (see below).
Emit a `report` dict and cite its numbers.

Distinguishing common-essential genes (no therapeutic window) from selective dependencies (targetable
vulnerabilities).

**`CRISPRGeneEffect.csv` is cell lines × genes** — every snippet here indexes accordingly. If that is
news, read `depmap_loading.md` first; a transposed index is the single most common way this analysis
goes silently wrong.

## Binary dependency call

DepMap's conventional threshold: gene-effect < −0.5 = "dependent".

```python
dependent = gene_effect < -0.5                       # lines × genes, boolean
dependency_frequency = dependent.mean(axis=0)        # axis=0 → per gene, fraction of LINES
```

`axis=0` averages down the rows (cell lines), giving one number per gene. `axis=1` would average each
cell line across all 18k genes — a meaningless number that still returns a Series, so it fails
downstream rather than here.

The **probability of dependency** file is an alternative, thresholded at 0.5:

```python
dep_prob = pd.read_csv("CRISPRGeneDependency.csv", index_col=0)   # also lines × genes, 0–1
dependent = dep_prob > 0.5
```

## Common-essential vs selective: use DepMap's own calls

Do **not** re-derive essentiality with a frequency cutoff. DepMap ships the classification, computed
against its curated controls with the release's own screen-quality model:

```python
common_essential = set(pd.read_csv("CRISPRInferredCommonEssentials.csv").Essentials)
nonessential     = set(pd.read_csv("AchillesNonessentialControls.csv").Gene)
# all three use the same "SYMBOL (EntrezID)" labels as gene_effect.columns
selective_candidates = [
    c for c in gene_effect.columns
    if c not in common_essential and c not in nonessential
]
```

A hand-rolled `dependency_frequency >= 0.9` gate is not the same set and is not what DepMap means by
"common essential": it drifts with which lines are in your subset, and it has no notion of screen
quality. Reach for it only if you deliberately want a subset-specific frequency — and then say so, and
call it something other than "common essential".

**Why it matters:** common-essential genes (ribosome, proteasome, RNA Pol) are not drug targets — they
kill normal cells too. Filtering them out is what leaves a therapeutic window.

## normLRT — the published selective-dependency score (PARTIAL: needs R)

normLRT measures how far a gene's dependency distribution departs from a single normal. A gene that is
strongly essential in a *subset* of lines has a long left tail; a normal fits it badly.

**The definition** (Project DRIVE, McDonald et al. 2017; used by DepMap and Pacini et al. 2021):

> normLRT = 2 × ( log-likelihood of a **skew-t** fit − log-likelihood of a **normal** fit )

A gene is called **selectively dependent** when *all three* hold:

1. `normLRT >= 100`
2. `mean(gene_effect) < median(gene_effect)` — the skew is to the **left** (toward lethality)
3. the gene is **not** common-essential and **not** non-essential (use DepMap's lists, above)

Condition 2 is not decoration: normLRT is a two-sided measure of non-normality, so a right-skewed gene
(knockout *helps* growth in a few lines) scores just as high. Without it you rank growth-suppressors
alongside vulnerabilities.

**Skew-t, not skew-normal.** These are different distribution families, and the `>= 100` threshold is
calibrated to the skew-t fit. `scipy.stats.skewnorm` fits a skew-*normal* (no tail parameter) and
produces a different, smaller statistic — thresholding it at 100 does not reproduce the published
call. There is no Python substitute either: `scipy.stats.jf_skew_t` is the Jones–Faddy family, not
Azzalini's, and the PyPI package named `SkewT` is a meteorology plotting tool. **Do not approximate
this score and keep calling it normLRT.**

The reference implementation is R (`sn` ≥ 2.1, `MASS`), matching the published method — normal via
`MASS::fitdistr` (`$loglik`), skew-t via `sn::st.mple` (`$logL`), with the paper's degrees-of-freedom
fallback ladder when the free-`nu` fit fails to converge:

```R
library(sn); library(MASS)

normLRT <- function(y) {
  y <- y[!is.na(y)]
  ll_norm <- fitdistr(y, "normal")$loglik
  X <- matrix(1, nrow = length(y), ncol = 1)     # st.mple wants a design matrix of 1's
  fit <- try(st.mple(x = X, y = y), silent = TRUE)
  for (nu in c(2, 5, 10, 25, 50, 100)) {         # only reached if the free-nu fit errored
    if (!inherits(fit, "try-error")) break
    fit <- try(st.mple(x = X, y = y, fixed.nu = nu), silent = TRUE)
  }
  if (inherits(fit, "try-error")) return(NA_real_)   # report as unscored; do not call it 0
  2 * (fit$logL - ll_norm)
}
```

A gene whose skew-t fit fails at every `nu` is **unscored**, not "normLRT = 0". Zero means "fits a
normal perfectly" — i.e. definitively *not* selective — so defaulting to it silently converts a fit
failure into a substantive negative call. Count the NAs in the `report`.

Provision R + `sn` per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` (§A: a Pixi
feature with its own solve-group, composing `["core", "singlecell", <new>]`), and drive it from Python
with `rpy2` or via `Rscript` on a CSV.

**How expensive that is depends on where you are running, which you can see and this doc cannot.** R is
absent from `task1–4`, but many analysis containers ship `r-base`, in which case `install.packages("sn")`
is the whole cost. Check before deciding. The next section answers a **different question**, not a
cheaper version of this one — pick on the question, then price it.

## Group-comparison selective dependency (REFERENCE — pinned stack)

A different question, and often the one actually being asked: *is this gene more essential in cancer
type A than elsewhere?* normLRT does not take a group — it finds genes selective in *some* unnamed
subset. If you can name the subset, test it directly:

```python
from scipy.stats import mannwhitneyu

def selective_in_group(col, group_lines, other_lines):
    """col is a gene_effect column label, e.g. 'EGFR (1956)'."""
    g = gene_effect.loc[gene_effect.index.intersection(group_lines), col].dropna()
    o = gene_effect.loc[gene_effect.index.intersection(other_lines), col].dropna()
    stat, p = mannwhitneyu(g, o, alternative="less")   # group MORE dependent = lower gene-effect
    return {"gene": col, "delta": g.mean() - o.mean(), "n_group": len(g), "p": p}
```

`alternative="less"` is directional: it asks whether the group's scores are stochastically *lower*
(more lethal). Apply across genes and FDR-correct (`statsmodels.stats.multitest.multipletests`,
`method="fdr_bh"`). Report the FDR and the group sizes — with few lines in a lineage, a "significant"
delta of 0.05 is noise.

## Therapeutic-window logic

A candidate target is:

1. **Selectively dependent** — normLRT (unnamed subset) or the group test (named subset)
2. **Not common-essential** — DepMap's list, above → the window exists
3. **Druggable** — see `druggability.md`

```python
candidates = [
    c for c in selective_candidates                      # already excludes common-essential
    if (gene_effect.loc[gene_effect.index.intersection(cancer_lines), c] < -0.5).mean() > 0.5
]
```

DepMap screens cancer lines only — it never measures normal-cell toxicity. "Not common-essential" is
an *inference* that the window exists, not a measurement of it. Say so in the `report`.

## Pitfalls

- **Transposing the matrix** — it is lines × genes; `dependency_frequency` needs `axis=0`
- **Bare gene symbols** — columns are `SYMBOL (EntrezID)`; see `depmap_loading.md`
- **`skewnorm` called normLRT** — different family, uncalibrated against the ≥100 threshold
- **normLRT without the mean<median check** — ranks growth-suppressors as vulnerabilities
- **Hand-rolled ≥90% "common essential"** — DepMap ships the call; the frequency gate drifts with your subset
- **Unscored genes defaulted to 0** — 0 is the "definitely not selective" answer; keep NA and count it
- **normLRT on few lines** — the skew-t has 4 parameters; a tail needs a decent n (>50 lines)
- **CERES instead of Chronos** — amplified regions look falsely essential
- **Two-sided group test** — selective dependency is directional; use `alternative="less"`

## Grounding

`report`: DepMap release, dependency threshold, essentiality source (DepMap list vs a stated
frequency gate), n common-essential / selective-candidate genes; for normLRT — the R env and `sn`
version, n scored, n NA, and the three-part selectivity criterion; for the group test — n genes
tested, group sizes, FDR method, top genes with delta + p + padj.

## Sources

- McDonald et al. (2017) *Cell* — Project DRIVE, the normLRT score
- Pacini et al. (2021) *Nat Commun* — integrated dependency datasets; normLRT ≥ 100 + left-skew criterion
- `sn` (Azzalini) — `st.mple`, the reference skew-t fit · `MASS::fitdistr` — the normal fit
