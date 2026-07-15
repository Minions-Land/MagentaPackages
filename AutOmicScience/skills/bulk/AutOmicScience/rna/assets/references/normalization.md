# Normalization & filtering (bulk RNA-seq)

**Maturity: REFERENCE** — hand-rolled, and the **VST path runs on the pinned stack** with no provisioning
(`pydeseq2` 0.5.4 in `task1`, `modality="scrna"`). The **edgeR path is PARTIAL**: `edgeR` is **not
installed in any environment**, so `filterByExpr` / `calcNormFactors` / `cpm` need their own env
(`omics-shared`'s `assets/references/AOSE_nonStandard_env.md`, §A). The Python filter below is usually
enough — reach for R only if you specifically need edgeR's exact rule. Verified against pydeseq2 0.5.4.

Pick normalization **by goal**. A common error is z-scoring raw counts, or using log-CPM as a differential-
expression model input.

| Goal | Use | Why |
|---|---|---|
| **DE model input** | raw counts → DESeq2 size factors / edgeR TMM (the model normalizes internally) | count models want raw counts; they estimate the offset |
| **Clustering / PCA / heatmaps** | **VST** ← the one that runs here; *(rlog, or TMM→logCPM via `edgeR::cpm(log=TRUE)`, need R — PARTIAL)* | variance-stabilized, homoscedastic, comparable across samples |
| **Cross-sample viz of a few genes** | logCPM or VST | not raw counts |

## Low-expression filtering (do this first)

**Python (runs today).** This *approximates* `filterByExpr`'s main rule — a 10-count-equivalent CPM floor,
met in at least as many samples as the smallest group. It is not a reimplementation: edgeR also applies
`min.total.count`, `large.n`, and `min.prop`. Say "filterByExpr-style", not "filterByExpr".

```python
grp    = meta["condition"]
min_n  = grp.value_counts().min()                         # size of the smallest group
lib    = counts.sum(axis=1)                               # counts: samples x genes
cutoff = 10 / (lib.median() / 1e6)                        # edgeR's min.count=10 -> a CPM cutoff
cpm    = counts.div(lib, axis=0) * 1e6
keep   = (cpm >= cutoff).sum(axis=0) >= min_n
counts = counts.loc[:, keep]
# report: {"filter": f"CPM >= {cutoff:.3f} (10-count equiv.) in >= {min_n} samples", "n_genes_kept": int(keep.sum())}
```

**R (PARTIAL — `edgeR` is in no environment here):**

```r
# edgeR::filterByExpr — the idiomatic filter (keeps genes with enough counts in the smallest group)
library(edgeR); dge <- DGEList(cts, group=meta$condition)
keep <- filterByExpr(dge, group=meta$condition); dge <- dge[keep,, keep.lib.sizes=FALSE]
dge  <- calcNormFactors(dge, method="TMM")             # TMM normalization factors
logcpm <- cpm(dge, log=TRUE, prior.count=1)            # for viz/clustering
```

## VST for clustering / PCA (DESeq2) — runs on `task1`

```python
from pydeseq2.dds import DeseqDataSet
# `design=` — `design_factors=` is deprecated in pydeseq2 0.5.x (see de.md).
dds = DeseqDataSet(counts=counts, metadata=meta, design="~condition"); dds.deseq2()
dds.vst()                        # variance-stabilized matrix in dds.layers["vst_counts"]
# → use dds.layers["vst_counts"] for PCA / Ward clustering / heatmaps (not raw counts, not z-scored counts)
```

`rlog` has **no pydeseq2 equivalent** (`dds` exposes `vst`/`vst_fit`/`vst_transform` and nothing else), so
on this stack VST is the option that exists. Say "VST", not "rlog/VST", when you report — and if a reviewer
specifically wants rlog, that is an R env to provision, not a synonym to swap in.

## Rules

- **Do not** feed TPM/FPKM or log-CPM to a count model (DESeq2/edgeR) as if they were counts.
- **Do not** z-score raw counts for clustering — variance scales with the mean; variance-stabilize (VST/rlog) first.
- For very sparse / low-count matrices, a variance-stabilizing transform before PCA (or a sparse-aware
  decomposition) is more appropriate than dense PCA on raw counts.
- State the exact normalization + filter thresholds you used, so the analysis is reproducible.

## Sources

- Anders & Huber 2010, *Genome Biology* 11:R106 — size-factor normalization (+ DESeq2 VST, Love et al. 2014).
- Robinson & Oshlack 2010, *Genome Biology* 11:R25 — TMM normalization (edgeR).
- Chen, Lun & Smyth 2016, *F1000Research* — `filterByExpr` / edgeR RNA-seq DE workflow.
