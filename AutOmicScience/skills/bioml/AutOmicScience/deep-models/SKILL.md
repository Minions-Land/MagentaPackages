---
name: bioml-deep-models
disable-model-invocation: true
---

# BioML Deep Models — Single-Cell Foundation & Deep Integration Models

> Subskill of `bioml`. Enter here from the parent skill when you need to train or apply a single-cell deep learning model. Read the parent (`../SKILL.md`) and the always-loaded `omics-shared` skill first — their ML-engineering foundations and evidence rules apply here.

This subskill covers **single-cell deep learning models** for integration, label transfer, reference mapping, and representation learning — the scvi-tools / scArches / scGPT / SATURN ecosystem. These models often **match or beat bespoke methods** at a fraction of the complexity, making them the first escape-hatch to try before reproducing a heavy paper pipeline.

---

## Escape Hatch Priority

**Before reaching for a foundation model or reproducing a heavy paper pipeline, run the mature baseline first.** Across benchmarks, simpler methods repeatedly match or beat the advertised SOTA on well-posed tasks (scVI-KMeans ≥ meK-means, scANVI ≥ scPoli, DeepSTARR CNN ≥ Nucleotide Transformer). Foundation models justify their compute cost only for few-shot learning, cross-species without orthologs, or when the baseline provably falls short. See `assets/references/foundation_models_escape.md` for the decision tree and the baseline-first recipe.

---

## When to Use Deep Models

Use this path when:
- The task is **label transfer** (annotate query cells against a labeled reference)
- The task is **atlas integration** (harmonize multiple datasets into a shared embedding)
- The task is **multimodal integration** (joint RNA+ATAC, RNA+protein, spatial+scRNA)
- The baseline uses a transformer/GNN/VAE and you want to check whether a mature simpler model already clears the bar

**Skip this path** for standard scanpy analysis (QC/clustering/DE) — use `../../../single-cell/AutOmicScience/` instead.

---

## The Model Menu

Maturity here is **environment availability**, not method quality: **REFERENCE** = the package is in
`task1–4`, you hand-write the script; **PARTIAL** = provision it first (§2).

| Model | Use case | Package | Maturity | Compute |
|-------|----------|---------|----------|---------|
| **scVI** | Batch integration, denoising, dimensionality reduction | scvi-tools | **REFERENCE** — pinned | GPU (minutes) |
| **scANVI** | Semi-supervised annotation, label transfer | scvi-tools | **REFERENCE** — pinned | GPU (minutes) |
| **MultiVI** | Joint RNA+ATAC/protein (multiome) | scvi-tools | **REFERENCE** — pinned | GPU (minutes) |
| **totalVI** | RNA→protein prediction (CITE-seq) | scvi-tools | **REFERENCE** — pinned | GPU (minutes–hours) |
| **contrastiveVI** | Conditional generation, perturbation modeling | scvi-tools | **REFERENCE** — pinned | GPU (minutes–hours) |
| **PAGA** | Trajectory topology (coarse-grained, first try) | scanpy | **REFERENCE** — pinned | CPU (seconds) |
| **scVelo** | RNA velocity (pseudotime direction) | scvelo | **REFERENCE** — pinned | GPU (minutes) |
| **scArches** | Reference mapping (train on ref, project query) | scArches | **PARTIAL** — not pinned | GPU (minutes) |
| **scPoli** | Atlas-scale reference mapping, label transfer | scArches | **PARTIAL** — not pinned | GPU (minutes–hours) |
| **scib** (metrics) | ARI / NMI / silhouette benchmarking | scib | **PARTIAL** — not pinned | CPU |
| **sciPENN** | RNA→protein translation | sciPENN | **PARTIAL** — not pinned | GPU (minutes) |
| **PHLOWER** | Trajectory inference (tree topology, escalation) | PHLOWER (repo) | **PARTIAL** — not pinned | CPU (minutes) |
| **SATURN** | Cross-species / cross-modality matching | SATURN (separate repo) | **PARTIAL** — repo install | GPU (hours) |
| **scGPT** | Foundation model, few-shot learning | scGPT (separate repo) | **PARTIAL** — repo install | GPU (hours), large memory |
| **Geneformer** | Foundation model (few-shot alternative to scGPT) | Geneformer (HF) | **PARTIAL** — repo install | GPU (hours), 24 GB+ |

