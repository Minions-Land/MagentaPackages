# Functional Analysis — Pathway/TF Activity, Gene-set Enrichment, Perturbation

**Maturity: mixed.** Pathway/TF activity and gene-set enrichment are **READY** — they run through tested `omics_compute` subcommands (`pathway_activity`, `enrichment`) in the pinned `task1` env; call the tool. **ORA on the output of a pseudobulk DE run is REFERENCE** — the subcommand's universe is the wrong denominator for that input, so hand-roll the hypergeometric (§2b; `scipy` only, no install). **Perturbation / condition-response DE is REFERENCE** — there is no subcommand; hand-roll it in a Python script (§3).

## Goal / When to Use

Move from genes to **function**: regulatory/pathway activity per cell, gene-set enrichment of a gene list, or differential response to a perturbation/condition. Use when you want mechanistic interpretation beyond individual marker genes.

## Decision Criteria (which path)

- **Per-cell pathway / TF activity** to overlay on UMAP or compare across clusters → `pathway_activity` (READY).
- **Is gene-set X over-represented in a fixed gene list** (e.g. a cluster's specific markers)? → `enrichment` (ORA, READY). If the list came out of a **pseudobulk DE run**, the correct universe changes — §2b.
- **What changes between a treated/condition group and its control?** → §3 routes it. Don't reach for per-gene DE reflexively: "which genes" belongs to `markers_de.md`, "which cell types / which cells were really perturbed / how far they moved" needs `pertpy` (§3), and "did composition shift" belongs to `composition.md`.

Background rule for enrichment: ORA tests your query set against the resource's gene universe, so pass a *focused, biologically meaningful* list (a cluster's specific markers) — never a random HVG dump, which inflates apparent significance. That universe is the right denominator for a cluster's markers and the **wrong** one after a DE run — see §2b.

## 1. Pathway / TF activity (READY) — `pathway_activity`

```
omics_compute(
  subcommand="pathway_activity",
  modality="scrna",
  args={"adata": "processed.h5ad", "output": "pathway.h5ad",
        "method": "mlm", "resource": "progeny", "organism": "human"}
)
```

**Why these defaults:** `resource="progeny"` is a compact, well-curated set of ~14 signaling pathways with signed gene weights — ideal for per-cell activity and easy to read on a UMAP. `method="mlm"` (multivariate linear model) fits all pathways jointly, accounting for shared genes — the decoupler-recommended default for weighted networks. For **TF** activity switch `resource="collectri"` (CollecTRI regulons); for broad programs use `resource="msigdb"` (Hallmark). On very large datasets `method="ulm"` (univariate) is lighter. Optional flags: `layer`, `use-raw` (bare store-true), `min-size` (default 5).

**Output:** per-cell scores in `adata.obsm["pathway_<method>"]` and metadata in `uns["pathway_analysis"]` within `pathway.h5ad`; the returned `report` lists `n_pathways`, `n_cells`, and per-pathway mean/std (evidence recorded automatically). Read scores back for plotting:

```python
import scanpy as sc, pandas as pd
a = sc.read_h5ad("pathway.h5ad")
acts = pd.DataFrame(a.obsm["pathway_mlm"], index=a.obs_names,
                    columns=a.uns["pathway_analysis"]["pathway_names"])
acts["leiden"] = a.obs["leiden"].values
print(acts.groupby("leiden").mean())     # per-cluster mean activity
```

## 2. Gene-set enrichment (READY) — `enrichment`

```
omics_compute(
  subcommand="enrichment",
  modality="scrna",
  args={"gene-list": "CD3D,CD3E,IL7R,CCR7,GZMK,CD8A",
        "output": "enrichment.json",
        "method": "ora", "resource": "msigdb", "organism": "human"}
)
```

**Why these defaults:** `method="ora"` (over-representation / Fisher test) is the correct test for an *unranked* gene list — e.g. the top specific markers of one cluster. `resource="msigdb"` (Hallmark sets) gives broad, well-annotated biological programs; switch to `progeny`/`collectri` for pathway/TF sets. Build the gene list from the marker CSV's `names` column: sort by `scores`, filter on `specificity` and `logfoldchanges > 0.5`, take ~20–100 genes. Optional flags: `padj-threshold` (default 0.05), `top-n` (default 50).

> `method="gsea"` is **not** available here — GSEA needs a *ranked* gene list with scores, which this subcommand does not accept (it errors). For ranked enrichment, build a pseudobulk DE ranking and run GSEA in a Python script (REFERENCE), or use `pathway_activity` with `method="gsea"` on expression.

**Output:** a JSON file with `top_pathways` (sorted by adjusted p-value), `n_significant_pathways`, and the full result table; the returned `report` summarizes the top hits (evidence recorded automatically).

## 2b. ORA after pseudobulk DE (REFERENCE) — the universe matters

