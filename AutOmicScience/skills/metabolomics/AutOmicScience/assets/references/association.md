# Reference — Covariate-Adjusted Association (OLS)

**Maturity: REFERENCE** — hand-rolled per-feature OLS with `statsmodels` (pinned). Which covariates
enter the model is the study decision this doc exists to guide.

Per-metabolite OLS with clinical covariates.

## OLS per feature
```python
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

results = []
for feat in log_mat.columns:
    df = pd.DataFrame({"y": phenotype, "feat": log_mat[feat],
                       "Age": age, "BMI": bmi})
    model = smf.ols("y ~ feat + Age + BMI", data=df).fit()
    results.append({"feature": feat, "coef": model.params["feat"],
                    "p": model.pvalues["feat"]})
res = pd.DataFrame(results)
res["padj"] = multipletests(res.p, method="fdr_bh")[1]
```

## Thresholds
- Directionality matters: positive coef = metabolite↑ when phenotype↑
- **BH-FDR is the default gate**, because a per-metabolite screen is hundreds to thousands of tests
  and the uncorrected count is mostly noise at typical cohort sizes.
- **When the question states a threshold, that is the gate** — report counts at exactly the thresholds
  asked for, and put the FDR-adjusted count beside them. A screen reported at raw p is
  hypothesis-generating; say so and it is honest. Silently substituting a stricter gate answers a
  different question than the one asked.

## Pitfalls
- Wrong direction interpreted
- No FDR correction
- Non-log-transformed intensities

## Grounding
`report`: model formula, n features tested, n significant, top hits with coef + p + padj.
