---
name: gene-panel
description: 'End-to-end workflow for gene panel design in scRNA-seq and spatial transcriptomics,
  that should be **STRICTLY** followed: dataset understanding + smart downsampling
  + train/test splits, algorithmic selection (HVG/DE/RF/scGeneFit/SpaPROS), optimal
  sub-panel discovery (ARI vs size), biological completion with a stability gate (Completion
  Rule), consensus scoring and completion (only if there is still room), and benchmarking
  on test splits (ARI/NMI/Silhouette + UMAP similarity).'
tags:
- gene-panel
- selection
- scrna-seq
- spatial
- scanpy
- scverse
- benchmarking
- spapros
- scgenefit
- random-forest
source: PantheonOS
license: BSD-2-Clause
requiredTools:
- run_python
- create_notebook
- add_cell
- observe_figure
- read
- write
- edit
- find
- grep
- sub_agent
---

# Gene Panel Selection Workflow

Use this skill to construct **biologically meaningful** and **algorithmically robust** gene panels. Treat the user's request and the current Magenta session context as authoritative, and **STRICTLY** follow this **Gene Panel Selection Workflow**.

## Workflow Enforcement (MANDATORY)

Determine which stage of the workflow (Steps 1–5) is required for the current task,
and **STRICTLY** follow the corresponding step(s).

Once a step is entered, all its mandatory sub-steps must be executed.
No partial execution or silent degradation is allowed.



## Workdir
Always work in the workdir supplied by the user or parent session. If none is supplied, create a task-specific directory under the current workspace and report its path.

## Delegation in Magenta
Choose the smallest orchestration surface that preserves the task:

- Use native `web-search` and `web-fetch` directly for focused software or biological lookups. Use a one-shot `sub_agent` only when an independent research pass or a separate context window is useful.
- Use `bash` for short environment checks and `bg_shell` for long installs or computations. Do not delegate installation merely to imitate PantheonOS's former named system-manager role.
- Use a one-shot `sub_agent` with an explicit biology-review instruction for an independent interpretation of figures, panels, and intermediate results.
- Use a one-shot `sub_agent` with an explicit scientific-reporting instruction after the evidence and artifacts are complete. The parent session remains responsible for checking and delivering the report.
- Any `sub_agent` task that needs this workflow's skills or execution tools must set `packages: ["PantheonOS", "MagentaWithPantheonOS"]` in the request. Mentioning package names only in task prose does not grant them.
- Use `teammate_agent` only when the same collaborator must persist across multiple workflow stages; exchange assignments and results through `send_message`. `teammate_agent` currently has no `packages` parameter, so do not assign it work that depends on PantheonOS Package skills or tools.
- When several independent reviews can run concurrently and workflow support is enabled, use a `sub_agent` workflow (the Magenta multiagent capability). Otherwise issue ordinary one-shot `sub_agent` calls and synthesize their results yourself.

Never pass a PantheonOS role name as though Magenta exposes a named-agent registry. Give each delegated worker its role, inputs, artifact paths, expected output, and acceptance criteria in the task instruction.

## Files and visual checks
Use `read` for text and for PNG/JPEG/GIF/WebP images, `find` for file discovery, `grep` for content search, and `write`/`edit` for text artifacts. For every generated image:

1. Call `observe_figure(file_path=<figure path>, question=<specific semantic check>, expectation=<quality criterion>)`. It performs pixel preflight and a real vision-backed evaluation, returning `PASS`, `WARN`, or `FAIL`.
2. Accept the visual gate only on `PASS`. For `WARN` or `FAIL`, follow the returned `analysis` (and optional `observations` compatibility details), revise the figure, and rerun `observe_figure` until it passes or a documented blocker prevents correction.
3. When a second opinion or closer inspection is useful, call `read` on the image path so the current vision-capable model receives real ImageContent and checks legibility, clipping, contrast, panel consistency, and semantic content.
4. Use `show` only when a host preview is useful; it is not the model's semantic inspection channel.

