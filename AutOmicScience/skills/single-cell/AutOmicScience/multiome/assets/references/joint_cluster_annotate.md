# Joint Clustering & Annotation

**Maturity: mixed.** **Clustering is REFERENCE** — you write a Python script that calls `muon` (`mu.pp.neighbors` / `mu.tl.leiden`); `muon` is pinned in `task3`, nothing to install, and "hand-rolled" means *you* make the calls, not that you implement Leiden. **Annotation is READY** — the markers come from the scRNA `marker_table` subcommand, which records evidence for you, and you label from the marker patterns.

## Goal / When to Use

After joint embedding, cluster cells on the joint space and assign biological labels.

## Decision Criteria

- **Cluster on the joint graph/representation:**
  - **WNN** produces a joint **graph** (not an `X_wnn` embedding) — cluster directly on it: `mu.tl.leiden(mdata)` after `mu.pp.neighbors(mdata)`.
  - **MultiVI** produces `obsm["X_multivi"]` — cluster via `mu.pp.neighbors(mdata, use_rep="X_multivi")` → `mu.tl.leiden`.
  - Resolution by marker support, not an arbitrary number.
- **Annotate from markers (same as scRNA):** cluster → marker table → label from the marker patterns + tissue context; abstain to "unknown" when ambiguous (see `rna`: `annotation.md`).

## How-to

```python
import muon as mu
# cluster on the joint representation
mu.pp.neighbors(mdata)                      # WNN graph (or use_rep="X_multivi" for MultiVI)
mu.tl.leiden(mdata, resolution=1.0, key_added="leiden")
mu.tl.umap(mdata)
```

**Annotation — marker + LLM:** markers come from the **RNA** modality via the scRNA marker subcommand; write the RNA modality out and run:
```python
omics_compute(subcommand="marker_table", modality="scrna",
              args={"input": "rna.h5ad", "output": "markers.csv", "groupby": "leiden"})
# thread markers.csv + dataset summary + study description into a labeling decision (rna: annotation.md)
```
Validate each call against **both** modalities — RNA expression *and* ATAC accessibility at the marker genes.


## Failure Modes

- **Clustering on `X_wnn`** — *symptom:* `use_rep="X_wnn"` KeyError. *Diagnosis:* WNN is a graph, not an embedding. *Fix:* cluster on the WNN graph (`mu.tl.leiden(mdata)` after `mu.pp.neighbors`); only MultiVI has `X_multivi`.
- **Joint adds nothing** — *symptom:* joint ARI/NMI ≈ single-modality. *Fix:* report it; don't force a joint interpretation.

## Figure checkpoints

1. Joint UMAP by cluster + by RNA/ATAC QC + by modality weight.
2. Marker validation: do top RNA markers also show ATAC accessibility at those genes?

## Grounding

Record: n_clusters, resolution, annotation route, per-cluster markers, confidence → the `report` dict.

## Honesty

If the joint embedding doesn't beat single-modality (ARI/NMI), say so. Treat any pre-existing `cell_type` column as prior, not ground truth (compare post-hoc, never copy).
