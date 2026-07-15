# Mapping & Deconvolution

**Maturity: PARTIAL** — assign cell types to spatial locations from an scRNA reference. Both tools (**cell2location** for spot deconvolution, **Tangram** for cell/label mapping) need install (not in `task2`); cell2location wants a GPU.

## Goal / When to Use

Two related tasks, pick by platform resolution:
- **Spot deconvolution** (Visium, Slide-seq — multi-cell spots) → estimate **cell-type proportions per spot**. Default: **cell2location**.
- **Cell mapping / label transfer** (project a reference onto space; any platform) → **Tangram**.

Both need a well-annotated, **same-species same-gene-naming** scRNA reference covering the tissue's cell types.

**Their input requirements differ — do not merge them.** cell2location requires **raw counts** on both sides (`LayerField(..., is_count_data=True)`); Tangram's canonical workflow **library-size-normalizes** the reference (`sc.pp.normalize_total`) before `pp_adatas`. Feeding raw counts to Tangram because "both need raw counts" departs from upstream's own recipe. Gene naming likewise: `tg.pp_adatas` lowercases both var indices for you (`gene_to_lowercase=True`), while cell2location matches case-sensitively and hard-guards on it.

## Decision Criteria

- **Visium/spot proportions → cell2location** — Bayesian, models the multi-cell mixture per spot, returns calibrated abundances. GPU-recommended (30k training epochs).
- **"Where would each reference cell/type go" → Tangram** — a cell→voxel mapping fit by gradient descent on a cosine-similarity objective (**not** optimal transport — there is no transport plan or Sinkhorn step anywhere in the package). Also transfers labels and, separately, imputes genes (`imputation.md`).
- **No suitable reference** → stop; report that deconvolution/mapping needs a matched reference.

## How-to — spot deconvolution (cell2location, default)

Two stages: learn per-cell-type signatures from the reference, then map onto the spatial data.

```python
import numpy as np
import cell2location
from cell2location.models import RegressionModel, Cell2location
from cell2location.utils.filtering import filter_genes

# Stage A — reference signatures (raw-count scRNA, cell_type in .obs)
# Upstream filters the reference first: uninformative genes make the regression slow and noisy.
selected = filter_genes(adata_ref, cell_count_cutoff=5, cell_percentage_cutoff2=0.03, nonz_mean_cutoff=1.12)
adata_ref = adata_ref[:, selected].copy()

RegressionModel.setup_anndata(adata_ref, batch_key=None, labels_key="cell_type")
ref = RegressionModel(adata_ref)
ref.train(max_epochs=250, accelerator="gpu")            # `use_gpu=` is the dead pre-scvi-1.x kwarg
ref.plot_history()                                       # <- ELBO must have converged. Observe it.
adata_ref = ref.export_posterior(
    adata_ref, sample_kwargs={"num_samples": 1000, "batch_size": 2500, "accelerator": "gpu"})
ref.plot_QC()                                            # <- observe before trusting the signatures

inf_aver = adata_ref.varm["means_per_cluster_mu_fg"][
    [f"means_per_cluster_mu_fg_{c}" for c in adata_ref.uns["mod"]["factor_names"]]]
inf_aver.columns = adata_ref.uns["mod"]["factor_names"]

# Stage B — spatial mapping (raw-count Visium)
# The gene intersection must be TWO-WAY. Subsetting only adata_vis raises KeyError whenever the
# signature contains a gene the slide lacks (the normal case), and leaves inf_aver un-subset, so
# Cell2location's own guard `np.all(adata.var_names == cell_state_df.index)` can never pass.
intersect = np.intersect1d(adata_vis.var_names, inf_aver.index)
adata_vis = adata_vis[:, intersect].copy()
inf_aver  = inf_aver.loc[intersect, :].copy()

Cell2location.setup_anndata(adata_vis, batch_key="sample")
mod = Cell2location(adata_vis, cell_state_df=inf_aver,
                    N_cells_per_location=30, detection_alpha=20)
mod.train(max_epochs=30000, batch_size=None, train_size=1, accelerator="gpu")
mod.plot_history()                                       # <- 30k epochs converged? Observe it.
adata_vis = mod.export_posterior(
    adata_vis, sample_kwargs={"num_samples": 1000, "batch_size": mod.adata.n_obs, "accelerator": "gpu"})
adata_vis.obs[inf_aver.columns] = adata_vis.obsm["q05_cell_abundance_w_sf"].values   # per-spot abundances (q05)
```

