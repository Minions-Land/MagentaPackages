---
name: single-cell-multiome
disable-model-invocation: true
---

# Single-Cell Multiome (RNA + ATAC) Analysis

Paired RNA + ATAC from the same nuclei. Reuses the scRNA and scATAC per-modality recipes, adds joint modeling. Run compute through the **`omics_compute`** tool with `modality="multiome"` (dispatches into the pinned `task3` env, records evidence).

## Prerequisites

1. **Preflight**: `omics_preflight(modality="multiome")` must pass
2. **Shared foundation**: Load `omics-shared` first
3. **Data format**: MuData with paired cells, or separate RNA/ATAC AnnData to assemble
4. **Per-modality knowledge**: Familiar with the scRNA and scATAC recipes

## Capability Menu

| Capability | Maturity | How | Method doc |
|------------|----------|-----|------------|
| Load & assemble paired MuData | **READY** | `omics_compute load_multiome` (`--rna --atac --output`) | `assets/references/load_multiome.md` |
| Per-modality preprocess — RNA | **READY** | `omics_compute preprocess` (modality=scrna); write the modality out, run, read back | `assets/references/per_modality_preprocess.md` |
| Per-modality preprocess — ATAC | **REFERENCE** | hand-rolled `snapatac2` — pinned in `task3`; peak matrix in, so `select_features` + `spectral` only — **TSSE/FRiP/tiles need fragments, not reachable here** | `assets/references/per_modality_preprocess.md` |
| Joint embedding — **WNN** (default) | **REFERENCE** | hand-rolled `muon` `mu.pp.neighbors` — pinned in `task3` (no `joint_embed` subcommand: deliberately excluded pending migration) | `assets/references/joint_embedding.md` |
| Joint embedding — **MultiVI** | **PARTIAL** | `scvi-tools` `MULTIVI` — pinned in `task3` but **needs a GPU**; verify preflight | `assets/references/joint_embedding.md` |
| Joint clustering (Leiden on the joint rep) | **REFERENCE** | hand-rolled `muon` `mu.tl.leiden` — pinned in `task3` | `assets/references/joint_cluster_annotate.md` |
| Annotation (marker + LLM) | **READY** | `omics_compute marker_table` (modality=scrna) → LLM labeling | `assets/references/joint_cluster_annotate.md` |
| Chromatin-informed RNA velocity | **REFERENCE** | MultiVelo — **isolated env, cannot share `task3`** (pins `pandas<=1.4.4`); needs spliced/unspliced | `assets/references/multiome_velocity.md` |
| eGRN / regulation (TF→region→gene) | **REFERENCE** | SCENIC+ — **external Snakemake pipeline in its own env**; needs pycisTopic + Mallet/Java + MACS2 + motif DBs | `assets/references/regulation.md` |
| Cross-modal interpretation (modality weights) | **REFERENCE** | hand-rolled — read WNN's per-cell weights off `mdata.obs` | `assets/references/cross_modality.md` |

**"hand-rolled" = you write the Python script that calls the library** (muon, snapATAC2, …) — *not* that you implement the algorithm. `mu.pp.neighbors` is the real WNN. The only thing REFERENCE costs you versus READY is that no subcommand records evidence for you, so you `print(report)` yourself.

## Global Rules

1. **Preflight first**: `omics_preflight(modality="multiome")` before compute
2. **Reuse scRNA/scATAC**: Don't re-derive uni-modal steps - point to those recipes
3. **Ground every claim**: All quantitative results → the `report` dict
4. **Observe figures**: inspect every plot before conclusions
5. **Earn joint embedding**: Compare against single-modality baselines (ARI/NMI) - only claim improvement if measured
6. **Abstain over fabricate**: Missing data/deps → structured blocker, not guess
7. **Heavy methods expensive**: MultiVI/MultiVelo/SCENIC+ - start small, sanity-check, scale
8. **Write to workdir**: `output/` for reproducibility

## Container Structure

MuData with modalities under `.mod`:
```python
mdata.mod['rna']   # RNA AnnData
mdata.mod['atac']  # ATAC AnnData
mdata.obs          # Shared cell metadata
```

Per conventions (§6): counts in `layers["counts"]`, embeddings in `obsm["X_*"]`, clusters in `obs["leiden"]`, labels in `obs["cell_type"]`

## Standard Workflow

1. **Load/Assemble** → validated MuData with shared barcodes (`load_multiome`, READY)
2. **Per-Modality Preprocess** → RNA: QC/norm/HVG/PCA via the `preprocess` subcommand (modality=scrna). ATAC: feature selection + spectral embedding on the peak matrix — **TSSE-grade QC is not reachable here**; it needs the fragments route (`per_modality_preprocess.md`)
3. **Joint Embedding** → WNN (default) or MultiVI (PARTIAL — GPU) latent space
4. **Joint Cluster** → Leiden on the joint representation
5. **Annotate** → marker + LLM (markers via the `marker_table` subcommand) on the RNA modality (`joint_cluster_annotate.md`)
6. **Cross-Modal Interpretation** → modality weights: which populations are RNA- vs ATAC-driven (`cross_modality.md`). Peak→gene links, TF→target and eGRN are **not** here — they come from the SCENIC+ pipeline (`regulation.md`)

## Compute Dispatch

Run compute through the **`omics_compute`** tool with `modality="multiome"`:
```python
# Available subcommands under modality="multiome":
#   - load_multiome: Assemble/validate paired MuData   (flags: --rna --atac --output)
```

`load_multiome` is the **only** multiome-modality subcommand. The per-modality READY paths dispatch under a **different** modality — write the modality out of the MuData, run it there, read it back:

- RNA preprocess / marker table → `modality="scrna"` (task1)
- ATAC QC / peak calling / gene activity → `modality="scatac"` (task4) — **but only on a `snapatac2.pp.import_fragments` object.** They cannot run on `mdata["atac"]`, which is a peak matrix with no insertions; see `per_modality_preprocess.md`.

Joint embedding (WNN / MultiVI) is a `muon` / `scvi-tools` script — both pinned in `task3`. Velocity (MultiVelo) and eGRN (SCENIC+) run as external pipelines in **isolated envs** — see their method docs.
