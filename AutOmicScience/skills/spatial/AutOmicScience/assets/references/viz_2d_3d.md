# 2D/3D Visualization & Figure Inspection

**Maturity: REFERENCE** — hand-rolled plotting with squidpy / spatialdata-plot; every figure is observed before it backs a claim. Both land in `task2`, but note `spatialdata-plot` is **not** declared in `pixi.toml` — it arrives only as a transitive run-dep of conda-forge `squidpy`, so it is present today (lock: `spatialdata-plot 0.4.0`) on a dependency you do not control. APIs below verified against `scverse/spatialdata-plot` rev `076eeac` and `scverse/squidpy` rev `ea52e8e`.

## Goal / When to Use

Produce spatial figures that the agent then **observes** to re-route — overlays on tissue, multi-section comparisons, 3D point clouds. Use throughout spatial analysis; every figure is observed before it backs a claim.

## Decision Criteria

**The judgment this guides:**

- **2D scatter on `obsm['spatial']`** (`sq.pl.spatial_scatter`) for spots/cells colored by gene/cluster/QC — the lightweight default for most spatial plots

- **SpatialData + spatialdata-plot** (`sdata.pl.render_images(...).pl.render_shapes(...).pl.show()`) when you need the registered image, segmentation polygons, or transcripts at native resolution. These are **accessor methods on the SpatialData object**, not importable functions — see below.

- **3D point cloud** (matplotlib 3D / plotly) only when coordinates are genuinely 3D (z-stack, serial sections with registered z, Stereo-seq volumes) — not for 2D data artificially embedded in 3D

- **Choose by what must be verified**, not by aesthetics. A pretty figure that doesn't answer the QC/biological question is useless.

## Method Menu

- `squidpy.pl.spatial_scatter` / `spatial_segment` — 2D overlays on coords, with optional image
- `spatialdata_plot` — `import spatialdata_plot` registers a `.pl` accessor on `SpatialData`; chain `sdata.pl.render_*(...).pl.show()` for images/shapes/points/labels at native resolution
- `scanpy.pl.spatial` (legacy AnnData-with-image) — **deprecated in recent scanpy in favor of `squidpy.pl.spatial_scatter`** — prefer the squidpy plot and confirm availability against the pinned scanpy version
- 3D scatter (matplotlib `ax.scatter(xs, ys, zs)` or plotly) for serial sections / Stereo-seq volumes

## How-to

### 2D spatial scatter (most common)

```python
import squidpy as sq

# Gene expression overlay
sq.pl.spatial_scatter(
    adata,
    color='CD3D',   # or a cluster column like 'leiden'
    figsize=(6, 6),
    size=1.5,       # squidpy's param is `size`. `spot_size` is a scanpy-ism and does not
                    # exist in squidpy — it passes through to matplotlib and raises
                    # AttributeError: unexpected keyword argument 'spot_size'
    save='_CD3D_spatial.png'   # literal path under scanpy.settings.figdir -> figures/_CD3D_spatial.png
)
# inspect the figure: is the expected localization visible? (e.g., immune marker in immune-rich regions)

# Multi-gene panel
sq.pl.spatial_scatter(
    adata,
    color=['CD3D', 'MS4A1', 'LYZ'],
    ncols=3,
    figsize=(15, 5),
    save='_marker_panel.png'
)
```

### SpatialData with image/segmentation

```python
import spatialdata_plot   # side-effect import: registers the `.pl` accessor on SpatialData.
                          # It exports no render functions — __all__ is
                          # ["PercentileNormalize", "Verbosity", "pl", "set_verbosity"].

# Layers compose by CHAINING through `.pl`, in draw order (first call = bottom layer).
(
    sdata.pl.render_images("image")
         .pl.render_shapes("segmentation", fill_alpha=0.3)
         .pl.render_labels("cell_labels", color="leiden")
         .pl.show(figsize=(10, 10), save="_spatialdata_overlay.png")
)
```

Each `render_*` returns the `SpatialData` object, which is why the chain re-enters through `.pl` every
step. `.pl` is the **entry** accessor (`sdata.pl.render_images(...)`), never a trailing attribute on a
result. There is no pipe/`|` composition — `spatialdata-plot` defines no `__or__`.

First positional argument of every `render_*` is `element` (the element name in `sdata`); `color` is
positional-or-keyword on `render_shapes`/`render_labels`/`render_points`, and everything after is
keyword-only. `show()` takes `figsize`, `dpi`, `title`, `save`, `ax`, `return_ax` as keyword-only args.

### 3D point cloud (serial sections or volumetric)

```python
import matplotlib.pyplot as plt
# no Axes3D import needed — projection='3d' has been self-registering since matplotlib 3.2

fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

coords = adata.obsm['spatial']  # shape (n_obs, 3)
colors = adata.obs['leiden'].astype('category').cat.codes

# Downsample for responsiveness if n_obs is large
if coords.shape[0] > 10000:
    import numpy as np
    np.random.seed(0)
    idx = np.random.choice(coords.shape[0], 10000, replace=False)
    coords = coords[idx, :]
    colors = colors[idx]

ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2], c=colors, s=1, alpha=0.5)
ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
plt.savefig('figures/_3d_leiden.png', dpi=150)
plt.close()
```

## Pitfalls & Quality Checks

- **Spot size mismatched to coordinate scale** — yields a blank (spots too small, invisible) or a solid blob (spots too large, overlap). Tune `size` until individual spots/cells are visible but not overlapping. The param is `size`; `spot_size` belongs to `scanpy.pl.spatial` and raises in squidpy.

- **Coordinate flips** between image and array space are common (Visium row/col vs. image x/y) — verify a known landmark (e.g., an anatomical feature) aligns. If the tissue outline looks mirrored or rotated, coords may be flipped.

- **Color scale saturation** hides structure — if all values are squashed to one color, clip to a high percentile (e.g., `vmax=np.percentile(adata.obs['total_counts'], 99)`).

- **The whole point is to inspect the figure** — an empty/garbled figure is a red flag to re-route (wrong coords, missing data, scale issue). Inspecting it confirms the figure is usable.

- **3D responsiveness** — downsample to ~10K points if the dataset is large; fix a camera/orientation so successive frames are comparable (rotating the view makes before/after comparisons impossible).

## Grounding

**What to record in the `report` dict:**

```python
{
  "figure_path": "figures/_CD3D_spatial.png",   # save= is a literal path under figures/
  "plot_type": "spatial_scatter",
  "color_by": "CD3D",
  "coord_dim": 2,
  "size": 1.5,
  "n_obs_plotted": 3500,
  "figure_note": "tissue outline clear, CD3D high in lymphoid region"
}
```

Ground: figure path, what is plotted, color/scale settings. Inspecting the figure confirms it is usable.

## Honesty

- **A pretty figure is not a result** — only the grounded numbers behind it are. Do not let a visualization stand in for a quantitative claim (e.g., "CD3D is high in region X" needs a per-region mean, not just a colored plot).

- If a figure is unclear/ambiguous after inspection, **say so** — treat downstream claims as unconfirmed and either re-plot or gather orthogonal evidence.

- **Never present a figure you haven't inspected** — save it to disk, inspect it, then decide whether to use it. An inline-only plot (e.g., `plt.show()` in a notebook without `plt.savefig()`) is invisible to the agent and cannot back a claim.
