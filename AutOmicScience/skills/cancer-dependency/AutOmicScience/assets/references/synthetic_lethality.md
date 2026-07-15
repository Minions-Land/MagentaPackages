# Reference — Synthetic Lethality Discovery

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

Synthetic lethality (SL): two genes where loss of either alone is tolerated, but loss of both is
lethal. The basis for targeted therapies like PARP inhibitors in BRCA-mutant cancers.

## The concept

- Gene A alone knocked out → cell survives
- Gene B alone knocked out → cell survives
- Both A and B knocked out → cell dies

**Therapeutic exploitation:** if a tumour has lost gene A (mutation/deletion), drugging its SL partner
B selectively kills the tumour while sparing normal cells (which retain A).

**Canonical example:** BRCA1/2-mutant tumours depend on PARP1 (DNA-repair backup). PARP inhibitors
(olaparib) exploit this.

## Detection strategy 1: mutual exclusivity

If A and B are SL partners, tumours rarely lose both (double loss is lethal) → their alterations are
**mutually exclusive**:

```python
from scipy.stats import fisher_exact

def mutual_exclusivity(gene_a, gene_b, altered):
    """altered: samples × genes boolean alteration matrix."""
    a = altered[gene_a].astype(bool)
    b = altered[gene_b].astype(bool)
    table = [[(a & b).sum(), (a & ~b).sum()],
             [(~a & b).sum(), (~a & ~b).sum()]]
    odds, p = fisher_exact(table, alternative="less")   # depletion of the double-altered cell
    return {"pair": (gene_a, gene_b), "both": table[0][0], "odds": odds, "p": p}
```

The table is `[[both, only_a], [only_b, neither]]`, and `alternative="less"` tests odds ratio < 1 —
i.e. *fewer* double-altered samples than independence predicts. Verified: a perfectly exclusive pair
(20 A-only, 20 B-only, 0 both) gives odds = 0, p = 7e-12. A two-sided test dilutes this directional
signal.

Testing all pairs is `n²/2` tests — **FDR-correct** (`multipletests(..., method="fdr_bh")`) and say so.

## Detection strategy 2: dependency conditioned on genotype

Using DepMap: is gene B a stronger dependency in cell lines that have lost gene A? This is the direct
functional test, and the one that discovered WRN as the SL partner of microsatellite instability.

`CRISPRGeneEffect.csv` is **cell lines × genes** with `SYMBOL (EntrezID)` column labels — see
`depmap_loading.md`:

```python
from scipy.stats import mannwhitneyu

def conditional_dependency(col_b, a_mutant_lines, a_wt_lines):
    """col_b is a gene_effect column label, e.g. 'PARP1 (142)'."""
    idx = gene_effect.index
    b_mut = gene_effect.loc[idx.intersection(a_mutant_lines), col_b].dropna()
    b_wt  = gene_effect.loc[idx.intersection(a_wt_lines),     col_b].dropna()
    stat, p = mannwhitneyu(b_mut, b_wt, alternative="less")   # B MORE lethal in A-mutant
    return {"partner": col_b, "delta": b_mut.mean() - b_wt.mean(),
            "n_mut": len(b_mut), "n_wt": len(b_wt), "p": p}
```

Report `n_mut`: an SL test across six A-mutant lines is not evidence, however small the p-value.

## Priors: paralogs

Paralogs (duplicated genes with redundant function) are enriched for SL — losing one is buffered by
the other, so the pair is only lethal together.

```python
# Ensembl BioMart paralog table, or a curated list; filter on sequence identity
paralog_pairs = pd.read_csv("ensembl_paralogs.csv")
paralog_pairs = paralog_pairs[paralog_pairs.identity > 0.3]
```

## Priors: protein–protein interaction (STRING)

```python
import io, requests, pandas as pd

def string_partners(gene, species=9606, min_score=700, limit=1000):
    """High-confidence STRING partners. Pass an explicit limit — the API default is 10."""
    r = requests.get(
        "https://string-db.org/api/tsv/interaction_partners",
        params={"identifiers": gene, "species": species, "required_score": min_score,
                "limit": limit, "caller_identity": "aose"},
        timeout=30,
    )
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), sep="\t").preferredName_B.tolist()
```

> **`limit` defaults to 10 — pass it explicitly.** Omitting it truncates silently: BRCA1 has **373**
> partners at score > 700, and **PARP1 (score 0.974) is not in the default top 10**. A PPI prior built
> from the default call misses the canonical SL pair this entire document is about, and nothing in the
> response says it was truncated. Read the columns by name (`preferredName_B`), not by position — the
> TSV has 13 columns and their order is not part of STRING's contract.

