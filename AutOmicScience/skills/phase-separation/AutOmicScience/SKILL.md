---
name: phase-separation
description: Biomolecular condensate & liquid-liquid phase separation (LLPS) sequence analysis — amino-acid composition profiling and fold-change versus non-phase-separating controls, intrinsically disordered region (IDR) restricted composition, sticker-spacer and prion-like / low-complexity domain features, and benchmarking phase-separation predictors (PScore, PLAAC, catGRANULE, FuzDrop, and composite SaPS/PdPS feature-model scores) by ROC-AUC. Use when you have protein sequences and/or precomputed phase-separation propensity scores with condensate-related labels (self-assembling vs partner-dependent vs non-PS, or membraneless-organelle participants vs membrane-bound controls) and need to compare sequence composition or evaluate how well predictors discriminate phase-separating proteins.
requiredTools: [run_python, bash, read, write, observe_figure]
tags: [protein, phase-separation, llps, condensate, idr, prion-like, sticker-spacer, roc-auc, sequence-biophysics]
---

# Biomolecular Condensate / LLPS Sequence Analysis

Sequence-level analysis of liquid-liquid phase separation (LLPS): compare the amino-acid
composition of phase-separating proteins against non-phase-separating controls, restrict the
comparison to intrinsically disordered regions (IDRs), reason about sticker-spacer and
prion-like architecture, and benchmark how well published phase-separation predictors
discriminate condensate proteins. Builds on `omics-shared` (loaded automatically — its
evidence/grounding rules apply).

This is **sequence and predictor-score analysis**. It does **NOT** run molecular-dynamics
simulations, does **NOT** compute structures, and does **NOT** re-train the predictors —
it profiles composition and evaluates predictor scores you already have (or can compute).

---

## Domain background (read once)

Phase-separating proteins are commonly split by mechanism:

- **Self-assembling (SaPS)** — drive condensation largely on their own (multivalent IDRs,
  strong sticker density).
- **Partner-dependent (PdPS)** — phase-separate only with a partner (RNA, another protein);
  weaker intrinsic sticker density, often more charge-driven.
- **Non-PS (NoPS)** — negative controls that do not phase-separate.

The sequence grammar (Choi, Holehouse & Pappu, *Annu Rev Biophys* 2020) is **sticker-spacer**:
**stickers** (aromatics Y>F, and Arg via cation-π; also π-π contacts) drive associative
interactions; **spacers** (Gly/Ser/Pro-rich low-complexity, disordered) tune solubility.
Prion-like domains (Q/N-rich, Alberti) and RGG/RG motifs are recurrent signatures. Composition
differences between SaPS and PdPS are therefore expected to concentrate in aromatics, Arg,
Gly, and the polar/low-complexity residues, and to be sharpest **inside IDRs**.

Predictors encode different priors: **PScore** (Vernon 2018, planar π-π contact propensity),
**PLAAC** (Lancaster 2014, prion-like HMM composition), **catGRANULE** (Bolognesi 2016, RNA-granule
propensity incl. disorder + RNA-binding), **FuzDrop** (Hardenberg 2020, droplet-promoting
probability p_DP), and composite multi-feature models that emit separate self-assembling (SaPS) and partner-dependent (PdPS) scores. Because they
encode different biology, evaluate each **separately** and per PS-type.

---

## Prerequisites

1. **Sequences and/or scores** — either FASTA/`Sequence` column of protein sequences, or a
   table of precomputed predictor scores per protein (or both).
2. **Labels** — binary membership flags for the positive set(s) (e.g. SaPS, PdPS, or a curated
   condensate/MLO participant set) and a negative/background set (NoPS or a membrane-bound control).
3. **(Optional) IDR ranges** — per-protein disordered-region coordinates (from IUPred2A / MobiDB /
   D2P2) to restrict composition to IDRs.
4. **Library** — `numpy`, `pandas`, `scikit-learn` (ROC-AUC), `scipy` (paired tests). **All four are
   already pinned** in `task1–4` (numpy 2.4, pandas 2.3, scikit-learn 1.9, scipy 1.17) — select the env
   with `modality="scrna"` (an environment selector, not a claim about your data) and import them.
   Nothing to install.

Only `openpyxl` is missing, and only if your inputs are `.xlsx`. Provision it per `omics-shared`'s
`assets/references/AOSE_nonStandard_env.md` — or sidestep it by exporting the sheet to CSV, which is
usually the cheaper move for a one-off table.

> **Do not `pip install numpy pandas scikit-learn scipy`.** They are already here. A bare `pip`
> resolves against whatever `python` leads `$PATH` — frequently conda `base` — and reinstalling these
> four is the single most effective way to downgrade the versions `task1–4` are locked to and break
> every other skill in the package. If you need a package that genuinely is missing, it goes in a
> named env with its own solve-group. Never `base`, never a bare `pip`.

