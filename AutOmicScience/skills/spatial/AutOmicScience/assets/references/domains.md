# Spatial Domains

**Maturity: PARTIAL** — spatial domain detection. The opinionated default (**SpaGCN**) is not in `task2`; provision it into its own env per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` (that doc uses SpaGCN as its worked example). Never bare-`pip install`, and do not add it to `task2`. The **runnable baseline** (Leiden + majority-vote smoothing on the squidpy spatial graph) needs only the pinned stack and is verified to run on it. SpaGCN API verified against `jianhuupenn/SpaGCN` rev `dc7a1c2`; baseline verified against squidpy 1.8.1.

> **Pin note.** The baseline builds its graph with `sq.gr.spatial_neighbors`, which is the API in the pinned squidpy 1.8.1. Upstream removes it in **1.9.0** in favour of `spatial_neighbors_knn`/`_radius`/`_delaunay`/`_grid` — names that **do not exist in 1.8.1**. `pixi.toml` pins `squidpy = ">=1.8,<1.9"`; do not "modernise" the call.

## Goal / When to Use

Partition the tissue into **coherent spatial domains** (anatomical/functional regions) — groups of spots/cells that are both transcriptionally similar AND spatially contiguous. Distinct from plain expression clustering, which ignores location and shreds domains.

## Decision Criteria — pick one default

- **Default: SpaGCN** — a graph-convolutional method that fuses expression, spatial position, **and the H&E histology image** into smooth, contiguous domains. The right choice for Visium with histology. Needs install (PyTorch; the adjacency build is O(n²) — heavy for very large slides).
- **Runnable baseline: expression Leiden + spatial smoothing** — when SpaGCN isn't available or there's no histology. Simpler and runs today, but tends to over-fragment without the spatial term.

## How-to (default — SpaGCN)

```python
import SpaGCN as spg
import scanpy as sc

# adata.obs has array coords (x_array/y_array) and pixel coords (x_pixel/y_pixel); img = H&E array
adj = spg.calculate_adj_matrix(x=x_pixel, y=y_pixel, x_pixel=x_pixel, y_pixel=y_pixel,
                               image=img, beta=49, alpha=1, histology=True)   # fuses RGB + space
spg.prefilter_genes(adata, min_cells=3); spg.prefilter_specialgenes(adata)

# min_counts=0 is load-bearing. sc.pp.normalize_per_cell FILTERS as well as normalizes — its
# default min_counts=1 silently drops spots that gene-prefiltering zeroed out, after `adj` was
# built over ALL spots. SpaGCN then asserts adata.shape[0] == adj.shape[0] and dies with a bare
# AssertionError. (Upstream's own multi-sample tutorial passes min_counts=0 for this reason;
# its single-sample section does not, which is where this trap comes from.)
sc.pp.normalize_per_cell(adata, min_counts=0); sc.pp.log1p(adata)
# ^ normalize_per_cell is deprecated in scanpy (use normalize_total) but SpaGCN's own tutorial
#   and ez_mode use it. Keep it here for fidelity to upstream; note normalize_total has no
#   min_counts arg, so switching also removes the filtering side effect above.

l   = spg.search_l(p=0.5, adj=adj)                       # see the p note below
res = spg.search_res(adata, adj, l, target_num=7)        # resolution to hit ~7 domains (set from anatomy)

clf = spg.SpaGCN(); clf.set_l(l)                         # set_l is mandatory before train
clf.train(adata, adj, init="louvain", res=res)
adata.obs["domain"], _ = clf.predict()                   # predict() returns (labels, probs); it does not write adata
adata.obs["domain"] = adata.obs["domain"].astype("category")
```

Parameter rationale:
- `histology=True`, `beta=49`, `alpha=1` — fuse the H&E image (49-pixel window per spot, equal weight to space vs color); use `histology=False` (x/y only) when there's no usable image.
- `p=0.5` in `search_l` — **not a percentage**, despite upstream's own docs calling it one. `calculate_p` returns `mean(sum(adj_exp, 1)) - 1`, i.e. total *neighbour* weight against a self-weight of 1, and it is unbounded (upstream's tutorial prints values up to ~154). `p=0.5` means the neighbourhood carries half as much weight as the spot itself — 0.5/1.5 = **33%** of the total, not 50%. Raise it for more smoothing.
- `target_num=7` — set the expected domain count from the tissue's anatomy, not arbitrarily.
- `x=x_pixel, y=y_pixel` in `calculate_adj_matrix` is correct (upstream passes pixel coords here). Array coords are needed only by `spg.refine` — see Failure Modes.

**Runnable baseline (no SpaGCN).** The smoothing step is what makes this a *domain* method — expression Leiden alone is not a spatial segmentation, and stopping before the smoothing leaves you with exactly the thing this doc's Honesty section tells you not to call a domain map.

```python
import numpy as np, pandas as pd, scanpy as sc, squidpy as sq
from scipy import sparse

