# Benchmarking phase-separation predictors (ROC-AUC)

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

Goal: quantify how well each phase-separation predictor separates a positive set (condensate /
PS proteins) from a negative set, fairly and per-mechanism.

## Predictors you will encounter

| Predictor | Prior it encodes | Direction |
|-----------|------------------|-----------|
| **PScore** (Vernon 2018) | planar π-π contact propensity | higher = more PS-prone |
| **PLAAC** (Lancaster 2014) | prion-like (Q/N) composition, HMM | higher = more prion-like |
| **catGRANULE** (Bolognesi 2016) | RNA-granule propensity (disorder + RNA-binding) | higher = more PS-prone |
| **FuzDrop** (Hardenberg 2020) | droplet-promoting probability p_DP | higher = more PS-prone |
| composite SaPS/PdPS feature models | multi-feature, mechanism-specific (self-assembling vs partner-dependent) | higher = more PS-prone |

Predictors carry different scales and different missingness — treat each independently.

## 1. Fair set construction

- Positives from dataset membership; negatives from a **single fixed background set** reused across
  every comparison (so AUCs are comparable across datasets and predictors).
- Remove any protein that appears in both positive and negative for a given comparison.
- Encode labels as 1 (positive) / 0 (negative).

## 2. Per-predictor, per-comparison AUC

```python
from sklearn.metrics import roc_auc_score
import numpy as np

def auc_table(df, predictor_cols, label_col="label"):
    rows = []
    for p in predictor_cols:
        sub = df[[p, label_col]].dropna()               # NaN handling per predictor
        y = sub[label_col].values
        if len(np.unique(y)) < 2 or len(sub) < 10:       # need both classes + enough points
            rows.append((p, np.nan, len(sub), "insufficient")); continue
        auc = roc_auc_score(y, sub[p].values)
        rows.append((p, auc, len(sub), "ok"))
    return pd.DataFrame(rows, columns=["predictor", "auc", "n", "status"])
```

- **NaN is dropped per (predictor, comparison)** — different predictors cover different proteins,
  so the evaluated set differs; report `n` for each.
- **Score orientation:** all predictors above are "higher = more PS-prone". If a column is
  reverse-scored, negate it before `roc_auc_score`. An AUC well below 0.5 usually signals a flipped
  orientation, not a useless predictor — investigate before reporting.
- Run this **separately per PS-type** (e.g. SaPS-vs-NoPS, PdPS-vs-NoPS) and per dataset.

## 3. Multiple datasets vs a control group

When several positive datasets (e.g. distinct membraneless-organelle sets) are compared against a
control group (e.g. membrane-bound organelle proteins), against the same fixed negative background:

1. Compute AUC for **every dataset × predictor** cell.
2. Aggregate per group: mean predictor AUC per dataset; mean over the control set.
3. Test the group difference with a **paired test across predictors** (pairing on predictor, since
   predictors are the repeated unit), e.g.:

```python
from scipy.stats import wilcoxon
# mlo_auc, ctrl_auc: paired arrays, one value per predictor (or per dataset×predictor pair)
stat, p = wilcoxon(mlo_auc, ctrl_auc, alternative="greater")   # one-sided: MLO > control
```

4. State the conclusion **consistent with the numbers** — if mean MLO AUC ≈ control AUC, say the
   predictors do not discriminate, regardless of prior expectation.

## 4. Reporting

- AUC matrix: rows = datasets/comparisons, cols = predictors; include per-cell `n`.
- Which predictor wins for which PS-type / dataset, with the numeric AUC.
- The group-comparison statistic (test name, one/two-sided, p-value) and the aggregated means.
- Any predictor-comparison marked "insufficient" (missing class or too few points) and why.
- ROC curves → inspect before interpretation.
