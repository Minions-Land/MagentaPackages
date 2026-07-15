# Read Spatial Data

**Maturity: READY** — `omics_compute(subcommand="read_spatial", modality="spatial", ...)` dispatches the loader and returns a `report` dict — cite its numbers.

Two caveats before you pick a path:

- The grounded subcommand implements **three** loaders itself: `visium` (via scanpy), `xenium`
  (cell_feature_matrix.h5 + cells table), and `merfish` — where `merfish` is a **generic per-cell
  CSV reader**, not a Vizgen-format-aware reader. Point it at any layout with
  `counts-file` / `metadata-file` / `cell-id-col` / `x-col` / `y-col` (see the MERSCOPE example
  below).
- The `spatialdata_io` readers listed under Method Menu are a **hand-rolled REFERENCE path** and
  `spatialdata_io` is **not installed** in the pinned envs (only `spatialdata`); install it before
  using them.

## Goal / When to Use

Load any spatial format into the canonical containers (AnnData / SpatialData) and verify coordinates before any analysis. Use when starting with a spatial sample.

## Decision Criteria

**The judgment this guides:**

- **Container choice** — Use plain **`AnnData`** (coords in `obsm["spatial"]`) when the question is expression/cluster/stat-centric and you don't need the registered image/transcript/segmentation layers. Use **`SpatialData`** when you need image overlays at native resolution, transcript points, segmentation polygons, multiple coordinate systems, Visium HD bins, or you will aggregate transcripts/channels into a table. You can always derive an AnnData view from a SpatialData table and write results back.

- **Platform detection** — Visium (spaceranger dir), Visium HD (bins at multiple resolutions), Xenium, MERFISH/MERSCOPE, CosMx, Stereo-seq, or generic `.h5ad` with coords. Choose the loader by what the data *is*, not by what you wish it were.

## Method Menu

**By platform:**
- **Visium** — `squidpy.read.visium(path)` for a spaceranger output directory, or `spatialdata_io.visium(path)` for a SpatialData container
- **Visium HD** — `spatialdata_io.visium_hd(path)` (bins at 2/8/16 µm)
- **Xenium** — `spatialdata_io.xenium(path)`
- **MERFISH/MERSCOPE** — `spatialdata_io.merscope(path)`
- **CosMx** — `spatialdata_io.cosmx(path)`
- **Stereo-seq** — `spatialdata_io.stereoseq(path)`
- **Generic `.h5ad` with coords** — `anndata.read_h5ad(path)`, then validate `obsm["spatial"]` is present

**Grounded subcommand:** `omics_compute(subcommand="read_spatial", modality="spatial", args={"input": ..., "output": ..., "platform": "visium"|"xenium"|"merfish"})` dispatches the loader, sets `layers['counts']`, and returns a `report` (platform, n_obs, n_vars, coordinate_range, id_overlap). Coordinates must be finite, and counts/metadata IDs must overlap — a largely-disjoint pair fails loud rather than silently truncating to the shared cells.

`platform="merfish"` is a **generic per-cell CSV** reader; give it the real file/column names.
For a standard Vizgen MERSCOPE directory:

```python
omics_compute(subcommand="read_spatial", modality="spatial", args={
    "input": "merscope_out/", "output": "spatial.h5ad", "platform": "merfish",
    "counts-file": "cell_by_gene.csv", "metadata-file": "cell_metadata.csv",
    "cell-id-col": "EntityID", "x-col": "center_x", "y-col": "center_y",
})
```

For a platform outside those three, hand-roll with a `spatialdata_io` reader (install it first —
it is not in the pinned envs).

## How-to

### Via the grounded subcommand (preferred for AnnData output)

```
omics_compute(subcommand="read_spatial", modality="spatial",
              args={"input": "/path/to/spaceranger_output",
                    "output": "spatial.h5ad", "platform": "visium"})
```