# 1. Expression clusters. sc.pp.pca is REQUIRED: use_rep="X_pca" with no PCA raises
#    ValueError: Did not find X_pca in `.obsm.keys()`. You need to compute it first.
sc.pp.normalize_total(adata); sc.pp.log1p(adata)
sc.pp.pca(adata, n_comps=30)
sc.pp.neighbors(adata, use_rep="X_pca")
sc.tl.leiden(adata, resolution=1.0, key_added="leiden", flavor="igraph", n_iterations=2)

# 2. Spatial graph (coord_type="grid" for Visium hex; "generic" for imaging)
sq.gr.spatial_neighbors(adata, coord_type="grid", n_neighs=6)

# 3. Majority-vote each spot's label over its spatial neighbours + itself, a few rounds.
#    One-hot @ adjacency is the vectorised form of the vote — identical result to a per-spot
#    loop, but it stays fast at 50k spots.
codes = adata.obs["leiden"].cat.codes.to_numpy()
k = int(codes.max()) + 1
W = adata.obsp["spatial_connectivities"] + sparse.eye(adata.n_obs, format="csr")   # +self
labels = codes.copy()
for _ in range(3):                       # 3 rounds is usually enough; more = smoother, blunter
    votes = W @ np.eye(k, dtype=np.float32)[labels]
    labels = np.asarray(votes.argmax(axis=1)).ravel()

adata.obs["domain"] = pd.Categorical(labels.astype(str))
```

On a synthetic slide with two true regions this lifts ARI from 0.594 (raw Leiden) to 0.621 — a real but modest gain. That gap is the honest scale of what smoothing buys you: it cleans speckle, it does not discover structure the expression clusters missed. If you need the histology term, that is SpaGCN's whole point.

## Failure Modes

- **Domains are salt-and-pepper, not contiguous** — *symptom:* speckled labels. *Diagnosis:* spatial smoothing too weak (baseline: too few rounds) or wrong `l`. *Fix:* more smoothing rounds, raise `p`, or use SpaGCN with histology.
- **`spg.refine` refines on the wrong geometry** — *symptom:* refinement makes domains worse. *Diagnosis:* `refine(sample_id, pred, dis, shape="hexagon")` expects `dis` to be a **non-histology, array-coordinate** adjacency — `spg.calculate_adj_matrix(x=x_array, y=y_array, histology=False)` — not the histology-fused `adj` used for training. *Fix:* build a second `adj_2d` from the array coords and pass that.
- **Wrong number of domains** — *symptom:* one giant + many tiny. *Diagnosis:* `target_num`/resolution off. *Fix:* set `target_num` from anatomy; re-run `search_res`.
- **AssertionError inside `clf.train`** — *symptom:* bare `assert adata.shape[0]==adj.shape[0]`. *Diagnosis:* a preprocessing step dropped spots after `adj` was built. *Fix:* `normalize_per_cell(..., min_counts=0)`, and rebuild `adj` if you filter spots for any other reason.
- **SpaGCN dies on a large slide** — *symptom:* `MemoryError` in `calculate_adj_matrix` (it is `numba.njit(parallel=True)`, so it does not hang — it allocates). *Diagnosis:* the adjacency is a dense `n×n` float32: 50k spots ≈ 10 GB. *Fix:* bin/subset, or use the baseline above.

## Figure checkpoints

1. **Domains in space** (`sq.pl.spatial_scatter(adata, color="domain")`) — contiguous regions matching tissue architecture, or scattered noise?
2. **Domains vs H&E** — overlay on the histology; do boundaries follow real anatomical structure?

## Grounding

Record: method (SpaGCN / Leiden-spatial), n_domains, key params (`l`, `res`, `target_num`, histology used), domain sizes → put these in a `report` dict and cite its numbers.

## Honesty

- **Domains are hypotheses about tissue architecture** — validate against histology/known anatomy before naming them.
- **Expression clustering ≠ spatial domains** — if you used plain Leiden without spatial smoothing, say so; the result is not a spatial-domain segmentation.
- If domains don't match the histology, **flag it** rather than over-interpreting speckled clusters.
