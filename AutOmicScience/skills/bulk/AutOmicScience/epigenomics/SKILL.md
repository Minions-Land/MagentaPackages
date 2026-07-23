---
name: bulk-epigenomics
disable-model-invocation: true
---

# Bulk Epigenomics — ChIP-seq & ATAC-seq Peak Analysis

> Subskill of `bulk`. Enter here from the parent skill when the data is bulk ChIP-seq or ATAC-seq peak files (BED format). Read the parent (`../SKILL.md`) and the always-loaded `omics-shared` skill first — their evidence/grounding rules apply here.

This subskill covers **bulk epigenomic assays**: ChIP-seq (histone marks, TF binding), bulk ATAC-seq (chromatin accessibility), differential peak occupancy/accessibility, TSS annotation, enhancer calling, and TF footprinting. **NOT single-cell chromatin (scATAC-seq)** — that's in `single-cell/atac`.

---

## Prerequisites

1. **Data format**: peak BED files (chr, start, end, name, score) from MACS2/HOMER/Genrich, or count matrices (peaks × samples)
2. **Genome annotation**: GTF/GFF for TSS extraction, gene annotation
3. **Context**: sample metadata (condition, replicate) for differential occupancy

---

## Capability Menu

| Capability | Maturity | Tool/Method | Reference Doc |
|------------|----------|-------------|---------------|
| Differential occupancy (peak DE) | **REFERENCE** | pydeseq2 on a peak × sample count matrix — **runs on `task1`**; DiffBind not installed | `assets/references/differential_occupancy.md` |
| Histone mark interpretation | **REFERENCE** | domain knowledge — no dependency | `assets/references/histone_marks.md` |
| Read counts in intervals from BAM | **REFERENCE** | `pysam` — **pinned** (`.count()` per interval, `.mapped` for library size); the `bedtools` CLI is not installed and is not needed | `assets/references/differential_occupancy.md` |
| BED / narrowPeak loading & QC | **REFERENCE** | pandas — **runs on `task1`**; `pyranges` is an optional convenience | `assets/references/peak_loading.md` |
| Interval merge / overlap / nearest | **REFERENCE** | pandas; `pyranges` if the algebra earns its own env | `assets/references/peak_loading.md` |
| TSS annotation & distance | **REFERENCE** | pandas + a chunked GTF read; `gtfparse`/`ChIPseeker` optional | `assets/references/tss_annotation.md` |
| ATAC TF footprinting | **PARTIAL** | TOBIAS — **install**; HINT/RGT unverified | `assets/references/atac_footprinting.md` |

Everything here is hand-rolled (no `omics_compute` subcommand) because peak analysis requires
study-specific judgment: which peaks to merge, how to define promoters vs enhancers, which distance bands
matter, TSS precedence rules.

> **Environment reality — read before planning a run.** The **named domain tools are absent**
> (`bedtools`, `pyranges`, `gtfparse`, `pybedtools`, `DiffBind`, `ChIPseeker`, `TOBIAS`, `rpy2`; `r-env`
> carries `r-base` + `r-essentials` only). **The work is not.** On `task1` (`modality="scrna"` — an
> environment selector, not a claim about your data): peak/BED files are TSVs for **pandas**; interval
> merge, overlap and nearest are sorts and searches; **`pysam` reads BAMs** (`.count()` per interval is
> what `bedtools multicov` computes, `.mapped` gives library size); `pydeseq2` does peak DE; `scipy`
> does the tests.
>
> The absence of a tool is a reason to check whether you need it — not a reason to stop. What genuinely
> needs provisioning is the specialised modelling: **TOBIAS** footprinting, **DiffBind**'s peak-set
> semantics, R DE stacks. Provision those into their own environment per `omics-shared`'s
> `assets/references/AOSE_nonStandard_env.md`, which carries the routing and the hard rules. If a method
> can be neither imported nor provisioned, that is a **blocker with the install command** — say it was
> not run rather than substituting a weaker one.

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step.

### 1. Load peaks (BED) — PARTIAL

`pyranges` is not pinned; provision the `peaks` env first, or use the pandas route in the ref doc.

- **`read_bed` mislabels narrowPeak.** It applies BED12 names positionally, so `signalValue` comes
  back as `ThickStart`. For narrowPeak, read it with pandas and name the columns yourself
- State the caller, its threshold, the genome build and the blacklist version — a peak set without
  them is not reproducible

→ `assets/references/peak_loading.md`

### 2. Differential occupancy — the one path that runs on `task1`

Counts in peaks per sample → pydeseq2. **`bedtools` is not installed**: bring the count matrix from
your pipeline (featureCounts / nf-core/chipseq / bedtools upstream).

- Merge replicate peaks into a consensus set **first**, and state the rule (union vs
  present-in-≥2-replicates) — they give different peak sets and therefore different results
- `design=`, not `design_factors=` (deprecated in pydeseq2 0.5.x)
- **`summary()` returns `None`** and populates `.results_df`. Binding its return value gives `None`
  and the next attribute access dies
- **Shrink before ranking** (`lfc_shrink`). Peak counts are noisier than gene counts, so this matters
  more here than in RNA — and the parent skill requires it
- **Identify differential peaks with a significance gate, not fold-change alone** — a one-sided test in
  the asked direction (depletion / gain) with **BH-FDR** across all intervals, an effect-size cut, and a
  minimum-coverage filter. This holds **even with one library per condition**: use a count-based exact
  test (Poisson / negative-binomial with a fixed dispersion) on the two libraries and treat its FDR as
  the *identification gate* (a label-permutation null is degenerate at one library per condition). A fold-change
  plus a minimum-signal cutoff is a *ranking*, not a significance call — computing the p-values and then
  labelling them "descriptive only" abandons the gate the question asks for