Parameter rationale:
- `N_cells_per_location=30` — prior on cells per spot; **set from paired histology** (≈30 in many tissues). It regularises total abundance to a tissue-plausible count.
- `detection_alpha=20` — regularises within-slide detection variability; **20** for high variability (typical human data), **200** for low. These are the two hyperparameters the authors flag.
- `batch_size=mod.adata.n_obs` in Stage B's `export_posterior` — the default (2048) OOMs on a large slide; upstream passes the full obs count.
- Both stages need **raw counts** — cell2location only, see the note above about Tangram.

## How-to — cell/label mapping (Tangram)

```python
import tangram as tg

tg.pp_adatas(adata_sc, adata_sp, genes=markers)            # intersect/clean genes; writes training_genes
adata_map = tg.map_cells_to_space(adata_sc, adata_sp, mode="clusters",
                                  cluster_label="cell_type", density_prior="rna_count_based",
                                  num_epochs=1000, device="cpu")   # device="cuda:0" for GPU
tg.project_cell_annotations(adata_map, adata_sp, annotation="cell_type")
adata_sp.obsm["tangram_ct_pred"]                            # spots × cell types (spatial prediction)
```
- `mode="clusters"` (with `cluster_label`) maps cell-type clusters — robust, the common choice; `mode="cells"` maps individual cells (heavier). `density_prior="rna_count_based"` weights spots by RNA content.
- `tg.pp_adatas` is **mandatory** — `map_cells_to_space` raises `ValueError: Missing tangram parameters. Run 'pp_adatas()'.` without it. It also mutates both objects in place and **lowercases every `var_name`**, so index in lowercase afterwards.
- Whatever `mode`/`cluster_label` you use here must be **mirrored** in `project_genes` if you go on to impute (`imputation.md`) — they are one decision, not two.

## Failure Modes

- **Deconvolution returns one dominant type everywhere** — *symptom:* flat proportions. *Diagnosis:* reference missing tissue cell types, or signatures degenerate. *Fix:* check `labels_key` covers all types; complete the reference and retrain Stage A.
- **Genes don't intersect** — *symptom:* `KeyError` on the subset, or cell2location's `np.all(adata.var_names == cell_state_df.index)` guard failing. *Diagnosis:* a one-way subset (`adata_vis[:, inf_aver.index]`) assumes the slide contains every signature gene, which it does not. *Fix:* `np.intersect1d` both, then subset **both** — see Stage B.
- **30k epochs, plausible-looking maps, no convergence** — *symptom:* abundance maps look fine but are not reproducible. *Diagnosis:* neither `plot_history()` (ELBO) nor `plot_QC()` was inspected, so a non-converged run is indistinguishable from a good one. *Fix:* observe both after each stage; upstream treats them as mandatory, not optional.
- **Tangram map is diffuse** — *symptom:* every type smeared across all spots. *Diagnosis:* too few shared marker genes, or `mode="cells"` on sparse data. *Fix:* pass informative `genes=markers`; use `mode="clusters"`.

## Figure checkpoints

1. **ELBO history** (`ref.plot_history()`, `mod.plot_history()`) — flat tail = converged. A 30k-epoch run that has not converged still produces a pretty abundance map, which is exactly why this is checkpoint #1.
2. **`ref.plot_QC()`** — reconstruction accuracy of the reference signatures. Bad signatures cannot be rescued in Stage B.
3. **Abundance / proportion maps** (`sq.pl.spatial_scatter(adata_vis, color=<cell_type>)`) — does each type localize to its expected region (T cells in lymphoid areas, etc.)?
4. **Dominant-type map** — does the spatial pattern match the histology / known architecture?

## Grounding

Record: method, reference source + n cell types, `N_cells_per_location`/`detection_alpha` (cell2location) or `mode`/`density_prior` (Tangram), where abundances/predictions landed, and a per-type localization sanity-check → put these in a `report` dict and cite its numbers.

## Honesty

- **Proportions are estimates, not counts** — report inferred abundances; validate localization against markers/histology.
- **Garbage reference → garbage mapping** — if the reference doesn't match the tissue/species, the result reflects the reference, not the spatial biology; say so.
- Both tools need install + (cell2location) a GPU — if unavailable, state that deconvolution was not run rather than substituting a weaker method.
