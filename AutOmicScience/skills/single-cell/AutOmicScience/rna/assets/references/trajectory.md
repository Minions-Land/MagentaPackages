# scRNA-seq Trajectory, RNA Velocity & Fate

**Maturity: REFERENCE** — no compute subcommand; run the recipes below in a Python script, emit a
`report` dict and `print(report)` to stay grounded.

**What is already in the pinned `task1` env:** `scvelo` 0.3.4, `cellrank` 2.3.2 — no install needed.
**What you install for the task:** `monocle3-python`, `monocle2-python`, `tradeSeq-python`.

## Goal / When to Use

Use trajectory analysis when cells form a **continuum** (differentiation, activation, a developmental
axis) and you want to order them or infer direction. Do **not** reach for it when the biology is a
set of discrete, stable cell types — forcing a trajectory onto islands produces a confident-looking
artifact.

Two questions gate everything:
1. **Is a trajectory even supported?** If the cells fall into disconnected partitions, there is no
   single trajectory; abstain (§1 makes this check explicit).
2. **What is the root?** Pseudotime is meaningless without a biologically justified start (the
   stem/progenitor population). Never let a tool pick an arbitrary root.

## Decision Criteria

- **Ordering + branching topology → Monocle3** (§1). `learn_graph` fits a principal graph (SimplePPT)
  over the UMAP and `order_cells` projects pseudotime onto it. Unlike a diffusion pseudotime, the
  graph itself is the model: branch points are explicit objects you can test against.
- **Direction → scVelo** (§2), and only if `spliced`/`unspliced` layers exist. A standard Cell Ranger
  `filtered_feature_bc_matrix` does **not** have them. Pseudotime has no inherent direction; velocity
  is the only thing here that supplies it.
- **Fate probabilities → CellRank** (§3). Only after velocity is computed and its confidence is
  acceptable. It turns the velocity field into terminal states and per-cell fate probabilities.
- **Genes that change along the trajectory → tradeSeq** (§4a) for lineage-resolved NB-GAM tests, or
  **Monocle3 `graph_test`** (§4b) for a fast graph-autocorrelation screen.
- **Monocle2 only for BEAM** (§4c). Monocle3 supersedes Monocle2 for ordering — Monocle2's DDRTree
  forces the data onto a tree and scales poorly. Reach for `monocle2-python` when you specifically
  want **BEAM** (branch-dependent DE at a chosen branch point), which Monocle3 does not provide.

## 1. Topology + pseudotime — Monocle3

```bash
pip install monocle3-python
```

```python
import monocle3 as m3

m3.estimate_size_factors(adata)                 # REQUIRED before preprocess_cds
m3.preprocess_cds(adata, num_dim=50)            # size-factor norm + truncated PCA
m3.align_cds(adata, alignment_group="batch")    # only if batches need aligning
m3.reduce_dimension(adata)                      # UMAP
m3.cluster_cells(adata)                         # Leiden + partitions
m3.learn_graph(adata, use_partition=True)       # principal graph (SimplePPT)

# Root MUST be chosen biologically. order_cells raises if you omit it.
root = adata.obs_names[adata.obs["cell_type"] == "HSC"][:1].tolist()
m3.order_cells(adata, root_cells=root)          # writes obs["monocle3_pseudotime"]

m3.plot_cells(adata, color_cells_by="pseudotime", show_trajectory_graph=True)
```

`estimate_size_factors` is **not optional on your own data** — `preprocess_cds` raises
`ValueError: Call estimate_size_factors before preprocess_cds`. (The package's bundled demo datasets
arrive with size factors already set, so quickstarts appear to skip it.)

**The abstention gate is `obs["monocle3_partitions"]`.** `cluster_cells` assigns partitions —
groups of cells the kNN graph says are disconnected. With `use_partition=True` (the default),
`learn_graph` fits a **separate principal graph per partition**, so cells in different partitions
are never ordered onto one trajectory. If your progenitors and your putative endpoint land in
different partitions, that is the data telling you there is no continuum between them: report it and
stop, rather than forcing `use_partition=False`.

