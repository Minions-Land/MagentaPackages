# Reference — Mutation × Phenotype Association Testing

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

Testing whether a gene's alteration associates with a clinical phenotype (response, stage, subtype) via Fisher exact + FDR.

## The 2×2 table

For each gene, build a contingency table of alteration status × phenotype:

```
              Phenotype+   Phenotype-
Altered           a            b
Not altered       c            d
```

```python
from scipy.stats import fisher_exact

def gene_phenotype_test(gene, altered, phenotype_pos, alternative="two-sided"):
    """altered: patients × genes bool, already reindexed onto the cohort (recurrence.md).
    phenotype_pos: bool Series on the same cohort index."""
    is_altered = altered[gene].reindex(phenotype_pos.index, fill_value=False)
    a = ( is_altered &  phenotype_pos).sum()
    b = ( is_altered & ~phenotype_pos).sum()
    c = (~is_altered &  phenotype_pos).sum()
    d = (~is_altered & ~phenotype_pos).sum()
    assert a + b + c + d == len(phenotype_pos)        # the table must cover the whole cohort
    odds, p = fisher_exact([[a, b], [c, d]], alternative=alternative)
    return {"gene": gene, "a": a, "b": b, "c": c, "d": d, "odds_ratio": odds, "p": p}
```

> ### Reindex first, or the "Not altered" row silently loses its patients
>
> Without the `.reindex`, `is_altered` carries only the patients present in `altered` — i.e. those
> with ≥1 pathogenic variant *somewhere*. pandas then aligns `is_altered & phenotype_pos` to the union
> and fills `False`, so **`a` and `b` come out right** — but `~is_altered` is evaluated on the
> *unaligned* Series, so `c` and `d` only ever count patients who were already in `altered`. The
> mutation-free patients — who belong squarely in the "Not altered" row — disappear.
>
> Measured on a 120-patient cohort with 40 mutation-free patients: the table sums to **80**, giving
> OR = 0.375, **p = 0.078**. Reindexed, it sums to 120: OR = 0.154, **p = 0.0001**. Here it *hides* a
> real association; with the responders distributed the other way it manufactures one. The `assert` is
> the whole defence — this bug has no symptom other than the table not adding up.

## One-sided vs two-sided

- **Two-sided** (default): "is this gene associated with the phenotype?" (either direction)
- **One-sided** (`alternative="greater"` or `"less"`): "is this gene *enriched* in responders?" or directional **mutual exclusivity**

**Mutual exclusivity** (two genes rarely co-altered) → one-sided `"less"` on co-occurrence, or test depletion of the double-altered cell. When the question is specifically about exclusivity, use the directional test — a two-sided test does not match the one-directional (depletion) hypothesis and dilutes power.

```python
# ESR1 vs MAPK-pathway mutual exclusivity: one-sided
odds, p = fisher_exact([[both, esr1_only], [mapk_only, neither]], alternative="less")
```

## BH-FDR across the gene set

Testing many genes inflates false positives. Apply Benjamini-Hochberg FDR:

```python
from statsmodels.stats.multitest import multipletests

results = pd.DataFrame([gene_phenotype_test(g, altered, pheno) for g in recurrent_genes])
results["padj"] = multipletests(results.p, method="fdr_bh")[1]
significant = results[results.padj < 0.05].sort_values("padj")
```

**FDR family = the set of genes tested.** Restrict to recurrent genes (≥5 patients) BEFORE testing — this shrinks the family and improves power.

## Minimum cell-count gate

Fisher exact is valid for small counts, but a gene altered in 1 patient gives an uninterpretable test. Gate to genes with adequate support:

```python
# Only test genes altered in ≥5 patients
testable = [g for g in genes if altered[g].sum() >= 5]
```

The chi-square test additionally assumes expected cell counts ≥5 — Fisher exact doesn't need this, but the support gate is good practice regardless.

## Clinical variable cleaning

Phenotype variables often need cleaning before testing:

**T-stage collapse**:
```python
clinical["T_stage"] = clinical["ajcc_T"].str.extract(r"(T\d)")   # T2a → T2; non-matches become NaN
clinical = clinical.dropna(subset=["T_stage"])
```

`.str.extract` turns every unparseable value — `TX`, `[Not Available]`, `[Discrepancy]` — into `NaN`,
so `dropna` is what removes them. **`.isin([None, "TX"])` does not**: `isin` never matches `NaN`, so
that filter drops zero rows and the sentinels survive into the test. Same trap on the pathologic/clinical
fallback — `fillna` is a no-op when the missing value is the *string* `"[Not Available]"` rather than
`NaN`. Normalise sentinels to `NaN` first:

```python
clinical = clinical.replace(r"^\[.*\]$", np.nan, regex=True)
clinical["stage"] = clinical["path_T"].fillna(clinical["clin_T"])
```

**Response mapping** (irRECIST → binary):
```python
responder = clinical.irRECIST.isin(["CR", "PR"])
assert responder.any(), f"no responders matched; observed labels: {clinical.irRECIST.unique()}"
clinical["responder"] = responder
```

The `assert` is the point. irRECIST is written both as `CR`/`PR` and as `Complete Response`/`Partial
Response`, and a literal `isin(["CR","PR"])` against the long form returns **zero responders without
raising** — every downstream test then runs on an empty group and reports a clean null. Read the
observed labels before mapping them.

Drop ambiguous values ("Discrepancy", "Indeterminate", NA) explicitly.

## Full example: gene enrichment in responders

```python
# 1. Per-patient alteration (already collapsed)
# 2. Responder phenotype
responder = clinical.set_index("patient").responder
# 3. Test each recurrent gene, one-sided (enrichment in responders)
results = pd.DataFrame([
    gene_phenotype_test(g, altered, responder, alternative="greater")
    for g in recurrent_genes
])
results["padj"] = multipletests(results.p, method="fdr_bh")[1]
# 4. Surface BRCA2
print(results[results.gene == "BRCA2"])
```

## Pitfalls

- **2×2 that doesn't sum to the cohort** — `~is_altered` on an unaligned Series drops the
  mutation-free patients out of the "Not altered" row; reindex, then `assert` the total
- **Wrong sidedness** — exclusivity/enrichment questions need one-sided; using a two-sided test here is a common mistake
- **No FDR** — testing 100 genes at p<0.05 gives ~5 false positives
- **FDR family too large** — testing all genes instead of recurrent ones dilutes power
- **No support gate** — singleton genes give meaningless tests
- **Phenotype not cleaned** — "Discrepancy"/NA rows leak in, substages not collapsed
- **Mutation counts not per-patient** — use the binary altered matrix (see `recurrence.md`)

## Grounding

`report`: genes tested (with family size), test (Fisher, sidedness), **2×2 counts for significant hits
and their total** (it must equal the cohort size), odds ratio, raw p, padj.