**First try: scANVI** for label transfer; **scVI + KMeans** for integration. Both are pinned, fast,
well-tested, and often sufficient — which is also why the escape hatch above points at them. Note that
scArches is *not* pinned, so "first try scArches" costs you a provisioning step that scANVI doesn't.

### Task-specific reference docs

| Task | Reference doc |
|------|---------------|
| **scVI / scANVI / MultiVI training; scArches reference mapping; scib metrics** | `assets/references/scvi_workflow.md` |
| RNA→protein translation (CITE-seq prediction) | `assets/references/rna_to_protein.md` |
| Trajectory / pseudotime → dynverse output | `assets/references/trajectory_pseudotime.md` |
| Cross-species / cross-modality (SATURN) | `assets/references/saturn_cross_species.md` |
| Foundation-model decision + escape hatches | `assets/references/foundation_models_escape.md` |
| Perturbation outcome prediction (Perturb-seq) | `assets/references/perturbation_prediction.md` |

---

## General Deep Model Recipe

### 1. Confirm prerequisites

- GPU available (`nvidia-smi`, `torch.cuda.is_available()`)
- Enough GPU memory (scVI/scANVI: ~8 GB for 50k cells; scGPT: 24–40 GB)
- Data is preprocessed AnnData: `adata.layers["counts"]` exists (raw counts), basic QC done

### 2. Get the package — check before you install

**`scvi-tools` is already pinned** (`pixi.toml`: `scvi-tools = ">=1.1"`, resolved to 1.4.3 in
`task1–4`). scVI, scANVI, MultiVI and totalVI need **no installation at all** — import and go.

Everything else in the menu (`scArches`, `scPoli`, `scib`, `SATURN`, `scGPT`, `Geneformer`,
`sciPENN`, `PHLOWER`) is **not pinned**. Provision per `omics-shared`'s
`assets/references/AOSE_nonStandard_env.md` — §A, a Pixi feature + environment with its **own
solve-group**, composing `["core", "singlecell", <new>]` so the pinned stack comes with it:

```toml
# tools/omics-environment/pixi.toml
[feature.scarches.pypi-dependencies]
scarches = "*"
scib = "*"

[environments]
scarches = { features = ["core", "singlecell", "scarches"], solve-group = "scarches" }
```

```bash
pixi install --manifest-path tools/omics-environment/pixi.toml -e scarches
pixi lock    --manifest-path tools/omics-environment/pixi.toml
```

> **Never `pip install scvi-tools`.** It is already there, so the install is pure risk: a bare `pip`
> resolves against whatever `python` is first on `$PATH` — often conda `base` — and can downgrade the
> `pandas`/`numpy` that `task1–4` are locked to. The rule is absolute: named env, or nothing. GPU
> stacks that Pixi cannot solve are the §B conda-env case, still named, never `base`.

Record the env and the resolved versions in the `report`. `omics_preflight` only validates `task1–4`,
so check the import yourself after provisioning.

### 3. Prepare the data

- **Raw counts** in `adata.layers["counts"]` — capture them *before* normalising. These models are
  built on a count likelihood; log-normalised input makes the loss meaningless
- **Batch/condition** in `adata.obs["batch"]`; **labels** in `adata.obs["cell_type"]` for scANVI/scPoli
- Normalise + log for *visualisation only*

### 4. Train

- **scVI** — integration / denoising. `n_latent` and `gene_likelihood` both deviate from scvi-tools'
  own defaults (10, `zinb`) in most recipes, so **state which you used**
- **scANVI** — semi-supervised annotation. `unlabeled_category` goes to **`setup_anndata`**, not the
  constructor: `SCANVI.__init__`'s second positional is `registry`, so passing it there is silently
  swallowed
- **scArches** (PARTIAL) — reference mapping. Label transfer is a weighted-kNN pair that returns
  **uncertainty as well as labels**; `transfer_labels(...)` does not exist and never did. Keep the
  uncertainty — a high value is the model saying "this query cell has no reference match", usually a
  cell type absent from the reference. That is the finding, not the noise

### 5. Validate the embedding

UMAP on the latent representation, coloured by batch and by label. Inspect it before concluding:

- Are batches mixed (if integration was the goal)?
- Are known cell types still separated (if they should be)?
- Any clustering by `n_counts` / `pct_mito` — technical structure surviving?

### 6. Evaluate quantitatively (PARTIAL — `scib` not pinned)

ARI / NMI / silhouette **against the unintegrated baseline**, never in isolation.