**Root:** pass `root_cells` (cell barcodes) or `root_pr_nodes` (principal-graph vertex names, e.g.
`["Y_1"]`). `order_cells` **raises `ValueError: Provide root_pr_nodes or root_cells`** if you give
neither — it will not invent a root. Choose from progenitor markers or study design, and report the
choice.

**Pseudotime is `inf` for cells the root cannot reach** — i.e. cells in another partition. That is
not a bug; it is the abstention gate showing up numerically. Always check and filter:

```python
import numpy as np
reachable = np.isfinite(adata.obs["monocle3_pseudotime"])
# report reachable.sum() vs adata.n_obs; anything downstream must use only reachable cells
```

## 2. RNA velocity — scVelo (pinned env, no install)

```python
import scvelo as scv

# Gate on the data: skip this whole block if the layers are absent.
assert {"spliced", "unspliced"} <= set(adata.layers), \
    "no spliced/unspliced layers — skip velocity, report pseudotime only"

scv.pp.filter_and_normalize(adata, min_shared_counts=30, n_top_genes=2000)
scv.pp.moments(adata, n_pcs=30, n_neighbors=30)
scv.tl.recover_dynamics(adata, n_jobs=8)   # dynamical model fit
scv.tl.velocity(adata, mode="dynamical")
scv.tl.velocity_graph(adata)
scv.tl.velocity_confidence(adata)          # adata.obs["velocity_confidence"]

scv.pl.velocity_embedding_stream(adata, basis="umap", color="cell_type",
                                 show=False, save="_velocity_stream.png")
# Sanity-check direction on known markers (phase portraits):
scv.pl.velocity(adata, var_names=["CD34", "MPO", "HBB"], show=False, save="_phase.png")
```

Use `mode="dynamical"` (full kinetics) over `stochastic`: it is slower, but the steady-state
assumption fails exactly on the transient populations a trajectory is about.

## 3. Fate probabilities — CellRank (pinned env, no install)

```python
import cellrank as cr

vk = cr.kernels.VelocityKernel(adata)
vk.compute_transition_matrix()
ck = cr.kernels.ConnectivityKernel(adata)
ck.compute_transition_matrix()
combined = 0.8 * vk + 0.2 * ck             # velocity-led, connectivity-smoothed

g = cr.estimators.GPCCA(combined)
g.fit(cluster_key="cell_type")             # coarse-grains into macrostates
g.predict_terminal_states()
g.compute_fate_probabilities()             # adata.obsm["lineages_fwd"]
```

## 4. Genes that change along the trajectory

### (a) tradeSeq — lineage-resolved NB-GAM (the rigorous path)

```bash
pip install tradeSeq-python
```

tradeSeq fits a negative-binomial GAM per gene per lineage, so it needs **raw counts** and a
**per-lineage** description of the trajectory — not a single pseudotime column:

- `adata.layers["counts"]` — raw counts (our canonical layout already has this)
- `adata.obsm["pseudotime"]` — shape `(n_obs, n_lineages)`
- `adata.obsm["cell_weights"]` — shape `(n_obs, n_lineages)`, each cell's weight in each lineage

**Deriving the lineages from Monocle3 (§1).** tradeSeq infers nothing itself — it raises
`adata.obsm has no key 'pseudotime'` if handed a bare trajectory. Monocle3's principal graph already
contains the lineages: each **leaf** of the graph is the endpoint of one lineage, and the path
root→leaf is the lineage itself.

