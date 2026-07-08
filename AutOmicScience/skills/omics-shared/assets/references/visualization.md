# Visualization & Figure Inspection

Plotting patterns for omics figures (scanpy / matplotlib / squidpy), plus the habit of **inspecting a
figure before it backs a claim** (see also `grounding.md`).

## Save figures to disk

Save every figure (`show=False` → `savefig` → `close`) into a `figures/` directory — an inline plot
can't be inspected or attached to the report:

```python
import matplotlib.pyplot as plt
sc.pl.umap(adata, color="leiden", show=False)
plt.savefig("figures/umap_leiden.png", dpi=150, bbox_inches="tight")
plt.close()
```

## Inspect before citing

Before a figure backs a claim, **look at it** and check for: **artifacts** (stripes, all-one-color),
**wrong scale** (saturated/empty colorbar), **empty or mislabeled axes**, and **unexpected
structure** (one giant blob where you expected clusters; clusters tracking a QC metric rather than
biology). If it looks wrong, fix the upstream step and re-plot before reporting — don't cite a figure
you haven't verified.

## Common scanpy plots

**Embedding:**
```python
sc.pl.umap(adata, color=["leiden", "n_genes", "pct_mito"], show=False)
plt.savefig("figures/umap_overview.png", dpi=150, bbox_inches="tight"); plt.close()
```

**QC violin:**
```python
sc.pl.violin(adata, ["n_genes", "n_counts", "pct_mito"], groupby="leiden", show=False)
plt.savefig("figures/qc_violin.png", dpi=150, bbox_inches="tight"); plt.close()
```

**Marker heatmap:**
```python
sc.pl.heatmap(adata, marker_genes, groupby="leiden", swap_axes=True, show=False)
plt.savefig("figures/marker_heatmap.png", dpi=150, bbox_inches="tight"); plt.close()
```

**Spatial (if spatial data):**
```python
import squidpy as sq
sq.pl.spatial_scatter(adata, color="cell_type", size=1.5, show=False)
plt.savefig("figures/spatial_celltypes.png", dpi=150, bbox_inches="tight"); plt.close()
```

## DPI & format

- **DPI** 150 (quality/size balance); **PNG** (lossless for plots); `bbox_inches="tight"`.
- Publication: `plt.savefig("figures/fig.pdf", dpi=300, bbox_inches="tight")`.

## Batch plotting

```python
figures = {
    "umap_leiden":  lambda: sc.pl.umap(adata, color="leiden", show=False),
    "umap_batches": lambda: sc.pl.umap(adata, color="batch", show=False),
    "qc_violin":    lambda: sc.pl.violin(adata, ["n_genes", "pct_mito"], show=False),
}
for name, plot_fn in figures.items():
    plot_fn()
    plt.savefig(f"figures/{name}.png", dpi=150, bbox_inches="tight")
    plt.close()
```

## Pitfalls

- **`show=True` / relying on inline display** — not saved, can't be inspected. Always
  `show=False` + `savefig` + `close`.
- **Citing a figure you didn't look at** — "UMAP shows clear separation" without inspecting it.
- **Reusing filenames** — use descriptive unique names (`umap_leiden.png`, `umap_batch.png`).
- **Forgetting `plt.close()`** — accumulates figures in memory during batch plotting.

## Honesty

- If a figure looks wrong, off-scale, or ambiguous, say so in the conclusion — don't overstate what
  it shows. A figure is evidence only once you've actually looked at it.
