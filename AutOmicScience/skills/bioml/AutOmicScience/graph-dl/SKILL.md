---
name: bioml-graph-dl
disable-model-invocation: true
---

# BioML Graph & Geometric Deep Learning — GNNs on biological graphs

> Subskill of `bioml`. Enter here from the parent skill when the method is a **graph neural network** or a **geometric / 3D-structure** model. Read the parent (`../SKILL.md`) and the always-loaded `omics-shared` skill first — their ML-engineering foundations and evidence rules apply here.

This subskill covers the **graph-DL engineering layer** — the reusable machinery underneath a large family of biological DL methods:

- **Transductive node classification** on biological networks (gene/protein interaction + regulatory graphs) — e.g. predicting gene labels from multi-omics node features.
- **Graph autoencoders** for spatial-omics domain identification — the STAGATE / GraphST / SpatialGlue / MultiGATE family (spatial graph → latent embedding → domains).
- **Geometric / 3D GNNs** for structure→property tasks (protein–DNA binding, molecular/point-cloud regression) and cell-mesh models.

Built on **PyTorch Geometric (PyG)** — the standard library these methods use. This is the *how-to-build-and-train-the-GNN* layer; the spatial-analysis workflow that *calls* it lives in `../../../spatial/AutOmicScience/` and `../../../single-cell/AutOmicScience/`.

---

## When to use

- The method's core is a **GNN / message-passing network** (node/edge/graph prediction), a **graph autoencoder**, or a **geometric model over 3D coordinates / a mesh**.
- You need to **build a graph** from non-graph data (spatial coordinates, molecular structure, a cell mesh, an interaction network) and train a model on it.

**Skip this path** for standard scanpy analysis (`../../../single-cell/AutOmicScience/`, `../../../spatial/AutOmicScience/`), for sequence foundation models (`../sequence-fm/`), or for single-cell VAE/FM reproduction (`../deep-models/`). As always, first check whether the paper's own repo runs (`../repro/`) before reimplementing a bespoke GNN.

---

## The library

**PyTorch Geometric (PyG) ≥ 2.8** (recipes checked against **2.8.0** — the latest *released* tag).
> Earlier text here claimed verification against **2.9.0**. That version exists only on upstream's
> `master` and has never been released, so the claim could not have been true — and the `to_hetero`
> recipe below in fact fails on both 2.8 and 2.9. Treat these snippets as source-checked, not executed.
**Maturity: PARTIAL.** `torch_geometric` is in **no** pinned env (`torch` is; PyG is not), so nothing
below runs until you provision it. The install must match your torch/CUDA build, which is exactly the
case `AOSE_nonStandard_env.md` calls §B — a **named** conda env when Pixi can't solve a CUDA stack:

```bash
# §A first — try Pixi (works when you don't need a specific CUDA build):
#   [feature.pyg.pypi-dependencies]  torch_geometric = "*"
#   [environments]  pyg = { features = ["core", "singlecell", "pyg"], solve-group = "pyg" }
#
# §B — named conda env when the CUDA build must be pinned. NEVER base, never a bare pip:
conda create -y -n aose-pyg -c conda-forge -c nvidia python=3.11 pytorch pytorch-cuda=12.1
conda run -n aose-pyg pip install torch_geometric
# PyG 2.8 routes knn_graph / radius_graph through pyg-lib (torch-cluster deprecated in 2.8.0, #10682):
conda run -n aose-pyg pip install pyg-lib -f https://data.pyg.org/whl/torch-${TORCH}+${CUDA}.html
conda run -n aose-pyg pip install e3nn    # only for true SE(3)/O(3) equivariance (see geometric doc)
```

A bare `pip install torch_geometric` resolves against whatever `python` leads `$PATH` — often conda
`base` — and a PyG wheel drags its own torch pin with it, so this is a realistic way to downgrade the
`torch` that `task1–4` are locked to. A §B env is not in `pixi.lock`, so record the exact versions in
the `report`.

---

## Capability Menu

| Capability | Maturity | PyG entry point | Reference Doc |
|------------|----------|-----------------|---------------|
| Build a graph (coords / structure / mesh / network) | **PARTIAL** | `Data`/`HeteroData`, `T.KNNGraph`/`RadiusGraph`/`Delaunay`, `knn_graph`/`radius_graph` | `assets/references/graph_construction.md` |
| Transductive node classification (incl. hetero, imbalanced/AUPRC) | **PARTIAL** | `GCNConv`/`GATConv`/`SAGEConv`/`GINConv`, `to_hetero` | `assets/references/node_classification.md` |
| Scaling to large / dense-adjacency graphs | **PARTIAL** | `NeighborLoader`, `ClusterData`+`ClusterLoader`, `GraphSAINTRandomWalkSampler` | `assets/references/node_classification.md` |
| Graph autoencoder → spatial domains (STAGATE family) | **PARTIAL** | `GAE`/`VGAE` + custom MSE decoder; GAT-autoencoder | `assets/references/graph_autoencoders.md` |
| Geometric / 3D / mesh GNN (structure→property) | **PARTIAL** | `SchNet`/`DimeNet`/`PointNetConv`/`PointTransformerConv`, `radius_graph`; `e3nn` for equivariance | `assets/references/geometric_equivariant.md` |

**Everything is PARTIAL**: `torch` is pinned, but `torch_geometric` is in no pinned env — provision it
first (above). The recipes here were checked against PyG 2.8.0 **source**, not executed, so treat them
as source-verified rather than tested; the `to_hetero` recipe is known to fail on 2.8 and 2.9.