A vision-backend failure is a tool error, not a semantic `WARN`. Do not fabricate a verdict when `observe_figure` fails to run.

## Reporting
At the end of the task, write a markdown report named:

`report_analysis.md`

The report **must** include:
- Summary
- Data (inputs, key parameters, outputs)
- Results (figures + tables)
- Key findings
- Next steps

## Large datasets
If the dataset is large, perform **smart downsampling** while preserving **all cell types**.

---

## Gene Panel Selection Hyperparameters
<!-- Defaults live as module-level constants at the top of
`assets/references/scripts/gene_panel_helpers.py`. To override for a specific call, pass
the value as a kwarg (e.g., `select_spapros(..., n_hvg=5000)`). No
global config file to edit. -->

| Constant (in `assets/references/scripts/gene_panel_helpers.py`) | Default | Description |
|---|---|---|
| `SCGENEFIT_MAX_CONSTRAINTS` | 1000 | Max LP constraints for scGeneFit |
| `SPAPROS_N_HVG` | 3000 | HVG pre-filter size for SpaPROS |
| `RF_N_ESTIMATORS` | 300 | Random Forest tree count |
| `SPAPROS_RUNTIME_WARNING_MINUTES` | 5.0 | Current session requests explicit user approval if the SpaPROS estimate exceeds this |
| `SPAPROS_RUNTIME_SKIP_MINUTES` | 30.0 | Strong-warning threshold; user may choose to skip SpaPROS |
| `ARI_DROP_THRESHOLD` | 0.05 | Max acceptable ARI degradation during panel completion |
| `DOWNSAMPLE_MAX_CELLS` | 500000 | Above this cell count, downsampling is required before selection |
| `GENE_COUNT_THRESHOLD` | 30000 | Above this gene count, gene subsetting is required before selection |
| `N_TRAINING_SPLITS` | 1 | Number of training datasets to build during the train/test split |
| `N_TEST_SPLITS` | 5 | Minimum number of test splits to build (more is fine) |
| `SPLIT_CELL_LIMIT` | 50000 | Target cells per test split (soft cap, preserve diversity) |

---

# Workflow (IMPORTANT : STRICLY FOLLOW NEEDED STEPS)

## 0. Dataset

**If the user provided an AnnData object / dataset path → skip to Step 1.**

If no dataset was provided, you **must** search and retrieve a relevant dataset
before proceeding. Follow the sub-steps below **in order**.

> [!IMPORTANT]
> Before starting, load the **`database-access`** skill (listed in the skills catalog)
> and follow the reference guides it points to (especially its CELLxGENE Census and gget guides).

### 0.1 Parse the user query
Extract search parameters from the user request and current session context:
- **Organism**: e.g., "Homo sapiens", "Mus musculus"
- **Tissue / organ**: e.g., "lung", "brain", "bone marrow", "tumor"
- **Disease context**: e.g., "COVID-19", "cancer", "normal"
- **Cell types of interest**: e.g., "immune cells", "T cells", "neurons"
- **Assay preference**: e.g., scRNA-seq, spatial transcriptomics
- **Scope**: Is this a **focused** task (single tissue/disease/system) or a **broad** task
  (multi-tissue, pan-disease, cross-system)? This is critical for dataset selection.

> [!CRITICAL]
> **Match dataset scope to task scope.** The dataset(s) you retrieve must be
> representative of the **full biological diversity** the panel is designed for.
> - **Focused task** (e.g., "brain cortex panel", "kidney disease panel") →
>   fetch data from that specific tissue/disease/system
> - **Broad / cross-tissue task** (e.g., "pan-cancer panel", "whole-body immune panel",
>   "multi-organ developmental panel") → you **must** include data from **all relevant
>   tissues, diseases, or biological contexts** so the panel captures both shared and
>   context-specific biology. **Do NOT narrow down to a single tissue or disease.**
> - In general: the biological diversity in the retrieved dataset should reflect the
>   biological diversity that the final gene panel must resolve. If the panel needs
>   to distinguish 10 tissues, the dataset must contain cells from those 10 tissues.