```python
import numpy as np, tradeseq as ts

aux = adata.uns["monocle3"]["principal_graph_aux"]["UMAP"]
g   = adata.uns["monocle3"]["principal_graph"]["UMAP"]        # igraph.Graph
root_idx = g.vs.find(name=list(aux["root_pr_nodes"])[0]).index

# One lineage per leaf: the vertex path root -> leaf
leaves = [v.index for v in g.vs if g.degree(v.index) == 1 and v.index != root_idx]
paths  = [set(g.get_shortest_paths(root_idx, to=l)[0]) for l in leaves]
paths  = [p for p in paths if p]                    # drop leaves unreachable from the root

# Each cell sits at its closest principal-graph vertex. V1 is 1-based (R convention).
cell_v = aux["pr_graph_cell_proj_closest_vertex"]["V1"].to_numpy() - 1
pt1    = adata.obs["monocle3_pseudotime"].to_numpy()

cell_weights = np.zeros((adata.n_obs, len(paths)))
for j, p in enumerate(paths):
    cell_weights[:, j] = np.isin(cell_v, sorted(p)).astype(float)
pseudotime = np.where(cell_weights > 0, pt1[:, None], 0.0)

keep = np.isfinite(pt1) & (cell_weights.sum(1) > 0)  # drop unreachable / off-graph cells
sub  = adata[keep].copy()
sub.obsm["pseudotime"]   = pseudotime[keep]
sub.obsm["cell_weights"] = cell_weights[keep]
```

Cells on the trunk lie on **every** root→leaf path, so they get weight 1 in each lineage; cells past
a branch point get weight 1 in one. That is the shape tradeSeq expects — shared progenitors,
divergent tips. Report `keep.sum()` vs `adata.n_obs`: cells dropped here are cells the root could not
reach, and silently losing them would overstate the trajectory's coverage.

```python
ts.fit_gam(sub, n_knots=6, layer="counts")          # NB-GAM per gene, per lineage

assoc = ts.association_test(sub)       # does expression change along pseudotime, within a lineage?
start = ts.start_vs_end_test(sub)      # progenitor vs endpoint markers
diff  = ts.diff_end_test(sub)          # do lineages end in different states?
patt  = ts.pattern_test(sub)           # do lineages follow different trajectories?
early = ts.early_de_test(sub, knots=(1, 2))         # early drivers of the branch
# each returns a DataFrame: waldStat / df / pvalue / meanLogFC

ts.plot_smoothers(sub, gene=start["waldStat"].idxmax())
```

Pick `n_knots` with `ts.evaluate_k(...)` rather than accepting 6 blindly — too many knots fits noise,
too few flattens real dynamics.

> **These weights are hard (0/1), not soft.** A cell is either on a lineage's path or it is not,
> whereas a curve-fitting upstream would give each cell a graded weight per lineage. Near a branch
> point the assignment is therefore abrupt where the biology is gradual, which makes `pattern_test`
> and `early_de_test` — the two tests that hinge on exactly that region — the most sensitive to the
> ordering. Report which upstream produced the lineages next to any tradeSeq result: the p-values are
> conditional on it.

> **Monocle2 (§4c) cannot feed this directly.** It builds its own `cds` and DDRTree ordering with no
> principal-graph vertex mapping of this shape; its branch analysis is BEAM, not tradeSeq. Use one or
> the other per question — do not mix a Monocle2 ordering with tradeSeq's lineage matrices.

### (b) Monocle3 `graph_test` — fast screen

```python
res = m3.graph_test(adata, neighbor_graph="principal_graph", cores=8)
# columns: status, p_value, morans_I, q_value  — rank by morans_I, filter q_value
```

`neighbor_graph="principal_graph"` tests autocorrelation **along the learned trajectory** (what you
want here); `"knn"` tests it over the kNN graph instead (a general spatial-autocorrelation screen,
closer to "is this gene locally structured at all"). This is a screen, not a lineage-resolved model:
it says "this gene varies over the graph", not "this gene diverges between branch A and branch B".

### (c) Monocle2 `beam` — branch-dependent DE

```bash
pip install monocle2-python
```

**Preprocessing depends on what your matrix measures — this is the one Monocle2 decision you cannot
skip.** Monocle2 models expression with an explicit `expression_family`, and the right family is
determined by the assay, not by preference:

