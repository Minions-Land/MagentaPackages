# Building graphs for PyG

**Maturity: PARTIAL** — `torch-geometric` is **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Follow `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`: §A a new Pixi feature + environment with its **own solve-group** (preferred — lands in `pixi.lock`), or §B a **named** conda env if Pixi can't solve it. Never a bare `pip install` (it can land in `base`), and never add these pins to `task1–4`. `omics_preflight` does not cover non-standard envs — check the import yourself, and record the env + versions in the `report`. If it can be neither imported nor provisioned, that is a **blocker**, not a cue to substitute a weaker method.

Everything downstream consumes a PyG `Data`/`HeteroData` with a **sparse `edge_index [2, E]`** (COO;
`edge_index[0]`=source, `edge_index[1]`=target). Never build a dense `[N, N]` adjacency — it is O(N²)
and infeasible for large biological networks.

## `Data` (homogeneous)

```python
from torch_geometric.data import Data
import torch
data = Data(
    x=torch.randn(N, F),                                   # [N, F] node features
    edge_index=torch.tensor([[...],[...]], dtype=torch.long),  # [2, E] COO
    y=labels,                                              # node (or graph) labels
)
data.train_mask = mask_tr    # [N] bool — set by attribute (NOT an __init__ arg)
data.val_mask, data.test_mask = mask_va, mask_te
data.validate()              # sanity-check shapes
```

## `HeteroData` (multi-relational biological networks)

For a gene/protein graph with several relation types (e.g. multiple PPI networks + regulatory edges),
or multiple node types:

```python
from torch_geometric.data import HeteroData
data = HeteroData()
data['gene'].x = torch.randn(n_genes, F)                   # per-node-type features
data['gene'].y = gene_labels
data['gene', 'ppi_string', 'gene'].edge_index = ei_string  # [2, E] per relation type
data['gene', 'regulates', 'gene'].edge_index = ei_reg
meta = data.metadata()        # (node_types, edge_types) — feed to to_hetero()
xd, eid = data.x_dict, data.edge_index_dict
```

Multiple interaction networks over the same nodes = multiple edge types (or train one model per
network and ensemble). Keep each `edge_index` sparse.

## From coordinates (`pos` → edges): spatial, point clouds, structures

Transforms read `data.pos` and write `data.edge_index`:

```python
import torch_geometric.transforms as T
# force_undirected defaults to False -> a k-NN graph is DIRECTED: each node gets exactly k in-edges,
# so a hub influences many nodes and receives from none. Almost never what you want for a spatial or
# co-expression graph. Set it, or call to_undirected(edge_index) after.
data = T.KNNGraph(k=6, force_undirected=True)(Data(pos=coords))   # k-NN graph
data = T.RadiusGraph(r=150.0)(Data(pos=coords))            # radius graph (spatial, µm units) — symmetric by construction
data = T.Compose([T.Delaunay(), T.FaceToEdge()])(Data(pos=xy))  # Delaunay triangulation → edges
```

Neither builder adds **self-loops** (`loop=False`). That is fine for GCN/GraphSAGE, which fold in the
root feature themselves — but a conv constructed with `add_self_loops=False` (e.g. `GATConv`) will then
output **exactly zero** for any node with no in-edges. Either leave `add_self_loops=True` (the default),
or add them explicitly:

```python
from torch_geometric.utils import add_self_loops
data.edge_index, _ = add_self_loops(data.edge_index, num_nodes=data.num_nodes)
```

Needs `pyg-lib` in PyG 2.8 — **both** the functional form below and the `T.KNNGraph`/`T.RadiusGraph`
transforms above, which delegate to it (`batch` keeps edges within one sample):

```python
from torch_geometric.nn import knn_graph, radius_graph
edge_index = knn_graph(pos, k=6, batch=batch)              # [2, E]
edge_index = radius_graph(pos, r=0.2, batch=batch, max_num_neighbors=64)
```

**Spatial-omics graph** (STAGATE-style): build a radius/k-NN graph on `adata.obsm["spatial"]`, add
self-loops, and attach `adata.X` as node features — see `graph_autoencoders.md`.

## From a mesh (cells, tissue)

A triangular/tetrahedral mesh (`data.face [3|4, n_faces]`) becomes a graph with:

```python
data = T.FaceToEdge(remove_faces=True)(data)               # face -> undirected edge_index
```

Then engineer geometry features (areas, edge lengths, curvatures) as `data.x` — see
`geometric_equivariant.md`.

## Reporting

- n nodes, n edges (and per-edge-type counts for `HeteroData`), node-feature dim, how edges were
  built (kNN k / radius r / Delaunay / given network), and confirmation the adjacency is sparse.
