---
name: omics-shared
description: Foundational layer for every omics modality — the omics_compute contract, maturity legend, global rules (preflight, evidence grounding, anti-circular), scverse data conventions, and the index/routing to every modality skill. Read first for any omics task.
requiredTools: [run_python, create_notebook, add_cell, observe_figure, omics_preflight, omics_compute]
tags: [omics, scverse, shared, anndata, mudata, spatialdata]
---

# Omics Shared — AOSE Operating Guide & Skill Index

This skill is AOSE's operating guide and the index to every modality skill — read it first for any omics task. It is the shared substrate every modality builds on (single-cell, spatial, bulk, proteomics, metabolomics, microbiome, genomics, and more): it defines **how to run compute**, the **rules every analysis follows**, and **which modality skill to route to**. Its catalog entry is always present; read it, then the relevant modality skill.

## How to run compute

Standardized steps run through the **`omics_compute`** tool, which executes a compute subcommand in the modality's pinned Pixi environment and returns a `report` dict:

```
omics_compute(
  subcommand="preprocess",
  modality="scrna",          # selects the pinned env (scrna→task1, spatial→task2, scatac→task4, multiome→task3)
  args={"input": "raw.h5ad", "output": "processed.h5ad"}
)
```

- `args` keys are the subcommand's `--kebab-case` flags. A value of `""`/`"true"` is a bare store-true flag; `"false"` omits it.
- The tool returns `{subcommand, pythonBin, report}`. The `report` dict carries the numbers — cite them in conclusions.
- For a method with **no** compute subcommand (a `REFERENCE` method), write it by hand and run it; print a trailing JSON `report` so the numbers are inspectable.
- Implementation helpers live in the `aose_omics_runtime` package (single source of truth), imported by name — e.g. `from aose_omics_runtime.shared.layout import assert_layout`. Prefer the matching `omics_compute` subcommand; if you import a helper directly, put this package's `tools/omics-compute/python/` on `sys.path` first.

## Maturity legend (used by every modality skill)

Each capability is tagged so you know what actually runs:

- **READY** — backed by a tested `omics_compute` subcommand. Call the tool.
- **PARTIAL** — runnable but gated by an extra install or GPU: either an `omics_compute` subcommand that needs heavier deps/GPU, or a well-defined method whose package is not in the default env. Verify preflight / install the dependency first, then run.
- **REFERENCE** — no compute subcommand and no baseline; the method doc gives one opinionated, hand-written recipe you run by hand (in the installed env, or a dedicated env when the package version-conflicts).

To provision any PARTIAL / REFERENCE method (or a user-named package) whose package is **not** in `task1–4`, follow `assets/references/AOSE_nonStandard_env.md`.

## Skill index — route to the right modality (read after preflight)

After `omics_preflight` confirms the modality, read its skill and the specific method doc you need. Skills are grouped by three orthogonal axes — pick by **what data you have** (resolution or molecule), then optionally add a **cross-cutting** skill for downstream statistics or ML engineering.

**By resolution (transcriptomics-centric):**

| Modality | Skill | Method docs |
|----------|-------|-------------|
| Single-cell (scRNA / scATAC / multiome) | `../../single-cell/AutOmicScience/SKILL.md` | routes to `rna/`, `atac/`, `multiome/` subskills |
| Spatial transcriptomics | `../../spatial/AutOmicScience/SKILL.md` | `../../spatial/AutOmicScience/assets/references/*.md` |
| Bulk (RNA-seq / epigenomics) | `../../bulk/AutOmicScience/SKILL.md` | routes to `rna/`, `epigenomics/` subskills |

**By molecule / assay (beyond transcriptomics):**

