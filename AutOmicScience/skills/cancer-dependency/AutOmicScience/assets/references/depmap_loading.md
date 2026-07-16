# Reference — DepMap Data Loading & Context

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

DepMap (Dependency Map) is a genome-wide CRISPR knockout screen across ~1,100 cancer cell lines. This
doc pins down the two things every downstream script depends on: **the matrix orientation** and **the
current file/column names**.

## The stock release is cell lines × genes

`CRISPRGeneEffect.csv` has **one row per cell line and one column per gene** — not the other way
round. Verified against the released file (26Q1 / 24Q4):

```
,A1BG (1),A1CF (29974),A2M (2),A2ML1 (144568),...      <- 18,531 gene columns
ACH-000001,-0.0363...,0.2986...,0.1898...,...          <- one row per model
```

```python
import pandas as pd
gene_effect = pd.read_csv("CRISPRGeneEffect.csv", index_col=0)
# index = ModelID (ACH-######) ; columns = "SYMBOL (EntrezID)" ; values ≈ −2 .. +0.5
```

Everything follows from this:

| You want | Correct | Wrong (transposed) |
|---|---|---|
| One gene across lines | `gene_effect[gene]` | `gene_effect.loc[gene]` |
| A gene in chosen lines | `gene_effect.loc[lines, gene]` | `gene_effect.loc[gene, lines]` |
| Subset to a lineage | `gene_effect.loc[lines]` | `gene_effect[lines]` |
| Fraction of **lines** dependent, per gene | `(gene_effect < -0.5).mean(axis=0)` | `.mean(axis=1)` |

`.mean(axis=1)` on the real file averages **each cell line over all 18k genes** — it returns one
number per line, indexed by `ACH-######`, and every downstream `[gene]` lookup then raises `KeyError`.
That is the good case; a transposed `.loc` that happens to hit a valid label fails silently instead.

**This holds for the stock release, not for every file called a DepMap score matrix.** Anything
re-exported — a subset, a paper's supplement, a model's output — may be transposed, and two such files
can disagree with each other. The first column settles it in one look: `ACH-######` means rows are
models, a gene symbol means they are not. Look, rather than assume.

## Gene columns carry an Entrez suffix

