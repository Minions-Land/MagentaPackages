---
name: immune-repertoire
description: Single-cell immune repertoire (AIRR-seq) analysis with dandelion + scirpy — raw 10x V(D)J contig preprocessing/reannotation (IgBLAST/TIgGER), contig QC, paired scTCR/scBCR clonotype definition from CDR3 + V/J across both chains, clonal expansion, public / shared clonotype discovery across donors, BCR somatic-hypermutation / isotype / clonal-lineage analysis, and linkage of clonality to GEX cell state. Use when you have T-cell or B-cell receptor data (10x VDJ contigs, AIRR rearrangement tables, or per-cell paired-chain annotations) and need to reannotate/QC it, define clonotypes, quantify expansion, find clonotypes shared across patients, analyze BCR mutation/lineage, or connect receptor clonality to cell phenotype.
requiredTools: [run_python, bash, read, write, observe_figure]
evidencePolicy: required
outputSchema: grounded_response
minConfidence: medium
tags: [immune-repertoire, airr, sctcr, scbcr, tcr, bcr, clonotype, clonal-expansion, public-clonotype, shm, dandelion, scirpy, single-cell]
extends: omics-shared
---

# Immune Repertoire (AIRR-seq) Analysis — dandelion + scirpy

Analyze single-cell adaptive immune receptor repertoires with the two field-standard scverse tools,
which are **complementary** and **interoperate**:

- **`dandelion`** (`sc-dandelion`) — owns **upstream**: reannotating raw 10x V(D)J contigs
  (IgBLAST + TIgGER + constant-gene BLAST), contig QC, and **BCR-specific** biology (somatic
  hypermutation, isotype/class-switch, germline reconstruction, clonal lineage networks). Also does
  clone calling, V(D)J networks, and GEX transfer.
- **`scirpy`** (`ir`) — owns **downstream repertoire analytics** on annotated AIRR held in a MuData:
  distance-based clonotype definition, clonal expansion, public/shared clonotypes, diversity,
  repertoire overlap, gene-usage, and epitope-database queries; scanpy-native.

Builds on `omics-shared` (loaded automatically). This is **repertoire** analysis — for the GEX side
(clustering/annotating the T/B cells) use the `single-cell` skill and join the two in a MuData.

---

## Domain background (read once)

- A **clonotype** is cells descending from one lymphocyte, sharing receptor sequence. For
  cross-individual comparison it must be defined **from the receptor sequence** — paired **VJ-arm**
  (TRA/IGK/IGL) + **VDJ-arm** (TRB/IGH) CDR3 + V/J genes — **not** a vendor per-sample clonotype ID,
  which is unique only within one sample.
- **Clonal expansion** = a clonotype occupying many cells **within** a donor. **Public clonotype** =
  the same sequence-defined receptor in **≥2 donors**. Keep the two separate.
- **TCR vs BCR** differ in method: TCR clonotypes use exact or `tcrdist` matching; **BCR** undergoes
  **somatic hypermutation (SHM)**, so exact-identity is meaningless — cluster by sequence
  *similarity* (e.g. ~85%) with same V+J, and reannotate contigs first (CellRanger output lacks the
  IMGT numbering SHM/phylogenetics need).
- scirpy's data model (v0.13+) stores chains in `adata.obsm["airr"]` (awkward array) + `chain_indices`;
  it operates on a **MuData** `{"gex": …, "airr": …}` and defaults to the `airr` modality.

---

## Prerequisites

1. **Receptor data**: raw 10x V(D)J (`filtered_contig_annotations.csv`+`.fasta`), an AIRR
   rearrangement `.tsv`, or a per-cell table already annotated with both chains' V/J/CDR3.
2. **Cell metadata**: at minimum a donor/patient column; ideally a GEX cell-type/state column.
3. **Libraries** — `pip install scirpy sc-dandelion` (scirpy ≥ 0.21, Python ≥ 3.12). Set dandelion's
   mature backend once: `ddl.set_backend("base")` (default is `auto`→polars). Raw-contig
   **reannotation** additionally needs dandelion's **Singularity/Docker container** (IgBLAST, BLAST,
   changeo, TIgGER, R/SHazaM, germline DBs); all **downstream** steps are pure-Python.

