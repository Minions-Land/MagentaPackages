# Reference — Mediation (DE ∩ Correlation vs Formal)

**Maturity: REFERENCE** — hand-rolled with `statsmodels` (pinned). The integration heuristic is a set
operation; the formal path is `statsmodels.stats.mediation.Mediation`, which you call, not reimplement.

Two legitimate approaches, chosen by the question: a DE ∩ phenotype-correlation integration heuristic vs formal causal mediation.

## Integration heuristic (DE ∩ phenotype-correlation)
A screen that nominates candidate *mediating* species: features that are both DE (metabolite ↑ in condition) AND correlated with the phenotype (integration, not a causal estimate).

```python
de_up = set(de_res[(de_res.padj < 0.05) & (de_res.log2FC > 0.5)].feature)
corr_pos = set(corr_res[(corr_res.padj < 0.05) & (corr_res.r > 0)].feature)
mediators = de_up & corr_pos
```

## Formal causal mediation
Baron-Kenny steps or `statsmodels.mediation`:

```python
import statsmodels.formula.api as smf
from statsmodels.stats.mediation import Mediation

# Pass UNFITTED model objects — Mediation refits them internally on each bootstrap draw.
outcome_model  = smf.ols("Y ~ X + M", df)     # outcome on exposure + mediator
mediator_model = smf.ols("M ~ X", df)         # mediator on exposure
res = Mediation(outcome_model, mediator_model, exposure="X", mediator="M").fit(n_rep=200)
print(res.summary())   # ACME (indirect), ADE (direct), Total effect, Prop. mediated
# ACME (indirect effect), ADE (direct), proportion mediated
```

## Which to use
- **Identify/nominate mediating species** from DE + correlation: integration heuristic (DE∩correlation)
- **Estimate a causal/indirect effect**: formal mediation (causal pathway)

The word *mediate/mediating* in a question does **not** by itself call for formal mediation. "Which
species mediate X?" asks you to **nominate** candidates → integration heuristic (the default; run DE and
correlation separately, then intersect). Reserve formal mediation for an explicit request to **estimate**
an indirect effect (ACME/proportion mediated).

> **Do not call `.fit()` on the models first.** `Mediation` needs the model objects, not their
> results — passing `smf.ols(...).fit()` raises `AttributeError: 'OLSResults' object has no attribute
> 'exog'`, which names nothing useful about the actual mistake.

## Pitfalls
- Mediation approach mismatched to the question (integration heuristic nominates candidates; formal mediation estimates the indirect effect)
- Not testing both DE and correlation separately before intersection
- Mediation without temporal ordering (M must precede Y causally)

## Grounding
`report`: method (DE∩correlation vs formal), thresholds (DE padj, correlation r), n mediators, if formal: ACME + ADE + proportion.
