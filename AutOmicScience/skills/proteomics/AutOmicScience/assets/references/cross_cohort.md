# Reference — Cross-Cohort Hypergeometric Enrichment

**Maturity: REFERENCE** — hand-rolled in a Python script with `scipy.stats.hypergeom` (pinned).
The universe definition is the whole analysis; no library can pick it for you.

Testing whether upregulated proteins in cohort A are enriched among upregulated proteins in cohort B — the key test for replication across independent studies.

## The hypergeometric setup

**Question:** Are the "hits" in cohort A over-represented in the "hits" in cohort B, beyond what's expected by chance?

**Hypergeometric parameters:**
- **M**: total universe size (all proteins measured in both cohorts)
- **N**: number of "successes" in the urn (proteins upregulated in cohort A)
- **n**: number of draws (proteins upregulated in cohort B)
- **k**: observed overlap (proteins upregulated in both)

**P(X ≥ k)** = probability of seeing ≥k overlap by chance.

```python
from scipy.stats import hypergeom

# Cohort A: DE results
up_A = set(de_A[(de_A.padj < 0.05) & (de_A.log2FC > 0.5)].protein)
# Cohort B: DE results
up_B = set(de_B[(de_B.padj < 0.05) & (de_B.log2FC > 0.5)].protein)

# Universe = proteins measured in BOTH cohorts (intersection of tested sets)
universe = set(de_A.protein) & set(de_B.protein)
M = len(universe)
N = len(up_A & universe)  # up in A, and in the shared universe — the `& universe` is load-bearing
n = len(up_B & universe)  # up in B, and in the shared universe
k = len(up_A & up_B)      # overlap

p = hypergeom.sf(k - 1, M, N, n)  # P(X ≥ k), sf(k-1) = 1 - cdf(k-1)
print(f"Overlap: {k} / {n} (p={p:.3e})")
```

> ### Intersect with the universe *before* counting, not after
>
> `N = len(up_A)` is the tempting shortcut and it is wrong — not conservative, wrong. It counts
> proteins cohort B never measured, so they are not in the urn and the hypergeometric no longer
> describes anything.
>
> The failure is silent and can be enormous. On a whole-proteome cohort A against an Olink panel B,
> `len(up_A)` can exceed `M` outright — and `hypergeom.sf(k-1, M, N, n)` with `N > M` returns
> **`nan` without raising**. `nan` prints as a number, formats as a p-value, and lands in the report.
> Measured on a realistic pair, the un-intersected form was off by ~16 orders of magnitude before it
> tipped over into `nan`.
>
> (`k = len(up_A & up_B)` needs no `& universe`: `up_A ⊆ de_A.protein` and `up_B ⊆ de_B.protein`, so
> their intersection is already inside it. `N` and `n` are the ones that escape.)

## Critical: the universe must be the measured proteins

**WRONG:** using the full human proteome (~20,000 genes) as M.

**RIGHT:** using only the proteins **measured in both cohorts** (the intersection of tested sets).

Why? If cohort A measures 1,000 proteins and cohort B measures 500 (different panels), you can't draw from the 19,500 unmeasured proteins. The hypergeometric denominator is the shared, testable space.

## Directional concordance

"Overlap" means **directionally concordant** (both up, or both down), not just significant in both:

```python
# Upregulated in both
up_both = (
    set(de_A[(de_A.padj < 0.05) & (de_A.log2FC > 0.5)].protein) &
    set(de_B[(de_B.padj < 0.05) & (de_B.log2FC > 0.5)].protein)
)

# Downregulated in both
down_both = (
    set(de_A[(de_A.padj < 0.05) & (de_A.log2FC < -0.5)].protein) &
    set(de_B[(de_B.padj < 0.05) & (de_B.log2FC < -0.5)].protein)
)

# Total concordant
concordant = up_both | down_both
# Discordant = sig in both but opposite directions
discordant = (
    (set(de_A[de_A.padj < 0.05].protein) & set(de_B[de_B.padj < 0.05].protein)) -
    concordant
)
```

Report concordant vs discordant separately. Discordance suggests batch effects or biological heterogeneity.

## The hit definition is a decision, not a constant

`padj < 0.05 & log2FC > 0.5` above is an example, not the rule. The question sets it: FDR only, FDR +
effect, a top-N ranked list, or every feature carrying an estimate. Two cohorts screened at different
cutoffs are not comparable, so if both sides are thresholded, say which cutoff you applied to each and
why.

> **Do not carry an effect-size cutoff across cohorts whose estimates are in different units.**
> An NPX log2 delta and a per-unit regression β are not the same quantity. A 0.5 cutoff that keeps
> hundreds on one side can keep ~0 on the other, and the overlap then comes out **empty with no
> error** — the analysis looks completed and finds nothing. `de_A.estimate.abs().describe()` next to
> `de_B.estimate.abs().describe()` shows this in one line; check before importing a threshold.

## Full example: cross-cohort replication

```python
# Cohort A: upregulated in sepsis vs healthy
up_A = set(de_cohortA[(de_cohortA.padj < 0.05) & (de_cohortA.log2FC > 0.5)].protein)
# Cohort B: same
up_B = set(de_cohortB[(de_cohortB.padj < 0.05) & (de_cohortB.log2FC > 0.5)].protein)

# Universe
universe = set(de_cohortA.protein) & set(de_cohortB.protein)
M = len(universe)
N = len(up_A & universe)
n = len(up_B & universe)
k = len(up_A & up_B)

p = hypergeom.sf(k - 1, M, N, n)
print(f"Replication: {k}/{n} proteins upregulated in both cohorts (p={p:.3e})")
```

## Pitfalls

- **Universe = full proteome** — inflates p (wrong denominator)
- **No directional concordance check** — conflating discordance with replication
- **Threshold mismatch** — cohort A log2FC>0.5, cohort B log2FC>1.0
- **Not intersecting the tested sets** — proteins only measured in one cohort counted in M
- **Ranking by p-value instead of overlap size** — a 2/3 overlap (67%) can be more interesting than 10/100 (10%) even if the latter has lower p

## Grounding

`report`: M (universe size), N (cohort A hits in universe), n (cohort B hits in universe), k (observed overlap), p-value, concordant vs discordant breakdown.