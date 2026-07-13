# PantheonOS Skills Package

This package contains bioinformatics and scientific workflow skills migrated from [PantheonOS](https://github.com/aristoteleo/PantheonOS) (BSD-2-Clause license).

## Overview

PantheonOS skills provide comprehensive guidance for:
- **Single-cell & spatial omics** analysis (scRNA-seq, scATAC-seq, spatial transcriptomics)
- **Image analysis** (cell/nucleus segmentation)
- **Scientific publishing** (paper writing, figure styling, presentations)
- **Bioinformatics pipelines** (nf-core)

## Skills Inventory

### Omics Analysis (6 skills)

| Skill | Description |
|-------|-------------|
| **single-cell** | scRNA-seq QC, annotation, trajectory inference |
| **spatial** | Spatial transcriptomics, 3D visualization, single-cell to spatial mapping |
| **gene-panel** | Gene panel design workflow for spatial transcriptomics |
| **sc-best-practices** | Comprehensive reference from sc-best-practices.org |
| **cell-segmentation** | Cellpose, SAM, StarDist, InstanSeg, Mesmer |
| **database-access** | gget, iSeq, CELLxGENE Census API — *shared with infrastructure* |

### Infrastructure (3 skills)

| Skill | Description |
|-------|-------------|
| **nf-core** | nf-core community pipelines (143+ workflows) |
| **data-analysis** | Environment setup, parallel computing, HPC data transfer |
| **database-access** | gget, iSeq, CELLxGENE Census API — *shared with omics* |

### Publishing (3 skills)

| Skill | Description |
|-------|-------------|
| **paper-writing** | Academic and report templates (HTML/LaTeX) |
| **figure-styling** | Aesthetic guidelines for scientific figures |
| **presentation** | Marp slides and presentation templates |

## Structure

Each skill follows the HCP-isomorphic Magenta package structure:

```
skills/skill-name/
├── HcpServer.ts
└── PantheonOS/
    ├── HcpMagnet.ts
    ├── SKILL.md            # Main skill document with YAML frontmatter
    └── assets/             # Optional bundled resources
        ├── references/     # Method documentation (loaded on demand)
        ├── scripts/        # Helper scripts
        └── templates/      # Output templates
```

## Usage in Magenta

Load this resource package together with its execution companion:

```bash
magenta \
  --harness-package PantheonOS \
  --harness-package MagentaWithPantheonOS
```

For versioned releases, select both packages explicitly:

```bash
magenta \
  --harness-package github:Minions-Land/Magenta-CLI/PantheonOS@0.1.0 \
  --harness-package github:Minions-Land/Magenta-CLI/MagentaWithPantheonOS@0.1.0
```

`PantheonOS` provides the 11 skill resources. `MagentaWithPantheonOS` provides the stateless `run_python`, atomic `create_notebook`/`add_cell`, and vision-backed `observe_figure` tools used by execution-heavy workflows.

## Skill Relationships

**Key omics skills:**
- `single-cell` → scRNA-seq workflows
- `spatial` → Spatial transcriptomics
- `cell-segmentation` → image-based segmentation (supports spatial)

**Cross-references:**
- `gene-panel` depends on `database-access` for dataset acquisition (step 0)
- `single-cell` references `sc-best-practices` for deeper background
- `spatial` references `single-cell` for expression-based workflows

## Key Features

### 1. Comprehensive Omics Coverage
- End-to-end single-cell workflows (QC → annotation → downstream)
- Spatial transcriptomics (mapping, domains, CCC)
- Public database access (programmatic queries)

### 2. Best Practices
- Evidence-based methods from sc-best-practices.org
- Validated workflows for common tasks
- Troubleshooting guidance for failure modes

### 3. Pipelines
- nf-core pipelines for standard workflows
- Environment management and reproducibility

### 4. Scientific Publishing
- Report templates (HTML, LaTeX)
- Figure styling for venues (Nature, NeurIPS, IEEE)
- Presentation tools (Marp)

## Dependencies

The package-level execution dependency is `MagentaWithPantheonOS`; load it in the same session as shown above. Individual workflows also require the scientific libraries they describe. Most skills use the **scanpy/scverse ecosystem**:
- `scanpy` — Single-cell analysis
- `squidpy` — Spatial transcriptomics
- `muon` — Multimodal integration
- `scvi-tools` — Deep generative models
- `cellpose` — Cell segmentation

## Migration Notes

- **Source**: `PantheonOS-main/pantheon/factory/templates/skills/`
- **Migrated**: 2026-07-07
- **Transformations**:
  - Flattened nested hierarchy (`omics/single_cell` → `single-cell`)
  - Standardized frontmatter (added `source`, `license`)
  - Moved sub-documents to `assets/references/`
  - Updated cross-references to new paths
  - Localized named PantheonOS roles and file operations to Magenta tools
  - Documented the required `MagentaWithPantheonOS` execution companion

## License

All skills retain their original BSD-2-Clause license from PantheonOS.

## See Also

- [PantheonOS Repository](https://github.com/aristoteleo/PantheonOS)
- [Single-cell Best Practices](https://www.sc-best-practices.org)
- [scverse Documentation](https://scverse.org)
- [nf-core Pipelines](https://nf-co.re)