Returns `{platform, n_obs, n_vars, coordinate_range}`; cite those numbers. To call a
platform loader directly in a hand-written cell (e.g. to tweak reader parameters),
import it from the package runtime:

```python
import os, sys
sys.path.insert(0, os.environ.get("AOSE_OMICS_PYTHON_DIR") or "tools/omics-compute/python")
from aose_omics_runtime.spatial.read_spatial import load_visium  # or load_xenium, load_merfish

adata, report = load_visium(path="/path/to/spaceranger_output")
print(f"Loaded {report['n_obs']} obs x {report['n_vars']} vars; coords {report['coordinate_range']}")
```

### For image/segmentation work (SpatialData)

```python
import spatialdata_io as sdio

# Read into SpatialData
sdata = sdio.xenium("/path/to/xenium_output")

# Inspect elements
print(sdata)  # shows images, labels, points, shapes, tables

# Extract the AnnData table
adata = sdata.tables['table']  # Xenium typically names it 'table'

# Or validate an existing spatial AnnData
from aose_omics_runtime.spatial.read_spatial import validate_spatial_adata
report = validate_spatial_adata(adata, require_counts=True)
```

### Coordinate validation

```python
# After load, verify spatial coords are sane
import matplotlib.pyplot as plt
import squidpy as sq

sq.pl.spatial_scatter(
    adata,
    color='total_counts',
    figsize=(6, 6),
    save='_spatial_qc_counts.png'
)
# inspect the figure: is a tissue outline visible? or just noise/empty?
```

## Pitfalls & Quality Checks

- **Coordinate units differ per platform** — Visium is in array coordinates (row, col), Xenium/MERFISH/CosMx are in microns, Stereo-seq is in bin IDs. Never assume — check `obsm['spatial'].min()`, `.max()` and plot it.

- **Visium HD at 2 µm bins is NOT single-cell** — bin to 8/16 µm or treat as spots (multi-cell aggregates). Don't run single-cell annotation on 2 µm bins as if they were cells.

- **Imaging panels are targeted** (hundreds of genes, not whole transcriptome) — HVG/marker logic that assumes 20K genes will mislead. Methods like gene activity or imputation that expect broad coverage will fail or give garbage.

- **Control/blank probes in imaging data must be filtered before QC** — Xenium/MERFISH/CosMx include negative-control probes (named `NegControl*`, `BLANK*`, etc.) for QC purposes; these are not real genes and will poison downstream analysis if not removed. The loaders do **not** strip them — filter by var-name prefix right after load, e.g. `adata = adata[:, ~adata.var_names.str.startswith(("NegControl", "BLANK", "antisense", "UnassignedCodeword"))].copy()`.

- **Inspect the figure** — a spatial scatter of `total_counts`: is a tissue outline visible, or is it uniform noise? An empty/garbled spatial plot signals wrong platform, missing coords, or a load failure.

## Grounding

**What to record** (from the helper `report`):

```python
{
  "platform": "visium",
  "n_obs": 3500,
  "n_vars": 18000,
  "coordinate_range": {"x_min": 0.0, "x_max": 127.0, "y_min": 0.0, "y_max": 127.0}
  # plus platform-specific fields (e.g. n_in_tissue for Visium)
}
```

Ground: n obs/vars, the coordinate range, and the detected platform.

## Honesty

- If a format/version is **unsupported by the available readers**, surface the blocker (preflight should catch this) — do not hand-roll a brittle parser that silently mis-loads.

- If the input path is missing or malformed, **fail loud** — the helper raises `FileNotFoundError` with the expected layout for that platform.

- If `obsm['spatial']` is absent or its dimensionality is wrong (not 2D or 3D), **raise** — do not fabricate coordinates.

- **Pairing (multiome / multi-modal)** — if the data is described as "spatial transcriptomics + protein" or similar, note that the load step here only brings in the RNA/peak matrix; the protein/ADT modality is a separate load.
