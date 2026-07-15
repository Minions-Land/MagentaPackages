# Reference — scvi-tools / scArches Workflow (scVI · scANVI · MultiVI · reference mapping)

**Maturity: mixed.** **scVI / scANVI / MultiVI / totalVI are REFERENCE** — `scvi-tools` is pinned in
`task1–4` (`scvi-tools = ">=1.1"`, resolved to **1.4.3**); you hand-write the calls. **scArches and
scib are PARTIAL** — neither is in any pinned env; provision them per `omics-shared`'s
`assets/references/AOSE_nonStandard_env.md` (§A, own solve-group, composing `["core","singlecell",…]`)
before the blocks that use them. Never a bare `pip install`. `omics_preflight` covers only `task1–4`,
so check the imports yourself and record the env + versions in the `report`.

All signatures below were verified against **scvi-tools 1.4.3** by live introspection, and against
scArches / scib upstream source.

## 1. Prepare the data

Models consume **raw counts**. Normalising first destroys the count likelihood they are built on.

```python
import scanpy as sc
adata = sc.read_h5ad("data.h5ad")

if "counts" not in adata.layers:
    adata.layers["counts"] = adata.X.copy()      # capture counts BEFORE any normalisation

# Normalise/log for visualisation only — the model reads layer="counts", not .X
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
```

Also needed: a batch/condition column (`adata.obs["batch"]`), and for scANVI/scPoli a label column
(`adata.obs["cell_type"]`).

## 2. scVI — integration / denoising / latent representation

```python
import scvi
scvi.model.SCVI.setup_anndata(adata, layer="counts", batch_key="batch")
model = scvi.model.SCVI(adata, n_latent=30, gene_likelihood="nb")
model.train(max_epochs=400)
adata.obsm["X_scvi"] = model.get_latent_representation()
```

- `n_latent=30` is **this doc's** choice, workable to ~100k cells; raise to ~50 beyond that.
  **scvi-tools' own default is 10** — say which you used.
- `gene_likelihood`: `"nb"` for UMI counts. **The library default is `"zinb"`**, so passing `"nb"` is a
  deliberate deviation; `"zinb"` suits high-dropout data. State the choice either way.

## 3. scANVI — semi-supervised annotation / label transfer

```python
scvi.model.SCANVI.setup_anndata(
    adata, layer="counts", batch_key="batch",
    labels_key="cell_type", unlabeled_category="Unknown",
)
model = scvi.model.SCANVI(adata, n_latent=30)
model.train(max_epochs=400)
adata.obs["scanvi_prediction"] = model.predict()
```

> **`unlabeled_category` belongs to `setup_anndata`, not to the constructor.** `SCANVI.__init__` is
> `(self, adata=None, registry=None, n_hidden=128, n_latent=10, …)` — the **second positional is
> `registry`**. So `SCANVI(adata, "Unknown")` binds `"Unknown"` to `registry` and is swallowed; the
> code only works at all because `setup_anndata` already registered the category. Pass it by keyword,
> to `setup_anndata`.

`unlabeled_category` must be the literal value present in `adata.obs[labels_key]` for the cells you
want predicted.

## 4. scArches — reference mapping (PARTIAL: provision first)

Train on a large reference once, project new queries without retraining the atlas.

```python
import scarches as sca

# 1. Reference
sca.models.SCVI.setup_anndata(ref_adata, layer="counts", batch_key="batch")
ref_model = sca.models.SCVI(ref_adata, n_latent=30)
ref_model.train()
ref_model.save("ref_model/")

# 2. Query
query_model = sca.models.SCVI.load_query_data(query_adata, "ref_model/")
query_model.train(max_epochs=200)
query_adata.obsm["X_scvi"] = query_model.get_latent_representation()

# 3. Label transfer — weighted kNN, and keep the uncertainty
from scarches.utils.knn import weighted_knn_trainer, weighted_knn_transfer

knn = weighted_knn_trainer(ref_adata, "X_scvi", n_neighbors=50)
labels, uncert = weighted_knn_transfer(query_adata, "X_scvi", ref_adata.obs, "cell_type", knn)
query_adata.obs["predicted_cell_type"] = labels["cell_type"]
query_adata.obs["transfer_uncertainty"] = uncert["cell_type"]
```