### 0.2 Search CELLxGENE Census (PRIMARY source)
CELLxGENE Census is the largest curated single-cell collection (217M+ cells)
and returns AnnData objects directly — **always try this first**.

See the **`database-access`** skill for the CELLxGENE Census access guide.

Strategy:

**A) First, look for existing atlases / large integrated datasets** that already match
the task scope. CELLxGENE hosts many curated cross-tissue and disease-specific atlases
(e.g., Tabula Sapiens, Human Cell Atlas collections, organ-specific atlases,
disease-focused atlases). A single well-curated atlas is far better than stitching
together cells from separate studies (avoids batch effects, inconsistent annotations, etc.).

```python
import cellxgene_census
with cellxgene_census.open_soma() as census:
    # List all datasets and inspect their descriptions
    datasets = census["census_info"]["datasets"].read().concat().to_pandas()
    # Browse dataset titles/collections to find relevant atlases
    print(datasets[["dataset_id", "collection_name", "dataset_title"]].head(30))
    # Score datasets by their biological diversity
    obs_df = cellxgene_census.get_obs(
        census, "<organism>",
        value_filter="is_primary_data == True",
        column_names=["dataset_id", "tissue_general", "disease", "cell_type"],
    )
    diversity = obs_df.groupby("dataset_id").agg(
        n_cells=("cell_type", "size"),
        n_tissues=("tissue_general", "nunique"),
        n_diseases=("disease", "nunique"),
        n_cell_types=("cell_type", "nunique"),
    ).sort_values("n_tissues", ascending=False)
    print(diversity.head(20))
```

Pick the dataset that best matches the task scope. For broad tasks, prioritize datasets
with highest tissue/disease/cell-type diversity. For focused tasks, prioritize relevance
to the specific tissue/disease. Prefer datasets with >50k cells and existing cell type annotations.

**B) If no single atlas suffices**, build a composite query across multiple tissues/diseases:

1. **Explore available data** — query cell metadata to estimate dataset sizes:
   ```python
   with cellxgene_census.open_soma() as census:
       obs_df = cellxgene_census.get_obs(
           census, "<organism>",
           value_filter="tissue_general == '<tissue>' and is_primary_data == True",
           column_names=["cell_type", "tissue", "tissue_general", "disease", "assay", "dataset_id"],
       )
       print(f"Total cells: {len(obs_df)}")
       print(obs_df["cell_type"].value_counts().head(20))
       print(obs_df["disease"].value_counts().head(10))
       print(obs_df["tissue_general"].value_counts().head(15))
   ```
2. **Refine filters — but preserve the task scope**:
   - For **broad tasks**: keep multiple tissues/diseases/contexts in the filter.
     Sample a **balanced** number of cells per category to avoid one dominating.
   - For **focused tasks**: narrow to the specific tissue/disease/context.
   - Always check the diversity of cell types, tissues, and diseases after filtering
     to confirm the dataset matches the task scope.

3. **Download the dataset** as AnnData:
   ```python
   with cellxgene_census.open_soma() as census:
       adata = cellxgene_census.get_anndata(
           census,
           organism="<organism>",
           obs_value_filter="<refined_filter> and is_primary_data == True",
           column_names={
               "obs": ["cell_type", "tissue", "tissue_general", "disease", "sex",
                        "assay", "donor_id", "dataset_id", "development_stage"],
           },
       )
   ```
4. **Always filter `is_primary_data == True`** to avoid duplicate cells
5. If the dataset is very large (above `DOWNSAMPLE_MAX_CELLS`, default 500000), **downsample per category** rather than
   dropping entire tissues/diseases. For example, sample up to N cells per
   (tissue, disease) combination to keep diversity while controlling size.
   Alternatively, use the streaming API (`ExperimentAxisQuery`) — see the skill file.

### 0.3 Alternative sources (if Census is insufficient)
If CELLxGENE Census does not have suitable data (e.g., rare tissue, specific organism,
spatial data needed), try these alternatives **in order of preference**:

