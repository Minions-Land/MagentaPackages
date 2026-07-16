# Reference — ATAC-seq TF Footprinting

**Maturity: PARTIAL** — **TOBIAS is not installed in any environment here** (nor is HINT/RGT). Provision it
into its own environment per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` — its own env,
because TOBIAS drags in a heavy tree (`pyBigWig`, `MOODS`) that has no business in `task1–4`:

```toml
# pixi.toml, at your analysis root
[workspace]
name = "tobias"
channels = ["conda-forge", "bioconda"]
platforms = ["linux-64"]

[dependencies]
tobias = "*"                      # bioconda
```
```bash
pixi lock && pixi install --locked
pixi run --frozen TOBIAS ATACorrect --help
```
If that solve fails, fall back to a **named** conda env — never `base` — and record the exact versions in
the report, since a conda env is not in any lock. Footprinting also needs BAMs + a genome FASTA, which
the `omics_compute` path never produces — if you have neither, that is a blocker to report, not a step to
approximate. Commands below verified against `loosolab/TOBIAS` v0.14.0 and re-checked against `main`
(0.17.4) — they hold on both.

Detecting transcription-factor binding from ATAC-seq via footprint analysis — TF-bound sites show local signal depletion (protein occludes Tn5 cutting) flanked by high accessibility.

## The footprint signal

At a TF-bound motif:
- **Center** (motif): signal depletion (TF protein blocks Tn5 transposase)
- **Flanks** (±50bp): signal peaks (open chromatin around the binding site)

Differential footprinting = differential TF activity.

## TOBIAS (standard tool)

TOBIAS: Transcription factor Occupancy prediction By Investigation of ATAC-seq Signal.

The chain is **ATACorrect → ScoreBigwig → BINDetect**, and each step consumes the previous step's output.
Run steps 1–2 **per condition**; BINDetect is the step that compares them.

```bash
# 1. Bias correction (Tn5 cutting bias). Emits <outdir>/<bam-basename>_corrected.bw
#    (plus _uncorrected/_bias/_expected.bw) — the prefix comes from the BAM filename.
TOBIAS ATACorrect --bam cond1.bam --peaks consensus_peaks.bed \
  --genome hg38.fa --outdir corrected/
TOBIAS ATACorrect --bam cond2.bam --peaks consensus_peaks.bed \
  --genome hg38.fa --outdir corrected/

# 2. Footprint scoring — the subcommand is ScoreBigwig. ("FootprintScores" was renamed in v0.4.0
#    (2019-04-29); the old name survives as a hidden alias that still parses but is absent from --help.)
TOBIAS ScoreBigwig --signal corrected/cond1_corrected.bw \
  --regions consensus_peaks.bed --output cond1_footprints.bw
TOBIAS ScoreBigwig --signal corrected/cond2_corrected.bw \
  --regions consensus_peaks.bed --output cond2_footprints.bw

# 3. Differential footprinting. --genome is REQUIRED (BINDetect exits with
#    "ERROR: Missing argument --genome" without it). --signals takes the FOOTPRINT bigwigs from step 2.
TOBIAS BINDetect --motifs jaspar_motifs.txt \
  --signals cond1_footprints.bw cond2_footprints.bw \
  --peaks consensus_peaks.bed --genome hg38.fa \
  --outdir bindetect_out/ --cond-names cond1 cond2