---

## Capability Menu

| Capability | Maturity | Method | Reference Doc |
|------------|----------|--------|---------------|
| Set-level amino-acid composition (pooled) | **REFERENCE** | concatenate → count → normalize | `assets/references/composition_analysis.md` |
| Fold-change vs non-PS reference | **REFERENCE** | ratio with stabilization | `assets/references/composition_analysis.md` |
| Property-based amino-acid ordering | **REFERENCE** | disorder / charge / hydrophobicity / aromaticity scales | `assets/references/composition_analysis.md` |
| IDR-restricted composition | **REFERENCE** | 1-based-inclusive segment extraction | `assets/references/composition_analysis.md` |
| Sticker-spacer / prion-like interpretation | **REFERENCE** | biological reading of composition | `assets/references/sequence_biophysics.md` |
| Predictor discrimination (ROC-AUC) | **REFERENCE** | per-predictor, per-PS-type AUC | `assets/references/predictor_benchmarking.md` |
| Dataset-vs-control predictor comparison | **REFERENCE** | per dataset×predictor AUC + paired test | `assets/references/predictor_benchmarking.md` |

All **REFERENCE** — LLPS analysis needs judgment on set definition, IDR handling, and score
orientation. Read the method doc before running each capability.

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step.

### 1. Sequence composition / biophysics

Per-protein amino-acid composition, charge, hydropathy, aromatics.

- Composition is only meaningful against a **matched background** — a whole-proteome baseline is not
  the same comparison as a length-matched or localisation-matched control. State which
- Report the **feature definition**, not just the number: "aromatic fraction" means nothing without
  the residue set

→ `assets/references/sequence_biophysics.md`

### 2. Restrict to IDRs (optional)

Slice the sequence to disordered regions from UniProt / MobiDB / IUPred2A / D2P2.

- **The coordinates are 1-based inclusive.** Python slicing is 0-based half-open, so you subtract 1
  from **START only** — the END is already exclusive-correct. An off-by-one here shifts every residue
  and silently changes every composition number downstream
- Whether to restrict at all is a design decision: IDR-only sharpens the signal but discards folded
  domains that may genuinely contribute

→ `assets/references/composition_analysis.md`

### 3. Compare positive vs background sets

Composition of a condensate/MLO participant set against a negative set.

- The **negative set defines the result**. NoPS vs a membrane-bound control answer different questions
- Paired vs unpaired test follows from the design, not from convenience

→ `assets/references/composition_analysis.md`

### 4. Benchmark a predictor

ROC-AUC of a predictor's scores against the labels.

- **ROC-AUC is misleading on heavy class imbalance** — condensate positives are rare. Report AUPRC
  beside it, and the positive rate, or a 0.9 AUC can mean nothing
- Never benchmark on sequences the predictor trained on; state the overlap you checked

→ `assets/references/predictor_benchmarking.md`

---

## Best Practice (on top of omics-shared)

- **Pool, don't average** — set composition = pooled residue counts / total residues.
- **Ratios for fold-change** — enrichment is a ratio vs the reference set, with a small stabilizer.
- **Separate comparisons** — SaPS-vs-NoPS and PdPS-vs-NoPS (and each dataset-vs-control) are
  independent; never pool PS-types or predictors into one AUC.
- **Fixed negative background** — one shared NoPS/control set makes AUCs comparable across positives.
- **1-based inclusive IDR coordinates** — `seq[start-1:end]`; document off-by-one handling.
- **Per-predictor NaN + orientation** — drop missing per predictor; check AUC<0.5 for flips.

---

## Pitfalls

- **Per-protein-averaged composition** — length-biased; always pool residues.
- **Fold-change by subtraction** — must be a ratio.
- **Label leakage** — a protein flagged both positive and negative, or "PS" defined as "not NoPS"
  (absence of a flag) rather than an explicit negative set.
- **One AUC over pooled predictors/PS-types** — hides which predictor works for which mechanism.
- **IDR off-by-one** — `seq[start:end]` or `seq[start-1:end-1]` corrupts the segment; use `seq[start-1:end]`.
- **Ignoring score direction** — a reverse-scored predictor looks useless (AUC<0.5) unless negated.
- **Silent NaN drops** — undocumented per-predictor missingness changes the evaluated set.

---

## Evidence & Reporting

Every analysis emits:
- **Sets**: name and size of each positive and negative set; overlap check.
- **Composition**: pooled 20-AA fractions per set (summing to ~1.0) and fold-change vs reference;
  property-ordering rationale; IDR-restricted version if IDR data present.
- **Predictors**: per-predictor, per-PS-type ROC-AUC with sample sizes and NaN counts; group
  comparison statistic for dataset-vs-control.
- **Interpretation**: sticker-spacer / prion-like reading, with predictor-paper citations.
- **Figures** → inspect before citing.

See the reference docs for per-analysis templates.