1. **gget.cellxgene** — query CZ CELLxGENE Discover for specific datasets:
   See the **`database-access`** skill for the gget access guide.
   ```python
   import gget
   gget.setup("cellxgene")
   adata = gget.cellxgene(species="homo_sapiens", tissue="<tissue>",
                           cell_type=["<cell_type1>", "<cell_type2>"])
   ```
2. **GEO / ArrayExpress** — use `web-search` and `web-fetch` to find accession numbers,
   then download via `gget` or a verified direct URL
3. **Human Cell Atlas (HCA)** / **Tabula Sapiens** / **Broad Single Cell Portal**
   — use `web-search` and `web-fetch` to locate and verify specific dataset URLs

Prefer datasets that already provide **processed count matrices**
(h5ad, loom, mtx format) with cell type annotations and metadata.

### 0.4 Validate the retrieved dataset
Before proceeding to Step 1, verify:
- [ ] Dataset is loaded as an AnnData object
- [ ] Sufficient number of cells (ideally >10k for robust panel selection)
- [ ] Cell type annotations exist (check `.obs` columns) — if not, they will be computed in Step 1
- [ ] The dataset is relevant to the user's biological context
- [ ] Save the dataset to the workdir from Python, then verify the path with `find` or `read` as appropriate

> [!NOTE]
> Document in the notebook which database was queried, what filters were used,
> and why this dataset was selected. This information goes into the final report (Step 6).

## 1) Dataset Understanding and Splitting

Start exploratory inspection by creating an nbformat record with `create_notebook` and `add_cell`, then execute each computation with a fresh `run_python` call. Persist datasets, tables, and figures to the workdir between calls; notebook cells do not share interpreter memory.

### 1.1 Basic structure
Inspect:
- file format (h5ad or other)
- number of cells / genes
- batches / conditions
- `.obs`, `.var`, `.obsm`, `.uns`
- whether dataset has spatial or multimodal components

Checklist:
- [ ] Identify `label_key` (true cell type recommended if present)
- [ ] Identify batch/condition columns
- [ ] Confirm whether `adata.X` is raw counts or normalized/log1p

---

### 1.2 Downsampling (CRITICAL)

Thresholds come from the module-level constants in
`assets/references/scripts/gene_panel_helpers.py` (see the Hyperparameters table at the top).

Rules:
- If `adata.n_obs > DOWNSAMPLE_MAX_CELLS` (default 500000): downsample to below that limit, **preserving all cell types**.
- If `adata.n_vars > GENE_COUNT_THRESHOLD` (default 30000): reduce to ≤ `GENE_COUNT_THRESHOLD` via QC/HVG for compute-heavy steps.
- Save downsampled `adata` to a new file in the workdir from Python, then verify that the output exists.

> [!IMPORTANT]
> Prefer stratified downsampling by `label_key` if available; otherwise stratify by clustering labels.
> Use the constants imported from `gene_panel_helpers` (or the numeric defaults documented above) — don't re-hardcode them elsewhere.

---

### 1.3 Splitting
If provided one dataset, split to preserve all cell type distribution across all datasets:
- `N_TRAINING_SPLITS` training dataset(s), diversified (default: 1).
- at least `N_TEST_SPLITS` test batches (default: 5).
- constraint: each split should target `SPLIT_CELL_LIMIT` cells (default: 50000) to preserve diversity — treat this as a soft cap, go slightly under rather than well under.
- make splits as non-redundant as possible and represent **all cell types**.

### 1.4 Disk Space Management (MANDATORY)

> [!CRITICAL]
> Gene panel selection generates large intermediate files. You **must** minimize disk usage
> to avoid running out of space mid-pipeline.

Rules:
- **Process in memory whenever possible.** Do not save intermediate h5ad files unless they
  will be re-read later by a different step. Chain downsampling → splitting → preprocessing
  in one complete `run_python` stage when feasible; otherwise persist only the artifacts required by the next fresh call.
