# Clonal expansion, public clonotypes, phenotype linkage

**Maturity: depends on your input, not on scirpy.**

- **Input is already a per-cell table with a `clone_id` and a donor column** → **REFERENCE**, pinned.
  Expansion and public-clonotype counting are `groupby`s on `adata.obs` (or a plain DataFrame); the
  scirpy calls below are conveniences over the same operation, not requirements.
- **You still need to *build* `clone_id` from chains** → see `clonotype_definition.md`. Distance-based
  clustering needs scirpy; **exact-identity matching does not** — it is a string key and a `groupby`.

`scirpy` is in no pinned env (`task1–4`). When you do need it, provision it into its own
environment per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`, which carries the
routing and the hard rules.

Downstream of a sequence-defined `clone_id` (see `clonotype_definition.md`). Two distinct concepts:
**expansion** = within-donor clonal size; **public** = cross-donor sharing. Don't conflate them.

> obs keys: examples use a bare AIRR **AnnData** (`adata.obs`, keys `clone_id` / `patient`). On a
> **MuData**, use `mdata.obs` with `airr:` / `gex:` prefixes (e.g.
> `mdata.obs.groupby("airr:clone_id")["gex:patient"]`).

## 1. Clonal expansion (per donor)

```python
import scirpy as ir
ir.tl.clonal_expansion(adata, target_col="clone_id", expanded_in="patient")   # obs["clonal_expansion"] bins, within donor
sizes = ir.tl.group_abundance(adata, groupby="patient", target_col="clone_id") # donor × clonotype counts
# dandelion equivalent: ddl.tl.clone_size(vdj, max_size=3) -> Rare/Small/…/Hyperexpanded categories
```

`group_abundance(target_col="clone_id")` gives per-donor clonotype cell counts (there is **no**
`clonotype_abundance` function). **Per-donor minimum cell filter** — require a minimum number of
cells **within a donor**, applied per `(donor, clonotype)`, never pooled:

```python
per = adata.obs.groupby(["patient", "clone_id"], observed=True).size().rename("n_cells").reset_index()
robust = per[per.n_cells >= 10]                    # (donor, clonotype) pairs passing the threshold
```

## 2. Public / shared clonotypes across donors

scirpy has no dedicated helper — count distinct donors per clonotype on the sequence-defined key:

```python
donors_per_clone = adata.obs.groupby("clone_id", observed=True)["patient"].nunique()
public_clones = donors_per_clone.index[donors_per_clone >= 2]      # shared by >= 2 donors
```

(To *forbid* public clonotypes at definition time instead, pass `within_group="patient"` to
`define_clonotype_clusters`.) When the question wants **robustly expanded, public** clonotypes, keep
clonotypes that are public **and** pass the per-donor min-cell threshold in the donors carrying them.

Report each public clonotype's **full paired receptor spec** (both chains' V/J + CDR3). In scirpy,
per-chain values aren't in `obs` — pull them with the getter:

```python
for chain in ("VJ_1", "VDJ_1"):
    for var in ("v_call", "j_call", "junction_aa"):
        adata.obs[f"{chain}_{var}"] = ir.get.airr(adata, var, chain)
spec = (adata.obs[adata.obs.clone_id.isin(public_clones)]
        .groupby("clone_id")[[f"{c}_{v}" for c in ("VJ_1","VDJ_1") for v in ("v_call","j_call","junction_aa")]]
        .first())
```

(In dandelion, `vdj.metadata` already carries the collapsed per-cell V/J/CDR3 columns.)

## 3. Prioritization

Rank public candidates by a **clinical grouping** of interest (e.g. responders vs non-responders —
any obs column) and by per-donor expansion. Keep the ranking criterion explicit and data-driven, not
an assumed answer.

## 4. Phenotype linkage

Connect clonality to GEX cell state:

```python
xt = adata.obs.groupby(["clone_id", "cell_type"], observed=True).size().unstack(fill_value=0)
# dandelion: ddl.tl.transfer(adata, vdj) moves clone info into adata.obs / .obsm["X_vdj"] for GEX plots
```

(For repertoire-level summaries, scirpy has `alpha_diversity` / `repertoire_overlap` and dandelion
has `clone_diversity` / `clone_overlap` — use them only when the question asks for diversity/overlap.)

## 5. Reporting

- n cells / n with a productive paired receptor / n donors; the clonotype definition used.
- Expansion: per-donor size distribution; any per-donor min-cell threshold.
- Public clonotypes: count; per candidate the paired receptor spec, donors carrying it, per-donor
  cell counts; the prioritization criterion.
- Figures/networks inspected before they back a claim.
