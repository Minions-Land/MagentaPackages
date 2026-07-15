# Per-Modality Preprocessing

**Maturity: mixed.** **RNA is READY** — it goes through the scRNA `preprocess` subcommand (write the modality out, run, read back). **ATAC is REFERENCE** — hand-rolled snapATAC2 in a Python script (`snapatac2` is pinned in `task3`). Prepare each modality for joint analysis by **reusing the scRNA and scATAC recipes** on `mdata["rna"]` / `mdata["atac"]`. No new steps invented here.

> **`mdata["atac"]` is a peak matrix, not a snapATAC2 fragments object** — it has no insertions in `obsm`. That single fact decides which ATAC QC is reachable at all. Read *"What ATAC QC is possible here"* below **before** reaching for `atac_qc`, `snap.metrics.tsse`, or `snap.pp.add_tile_matrix`; none of the three can run on this object.

## Goal / When to Use

Before joint embedding, each modality needs its own embedding (RNA: PCA; ATAC: spectral/LSI) with **raw counts preserved** (`layers["counts"]`). What you compute is governed by the joint method you'll use.

## Decision Criteria

- **RNA** (`mdata["rna"]`) — scRNA recipe: QC → normalize → HVG → PCA. For **MultiVI** keep `layers["counts"]` intact (it needs raw counts); for **WNN** you need `X_pca`.
- **ATAC** (`mdata["atac"]`) — you arrive holding a **peak matrix**, so the scATAC recipe starts at **feature selection → spectral embedding**. The fragments-based QC (TSSE/FRiP/nucleosome) and the tile-matrix step are **not reachable from here** — see below. For **MultiVI** keep `layers["counts"]`; for **WNN** you need `X_spectral` (or `X_lsi`).
- **Which joint method governs requirements:** WNN → per-modality embeddings; MultiVI → raw counts in both.

## How-to

Run each modality through its modality's path, then re-intersect if filtering dropped cells.

```python
# RNA — scRNA preprocess subcommand (write the modality out, run, read back)
omics_compute(subcommand="preprocess", modality="scrna",
              args={"input": "rna.h5ad", "output": "rna_pp.h5ad"})   # QC→norm→HVG→PCA→neighbors→UMAP→Leiden

# ATAC — mdata["atac"] is a PEAK matrix: select features, then embed. No tsse / add_tile_matrix here
# (both read insertions, which this object does not have — see the QC table below).
import snapatac2 as snap, muon as mu
snap.pp.select_features(mdata["atac"], n_features=25000)
snap.tl.spectral(mdata["atac"], n_comps=30)                          # -> obsm["X_spectral"]

# Re-intersect if either modality dropped cells during QC
mu.pp.intersect_obs(mdata)
```

Point at the modality recipes — **don't duplicate them here**: `rna` (`../../../rna/assets/references/qc.md`, `../../../rna/assets/references/integration.md`) and `atac` (`../../../atac/assets/references/atac_qc.md`, `../../../atac/assets/references/feature_matrix.md`, `../../../atac/assets/references/dimred_cluster.md`). Note the ATAC recipes assume a snapATAC2 fragments object — see the next section for what carries over to a multiome peak matrix and what does not.

## What ATAC QC is possible here

`load_multiome` hands you a **peak matrix**: it reads the ATAC `.h5ad` as a plain AnnData and never imports fragments. (Its Python-level `fragments_path` argument only records the path string into `mdata["atac"].uns["files"]` — it does not import anything, and the `omics_compute load_multiome` CLI does not even expose it: the flags are `--rna --atac --output`.) So `mdata["atac"].obsm` holds **no insertions**, and that decides what is computable:

| Metric | On this object? | Why |
|---|---|---|
| Peaks per cell, total counts | ✅ | already computed by `load_multiome` (`n_genes_by_counts`), which filters at `min_peaks=500` |
| TSSE | ❌ | insertion-based by definition — a peak matrix has counts *per peak*, not insertion positions |
| FRiP | ❌ | the denominator is total fragments; a peak matrix holds only the numerator |
| Fragment size / nucleosome signal | ❌ | needs paired fragment lengths |
| `n_fragment` | ❌ | written by `import_fragments`; `atac_qc.md` states there is no proxy path |

**`omics_compute atac_qc` cannot be called on `mdata["atac"]`.** The tool descriptor is explicit: the three scatac subcommands "take an `--adata` produced by `snapatac2.pp.import_fragments` (they read insertions from `obsm`, so **a plain feature matrix is rejected**)". The same requirement blocks `snap.metrics.tsse` and `snap.pp.add_tile_matrix` in a hand-written script — the constraint is snapATAC2's, not the subcommand's, so dropping to a script does not evade it.

**If you need TSSE-grade ATAC QC**, take the fragments route instead — 10x multiome ships `atac_fragments.tsv.gz` beside the matrix:

1. `snap.pp.import_fragments(fragment_file="atac_fragments.tsv.gz", chrom_sizes=snap.genome.hg38.chrom_sizes)` (`atac`: `import_fragments.md`)
2. `omics_compute(subcommand="atac_qc", modality="scatac", args={"adata": "...", "gtf-file": "...", ...})` — **READY**, and it records evidence for you
3. Carry the resulting `obs` metrics back onto `mdata["atac"]` **by barcode**, then `mu.pp.intersect_obs(mdata)`

If there is no fragments file, **say so**: report that ATAC QC here is limited to per-cell peak counts. Do not present the `min_peaks` filter as if it were full ATAC QC — it is a count floor, not a signal-quality measure.

## Failure Modes

- **Normalized the layer MultiVI reads from** — *symptom:* garbage MultiVI latent. *Diagnosis:* MultiVI needs raw counts. *Fix:* keep `layers["counts"]`; point MultiVI at it.
- **Forgot to re-intersect after per-modality filtering** — *symptom:* modality cell counts diverge, joint step errors. *Fix:* `mu.pp.intersect_obs(mdata)` after QC.
- **`tsse` / `add_tile_matrix` / `atac_qc` on `mdata["atac"]`** — *symptom:* the call errors on missing insertions, or `atac_qc` rejects the input. *Diagnosis:* all three read insertions from `obsm`, and the multiome load path produces a peak matrix without them. *Fix:* don't call them here — use `select_features` + `spectral` (above); if you need TSSE, go the fragments route.
- **`add_tile_matrix` on an object that already has peaks** — *symptom:* you "rebuild" features you already have. *Diagnosis:* tiles come *before* peaks in the scATAC flow (`atac`: `feature_matrix.md`), and multiome starts at peaks. *Fix:* skip it; select features from the peaks you have.
- **Poor ATAC TSSE** — *symptom:* one modality low-quality. *Diagnosis:* it poisons the joint embedding (WNN weights reveal it). *Fix:* flag it; consider single-modality for that population. (Requires the fragments route — TSSE is not computable from the peak matrix.)

## Figure checkpoints

- RNA QC (n_genes / mt%) and ATAC TSSE distributions — reuse the per-modality checks; both modalities must pass before joining.

## Grounding

Per modality: cells/features after filtering, HVG count, PCA/spectral variance, counts preserved → the `report` dict.

## Honesty

If one modality is low-quality (e.g., poor TSSE), flag it — a weak modality drags the joint embedding, and the WNN weights will show it.
