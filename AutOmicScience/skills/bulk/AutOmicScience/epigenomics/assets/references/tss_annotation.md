# Reference — TSS Annotation & Genomic Feature Classification

**Maturity: REFERENCE** — annotate peaks to genes and classify them by genomic feature. A GTF is a TSV
and a TSS is one coordinate, so **pandas on `task1` does this**; a multi-GB GTF reads fine with
`pd.read_csv(..., chunksize=...)`. **Neither `pyranges` nor `gtfparse` is installed** — they are
conveniences worth their own solve-group only if the interval work is intricate; not a gate. The
pyranges/gtfparse API below is verified against `pyranges` **0.1.4** (executed) and `gtfparse` rev
`cb3788e`, for when you do provision them.

> **Provisioning — follow `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`** (§A: a new Pixi
> feature + environment with its **own solve-group**, which keeps these pins away from `task1–4` and lands
> the env in `pixi.lock`). Do **not** bare-`pip install` — the machine's `python`/`pip` may point at conda
> `base`, and `pandas<3` would downgrade it. Do not add these to `task1–4` either: `pandas<3` conflicts with
> the pinned stack, which is exactly what an isolated solve-group is for.
>
> ```toml
> # tools/omics-environment/pixi.toml
> [feature.peaks.pypi-dependencies]
> pyranges = "==0.1.4"
> gtfparse = "*"
> [feature.peaks.dependencies]
> pandas = "<3"
> [environments]
> peaks = { features = ["core", "peaks"], solve-group = "peaks" }
> ```
> ```bash
> pixi install --manifest-path tools/omics-environment/pixi.toml -e peaks
> pixi run --manifest-path tools/omics-environment/pixi.toml -e peaks python annotate_peaks.py
> ```
> One-off instead: `pixi exec --spec "pyranges==0.1.4" --spec "pandas<3" --spec gtfparse -- python annotate_peaks.py`
> (ephemeral, **not** in the lock — record the versions in your report yourself).
>
> **Both pins are load-bearing:**
> - **`pyranges` 0.1.4 is the current release** — there is no 1.x on PyPI under this name. pyranges v1 ships
>   as a **separate distribution**, `pyranges1`, imported as `import pyranges1`. So `import pyranges as pr`
>   is the **v0 API**, and the v0 API is what this doc uses. Do not "modernise" these calls to
>   `nearest_ranges`/`merge_overlaps` — those exist only in `pyranges1`.
> - **`pandas<3` is mandatory.** pyranges 0.1.4 declares no pandas upper bound, so an unpinned install
>   pulls pandas 3.x, under which the attribute-assignment path raises
>   `ValueError: Length of values does not match length of index`. Upstream pinned `pandas<3.0.0` on master
>   but has **not released it**.

## TSS extraction from GTF

The TSS is the transcript start — strand-dependent:

```python
import gtfparse
# result_type="pandas" is REQUIRED. The default is "polars" (read_gtf.py:274), and a polars frame has no
# .feature attribute access, no boolean-mask indexing, no .copy(), and no .apply(axis=1) — the block below
# raises on every one of those if you take the default.
gtf = gtfparse.read_gtf("genes.gtf", result_type="pandas")
tx = gtf[gtf.feature == "transcript"].copy()
# + strand: TSS = start; - strand: TSS = end
tx["tss"] = tx.apply(lambda r: r.start if r.strand == "+" else r.end, axis=1)
```

## Building the TSS PyRanges — construct in ONE frame

```python
import pyranges as pr

tss_gr = pr.PyRanges(pd.DataFrame({
    "Chromosome": tx.seqname, "Start": tx.tss, "End": tx.tss + 1,
    "Strand": tx.strand, "gene_name": tx.gene_name,
}))
```

> **Never attach a column by attribute assignment after construction.** `tss_gr.gene_name = tx.gene_name.values`
> looks equivalent and **silently mis-assigns the names**. The constructor regroups rows into a per-
> `(Chromosome, Strand)` dict, and `Strand` is an *ordered* categorical `[".", "-", "+"]` — so the `-` group
> is stored **before** the `+` group. Attribute assignment then slices the flat array positionally across
> those groups, so GTF order ≠ internal order. Verified on pyranges 0.1.4 / pandas 2.3.3: **3 of 4 gene
> names landed on the wrong interval, with no error and no warning.** Every downstream "nearest gene" is
> then confidently wrong. Passing one DataFrame to the constructor keeps each row's fields together.

## Nearest-gene annotation — `Distance` is UNSIGNED, compute the sign yourself