- **Keep only these files on disk:**
  - The **raw downloaded dataset** (Step 0 output) — for reproducibility
  - The **training split** (preprocessed) — used by all algorithmic methods
  - The **test splits** — used by benchmarking (Step 5)
- **Delete intermediate h5ad files** after they are no longer needed:
  - After downsampling + splitting is complete, delete the intermediate downsampled file
    (you already have the splits).
  - After preprocessing the training split, delete the unprocessed training split
    (you now have the preprocessed version).
- **Check available disk space** before downloading datasets (Step 0):
  ```python
  import shutil
  free_gb = shutil.disk_usage('/').free / (1024**3)
  print(f"Available disk space: {free_gb:.1f} GB")
  # Ensure at least 50GB free before proceeding
  ```
  If less than 50 GB available, warn the user before downloading.

---

### 1.5 Preprocessing status
Check:
- normalization
- PCA
- UMAP
- clustering

Recompute only if missing or invalid.

---

### 1.6 Preprocessing (if needed)
- QC (follow the QC skill if available)
- Normalize / log1p / scale
- PCA / neighbors / UMAP
- Batch correction (if needed)
- Leiden clustering
- DEG & marker detection
- Cell type annotation
- Marker plots (dotplots, heatmaps)

> [!IMPORTANT]
> For heavy steps, run tested Python scripts or `run_python` calls in the selected project Pixi environment, save checkpoints to the workdir, and record the exact code and artifact paths in the notebook.

---

## 2) Algorithmic Gene Panel Selection 

### 2.1 Pre-established methods
Algorithmic Methods = `{HVG, DE, Random Forest, scGeneFit, SpaPROS}`

- Use true cell type as `label_key` whenever available.
- Implement **HVG / DE** via Scanpy directly (`sc.pp.highly_variable_genes`,
  `sc.tl.rank_genes_groups`).
- For **Random Forest / scGeneFit / SpaPROS** use the helper script shipped
  with this skill: `assets/references/scripts/gene_panel_helpers.py`. It is a plain Python
  module (no registered toolset) with four functions:
  `select_spapros`, `select_random_forest`, `select_scgenefit`,
  `estimate_spapros_runtime`.

#### Load the helper script

The helper lives at `assets/references/scripts/gene_panel_helpers.py`, resolved
relative to **this skill's directory** (the directory containing this SKILL.md).
You already know that directory's absolute path from the skills catalog (the skill's
`<location>`). Record the import in a notebook code cell, and execute the same complete code through `run_python` with that directory on `sys.path`:

```python
import sys
from pathlib import Path

# Substitute the absolute path of THIS skill's directory (the one holding SKILL.md),
# e.g. <PACKAGE_ROOT>/skills/gene-panel/PantheonOS
skill_dir = Path("<ABSOLUTE PATH OF THIS SKILL SOURCE DIRECTORY>")
sys.path.insert(0, str(skill_dir / "assets/references/scripts"))

from gene_panel_helpers import (
    estimate_spapros_runtime,
    select_spapros,
    select_random_forest,
    select_scgenefit,
    # Hyperparameter defaults (override per call with kwargs if needed):
    SCGENEFIT_MAX_CONSTRAINTS,
    SPAPROS_N_HVG,
    RF_N_ESTIMATORS,
    SPAPROS_RUNTIME_WARNING_MINUTES,
    SPAPROS_RUNTIME_SKIP_MINUTES,
)
```

Resolve this skill's absolute `<location>` from the skills catalog, take its parent
directory as `skill_dir`, and `read` the absolute path
`<skill_dir>/assets/references/scripts/gene_panel_helpers.py` before importing.
Native file tools resolve relative paths from the agent workspace, not from the skill directory.

