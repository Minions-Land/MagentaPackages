# Reference — Peak Loading & QC (BED / narrowPeak)

**Maturity: REFERENCE** — peak files are TSVs and intervals are integers; **pandas on `task1` does all
of it**, including merge, overlap and nearest. `pyranges` is a convenience for interval algebra, not a
prerequisite — it is **not installed** here, and provisioning it costs an environment of its own (it pins
`pandas<3`, so it must never go into `task1–4`; see `omics-shared`'s `AOSE_nonStandard_env.md`).
Take it if the interval work is intricate enough to earn that; do not stop for it. API below verified
against pyranges **0.1.4** (executed).

> **`import pyranges as pr` is the v0 API, and 0.1.4 is the current release.** There is no 1.x on PyPI under
> the name `pyranges`; pyranges v1 ships as a separate distribution, `pyranges1` (`import pyranges1`), with
> a rewritten API (`nearest_ranges`, `merge_overlaps`, and `PyRanges` subclassing `DataFrame` so that
> `.merge()` becomes a pandas *join*). Do not "modernise" the calls in this doc — they are correct for what
> installing `pyranges` actually gives you. `pandas<3` is required because 0.1.4 declares no upper bound
> and breaks under pandas 3; upstream pinned it on master but has not released that fix.

Parsing and quality-checking ChIP-seq / ATAC-seq peak files.

## BED / narrowPeak format

Peaks come as BED3, BED6, or narrowPeak (BED6+4):

| Column | BED6 | narrowPeak extras |
|--------|------|-------------------|
| 1 | chrom | |
| 2 | start (0-based) | |
| 3 | end | |
| 4 | name | |
| 5 | score | |
| 6 | strand | |
| 7 | | signalValue (fold enrichment) |
| 8 | | pValue (-log10) |
| 9 | | qValue (-log10) |
| 10 | | peak (summit offset) |

```python
# For narrowPeak, read it with pandas and NAME THE COLUMNS YOURSELF:
import pandas as pd
cols = ["chrom","start","end","name","score","strand",
        "signalValue","pValue","qValue","peak"]
df = pd.read_csv("peaks.narrowPeak", sep="\t", header=None, names=cols)

# pr.read_bed is fine for BED3/BED6, but it MISLABELS narrowPeak:
import pyranges as pr
peaks = pr.read_bed("peaks.bed")            # BED3/BED6 -> Chromosome, Start, End, Name, Score, Strand
```

> **`pr.read_bed` does not understand narrowPeak.** It assigns the **BED12** name list positionally to
> however many columns it finds, so a 10-column narrowPeak comes back as
> `… Strand, ThickStart, ThickEnd, ItemRGB, BlockCount` — i.e. `signalValue` is silently renamed
> `ThickStart`, `pValue` → `ThickEnd`, `qValue` → `ItemRGB`, `peak` → `BlockCount`. Verified: a peak with
> `signalValue=7.5` reads back as `ThickStart=7.5`. The **values are not shifted, only the names are
> wrong** — which is worse, because `df.ThickStart` returns a plausible number rather than raising. Use the
> pandas reader above for narrowPeak, or rename the columns immediately after `read_bed`.

**0-based half-open** — BED coordinates start at 0; end is exclusive. Don't mix with 1-based (GTF/VCF).

## QC metrics

- **Peak count** — order 10⁴ for a good TF ChIP or H3K4me3; broad marks (H3K27me3/H3K9me3) give fewer,
  wider domains. Treat these as orientation only: peak count is strongly antibody-, depth-, and
  caller-dependent, so a count outside the range is a prompt to check the sample, not a verdict.
- **FRiP** (Fraction of Reads in Peaks) — **>1% is ENCODE's guidance for TF ChIP specifically** (Landt et
  al. 2012), and it does **not** generalize: ATAC-seq convention is far higher (~0.2–0.3), and broad marks
  are *expected* to score low because the signal is spread over domains rather than concentrated in peaks
  (see `histone_marks.md`). Compare FRiP against the assay's own convention, and name the assay when you
  report it.
- **Peak width distribution** — narrow (TF, ATAC ~200–500bp) vs broad (H3K27me3, H3K9me3 kb-scale)
- **Signal-to-noise** — signalValue distribution; drop peaks below a fold-enrichment threshold

```python
print(f"n peaks: {len(df)}")
print(f"width: median={df.eval('end-start').median():.0f}bp")
print(f"signalValue: median={df.signalValue.median():.2f}")
```

## Consensus peaks (merging replicates)

Overlapping peaks across replicates must be merged into a consensus set:

```python
# Combine replicate peak sets, merge overlapping intervals
combined = pr.concat([rep1, rep2, rep3])
consensus = combined.merge()   # union of overlapping intervals
# Or require peaks present in ≥2 replicates:
consensus = combined.merge(count=True)
consensus = consensus[consensus.Count >= 2]
```

## Blacklist filtering

ENCODE blacklist regions (repetitive/artifact-prone) should be removed:

```python
blacklist = pr.read_bed("hg38-blacklist.v2.bed")
peaks_clean = peaks.overlap(blacklist, invert=True)
```

## Narrow vs broad peaks

- **Narrow** (MACS2 default): TF ChIP, ATAC, H3K4me3, H3K27ac — sharp summits
- **Broad** (MACS2 --broad): H3K27me3, H3K9me3, H3K36me3 — diffuse domains

Use the right mode; calling broad marks with narrow settings fragments the domains.

## Pitfalls

- **0-based vs 1-based confusion** — BED is 0-based; off-by-one shifts annotation
- **Not filtering blacklist** — artifact regions inflate peak counts and false positives
- **Not merging replicates** — replicate-specific peaks bias differential analysis
- **Wrong peak mode** — broad marks called as narrow gives fragmented peaks
- **Ignoring FRiP** — low-enrichment samples pollute the analysis

## Grounding

`report`: n peaks per sample, peak caller + settings, FRiP if available **plus the assay it is being judged
against** (TF-ChIP / ATAC / broad mark — the thresholds differ), consensus peak count + the rule used
(union vs ≥2 replicates), blacklist filtering applied + blacklist version, genome build.

## Sources

- Landt et al. 2012, *Genome Research* 22:1813 — ENCODE/modENCODE ChIP-seq guidelines (FRiP >1% for TF ChIP,
  replicate/consensus practice).
- Amemiya, Kundaje & Boyle 2019, *Sci Rep* 9:9354 — the ENCODE blacklist (hg38-blacklist.v2).
- Zhang et al. 2008, *Genome Biology* 9:R137 — MACS (narrow vs broad calling).
- Stovner & Sætrom 2020, *Bioinformatics* 36:918 — pyranges.
- narrowPeak/BED column specs: UCSC BED format + ENCODE narrowPeak (BED6+4).
