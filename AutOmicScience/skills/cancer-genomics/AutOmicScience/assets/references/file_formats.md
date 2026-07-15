# Reference — MAF & CNA File Formats

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

Parsing conventions for cancer genomics tabular files: MAF (Mutation Annotation Format), CNA matrices, and cBioPortal/MSK-IMPACT exports.

## MAF (Mutation Annotation Format)

Tab-delimited, one row per mutation call. Standard GDC/TCGA columns:

| Column | Meaning |
|--------|---------|
| `Hugo_Symbol` | Gene name (HGNC) |
| `Chromosome`, `Start_Position`, `End_Position` | Genomic coordinates |
| `Variant_Classification` | Consequence class (Missense_Mutation, Nonsense_Mutation, …) |
| `Variant_Type` | SNP / DEL / INS |
| `Reference_Allele`, `Tumor_Seq_Allele2` | Alleles |
| `Tumor_Sample_Barcode` | Sample ID (join key to clinical) |
| `HGVSp_Short` | Protein change (e.g., `p.Y537S`) |
| `Protein_position` | AA position (may be `537/595` format) |

**Parsing:**
```python
import pandas as pd
maf = pd.read_csv("data.maf", sep="\t", comment="#", low_memory=False)
```

Some MAFs have `#version 2.4` header lines → `comment="#"` skips them.

## cBioPortal / MSK-IMPACT exports

cBioPortal clinical files have **N leading `#`-comment metadata rows** (typically 4–5) before the header. These describe display names, datatypes, priorities:

```
#Patient Identifier	Sample Identifier	...
#Patient Identifier	Sample Identifier	...
#STRING	STRING	...
#1	1	...
PATIENT_ID	SAMPLE_ID	...       <- actual header (5th line)
P-0001	P-0001-T01	...
```

**Parse by skipping comment rows:**
```python
# Count leading # rows, then read
clinical = pd.read_csv("data_clinical_sample.txt", sep="\t", comment="#")
# comment="#" drops ALL # lines including the header if it starts with #.
# Safer: count them explicitly:
with open("data_clinical_sample.txt") as f:
    skip = sum(1 for line in f if line.startswith("#"))
clinical = pd.read_csv("data_clinical_sample.txt", sep="\t", skiprows=skip)
```

**Key files in a cBioPortal study:**
- `data_mutations.txt` / `data_mutations_extended.txt` — MAF-like
- `data_cna.txt` — gene × sample GISTIC matrix
- `data_clinical_patient.txt` — patient-level clinical
- `data_clinical_sample.txt` — sample-level clinical
- Join on `Tumor_Sample_Barcode` ↔ `SAMPLE_ID`, and `SAMPLE_ID` → `PATIENT_ID`

## CNA (Copy Number Alteration)

Two common shapes:

**1. GISTIC discrete matrix** (gene × sample), values in {−2, −1, 0, +1, +2}:
```python
cna = pd.read_csv("data_cna.txt", sep="\t", index_col=0)  # genes × samples
# -2 = deep deletion, -1 = shallow loss, 0 = neutral, +1 = gain, +2 = amplification
```

**2. Segment file** (chrom, start, end, log2ratio):
```python
seg = pd.read_csv("segments.seg", sep="\t")
# columns: ID, chrom, loc.start, loc.end, num.mark, seg.mean (log2 ratio)
```

## Critical conventions

- **Mutation ≠ amplification.** ERBB2 point mutation (from MAF) is a different alteration axis than ERBB2 amplification (from CNA matrix). Never conflate them — consult both files separately.
- **Sample vs patient.** One patient may have multiple samples (primary + metastasis). Decide the analysis unit explicitly; collapse to patient-level when computing recurrence.
- **Barcode matching.** TCGA barcodes: `TCGA-XX-XXXX-01A-...` — the first 12 chars (`TCGA-XX-XXXX`) identify the patient; `-01` = primary tumor, `-11` = normal. Truncate consistently.

## Sources
- GDC MAF specification: docs.gdc.cancer.gov
- cBioPortal file formats: docs.cbioportal.org/file-formats
