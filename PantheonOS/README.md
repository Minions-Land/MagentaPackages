# PantheonOS Package

Bioinformatics and scientific workflow skills migrated from PantheonOS covering single-cell/spatial omics, image analysis, and scientific publishing. This package owns the instruction resources; `MagentaWithPantheonOS` supplies the companion execution tools.

## Package Structure

PantheonOS is organized into **3 domain profiles** for selective loading:

### Available Profiles

| Profile | Description | Skills |
|---------|-------------|--------|
| `omics` | Single-cell, spatial, and image-based omics analysis | 6 |
| `infrastructure` | Data access, workflow pipelines, and compute environment | 3 |
| `publishing` | Scientific paper writing, figures, and presentations | 3 |

> `database-access` belongs to **both** `omics` and `infrastructure` (data acquisition serves both), so the distinct skill count is **11**.

## Usage

Load `PantheonOS` and `MagentaWithPantheonOS` together. Harness package selectors are repeatable; loading only this package provides guidance but not the companion notebook/Python execution surface expected by execution-heavy workflows such as `gene-panel`.

### Load All Skills and Tools

```bash
magenta \
  --harness-package PantheonOS \
  --harness-package MagentaWithPantheonOS
```

### Load Specific Skill Profiles

```bash
magenta \
  --harness-package PantheonOS:omics,publishing \
  --harness-package MagentaWithPantheonOS
```

For versioned releases, select both packages explicitly:

```bash
magenta \
  --harness-package github:Minions-Land/Magenta-CLI/PantheonOS@0.1.0 \
  --harness-package github:Minions-Land/Magenta-CLI/MagentaWithPantheonOS@0.1.0
```

Magenta's native `read`, `write`, `edit`, `find`, `grep`, `show`, `bash`, `bg_shell`, `web-search`, and `web-fetch` tools remain responsible for ordinary file, process, preview, and web operations. Use `sub_agent` for one-shot delegation, `teammate_agent` for a persistent collaborator, and a `sub_agent` workflow only when workflow support is enabled.

## Skills Inventory

### Omics Analysis (6 skills)

| Skill | Description |
|-------|-------------|
| **single-cell** | scRNA-seq QC, annotation, trajectory inference |
| **spatial** | Spatial transcriptomics, 3D visualization, mapping |
| **gene-panel** | Gene panel design for spatial transcriptomics |
| **sc-best-practices** | Reference from sc-best-practices.org |
| **cell-segmentation** | Cellpose, SAM, StarDist cell/nucleus segmentation |
| **database-access** | Query genomic databases (gget, CELLxGENE Census) — *shared with infrastructure* |

### Infrastructure (3 skills)

| Skill | Description |
|-------|-------------|
| **nf-core** | 143+ nf-core community pipelines |
| **data-analysis** | Environment setup, parallel computing, HPC |
| **database-access** | Query genomic databases (gget, CELLxGENE Census) — *shared with omics* |

### Publishing (3 skills)

| Skill | Description |
|-------|-------------|
| **paper-writing** | Academic and report templates (HTML/LaTeX) |
| **figure-styling** | Aesthetic guidelines for scientific figures |
| **presentation** | Marp slides and presentation templates |

## Key Technologies Covered

### Single-Cell & Spatial
- **Python ecosystem**: scanpy, squidpy, spatialdata, muon
- **Pipelines**: nf-core/scrnaseq, nf-core/spatialvi

### Image Analysis
- **Segmentation**: Cellpose, Segment Anything Model (SAM), StarDist
- **Frameworks**: napari, scikit-image

### Databases
- **gget**: 23 modules for Ensembl, NCBI, UniProt, ARCHS4, etc.
- **CELLxGENE Census**: 217M+ single-cell profiles

### Scientific Publishing
- **Templates**: HTML reports, LaTeX academic papers
- **Figure styles**: Publication-ready matplotlib themes
- **Presentations**: Marp markdown slides

## Migration Notes

- **Source**: PantheonOS-main/pantheon/factory/templates/skills/
- **Migrated**: 2026-07-07
- **Transformations**:
  - Flattened nested hierarchy (`omics/single_cell` → `single-cell`)
  - Standardized frontmatter (added `source`, `license`)
  - Moved sub-documents to `assets/references/`
  - Created package.toml with profiles
  - Localized PantheonOS named-agent and file-manager instructions to Magenta's native tools
  - Declared `MagentaWithPantheonOS` as the execution companion in usage documentation

## License

All skills retain their original BSD-2-Clause license from PantheonOS.

## See Also

- Magenta's bundled package documentation — how packages load and how to combine selectors
- [PantheonOS Repository](https://github.com/aristoteleo/PantheonOS)
- [Single-cell Best Practices](https://www.sc-best-practices.org)
- [scverse Documentation](https://scverse.org)
- [nf-core Pipelines](https://nf-co.re)