> [!CAUTION]
> **SpaPROS runtime gate (MANDATORY).** SpaPROS can run for tens of minutes
> to hours on large datasets. Call `estimate_spapros_runtime(...)` **first**
> and inspect the `severity` tier of the returned dict:
>
> - `"fast"` → run `select_spapros(...)` directly, no user confirmation needed.
> - `"slow"` or `"very_slow"` → **stop** and present the estimate dict to the
>   user in the current conversation with a clear Run/Skip choice. Continue only
>   after an explicit response:
>     - Run approved → call `select_spapros(...)` as normal.
>     - Skip chosen → **do not** call `select_spapros`; report the skip in
>       `report_analysis.md` and continue with the other methods only.
>
> A delegated worker cannot approve this cost. It must return the estimate to its
> parent session, which obtains the user's decision before dispatching more work.

```python
# --- SpaPROS pre-check (cheap, metadata-only read of the .h5ad) ---
estimate = estimate_spapros_runtime(
    adata_path=adata_path,
    num_markers=200,
    n_hvg=SPAPROS_N_HVG,
    warning_minutes=SPAPROS_RUNTIME_WARNING_MINUTES,
    skip_minutes=SPAPROS_RUNTIME_SKIP_MINUTES,
)
print(estimate)
# If estimate["severity"] != "fast": return this dict verbatim to the
# parent session and STOP. Do not call select_spapros in this dispatch.

# IMPORTANT: call each method ONCE with return_scores=True.
# This writes a full ranked CSV (every gene + score). For the ARI vs K
# sweep in Step 3, slice top-K from that CSV in pandas — do NOT re-run
# the algorithm with different K values.

select_scgenefit(
    adata_path=adata_path,
    label_key="cell_type",
    return_scores=True,
    max_constraints=SCGENEFIT_MAX_CONSTRAINTS,
    workdir=workdir,
)

# SpaPROS — ONLY when severity=="fast" or the session context records
# explicit user approval. Otherwise, skip this cell entirely.
select_spapros(
    adata_path=adata_path,
    label_key="cell_type",
    num_markers=200,  # selector cutoff; full table is still saved
    n_hvg=SPAPROS_N_HVG,
    return_scores=True,
    workdir=workdir,
)

select_random_forest(
    adata_path=adata_path,
    label_key="cell_type",
    n_estimators=RF_N_ESTIMATORS,
    return_scores=True,
    workdir=workdir,
)
```

- Always request **gene scores** (`return_scores=True`).
- Outputs land in `workdir/gene_panels/{spapros,random_forest,scgenefit}/`.
- Each method writes a **scores CSV** that is the single source of truth
  for ranking — Step 3 consumes these files directly.
- To override any cap per call, pass the kwarg (`max_constraints=`,
  `n_hvg=`, `n_estimators=`, etc.); don't edit the defaults in the helper
  unless the new value should apply project-wide.

---

## 3) Optimal SEED panel Discovery

For **each method independently (HVG, DE, Scgenefit, RF, SpapROS)**:

Let N be the target final panel size requested by the user.

> [!CRITICAL]
> The ARI vs K sweep is a **pandas slicing** operation, not a re-run of
> the algorithm. Each method's scores CSV (from Step 2.1) already ranks
> every gene. Call each algorithm **once**; slice top-K in memory.

1. Load the method-specific gene score CSV and rank genes (descending score):
   ```python
   import pandas as pd
   scores = pd.read_csv(scores_csv).sort_values("score", ascending=False)
   ```
2. Build candidate sub-panels of sizes K ∈ {100, 200, …, N} by taking the top-K:
   ```python
   panel_K = scores.head(K)["gene"].tolist()
   ```
3. For each method and each K:
   - Subset the dataset to panel genes only: `adata_K = adata[:, panel_genes]`
   - Recompute neighbors + Leiden on `adata_K` (same preprocessing policy across K)
   - Compute ARI between Leiden clusters and true cell types (`label_key`).
4. Plot ARI vs K for each method.
5. Pick the **seed panel** = (method, K*) with the best ARI.

**Note**: **SEED STEP** is performed using the training `adata`. It is **IMPORTANT** you investigate ARI vs panel size for all methods (HVG, DE, Scgenefit, RF, SpapROS) when possible, to make sure you take the best one!

---

## 4) Curation Logic