```python
import numpy as np

annotated = peaks.nearest(tss_gr, suffix="_tss", apply_strand_suffix=False).df

# pyranges writes an absolute INTERVAL GAP into a column literally named `Distance`:
#   - there is no `distance_to_tss` column (that name is invented);
#   - it is not `peak.Start - tss.Start`;
#   - it is >= 0 always, so it cannot tell upstream from downstream.
# Verified: a peak 500-600 UPSTREAM of TSS 1000 -> Distance = 401 (= 1000-600+1); a peak at 45000
# DOWNSTREAM of TSS 40000 -> Distance = 5000. Both positive.
center = (annotated.Start + annotated.End) // 2
raw    = center - annotated.Start_tss                       # genomic-coordinate difference
annotated["signed_dist"] = np.where(annotated.Strand == "+", raw, -raw)   # - strand: upstream is HIGHER coord
annotated["direction"]   = np.where(annotated.signed_dist < 0, "upstream", "downstream")
```

Verified on all four cases (peak upstream/downstream of a `+` gene and of a `-` gene): the sign is correct
in each, including the `-`-strand flip. Without the `np.where` flip, every `-`-strand gene's upstream and
downstream are swapped.

## Feature precedence rule

A peak may overlap multiple feature types. Standard precedence (ChIPseeker convention):

```
Promoter (TSS ±3kb) > 5'UTR > 3'UTR > Exon > Intron > Downstream > Distal Intergenic
```

```python
def classify_feature(signed_dist, overlaps):
    """Apply the HIGHEST-priority matching category, not all matches.

    Takes `signed_dist` from the block above. The promoter window is symmetric, so it uses |dist|;
    keep the sign for reporting direction.
    """
    if abs(signed_dist) <= 3000:
        return "Promoter"
    if overlaps.exon:
        return "Exon"
    if overlaps.intron:
        return "Intron"
    if abs(signed_dist) <= 10000:
        return "Proximal"
    return "Distal Intergenic"
```

## Distance bands — one scheme, used everywhere

These are the bands this subskill uses. They match `classify_feature` above and `SKILL.md`'s table; do not
introduce a second scheme mid-analysis.

| Band | |distance to TSS| |
|---|---|
| promoter | ≤ 3 kb |
| proximal | 3–10 kb |
| distal | 10–100 kb |
| gene-desert | > 100 kb |

```python
bands = pd.cut(annotated.signed_dist.abs(),
               bins=[0, 3000, 10000, 100000, np.inf],
               labels=["promoter", "proximal", "distal", "gene-desert"])
print(bands.value_counts())
```

Report the full distribution, not just the nearest gene.

## ChIPseeker (R, gold standard) — not installed

```python
# Via rpy2: ChIPseeker::annotatePeak(peaks, TxDb=..., tssRegion=c(-3000, 3000))
# Returns per-peak annotation + feature distribution + distance-to-TSS plot
```

`ChIPseeker` is **not in any environment here** (nor is `rpy2`, nor a Bioconductor `TxDb`). Its
`annotatePeak` handles the precedence and produces the publication-standard feature pie chart; if you need
that exact output, report the missing R stack as a blocker rather than approximating it silently.

## Enrichment test (gained peaks in promoters)

Test whether differential peaks are enriched in a feature vs the background of all tested peaks:

```python
from scipy.stats import fisher_exact
# 2x2: (gained ∩ promoter, gained ∩ non-promoter, unchanged ∩ promoter, unchanged ∩ non-promoter)
table = [[gained_prom, gained_nonprom], [unchanged_prom, unchanged_nonprom]]
odds, p = fisher_exact(table, alternative="greater")
```

**Background universe = all tested peaks**, NOT the whole genome. Using the genome inflates enrichment.
(`scipy` **is** in `task1`, so this test runs today once you have the classification.)

## Pitfalls

- **Attaching columns by attribute assignment** — silently scrambles them across strand groups; construct
  in one DataFrame. This is the worst failure here because it never raises.
- **Trusting `Distance` as signed** — it is an unsigned gap; derive `signed_dist` strand-aware.
- **Taking `gtfparse.read_gtf`'s default** — it returns polars, and every pandas idiom below it fails.
- **Strand-unaware TSS** — using gene start for both strands mislabels − strand genes.
- **All-matches instead of precedence** — a peak counted as both promoter AND intron.
- **Whole-genome enrichment background** — inflates promoter enrichment; use tested peaks.
- **GTF 1-based vs BED 0-based** — coordinate systems differ; convert consistently.

## Grounding

`report`: annotation method (ChIPseeker/pyranges + version), tssRegion definition, per-peak nearest gene +
**signed** distance + feature class, feature distribution over the band table above, enrichment test
(Fisher, background = tested peaks) with odds + p.

## Sources

- Yu, Wang & He 2015, *Bioinformatics* 31:2382 — ChIPseeker (feature precedence + `annotatePeak`).
- Stovner & Sætrom 2020, *Bioinformatics* 36:918 — pyranges.
- The promoter ±3 kb window and the promoter/proximal/distal banding follow ChIPseeker's `tssRegion`
  convention; they are a stated analysis choice, not a biological constant — report the window you used.
