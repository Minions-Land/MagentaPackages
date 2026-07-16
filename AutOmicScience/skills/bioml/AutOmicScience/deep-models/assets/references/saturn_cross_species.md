# Reference — SATURN Cross-Species / Cross-Modality Matching

**Maturity: PARTIAL** — `saturn` is **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Provision it into its own environment per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`, which carries the routing and the hard rules.

SATURN aligns cells across species (human / mouse) or modalities (scRNA / scATAC) via a macrogene abstraction + VAE architecture. Use when simpler methods (scVI/scArches on shared genes) fail due to namespace mismatch.

## When SATURN justifies complexity

SATURN wins when:
- **Cross-species** with <70% ortholog coverage (e.g., zebrafish → human)
- **Cross-modality** (scRNA → scATAC) where gene-activity scores don't align well
- The baseline (scVI on shared genes or GLUE) scores <0.6 on the target metric

**Escape hatch:** Try **scVI on orthologs** first (human-mouse share ~80% orthologs; scVI on the shared set is often within 0.03 of SATURN). SATURN's macrogene construction is elegant but adds days of setup; only escalate if simpler methods miss the bar.

## The macrogene concept

SATURN groups genes into evolutionarily-conserved modules (macrogenes) via:
1. Ortholog mapping (Ensembl BioMart, OrthoFinder)
2. Co-expression clustering within each species
3. Alignment of clusters across species (consensus macrogenes)

A macrogene = a stable functional unit (pathway/complex) that exists in both species, even if individual gene names differ.

## Workflow (high-level)

```python
# SATURN has NO importable Python API. There is no `saturn` module, no `SATURN` class, no
# `get_latent_representation()`, and no `species_key` anywhere in the repo (all 0 hits at rev 6906abf).
# It is a CLI. Do not write `from saturn import SATURN` — it will not import.

# 1. Build the input CSV: one row per species, columns `path,species,embedding_path`
#    (`path` -> that species' .h5ad; `embedding_path` -> its protein-embedding .pt)

# 2. Train — this is the whole entry point
```
```bash
python train-saturn.py \
  --in_data species_map.csv \
  --in_label_col cell_type \
  --ref_label_col cell_type \
  --num_macrogenes 2000 \
  --epochs 50 \
  --work_dir ./saturn_out
```
```python
# 3. SATURN writes its shared embedding to an .h5ad under --work_dir; read it back with scanpy
#    and use obsm["X_saturn"] from there. Verify the key in the output file — do not assume it.
import scanpy as sc
adata_combined = sc.read_h5ad("saturn_out/<run>_saturn_seed_0.h5ad")

# 4. Transfer labels via kNN in the shared space
from sklearn.neighbors import KNeighborsClassifier
ref = adata_combined[adata_combined.obs.species == "human"]
knn = KNeighborsClassifier(n_neighbors=15)
knn.fit(ref.obsm["X_saturn"], ref.obs["cell_type"])
adata_combined.obs["predicted_type"] = knn.predict(adata_combined.obsm["X_saturn"])
```

Real flags (verified from `train-saturn.py` at rev `6906abf`): `--in_data --in_label_col --ref_label_col
--num_macrogenes --epochs --work_dir --hv_genes --pretrain --pretrain_epochs --embedding_model --device
--seed --vae --score_adatas` and others. `Vignettes/frog_zebrafish_embryogenesis/Train SATURN.ipynb`
upstream is the worked example.

## Output contract

Cross-species tasks often require:
- **Cell-type transfer accuracy** (fraction of query cells correctly labeled)
- **Shared embedding quality** (silhouette, batch-mixing, ASW)

Verify the exact required metric — some score ARI, some accuracy, some cosine on embeddings.

## Installation

SATURN is a research repo (not on PyPI) and **has no `setup.py` or `pyproject.toml`**, so
`pip install -e .` fails — there is nothing to install. Clone it and run the script in place, from an env
provisioned per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` — an env of your own for its
torch stack, or a named conda env if CUDA needs pinning:

```bash
git clone https://github.com/snap-stanford/SATURN.git
cd SATURN
pip install -r requirements.txt      # into the provisioned env — never base
python train-saturn.py --in_data ... # run in place; there is no installed package to import
```

Document the commit SHA + dependencies in your environment lockfile.

## Pitfalls

- **Skipping the ortholog baseline** — scVI on orthologs often gets within 0.03 of SATURN for mouse-human at 10% of the effort
- **Macrogene construction failures** — need sufficient co-expression signal; low-quality data breaks clustering
- **Wrong species metadata** — SATURN's batch-correction keys on `species`; mislabeling scrambles the embedding
- **Ignoring the required metric** — cross-species papers report many metrics; use the required one

## Grounding

`report`: SATURN version + commit SHA, macrogene construction details (n macrogenes, ortholog source), embedding quality (silhouette, ASW), transfer accuracy or ARI, comparison to ortholog-based scVI baseline (and why SATURN was chosen over the simpler path).
