# Gene Imputation for Targeted Panels

**Maturity: PARTIAL** — gene imputation via **Tangram** (`project_genes`), hand-rolled in Python. Tangram is **not** in `task2`: provision it into its own env per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` (§A, isolated `solve-group` — it pulls in **torch**, which is exactly why it must not go into `task2`). **The distribution name is `tangram-sc`**, not `tangram` — the latter is an unrelated package on PyPI; get this wrong in a spec and you install something else entirely. CPU is fine for cluster-mode maps; single-cell-mode mapping over a large reference wants a GPU (§B conda if the CUDA stack needs pinning). Imaging panels only. API below verified against `broadinstitute/Tangram` rev `4c68995`.

## Goal / When to Use

Predict expression of genes **not in a targeted imaging panel** at spatial locations, from a whole-transcriptome scRNA reference. Use **only for imaging platforms** (Xenium, MERFISH, CosMx) where the panel is limited. Do not use it for whole-transcriptome spatial (Visium, Slide-seq, Stereo-seq) — there is nothing to impute.

## Decision Criteria

- **Imputation engine — Tangram `project_genes`.** Tangram fits a cell→voxel mapping by gradient descent (Adam) on a **cosine-similarity** objective over the shared genes, then projects every reference gene through that map. It is **not** an optimal-transport method: there is no transport plan and no Sinkhorn step anywhere in the package. If you specifically want OT, that is a different family (novoSpaRc / SpaOTsc) and this doc does not cover it.

- **Reuse the map from `mapping_deconv.md`** instead of re-mapping — but the `mode` / `cluster_label` used there **must be mirrored** in `project_genes`. They are not independent knobs; see below.

- **Decide by:** shared-gene adequacy (panel ∩ reference), whether a map already exists, and compute budget.

## Method Menu

- **`tg.pp_adatas(adata_sc, adata_sp, genes=...)`** — mandatory preprocessing; also defines the training / held-out split
- **`tg.map_cells_to_space(...)`** — fit the map (parameters in `mapping_deconv.md`)
- **`tg.project_genes(adata_map, adata_sc, cluster_label=...)`** — project reference genes onto space
- **`tg.compare_spatial_geneexp(adata_ge, adata_sp, adata_sc)`** — the validation table (`score` + `is_training`)
- **`tg.cross_val(..., cv_mode="loo")`** — leave-one-gene-out, for panels too small to split

## How-to

### The held-out split is made in `pp_adatas` — this is what makes validation mean anything

`pp_adatas` sets `training_genes = genes ∩ panel ∩ reference` and stores it in `uns`. Call it **without** `genes=` and every panel gene becomes a training gene — there is then nothing left to validate on, and scoring the panel reports **training-set fit**, not accuracy. That number always looks good and means nothing.

```python
import tangram as tg
import numpy as np

