# Graph autoencoders & spatial domain identification

Unsupervised graph representation learning: encode nodes into a latent embedding, reconstruct
(edges or features), then cluster the latent. This is the backbone of spatial-omics domain
identification (STAGATE / GraphST / SpatialGlue / MultiGATE).

## PyG `GAE` / `VGAE` (link reconstruction)

```python
from torch_geometric.nn import GAE, VGAE, GCNConv

class Enc(torch.nn.Module):                       # GAE encoder → single z
    def __init__(s, i, o): super().__init__(); s.c1=GCNConv(i, 2*o); s.c2=GCNConv(2*o, o)
    def forward(s, x, ei): return s.c2(s.c1(x, ei).relu(), ei)

model = GAE(Enc(in_ch, 16))                        # default decoder = InnerProductDecoder σ(z·zᵀ)
z    = model.encode(x, train_pos_edge_index)
loss = model.recon_loss(z, train_pos_edge_index)  # BCE on pos + auto-sampled neg edges
auc, ap = model.test(z, pos_edge_index, neg_edge_index)
```

`VGAE`'s encoder must return a **tuple `(mu, logstd)`**; add the KL term:

```python
class VEnc(torch.nn.Module):
    def __init__(s, i, o): super().__init__(); s.c1=GCNConv(i, 2*o); s.mu=GCNConv(2*o, o); s.ls=GCNConv(2*o, o)
    def forward(s, x, ei): h = s.c1(x, ei).relu(); return s.mu(h, ei), s.ls(h, ei)
model = VGAE(VEnc(in_ch, 16))
z    = model.encode(x, train_pos_edge_index)
loss = model.recon_loss(z, train_pos_edge_index) + (1 / N) * model.kl_loss()
```

**Key point:** `recon_loss` reconstructs **edges** (link prediction). For spatial-omics you instead
reconstruct **node features** — that needs a custom decoder + MSE (below), not `GAE.recon_loss`.

## Spatial GAT-autoencoder → domains (STAGATE pattern)

The reusable three-step pattern (verified against STAGATE_pyG):

```python
import STAGATE_pyG as STAGATE           # or reimplement the pattern with PyG GATConv
# 1) spatial neighbor graph on the coordinates
STAGATE.Cal_Spatial_Net(adata, rad_cutoff=150)          # Radius; or model='KNN', k_cutoff=6
#    -> edge list in adata.uns['Spatial_Net']; Transfer_pytorch_Data adds self-loops + Data(x=adata.X)
# 2) GAT-autoencoder: encoder (GAT) -> latent -> decoder -> reconstruct expression, MSE loss
adata = STAGATE.train_STAGATE(adata, hidden_dims=[512, 30], n_epochs=1000, lr=1e-3)
#    -> latent embedding in adata.obsm['STAGATE']  (loss = F.mse_loss(x, reconstruction))
# 3) cluster the latent into spatial domains
adata = STAGATE.mclust_R(adata, num_cluster=7, used_obsm='STAGATE')   # R mclust (GMM)
#    alt (no R): sc.pp.neighbors(adata, use_rep='STAGATE'); sc.tl.leiden(adata)
```

To reimplement the model directly in PyG: a symmetric encoder→decoder of `GATConv` layers that
**reconstructs the input features** (MSE), taking the latent from the bottleneck. STAGATE additionally
ties decoder weights to the transposed encoder and shares the encoder's attention on the decoder —
useful but optional; a plain GAT/GCN autoencoder with MSE feature reconstruction is a solid baseline.

```python
from torch_geometric.nn import GATConv
class GATAutoEncoder(torch.nn.Module):
    def __init__(s, d_in, d_hidden, d_lat):
        super().__init__()
        s.enc1 = GATConv(d_in, d_hidden, heads=1, concat=False, add_self_loops=False)
        s.enc2 = GATConv(d_hidden, d_lat, heads=1, concat=False, add_self_loops=False)
        s.dec1 = GATConv(d_lat, d_hidden, heads=1, concat=False, add_self_loops=False)
        s.dec2 = GATConv(d_hidden, d_in, heads=1, concat=False, add_self_loops=False)
    def forward(s, x, ei):
        z = s.enc2(F.elu(s.enc1(x, ei)), ei)          # latent
        xr = s.dec2(F.elu(s.dec1(z, ei)), ei)         # reconstruction
        return z, xr
# train: z, xr = model(data.x, data.edge_index); loss = F.mse_loss(data.x, xr)
# cluster z -> domains (mclust / Leiden / KMeans with the target k)
```

## Generalizing to multi-modal spatial methods

Same skeleton, different encoder:
- **GraphST** — graph autoencoder + contrastive augmentation on the spatial graph.
- **SpatialGlue** — dual-modality (e.g. RNA+ATAC / RNA+protein) with cross-modal attention integration.
- **MultiGATE** — multi-modal graph-attention autoencoder over a gene–peak + spatial graph.
All: spatial graph on `obsm["spatial"]` → (multi-)encoder → latent in `obsm[...]` → cluster to a
fixed number of domains. Reproduce via `../repro/` (run the repo) when matching a specific method;
the PyG GAT-autoencoder above is the from-scratch baseline.

## Reporting

- Graph (n spots, edges, radius/k), model (encoder type, hidden/latent dims, epochs, lr), final
  reconstruction loss, clustering method + k, and the domain metric (e.g. ARI vs a reference labeling).
