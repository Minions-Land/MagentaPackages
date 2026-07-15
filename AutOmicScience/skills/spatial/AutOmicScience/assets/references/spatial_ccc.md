# Spatial Cell-Cell Communication

**Maturity: REFERENCE** — ligand-receptor analysis. The default (**squidpy `gr.ligrec`**) runs on the pinned stack, but **it fetches its interaction database from OmniPath over the network** unless you pass `interactions=` — see below; it is not offline-clean. The directional alternative (**COMMOT**) needs an isolated env. Verified against squidpy 1.8.1 and `zcang/COMMOT` rev `d117445`.

## Goal / When to Use

Generate **ligand-receptor interaction hypotheses** between annotated cell types/domains in spatial context. Use after a trustworthy annotation (garbage labels → garbage CCC). Spatial CCC adds proximity over expression-only CCC.

## Decision Criteria — pick one default

- **Default: squidpy `gr.ligrec`** — a permutation test for enriched ligand-receptor pairs between cluster pairs. The **method** is CellPhoneDB's; the **resource** is **OmniPath**, fetched live. Name both when you report — "CellPhoneDB-style" describes the test, not the database, and the database is the part that decides which interactions can be found at all.
- **Directional, distance-aware → COMMOT (isolated env)** — collective optimal transport that infers **signaling direction and per-spot sent/received signal**, constrained by spatial distance. Use when you specifically need directionality / spatial range. Its `setup.cfg` declares `>=` **floors** (`anndata>=0.7.6`, `pandas>=1.3.5`, `pot>=0.8.0`), *not* pins — the `==` pins in its `requirements.txt` are a dev file pip never applies on install, and they contradict `setup.cfg`. The real reasons to isolate it are that it is v0.0.3, its classifiers stop at Python 3.9, and it drags in pysal/karateclub/rpy2 — a solve that will not co-exist cleanly with `task2`. Isolate it for those reasons, not for a pin that does not exist.

## How-to (default — squidpy ligrec)

```python
import squidpy as sq
from omnipath.interactions import import_intercell_network

# Fetch the resource ONCE, explicitly, and keep it. Leaving interactions=None makes ligrec fetch
# from OmniPath itself on every call: a hidden network dependency (fails offline) against a
# mutable, unversioned upstream (the same code returns different results next month).
interactions = import_intercell_network(
    transmitter_params={"categories": "ligand"}, receiver_params={"categories": "receptor"}
)

sq.gr.ligrec(
    adata, cluster_key="cell_type",
    interactions=interactions,    # pin the resource; record it in the report
    n_perms=1000,                 # NOT a named param — rides **kwargs into .prepare()/.test()
    threshold=0.01,               # EXPRESSION filter: L/R must be expressed in >=1% of a cluster
    corr_method="fdr_bh",         # default is None -> NO multiple-testing correction at all
    corr_axis="clusters",
    use_raw=False,                # default is True and raises AttributeError if .raw is absent
)
res = adata.uns["cell_type_ligrec"]         # {"means", "pvalues", "metadata"}

sq.pl.ligrec(
    res,
    pvalue_threshold=0.05,              # THIS filters. Default 1.0 = show everything.
    remove_nonsig_interactions=True,    # default False
    save="_ligrec.png",
)
```

Three defaults worth stating plainly, because the obvious reading of each is wrong:

- **`alpha` does not filter.** It only draws p≤alpha as tori instead of dots; the default is already 0.001. The filters are `pvalue_threshold` (default **1.0**, i.e. nothing is filtered) and `remove_nonsig_interactions` (default **False**). A dotplot built with `alpha=` alone shows *every* non-empty interaction, which is exactly the "everything is significant" failure below.
- **`corr_method` defaults to `None`** — no FDR. Across thousands of L/R × cluster-pair tests that is not a defensible p-value. Set `fdr_bh`.
- **`threshold` is an expression filter, not a significance knob.** Raising it drops lowly-expressed pairs; it does nothing about multiple testing.