→ `assets/references/differential_occupancy.md`

### 3. TSS annotation — PARTIAL

Nearest-TSS per peak, then band classification.

- `gtfparse.read_gtf` defaults to **polars** — pass `result_type="pandas"` or every pandas idiom fails
- TSS is **strand-aware**: it is `start` on `+`, `end` on `−`. "Promoter = gene start" is wrong for
  half the genome
- **pyranges' `Distance` is an unsigned interval gap.** It cannot tell upstream from downstream —
  derive the signed distance yourself, strand-aware
- **Never attach a column to a PyRanges by attribute assignment** — it silently scrambles values
  across strand groups. Build the frame in one `DataFrame`
- Report the **distribution** across bands, not just "nearest gene"

→ `assets/references/tss_annotation.md`

---

## Epigenomics Best Practice (on top of omics-shared)

### 1. Histone mark interpretation

- **H3K4me3**: active promoters (the mark itself concentrates within ~1kb of the TSS)
- **H3K27ac**: active regulatory elements — at promoters *and* at enhancers; the enhancer subset is the
  **non-promoter** one (outside the promoter window below)
- **H3K27me3**: repressed/poised (Polycomb, often developmental genes)
- **H3K36me3**: gene-body mark (elongation)

Differential H3K4me3 = differential promoter activity. See `assets/references/histone_marks.md`.

### 2. Promoter vs enhancer distance bands

**One banding scheme, used everywhere in this subskill** — it matches `assets/references/tss_annotation.md`'s
`classify_feature` and its `pd.cut` bins. Do not introduce a second one mid-analysis:

| Band | |distance to TSS| |
|---|---|
| **promoter** | ≤ 3 kb |
| **proximal** | 3–10 kb |
| **distal** (candidate enhancer) | 10–100 kb |
| **gene-desert** | > 100 kb |

The bands are an **analysis choice**, not a biological constant — report the window you used. Note the two
senses of "distal": *non-promoter* (>3 kb, the sense used for H3K27ac enhancers above) vs *the distal band*
(10–100 kb). Say which you mean.

Report the distribution, not just "nearest gene."

### 3. Peak merging across replicates

Merge overlapping peaks into a consensus set before differential analysis, and state the rule (union vs
present-in-≥2-replicates) — they give different peak sets. `bedtools merge` is the usual tool but is **not
installed here**; `pyranges`' `combined.merge(count=True)` does the same in a side env
(`assets/references/peak_loading.md`).

### 4. ATAC footprinting for TF activity

ATAC signal has a **TF footprint** (depletion at the motif center, flanked by high signal). TOBIAS / HINT-ATAC detect these. Differential footprinting = differential TF activity. TOBIAS is **not installed**; its chain is ATACorrect → **ScoreBigwig** → BINDetect, and each step must consume the previous step's output (`assets/references/atac_footprinting.md`).

### 5. A provided TF ChIP-seq anchors a specific gene's enhancers

When a task provides a **sequence-specific transcription-factor ChIP-seq** alongside the histone mark
and the question targets a **specific gene's** regulatory response, use the TF peaks and their treatment
response to define that gene's **candidate distal enhancers** — TF-bound intervals within distal distance
windows of the gene — then report the histone-mark change at each anchor. Do not stop at the genome-wide
differential scan: the provided TF track is the signpost to the specific regulatory elements the question
is about, and pairing it with the mark is what identifies the responsive enhancers rather than a
chromosome-wide list.

---

## Pitfalls

- **Not merging replicate peaks** — overlapping peaks counted multiple times
- **Trusting a nearest-gene `Distance` as signed** — pyranges' `Distance` is an unsigned interval gap; it
  cannot separate upstream from downstream. Derive the sign strand-aware.
- **Attaching a column to a PyRanges by attribute assignment** — silently scrambles it across strand
  groups. Construct in one DataFrame.
- **Promoter = gene start** — TSS varies by strand; always use strand-aware TSS
- **`res = stat.summary()`** — pydeseq2's `summary()` returns `None` and populates `.results_df`; binding
  its return value gives `None` and the next attribute access dies.
- **Ranking unshrunk peak LFCs** — shrink first; peak counts are noisier than gene counts, so this matters
  more here, and the parent skill requires it.
- **No FDR** — testing thousands of peaks needs BH correction; and the FDR must be the *identification
  gate*, not a "descriptive" column next to a fold-change + min-signal call (true even at n=1 per
  condition — use a count-based exact test, e.g. fixed-dispersion NB/Poisson)
- **Histone mark misinterpretation** — H3K27me3 ≠ active; it's repressive
- **Judging a broad mark by TF-ChIP FRiP** — the >1% rule is TF-ChIP-specific; broad marks are expected to
  score low.

---

## Evidence & Reporting

Every analysis emits:
- **Peak provenance**: caller (MACS2 q<0.05?), n peaks, genome build, consensus rule, blacklist version
- **Differential occupancy**: n tested, n significant (padj<0.05), **shrinkage coeff**, top hits with log2FC
- **TSS annotation**: per-peak **signed** distance, band classification distribution, the window used
- **Which packages were actually available** — most of this subskill's toolchain is not installed (see the
  Environment reality note above). If a step was not run, say so; do not report a number you could not compute.
- **Figures** → inspect each before it backs a claim

See reference docs for per-analysis reporting templates.

## Provenance

Every recipe here is standard bulk-epigenomics methodology traceable to external field authorities (ENCODE
ChIP-seq guidelines, MACS, ChIPseeker, DiffBind, TOBIAS, Roadmap/ChromHMM) — see the `## Sources` block in
each method doc. Package APIs were verified against upstream source at the versions named in each doc;
where a package is absent from this environment, its recipe was checked against source but **not executed**,
and each doc says which.
