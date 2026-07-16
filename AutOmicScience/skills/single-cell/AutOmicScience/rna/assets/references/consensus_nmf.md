# Gene Programs — Consensus NMF (cNMF)

**Maturity: PARTIAL** — no compute subcommand, and `cnmf` is **not** in the pinned `task1` env, so it must
be **provisioned into its own environment** first: follow `omics-shared`'s
`assets/references/AOSE_nonStandard_env.md` (§A — a `cnmf` feature + env with its own `solve-group`; §B a
**named** conda env if the solve fails). Never a bare `pip install` — the machine's `pip` may point at
conda `base` — and never add it to `task1`. Then run it in a Python script, emit a `report` dict and
`print(report)` to stay grounded; record the env + version there, since `omics_preflight` does not cover
non-standard envs. API below verified against **cNMF v1.7.1** (`dylkot/cNMF`, rev `5dbc5ba`).

**This doc owns continuous gene programs.** For discrete labels see `annotation.md`; for "which genes
mark cluster X" see `markers_de.md`. Programs and cell types answer different questions — both can be
true of the same cell at once.

## Goal / When to Use

A Leiden label gives each cell **one** identity. A cell actually runs several transcriptional programs
at once — a lineage program *and* cell cycle *and* an interferon response — and a clustering cannot
express that: it must either split the cell off into a "cycling" cluster or lump it. cNMF factors the
expression matrix into `X ≈ W × H`:

- **spectra** (programs × genes) — what each program *is*, as a ranked gene set
- **usage** (cells × programs) — how much each cell *uses* each program, continuously

Use it when a cluster looks like two things at once, when a state (cycling, hypoxia, IFN) cuts across
several cell types, or when you want gene modules instead of labels. The hard part is not the
factorization — it is choosing **k**.

## Decision Criteria

- **Discrete identity, one label per cell** → Leiden + `annotation.md`. Not this doc.
- **Continuous, co-occurring states** → cNMF (here).
- **A signature you already know** → score it directly with `pathway_activity` (`functional.md`).
  Don't rediscover a known program with NMF.
- **Recurrence across datasets** → run cNMF per dataset, then cluster the resulting spectra across
  datasets to find **metaprograms**. Never pool raw counts from several datasets into one run — the
  batch effect becomes the strongest "program".

## Workflow

`prepare` takes a **path**, not an AnnData — it reads the file itself and dispatches on the extension.
It also does its **own** HVG selection and variance normalization, so feed it **raw counts** and let
`num_highvar_genes` control the gene set. Do not pre-filter to HVGs and do not pre-normalize.

```python
import numpy as np, scanpy as sc
from cnmf import cNMF

adata.write_h5ad("counts_for_cnmf.h5ad")        # raw counts in X

cnmf_obj = cNMF(output_dir="./cnmf_out", name="programs")
cnmf_obj.prepare(counts_fn="counts_for_cnmf.h5ad",
                 components=np.arange(5, 11),   # the k values to scan
                 n_iter=20,                     # NMF replicates per k
                 seed=14,                       # REQUIRED — defaults to None
                 num_highvar_genes=2000)        # cNMF picks the HVGs itself
cnmf_obj.factorize(worker_i=0, total_workers=1) # parallelize by splitting worker_i over total_workers
cnmf_obj.combine()
cnmf_obj.k_selection_plot(close_fig=False)      # observe this BEFORE choosing k
```

Choose `k` from that plot (next section), then run consensus and load:

```python
cnmf_obj.consensus(k=selected_k, density_threshold=2.00, show_clustering=True)  # pass 1: see histogram
cnmf_obj.consensus(k=selected_k, density_threshold=0.10, show_clustering=True)  # pass 2: filter outliers

usage, spectra_scores, spectra_tpm, top_genes = cnmf_obj.load_results(
    K=selected_k, density_threshold=0.10)
# usage          cells × k, normalized to sum to 1 per cell
# spectra_scores k × genes, z-scored (high = better marker for that program)
# top_genes      ranked marker genes per program — already computed, don't hand-roll it
```

## Choosing k — stability vs error, and it is a judgement

`k_selection_plot` writes a two-axis figure: **Stability** (blue — the silhouette score of the
clustered replicate spectra) and **Error** (red — Frobenius reconstruction error) against k. Error
falls monotonically with k, so it is not a criterion on its own. Upstream's own rule:

> "There is no universally definitive criteria for choosing K but we will typically use the largest
> value that is reasonably stable and/or a local maximum in stability."
> — `Stepwise_Guide.md`, dylkot/cNMF

Take the largest k that is still reasonably stable, or a local stability maximum, and say which.

**cNMF does not compute a cophenetic coefficient.** That is Brunet et al. 2004's criterion for a
different consensus-NMF formulation (built on a sample × sample consensus matrix). cNMF's k-selection
lineage is Alexandrov et al. 2013. If a plan says "pick k where cophenetic peaks", it is not
describing cNMF — it is describing Brunet's, which is a different analysis on a different matrix and
is not blocked here: see `omics-shared`'s `assets/references/unsupervised_structure.md`.

