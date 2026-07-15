# Contig preprocessing & BCR analysis with dandelion

**Maturity: PARTIAL** — `sc-dandelion` is **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Follow `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`: §A a new Pixi feature + environment with its **own solve-group** (preferred — lands in `pixi.lock`), or §B a **named** conda env if Pixi can't solve it. Never a bare `pip install` (it can land in `base`), and never add these pins to `task1–4`. `omics_preflight` does not cover non-standard envs — check the import yourself, and record the env + versions in the `report`. If it can be neither imported nor provisioned, that is a **blocker**, not a cue to substitute a weaker method.

dandelion owns the **upstream** of single-cell repertoire work that scirpy does not: reannotating
raw 10x V(D)J contigs to IMGT-numbered AIRR, contig QC, and BCR-specific biology (somatic
hypermutation, isotype, germline, lineage).

```python
import dandelion as ddl
```

> There is **no backend to select**. `ddl.set_backend()` does not exist in 0.5.7, in the 1.0.0a0
> pre-release, or on master (0 hits), and there is no polars backend — master's polars lines are all
> commented out. Calling it raises `AttributeError` on line 2.

## 1. Reannotate raw 10x contigs

CellRanger V(D)J output lacks the IMGT numbering that SHM/phylogenetics need, so reannotate first.
Two equivalent routes:

**(a) Container CLI (recommended — bundles IgBLAST/BLAST/changeo/TIgGER/R + germline DBs):**

```bash
singularity pull library://kt16/default/sc-dandelion:latest
# IG by default; add --chain TR for TCR (incl. gamma/delta), which skips the IG-only steps
singularity run -B $PWD sc-dandelion_latest.sif dandelion-preprocess --file_prefix filtered
```

Useful flags: `--chain {IG,TR}`, `--org`, `--db {imgt,ogrdb}`, `--flavour {strict,original}`,
`--filter_to_high_confidence`, `--skip_tigger`, `--meta <demux.csv>`. Output:
`dandelion/<prefix>_contig_dandelion.tsv` (AIRR — consumable by dandelion, scirpy, changeo).

**(b) Pure-API pipeline** (same steps the container runs; each wraps an external tool):

```python
ddl.pp.format_fastas(samples, prefix=samples, filename_prefix="filtered")  # rewrite headers (pure-python)
ddl.pp.reannotate_genes(samples, filename_prefix="filtered")               # IgBLAST + changeo MakeDb
ddl.pp.reassign_alleles(samples, combined_folder="tigger",                 # TIgGER personalized genotype
                        filename_prefix="filtered")
ddl.pp.assign_isotypes(samples, filename_prefix="filtered")                # blastn C-gene → c_call
for s in samples:
    ddl.pp.quantify_mutations(s + "/dandelion/filtered_contig_dandelion.tsv")  # SHM (SHazaM)
```

## 2. Load & QC

```python
import scanpy as sc
vdj = ddl.read_airr("dandelion/filtered_contig_dandelion.tsv")   # -> Dandelion (.data contigs, .metadata per-cell)
adata = sc.read_h5ad("gex.h5ad")                                 # scanpy-processed GEX
vdj, adata = ddl.pp.check_contigs(vdj, adata)                    # QC: flags `ambiguous`, resolves UMI dominance,
                                                                  # merges exact-match contigs, drops barcodes absent from adata
```

Readers: `ddl.read_airr` (AIRR tsv), `ddl.read_10x_vdj` (raw 10x csv/json), `ddl.read_10x_airr`
(CellRanger `airr_rearrangement.tsv`), `ddl.read_h5ddl` (native). Merge samples with `ddl.concat([...])`.
**Use `check_contigs`, not `filter_contigs`** — because it is the better filter, *not* because the old one
is gone: `filter_contigs` is still exported and undeprecated in the released 0.5.7 (it disappears only in
unreleased master), so "removed from the current API" would be a wrong reason for a right call.

## 3. BCR-specific analysis (dandelion's differentiators)

These wrap the immcantation R suite via rpy2 and need R + SHazaM/changeo (or the container):

```python
ddl.pp.create_germlines(vdj)                                     # reconstruct germline (changeo CreateGermlines)
ddl.pp.quantify_mutations(vdj)                                   # SHM load -> mu_count*/mu_freq* in .data
ddl.pp.quantify_mutations(vdj, frequency=True, combine=False)    # SHM frequency, R/S split
ddl.pp.calculate_threshold(vdj)                                  # SHazaM distToNearest -> clonal-distance cutoff
```

- **Isotype / class-switch**: `assign_isotypes` sets `c_call`; per-cell `isotype_status` /
  `locus_status` land in `.metadata` (plot with `ddl.pl.stackedbarplot(..., color="isotype_status")`).
- **Clonal lineage / network**: `ddl.tl.generate_network(vdj, min_size=2)` builds the V(D)J graph
  (`.graph`, `.layout`, `.distances`) used for lineage/centrality.

## 4. Hand off to scirpy (or stay in dandelion)

```python
mdata = ddl.to_scirpy(vdj, to_mudata=True, gex_adata=adata)   # MuData .mod['gex']/.mod['airr']
# or to_mudata=False -> AnnData with .obsm["airr"]; reverse: ddl.from_scirpy(mdata)
```

## What needs the container/external tools vs pure-Python

- **Container / IgBLAST+BLAST+changeo+TIgGER+R + germline DBs:** `reannotate_genes`,
  `reassign_alleles`, `assign_isotypes`, and the immcantation wrappers `quantify_mutations`,
  `create_germlines`, `calculate_threshold`, `define_clones`.
- **Pure-Python (no container):** all readers, `check_contigs`, `find_clones`, `generate_network`,
  `clone_size`, `clone_overlap`, `transfer`, `to_scirpy`/`from_scirpy`. So if you already have a
  reannotated `*_contig_dandelion.tsv`, the whole downstream runs without the container.

## Reporting

- Reannotation: tool/DB/org used, n contigs in/out of `check_contigs`, n flagged ambiguous.
- BCR: SHM frequency per subregion, isotype distribution, germline source, lineage/network summary.
