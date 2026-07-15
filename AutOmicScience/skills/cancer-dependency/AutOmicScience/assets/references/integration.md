# Reference — Multi-Omic Integration with Dependency Data

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

Combining DepMap dependency with phosphoproteomics, expression, or mutation data to prioritize targets
with converging evidence.

## Both DepMap matrices are cell lines × genes

`CRISPRGeneEffect.csv` **and** `OmicsExpressionProteinCodingGenesTPMLogp1.csv` are rows = `ModelID`,
columns = `SYMBOL (EntrezID)`. (DepMap's pipeline builds the expression matrix genes-on-index and
transposes it on the way out — `depmapomics/expressions.py`.) Read `depmap_loading.md` before writing
any of this; the joins below are all on that shape.

```python
gene_effect = pd.read_csv("CRISPRGeneEffect.csv", index_col=0)                       # lines × genes
expression  = pd.read_csv("OmicsExpressionProteinCodingGenesTPMLogp1.csv", index_col=0)  # lines × genes
symbol_to_col = {c.split(" (")[0]: c for c in gene_effect.columns}
```

## The integration principle

A target with **converging evidence** across data types is more credible than one supported by a
single assay:

- **Dependency** (DepMap): knockout is lethal → functional requirement
- **Expression/phospho** (upregulated): the pathway is active → biological relevance
- **Mutation**: genotype context → patient stratification

Converging = dependent AND (over-expressed OR activated OR in a mutated pathway).

## Dependency + phosphoproteomics

Genes that are both (a) phospho-activated and (b) a dependency → active-pathway driver candidates:

```python
# Phospho: activating-site upregulated (see proteomics/phosphoproteomics.md) — bare HGNC symbols
phospho_up = set(de_phospho[(de_phospho.padj < 0.05) & (de_phospho.log2FC > 1)].gene)

# Dependency: mean gene-effect over the cancer's lines, per gene
lines = gene_effect.index.intersection(cancer_lines)
mean_effect = gene_effect.loc[lines].mean(axis=0)          # axis=0 → per gene
dep_cols = mean_effect[mean_effect < -0.5].index           # 'SYMBOL (EntrezID)' labels

candidates = phospho_up & {c.split(" (")[0] for c in dep_cols}
```

Strip the Entrez suffix on **one** side before intersecting — a `set` of `'EGFR'` and a set of
`'EGFR (1956)'` intersect to the empty set without raising.

## Dependency + expression

Overexpressed genes that are also dependencies (the oncogene-addiction pattern):

```python
from scipy.stats import spearmanr

def expr_dep_corr(col, cancer_lines):
    """col: a 'SYMBOL (EntrezID)' label. Negative r = higher expression, stronger dependency."""
    lines = (expression.index
             .intersection(gene_effect.index)
             .intersection(cancer_lines))
    expr = expression.loc[lines, col].dropna()
    dep  = gene_effect.loc[lines, col].dropna()
    common = expr.index.intersection(dep.index)            # .intersection(), not &
    r, p = spearmanr(expr[common], dep[common])
    return {"gene": col, "spearman_r": r, "p": p, "n": len(common)}
```

**`.intersection()`, not `&`.** pandas removed the set-operator meaning of `&` on `Index` in 2.0; on
the pinned pandas 2.3 `expr.index & dep.index` raises `TypeError: unsupported operand type(s) for &:
'str' and 'str'`. It is not a subtle bug — the line simply never runs.

Sign: gene-effect is negative-for-lethal, so **negative Spearman** = higher expression tracks with
stronger dependency.

## Dependency + mutations

Mutation status as a dependency modifier (the SL logic — see `synthetic_lethality.md`):

```python
from scipy.stats import mannwhitneyu

mut = pd.read_csv("OmicsSomaticMutations.csv")
# Current columns: HugoSymbol, ModelID, Chrom, Pos, Ref, Alt, VariantInfo, ProteinChange, ...
# (Hugo_Symbol / DepMap_ID are the pre-23Q2 names, and Hugo_Symbol is the MAF-export spelling.)
a_mutant = set(mut.loc[mut.HugoSymbol == "GENE_A", "ModelID"])

lines = gene_effect.index.intersection(cancer_lines)
mut_lines = lines.intersection(a_mutant)
wt_lines  = lines.difference(a_mutant)

col_b = symbol_to_col["GENE_B"]
b_mut = gene_effect.loc[mut_lines, col_b].dropna()
b_wt  = gene_effect.loc[wt_lines,  col_b].dropna()
stat, p = mannwhitneyu(b_mut, b_wt, alternative="less")     # B more lethal in A-mutant
```

`OmicsSomaticMutations.csv` lists **every** variant call, including silent and low-VAF ones. Filter on
`VariantInfo` / `ProteinChange` for the consequence you actually mean before calling a line "mutant" —
otherwise the mutant group is mostly passengers and the test is powered to find nothing.

## Multi-cancer breadth ranking

A target essential across many cancer types has broad therapeutic potential:

```python
breadth = {}
for col in selective_cols:
    n = 0
    for cancer, lines in cancer_type_lines.items():
        idx = gene_effect.index.intersection(lines)
        if len(idx) and (gene_effect.loc[idx, col] < -0.5).mean() > 0.5:
            n += 1
    breadth[col] = n
breadth_ranked = pd.Series(breadth).sort_values(ascending=False)
```

The `len(idx)` guard matters: an empty intersection makes `.mean()` return `nan`, `nan > 0.5` is
`False`, and the lineage silently drops out of the count instead of erroring.

## Combining rule semantics

| Rule | Meaning | Use when |
|------|---------|----------|
| **Intersection (AND)** | Supported by all data types | High-confidence, conservative |
| **Union (OR)** | Supported by any | Discovery, sensitive |
| **Weighted score** | Rank by combined evidence | Prioritization with tradeoffs |

State which rule you used and why.

## Pitfalls

- **Transposed indexing** — both matrices are lines × genes; `mean(axis=0)` is per gene
- **`&` on a pandas Index** — raises on pandas ≥2; use `.intersection()`
- **Mixing suffixed and bare symbols** — `{'EGFR'} & {'EGFR (1956)'}` is empty, silently
- **Legacy column names** — `Hugo_Symbol`/`DepMap_ID` are pre-23Q2 (`HugoSymbol` for the MAF export)
- **Unfiltered mutation calls** — silent/passenger variants dilute the "mutant" group
- **Union when intersection intended** — "converging evidence" means AND
- **Comparing across scales without normalisation** — dependency (−2..0.5), TPM, phospho log2 ratio
- **Correlation sign confusion** — negative Spearman = stronger dependency with higher expression
- **Cell line vs patient mismatch** — DepMap is cell lines; don't equate to patient frequencies
- **Ignoring lineage** — a pan-cancer dependency may be one dominant lineage

## Grounding

`report`: DepMap release, data types integrated, combination rule (AND/OR/weighted), n lines in each
join (post-intersection), mutation filter applied, converging candidates with per-data-type evidence,
breadth if computed.