§2 tests your list against **the resource's** gene universe. That is the right denominator for a
cluster's markers, and the wrong one for the output of a pseudobulk DE run (`markers_de.md` Part B):
genes that failed the expression filter were **never tested**, so they could not have come out DE, and
leaving them in the background inflates every enrichment. When the input is "the upregulated genes
from DESeq2", hand-roll the hypergeometric with the **tested genes** as the universe:

```python
from scipy.stats import hypergeom       # scipy ships with scanpy — nothing to install

universe  = set(de_results.index)                        # every gene DESeq2 returned a result for
signature = set(my_signature) & universe                 # restrict the set to the universe
de_genes  = set(de_results[(de_results.padj < 0.05) &
                           (de_results.log2FoldChange > 0.5)].index)
overlap   = de_genes & signature

N, K, n, k = len(universe), len(signature), len(de_genes), len(overlap)
p    = hypergeom.sf(k - 1, N, K, n)      # P(X >= k), one-sided: enrichment
fold = (k / n) / (K / N)                 # observed vs expected overlap fraction
print({"N": N, "K": K, "n": n, "k": k, "fold_enrichment": fold, "p": p})
```

**N is the tested genes, not the genome.** If DESeq2's independent filtering left 12,000 results,
N = 12,000 — not ~20,000. Read it off `len(de_results)`; never type a round number.

**Split up and down.** Pooled, a set that is genuinely up-enriched gets diluted by the down half. Run
the block twice (`log2FoldChange > 0.5`, then `< -0.5`) and report the direction next to the p-value.

**Correct across signatures.** Testing 50 signatures means BH-FDR over those 50 p-values, not 50 raw
ones.

The same restriction applies to the signature itself: intersect it with the universe *before* counting
`K`, and make sure both sides use the same namespace — a symbol-vs-Ensembl mismatch silently drops the
overlap to zero (Failure Mode 2).

## 3. Perturbation / condition response (REFERENCE) — hand-rolled

No subcommand — write a Python script. **First decide what the question actually is.** "Perturbation
analysis" is several distinct questions, and only one of them is per-gene DE:

| Question | Where |
|---|---|
| Which **genes** respond between conditions? | **`markers_de.md` Part B** — pseudobulk + PyDESeq2, already in the pinned env. Not repeated here. |
| Did cell-type **composition** shift? | **`composition.md`** — scCODA / Milo. |
| Which **cell types** respond most? | §3a below — `pt.tl.Augur` |
| CRISPR screen: which cells were **actually perturbed**? | §3b below — `pt.tl.Mixscape` |
| **How far** did the perturbation move cells overall? | §3c below — `pt.tl.Distance` |

The three below are what `pertpy` uniquely adds: they answer questions per-gene DE *cannot*.
For the genes question, use `markers_de.md` — it needs no install and states the correct stance
(never run a per-cell test across conditions; cells from one donor are not replicates).

