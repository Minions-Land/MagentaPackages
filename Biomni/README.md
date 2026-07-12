# Biomni Package for Magenta

Biomni integrates selected resources from the Stanford SNAP Lab
[Biomni project](https://github.com/snap-stanford/Biomni) into Magenta. The
package contains three skills, including focused workflow guides and more than
200 biomedical Python functions across 22 modules. It does not require the
upstream `biomni` Python package.

## Skills

### `sgrna-design`

CRISPR sgRNA design guidance with two executable functions:

- `design_knockout_sgrna` searches pre-computed human or mouse knockout
  libraries.
- `perform_crispr_cas9_genome_editing` simulates an editing workflow.

The sgRNA libraries are large external data-lake files and are not stored in
this repository.

### `single-cell-annotation`

Single-cell RNA-seq annotation guidance with three executable functions:

- `annotate_celltype_scRNA` performs LLM-assisted marker-based annotation.
- `annotate_celltype_with_panhumanpy` runs Panhuman Azimuth annotation.
- `unsupervised_celltype_transfer_between_scRNA_datasets` performs
  multi-method reference transfer with popV.

### `biomedical-tools`

A general toolkit containing more than 200 functions across these 22 modules:

`biochemistry`, `bioengineering`, `bioimaging`, `biophysics`,
`cancer_biology`, `cell_biology`, `database`, `genetics`, `genomics`,
`glycoengineering`, `immunology`, `lab_automation`, `literature`,
`microbiology`, `molecular_biology`, `pathology`, `pharmacology`, `physiology`,
`protocols`, `support_tools`, `synthetic_biology`, and `systems_biology`.

Coverage includes biomedical database access, pharmacology, genomics,
bio-imaging, molecular biology, literature analysis, PyLabRobot documentation
and script validation, Protocols.io access, and local protocol reading.

Both focused sgRNA functions (`design_knockout_sgrna` and
`perform_crispr_cas9_genome_editing`) and all three single-cell annotation
functions are also included in the relevant general modules. This duplication
is intentional: each skill can be used independently. Keep both copies
synchronized when modifying one of these functions.

## Package Layout

```text
Biomni/
├── package.toml
├── README.md
├── scripts/
│   └── fetch_biomni_data.py
└── skills/
    ├── sgrna-design/
    │   ├── SKILL.md
    │   ├── assets/references/
    │   └── tools/
    ├── single-cell-annotation/
    │   ├── SKILL.md
    │   ├── assets/references/
    │   └── tools/
    └── biomedical-tools/
        ├── SKILL.md
        └── tools/
            ├── *.py
            ├── schema_db/
            └── tool_description/
```

All three manifest components have `kind = "skill"`. Biomni has no profiles;
loading the package selects all three skills.

## Bundled and External Data

The package bundles:

- Python implementations for all included tools;
- knowledge guides and reference documentation;
- 33 database API schema caches under `schema_db/`;
- Python tool-parameter descriptors under `tool_description/`.

Large scientific datasets are not bundled. They include the sgRNA knockout
libraries, CZI Census metadata, HPO ontology, TxGNN predictions, and DDInter
tables required by specific functions.

Download the files used by all three skills into a directory outside this
package:

```bash
python Biomni/scripts/fetch_biomni_data.py --dest /absolute/path/to/biomni-data
export BIOMNI_DATA_LAKE=/absolute/path/to/biomni-data
```

The default download contains the 14 files used by this package. To download
only one skill's files or the full upstream data lake:

```bash
python Biomni/scripts/fetch_biomni_data.py \
  --dest /absolute/path/to/biomni-data \
  --skill sgrna-design

python Biomni/scripts/fetch_biomni_data.py \
  --dest /absolute/path/to/biomni-data \
  --all
```

Functions that accept `data_lake_path` use that explicit path first and fall
back to `BIOMNI_DATA_LAKE`. DDInter functions generate their pickle caches next
to the downloaded CSV files on first use.

## Usage

Load all three skills through Magenta:

```bash
magenta --harness-package Biomni
```

Magenta loads each `SKILL.md` together with its bundled tools and references.
The skill instructions describe which module and function to use for a task.

The general modules can also be imported directly:

```python
import sys

sys.path.insert(0, "Biomni/skills/biomedical-tools/tools")

from literature import query_pubmed

papers = query_pubmed("CRISPR gene editing", max_papers=10)
```

Consult the implementation and its corresponding
`tools/tool_description/<module>.py` descriptor for the current parameters and
return format.

## Runtime Requirements

The tool code is bundled, but its third-party scientific dependencies are not.
Requirements vary substantially by module and function. Representative
dependencies include:

- common utilities: `numpy`, `pandas`, `requests`;
- databases and literature: `biopython`, `beautifulsoup4`, `PyPDF2`, `pymed`,
  `googlesearch-python`;
- LLM-backed functions: `langchain-core`, `langchain-anthropic`, and
  `ANTHROPIC_API_KEY`;
- pharmacology: `rdkit`, `chembl-webresource-client`, `DeepPurpose`;
- single-cell analysis: `scanpy`, `celltypist`, `scvi-tools`.

Some functions additionally require external programs, containers, large model
downloads, service credentials, or specialized environments. Read the relevant
module and [`biomedical-tools/SKILL.md`](skills/biomedical-tools/SKILL.md) before
running a function. Common configuration variables include:

- `BIOMNI_DATA_LAKE`;
- `ANTHROPIC_API_KEY`;
- `PROTOCOLS_IO_ACCESS_TOKEN` or `BIOMNI_PROTOCOLS_IO_ACCESS_TOKEN`;
- `BIOMNI_PROTOCOLS_DIR`;
- `SYNAPSE_AUTH_TOKEN`.

## Upstream Adaptation

The bundled code is derived from the MIT-licensed Biomni tool modules and has
been adapted to operate without the upstream `biomni` package. Local changes
include:

- replacing upstream configuration and utility imports with local helpers;
- using Claude Sonnet 5 for the included Anthropic-backed functions;
- resolving external datasets through `BIOMNI_DATA_LAKE` or explicit paths;
- preparing DDInter caches from downloaded CSV files;
- making local protocol storage configurable with `BIOMNI_PROTOCOLS_DIR`;
- removing the unused upstream tool registry and fixing copied integration
  issues.

Knowledge guides use CC BY 4.0. See each skill's frontmatter for its declared
license and source information.

## Citation

If you use the bundled Biomni resources, cite the upstream project and its
paper:

```text
Biomni: A General-Purpose Biomedical AI Agent
bioRxiv 2025.05.30.656746v1
https://github.com/snap-stanford/Biomni
```

For sgRNA data and single-cell workflows, also follow the citations documented
in the corresponding skill references.

## Related Packages

- [AutOmicScience](../AutOmicScience/)
- [ClaudeScience](../ClaudeScience/)
- [PantheonOS](../PantheonOS/)
