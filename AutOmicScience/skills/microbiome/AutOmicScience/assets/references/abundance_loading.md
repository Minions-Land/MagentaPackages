# Reference — Abundance Table Loading & CLR Transformation

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

Loading 16S OTU/ASV or metagenomic taxonomic abundance tables, filtering, and CLR transformation.

## Format
**Taxa × samples** matrix. Rows = OTUs/ASVs/species; columns = samples. Values = counts (raw reads) or relative abundance.

```python
import pandas as pd
abundance = pd.read_csv("otu_table.csv", index_col=0)  # taxa in rows
taxonomy = pd.read_csv("taxonomy.csv", index_col=0)    # OTU_ID → taxonomy levels
```

Taxonomy columns: Kingdom, Phylum, Class, Order, Family, Genus, Species (or collapsed like "k__Bacteria;p__Firmicutes;...").

## Prevalence filtering
Taxa present in <10% of samples are noise:
```python
prevalence = (abundance > 0).sum(axis=1) / abundance.shape[1]
keep = prevalence >= 0.1
abundance_filt = abundance.loc[keep]
```

## CLR transformation (centered log-ratio)
Compositional data requires log-ratio transformation:
Zeros are the whole problem: CLR takes a log ratio, so every zero must be replaced first, and *how*
you replace it changes the result.

**Preferred — `scikit-bio` (not pinned; provision per `AOSE_nonStandard_env.md`):**

```python
from skbio.stats.composition import clr, multi_replace

# skbio takes rows = compositions, so transpose the taxa × samples table
clr_abundance = clr(multi_replace(abundance_filt.T.values)).T
```

`multi_replace` uses **multiplicative replacement**: it swaps zeros for a small δ *and rescales the
rest so each sample still sums to 1*. That is what keeps the object a composition.

**Fallback — pinned stack only (`scipy`), if you cannot provision `scikit-bio`:**

```python
import numpy as np
from scipy.stats.mstats import gmean

def clr(counts):
    """CLR over a taxa × samples table. counts must be strictly positive."""
    gm = gmean(counts, axis=0)          # geometric mean per sample (down each column)
    return np.log(counts / gm)

clr_abundance = clr(abundance_filt.values + 1)   # additive pseudocount — see the caveat
```

Both give a valid CLR (each sample's values sum to 0), but **they are not the same numbers**: on a
sparse table the two differ by up to ~1 natural-log unit per entry, because `+1` shifts every count
additively and so changes the composition itself — most for the low-count taxa a microbiome study
cares about. If you use the `+1` route, say so in the `report`; do not present it as "CLR" without
the qualifier.

**Why CLR:** microbiome counts are compositional (sum-to-constant constraint). Raw counts violate independence. CLR removes the constraint.

## Rarefaction (deprecated for DE)
Subsampling to even depth (rarefying) was common but **deprecated** — it discards information. Use CLR or DESeq2 size factors instead.

## Aggregating taxonomy levels
Collapse to a specific level (e.g., Genus):
```python
# Group by Genus column, sum counts
genus_abundance = abundance.groupby(taxonomy["Genus"]).sum()
```

Analyze at the finest reliable level (Genus/Species for 16S; Species for shotgun). Phylum is too coarse.

## Pitfalls
- No prevalence filter → testing rare taxa
- Not CLR-transforming → violates parametric assumptions
- **`+1` instead of multiplicative replacement** → still a valid CLR, but of a different (shifted) composition; report which route you took
- Rarefaction for DE → loses power
- Wrong taxonomy level (Phylum → loses signal)

## Grounding
`report`: n samples, n taxa (raw / filtered), prevalence threshold, transformation and **which zero-replacement** (skbio `multi_replace` + `clr` / `+1` + scipy `gmean` / raw), taxonomy level.
