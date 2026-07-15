# Cellular Neighborhoods (Niches)

**Maturity: REFERENCE** — no compute subcommand. The default (**squidpy `gr.calculate_niche`**) runs on the pinned stack; the Nolan-lab CN k-means variant is a short hand-rolled script; **CytoCommunity** is an external GPU package. Verified against squidpy 1.8.1.

## Goal / When to Use

Find **recurrent cellular neighborhoods** — spatial niches defined by their local *cell-type composition*, not by their own expression. A niche is "wherever T cells sit next to macrophages next to stroma in this proportion", and the same niche recurs across the tissue and across samples.

Requires a cell-type label you trust: this method clusters compositions *of that label*, so a bad annotation produces confidently wrong niches. Distinct from `domains.md`, which partitions tissue by **expression** + position; niches partition by **who is next to whom**.

## Decision Criteria

- **Default: `sq.gr.calculate_niche(flavor="neighborhood")`** — squidpy's maintained implementation of exactly this idea: build the neighbourhood profile (per-cell cell-type composition of its spatial window), then cluster it. Pinned, tested, handles z-scaling, `min_niche_size`, and n-hop windows. Start here.
- **Other flavors** — `utag`, `cellcharter`, `spatialleiden` are alternative niche definitions behind the same call. Try them before reaching outside squidpy.
- **Nolan-lab CN k-means (hand-rolled)** — the classic definition: kNN window → composition → **k-means**. Reach for it only when you specifically need *that* definition (e.g. reproducing a CODEX paper); `calculate_niche` clusters with Leiden, so results are not interchangeable.
- **CytoCommunity (GNN, external + GPU)** — a graph neural network with soft assignment. Higher ceiling on some benchmarks, much more setup (`torch-geometric` + the package, not in `task2`). Only after the simple methods have been tried and reported — they are competitive, and a GNN is not a substitute for a trustworthy annotation.

## How-to (default — squidpy)

```python
import squidpy as sq

sq.gr.spatial_neighbors(adata, coord_type="generic", n_neighs=10)   # the window; see pin note
sq.gr.calculate_niche(
    adata,
    flavor="neighborhood",
    groups="cell_type",       # the obs column whose composition defines a niche
    n_neighbors=10,
    resolutions=[0.5],        # Leiden resolution(s); pass several to sweep
)
# -> writes adata.obs["nhood_niche_res=0.5"]
```

`scale=True` (default) z-scales the composition profile before clustering; `min_niche_size` drops
niches too small to be real; `distance=` / `n_hop_weights=` widen the window past one hop.

> **Pin note.** `sq.gr.spatial_neighbors` is the graph builder in the pinned squidpy 1.8.1. Upstream removes it in **1.9.0** in favour of `spatial_neighbors_knn`/`_radius`/`_delaunay`/`_grid` — names that **do not exist in 1.8.1**. `pixi.toml` pins `squidpy = ">=1.8,<1.9"`; do not "modernise" the call. Note also that `calculate_niche` is absent from squidpy 1.4–1.7, which is why the floor is 1.8.

## How-to (Nolan-lab CN k-means, hand-rolled)

Only when you need this exact definition. It is ~15 lines because the idea is simple — not because squidpy lacks it.

```python
import numpy as np, pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import KMeans

def cellular_neighborhoods(coords, cell_types, k_neighbors=10, n_neighborhoods=10, random_state=0):
    """Nolan-lab CN: kNN window -> cell-type composition -> k-means.

    NOTE the window is self-inclusive: NearestNeighbors(...).kneighbors(coords) returns each cell
    as its own nearest neighbour (distance 0), so k_neighbors=10 means self + 9 others. That IS
    the Nolan definition — do not "fix" it — but it differs from squidpy's off-diagonal graph, so
    the two are not directly comparable.
    """
    ct = pd.get_dummies(cell_types).values.astype(np.float32)
    nn = NearestNeighbors(n_neighbors=k_neighbors).fit(coords)
    _, idx = nn.kneighbors(coords)
    window_composition = ct[idx].mean(axis=1)          # (n_cells, n_types)
    return KMeans(n_clusters=n_neighborhoods, random_state=random_state).fit_predict(window_composition)
```

- **`k_neighbors`** — window size (10–20 typical). Too small → noisy windows; too large → over-smoothed.
- **`n_neighborhoods`** — match the expected number of tissue niches; sweep it and check stability rather than trusting one value.
- **`random_state`** — set it. K-means is seed-dependent, and an unseeded niche map cannot be reproduced.

