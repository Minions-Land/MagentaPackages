---
name: bioml-graph-dl
disable-model-invocation: true
---

# BioML Graph & Geometric Deep Learning — GNNs on biological graphs

> Subskill of `bioml`. Enter here from the parent skill when the method is a **graph neural network** or a **geometric / 3D-structure** model. Read `../SKILL.md` (parent) and `../../omics-shared/SKILL.md` first — their ML-engineering foundations and evidence rules apply here.

This subskill covers the **graph-DL engineering layer** — the reusable machinery underneath a large family of biological DL methods:

- **Transductive node classification** on biological networks (gene/protein interaction + regulatory graphs) — e.g. predicting gene labels from multi-omics node features.
- **Graph autoencoders** for spatial-omics domain identification — the STAGATE / GraphST / SpatialGlue / MultiGATE family (spatial graph → latent embedding → domains).
- **Geometric / 3D GNNs** for structure→property tasks (protein–DNA binding, molecular/point-cloud regression) and cell-mesh models.

Built on **PyTorch Geometric (PyG)** — the standard library these methods use. This is the *how-to-build-and-train-the-GNN* layer; the spatial-analysis workflow that *calls* it lives in `../../spatial/` and `../../single-cell/`.

---

## When to use

- The method's core is a **GNN / message-passing network** (node/edge/graph prediction), a **graph autoencoder**, or a **geometric model over 3D coordinates / a mesh**.
- You need to **build a graph** from non-graph data (spatial coordinates, molecular structure, a cell mesh, an interaction network) and train a model on it.

**Skip this path** for standard scanpy analysis (`../../single-cell/`, `../../spatial/`), for sequence foundation models (`../sequence-fm/`), or for single-cell VAE/FM reproduction (`../deep-models/`). As always, first check whether the paper's own repo runs (`../repro/`) before reimplementing a bespoke GNN.

---

## The library

**PyTorch Geometric (PyG) ≥ 2.6** (recipes verified against **2.9.0**). Install matches your torch/CUDA build:

```bash
pip install torch_geometric
# PyG 2.9 routes knn_graph / radius_graph through pyg-lib (torch-cluster is deprecated/ignored):
pip install pyg-lib -f https://data.pyg.org/whl/torch-${TORCH}+${CUDA}.html
pip install e3nn        # only if you need true SE(3)/O(3) equivariance (see geometric doc)
```

```python
import torch, torch.nn.functional as F
import torch_geometric.transforms as T
from torch_geometric.data import Data, HeteroData
from torch_geometric.nn import GCNConv, GATConv, SAGEConv, GINConv, to_hetero, knn_graph, radius_graph
from torch_geometric.loader import NeighborLoader, ClusterData, ClusterLoader
```

---

## Capability Menu

| Capability | PyG entry point | Reference Doc |
|------------|-----------------|---------------|
| Build a graph (coords / structure / mesh / network) | `Data`/`HeteroData`, `T.KNNGraph`/`RadiusGraph`/`Delaunay`, `knn_graph`/`radius_graph` | `assets/references/graph_construction.md` |
| Transductive node classification (incl. hetero, imbalanced/AUPRC) | `GCNConv`/`GATConv`/`SAGEConv`/`GINConv`, `to_hetero` | `assets/references/node_classification.md` |
| Scaling to large / dense-adjacency graphs | `NeighborLoader`, `ClusterData`+`ClusterLoader`, `GraphSAINTRandomWalkSampler` | `assets/references/node_classification.md` |
| Graph autoencoder → spatial domains (STAGATE family) | `GAE`/`VGAE` + custom MSE decoder; GAT-autoencoder | `assets/references/graph_autoencoders.md` |
| Geometric / 3D / mesh GNN (structure→property) | `SchNet`/`DimeNet`/`PointNetConv`/`PointTransformerConv`, `radius_graph`; `e3nn` for equivariance | `assets/references/geometric_equivariant.md` |

Read the method doc before running each capability.

---

## Standard patterns (see the reference docs for full code)

1. **Construct the graph.** Keep connectivity as a **sparse `edge_index [2, E]`** — never materialize a dense `[N, N]` adjacency (O(N²), tens of GB at scale). Build edges from `pos` with `knn_graph`/`radius_graph`/`Delaunay`, or from an interaction network with `HeteroData`.
2. **Node classification.** Pass the **full graph** each step; boolean `train/val/test_mask`s select which nodes count. Match the loss to the head (raw logits + `F.cross_entropy`, or `log_softmax` + `F.nll_loss`). For a binary, class-imbalanced target scored by AUPRC, use a single-logit head + `binary_cross_entropy_with_logits(pos_weight=…)` and `sklearn.metrics.average_precision_score`.
3. **Spatial graph autoencoder.** Spatial neighbor graph on `obsm["spatial"]` → GAT/GCN encoder → latent in `obsm[...]` → reconstruct node features (MSE) → cluster the latent (mclust/Leiden) into domains. This is the STAGATE pattern; multi-modal variants (GraphST/SpatialGlue/MultiGATE) add per-modality encoders or cross-modal attention.
4. **Geometric / 3D.** Build a 3D neighborhood with `radius_graph(pos, r)`; use an invariant model (`SchNet`, `DimeNet`) or point conv (`PointNetConv`, `PointTransformerConv`) for structure→property; for true rotational **equivariance** PyG ships only `ViSNet` — use **`e3nn`** for SE(3)/O(3) tensor-product layers.

---

## Pitfalls (verified against PyG 2.9)

- **Materializing a dense `[N, N]` adjacency** — infeasible for large networks; keep sparse `edge_index` and sample subgraphs (`NeighborLoader`/`ClusterData`) if the full graph won't fit.
- **VGAE encoder must return a tuple `(mu, logstd)`** (GAE returns a single `z`); `GAE`/`VGAE`'s built-in `recon_loss` is **link** reconstruction — attribute reconstruction (STAGATE-style) needs a **custom decoder + MSE**, not `recon_loss`.
- **Loss/head mismatch** — don't put `log_softmax` in `forward` and then use `cross_entropy` (double-counts); pick one convention.
- **PyG ships no AUPRC metric and no focal loss** — use `sklearn.metrics.average_precision_score` and `torchvision.ops.sigmoid_focal_loss` (or a hand-written one); PyG's `ImbalancedSampler` only helps mini-batch loaders, not a full-batch transductive loop (use `pos_weight` there).
- **`knn_graph`/`radius_graph` in PyG 2.9 need `pyg-lib`** (torch-cluster is deprecated/ignored) — install it or the call errors.
- **`to_hetero` + lazy dims** — use `in_channels=-1` so each per-edge-type replica infers its input dim; run one dummy forward to initialize before loading weights.

---

## Evidence & Reporting

Every run emits a trailing JSON `report` (cite its numbers): graph size (n nodes/edges, node-feature dim), model + key hyperparameters (layers, hidden dim, heads, lr, epochs), the exact metric (ARI / AUPRC / MAE / Pearson) computed on the held-out split, and the output artifact's shape/dtype. Inspect any embedding/UMAP/loss figure before it backs a claim. Record the PyG version and, for reproduced methods, the source repo + commit (see `../repro/`).
