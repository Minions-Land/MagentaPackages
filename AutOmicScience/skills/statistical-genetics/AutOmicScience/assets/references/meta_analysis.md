# Meta-analysis with gwaslab

**Maturity: PARTIAL** — `gwaslab` is **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Follow `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`: §A a new Pixi feature + environment with its **own solve-group** (preferred — lands in `pixi.lock`), or §B a **named** conda env if Pixi can't solve it. Never a bare `pip install` (it can land in `base`), and never add these pins to `task1–4`. `omics_preflight` does not cover non-standard envs — check the import yourself, and record the env + versions in the `report`. If it can be neither imported nor provisioned, that is a **blocker**, not a cue to substitute a weaker method.

Combine the same variant across cohorts. `gwaslab` implements fixed- and random-effects
inverse-variance meta-analysis natively (validated against METAL) — use it rather than a
hand-rolled loop; it handles allele matching, missing-value masking, and heterogeneity.

## 1. Two studies — `SumstatsMulti` (a list of two)

```python
import gwaslab as gl
# `SumstatsPair` does NOT have run_meta_analysis (and has no base class to inherit one) — it is for
# clump / coloc / MR. Meta-analysis lives on SumstatsMulti, which takes a List[Sumstats]; "two studies"
# is simply a list of length 2. Verified against gwaslab v4.0.2.
multi = gl.SumstatsMulti([ss_discovery, ss_replication])
meta  = multi.run_meta_analysis(random_effects=False,   # fixed-effects inverse-variance
                                match_allele=True)        # flips BETA/EAF for swapped variants, drops unmatched
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