Read the method doc before running each capability.

---

## Standard patterns (see the reference docs for full code)

1. **Construct the graph.** Keep connectivity as a **sparse `edge_index [2, E]`** — never materialize a dense `[N, N]` adjacency (O(N²), tens of GB at scale). Build edges from `pos` with `knn_graph`/`radius_graph`/`Delaunay`, or from an interaction network with `HeteroData`.
2. **Node classification.** Pass the **full graph** each step; boolean `train/val/test_mask`s select which nodes count. Match the loss to the head (raw logits + `F.cross_entropy`, or `log_softmax` + `F.nll_loss`). For a binary, class-imbalanced target scored by AUPRC, use a single-logit head + `binary_cross_entropy_with_logits(pos_weight=…)` and `sklearn.metrics.average_precision_score`.
3. **Spatial graph autoencoder.** Spatial neighbor graph on `obsm["spatial"]` → GAT/GCN encoder → latent in `obsm[...]` → reconstruct node features (MSE) → cluster the latent (mclust/Leiden) into domains. This is the STAGATE pattern; multi-modal variants (GraphST/SpatialGlue/MultiGATE) add per-modality encoders or cross-modal attention.
4. **Geometric / 3D.** Build a 3D neighborhood with `radius_graph(pos, r)`; use an invariant model (`SchNet`, `DimeNet`) or point conv (`PointNetConv`, `PointTransformerConv`) for structure→property; for true rotational **equivariance** PyG ships only `ViSNet` — use **`e3nn`** for SE(3)/O(3) tensor-product layers.

---

## Pitfalls (checked against PyG 2.8.0)

- **Materializing a dense `[N, N]` adjacency** — infeasible for large networks; keep sparse `edge_index` and sample subgraphs (`NeighborLoader`/`ClusterData`) if the full graph won't fit.
- **VGAE encoder must return a tuple `(mu, logstd)`** (GAE returns a single `z`); `GAE`/`VGAE`'s built-in `recon_loss` is **link** reconstruction — attribute reconstruction (STAGATE-style) needs a **custom decoder + MSE**, not `recon_loss`.
- **Loss/head mismatch** — don't put `log_softmax` in `forward` and then use `cross_entropy` (double-counts); pick one convention.
- **PyG ships no AUPRC metric and no focal loss** — use `sklearn.metrics.average_precision_score` and `torchvision.ops.sigmoid_focal_loss` (or a hand-written one); PyG's `ImbalancedSampler` only helps mini-batch loaders, not a full-batch transductive loop (use `pos_weight` there).
- **`knn_graph`/`radius_graph` in PyG 2.8 need `pyg-lib`** — and so do `T.KNNGraph`/`T.RadiusGraph`,
  which delegate to them, plus `SchNet`/`DimeNetPlusPlus`, which build a `radius_graph` internally.
  The caveat is not limited to the functional form.
- **`GraphSAINTRandomWalkSampler` additionally needs `torch-sparse`** — it imports and builds a
  `SparseTensor` (`loader/graph_saint.py:8,68`), which **pyg-lib does not provide**. That contradicts the
  pyg-lib-only spec above: follow it and GraphSAINT cannot run (`ImportError: 'SparseTensor' requires
  'torch-sparse'`). Add `torch-sparse` to the env spec, or use `NeighborLoader`/`ClusterData`, which
  accept **either** backend. Verified against 2.8.0.
- **k-NN graphs are DIRECTED** — `T.KNNGraph`/`knn_graph` default to `force_undirected=False`
  (`transforms/knn_graph.py:36`), so every node gets exactly *k* in-edges while a hub sends many and
  receives none. Pass `force_undirected=True`, or `to_undirected(edge_index)`. (Radius graphs are
  symmetric by construction — this is k-NN-specific.)
- **`add_self_loops=False` on a loop-free graph silently zeroes isolated nodes** — a node with no
  in-edges never sees its own features and its output is **exactly 0.0** (reproduced on 2.8.0: `|out|`
  = 0.000000 vs 1.797751 with loops). STAGATE gets away with it only because
  `Transfer_pytorch_Data` injects self-loops itself (`utils.py:19`); a generic `knn_graph`
  (`loop=False` by default) does not. Call `add_self_loops(edge_index)` first, or `knn_graph(..., loop=True)`.
- **`SAGEConv(aggr="lstm")` requires a destination-sorted `edge_index`** — otherwise
  `ValueError: Can not perform aggregation since the 'index' tensor is not sorted`. Fix:
  `sort_edge_index(edge_index, sort_by_row=False)`. `aggr="mean"` has no such requirement.
- **`to_hetero` + lazy dims** — use `in_channels=-1` so each per-edge-type replica infers its input dim; run one dummy forward to initialize before loading weights. **Do not wrap PyG's `Sequential` in `to_hetero`** — it is not fx-traceable (`TraceError`); write a plain `nn.Module`, and keep the `forward` arg names `x`/`edge_index` (`to_hetero` dispatches on them).

---

## Evidence & Reporting

Every run emits a trailing JSON `report` (cite its numbers): graph size (n nodes/edges, node-feature dim), model + key hyperparameters (layers, hidden dim, heads, lr, epochs), the exact metric (ARI / AUPRC / MAE / Pearson) computed on the held-out split, and the output artifact's shape/dtype. Inspect any embedding/UMAP/loss figure before it backs a claim. Record the PyG version and, for reproduced methods, the source repo + commit (see `../repro/`).
