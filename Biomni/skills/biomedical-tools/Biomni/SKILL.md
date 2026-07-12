---
name: biomedical-tools
description: >
  General biomedical research tools covering database queries (PubMed, UniProt, KEGG),
  drug discovery (ADME prediction, docking), genomics analysis, bio-imaging, and lab
  automation. Use when querying biomedical databases, predicting drug properties,
  analyzing genomic data, processing microscopy images, or automating lab workflows.
tags:
- database
- drug-discovery
- genomics
- imaging
- lab-automation
source: Biomni
license: MIT
---

# Biomedical Research Tools

Comprehensive toolkit of biomedical research functions from Biomni covering database access, computational analysis, and lab automation. This page is a **domain map** — for the exact, current function list and parameters, read `tools/tool_description/<module>.py` (the authoritative, code-synced descriptors).

## When to Use This Skill

Use this skill when you need to:
- Query biomedical databases (PubMed, UniProt, KEGG, STRING, etc.)
- Predict drug properties (ADME, toxicity, binding affinity)
- Analyze genomic or genetic data
- Process bio-imaging data (cell segmentation, quantification)
- Automate laboratory workflows

## Tool Categories

### Database & Information

**Database queries** (`database` module):
- UniProt protein information
- KEGG pathway data
- STRING protein interactions
- cBioPortal cancer genomics
- Ensembl, NCBI, PDB structure data
- And 20+ more databases

**Literature analysis** (`literature` module):
- PubMed / scientific paper search and analysis

**Invocation**: Tools are bundled as self-contained modules in this skill's `tools/`
directory (no `pip install biomni`). Add `tools/` to `sys.path` once, then import each
tool by its module name. `<SKILL_DIR>` = this skill's directory (where SKILL.md lives).

```python
import sys
sys.path.insert(0, "<SKILL_DIR>/tools")   # once per session

from literature import query_pubmed
from database import query_uniprot

# Search literature
papers = query_pubmed("CRISPR gene editing", max_papers=10)

# Get protein info
protein = query_uniprot(prompt="Find information about human insulin")
```

### Drug Discovery

**Pharmacology** (`pharmacology` module):
- ADME property prediction
- Toxicity assessment
- Molecular docking (AutoDock Vina, DiffDock)
- Binding affinity prediction
- Drug-drug interactions
- Physicochemical property calculation

```python
from pharmacology import predict_admet_properties, docking_autodock_vina

# Predict ADME
results = predict_admet_properties(
    smiles_list=["CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"],
    ADMET_model_type="MPNN"
)

# Molecular docking
docking = docking_autodock_vina(
    smiles_list=["CCO"],
    receptor_pdb_file="protein.pdb",
    box_center=[10, 10, 10],
    box_size=[20, 20, 20]
)
```

### Genomics & Genetics

**Genomics** (`genomics` module):
- Single-cell RNA-seq embeddings (scVI, Harmony, UCE, ESM, transcriptformer)
- Cell-type annotation & cross-dataset label transfer
- Gene-set enrichment analysis
- ChIP-seq peak calling (MACS2) & motif discovery (HOMER)
- Chromatin-interaction & comparative-genomics analysis

**Genetics** (`genetics` module):
- Statistical genetics: Bayesian fine-mapping, genomic prediction
- Population genetics: demographic-history simulation
- Coordinate liftover, TF-binding-site & phylogeny analysis

```python
from genomics import get_rna_seq_archs4

# Retrieve genes co-expressed with a query gene (ARCHS4)
result = get_rna_seq_archs4(gene_name="TP53", K=10)
```

### Molecular Biology

**Molecular biology** (`molecular_biology` module):
- PCR primer design
- Plasmid annotation
- Restriction enzyme analysis
- Golden Gate assembly
- Sequence mutations

```python
from molecular_biology import design_primer, pcr_simple

# Design primers around a target position
primers = design_primer(
    sequence="ATGCGATCG...",
    start_pos=100,
)

# Simulate PCR
pcr_result = pcr_simple(
    sequence="ATGC...",
    forward_primer="ATGC",
    reverse_primer="GCAT",
)
```

### Bio-Imaging & Pathology

**Bio-imaging** (`bioimaging` module):
- Medical image segmentation (nnU-Net)
- Image registration (rigid / affine / deformable)
- Image preprocessing & similarity metrics

**Pathology** (`pathology` module):
- Pathology image analysis
- Tissue quantification

**Cell biology** (`cell_biology` module):
- Cell-based assays

```python
from bioimaging import calculate_similarity_metrics

# Compare two medical images (e.g., before/after registration)
metrics = calculate_similarity_metrics(
    image1_path="fixed.nii.gz",
    image2_path="moving.nii.gz",
)
```

### Lab Automation

**Lab automation** (`lab_automation` module):
- PyLabRobot liquid-handling documentation
- PyLabRobot materials documentation
- PyLabRobot script validation & testing

```python
from lab_automation import get_pylabrobot_documentation_liquid

# Retrieve PyLabRobot liquid-handling documentation
docs = get_pylabrobot_documentation_liquid()
```

