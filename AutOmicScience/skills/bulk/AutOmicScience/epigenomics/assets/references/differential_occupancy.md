# Reference — Differential Occupancy / Accessibility

**Maturity: REFERENCE** — hand-rolled on the pinned stack. `pydeseq2` 0.5.4 and `pysam` are both in
`task1` (`modality="scrna"` — an environment selector, not a claim about your data). Verified against
pydeseq2 0.5.4 (executed).

## The count matrix

Count reads in consensus peaks per sample (peaks × samples).

**The `bedtools` CLI is not installed — `pysam` is, and it does this.** `AlignmentFile.count(chrom,
start, end)` is what `bedtools multicov` computes per interval, and `.mapped` gives the library size
for CPM without a second pass. Counting a genome-wide peak set is cheap enough to do in-session.

If your pipeline already produced a count matrix (`featureCounts`, `bedtools multicov`,
nf-core/chipseq), read it instead — but the absence of `bedtools` is not a reason to stop.

```python
import pandas as pd
counts = pd.read_csv("peak_counts.txt", sep="\t", header=None)
peak_ids = counts.iloc[:, :3].astype(str).agg("_".join, axis=1)
count_matrix = counts.iloc[:, 3:]
count_matrix.index = peak_ids
count_matrix.columns = sample_names
```

**Replicates decide the test, not the tool.** `pydeseq2` estimates dispersion across replicates; with
n=1 per condition it has nothing to estimate from. That is a property of the design — pick a test that
matches it (a count model on the two libraries, an exact test, a permutation) and say which, rather
than reporting a fold-change with no p-value.

## Method 1: DiffBind (R, gold standard) — PARTIAL, not installed

```python
# Via rpy2, or run an R script
# dba → dba.count → dba.contrast → dba.analyze
# Returns differential peaks with Fold, p, FDR
```

DiffBind handles the ChIP-specific normalization (library size, effective genome size) and is the community
standard. It is **not in any environment here** (nor is `rpy2`); `r-env` ships `r-base` + `r-essentials`
only. Use Method 2, or report the missing R stack as a blocker.

## Method 2: pydeseq2 (pure Python) — the default here; runs on `task1`

Treat peaks like genes — negative-binomial DE on the count matrix:

```python
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

metadata = pd.DataFrame({"condition": conditions}, index=sample_names)
# `design=` — `design_factors=` is deprecated in pydeseq2 0.5.x and will be removed.
dds = DeseqDataSet(counts=count_matrix.T, metadata=metadata, design="~condition")
dds.deseq2()
stat = DeseqStats(dds, contrast=["condition", "treated", "control"])

# summary() returns None — it POPULATES stat.results_df. `res = stat.summary()` binds None, and the
# next line (`res.log2FoldChange`) dies with AttributeError.
stat.summary()

# Shrink before ranking — the parent skill requires it, and it matters MORE for peaks than for genes:
# peak counts are lower and noisier, so unshrunk LFCs over-weight low-count peaks. The coeff must be a
# real LFC column name (formulaic style), not R-DESeq2's "condition_treated_vs_control".
stat.lfc_shrink(coeff=dds.varm["LFC"].columns[-1])        # -> 'condition[T.treated]'
res = stat.results_df.dropna(subset=["padj"])
# res: baseMean, log2FoldChange (shrunken), lfcSE, stat, pvalue, padj (per peak)
```

## Method 3: CPM + descriptive log2FC (n=2, no proper model)

When replicates are too few for a statistical model (n=2), report descriptive fold-changes with an explicit caveat:

```python
import numpy as np
cpm = count_matrix / count_matrix.sum(axis=0) * 1e6
log2fc = np.log2(cpm[treated_cols].mean(axis=1) + 1) - np.log2(cpm[control_cols].mean(axis=1) + 1)
# CAVEAT: n=2 gives no valid p-value; this is descriptive ranking only
```

**Flag the n=2 limitation** — with 2 replicates, DESeq2's dispersion estimate is unstable; report fold-changes as exploratory.

## Thresholds

- **|log2FC| > 1** (2-fold) + **padj < 0.05** — a common convention, not a standard. State it; a
  neighbouring choice is equally defensible. Report counts at whatever thresholds the question names.

```python
gained = res[(res.log2FoldChange > 1) & (res.padj < 0.05)]
lost = res[(res.log2FoldChange < -1) & (res.padj < 0.05)]
```

**Testing a fold-change threshold properly.** Filtering `padj` from an `lfc_null=0` fit and *then* applying
`|log2FC| > 1` tests the null "no change at all" and post-hoc filters the effect size — it does not test
"changes by more than 2-fold". pydeseq2 exposes the real threshold test (the DESeq2 `lfcThreshold` /
`altHypothesis` mechanism), so use it when the 2-fold claim is the point:

```python
stat = DeseqStats(dds, contrast=["condition", "treated", "control"],
                  lfc_null=1.0, alt_hypothesis="greaterAbs")   # H0: |LFC| <= 1
```

`alt_hypothesis` accepts `"greaterAbs" | "lessAbs" | "greater" | "less"` — `"greater"`/`"less"` are the
directional (one-sided) forms, e.g. for testing H3K27ac depletion after treatment. Verified on pydeseq2
0.5.4. Do not hand-roll a one-sided p from a two-sided fit.

## Normalization considerations

- **Library size** — deeper-sequenced samples have more reads per peak; DESeq2 size factors handle this
- **Effective genome size** — differs by assay; DiffBind accounts for it
- **Spike-in normalization** — for global changes (e.g., global H3K27me3 loss), spike-in is more accurate than library-size normalization

## Pitfalls

- **`AttributeError: 'NoneType' object has no attribute 'log2FoldChange'`** — `res = stat.summary()` binds
  `None`; `summary()` populates `stat.results_df` as a side effect. Call it, then read the attribute.
- **`KeyError` from `lfc_shrink`** — the coeff is formulaic-style (`condition[T.treated]`), not R's
  `condition_treated_vs_control`. Read it off `dds.varm["LFC"].columns`.
- **Ranking unshrunk peak LFCs** — the top "most changed" peaks come back as low-count noise. Shrink first;
  this bites harder on peaks than on genes.
- **n=2 treated as high-confidence** — flag the caveat; dispersion is unstable
- **Not merging replicate peaks first** — inflates the peak set
- **Wrong contrast direction** — verify treated vs control in the summary
- **CPM without size factors for statistical tests** — use DESeq2 normalization, not raw CPM, when computing p-values
- **No FDR** — thousands of peaks need BH correction

## Grounding

`report`: count method (multicov/featureCounts + who produced it), n peaks tested, DE method
(DiffBind/pydeseq2/CPM), **shrinkage coeff** (or an explicit note that shrinkage was skipped and why),
`lfc_null`/`alt_hypothesis` if a threshold test was used, replicate count + caveat if n≤2, n gained/lost
with thresholds, top peaks with log2FC + padj.

## Sources

- Love, Huber & Anders 2014, *Genome Biology* 15:550 — DESeq2 (size factors, `lfcThreshold`/`altHypothesis`).
- Zhu, Ibrahim & Love 2019, *Bioinformatics* 35:2084 — apeglm LFC shrinkage.
- Muzellec et al. 2023, *Bioinformatics* — PyDESeq2.
- Ross-Innes et al. 2012, *Nature* 481:389 — DiffBind (differential binding for ChIP-seq).
- Stark & Brown, DiffBind Bioconductor vignette — ChIP-specific normalization choices.