> **There is no `transfer_labels(...)`** — not in scArches, not in scvi-tools. It was never a real
> function. The real API is the weighted-kNN pair above (`scarches/utils/knn.py`:
> `weighted_knn_trainer(train_adata, train_adata_emb, n_neighbors=50)` and
> `weighted_knn_transfer(query_adata, query_adata_emb, ref_adata_obs, label_keys, knn_model, …)`),
> and it returns **two** DataFrames: predictions and per-cell uncertainty.

**Keep the uncertainty and gate on it.** A transferred label with high uncertainty is the model saying
the query cell has no good reference match — usually a cell type absent from the reference, which is
exactly the finding worth surfacing. Dropping the second return value converts that into a confident
wrong label.

## 5. Validate the embedding

```python
sc.pp.neighbors(adata, use_rep="X_scvi")
sc.tl.umap(adata)
sc.pl.umap(adata, color=["batch", "cell_type"], save="scvi_umap.pdf")
```

Inspect it before concluding anything:
- Are batches mixed (if integration was the goal)?
- Are known cell types still separated (if they should be)?
- Any clustering by `n_counts` / `pct_mito` — i.e. technical structure surviving?

## 6. Evaluate quantitatively (PARTIAL: `scib` not pinned)

```python
from scib.metrics import ari, nmi, silhouette

ari_score = ari(adata, "leiden", "cell_type")     # (adata, cluster_key, label_key)
nmi_score = nmi(adata, "leiden", "cell_type")
sil_score = silhouette(adata, label_key="cell_type", embed="X_scvi")
```

- **scib exports `silhouette` and `silhouette_batch`. There is no `silhouette_label`** — that import
  raises `ImportError`, so a block written against it never ran at all.
- Argument order is `(cluster_key, label_key)`. Both metrics are **symmetric**, so swapping them
  returns the identical number — which is precisely why a swapped call survives review. Get it right
  so the code states its intent.

Compare against:
- **the unintegrated baseline** (same metrics on PCA) — integration must not degrade biology
- **the task's SOTA**, if reproducing a benchmark

Emit the metrics in a `report` dict and cite the exact numbers.

## Pitfalls

- **Normalised input** — the model wants raw counts in `layers["counts"]`; log-normalised input makes
  the loss meaningless (and often flat)
- **`unlabeled_category` to the constructor** — silently bound to `registry`
- **`train_size=` to cut memory** — that is the train/validation **split fraction**. Halving it
  discards ~40% of your training data and does nothing to peak memory. Use `batch_size=` (default 128)
- **`transfer_labels(...)`** — does not exist; use the weighted-kNN pair
- **Discarding the kNN uncertainty** — turns "no reference match" into a confident wrong label
- **`silhouette_label`** — not a scib export
- **Embedding never validated** — always UMAP + a metric against the unintegrated baseline
- **`n_latent`/`gene_likelihood` unreported** — both deviate from scvi-tools' defaults (10, `zinb`)

## Grounding

`report`: model + version (e.g. `scvi-tools==1.4.3`), env (pinned `task1–4` vs a provisioned env for
scArches/scib), hyperparams (`n_latent`, `gene_likelihood`, `max_epochs`, `batch_size`), embedding key
and shape, metrics (ARI/NMI/silhouette) **with the unintegrated baseline beside them**, transfer
uncertainty distribution if labels were transferred, and the UMAP path (inspected).

## Sources
- scvi-tools 1.4.3 — `scvi.model.SCVI` / `SCANVI` / `MULTIVI` (signatures verified by introspection)
- scArches — `scarches/utils/knn.py` (`weighted_knn_trainer`, `weighted_knn_transfer`)
- scib — `scib/metrics/__init__.py` (`ari`, `nmi`, `silhouette`, `silhouette_batch`)