### 4.1 Curation pipeline (STRICT ORDER)

Final panel is built in **two phases**:

#### Phase 1 — Seed-panel (algorithmic)
- Use the optimal Seed-panel identified in Step 3 as seed subpanel
- Do **not** change genes in the seed

#### Phase 2 — Completion (biological lookup is the PRIMARY mechanism)

> **CRITICAL**: Biological curation is the MAIN completion mechanism, NOT consensus fill.
> The purpose of completion is to add biologically meaningful genes that algorithmic methods may have missed.
> Consensus fill is ONLY a small last-resort gap filler. If you find yourself adding more consensus-fill genes
> than biological genes, you have NOT done enough biological lookup.

**0) Completion Rule**
Before adding a batch of genes:
- test whether it makes ARI drop considerably or become less stable (training)
- If completing the panel up to size **N** degrades performance substantially (eg ARI drop > `ARI_DROP_THRESHOLD`), propose:
  - an optimal stable panel (< N)
  - a supplemental gene list to reach N if required
- a modest ARI drop is acceptable if it adds important biological coverage
Check this on the training dataset.

**1) Assess Seed Coverage First**
Before biological lookup, inspect genes in the seed panel:
- Map seed gene IDs to symbols
- Identify which biological categories from the user request and session context are already covered
- Note which categories are MISSING or under-represented

**2) Exhaustive Biological Lookup (CRITICAL — MUST BE THOROUGH)**
Derive the relevant biological categories from the **user request and session context** (e.g., cell type markers, signaling pathways, functional states, disease-specific genes — whatever the user's goal requires).

Run **multiple focused literature/database searches**, once per major biological category identified. Use native `web-search`/`web-fetch`; delegate independent search streams through `sub_agent` only when parallelism or an isolated context is useful.
For **each category**, collect **all** well-established marker genes (typically 10-30+ per category, not just 3-5).
Sources: GeneCards, GO, UniProt, KEGG, Reactome, MSigDB, published marker gene lists, review articles.

> A single broad search returning a handful of genes for an entire panel is INSUFFICIENT.
> The number of biologically curated genes should scale with the gap between seed size and target N.
> Do multiple rounds of lookup — breadth across ALL relevant categories AND depth within each.

**3) Add Biologically Relevant Genes**
For each candidate gene:
   - check not already in seed panel
   - ensure no redundancy
   - maintain balanced biological coverage across categories
   - categorize into a relevant biological category (from user/session context, or inferred)
   - after each batch of additions, check Completion Rule (ARI stability on training)
   - if ARI drops sharply, try a different set; a modest drop for strong biological coverage is acceptable
   - continue until all important biological genes are added or panel reaches size N

**4) Consensus Fill (LAST RESORT ONLY — small gap filler)**
Only if after exhaustive biological lookup, `{seed + biological genes} < N`:
   - normalize scores per method (same scale, no method dominates)
   - aggregate into a consensus table
   - fill the small remaining gap by score priority, excluding genes already present

**Deliverable: a gene × {method where it comes from, biological category, biological function, source/reference} table.**

**Note**: Every accepted gene must be **justified**, assigned a **biological category**, and referenced with a source (seed/method score or website/literature) and a gene function description.

---

## 5) Benchmarking (MANDATORY)

### 5.0 Panel genes comparison
Create an **UpSet plot** for all **N-size** algorithmic panels to see overlap.

Use the **full original dataset** for evaluation.

### 5.1 Dataset
Benchmarking is performed on **test datasets**.

### 5.2 Metrics
For each subset compute (across test splits):
1. all algorithmic **N** size panels
2. final curated **N** size panel
3. if curated **N** was not optimal per **Completion Rule**, also benchmark the optimal stable (<N) panel
4. full gene set baseline

Compute:
- Leiden over-clustering on panel genes
- **ARI, NMI** between Leiden and true labels
- **Silhouette Index** using Leiden assignments

Plots:
- one figure per metric
- boxplots
- high-quality formatting