- Integration that improves batch-mixing while lowering ARI against known labels has **destroyed
  biology**. The baseline comparison is the only thing that makes that visible
- scib exports `silhouette` / `silhouette_batch` — there is no `silhouette_label`
- Emit the numbers in a `report` dict and cite them exactly

---

Steps 3–6 are runnable in **`assets/references/scvi_workflow.md`** — signatures verified against
scvi-tools 1.4.3 and scArches/scib upstream source. Task-specific paths (RNA→protein, trajectory,
SATURN, foundation-model escape, perturbation) have their own docs, listed above.


## Model-Specific Notes

### scVI
- **Fast, robust, works out of the box** for most integration tasks.
- `n_latent=30` is *this doc's* choice and works up to ~100k cells; increase to 50 for larger. (scvi-tools'
  own default is **10**, not 30 — say which you used.)
- Use `gene_likelihood="nb"` (negative binomial) for UMI counts; `"zinb"` if high dropout.

### scANVI
- Semi-supervised: you label a subset, it propagates labels to unlabeled cells.
- `unlabeled_category` must be in `adata.obs[labels_key]` for the cells you want predicted.
- Train epochs: ~400 for scVI phase, ~200 for scANVI phase.

### scArches / scPoli
- **Reference mapping** — train on a large reference once, project new queries without retraining the full atlas.
- scPoli extends scArches with label transfer and uncertainty quantification.
- Best for atlas-scale tasks (millions of reference cells).

### MultiVI
- Joint RNA+ATAC or RNA+protein in a single MuData.
- Expects `mdata.mod["rna"]` and `mdata.mod["atac"]` (or `protein`).
- Setup: `scvi.model.MULTIVI.setup_mudata(mdata, modalities={"rna_layer": "rna", "atac_layer": "atac"})`
  — the dict maps **param name → modality name**. Inverting it raises
  `ValueError: Extraneous modality mapping(s) detected`.

### SATURN / scGPT
- **Foundation models** — pre-trained on large corpora, fine-tune on your task.
- Require their own repos (not in scvi-tools). Follow their READMEs closely.
- GPU memory: 24–40 GB. Wall-clock: hours for fine-tuning.
- Best for **few-shot** tasks (small labeled set) or **cross-species** transfer.

---

## Pitfalls & fixes

| Symptom / mistake | Cause | Fix |
|-------------------|-------|-----|
| Loss doesn't decrease | LR too high, or non-raw input (log-normalized / all-zeros / wrong format) | Ensure raw UMI counts in `adata.layers["counts"]`; lower the LR |
| OOM during training | Batch size too large for the GPU | `.train(batch_size=32)` (default 128). **Not** `train_size=` — that is the train/validation **split fraction**, so halving it silently discards ~40% of your training data and does nothing to peak memory |
| Embedding looks like noise | Too few epochs / `n_latent` too low; embedding never validated | Train longer (~800 epochs), raise `n_latent` (~50); always UMAP + metric check |
| Worse than baseline | Integration too aggressive (biology lost), or the baseline was skipped | Compare ARI/NMI vs unintegrated (don't integrate if it degrades); check scVI + KMeans clears the bar first |
| "Beats SOTA" that doesn't hold up | Compared on a cherry-picked metric | Confirm which metric actually matters for the task |
| `pandas`/`numpy` downgraded, `task1–4` broken | A bare `pip install` resolved against conda `base` | scvi-tools is already pinned — don't install it; everything else goes in a named env (§2) |
| `ModuleNotFoundError: scarches` / `scib` | Neither is pinned; only scvi-tools is | Provision per §2 — `omics_preflight` won't catch this, it only covers `task1–4` |

---

## Evidence & Reporting

Every deep-model run emits:
- Model name + version (e.g., `scvi-tools==1.0.3`)
- Hyperparams: `n_latent`, `gene_likelihood`, `max_epochs`, `train_size`
- Embedding shape and where it's stored (`adata.obsm["X_scvi"]`)
- Quantitative metrics: ARI, NMI, silhouette, ASW (batch), etc. — cite exact numbers from the `report` dict
- UMAP figure → inspect it before it backs a claim
- Comparison to baseline (unintegrated, or task SOTA)

This is your audit trail. If the model beats the baseline, document **why** (better batch correction? better latent structure?). If it doesn't, document **why not** (biology degraded? wrong hyperparams? task mismatch?).