| Your matrix | `expression_family` | Why |
|---|---|---|
| **UMI counts** (10x, Drop-seq) | `m2.negbinomial_size()` | UMIs are absolute transcript counts; NB with a size parameter is the generative model. |
| **FPKM / TPM** (SMART-seq2, bulk-like full-length) | **Census first** (`m2.relative2abs`), then `m2.negbinomial_size()` | FPKM is *relative* — it says nothing about how many transcripts a cell held. Census converts relative → estimated absolute transcript counts so the NB model applies. |
| FPKM / TPM, without converting | `m2.tobit(Lower=0.1)` | Monocle2's classic censored-normal path for relative values. Works, but downstream tests are weaker than the Census route. |
| log-transformed FPKM | `m2.gaussian_family()` | Already on a roughly-normal scale; do **not** stack a count model on top of a log. |

Giving UMI counts to `tobit()`, or raw FPKM to `negbinomial_size()`, does not error — it silently
fits the wrong noise model and every downstream p-value inherits it.

```python
import monocle2py as m2
import pandas as pd

# feature_data must carry a 'gene_short_name' column, or plotting/BEAM helpers warn and misbehave.
var = pd.DataFrame({"gene_short_name": gene_names}, index=gene_names)

# --- UMI path ---
cds = m2.new_cell_dataset(counts, pheno_data=obs, feature_data=var,
                          expression_family=m2.negbinomial_size())

# --- FPKM/TPM path: Census, then the same NB family ---
# abs_counts = m2.relative2abs(rel_adata, method="num_genes")   # expected_capture_rate=0.25 prior
# cds = m2.new_cell_dataset(abs_counts, pheno_data=obs, feature_data=var,
#                           expression_family=m2.negbinomial_size())

m2.estimate_size_factors(cds); m2.estimate_dispersions(cds)
m2.reduce_dimension(cds, reduction_method="DDRTree")
m2.order_cells(cds)
res = m2.beam(cds, branch_point=1)          # genes whose kinetics depend on the branch
m2.plot_genes_branched_heatmap(cds, branch_point=1)
```

`relative2abs` assumes `expected_capture_rate=0.25` — a prior, not a measurement. Census output is an
*estimate* of transcript counts; report that the absolute numbers are model-derived.

Use Monocle2 **only** for BEAM. It needs its own `cds` and its own DDRTree ordering — it does not
read Monocle3's graph — so this is a second, parallel trajectory fit. If BEAM's branch disagrees with
Monocle3's, that is a real finding about ordering instability, not a bug to hide.

## 5. Emit the report and ground it

```python
report = {
    "method": "monocle3",                          # + scvelo/cellrank/tradeseq if run
    "n_cells_reachable_from_root": int(np.isfinite(adata.obs["monocle3_pseudotime"]).sum()),
    "root_cells": root,
    "n_cells": int(adata.n_obs),
    "n_partitions": int(adata.obs["monocle3_partitions"].nunique()),
    "pseudotime_range": [float(adata.obs["monocle3_pseudotime"].min()),
                         float(adata.obs["monocle3_pseudotime"].max())],
    # include only if velocity ran:
    "velocity_mode": "dynamical",
    "mean_velocity_confidence": float(adata.obs["velocity_confidence"].mean()),
    "terminal_states": sorted(map(str, g.terminal_states.cat.categories)),
}
report
```

`print(report)`. Drop the `velocity_*`/`terminal_states` keys when velocity was not run. Record
**`n_partitions`** always — it is the evidence that a single trajectory was defensible.

## Failure Modes

1. **`ValueError: Provide root_pr_nodes or root_cells`** — *symptom:* `order_cells` raises.
   *Diagnosis:* Monocle3 refuses to guess a root. *Fix:* pass one, chosen from progenitor markers.
   This is the tool being correct; do not work around it.

2. **Cells in different partitions.** *Symptom:* `monocle3_partitions` has several levels and
   pseudotime is only defined within each. *Diagnosis:* the kNN graph says these groups are not
   connected. *Fix:* report that there is no single trajectory. `use_partition=False` will force one
   graph over everything and produce a fabricated ordering — don't.