Every column of the stock release is `SYMBOL (EntrezID)`: `A1BG (1)`, `A1CF (29974)` — built that way
by DepMap's pipeline, falling back to `SYMBOL (Unknown)` when no Entrez ID maps
([`depmap_omics/depmapomics/dm_omics.py`](https://github.com/broadinstitute/depmap_omics)). So a bare
`gene_effect["EGFR"]` raises `KeyError`.

```python
symbol_to_col = {c.split(" (")[0]: c for c in gene_effect.columns}
egfr = gene_effect[symbol_to_col["EGFR"]]
```

**A file that went through R arrives mangled.** `make.names` rewrites `A1BG (1)` to `A1BG..1.`, so the
`split(" (")` above yields the whole string back and the lookup `KeyError`s. Match on the label shape
you actually see rather than on the one the release documents.

Strip the suffix only if you have a reason to; the Entrez ID is what disambiguates symbols that HGNC
has since merged or retired. Never strip it off `.index` — the index is cell lines.

## Current file names (and the legacy ones they replaced)

DepMap renamed most files across 22Q2–23Q2. Code written against the old names fails on any modern
release:

| Current file | Holds | Legacy name (≤22Q4) |
|---|---|---|
| `CRISPRGeneEffect.csv` | Chronos gene-effect, lines × genes | `CRISPR_gene_effect.csv` |
| `CRISPRGeneDependency.csv` | Dependency probability 0–1, lines × genes | `CRISPR_gene_dependency.csv` |
| `Model.csv` | Cell-line metadata | `sample_info.csv` |
| `OmicsSomaticMutations.csv` | Somatic mutations | `CCLE_mutations.csv` |
| `OmicsExpressionProteinCodingGenesTPMLogp1.csv` | RNA log2(TPM+1) | `CCLE_expression.csv` |

Column renames that bite just as hard — `DepMap_ID` became `ModelID` **at 23Q2**
(`depmap_omics/depmapomics/qc/test_compare_to_ref_release.py` still carries the
`# 23Q2 only: rename DepMap_ID -> ModelID` shim):

| Current column | Legacy |
|---|---|
| `ModelID` | `DepMap_ID` |
| `OncotreeLineage` | `lineage` |
| `OncotreePrimaryDisease` | `primary_disease` |
| `HugoSymbol` (in `OmicsSomaticMutations.csv`) | `Hugo_Symbol` |

`Hugo_Symbol` (with the underscore) is **not** wrong everywhere — it is the column name in DepMap's
MAF-format export, consumed by tools like maftools. The released `OmicsSomaticMutations.csv` uses
`HugoSymbol` (`depmapomics/constants.py`: `HUGO_COL = "HugoSymbol"`).

Always state the release you used (`26Q1`, `24Q4`, …) in the `report`; file and column names are
release-scoped, not stable.

## Cell-line metadata

```python
model = pd.read_csv("Model.csv", index_col="ModelID")
# Key columns: OncotreeLineage, OncotreePrimaryDisease, OncotreeSubtype, SampleCollectionSite
breast_lines = model.index[model.OncotreeLineage == "Breast"]
breast_effect = gene_effect.loc[gene_effect.index.intersection(breast_lines)]
```

Intersect rather than index directly: `Model.csv` lists models that have *any* data type, and only a
subset were CRISPR-screened, so `gene_effect.loc[breast_lines]` raises `KeyError` on the ones without
a screen.

`OncotreeLineage` is the tissue of origin; `OncotreePrimaryDisease` is finer (e.g. "Lung
Adenocarcinoma" vs "Lung Squamous Cell Carcinoma"). Note that lineage lives in the Oncotree columns —
tissue words also appear in `SampleCollectionSite`, which is the collection site, not the lineage.

## Getting the data: the portal blocks scripts

`https://depmap.org/portal/...` sits behind a browser verification challenge that answers **HTTP 200
with an HTML challenge page**. A `requests.get(...)` + `if r.ok` check passes, then `read_csv` chokes
on HTML — or worse, an "offline fallback" reports it as a network flake. It is not a flake; the
portal is gated.

Use the figshare release instead, which serves the same files unauthenticated and supports range
requests (handy: the header alone tells you the orientation without a 400 MB download):

```python
# DepMap 24Q4 Public = figshare article 27993248; list files via the figshare API:
#   https://api.figshare.com/v2/articles/27993248/files
# then GET the download_url. Record the article id + release in the report.
```

## Use DepMap's own essentiality calls

DepMap ships its common-essential and non-essential gene lists — do not re-derive them with a
hand-rolled frequency threshold (see `dependency_analysis.md`):

| File | Content | Column |
|---|---|---|
| `CRISPRInferredCommonEssentials.csv` | ~1,537 genes inferred common-essential in this release | `Essentials` |
| `AchillesCommonEssentialControls.csv` | ~1,247 curated common-essential controls | `Gene` |
| `AchillesNonessentialControls.csv` | ~781 curated non-essential controls | `Gene` |

All three use the same `SYMBOL (EntrezID)` labels as the gene-effect columns, so they join directly:

```python
common_essential = set(pd.read_csv("CRISPRInferredCommonEssentials.csv").Essentials)
selective_candidates = [c for c in gene_effect.columns if c not in common_essential]
```

## Chronos vs CERES

- **Chronos** (current, 21Q2+): corrects copy-number and screen-quality confounds
- **CERES** (legacy): older algorithm; amplified regions look falsely essential

Prefer Chronos (`CRISPRGeneEffect.csv`).

## Sign convention

- **Negative = lethal** (knockout reduces fitness); −1.0 ≈ the median common-essential gene
- **0 = no effect**; **positive = knockout enhances growth** (rare)

The −1.0 anchor is by construction: Chronos scales scores so common essentials centre near −1 and
non-essentials near 0. That is why the control lists above are the right reference point.

## Pitfalls

- **Assuming genes × cell lines** — the file is lines × genes; a transposed `.loc` either `KeyError`s
  or silently reads the wrong axis
- **Bare gene symbols** — columns are `SYMBOL (EntrezID)`; build a symbol→column map
- **Legacy names** — `CRISPR_gene_effect.csv` / `sample_info.csv` / `DepMap_ID` are pre-23Q2
- **Scripting depmap.org** — challenge-gated, returns HTTP 200 + HTML; use figshare
- **Indexing `gene_effect` with all of `Model.csv`** — not every model was CRISPR-screened; intersect
- **Sign confusion** — negative = lethal, positive = growth advantage

## Grounding

`report`: DepMap release (e.g. 24Q4) and where it came from (figshare article id), n_models, n_genes,
lineage distribution, any subsetting applied.