### Immunology & Microbiology

**Immunology** (`immunology` module):
- Antibody design
- Immune repertoire analysis

**Microbiology** (`microbiology` module):
- Microbiome analysis
- Metagenomics

### Cancer & Systems Biology

**Cancer biology** (`cancer_biology` module):
- Somatic mutation analysis
- Structural variant detection
- Copy number analysis

**Systems biology** (`systems_biology` module):
- Network analysis
- Pathway simulation

### Physiology & Biochemistry

**Physiology** (`physiology` module):
- Physiological modeling

**Biochemistry** (`biochemistry` module):
- Protein analysis
- Enzyme kinetics

### Synthetic Biology & Bioengineering

**Synthetic biology** (`synthetic_biology` module):
- Genetic circuit design
- Metabolic engineering

**Bioengineering** (`bioengineering` module):
- Tissue engineering
- Biomaterial design

**Biophysics** (`biophysics` module):
- Biophysical calculations

**Glycoengineering** (`glycoengineering` module):
- Glycan structure analysis

### Protocols & Support

**Protocols** (`protocols` module):
- Standard lab protocols

**Support tools** (`support_tools` module):
- Utility functions

## Installation

These tools are bundled with this skill — **no `pip install biomni` required**. They do
need their scientific dependencies available in the runtime environment (e.g. `scanpy`,
`pandas`, `requests`, `biopython`; LLM-backed tools additionally need `langchain-anthropic`
and an `ANTHROPIC_API_KEY`). Check a module's imports for its specific requirements.

Some tools have heavier, tool-specific requirements you must provision yourself: external
CLIs (e.g. `gatk`, `bwa`, `macs2`, `snpEff`, `prokka`, `iqtree`, `synapse`), Docker + a GPU
(DiffDock docking), a `conda` environment (panhumanpy), or large model downloads (~25 GB for
SE-600M). A few tools also read tokens/paths from the environment:
`BIOMNI_DATA_LAKE`, `SYNAPSE_AUTH_TOKEN`, `PROTOCOLS_IO_ACCESS_TOKEN`,
`BIOMNI_PROTOCOLS_DIR`.

## Tool Organization

Tools are bundled as self-contained modules in this skill's `tools/` directory:

- `tools/database.py` - Database queries
- `tools/pharmacology.py` - Drug discovery
- `tools/genomics.py` - Genomics analysis
- `tools/molecular_biology.py` - Molecular biology
- `tools/bioimaging.py` - Image analysis
- `tools/lab_automation.py` - Lab automation
- And 16 more modules...

## Finding Tools

**By domain**: See sections above

**By exact parameters**: This skill bundles machine-readable tool schemas at
`tools/tool_description/<module>.py` — one entry per function with its name,
description, and required/optional parameters (name, type, default). Read the
matching module file before calling a tool to get exact parameter names and defaults.

**Upstream reference**: https://github.com/snap-stanford/Biomni

## Usage Pattern

General pattern for using these bundled tools:

```python
# 1. Put this skill's tools/ on sys.path (once), then import the tool by module name
import sys
sys.path.insert(0, "<SKILL_DIR>/tools")
from {module} import {function_name}

# 2. Prepare parameters (see tools/tool_description/{module}.py for exact params)
params = {
    "required_param": "value",
    "optional_param": "value"
}

# 3. Call the function
result = {function_name}(**params)

# 4. Process results
print(result)
```

## Data Requirements

Some tools need external data files such as `hp.obo`,
`czi_census_datasets_v4.parquet`, `sgRNA_KO_SP_*.txt`, TxGNN predictions, or
DDInter tables. These files are not bundled or auto-downloaded by the tools.

From the MagentaPackages repository root, fetch the files used by this skill:

```bash
python Biomni/scripts/fetch_biomni_data.py \
  --dest /absolute/path/to/biomni-data \
  --skill biomedical-tools
export BIOMNI_DATA_LAKE=/absolute/path/to/biomni-data
```

Functions that accept `data_lake_path` use that explicit path first and fall
back to `BIOMNI_DATA_LAKE`. DDInter functions prepare their pickle caches next
to the downloaded CSV files on first use.

## Resources

**Biomni Documentation**:
- GitHub: https://github.com/snap-stanford/Biomni
- Paper: bioRxiv 2025.05.30.656746v1
- Web UI: https://biomni.stanford.edu

**Tool Descriptions**:
- Machine-readable parameter schemas bundled in this skill at `tools/tool_description/`
- 22 modules with full API schemas

## Citation

If using Biomni tools:

```
Biomni: A General-Purpose Biomedical AI Agent
bioRxiv 2025.05.30.656746v1
```

## License

- Tool code: MIT License
- This documentation: CC BY 4.0
- Commercial use: Allowed with attribution

## Related Skills

For specific workflows, see:
- **sgrna-design**: CRISPR guide RNA design
- **single-cell-annotation**: scRNA-seq cell type annotation
