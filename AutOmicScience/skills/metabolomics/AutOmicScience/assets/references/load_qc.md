# Reference — Metabolite Loading & QC

**Maturity: REFERENCE** — hand-rolled with `pandas` / `numpy`, both pinned. The filter thresholds and
the normalisation choice are study decisions; the code below is short because the judgment, not the
implementation, is the work.

Load metabolite/lipid intensity matrices, apply QC filters, normalise, log-transform.

## Format

Samples × features (metabolites/lipids) intensity matrix. Feature IDs: HMDB, KEGG, or lipid
shorthand (`lipid_nomenclature.md` parses the last of those).

```python
import pandas as pd
import numpy as np

mat = pd.read_csv("metabolites.csv", index_col=0)   # rows = samples, columns = features
```

## Zero means "not detected"

```python
mat = mat.replace(0, np.nan)      # do this FIRST — every step below depends on it
```

A zero intensity is a non-detection, not a measurement of zero. Carrying it as a number makes every
downstream step wrong: it drags means down, it inflates variance, and it survives the log transform
as a fabricated value (see the pitfall below). Decide explicitly what to do with the NaNs —
**leave them** (pairwise-complete tests), **impute at LOD/2**, or **drop the feature** — and report
which.

## QC filters

```python
detected = mat.notna().mean(axis=0)          # per-feature detection rate across samples
keep_detect = detected >= 0.8                # drop features missing in >20% of samples

cv = mat.std(axis=0) / mat.mean(axis=0)      # CV on the RAW scale, before log
keep_var = cv >= 0.1                         # drop constant / near-constant features

mat_clean = mat.loc[:, keep_detect & keep_var]
```

**CV belongs on the raw scale.** After log2 the mean of a feature can sit near zero, so `std/mean`
explodes or flips sign — a CV computed on logged intensities does not measure what the filter is for.

## Normalisation (before the log)

Sample-level intensity differences (dilution, injection volume) are **multiplicative**, so correct
them on the raw scale:

```python
def pqn(df):
    """Probabilistic quotient normalisation — the metabolomics default."""
    ref = df.median(axis=0)                  # reference spectrum
    quot = df.div(ref, axis=1)               # per-feature quotient vs reference
    return df.div(quot.median(axis=1), axis=0)   # divide each sample by its median quotient

norm = pqn(mat_clean)
```

Alternatives: **total-sum** (`df.div(df.sum(axis=1), axis=0)`) — simple but a few abundant features
dominate the sum; **quantile** — forces identical distributions, so use it only when you believe that
assumption. PQN is the usual choice for clinical/plasma panels.

If you normalise after logging instead, PQN's division must become a **subtraction**
(`logdf.sub(quot.median(axis=1), axis=0)`) — running the division-based code above on logged values
divides one log by another, which is not a correction of anything.

## Log-transform

```python
log_mat = np.log2(norm)          # NaNs stay NaN — no pseudocount
```

Metabolite intensities are right-skewed; log2 makes them usable by parametric tests and turns a fold
change into a difference.

## Pitfalls

- **`np.log2(mat + 1)`** — the RNA-seq pseudocount does not transfer. Metabolomics intensities run
  ~1e4–1e8, so a real floor lands near log2 ≈ 13 while `+1` maps a non-detection to log2 = 0. That
  gap (≈13 log2 units on typical data) is larger than any biological effect and will dominate every
  t-test, while looking like an ordinary low measurement. Replace zeros with NaN instead.
- **Filtering, then re-introducing zeros** — deciding on LOD/2 or drop in QC and then reaching for
  `+1` at the log step undoes the decision.
- **CV or normalisation on logged data** — both assume the raw, multiplicative scale.
- **Wrong axis** — `mat.notna().mean(axis=0)` is per-feature only when samples are rows. Check
  `mat.shape` against `n_samples` before trusting any filter.

## Grounding

`report`: n samples, n features in / out, detection-rate and CV thresholds, **how many features each
filter dropped**, the NaN policy (left / imputed at LOD-2 / dropped), normalisation method, and that
log2 was applied without a pseudocount.