## Evaluating against a reference labelling

Niche labels are arbitrary — cluster 0 in your run and cluster 0 in the reference have no relation — so match them optimally before scoring.

```python
import numpy as np, pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import confusion_matrix, f1_score

def hungarian_f1(y_true, y_pred):
    """Macro-F1 after optimally matching predicted labels to reference labels.

    Both sides are factorized to integer codes first. This is the whole trick: a confusion matrix
    is indexed by POSITIONS into the sorted union of labels, and linear_sum_assignment returns
    positions — not label values. Using those positions as if they were labels silently scores a
    perfect clustering as 0.0 whenever the labels are not already 0..K-1, and raises outright on
    string labels (the normal form for niche names read from a CSV).
    """
    t_codes, t_uniq = pd.factorize(np.asarray(y_true))
    p_codes, p_uniq = pd.factorize(np.asarray(y_pred))
    k = max(len(t_uniq), len(p_uniq))
    cm = confusion_matrix(t_codes, p_codes, labels=np.arange(k))
    row_ind, col_ind = linear_sum_assignment(-cm)          # maximize the matched diagonal
    mapping = dict(zip(col_ind, row_ind))                  # predicted code -> reference code
    p_matched = np.array([mapping[c] for c in p_codes])
    return f1_score(t_codes, p_matched, average="macro")
```

Verified on the cases that break the naive version: perfect clustering with labels `[10,20,30]` → **1.0** (the positional version returns 0.0), string labels `["CN_A","CN_B","CN_C"]` → **1.0** (the positional version raises `ValueError: Mix of label input types`).

## Pitfalls

- **Scoring without matching, or matching by confusion-matrix position** — *symptom:* macro-F1 near zero on a clustering that looks right, or `ValueError: Mix of label input types (string and number)`. *Diagnosis:* cluster IDs are arbitrary, and `linear_sum_assignment` returns positions, not labels. *Fix:* the `hungarian_f1` above.
- **Unseeded k-means** — *symptom:* the niche map changes between runs. *Fix:* `random_state=`, and record it.
- **Wrong window size** — it dominates the niche definition; report `k_neighbors`/`n_neighbors` next to every niche claim.
- **Garbage cell-type labels** — niches are clusters *of your annotation*. If the annotation is shaky, the niches are shaky in a way no amount of clustering fixes. Validate the annotation first.
- **Jumping to the GNN** — CN k-means and `calculate_niche` are competitive and far simpler. Run one, report it, and only then argue that a GNN is needed.

## Figure checkpoints

- **Niches in space** (`sq.pl.spatial_scatter(adata, color="nhood_niche_res=0.5", img=False, shape=None)`) — do niches form coherent regions, or salt-and-pepper? Speckle means the window is too small or the annotation is noisy.
- **Niche × cell-type composition heatmap** — is each niche a distinct, interpretable mixture, or are two niches near-identical (over-clustering)?

Observe each before it backs a claim.

## Grounding

```python
report = {
    "method": "squidpy_calculate_niche",     # or "nolan_cn_kmeans"
    "flavor": "neighborhood",
    "groups": "cell_type",
    "n_neighbors": 10,
    "resolutions": [0.5],
    "random_state": 42,                       # calculate_niche's default; set it explicitly for k-means
    "n_niches": int(adata.obs["nhood_niche_res=0.5"].nunique()),
    "cell_type_source": "marker+LLM annotation",
    "macro_f1_hungarian": None,               # only if a reference labelling exists
}
```

Record the window size, the label column the niches were built from, the seed, and the niche count. A niche map without its window size and annotation source is not interpretable — both change the answer.

## Honesty

- **Niches are clusters of an annotation, not measurements.** Every niche claim inherits the annotation's uncertainty; say which annotation produced it.
- **The window size defines the niche.** "Niche 3 is a tumour-immune interface" is a statement about a 10-neighbour window, and a 30-neighbour window may not contain it. State the window.
- **Niche count is a choice.** Leiden resolution / k-means `n_neighborhoods` set it; report the value and that a neighbouring one was defensible.
- **Different flavors are different definitions.** squidpy's `neighborhood` (Leiden on the profile) and Nolan's k-means answer the same question with different clusterers — do not present a number from one as validating the other.
