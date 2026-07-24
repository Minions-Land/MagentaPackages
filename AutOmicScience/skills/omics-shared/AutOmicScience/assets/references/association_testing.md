# Reference — Association Testing (cross-modality)

**Maturity: REFERENCE** — `scipy`, `statsmodels` and `pandas` are in the pinned `task1` env (select it
with `modality="scrna"` — an environment selector, not a claim about your data). Emit a `report` dict
and cite its numbers.

"Does feature X associate with phenotype Y, adjusted for Z?" is asked of every modality, so it belongs
to none of them. This is its home. The modality skills own the **data** (what a feature is, how it was
normalised, what a sensible covariate is); this doc owns the parts that are the same everywhere.

The models themselves are ordinary `statsmodels`/`scipy` — `smf.ols("y ~ feat + age + bmi")`,
`spearmanr`, `fisher_exact`, `anova_lm`. What follows is what those APIs do not tell you.

## The correction family is a decision

BH-FDR corrects **within a family of tests that answer one question**. Choosing the family is part of
the analysis, not a mechanical step:

- Screening every feature against one phenotype → one family, one BH pass.
- The same screen run **pooled and then within each treatment arm** → these are **different families**.
  One global BH across all three mixes them, and the pooled result then borrows evidence from the
  strata (and vice versa). Correct within each, and say so.
- Testing several phenotypes → per-phenotype families unless the question is explicitly "anything
  anywhere", in which case say that.

Report raw **and** adjusted p, plus the family size. A q-value whose family is unstated is not
interpretable.

## Repeated measures and nested designs

`statsmodels.MixedLM` is **pinned** — a random intercept per participant needs no provisioning:

```python
import statsmodels.formula.api as smf
smf.mixedlm("npx ~ timepoint + age", df, groups=df.subject).fit()
```

Reach for it when the same subject contributes several rows (timepoints, replicates, tissues). A
plain OLS over those rows treats them as independent and understates the standard errors. Paired
designs with exactly two timepoints are the special case where `ttest_rel` is equivalent and simpler.

## Correlation as a screen

Pearson assumes linearity; Spearman is the safe default for scores on unknown scales and is what most
per-feature screens want. Both need a minimum n stated — a ρ over six samples is not evidence.

Report the **ranking axis** you used and why: "which associate most strongly" is a question about
effect size; "which are most significant" is about evidence. They give different orders.

## Interaction and stratification

"Does the effect differ between groups?" is **not** answered by testing each group separately and
comparing the two p-values — two significant-vs-not results can arise from the same underlying effect.
It needs an interaction term:

```python
smf.ols("pct ~ disease * ethnicity", df).fit()   # the disease:ethnicity coefficient is the claim
```

Stratified estimates describe each group; the interaction tests whether they really differ.

For a **balanced factorial design** (two categorical factors, e.g. condition × group), the same model is
conventionally reported as a **two-way ANOVA** — `anova_lm(model, typ=2)` gives the interaction
**F-statistic and partial η²**, which many fields expect over the raw OLS coefficient. When the outcome is
a clinical/physiological or metabolic-phenotype index, the `metabolomics` skill's
`assets/references/clinical_metabolic.md` carries the index precedence and the two-way-ANOVA template for
exactly this kind of condition × group question.

## Pitfalls

- **One global BH across pooled + per-stratum tests** — mixes families; correct within each
- **Comparing two p-values to claim a difference in effect** — use an interaction term
- **OLS over repeated measures** — understates SE; `MixedLM` is pinned
- **A q-value with no stated family** — not interpretable
- **Covariates chosen after seeing the result** — pre-specify them, or say that you did not
- **ρ or OR with no n** — report the n that produced it

## Grounding

`report`: model + formula, covariates and why, n per test, correction method **and family**, raw and
adjusted p, effect size with its direction, and the ranking axis.
