# Reference — Tumor Mutational Burden (TMB)

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

TMB = the count of somatic mutations, a biomarker for immunotherapy response.

## Definition

**TMB = number of non-synonymous (or all somatic) mutations**, optionally normalized per megabase (Mb) of sequenced territory.

Two common forms:
- **Raw count**: total non-synonymous mutations per sample
- **Per-Mb**: count / panel_size_Mb (e.g., MSK-IMPACT ≈ 1.2 Mb, whole-exome ≈ 30–50 Mb)

```python
# Non-synonymous = coding, protein-altering
nonsyn_classes = [
    "Missense_Mutation", "Nonsense_Mutation", "Frame_Shift_Del",
    "Frame_Shift_Ins", "Splice_Site", "In_Frame_Del", "In_Frame_Ins",
    "Nonstop_Mutation", "Translation_Start_Site"
]
cohort = maf.Tumor_Sample_Barcode.unique()            # pin the cohort BEFORE filtering
nonsyn = maf[maf.Variant_Classification.isin(nonsyn_classes)]

tmb = (nonsyn.groupby("Tumor_Sample_Barcode").size()
       .reindex(cohort, fill_value=0))                # a TMB-zero tumour is a data point, not a gap

# Per-Mb (if panel size known):
panel_mb = 1.2   # MSK-IMPACT; whole-exome ≈ 30–50 Mb — state which you used
tmb_per_mb = tmb / panel_mb
```

Some definitions include synonymous mutations (total mutational burden); the immunotherapy-relevant
TMB is usually **non-synonymous only** (neoantigen-generating). State which you use.

> ### `.reindex(cohort, fill_value=0)` is not optional
>
> `groupby().size()` emits a row only for samples that survived the filter. A sequenced tumour with
> zero non-synonymous calls — routine in low-TMB tumours and on small panels — vanishes, and every
> statistic is then computed over "mutated samples" instead of the cohort. On a 100-sample cohort with
> 30 such tumours, the median TMB reads **1.40× too high** (0.184 vs 0.132/Mb) and the IQR lower bound
> reads 0.132 instead of 0.000. Nothing raises; the distribution just quietly loses its left tail —
> which is exactly the tail a TMB-high/TMB-low split depends on.

## Distribution: median + IQR, not mean±SD

TMB is **right-skewed** (hypermutators create a long tail). Always report **median + interquartile
range**, never mean±SD:

```python
median = tmb.median()
q1, q3 = tmb.quantile([0.25, 0.75])
print(f"TMB median={median:.1f}, IQR=[{q1:.1f}, {q3:.1f}], n={len(tmb)}")
```

Report `n` next to the median. It is the one number that reveals a cohort-sized denominator turning
into a mutated-sample one.

## Group comparison

**Two groups** (e.g. responder vs non-responder) → Mann-Whitney U (non-parametric, since skewed):

```python
from scipy.stats import mannwhitneyu
tmb_resp    = tmb.reindex(responder_samples,    fill_value=0)
tmb_nonresp = tmb.reindex(nonresponder_samples, fill_value=0)
stat, p = mannwhitneyu(tmb_resp, tmb_nonresp, alternative="two-sided")
```

Use `.reindex(...)`, not `tmb[responder_samples]`: on pandas ≥2 a label-list lookup **raises
`KeyError: "['S042'] not in index"`** the moment one responder had zero non-synonymous calls. That
failure is the good outcome — it is loud. If `tmb` was already reindexed onto the cohort, both forms
agree and the guard costs nothing.

**≥3 groups** (e.g., breast cancer subtypes) → Kruskal-Wallis:

```python
from scipy.stats import kruskal
stat, p = kruskal(tmb_subtypeA, tmb_subtypeB, tmb_subtypeC, tmb_subtypeD)
```

## TMB ↔ immunotherapy framing

High TMB → more neoantigens → better response to immune checkpoint inhibitors (anti-PD-1/PD-L1, anti-CTLA-4). When interpreting a TMB↔response association:
- Higher TMB in responders supports the neoantigen hypothesis
- FDA-approved threshold: TMB ≥ 10 mut/Mb = "TMB-high" (pembrolizumab tumor-agnostic indication)
- Report the effect direction + biological framing, not just the p-value

## Pitfalls

- **Zero-mutation samples dropped** — `groupby().size()` omits them; `.reindex(cohort, fill_value=0)`
  or the median is computed over mutated samples only
- **`tmb[sample_list]`** — raises `KeyError` on pandas ≥2 for a zero-TMB sample; use `.reindex`
- **Mean±SD on skewed data** — always median+IQR for TMB
- **Parametric t-test** — use Mann-Whitney/Kruskal (non-parametric)
- **Counting silent mutations** — non-synonymous TMB is the standard for immunotherapy
- **Not normalizing per-Mb when comparing panels** — WES and targeted panels give different raw counts
- **Hypermutators not flagged** — MSI-high / POLE-mutant tumours are biologically distinct; consider
  reporting separately

## Grounding

`report` with: TMB definition used (which `Variant_Classification` set; raw count vs per-Mb and the
panel size assumed), **n samples in the denominator and how many had zero non-synonymous calls**,
median+IQR per group, test statistic + p-value, effect direction.
