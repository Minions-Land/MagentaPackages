# Reference — Per-Patient Gene Recurrence

**Maturity: REFERENCE** — `pandas` is in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data); you hand-write the script. Emit a `report` dict and cite its numbers.

Two conventions decide whether every number downstream is right: **collapse to per-patient binary
alteration**, and **keep the whole cohort in the denominator**.

## The hypermutator problem

If you count raw mutation rows, a single hypermutator patient (e.g. MSI-high, 10,000 mutations)
dominates every gene's frequency. The biological question is almost always "in what fraction of
*patients* is gene X altered?" — a binary per-patient call.

**Wrong:**
```python
# Counts mutations — hypermutators dominate
gene_counts = maf.groupby("Hugo_Symbol").size()
```

**Right:**
```python
# Per-patient binary: is this gene altered in this patient at all?
altered = (
    pathogenic
    .groupby(["Tumor_Sample_Barcode", "Hugo_Symbol"])
    .size()
    .gt(0)                          # any pathogenic mutation → True
    .unstack(fill_value=False)      # patients × genes boolean matrix
)
```

## Pin the cohort, then reindex onto it

`altered` above has **one row per patient that survived the pathogenic filter** — patients whose
variants were all silent, and patients with no calls at all, are simply absent. They are still part of
the cohort, and they belong in every denominator. Define the cohort once and reindex:

```python
cohort = maf.Tumor_Sample_Barcode.unique()        # BEFORE filtering to pathogenic
altered = altered.reindex(cohort, fill_value=False)
assert altered.shape[0] == len(cohort)
```

Even `maf.Tumor_Sample_Barcode.unique()` understates it if a sequenced tumour produced **zero** calls
of any class — it never appears in the MAF at all. When a sample manifest or clinical table exists,
take the cohort from there and reindex onto that; then `n_patients` is the number sequenced, not the
number mutated.

**This is not a rounding error.** On a cohort of 10 where 6 carry pathogenic variants and TP53 is hit
in 4 of them, `altered.shape[0]` is 6, so TP53 reports **66.7%** — its true cohort frequency is
**40%**. Every gene is inflated by the same factor, so the ranking survives and the numbers do not;
nothing raises, and the report reads as a normal result.

## Recurrence frequency

```python
n_patients = len(cohort)                  # NOT altered.shape[0]
freq = (altered.sum(axis=0) / n_patients).sort_values(ascending=False)
print(freq.head(20))                      # top recurrently-altered genes
```

Report as `gene: n_altered/n_total (pct%)` — carrying `n_total` in the report is what makes a wrong
denominator visible to a reader.

## Minimum-support filtering

Genes altered in very few patients are statistical noise. For association testing, gate to genes
altered in **≥5 patients** (or ≥5% frequency):

```python
recurrent_genes = freq[altered.sum(axis=0) >= 5].index.tolist()
```

This also controls the FDR family size (fewer tests → more power after correction). The gate counts
patients, so it is unaffected by the denominator — but the *frequency* form (≥5%) is not.

## Building the analysis matrix

The patients × genes boolean matrix `altered` is the substrate for:
- Frequency ranking (above)
- Fisher mutation×phenotype tests (`association.md`)
- Oncoplot (`oncoplot.md`)
- Mutual-exclusivity / co-occurrence

**Combining mutation + CNA into one alteration matrix:**
```python
# mut_altered: patients × genes (from MAF)
# cna_amp: patients × genes (GISTIC +2)
# cna_del: patients × genes (GISTIC -2)
# "altered" = any of pathogenic mutation, amplification (oncogene), deletion (TSG)
combined = mut_altered | cna_amp_oncogenes | cna_del_tsg
```

Be explicit about the per-gene rule (see `pathway_alteration.md`).

## Patient-level frequency ranking example

```python
# TCGA PRAD: rank genes by patient-level alteration frequency
freq = altered.sum(axis=0).sort_values(ascending=False)
# Expected top: TP53, SPOP, ... 
top10 = freq.head(10)
```

## Pitfalls

- **Counting mutations not patients** — the #1 error; always collapse to per-patient binary first
- **`altered.shape[0]` as the denominator** — that is the count of *mutated* patients; reindex onto
  the cohort so mutation-free patients are `False` rows rather than missing ones
- **Not deduplicating multi-sample patients** — a patient with primary+met counted twice
- **Forgetting the minimum-support gate** before association testing
- **Including silent mutations** — filter to pathogenic first (see `variant_classification.md`)

## Grounding

Emit a `report` with: **n_patients in the cohort** and where that number came from (MAF barcodes vs a
sample manifest), n patients carrying ≥1 pathogenic variant, n_genes tested, and top recurrent genes
with exact frequencies. Every frequency traces to `altered.sum() / len(cohort)` — state both parts of
the fraction, never the percentage alone.