3. **No spliced/unspliced layers** — *symptom:* the assert in §2 fires. *Diagnosis:* the matrix came
   from Cell Ranger `filtered_feature_bc_matrix`, which has no nascent counts. *Fix:* re-quantify
   with velocyto or kb-python, or skip velocity and report pseudotime only, stating the limitation.

4. **Velocity arrows point backward or scatter randomly** — *symptom:* stream plot disagrees with
   known biology; `velocity_confidence` low. *Diagnosis:* steady-state assumption wrong, low depth,
   or cell cycle dominating. *Fix:* use `mode="dynamical"`, inspect phase portraits for key markers,
   score/regress cell cycle; if confidence stays low, drop velocity and report pseudotime only.

5. **Pseudotime contradicts known biology** — *symptom:* mature cells get low pseudotime.
   *Diagnosis:* wrong root, or no real continuum. *Fix:* re-pick the root; check partitions.

6. **`adata.obsm has no key 'pseudotime'` from `fit_gam`** — *symptom:* tradeSeq raises immediately.
   *Diagnosis:* you passed a trajectory but not the `(n_obs, n_lineages)` pseudotime/weights matrices
   it requires. *Fix:* build them from an upstream lineage model (§4a) — a single `obs` pseudotime
   column is not a substitute.

7. **`RuntimeError: Parametric dispersion fit failed: extraPois < 0`** — *symptom:* Monocle2's
   `estimate_dispersions` raises. *Diagnosis:* the matrix is not overdispersed the way the NB model
   expects — usually the wrong `expression_family` for the assay (§4c), or a matrix that was already
   normalized/log-transformed. *Fix:* re-check what the matrix measures and pick the family from the
   table; do not lower the detection threshold until the model matches the assay.

8. **CellRank reports too many terminal states** — *symptom:* more terminal macrostates than
   plausible endpoints. *Diagnosis:* over-clustering or noisy velocity. *Fix:* coarsen `cluster_key`,
   validate each terminal state with markers, discard the spurious ones.

## Figure checkpoints

Inspect each before it backs a claim:
1. **`plot_cells(color_cells_by="partition")`** — one partition spanning the biology, or several
   islands (islands ⇒ no single trajectory).
2. **`plot_cells(color_cells_by="pseudotime", show_trajectory_graph=True)`** — smooth gradient
   emanating from the root, and a principal graph that follows the cells rather than cutting across
   empty space.
3. **Velocity stream** — flow consistent with known differentiation direction.
4. **Phase portraits** (`scv.pl.velocity`) — clean up/down-regulation arcs for marker genes; flat
   clouds ⇒ unreliable velocity.
5. **`ts.plot_smoothers`** for top tradeSeq hits — does the fitted smoother track the data, or is it
   chasing a handful of high-count cells?
6. **Fate probabilities** — each terminal state is a real, marker-supported endpoint.

## Honesty / when to abstain

- **No continuum → no trajectory.** If partitions are disconnected, say so and stop; do not impose
  pseudotime on stable cell types.
- **State the root and that it is a choice.** Pseudotime is relative to the root you picked; report
  which population and why.
- **Pseudotime has no direction.** If velocity was not run, never narrate "A becomes B" — the
  ordering is symmetric until something breaks the tie.
- **Report the upstream of any tradeSeq result.** Its tests are conditional on the lineage model that
  produced `pseudotime`/`cell_weights`; a different upstream can change every p-value.
- **Low velocity confidence is a result, not a nuisance.** Report mean confidence; if it is low
  across the manifold, present velocity as inconclusive rather than narrating arrows.
- **Cycling/stressed cells confound velocity.** Flag this when the population includes proliferating
  cells.
- **Two trajectory fits that disagree is a finding.** Monocle3 and Monocle2/DDRTree optimize
  different objectives; if their branch structure conflicts, report the instability rather than
  picking the prettier one.
