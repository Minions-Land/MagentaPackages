# Reference — Unsupervised Structure in a Sample × Feature Table

**Maturity: REFERENCE** — `scipy`, `scikit-learn` and `statsmodels` are all in the pinned `task1` env
(select it with `modality="scrna"` — an environment selector, not a claim about your data). Emit a
`report` dict and cite its numbers.

This is the home for analyses whose **unit is the sample, not the assay**: cluster the patients,
stratify the cohort, correlate the scores, decompose the matrix. The rest of this package indexes by
modality, so a `patient × score` table or a `patient × cell-type` matrix — built from metadata, with
no count matrix in sight — has nowhere else to land.

Every method below is standard `scipy`/`sklearn`. This doc exists to say **where it lives** and to
record the few things you cannot read off the API.

## Which decomposition

| Matrix | Use | Why |
|---|---|---|
| Dense, moderate features | `PCA` | the default |
| **Sparse, high-dimensional counts** (3'-end/UMI protocols, full-annotation gene sets) | **`TruncatedSVD`** | it factorises the sparse matrix directly. `PCA` mean-centres, which **densifies** — every structural zero becomes a stored float, and the matrix can no longer fit where the sparse one did. Same subspace, without the blow-up |
| Non-negative parts-based structure | `NMF` | W = sample loadings, H = feature coefficients |

Normalise before decomposing, and say how. For sparse count matrices, library-size scaling +
`log2(x+1)` then variance-based feature selection is the usual route; `bulk`'s
`normalization.md` covers the count-model alternatives and when each applies.

## Stability of a k

`sklearn.decomposition.NMF` is a single run from a random init — the factorisation is not unique. To
claim a k, run it many times and measure how often two samples land in the same cluster (a
connectivity matrix, averaged into a consensus matrix), then score that consensus with
`scipy.cluster.hierarchy.cophenet`.

**That cophenetic criterion is Brunet et al. 2004** — a sample × sample consensus. It is *not* cNMF's
k-selection (Alexandrov et al. 2013 lineage), so `single-cell/rna`'s `consensus_nmf.md` correctly says
it plays no part there. Different analysis, different matrix; both are fine, they just are not each
other.

## Distance from correlation

A correlation matrix becomes a distance with `1 - corr` before `scipy.cluster.hierarchy.linkage`.
State the correlation (Pearson assumes linearity; Spearman is the safe default for scores on unknown
scales) **and the linkage** — average/complete/Ward give visibly different trees on the same data, and
Ward assumes Euclidean distances, which `1 - corr` is not.

Reorder rows **and** columns by the same leaf order, or the heatmap will not show the blocks the
dendrogram found.

## Cluster vs clinical feature

Once samples carry a cluster label, testing it against covariates is an ordinary per-variable test —
but the variable's type picks the test, and mixing them up is the common error:

- **continuous / ordinal** (age, a severity or grading score, stage) → Kruskal-Wallis across clusters,
  Mann-Whitney for two
- **categorical** (sex, subtype, response) → chi-square, or Fisher when cells are small

Correct across the covariates tested, and say what the family was.

## Pitfalls

- **`PCA` on a large sparse matrix** — densifies; use `TruncatedSVD`
- **One NMF run treated as *the* answer** — it is one random init; measure stability or don't claim k
- **Ward on `1 - corr`** — Ward's objective assumes Euclidean geometry
- **Reordering rows only** — the heatmap stops matching the dendrogram
- **k chosen and never justified** — state the criterion (cophenetic, silhouette, elbow) and show it
- **A cluster-vs-covariate p with no family** — correcting across covariates is part of the claim

## Grounding

`report`: matrix shape and how it was built, normalisation, decomposition + n components, k with the
criterion that chose it, cluster sizes, and per-covariate test + statistic + p + the correction family.
