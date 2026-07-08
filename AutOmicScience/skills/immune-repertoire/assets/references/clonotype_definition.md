# Clonotype / clone definition (paired-chain, cross-donor comparable)

Define clonotypes from the **receptor sequence** using **both** chains — not a vendor per-sample
clonotype ID (`P1 clonotype12` ≠ `P2 clonotype12`; unique only within one sample, so it silently
breaks cross-donor "public" discovery). Two engines: scirpy (flexible distance metrics) and
dandelion (`find_clones`, tied to its preprocessing/lineage).

## scirpy — `ir.pp.ir_dist` + `ir.tl.define_clonotype(_clusters)`

Compute a pairwise sequence distance, then partition it. **`sequence` + `metric` must match across
`ir_dist`, `define_clonotype_clusters`, and `clonotype_network`.**

**TCR — exact paired identity** (nucleotide):
```python
ir.pp.ir_dist(mdata)                                            # defaults metric="identity", sequence="nt"
ir.tl.define_clonotypes(mdata, receptor_arms="all", dual_ir="primary_only")   # -> clone_id, clone_id_size
```
`define_clonotypes` is `define_clonotype_clusters` pinned to nt/identity/connected; it auto-runs
`ir_dist` if missing.

**TCR — similarity clusters** (amino-acid, tcrdist):
```python
ir.pp.ir_dist(mdata, metric="tcrdist", sequence="aa", cutoff=15)
ir.tl.define_clonotype_clusters(mdata, sequence="aa", metric="tcrdist",
                                receptor_arms="all", dual_ir="any")   # -> cc_aa_tcrdist
```

**BCR — SHM-aware similarity** (~85%, same V+J; exact identity is wrong for hypermutated BCR):
```python
ir.pp.ir_dist(mdata, metric="normalized_hamming", sequence="nt", cutoff=15)   # 15 ≈ 85% junction similarity
ir.tl.define_clonotype_clusters(mdata, sequence="nt", metric="normalized_hamming",
    receptor_arms="all", dual_ir="any", same_v_gene=True, same_j_gene=True,
    partitions="fastgreedy", key_added="clone_id")
```

Parameter semantics (defaults in parentheses):

| Param | Meaning | For exact paired identity |
|-------|---------|---------------------------|
| `receptor_arms` (`all`) | `all`=both VJ+VDJ chains match; `any`=either; `VJ`/`VDJ`=one arm | `all` |
| `dual_ir` (`any`) | `all`=primary+secondary match; `primary_only`=dominant chain per arm; `any`=either | `primary_only` (TCR) / `any` (BCR) |
| `same_v_gene` (`False`), `same_j_gene` (`False`) | require identical V / J gene | `True` (esp. BCR) |
| `sequence` (`aa`), `metric` (`identity`) | CDR3 aa vs nt; `identity`/`tcrdist`/`normalized_hamming`/`levenshtein`/… | `identity` for exact |
| `within_group` (`receptor_type`) | only match within a category (needs `chain_qc`); set to a donor column to **forbid public clonotypes** at definition | `receptor_type` or `None` |
| `partitions` (`connected`) | graph partitioning; `fastgreedy` for BCR clusters | — |

Output: `clone_id` (+ `clone_id_size`) for `define_clonotypes`; `cc_{sequence}_{metric}` for
`define_clonotype_clusters` unless `key_added` given.

## dandelion — `ddl.tl.find_clones`

```python
ddl.tl.find_clones(vdj, identity=0.85)          # junction Hamming; writes clone_id to .data, rebuilds .metadata
# identity may be per receptor type, e.g. {"ig": 0.85, "tr-ab": 1, "tr-gd": 1}
ddl.tl.generate_network(vdj, min_size=2)        # V(D)J graph/layout/distances (lineage, centrality)
```

Default clustering key is `junction_aa` for Ig, `junction` for TCR. For BCR, `ddl.tl.define_clones`
(changeo `DefineClones.py`) is an alternative that ties into dandelion's germline/SHM machinery
(needs the container / R).

## Choosing

- **scirpy** when you want flexible distance metrics (tcrdist, normalized_hamming), the downstream
  repertoire analytics (expansion/public/diversity/overlap), or epitope-DB queries.
- **dandelion** when clone calling should sit with its preprocessing + BCR lineage/SHM (a
  reannotated `Dandelion` object flowing into `generate_network`).
- Either way, key on paired chains + V/J; state the choice (arms, aa/nt, metric, same V/J) in the report.
