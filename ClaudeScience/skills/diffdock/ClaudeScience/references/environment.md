# DiffDock environment

Use Python 3.11, CUDA 12.1, and a C/C++ compiler. The validated DiffDock 1.1.3
environment uses:

```bash
export CC=gcc CXX=g++
python -m pip install "torch==2.1.2" "numpy~=1.26.4" "pandas~=2.1.4"
python -m pip install \
  "torch-geometric==2.6.1" "torch-scatter==2.1.2" \
  "torch-sparse==0.6.18" "torch-cluster==1.6.3" \
  -f https://data.pyg.org/whl/torch-2.1.0+cu121.html
python -m pip install \
  "e3nn==0.5.1" "hydra-core==1.3.2" "pyrsistent==0.20.0" \
  "rdkit==2024.3.5" "scipy==1.13.1" "biopython==1.79" \
  "fair-esm==2.0.0" "networkx==3.2.1" "pyyaml==6.0.1" "prody==2.6.1"
```

DiffDock imports `torch_cluster`, `torch_scatter`, and `torch_sparse` directly,
so the matching CUDA wheels are required even though PyG has Python fallbacks.
Clone `github.com/gcorso/DiffDock` at commit
`9a22cbcbc7612c7565c80e8399d9be298971f156` for the validated source state.
The first SO(3)/torus precompute needs at least 64 GB host RAM.