```python
import scirpy as ir
import dandelion as ddl; ddl.set_backend("base")
```

---

## Capability Menu

| Capability | Tool | Entry point | Reference Doc |
|------------|------|-------------|---------------|
| Raw 10x contig reannotation (IgBLAST/TIgGER) | dandelion (container) | `dandelion-preprocess` / `ddl.pp.*` | `assets/references/preprocessing_dandelion.md` |
| Contig QC / ambiguity filtering | dandelion | `ddl.pp.check_contigs` | `assets/references/preprocessing_dandelion.md` |
| BCR SHM / isotype / germline / lineage | dandelion | `ddl.pp.quantify_mutations`, `assign_isotypes`, `ddl.tl.generate_network` | `assets/references/preprocessing_dandelion.md` |
| Load annotated AIRR; tool interop | both | `ir.io.read_airr` / `ddl.read_airr` / `ddl.tl.to_scirpy` ↔ `ir.io.from_dandelion` | `assets/references/data_loading.md` |
| Paired-chain clonotype definition | scirpy | `ir.pp.ir_dist` + `ir.tl.define_clonotype(_clusters)` | `assets/references/clonotype_definition.md` |
| Clone calling by junction identity | dandelion | `ddl.tl.find_clones` (`ddl.tl.define_clones` for BCR) | `assets/references/clonotype_definition.md` |
| Clonal expansion / clone size | both | `ir.tl.clonal_expansion` / `ddl.tl.clone_size` | `assets/references/clonal_and_public.md` |
| Public / shared clonotypes across donors | scirpy + pandas | groupby `clone_id` × donor | `assets/references/clonal_and_public.md` |
| Clonality → GEX phenotype linkage | both | `ddl.tl.transfer` / `ir.get.airr_context` | `assets/references/clonal_and_public.md` |

Read the method doc before running each capability.

---

## Standard Workflow — pick the entry point

### Path A — raw 10x contigs (or any BCR data): reannotate with dandelion first

```bash
# containerized reannotation (IG by default; add --chain TR for TCR incl. gamma/delta)
singularity run -B $PWD sc-dandelion_latest.sif dandelion-preprocess --file_prefix filtered
```

```python
import dandelion as ddl; ddl.set_backend("base")
import scanpy as sc
vdj = ddl.read_airr("dandelion/filtered_contig_dandelion.tsv")   # reannotated AIRR
adata = sc.read_h5ad("gex.h5ad")                                  # scanpy-processed GEX
vdj, adata = ddl.pp.check_contigs(vdj, adata)                    # QC / ambiguity filter
```

Then either analyze in dandelion (`find_clones`/`generate_network`/SHM) or hand a clean object to
scirpy via `ddl.tl.to_scirpy(vdj, to_mudata=True, gex_adata=adata)`. See
`assets/references/preprocessing_dandelion.md`.

### Path B — already-annotated per-cell AIRR: straight to scirpy

For a per-cell table with both chains' V/J/CDR3 already annotated, load it into scirpy directly (no
reannotation needed). See `assets/references/data_loading.md` for the wide→long load.

```python
import scirpy as ir
adata = ir.io.read_airr(wide_to_airr(df_cells))   # AIRR AnnData; attach cell-state cols to adata.obs
# if you also have a GEX count matrix: mdata = mu.MuData({"gex": adata_gex, "airr": adata})
ir.pp.index_chains(adata)          # -> obsm["airr"]["chain_indices"] (VJ_1/2, VDJ_1/2)
ir.tl.chain_qc(adata)              # -> receptor_type / chain_pairing
```

### Define clonotypes (scirpy)

```python
# TCR, exact paired identity:
ir.pp.ir_dist(adata)                                            # nt identity (default)
ir.tl.define_clonotypes(adata, receptor_arms="all", dual_ir="primary_only")   # -> clone_id
# BCR, ~85% similarity with same V+J (SHM-aware):
ir.pp.ir_dist(adata, metric="normalized_hamming", sequence="nt", cutoff=15)
ir.tl.define_clonotype_clusters(adata, metric="normalized_hamming", sequence="nt",
    receptor_arms="all", dual_ir="any", same_v_gene=True, same_j_gene=True,
    partitions="fastgreedy", key_added="clone_id")
```