```

> **Feed BINDetect the footprint scores, not the corrected cut-sites.** Passing
> `corrected/*_corrected.bw` (step 1's output) straight into `--signals` **runs without error** — a bigwig
> is a bigwig — and inverts the biology: BINDetect calls a site bound when the signal *exceeds* a
> threshold, but a bound site has **low** corrected cut-site signal and **high** footprint score. If step
> 2's output is not what step 3 consumes, step 2 did nothing and step 3 is scoring the wrong quantity.

**Output.** BINDetect writes `bindetect_out/bindetect_results.txt` (and `.xlsx`, plus
`bindetect_distances.txt`, `bindetect_figures.pdf`, and per-TF `<TF>/<TF>_overview.txt` +
`<TF>/beds/<TF>_<cond>_{bound,unbound}.bed`). With `--cond-names cond1 cond2`, the columns of
`bindetect_results.txt` are exactly:

`output_prefix`, `name`, `motif_id`, `cluster`, `total_tfbs`, `cond1_mean_score`, `cond1_bound`,
`cond2_mean_score`, `cond2_bound`, `cond1_cond2_change`, `cond1_cond2_pvalue`, `cond1_cond2_highlighted`

Read that column list literally:
- The TF name is **`name`** / `output_prefix`. There is **no `TF_name` column** — that insert is commented
  out in TOBIAS's own source.
- The per-condition statistic is **`<cond>_mean_score`** (mean footprint score) and **`<cond>_bound`** (a
  site count). TOBIAS has **no "footprint depth" concept** at all.
- The differential statistic is **`<cond1>_<cond2>_change`**, not `log2FC`. A `log2fc` exists only
  **per-site**, in `<TF>_overview.txt` as `cond1_cond2_log2fc` — a different file at a different
  granularity. Do not conflate them.
- The p-value is always comparison-prefixed: **`<cond1>_<cond2>_pvalue`**, never bare `pvalue`.

## HINT-ATAC (alternative)

```bash
rgt-hint footprinting --atac-seq --paired-end --organism=hg38 \
  --output-location=. condition1.bam peaks.bed

rgt-motifanalysis matching --organism=hg38 \
  --input-files condition1_footprints.bed
```

HINT is faster but less granular than TOBIAS for differential analysis. Like TOBIAS, RGT is **not installed
here** — provision it per `AOSE_nonStandard_env.md` (`rgt` on PyPI; a named conda env if the solve fails, since it
compiles C extensions).

Both commands verified against `CostaLab/reg-gen` rev `66f5fbb`: `footprinting` is a real subcommand
(`rgt/HINT/Main.py:52`) and `--atac-seq`, `--paired-end`, `--organism`, `--output-location` all exist
(`rgt/HINT/Footprinting.py:96+`), with BAM + BED as positionals (`input_files`, metavar
`reads.bam regions.bed`). `matching` is real (`rgt/motifanalysis/Main.py:41`) and `--input-files`
(metavar `regions.bed`, `nargs='+'`) is real (`rgt/motifanalysis/Match.py:110`) — note it is **mutually
exclusive** with `--input-matrix`, and `--organism` is **required**.

> **`--organism=hg38` resolves against a data directory the install does not fill.** RGT reads
> `$RGTDATA`, defaulting to **`~/rgtdata`** (`setup.py:238`). `setup.py` writes the *config* pointing at
> `genome_hg38.fa` / `chrom.sizes.hg38` / `genes_Gencode_hg38.bed` (`:288-293`) but contains **no download
> logic** — the genomes come from a separate script, `data/setupGenomicData.py` (`:383` "Downloading hg38
> genome"), which must be run after install. A fresh `rgt` install therefore has a valid config pointing at
> files that do not exist. If you cannot fetch that data, it is a blocker to report.

## Interpreting differential footprints

- **↑ footprint depth in condition A** → TF more active/bound in A
- **Motif present but no footprint** → motif not occupied (pioneer site, or TF not expressed)
- **Footprint without motif match** → composite/indirect binding, or low PWM score

Footprinting is **condition-specific** — a TF's expression must be high for binding to occur. Cross-check TF mRNA expression (bulk RNA-seq) to validate.

## Motif databases

- **JASPAR** (2024 release): curated vertebrate TFs
- **HOCOMOCO** (v11): human/mouse TF motifs
- **CIS-BP**: comprehensive, many species

Match the organism and version to the ATAC-seq genome build.

## Pitfalls

- **Feeding BINDetect the corrected cut-site bigwigs instead of the footprint scores** — runs silently,
  inverts the bound/unbound call. Step 3's `--signals` must be step 2's `--output` files.
- **Omitting `--genome` from BINDetect** — hard exit: `ERROR: Missing argument --genome`.
- **Inventing output columns** — the differential statistic is `<cond1>_<cond2>_change`; there is no
  `log2FC` column in `bindetect_results.txt`, and no `TF_name`. Read the real header before citing a number.
- **No bias correction** — Tn5 has sequence bias; raw signal gives false footprints
- **Comparing raw ATAC signal instead of footprints** — open region ≠ TF-bound; need the footprint shape
- **Motif match without expression check** — a motif is just sequence; the TF must be expressed
- **Using the wrong motif database version** — organism mismatch or outdated PWMs
- **Not validating differential footprinting with TF expression** — ↑ footprint + ↑ TF mRNA is stronger evidence than footprint alone

## Grounding

`report`: tool + **version** (TOBIAS / HINT), motif database + version, bias-correction applied, and — using
the real column names — per-TF `<cond>_mean_score`, `<cond>_bound`, `<cond1>_<cond2>_change`,
`<cond1>_<cond2>_pvalue` from `bindetect_results.txt`; TF expression validation (RNA-seq) if available; top
differential TFs with motif examples. Cite the column you actually read; a "log2FC" in a footprinting
report is a sign the number was invented rather than parsed.

## Sources

- Bentsen et al. 2020, *Nat Commun* 11:4267 — TOBIAS (ATACorrect / ScoreBigwig / BINDetect).
- Li et al. 2019, *Genome Biology* 20:45 — HINT-ATAC.
- Castro-Mondragon et al. 2022, *NAR* 50:D165 — JASPAR 2022 (2024 release is current).
- Vorontsov et al. 2024, *NAR* — HOCOMOCO v12 (supersedes the v11 named above).
