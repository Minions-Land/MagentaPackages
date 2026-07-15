# Geometric / 3D GNNs & equivariance

**Maturity: PARTIAL** — `torch-geometric` is **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Follow `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`: §A a new Pixi feature + environment with its **own solve-group** (preferred — lands in `pixi.lock`), or §B a **named** conda env if Pixi can't solve it. Never a bare `pip install` (it can land in `base`), and never add these pins to `task1–4`. `omics_preflight` does not cover non-standard envs — check the import yourself, and record the env + versions in the `report`. If it can be neither imported nor provisioned, that is a **blocker**, not a cue to substitute a weaker method.

For methods over **3D coordinates** (molecular/protein structure, point clouds) or a **mesh** (e.g.
cell geometry): build a spatial neighborhood, message-pass on it, read out a per-graph or
per-position property. Distinguish **invariant** (output unchanged under rotation/translation — right
for scalar properties) from **equivariant** (output transforms with the input — right for vectors/
tensors like force fields or oriented features).

## Build the 3D neighborhood

```python
from torch_geometric.nn import radius_graph, knn_graph
edge_index = radius_graph(pos, r=10.0, batch=batch, max_num_neighbors=32)   # pos [N,3]
# or knn_graph(pos, k=16, batch=batch)
```

## Invariant models (scalar property from structure) — PyG built-ins

All take atomic numbers `z` (or features `x`), coordinates `pos [N,3]`, and `batch [N]`, and build
their own `radius_graph` internally:

```python
from torch_geometric.nn import SchNet, DimeNetPlusPlus
model = SchNet(hidden_channels=128, num_interactions=6, cutoff=10.0)  # E(3)-invariant: distances only
y = model(z, pos, batch)                                              # per-graph scalar
# DimeNetPlusPlus: distances + bond angles (directional), stronger but heavier
model = DimeNetPlusPlus(hidden_channels=128, out_channels=1, num_blocks=4,
                        int_emb_size=64, basis_emb_size=8, out_emb_channels=256,
                        num_spherical=7, num_radial=6, cutoff=5.0)
```

Point-cloud convs (translation-invariant via **relative** coordinates `pos_j - pos_i`):

```python
from torch_geometric.nn import PointNetConv, PointTransformerConv, global_max_pool
h = PointNetConv(local_nn=mlp)(x, pos, edge_index)          # x may be None
# PointTransformerConv(in, out, pos_nn=None, attn_nn=None): vector attention with positional encoding
out = global_max_pool(h, batch)                            # -> per-cloud property
```

## Structure → property with a positional readout (e.g. protein–DNA binding)

Tasks like predicting a **per-position nucleotide distribution (PWM)** from a protein–DNA complex:
build graphs over the atoms/residues (protein) and the DNA (a helix graph), message-pass with a
geometric conv, and read out **per DNA position** a length-4 distribution (softmax over {A,C,G,T},
rows summing to 1). Metric is typically MAE/KL vs the reference PWM.

```python
# per-position head: node/edge features along the DNA -> Linear(., 4) -> softmax(dim=-1)
pwm = F.softmax(head(dna_node_repr), dim=-1)               # [L, 4], each row sums to 1
```

Reproduce a specific published geometric model (e.g. a groove+shape dual-graph network) via
`../repro/` when matching its exact metric; the invariant convs above are the from-scratch backbone.

## Mesh GNNs (cell / tissue geometry)

A mesh becomes a graph with `T.FaceToEdge()` (see `graph_construction.md`). The dominant work is
**geometry feature engineering** on nodes/edges (cell areas, edge/junction lengths, curvatures, and
their temporal derivatives), then a standard message-passing GNN (GCN/GAT/SAGE) with one head per
target (multi-task: a classification head + regression heads). Watch for non-Python mesh formats
(e.g. MATLAB `.mat`) — load and convert to `pos`/`face` first.

## Equivariance (when invariance isn't enough)

- **PyG ships no E(n)/SE(3)-equivariant conv.** `SchNet`/`DimeNet` are **invariant**; the only
  equivariant model in PyG is **`ViSNet`** (equivariant vector-scalar interactive GNN) — a reasonable
  in-PyG option when you need equivariant vector features.
- **For true O(3)/SE(3) tensor-product equivariance, use the external library `e3nn`** (irreps +
  spherical-harmonic tensor products). Reach for it only when the target is a vector/tensor field or
  orientation — for scalar properties an invariant model (SchNet/DimeNet) is simpler and usually
  sufficient.

## Reporting

- How the 3D neighborhood was built (radius r / k), the model (SchNet/DimeNet/point/ViSNet/e3nn) and
  whether it is invariant vs equivariant + why, hyperparameters, and the metric (MAE / Pearson / …)
  on the held-out set. For a PWM output, confirm each row sums to 1.