### 5.3 UMAP comparison
Compute UMAPs for:
- full genes (reference)
- each algorithmic **N** size panel
- final curated **N** size panel
- if needed, the optimal stable panel

Compare vs reference:
- qualitative
- quantitative (distance correlation / Procrustes-like metrics)

---

## 6) Summarizing

Report must include the full workflow (Steps 0 → 5) in a well-written **PDF**. A reporting `sub_agent` may draft it from completed evidence and artifacts, but the current session must verify the final file:

- **Objective & context**
- **Dataset description** (structure, labels, preprocessing status)
- **Algorithmic methods run** (HVG/DE/RF/scGeneFit/SpaPROS): what each optimizes (detailed)
- **Sub-panel selection**:
  - ARI vs size curves per method
  - UpSet plot of different panels (overlaps)
  - selection decision (method + size) and why
- **Consensus table construction**:
  - normalization choice
  - aggregation rule
  - resulting ranked list
- **Curation & completion reasoning (step-by-step)**:
  - per added gene: lookup → match to context → accept/reject
  - redundancy checks + category balance
  - **all biological references**
- **Benchmarking results**:
  - UpSet plot comparing algorithmic panels and curated panel
  - ARI/NMI/SI boxplots across test subsets
  - UMAP comparisons + quantitative similarity metric
  - interpretation of performance differences

### Tables (MANDATORY)
1) Recap table of final panel (all N genes):

| Gene | Methods where it appears | Biological Function | Relevance score |
|------|--------------------------|----------------------|-----------------|

2) Per-category count recap table based on the user request and session context.

### Figures (MANDATORY)
The report should contain at **least** all of the following figures , and any other figures that you consider relevant:
  - ARI vs size curves per method (See above **Sub-panel selection**)
  - UpSet plot comparing algorithmic panels and curated panel (See above **Benchmarking results**)
  - ARI/NMI/SI boxplots across test subsets (See above **Benchmarking results**)
  - UMAP comparisons + quantitative similarity metric (See above **Benchmarking results**)
---

# Guidelines for reproducible notebook records

Use `create_notebook` to initialize one nbformat notebook per analysis task and `add_cell` to record Markdown and code cells. These tools edit notebook structure; they do not execute cells and they do not own a persistent kernel.

- Start each notebook with a Markdown cell containing the background and objective.
- Use `run_python` for computation. Every call starts a fresh interpreter, so each call must include all imports and definitions it needs, or load explicit artifacts saved by an earlier call.
- After a successful `run_python` call, add the exact code to the notebook with `add_cell`, then add a Markdown cell explaining the observed result. Do not imply that adding the cell executed it or populated notebook outputs.
- Save datasets, tables, models, and figures under the workdir so later stateless calls can load them. Record those artifact paths in the notebook.
- Keep related code in the same notebook, but split memory-heavy work into complete, independently executable stages that communicate through saved artifacts.
- Use **stratified downsampling** only when justified by the workflow thresholds, preserving all cell types, and document what was checked, changed, and why.

> [!IMPORTANT]
> **Do not reduce the data merely to evade a memory failure.** First make the computation more memory-efficient or split it into explicit stateless stages. If the complete code is too large for a practical inline `run_python` call, write a `.py` script, record that script path in a notebook Markdown cell, and use `run_python` with a small loader that executes the script in its fresh interpreter. Document the reason in `report_analysis.md`.

---

# Visualization quality gate

We expect **high-quality, publication-level figures**.

After generating a figure:
- call `observe_figure(file_path=<figure path>, question=<specific semantic check>, expectation=<quality criterion>)`
- accept the quality gate only on vision-backed `PASS`; for `WARN` or `FAIL`, revise according to the returned analysis and rerun the check
- when useful, call `read` on the image path for a second semantic inspection by the current model using the returned ImageContent
- use `show` only for optional host preview; if the vision evaluator cannot run, treat that as a tool error and do not guess

High-quality means:
- clear, readable
- labeled axes
- good color/contrast
- informative title (not too long)

If figure is not satisfactory → **replot**