## Canonical SL pairs (curated) — and why the list is short

```python
canonical_sl_pairs = {
    ("BRCA1", "PARP1"), ("BRCA2", "PARP1"),   # DNA repair; PARP inhibitors — clinically validated
    ("SMARCA4", "SMARCA2"),                     # SWI/SNF paralogs
    ("ARID1A", "ARID1B"),                       # SWI/SNF paralogs
    ("MTAP", "PRMT5"),                          # MTAP deletion → PRMT5 dependency
}
```

Use **HGNC approved symbols** — this set is matched against DepMap labels, which are HGNC. An alias
never matches and never errors: `("VHL", "GLUT1")` is a silent no-op, because HGNC's approved symbol
is `SLC2A1`. Same for `HER2`/`ERBB2`, `p53`/`TP53`.

Three pairs that look canonical and are **not** — each fails in a way worth knowing:

- **KRAS–STK33**: the 2009 RNAi finding was **refuted**. Potent selective inhibitors (ML281) showed no
  effect on KRAS-dependent cells at 10 µM (Babij et al. 2011; Luo et al. 2012). It is the textbook
  irreproducible SL claim — keeping it as a prior *upweights* a known false positive.
- **VHL–CDK6**: the real result is that VHL loss is SL with losing **CDK4 *and* CDK6 together** —
  "loss of neither CDK4 nor CDK6 phenocopied the effects of the dual CDK4/6 inhibitors"
  (Nicholson et al. 2019). A single-gene DepMap knockout of CDK6 in VHL-mutant lines *correctly*
  shows nothing. As a pair it is not merely wrong — a pairwise prior cannot express a three-way
  interaction, so the analyst reads a correct negative as a broken pipeline.
- **VHL–SLC2A1**: real, but **chemical** SL (the STF-31 compound blocking GLUT1-mediated glucose
  uptake; Chan et al. 2011), not a genetic knockout interaction. Don't expect it in gene-effect data.

That is the point of the short list: priors are only useful if every entry survives functional
replication. Add to it from DepMap-scale evidence, not from a single paper's abstract.

## Combining evidence

Rank candidates by combining:

1. Mutual-exclusivity p-value (patient tumour data)
2. Conditional-dependency p-value (DepMap functional data)
3. Paralog / PPI prior (mechanistic plausibility)

```python
candidates["is_canonical"] = candidates.pair.apply(
    lambda p: p in canonical_sl_pairs or p[::-1] in canonical_sl_pairs
)
candidates["is_paralog"] = candidates.pair.apply(lambda p: p in paralog_set)
```

Priors reorder candidates; they do not confirm them. STK33 is what a prior looks like when it
outlives its evidence.

## Pitfalls

- **STRING's default `limit=10`** — silently drops most partners; pass `limit` explicitly
- **Positional TSV parsing** — read `preferredName_B` by name; column order is not a contract
- **Aliases in the canonical set** — `GLUT1`/`HER2` never match HGNC labels and never error
- **Transposing gene_effect** — it is lines × genes; see `depmap_loading.md`
- **Two-sided test for exclusivity** — SL predicts depletion; use `alternative="less"`
- **Mutual exclusivity alone** — many exclusive pairs are just different subtypes; confirm functionally
- **No FDR** — all-pairs testing is n²/2 tests
- **Tiny genotype groups** — a p-value over six mutant lines is not evidence; report n
- **Confusing SL with co-dependency** — SL: loss of A makes B essential. Co-dependency: both needed together

## Grounding

`report`: detection method(s), candidate pairs with mutual-exclusivity + conditional-dependency stats,
group sizes, FDR method, prior support (paralog/PPI/canonical), and the STRING `limit` + `required_score`
if a PPI prior was used.

## Sources
- Lord & Ashworth (2017) — PARP inhibitors / BRCA SL
- Chan et al. (2019) *Nature*; Behan et al. (2019) *Nature* — WRN / MSI, the DepMap-scale SL discovery
- Dede et al. (2020) — paralog dependency in cancer
- Babij et al. (2011); Luo et al. (2012) — the KRAS–STK33 refutation
- Nicholson et al. (2019) *Sci Signal* — VHL / CDK4+CDK6 (both required)
- Chan et al. (2011) *Sci Transl Med* — VHL / GLUT1 chemical SL
- STRING: string-db.org/help/api · Ensembl BioMart paralogs: ensembl.org/biomart
