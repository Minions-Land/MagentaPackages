# Reference — Differential Abundance (DESeq2 / ANCOM / ALDEx2)

**Maturity: PARTIAL — per method, not as a whole.** Only DESeq2 runs on the pinned stack:

| Method | Needs | State |
|---|---|---|
| **DESeq2** | `pydeseq2` | **pinned** in `task1–4` — run it as-is |
| **ANCOM / ANCOM-BC** | `scikit-bio` | not pinned — provision (below) |
| **ALDEx2** | R + Bioconductor `ALDEx2` + `rpy2` | not pinned, and costly: `pixi.toml`'s `r` feature is composed by no environment and lacks ALDEx2 — prefer ANCOM-BC |
| **Per-taxon Cox** | `lifelines` | not pinned — provision (below) |

Provision the missing ones per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`: §A a new
Pixi feature + environment with its **own solve-group** (preferred — lands in `pixi.lock`), composing
`["core", "singlecell", <new>]` so the pinned stack comes with it. Never a bare `pip install` (it can
land in `base`), and never add these pins to `task1–4`. `omics_preflight` does not cover non-standard
envs — check the import yourself and record the env + versions in the `report`. If a method can be
neither imported nor provisioned, that is a **blocker**, not a cue to substitute a weaker one.

Testing which taxa differ in abundance between conditions.

## Method 1: DESeq2 (count-based, negative-binomial)
```python
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

# abundance: taxa × samples (counts)
metadata = pd.DataFrame({"condition": conditions, "batch": batches}, index=abundance.columns)
dds = DeseqDataSet(counts=abundance.T, metadata=metadata, design="~condition + batch")
dds.deseq2()
stat = DeseqStats(dds, contrast=["condition", "disease", "healthy"])
res = stat.summary()
# res: log2FoldChange, pvalue, padj per taxon
```

DESeq2 handles zero-inflation and compositional effects via size factors. Standard for RNA-seq, adopted for microbiome.

## Method 2: ANCOM / ANCOM-BC (compositionally-aware)

`scikit-bio` implements both — do not reach for R or hand-roll the log-ratio tests:

**ANCOM-BC (preferred)** — bias-corrected, takes covariates, returns effect sizes with FDR:

```python
from skbio.stats.composition import ancombc

# table is samples × taxa; metadata is indexed by sample
res = ancombc(table=abundance.T, metadata=metadata, formula="condition + batch")
# res: DataFrame with Log2(FC), SE, W, pvalue, qvalue — indexed by (FeatureID, Covariate),
# so pick the covariate you care about: res["qvalue"].xs("condition[T.B]", level="Covariate")
```

**ANCOM (original)** — only if you need its W for comparability with an older analysis:

```python
from skbio.stats.composition import ancom, multi_replace

# ancom takes a composition, not raw counts with zeros — replace them multiplicatively
comp = multi_replace(abundance.T.values)
res, _ = ancom(pd.DataFrame(comp, index=abundance.columns, columns=abundance.index),
               grouping=pd.Series(conditions, index=abundance.columns))
# res columns: W, Signif
```

`ancom` returns a **W statistic, not a p-value**: W counts how many of a taxon's pairwise log-ratio
tests rejected, so it ranks taxa rather than thresholding at 0.05, and it cannot take covariates.
That is the reason to prefer `ancombc`.

> **`multi_replace`, not `+1`.** ANCOM operates on compositions; multiplicative replacement swaps
> zeros for a small δ while keeping each sample summing to 1, which a `+1` pseudocount does not do.

## Method 3: ALDEx2 (CLR + Monte Carlo) — R only

```R
library(ALDEx2)
aldex_out <- aldex(counts, conditions, mc.samples=128, test="t")
# Returns effect size (diff.btw / diff.win) + p-value
```

ALDEx2 is strict; low false-positive rate but lower power. **Provisioning it is a real cost**:
`pixi.toml`'s `r` feature (r-base, r-essentials, dplyr, ggplot2) is composed by no environment and
does not include Bioconductor's ALDEx2, so you would be adding R + Bioconductor + `rpy2` for this one
method. Reach for `ancombc` first — same compositional rigour, already in the Python stack you are
provisioning anyway.

## Which method?
- **DESeq2** — standard, fast, handles covariates (batch), good power · **pinned**
- **ANCOM-BC** — compositionally-aware, covariates, effect sizes + p-values · needs `scikit-bio`
- **ANCOM** — compositionally-aware, conservative, no covariates, W statistic only · needs `scikit-bio`
- **ALDEx2** — compositionally-strict, lowest FPR, lowest power · R only, **not provisioned here**

Start with DESeq2 (it runs today); validate with **ANCOM-BC** if compositionality is a concern.

## Thresholds
`|log2FC| > 1` (2-fold) AND `padj < 0.05`

## Univariate per-taxon Cox (for survival integration) — needs `lifelines`
```python
from lifelines import CoxPHFitter
from statsmodels.stats.multitest import multipletests

results = []
for taxon in clr_abundance.index:
    df = pd.DataFrame({"time": time, "event": event, "taxon": clr_abundance.loc[taxon]})
    cph = CoxPHFitter()
    cph.fit(df, duration_col="time", event_col="event")
    results.append({"taxon": taxon, "HR": cph.hazard_ratios_["taxon"],
                    "p": cph.summary.loc["taxon", "p"]})
res = pd.DataFrame(results)
res["padj"] = multipletests(res.p, method="fdr_bh")[1]
```

This is the univariate-Cox-per-taxon pattern.

## Pitfalls
- DESeq2 on CLR-transformed data (DESeq2 wants raw counts)
- ANCOM without prevalence filtering (slow, unstable)
- No FDR correction (thousands of taxa tested)
- Ignoring batch effects (sequencing run, extraction kit)

## Grounding
`report`: method (DESeq2/ANCOM/ALDEx2), covariates in design, n taxa tested, n significant (padj<0.05), top taxa with log2FC + padj + taxonomy.
