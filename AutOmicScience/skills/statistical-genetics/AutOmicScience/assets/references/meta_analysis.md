# Meta-analysis with gwaslab

Combine the same variant across cohorts. `gwaslab` implements fixed- and random-effects
inverse-variance meta-analysis natively (validated against METAL) — use it rather than a
hand-rolled loop; it handles allele matching, missing-value masking, and heterogeneity.

## 1. Two studies — `SumstatsPair`

```python
import gwaslab as gl
pair = gl.SumstatsPair(ss_discovery, ss_replication)   # merges by CHR/POS with allele alignment
meta = pair.run_meta_analysis(random_effects=False,    # fixed-effects inverse-variance
                              match_allele=True)         # require matching alleles across studies
# `meta` is a gwaslab Sumstats with combined stats; continue with get_lead / plot / to_format
```

## 2. Many studies — `SumstatsMulti`

```python
multi = gl.SumstatsMulti([ss1, ss2, ss3, ...])
meta  = multi.run_meta_analysis(random_effects=False)
```

## 3. What the meta output contains

`run_meta_analysis` (fixed-effects) computes, per variant present in ≥2 studies:

- **Inverse-variance combine:** weight `wᵢ = 1/SEᵢ²`, combined `BETA = Σ(wᵢβᵢ)/Σwᵢ`,
  `SE = √(1/Σwᵢ)`, `Z = BETA/SE`, `P = 2·Φ(-|Z|)`.
- **Sample-size-weighted allele frequency** across cohorts (not a plain mean).
- **Effect-direction string** per study (`+`/`-`/`0`/`?`) so you can see concordance at a glance.
- **Heterogeneity:** Cochran's **Q**, **I²**, and **P_HET**.
- **Random effects** (DerSimonian-Laird) when `random_effects=True`.

It masks invalid per-study rows (null/≤0 SE, null N/EAF) and de-duplicates before combining.

## 4. Interpreting

- Report combined BETA/SE/Z/P **with** Q/I²/P_HET. High I² (e.g. > 50–75%) means between-cohort
  heterogeneity — prefer/also report the random-effects estimate and be cautious about a single
  fixed-effects effect size.
- For **discovery + replication** designs, also check **effect-direction concordance** (the
  direction string) and that the replication p is below your stated threshold — same-direction
  replication is stronger than a pooled p alone.

Command-line alternatives exist (METAL, GWAMA, PLINK `--meta-analysis`) if you need genomic-control
schemes beyond gwaslab; harmonize inputs (gwaslab) first regardless.

## Reporting

- n cohorts, n variants combined, effect allele, fixed vs random effects.
- Per lead locus: combined BETA/SE/Z/P, Q/I²/P_HET, and the per-study direction string.
