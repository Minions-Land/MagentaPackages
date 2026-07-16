# Reference — Effect-Size Ranking vs P-Value Ranking

**Maturity: REFERENCE** — a ranking rule, not a computation; applies to any DE table this skill produces.

When a question asks "which proteins change *most*," rank by effect size (magnitude), not by p-value (evidence strength). A subtle but important distinction.

## The two axes are orthogonal

- **P-value** measures **evidence strength** = a function of effect size × sample size × variance. A tiny effect can have a tiny p-value if n is large.
- **Effect size** (log2FC, Cohen's d, |estimate|) measures **biological magnitude** — how big is the change?

A protein with log2FC=3.0, p=0.03 changed **more** than one with log2FC=0.4, p=1e-10. If the question is "which changed most," the first wins despite the weaker p-value.

## The rule

**"Which change most / are most different / largest change"** is a question about **magnitude**, so
rank by |effect size| — and gate on FDR first, so you are ranking among hits the data supports:

```python
credible = de[de.padj < 0.05]
top = credible.reindex(credible.log2FC.abs().sort_values(ascending=False).index).head(10)
```

**"Which are most significant / strongest evidence"** is a question about **evidence**, so rank by
p-value. Same analysis, different axis — read the question.

### When the gate empties the table

An FDR gate returning nothing is a **result**, not a failure: it says the data does not support any
hit at that threshold, and that belongs in the report as a number (`n_sig = 0` of n tested). It is
also common and unremarkable at small n.

What you do next is a judgement about what was asked. If a ranked shortlist is wanted regardless, a
raw-p ranking answers that, provided you show the FDR column beside it and say the set is exploratory.
Silently returning an empty table answers nothing; silently dropping the FDR column overclaims.
Neither extreme is the honest move.

## Why the ranking axis matters

When a question asks which proteins change *most*, rank by effect size (magnitude), not p-value (evidence strength). Ranking by p-value when magnitude was asked is a subtle but consequential error — right analysis, wrong ranking axis. The fix is a one-line change but requires reading the question carefully.

## Effect-size measures

| Measure | When | Formula |
|---------|------|---------|
| **log2FC** | Fold-change (expression, NPX) | log2(mean_case / mean_ctrl), or ΔNPX |
| **Cohen's d** | Standardized mean difference | (mean_A − mean_B) / pooled_SD |
| **\|estimate\|** | Regression coefficient | absolute value of the fitted β |
| **Correlation r** | Association strength | Pearson/Spearman r |

For NPX (already log2), the mean difference IS the log2FC.

## Multi-omic effect-size integration

When ranking candidates across multiple data types, combine effect sizes (e.g., product of absolute effects):

```python
# Join proteomics + transcriptomics + metabolomics on gene/analyte
merged = prot_de.merge(rna_de, on="gene").merge(metab_de, on="gene")

# Rank by product of absolute effect sizes (requires all three credible)
merged = merged[
    (merged.padj_prot < 0.05) &
    (merged.padj_rna < 0.05) &
    (merged.padj_metab < 0.05)
]
# Standardize BEFORE combining. Proteomic log2FC, RNA log2FC and a metabolite effect are on
# different scales with different spreads, so multiplying the raw magnitudes silently lets whichever
# assay happens to have the widest dynamic range dominate the ranking — the "combined" score is then
# mostly one omic wearing a trenchcoat. Rank-transform within each omic first (rank is robust to the
# heavy tails these distributions have; a z-score is the alternative if you prefer magnitudes).
for col in ["log2FC_prot", "log2FC_rna", "effect_metab"]:
    merged[f"r_{col}"] = merged[col].abs().rank(pct=True)      # 0..1 within this omic

merged["combined_effect"] = (
    merged.r_log2FC_prot *
    merged.r_log2FC_rna *
    merged.r_effect_metab
)
top = merged.sort_values("combined_effect", ascending=False).head(10)
```

Document the combination rule (product, sum, min) — each has different semantics. Product rewards consistency across omics; min rewards the weakest-link being strong.

Report the standardization alongside the rule: "product of within-omic percentile ranks" and "product of
raw |log2FC|" produce different top-10s, and only the first is comparable across assays.

## Pitfalls

- **Ranking by p when magnitude asked** — the classic error
- **No FDR gate before effect ranking** — a huge effect with p=0.9 is noise
- **Ranking by -log10(p) thinking it's effect size** — it's still evidence, not magnitude
- **Signed vs absolute** — "most changed" usually means |effect|; "most upregulated" means signed
- **Combining effects on different scales** — standardize (z-score or rank) before combining across omics

## Grounding

`report`: FDR gate applied, ranking axis (effect size vs p-value, matched to the question), top hits with both the effect size and the p-value shown.