| Modality | Skill | Method docs |
|----------|-------|-------------|
| Cancer genomics — DNA variants only (MAF / CNA) | `../../cancer-genomics/AutOmicScience/SKILL.md` | `../../cancer-genomics/AutOmicScience/assets/references/*.md` |
| Proteomics (Olink / MS) | `../../proteomics/AutOmicScience/SKILL.md` | `../../proteomics/AutOmicScience/assets/references/*.md` |
| Metabolomics / lipidomics | `../../metabolomics/AutOmicScience/SKILL.md` | `../../metabolomics/AutOmicScience/assets/references/*.md` |
| Microbiome (16S / metagenomics) | `../../microbiome/AutOmicScience/SKILL.md` | `../../microbiome/AutOmicScience/assets/references/*.md` |
| Cancer dependency (DepMap / CCLE CRISPR screens) | `../../cancer-dependency/AutOmicScience/SKILL.md` | `../../cancer-dependency/AutOmicScience/assets/references/*.md` |
| Statistical / population genetics — GWAS, heritability, fine-mapping, colocalization | `../../statistical-genetics/AutOmicScience/SKILL.md` | `../../statistical-genetics/AutOmicScience/assets/references/*.md` |
| Immune repertoire — TCR / BCR clonotypes (AIRR-seq) | `../../immune-repertoire/AutOmicScience/SKILL.md` | `../../immune-repertoire/AutOmicScience/assets/references/*.md` |
| Biomolecular phase separation / condensates (sequence & biophysical properties) | `../../phase-separation/AutOmicScience/SKILL.md` | `../../phase-separation/AutOmicScience/assets/references/*.md` |

**Cross-cutting layers (combine with any data skill above):**

| Layer | Skill | Method docs |
|-------|-------|-------------|
| Survival analysis (KM / Cox on features from any modality) | `../../clinical-survival/AutOmicScience/SKILL.md` | `../../clinical-survival/AutOmicScience/assets/references/*.md` |
| ML engineering / deep models (reproduce DL methods, foundation models) | `../../bioml/AutOmicScience/SKILL.md` | routes to `repro/`, `deep-models/`, `sequence-fm/`, `coding/`, `figure-check/` subskills |

Routing notes for ambiguous cases:
- **Tumor bulk/single-cell RNA-seq** → the resolution skill (`bulk` / `single-cell`), not `cancer-genomics`. `cancer-genomics` handles somatic DNA variants (MAF/CNA) only, not expression.
- **"Associate features with patient survival"** → first the data skill to derive features, then `clinical-survival` for the KM/Cox step.
- **Foundation-model application (scGPT, Geneformer, UCE, perturbation prediction)** → `bioml`, not the resolution skill.

The shared method docs (`assets/references/*.md`) cover containers, data context, preprocessing, grounding, visualization, and data acquisition — read them on demand.

## Global rules (always follow)

1. **Preflight first** — call `omics_preflight(modality=...)` before any `omics_compute`. On a blocker, surface the exact `fix` and stop. Never fake success.
2. **Summarize context once** — run the `summarize` subcommand right after load; thread its text plus the free-text study description into every downstream decision (annotation, DE, composition).
3. **Anti-circular rule** — treat any existing cell-type/label column as **prior annotation**: use it only for post-hoc comparison (ARI/NMI), never copy it as your answer.
4. **Ground every quantitative claim** — every number in a conclusion must come from a computation you actually ran (an `omics_compute` report, or your own script's printed output), never from memory.
5. **Inspect every figure** — before a figure backs a claim, check it for artifacts, wrong scale, empty axes, or unexpected structure; re-plot if it looks wrong.
6. **Abstain over fabricate** — missing data/deps → a blocker with the fix. An unresolvable cluster → "unknown", not an invented label.

## Data conventions

From `conventions.py`, the single source of truth (import the constants; never hardcode):

- **Raw counts**: `layers["counts"]` · **Normalized**: `X`
- **Embeddings**: `obsm["X_pca"]`, `obsm["X_scVI"]`, `obsm["X_umap"]`, `obsm["X_spectral"]`, … (any `obsm["X_*"]`)
- **Clusters**: `obs["leiden"]` · **Cell types**: `obs["cell_type"]`
- **Batch/condition**: `obs["batch"]`, `obs["condition"]` · **Spatial coords**: `obsm["spatial"]`

For hand-written analysis, import helpers from the package-local Python implementation. The `omics_compute` tool configures this automatically; if a manual script needs direct imports, put this package's `tools/omics-compute/python/` directory on `sys.path` first:

```python
import os, sys
implementation_dir = os.environ.get("AOSE_OMICS_PYTHON_DIR") or "tools/omics-compute/python"
sys.path.insert(0, implementation_dir)
from aose_omics_runtime.shared import conventions, io as omics_io, summarize, preprocess
```