## Choosing density_threshold — run consensus twice

`density_threshold` filters outlier replicate spectra by mean distance to their nearest neighbours
(`local_neighborhood_size=0.30` → 30% of replicates). The default `0.5` is not a recommendation, and
`2.00` filters nothing. Upstream's procedure is **two passes**: run at `2.00` to see the distance
histogram in the clustergram diagnostic plot, then set the threshold from that histogram and re-run.
Read the number off your own histogram — do not copy one from a doc, including this one.

## Failure Modes

1. **No seed → programs are not reproducible.** *Symptom:* re-running yields different programs; a
   reviewer cannot reproduce the figure. *Diagnosis:* `prepare(seed=...)` defaults to `None`, so every
   replicate starts from a fresh random state. *Fix:* always pass an explicit `seed` and record it.
   For a claim you intend to publish this is not optional.

2. **AnnData or array passed to `prepare`.** *Symptom:* `AttributeError: 'AnnData' object has no
   attribute 'endswith'`. *Diagnosis:* `counts_fn` is a path string; `prepare` dispatches on the file
   extension (`.h5ad` / `.mtx` / `.npz` / tab-delimited). *Fix:* write the object to disk, pass the path.

3. **Pre-filtered or pre-normalized input.** *Symptom:* programs look flat or a few genes dominate
   every one. *Diagnosis:* `prepare` already reduces to high-variance genes and variance-normalizes;
   handing it log-normalized or HVG-subset data normalizes twice. *Fix:* pass raw counts and control
   the gene set with `num_highvar_genes` (or `genes_file`).

4. **k chosen off the error curve.** *Symptom:* the selected k is the top of the scanned range.
   *Diagnosis:* reconstruction error decreases monotonically with k, so "minimize error" always picks
   the maximum. *Fix:* choose on **stability**; use error only to reject a k that buys no fit.

5. **density_threshold left at the default.** *Symptom:* a program's top genes read as a mixture of two
   unrelated modules. *Diagnosis:* outlier replicate spectra were folded into the consensus. *Fix:* the
   two-pass procedure above.

6. **A program read as a cell type.** *Symptom:* "program 3 is a macrophage population". *Diagnosis:*
   usage is continuous — every cell has some of every program; a program is not a partition. *Fix:*
   describe programs as programs ("cells high in program 3 span clusters 2 and 5"); for discrete types
   go to `annotation.md`.

## Figure checkpoints

- **k selection plot** — is there a stability plateau or local maximum at all? A monotonically
  decreasing stability curve means no k is well supported; say that instead of picking one anyway.
- **Clustergram + distance histogram** (`consensus(..., show_clustering=True)`) — is there a visible
  outlier tail to cut? This is the figure that sets `density_threshold`.
- **Usage on the UMAP**, one panel per program — does a program concentrate somewhere, or smear across
  everything? A smeared program is usually technical (depth, mito).
- **Program top genes** — a coherent module, or two modules glued together?

Observe each before it backs a claim.

## Interpreting programs

Annotate a program's top genes through the READY path — **not** gseapy, which is not in the pinned env:

```python
gene_list = ",".join(top_genes[program_id].dropna().head(50))
# omics_compute(subcommand="enrichment", modality="scrna",
#               args={"gene-list": gene_list, "output": "prog_enrich.json",
#                     "method": "ora", "resource": "msigdb", "organism": "human"})
```

A program's top 50 genes is exactly the "focused, biologically meaningful list" that subcommand wants
— see `functional.md` §2 for the background rule.

## Grounding

Build the `report` from the run (do not hardcode), then `print(report)`:

```python
import cnmf
report = {
    "method": "cnmf",
    "cnmf_version": cnmf.__version__,
    "seed": 14,
    "n_iter": 20,
    "components_scanned": list(range(5, 11)),
    "k_selected": int(selected_k),
    "k_rationale": "largest k on the stability plateau (stability=..., error=...)",
    "density_threshold": 0.10,
    "num_highvar_genes": 2000,
    "n_cells": int(usage.shape[0]),
    "top_genes_per_program": {c: list(top_genes[c].dropna().head(10)) for c in top_genes.columns},
}
report
```

`seed`, `n_iter`, `k`, and `density_threshold` are the four numbers that make a cNMF result
checkable. A program list without them cannot be reproduced by anyone — including you, next week.

## Honesty

- **k is a judgement, not a discovery.** Upstream states there is no definitive criterion. Report the
  k you chose, the stability at that k, and whether a neighbouring k was equally defensible.
- **Programs are not cell types.** Usage is continuous and every cell uses every program to some
  degree. "Cells high in program 3" is a claim; "program 3 cells" is not.
- **A program is not a mechanism.** "IFN-response program" names a correlated gene module, not a
  causal pathway.
- **Program identity depends on k and density_threshold.** Change either and programs split, merge, or
  disappear. Never present a program as an intrinsic property of the tissue without naming both.
- **Metaprograms need independent datasets.** Recurrence across samples from a single study mostly
  demonstrates that the study is internally consistent.
