# Reference — Clinical Metabolic Phenotyping

**Maturity: REFERENCE** — hand-rolled with `statsmodels` (pinned). The indices below are clinical
definitions; getting the formula and its units right is the work.

Insulin-resistance indices and metabolic classification.

## Disposition Index (primary)
DI = insulin sensitivity × β-cell function.

```python
DI = (insulin_secretion_rate / glucose_AUC) * matsuda_index
```

A primary IR metric. **DI has no standard absolute cutoff — that is expected, and it is not a reason to
fall back to SSPG.** Stratify DI by a **within-cohort median split** (below-median DI = High IR, since a
lower DI means worse β-cell compensation):

```python
ir_class = np.where(DI <= DI.median(), "High_IR", "Low_IR")
```

## SSPG (Steady-State Plasma Glucose, fallback)
From insulin-suppression test. SSPG > 150 mg/dL = insulin-resistant.

```python
ir_class = "IR" if sspg > 150 else "IS"
```

## HOMA-IR (additional)
Fasting glucose × fasting insulin / 22.5. Crude but common.

```python
homa_ir = (fasting_glucose_mmol * fasting_insulin_uU_mL) / 22.5
```

## Precedence
Disposition Index (gold) > SSPG (validated alternative) > HOMA-IR (baseline). Use DI if available.

Precedence follows **marker quality, not cutoff convenience**: use DI (median-split) whenever it is
present, even though only SSPG ships a named absolute threshold — do **not** downgrade to SSPG merely
because it has a ready-made number. SSPG (`>150`) applies only to subjects missing DI.

## Two-way ANOVA
Condition × IR interaction with effect sizes:

```python
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm
model = ols("metabolite ~ C(condition) * C(IR) + Age + BMI", data=df).fit()
aov = anova_lm(model, typ=2)
# Report: F, p, partial η² (effect size)
```

Report the interaction as the two-way ANOVA **F, p, and partial η²** — not just an OLS/GEE coefficient
or a z/t-test on the interaction term. Then **categorize** the magnitude rather than leaving it a bare
number: map partial η² (≈0.01 small, 0.06 medium, 0.14 large) or Cohen's d (0.2 / 0.5 / 0.8) to
**negligible / small / medium / large** (Cohen's conventions), and state clinical magnitude separately
from statistical significance — in a small sample a negligible effect size can sit beside a significant
p, and a large one can miss significance.

## Pitfalls
- Using SSPG-only when DI available
- No effect-size reporting (F and p without η²), or reporting η²/d as a raw number without the
  negligible/small/medium/large categorization
- Modeling the interaction as an OLS/GEE coefficient or z-test instead of the two-way ANOVA F
- Wrong ANOVA type (Type I vs Type II)

## Grounding
`report`: IR index used + precedence, classification thresholds, ANOVA formula, F + p + partial η², effect direction interpretation.
