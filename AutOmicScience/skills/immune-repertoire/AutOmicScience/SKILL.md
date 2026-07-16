---
name: immune-repertoire
description: Single-cell immune repertoire (AIRR-seq) analysis with dandelion + scirpy — raw 10x V(D)J contig preprocessing/reannotation (IgBLAST/TIgGER), contig QC, paired scTCR/scBCR clonotype definition from CDR3 + V/J across both chains, clonal expansion, public / shared clonotype discovery across donors, BCR somatic-hypermutation / isotype / clonal-lineage analysis, and linkage of clonality to GEX cell state. Use when you have T-cell or B-cell receptor data (10x VDJ contigs, AIRR rearrangement tables, or per-cell paired-chain annotations) and need to reannotate/QC it, define clonotypes, quantify expansion, find clonotypes shared across patients, analyze BCR mutation/lineage, or connect receptor clonality to cell phenotype.
requiredTools: [run_python, bash, read, write, observe_figure]
tags: [immune-repertoire, airr, sctcr, scbcr, tcr, bcr, clonotype, clonal-expansion, public-clonotype, shm, dandelion, scirpy, single-cell]
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
3. **Libraries** — neither `scirpy` nor `sc-dandelion` is in a pinned env; provision them per
   `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` — one env of your own with both specs
   (`scirpy` ≥ 0.21, `sc-dandelion`; Python ≥ 3.12). Never a bare `pip install`. dandelion's **reannotation** additionally
   needs dandelion's **Singularity/Docker container** (IgBLAST, BLAST, changeo, TIgGER, R/SHazaM,
   germline DBs) — a container case, and a blocker to report if unavailable; all **downstream** steps are
   pure-Python.

> **Pin `sc-dandelion` to 0.5.7 and index accordingly.** The released 0.5.7 exports `to_scirpy`/
> `from_scirpy`/`concat` at **top level** (`ddl.to_scirpy(...)`); unreleased master moves them under
> `ddl.tl`. Docs that mix the two eras describe no installable version. Prefer scirpy's version-tolerant
> `ir.io.from_dandelion(vdj, ...)` where it exists.

---

## Capability Menu

| Capability | Maturity | Tool | Entry point | Reference Doc |
|------------|----------|------|-------------|---------------|
| Raw 10x contig reannotation (IgBLAST/TIgGER) | **PARTIAL** — container | dandelion (container) | `dandelion-preprocess` / `ddl.pp.*` | `assets/references/preprocessing_dandelion.md` |
| Contig QC / ambiguity filtering | **PARTIAL** — not pinned | dandelion | `ddl.pp.check_contigs` | `assets/references/preprocessing_dandelion.md` |
| BCR SHM / isotype / germline / lineage | **PARTIAL** — not pinned | dandelion | `ddl.pp.quantify_mutations`, `assign_isotypes`, `ddl.tl.generate_network` | `assets/references/preprocessing_dandelion.md` |
| Load annotated AIRR; tool interop | **PARTIAL** — not pinned | both | `ir.io.read_airr` / `ddl.read_airr` / `ddl.to_scirpy` ↔ `ir.io.from_dandelion` | `assets/references/data_loading.md` |
| Paired-chain clonotype definition | **PARTIAL** — not pinned | scirpy | `ir.pp.ir_dist` + `ir.tl.define_clonotype(_clusters)` | `assets/references/clonotype_definition.md` |
| Clone calling by junction identity | **PARTIAL** — not pinned | dandelion | `ddl.tl.find_clones` (`ddl.tl.define_clones` for BCR) | `assets/references/clonotype_definition.md` |
| Clonal expansion / clone size | **REFERENCE** — pandas, given a `clone_id` | pandas (or `ir.tl.clonal_expansion` / `ddl.tl.clone_size`) | groupby `(donor, clone_id)` | `assets/references/clonal_and_public.md` |
| Public / shared clonotypes across donors | **REFERENCE** — pandas, given a `clone_id` | pandas | groupby `clone_id` × donor | `assets/references/clonal_and_public.md` |
| Clonality → GEX phenotype linkage | **PARTIAL** — not pinned | both | `ddl.tl.transfer` / `ir.get.airr_context` | `assets/references/clonal_and_public.md` |