# `genes=` defines the TRAINING set. Everything else in the panel becomes the test set.
panel = list(adata_sp.var_names)
rng = np.random.default_rng(0)                       # seed it — the split must be reproducible
train_genes = list(rng.choice(panel, size=len(panel) // 2, replace=False))

tg.pp_adatas(adata_sc, adata_sp, genes=train_genes)  # REQUIRED before mapping
```

Two side effects to know about: `pp_adatas` mutates **both** objects in place, and it **lowercases every `var_name`** (`gene_to_lowercase=True` by default). After this call your genes are `cd3d`, not `CD3D` — index in lowercase everywhere downstream, or pass `gene_to_lowercase=False` and handle case yourself.

Skipping the call is not an option: `map_cells_to_space` raises `ValueError: Missing tangram parameters. Run 'pp_adatas()'.`

### Map, then project — `cluster_label` must mirror the mapping

```python
adata_map = tg.map_cells_to_space(
    adata_sc, adata_sp,
    mode="clusters", cluster_label="cell_type",     # cluster mode: fast, CPU-friendly
    device="cpu", num_epochs=1000,
)

adata_ge = tg.project_genes(adata_map, adata_sc, cluster_label="cell_type")   # SAME cluster_label
```

**`cluster_label` does not mean "genes, not clusters".** `project_genes` always projects genes; the argument tells it how `adata_map`'s rows are indexed. Map in `mode="clusters"` and then project with `cluster_label=None` and you get `ValueError: The two AnnDatas need to have same 'obs' index.` — the map's rows are clusters while the reference's rows are cells. Mirror the argument, or the call fails.

`adata_ge.X` is **dense** — `project_genes` densifies internally, so `.toarray()` on it raises `AttributeError`. It also writes `adata_ge.var["is_training"]` for you, which is the whole point of the next step.

### Validate on the held-out genes

```python
df = tg.compare_spatial_geneexp(adata_ge, adata_sp, adata_sc)
# columns: score, is_training, sparsity_sp, sparsity_sc, sparsity_diff

train = df[df["is_training"]]
test  = df[~df["is_training"]]
```

**`score` is cosine similarity, not Pearson r.** Do not carry over r-thresholds from other tools.

**Read the train/test gap, not an absolute cutoff.** The reference distribution is the *training* score on your own data: if `test["score"].median()` is close to `train["score"].median()`, the map generalizes to genes it never saw, and the imputed values are usable. If test sits well below train, the map fit the training genes and did not learn transferable structure — report that and do not build claims on the imputed genes. A self-calibrating comparison beats a magic number invented in a doc, because the achievable score depends on panel size, sparsity, and tissue.

**When the panel is too small to split** — holding out half of a 100-gene panel starves the map — use leave-one-out instead:

```python
cv = tg.cross_val(adata_sc, adata_sp, cluster_label="cell_type", mode="clusters",
                  cv_mode="loo", device="cpu", verbose=False)
```

## Pitfalls & Quality Checks

- **Scoring the panel without holding anything out** — *symptom:* uniformly high correlations that never fail. *Diagnosis:* `pp_adatas` was called without `genes=`, so every scored gene is a training gene. *Fix:* split with `genes=`, then score only `is_training == False` rows — or use `cross_val`.

- **`cluster_label` not mirrored** — *symptom:* `ValueError: The two AnnDatas need to have same 'obs' index.` *Diagnosis:* mapping mode and projection mode disagree. *Fix:* pass the same `cluster_label` to both calls.

- **Uppercase gene lookups after `pp_adatas`** — *symptom:* `KeyError: 'CD3D'`. *Diagnosis:* `pp_adatas` lowercased the var index in place. *Fix:* use `cd3d`, or `gene_to_lowercase=False`.

- **Indexing `adata_ge` by the full panel** — *symptom:* `KeyError`. *Diagnosis:* `adata_ge.var` carries the **reference's** genes (after `filter_genes(min_cells=1)`), so panel genes absent from the reference are not in it. *Fix:* index `adata_ge.uns["overlap_genes"]`, or let `compare_spatial_geneexp` handle the intersection.

- **Imputed genes are predictions, not measurements** — the dominant pitfall is treating them as data. Never present an imputed gene as measured, in any figure legend, table, or claim.

- **A small shared-gene set makes imputation unreliable** — if panel ∩ reference is under ~100 genes, or the shared genes are all housekeeping, the map has little biological signal to learn from. Report the count; abstain rather than impute on nothing.

## Figure checkpoints

- **`tg.plot_auc(df)`** — the score-vs-sparsity curve over the validation table. A curve that collapses for sparse genes means the imputation is only reliable for abundant ones; say which.
- **Imputed gene vs. a measured marker of the same population** — overlay imputed FOXP3 against measured CD3D. If they do not co-localize, the imputation is wrong regardless of the score.

Observe each before it backs a claim.

## Grounding

Build the `report` from the returned objects, then `print(report)`:

```python
report = {
    "method": "tangram_project_genes",
    "mode": "clusters",
    "cluster_label": "cell_type",
    "device": "cpu",
    "num_epochs": 1000,
    "split_seed": 0,
    "n_train_genes": int(len(train)),
    "n_test_genes": int(len(test)),
    "median_score_train": float(train["score"].median()),   # cosine similarity
    "median_score_test": float(test["score"].median()),     # the number that matters
    "n_imputed_genes": int(adata_ge.n_vars),
    "imputed_genes_used": ["foxp3", "il2ra"],               # genes actually cited in claims
}
```

Record the **train/test split and its seed**, both medians, and the metric's name. A validation score without the split that produced it is not evidence.

## Honesty

- **Label imputed genes as imputed** everywhere. Not "FOXP3 is expressed in region X", but "imputed FOXP3 (held-out cosine 0.6 vs 0.65 on training genes) suggests expression in region X".
- **The train/test gap is the claim's warrant.** Report both numbers together — a test score alone cannot be judged, since the achievable ceiling depends on the panel and tissue.
- **Imputation is extrapolation.** It cannot recover genes the reference does not express, or spatial patterns the shared genes do not carry. A reference from another tissue or condition yields imputed values that reflect the reference's biology, not this tissue's.
- **Report when imputation is skipped.** Too few shared genes, or a test score far below train — say so and proceed without imputed genes rather than shipping unreliable predictions.
