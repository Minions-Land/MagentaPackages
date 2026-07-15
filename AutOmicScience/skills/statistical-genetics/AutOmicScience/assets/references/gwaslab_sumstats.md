# GWAS summary statistics with gwaslab

**Maturity: PARTIAL** — `gwaslab` is **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Follow `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`: §A a new Pixi feature + environment with its **own solve-group** (preferred — lands in `pixi.lock`), or §B a **named** conda env if Pixi can't solve it. Never a bare `pip install` (it can land in `base`), and never add these pins to `task1–4`. `omics_preflight` does not cover non-standard envs — check the import yourself, and record the env + versions in the `report`. If it can be neither imported nor provisioned, that is a **blocker**, not a cue to substitute a weaker method.

`gwaslab` (import as `gl`) wraps a `Sumstats` object around a summary-statistics table: load →
standardize → QC → complete statistics → align alleles → extract loci. Prefer it over hand-written
pandas — it handles 60+ formats and the allele/strand edge cases.

## 1. Load (`gl.Sumstats`)

```python
import gwaslab as gl

# explicit column mapping (works for any table, including headerless via readargs)
ss = gl.Sumstats("study.txt.gz",
                 snpid="SNP", chrom="CHR", pos="POS",
                 ea="ALT", nea="REF",          # EA = effect/tested allele (beta refers to it)
                 eaf="EAF", beta="BETA", se="SE", p="P", n="N",
                 build="19", sep="\t")
# headerless whitespace file: pass column order + readargs
ss = gl.Sumstats("raw.gz", chrom=0, pos=1, nea=2, ea=3, eaf=4, beta=5, se=6, p=7,
                 readargs={"sep": r"\s+", "header": None})
# or a named format preset: fmt="plink2" / "regenie" / "saige" / "metal" / "vcf" / ...
```

Effect columns can be `beta`+`se`, `or`, `z`, `chisq`, `mlog10p`, etc.; getting `ea`/`nea` right is
essential for meta + coloc.

## 2. Standardize & QC

```python
ss.basic_check()      # normalize IDs/chr/pos/alleles, dedup, sanity-check stat ranges
```

## 2b. Genomic inflation (λ GC) — compute it explicitly, gate on it

```python
lam = ss.get_gc()      # lambda GC (median chi2 / 0.4549); also lands in ss.meta["Genomic inflation factor"]
```

Call it yourself rather than letting it appear as a side effect of `plot_mqq()`. λ is not a diagnostic
you glance at after the fact — **every** downstream p-value, lead variant and meta-analysis weight
inherits it, so it gates the interpretation of everything below.

- **λ ≈ 1** — well calibrated.
- **λ substantially > 1** — inflation: population stratification, cryptic relatedness, or an
  unmodelled covariate. This is a **finding to surface**, not a nuisance to correct away silently.
- **λ < 1** — over-correction, or a too-small effective sample.

There is no universal cutoff. Report the number next to the results and say what you concluded from
it. Caveat: in large GWAS λ is confounded with genuine polygenicity — LDSC's intercept separates the
two, and **gwaslab does not compute it**, so do not read a mildly elevated λ as proof of confounding.

## 3. Complete statistics

```python
ss.fill_data(to_fill=["BETA","SE","Z","P","MAF"])   # derive missing stats from what's present
```

Useful downstream: `MAF = min(EAF, 1-EAF)`; `Z = BETA/SE`; **`varbeta = SE**2`** (coloc wants the
variance of beta, not SE).

## 4. Align alleles (when combining studies / traits)

Cross-study allele alignment is handled automatically when you build a `SumstatsPair`/`SumstatsMulti`
(see `meta_analysis.md`, `match_allele=True`). To align a single study to a reference genome/panel
(strand, palindromic SNPs), use `ss.harmonize(ref_seq=..., ref_infer=..., ref_alt_freq=...)`.

## 5. Lead variants / loci

```python
leads = ss.get_lead(sig_level=5e-8, windowsizekb=500)   # independent lead SNPs / loci (windowed)
```

## 6. Also available

gwaslab additionally provides genome-build `liftover`, LD `clump`, Manhattan/QQ/regional/Miami plots
(`plot_mqq`, `plot_region`), and `to_format` export — reach for these only when the analysis needs
them.

## Reporting

- Per study: n variants in/out of QC, build, effect allele; any variants dropped (dup / bad alleles)
  and why.