`pertpy` is **not** in the pinned env (confirmed against `pixi.toml`/`pixi.lock` — a stale copy may linger
in an un-rebuilt `.pixi/envs/task1`, so trust the lock, not a previous session's env). Provision it per
`omics-shared`'s `assets/references/AOSE_nonStandard_env.md` (§A, own `solve-group`); the `pertpy` spec
covers all three below. Never a bare `pip install`. Tools live in `pt.tl`; **plots are methods on the tool object** (`ag.plot_lollipop(...)`,
`ms.plot_barplot(...)`), not in `pt.pl` — that namespace is empty in 1.1.1. (`pertpy[de]` /
`pertpy[milo-edger]` exist for its DE and Milo backends, but §3 needs neither.)

**(a) Which cell types respond — Augur.** Prioritizes cell types by how separable
perturbed/control cells are (a classifier's cross-validated AUC), which per-gene DE cannot rank:

```python
import pertpy as pt
ag = pt.tl.Augur("random_forest_classifier")
loaded = ag.load(adata, label_col="condition", cell_type_col="cell_type")
v_adata, v_results = ag.predict(loaded, subsample_size=20, n_threads=4, random_state=0)
v_results["summary_metrics"]      # mean AUC per cell type; ~0.5 = indistinguishable
```

**(b) CRISPR screen — Mixscape.** Not every cell carrying a guide is perturbed (escapers); scoring
them together dilutes the effect. Mixscape first removes confounding variation, then classifies
each cell KO vs non-perturbed:

```python
ms = pt.tl.Mixscape()
ms.perturbation_signature(adata, pert_key="perturbation", control="NT", split_by="replicate")
ms.mixscape(adata, pert_key="gene_target", control="NT", layer="X_pert")
adata.obs["mixscape_class_global"]    # KO / NP / NT — filter to KO before downstream DE
```

`perturbation_signature` writes `layer="X_pert"`, which `mixscape` then consumes — run them in that
order. `split_by` should name the replicate column so signatures are computed within replicate
(default `ref_selection_mode="nn"` instead matches each cell to its nearest control cells).

**(c) Effect size — Distance.** E-distance summarizes how far a perturbation moved cells, with a
permutation test for significance:

```python
d = pt.tl.Distance(metric="edistance", obsm_key="X_pca")
pairwise = d.pairwise(adata, groupby="perturbation")
tab = pt.tl.DistanceTest("edistance", n_perms=1000)(adata, groupby="perturbation", contrast="control")
```

> **None of these three is a substitute for per-gene DE.** Augur ranks cell types, Mixscape
> classifies cells, Distance summarizes displacement — if the question is "which genes changed",
> go to `markers_de.md`.

## Failure Modes

1. **ORA on a noisy/huge gene list.** *Symptom:* hundreds of "significant" pathways, none specific. *Diagnosis:* the gene list was HVGs or a whole cluster's unfiltered genes, so everything overlaps something. *Fix:* pass only the top specific markers (high `specificity`, `logfoldchanges > 0.5`) — typically 20–100 genes — from `marker_table`.

2. **Wrong organism / symbol mismatch.** *Symptom:* near-zero pathways pass `min-size`, or activity scores are all ≈0. *Diagnosis:* `organism` doesn't match the gene symbols (mouse `Cd3d` vs human `CD3D`), so few genes map into the network. *Fix:* set `organism="mouse"` for mouse symbols; confirm `var_names` are gene symbols, not Ensembl IDs.


3. **Perturbation column/control level typo.** *Symptom:* `rank_genes_groups` errors on the reference level, the subset is empty, or Mixscape/Sccoda find no control cells. *Diagnosis:* the condition column or its control level doesn't match `obs` exactly (case/whitespace) — each tool names it differently (`reference=`, `baseline=`, `control=`). *Fix:* print `adata.obs[col].value_counts()` and copy the exact level string.

4. **Whole-genome universe after DE.** *Symptom:* nearly every signature enriches, fold-enrichments all >2, p-values absurdly small. *Diagnosis:* N was set to the genome (~20,000) instead of the genes DESeq2 actually tested — the untested genes could never have been DE, so they don't belong in the draw. *Fix:* `N = len(de_results)`; see §2b. (The READY path in §2 does not have this problem: it uses the resource's universe, which is the right denominator for a marker list.)


## Figure checkpoints

- **Pathway/TF activity UMAP or per-cluster heatmap** — do high-activity pathways match known biology (e.g. JAK-STAT high in activated immune cells)?
- **Enrichment bar plot (top sets by adjusted p)** — are the top sets plausible for the input gene list, or generic ("metabolism" everywhere = non-specific input)?
- **Perturbation volcano / top-gene dotplot** — are the top responders biologically coherent for the perturbation?
- **Augur AUC per cell type** — is any cell type near 0.5 (indistinguishable)? A ranking where everything scores high usually means label leakage or unequal cell counts.
- **Mixscape KO/NP posterior split** — do NT (control) cells land in NP as expected? NT classified KO means the signature failed.

Observe each before it backs a claim.

## Grounding

Record from each subcommand's `report` (captured automatically for the READY paths — cite them):

- **pathway_activity:** `method`, `resource`, `organism`, `n_pathways`, `n_cells`, per-pathway mean activity (top few).
- **enrichment:** `method`, `resource`, `n_input_genes`, `n_significant_pathways`, top pathway names + adjusted p-values.
- **§2b hand-rolled ORA:** nothing is captured for you — print `N` *and how it was defined* ("genes with a DESeq2 result"), `K`, `n`, `k`, fold-enrichment, the one-sided p, the direction (up/down), and the FDR method if several signatures were tested.

Always record the **resource and its version** (PROGENy / CollecTRI / MSigDB evolve — "STAT3 is active" depends on the network version).

For the REFERENCE perturbation path (§3) nothing is captured for you — record it in the script's output:

- **Always:** the `pertpy` version installed, the tool used, the condition column and its exact control/baseline level, and the cell counts per level.
- **Unit of replication** — cells or pseudobulk replicates, and how many biological replicates per condition. This determines whether the p-values mean anything.
- **Per tool:** (a) mean AUC per cell type; (b) the KO/NP/NT counts you filtered on; (c) the metric and `n_perms`.

## Honesty

- **Report the resource + version.** TF/pathway claims implicitly depend on the PROGENy/CollecTRI/MSigDB version.
- **Pathway activity is an aggregate proxy** for coordinated gene expression, not a flux measurement — don't over-read small shifts.
- **Augur ranks separability, not effect size.** A high AUC means perturbed/control cells are distinguishable, not that the biology is large or that specific genes changed.
- **Enrichment reflects your input set.** A generic gene list yields generic hits; state how the list was built (which cluster, which filters).
- **State the universe.** An ORA p-value is a statement about a specific background. "Enriched (p=1e-6)" is uninterpretable without saying whether the denominator was the resource's universe (§2) or the tested genes (§2b) — and the same overlap can be significant under one and not the other.