Also: with `n_perms=1000`, p is quantised to 0.001 steps, so `alpha=0.001` admits only p ∈ {0, 0.001} — it is the resolution floor, not a tuned level. And `use_raw=False` requires `.X` to be normalized but **not z-scored**: CellPhoneDB means are meaningless on scaled data.

**Directional CCC (COMMOT — isolated env):**
```python
import commot as ct
df = ct.pp.ligand_receptor_database(database="CellChat", species="human", signaling_type="Secreted Signaling")
df = ct.pp.filter_lr_database(df, adata, min_cell_pct=0.05)
ct.tl.spatial_communication(adata, database_name="cellchat", df_ligrec=df, dis_thr=200, heteromeric=True)
adata.obsm["commot-cellchat-sum-sender"]; adata.obsm["commot-cellchat-sum-receiver"]   # per-spot sent/received
```
- `dis_thr=200` — max signaling distance **in whatever units `adata.obsm["spatial"]` carries**, not µm. COMMOT computes `distance_matrix(obsm["spatial"], obsm["spatial"])` and thresholds that; for Visium those are full-resolution image **pixels**. Convert to your own units before choosing the number, or the one parameter COMMOT is worth using gets silently misscaled.
- `heteromeric=True` treats `_`-joined names as receptor complexes.
- Requires `obsm["spatial"]`, and calls `.X.toarray()` internally — a dense `.X` raises `AttributeError`.

## Failure Modes

- **Everything is "significant"** — *symptom:* thousands of LR pairs, or a dotplot showing every pair. *Diagnosis:* `corr_method=None` (no FDR) and/or the plot was filtered with `alpha=` rather than `pvalue_threshold`. *Fix:* `corr_method="fdr_bh"` in `gr.ligrec`, and `pvalue_threshold=0.05` + `remove_nonsig_interactions=True` in `pl.ligrec`. Raising `threshold` does *not* fix this — it filters on expression, not significance.
- **`AttributeError: No .raw attribute found`** — *symptom:* `gr.ligrec` errors immediately. *Diagnosis:* `use_raw` defaults to `True`. *Fix:* pass `use_raw=False` and make sure `.X` is normalized but not scaled.
- **Results change between runs / fail offline** — *symptom:* different LR hits than last month, or a network error in `.prepare()`. *Diagnosis:* `interactions=None` re-fetches OmniPath every call. *Fix:* fetch once, pass `interactions=`, record the resource + fetch date.
- **Implausible interactions** (types that can't touch) — *symptom:* spatially distant types "communicating". *Diagnosis:* expression-only ligrec ignores location. *Fix:* restrict to spatially adjacent pairs (`nhood_enrichment`), or use COMMOT's `dis_thr`.
- **COMMOT env collision** — *symptom:* solver conflicts installing it. *Diagnosis:* v0.0.3 with Python ≤3.9 classifiers and pysal/karateclub/rpy2 in its tree — not a version pin on anndata/pandas. *Fix:* dedicated env; never `task2`.

## Figure checkpoints

1. **Ligrec dotplot** (`sq.pl.ligrec`) — are the top source→target pairs biologically plausible (e.g. immune→epithelial)?
2. **COMMOT sender/receiver maps** — does sent/received signal localize to the expected interface regions?

## Grounding

Record: method, `cluster_key`, `n_perms` / `threshold` / **`corr_method`** (ligrec) or `database` / `dis_thr` **and its units** (COMMOT), top significant LR pairs (source, target, pair), and — critically — **the resource and when you fetched it**. OmniPath is unversioned and mutable, so "CellPhoneDB test on OmniPath, fetched 2026-07-15" is the only form of that claim that anyone can reproduce. Put these in a `report` dict and cite its numbers.

## Honesty

- **LR co-expression ≠ proven signaling** — these are hypotheses; spatial proximity strengthens but doesn't prove them.
- Restrict claims to **spatially adjacent** type pairs — expression-only ligrec will pair types that never touch.
- COMMOT directionality is an OT inference, not measured flow — present it as such.
- **Name the resource, not just the method.** "CellPhoneDB" describes the permutation test; the interactions came from OmniPath. Which database was used determines which interactions could be found at all, so a CCC claim without the resource + fetch date is not checkable.
