# Transductive node classification (+ hetero, imbalance, scale)

**Maturity: PARTIAL** — `torch-geometric` is **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Provision it into its own environment per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`, which carries the routing and the hard rules.

Predict a label per node from node features + graph structure. **Transductive** = the whole graph
(all nodes/edges) is present at train time; boolean masks decide which nodes contribute to the loss.

## Model (2-layer, swap the conv)

```python
import torch, torch.nn.functional as F
from torch_geometric.nn import GCNConv   # or GATConv / GATv2Conv / SAGEConv / GINConv

class GNN(torch.nn.Module):
    def __init__(self, in_ch, hidden, out_ch):
        super().__init__()
        self.conv1 = GCNConv(in_ch, hidden)          # GATConv(in,hidden,heads=8) / SAGEConv(in,hidden) / GINConv(mlp)
        self.conv2 = GCNConv(hidden, out_ch)
    def forward(self, x, edge_index):
        x = F.dropout(x, p=0.5, training=self.training)
        x = self.conv1(x, edge_index).relu()
        x = F.dropout(x, p=0.5, training=self.training)
        return self.conv2(x, edge_index)             # raw logits (no softmax here)
```

Conv choice: **GCN** (fast baseline), **GAT/GATv2** (attention, `heads=`, set `edge_dim=` to use edge
features), **SAGE** (`aggr="mean"`, or `aggr="lstm"` — which **requires a destination-sorted
`edge_index`**: `sort_edge_index(edge_index, sort_by_row=False)`, else
`ValueError: ... 'index' tensor is not sorted`), **GIN** (wraps your MLP, expressive).
`in_channels=-1` enables lazy dim inference.

## Training loop (full-batch transductive)

```python
opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)

def train():
    model.train(); opt.zero_grad()
    out  = model(data.x, data.edge_index)                         # ALL nodes
    loss = F.cross_entropy(out[data.train_mask], data.y[data.train_mask])   # logits in
    loss.backward(); opt.step(); return float(loss)

@torch.no_grad()
def test():
    model.eval(); pred = model(data.x, data.edge_index).argmax(-1)
    return [int((pred[m]==data.y[m]).sum())/int(m.sum())
            for m in (data.train_mask, data.val_mask, data.test_mask)]
```

**Match loss to head:** raw logits → `F.cross_entropy`; or `F.log_softmax` in `forward` → `F.nll_loss`.
Don't combine both.

## Binary + class-imbalanced target, scored by AUPRC

Common for "which genes/nodes are positive" tasks. Use a **single-logit head** and weight the loss
(PyG ships no AUPRC metric and no focal loss — these are torch/sklearn):

```python
ytr = data.y[data.train_mask]
pos_weight = ((ytr == 0).sum() / (ytr == 1).sum().clamp(min=1)).float()     # #neg / #pos

loss = F.binary_cross_entropy_with_logits(
    out[data.train_mask].view(-1), data.y[data.train_mask].float(), pos_weight=pos_weight)

from sklearn.metrics import average_precision_score                        # = AUPRC
prob = torch.sigmoid(out[mask]).view(-1).detach().cpu().numpy()
auprc = average_precision_score(data.y[mask].cpu().numpy(), prob)
```

For hard imbalance, `torchvision.ops.sigmoid_focal_loss(logits, targets, alpha, gamma)` is an
alternative to `pos_weight`. (`ImbalancedSampler` only helps mini-batch `NeighborLoader`, not a
full-batch loop.)

## Heterogeneous graphs (`to_hetero`)

Write a homogeneous model with **lazy `-1`** channels, then lift it:

```python
import torch
from torch_geometric.nn import SAGEConv, Linear, to_hetero

# to_hetero fx-traces the module, and PyG's own `Sequential` is NOT traceable: its forward is
# `forward(self, *args, **kwargs)`, and PyG's fx pass treats only `torch.nn.Sequential` as a leaf
# (nn/fx.py:287), so it traces into PyG's and dies unpacking *args:
#   TraceError: Proxy object cannot be iterated.
# Verified on 2.8.0. Write a plain nn.Module instead — upstream's own to_hetero tests do the same.
class GNN(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), 64)
        self.conv2 = SAGEConv((-1, -1), 64)
        self.lin = Linear(-1, num_classes)     # PyG's Linear — torch.nn.Linear rejects -1

    def forward(self, x, edge_index):          # the ARG NAMES are load-bearing (see below)
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index).relu()
        return self.lin(x)

model = to_hetero(GNN(), data.metadata(), aggr='sum')      # per-edge-type replicas, aggr over dst
out = model(data.x_dict, data.edge_index_dict)             # -> {'gene': (N, num_classes)}
# ^ this first call also materializes the lazy (-1) dims; do it before building the optimizer.
```

> **`to_hetero` reads your `forward` argument NAMES**, not positions — it decides what is a node
> feature vs an edge index from them. Rename `edge_index` to `ei` and it still traces, then fails at
> runtime with `ValueError: MessagePassing.propagate only supports integer tensors of shape
> [2, num_messages]` — a confusing error a long way from the cause. Keep the names `x` and `edge_index`.
> (Both behaviours reproduced on PyG 2.8.0.)

## Scaling: never build a dense `[N, N]`

For large/dense networks, sample **sparse subgraphs** instead of materializing the full adjacency:

- **`NeighborLoader`** (general, hetero-capable): `NeighborLoader(data, input_nodes=data.train_mask, num_neighbors=[25,10], batch_size=1024, shuffle=True)`. Each batch is a subgraph whose **first `batch_size` rows are the seed nodes** — compute loss on `out[:batch.batch_size]`.
- **`ClusterData` + `ClusterLoader`** (Cluster-GCN, cheap on clustered graphs): METIS-partition once (`ClusterData(data, num_parts=1500, save_dir=…)`), then `ClusterLoader(cluster_data, batch_size=20)`; loss on `out[batch.train_mask]`.
- **`GraphSAINTRandomWalkSampler`** (variance-corrected subgraph sampling): `(data, batch_size=6000, walk_length=2, num_steps=5, sample_coverage=100)`.

Picker: NeighborLoader = node-wise fanout; Cluster-GCN = cheap on clustered graphs; GraphSAINT =
subgraph sampling with normalization. All keep memory ∝ subgraph size, not N².

## Reporting

- Model (conv, layers, hidden, heads), optimizer/lr/weight-decay/epochs, best val epoch.
- The metric on the held-out mask (accuracy / macro-F1 / **AUPRC** with the exact `sklearn` call).
- If sampled: which loader + batch size / num_neighbors / num_parts.