`sequence`/`metric` must match across `ir_dist`, `define_clonotype_clusters`, and
`clonotype_network`. See `assets/references/clonotype_definition.md`.

### Downstream: expansion, public clonotypes, phenotype

```python
ir.tl.clonal_expansion(adata, target_col="clone_id", expanded_in="patient")   # per-donor bins
donors = adata.obs.groupby("clone_id", observed=True)["patient"].nunique()
public = donors.index[donors >= 2]                               # shared by >= 2 donors
```

(On a MuData, use `mdata.obs` with `airr:`/`gex:` prefixes.) See
`assets/references/clonal_and_public.md`. Inspect any expansion/network plot before it backs a
claim; cite dandelion and scirpy.

---

## Choosing dandelion vs scirpy

| Situation | Tool |
|-----------|------|
| Raw contigs need reannotation; any BCR data | **dandelion** (preprocess), then either tool |
| BCR SHM %, isotype/class-switch, germline, lineage trees | **dandelion** (no scirpy equivalent for reannotation-grade SHM) |
| Distance-based clonotype clusters (tcrdist), expansion, public, diversity, overlap, epitope query | **scirpy** |
| Already-annotated per-cell AIRR, TCR downstream | **scirpy** (fast path) |
| Move between them | `ddl.tl.to_scirpy` / `ir.io.from_dandelion` (needs `sc-dandelion`) |

---

## Best Practice (on top of omics-shared)

- **Sequence-defined clonotypes** — paired CDR3 + V/J; never a vendor per-sample clonotype ID for
  cross-donor work (state this in the write-up).
- **Reannotate before BCR analysis** — CellRanger BCR output lacks IMGT numbering; reannotate with
  dandelion (or airrflow/Immcantation) before clonotype/SHM work.
- **TCR = exact/tcrdist; BCR = similarity + same V/J** — don't apply exact identity to hypermutated BCR.
- **Per-donor granularity** — expansion and any per-donor min-cell filter are within each donor;
  public sharing is across donors (`≥2`). Keep them distinct.
- **Match `sequence`/`metric`** across `ir_dist` / `define_clonotype_clusters` / `clonotype_network`.
- **`ddl.set_backend("base")`** once after import (the default backend is not the mature one).

---

## Pitfalls

- **Vendor clonotype IDs across donors** — `P1 clonotype1` ≠ `P2 clonotype1`; not comparable.
- **Exact identity on BCR** — SHM makes it wrong; cluster by similarity (`normalized_hamming`) + same V/J.
- **Raw CellRanger BCR into a mutation/lineage analysis** — invalid without IMGT reannotation.
- **`filter_contigs`** — removed from dandelion's current API; use **`check_contigs`**.
- **Mismatched `sequence`/`metric`** between the distance and clonotype steps — silently wrong clusters.
- **Skipping `index_chains`** — scirpy `tl.*` clonotype functions need `obsm["airr"]["chain_indices"]`.
- **Stale scirpy API** — `from_airr` / `clonotype_abundance` / `IR_VJ_1_*` columns don't exist; use
  `read_airr`, `group_abundance`, `ir.get.airr`.

---

## Evidence & Reporting

Every analysis emits:
- **Inputs**: n cells, n with a productive paired receptor, n donors; reannotation status; the
  clonotype definition used (arms, aa/nt, metric, same V/J).
- **Expansion**: per-donor clonotype size distribution; any per-donor min-cell threshold.
- **Public clonotypes**: count and, per candidate, the full paired receptor spec (both chains'
  V/J + CDR3), donors carrying it, per-donor cell counts.
- **BCR (if applicable)**: SHM frequency per subregion, isotype distribution, lineage summary.
- **Phenotype**: clonotype × cell-state cross-tab where relevant.
- Inspect figures/networks before they back a claim; cite dandelion + scirpy.

See the reference docs for per-capability templates.