**What is gated is *building* the clonotype, not analysing it.** Reannotation needs dandelion's
container; distance-based clonotype clustering needs `scirpy`; neither is in `task1–4` (provision per
Prerequisites §3). But once each cell carries a sequence-defined `clone_id` and a donor label — which
an already-annotated table often does — expansion and public-clonotype analysis are `groupby`s on the
pinned stack. **Exact-identity clonotype matching also needs no scirpy**: it is a string key, and
`scirpy`'s `define_clonotype_clusters` is *distance*-based, so it answers a different question.

`omics_preflight` covers only `task1–4` — check the imports yourself and record the env + versions in
the `report`.

Read the method doc before running each capability.

---

## Standard Workflow — pick the entry point

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step. Everything here needs the
provisioned env (Prerequisites §3).

### Entry A — raw 10x contigs (BCR, or any SHM/lineage work)

Reannotate with dandelion's container first. CellRanger output lacks the **IMGT numbering** that SHM
quantification and phylogenetics need, so this step is not optional for BCR — and it is the one step
gated on Singularity/Docker. If the container is unavailable, that is a **blocker to report**.

→ `assets/references/preprocessing_dandelion.md`

### Entry B — an annotated AIRR table

Read AIRR directly and skip reannotation. Valid for TCR, and for BCR only if the table already carries
IMGT-numbered alignments.

- scirpy ≥0.13 stores chains in `adata.obsm["airr"]` (awkward array) + `chain_indices`, and operates
  on a **MuData** `{"gex":…, "airr":…}`, defaulting to the `airr` modality
- Interop runs through `ddl.to_scirpy` ↔ `ir.io.from_dandelion`

→ `assets/references/data_loading.md`

### 1. Define clonotypes

Distance-based clonotype calling: `ir.pp.ir_dist` then `ir.tl.define_clonotype(_clusters)`.

- **Define from the receptor sequence, never a vendor clonotype ID.** A per-sample ID is unique only
  within that sample, so cross-individual comparison built on it is meaningless
- Pair the **VJ-arm** (TRA/IGK/IGL) with the **VDJ-arm** (TRB/IGH) — CDR3 + V/J genes
- **TCR vs BCR is a real fork.** TCR: exact or `tcrdist` matching. BCR: somatic hypermutation makes
  exact identity meaningless — cluster by *similarity* (~85%) within the same V+J

→ `assets/references/clonotype_definition.md`

### 2. Clonal expansion and public clonotypes

- **Expansion** = one clonotype occupying many cells **within** a donor
- **Public** = the same sequence-defined receptor in **≥2 donors**
- These are different questions; keep them separate. Conflating them turns a big clone in one patient
  into a "public" response

→ `assets/references/clonal_and_public.md`

### 3. Link clonality to GEX phenotype

`ddl.tl.transfer` / `ir.get.airr_context` to carry receptor annotations onto the expression object.

→ `assets/references/clonal_and_public.md`

---

## Choosing dandelion vs scirpy

| Situation | Tool |
|-----------|------|
| Raw contigs need reannotation; any BCR data | **dandelion** (preprocess), then either tool |
| BCR SHM %, isotype/class-switch, germline, lineage trees | **dandelion** (no scirpy equivalent for reannotation-grade SHM) |
| Distance-based clonotype clusters (tcrdist), expansion, public, diversity, overlap, epitope query | **scirpy** |
| Already-annotated per-cell AIRR, TCR downstream | **scirpy** (fast path) |
| Move between them | `ddl.to_scirpy` / `ir.io.from_dandelion` (needs `sc-dandelion`) |

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
