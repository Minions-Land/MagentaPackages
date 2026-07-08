# Reference — Mediation (DE ∩ Correlation vs Formal)

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
from statsmodels.stats.mediation import Mediation
# Y ~ X (total), Y ~ X + M (direct), M ~ X (mediation path)
med = Mediation(outcome_model, mediator_model, exposure="X", mediator="M")
res = med.fit()
# ACME (indirect effect), ADE (direct), proportion mediated
```

## Which to use
- **Identify/nominate mediating species** from DE + correlation: integration heuristic (DE∩correlation)
- **Estimate a causal/indirect effect**: formal mediation (causal pathway)

## Pitfalls
- Mediation approach mismatched to the question (integration heuristic nominates candidates; formal mediation estimates the indirect effect)
- Not testing both DE and correlation separately before intersection
- Mediation without temporal ordering (M must precede Y causally)

## Grounding
`report`: method (DE∩correlation vs formal), thresholds (DE padj, correlation r), n mediators, if formal: ACME + ADE + proportion.
