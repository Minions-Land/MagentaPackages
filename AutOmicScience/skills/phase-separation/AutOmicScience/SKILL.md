---
name: phase-separation
description: Biomolecular condensate & liquid-liquid phase separation (LLPS) sequence analysis — amino-acid composition profiling and fold-change versus non-phase-separating controls, intrinsically disordered region (IDR) restricted composition, sticker-spacer and prion-like / low-complexity domain features, and benchmarking phase-separation predictors (PScore, PLAAC, catGRANULE, FuzDrop, and composite SaPS/PdPS feature-model scores) by ROC-AUC. Use when you have protein sequences and/or precomputed phase-separation propensity scores with condensate-related labels (self-assembling vs partner-dependent vs non-PS, or membraneless-organelle participants vs membrane-bound controls) and need to compare sequence composition or evaluate how well predictors discriminate phase-separating proteins.
requiredTools: [run_python, bash, read, write, observe_figure]
tags: [protein, phase-separation, llps, condensate, idr, prion-like, sticker-spacer, roc-auc, sequence-biophysics]
extends: omics-shared
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
4. **Library** — `numpy`, `pandas`, `scikit-learn` (ROC-AUC), `scipy` (paired tests). All standard.

```bash
pip install numpy pandas scikit-learn scipy openpyxl   # openpyxl only if inputs are .xlsx
```

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

### 1. Define positive and negative sets (leakage-free)

- Build each comparison as **positive vs a clean negative**: SaPS-vs-NoPS and PdPS-vs-NoPS are
  **separate** comparisons.
- Positives and negatives must be **mutually exclusive** (no protein in both). If SaPS and PdPS
  overlap, keep them separate — do not merge into one "PS" bucket that leaks across comparisons.
- Use a **single fixed negative background** across all comparisons so AUCs are comparable.
- Report the size of every set.

### 2. Pooled amino-acid composition

Compute composition at the **set level by pooling residues**, not by averaging per-protein
fractions (per-protein averaging biases toward short sequences):

```python
from collections import Counter
AA = "ACDEFGHIKLMNPQRSTVWY"

def pooled_composition(seqs):
    c = Counter()
    total = 0
    for s in seqs:
        s = "".join(ch for ch in str(s).upper() if ch in AA)  # drop X/B/Z/gaps
        c.update(s); total += len(s)
    return {a: c.get(a, 0) / total for a in AA}, total   # fractions sum to ~1.0
```

See `assets/references/composition_analysis.md`.

### 3. Fold-change vs the non-PS reference

```python
import numpy as np
def fold_change(pos_comp, neg_comp, eps=1e-9):
    return {a: (pos_comp[a] + eps) / (neg_comp[a] + eps) for a in AA}   # ratio, not difference
```

Report fold-change (or log2 fold-change) per amino acid; a value >1 means enrichment in the
positive set. **Fold-change is a ratio** — never a subtraction.

### 4. Property-based ordering

Order the 20 amino acids by a **defensible physicochemical scale** (IDR/disorder propensity,
charge, hydrophobicity, aromaticity) and apply the **same order** to every set so patterns are
comparable. Motivate the choice biologically (aromatics/Arg = stickers; Q/N = prion-like; G/S/P =
low-complexity spacers). You may also derive an ordering **empirically** from IDR frequencies
(step 5). See the reference doc.

### 5. IDR-restricted composition (if IDR ranges available)

IDR coordinates from UniProt/MobiDB/IUPred are almost always **1-based inclusive**. Convert to
Python slicing carefully:

```python
# start,end are 1-based inclusive residue positions
idr_segment = full_sequence[start - 1 : end]   # subtract 1 from START only
```

Concatenate IDR segments per set, recompute pooled composition, and compare — differences are
usually sharper inside IDRs. Report proteins dropped for missing IDR annotation or sequence.

### 6. Predictor benchmarking (ROC-AUC)

For **each predictor separately** and **each PS-type separately**, score positives vs the fixed
negative:

```python
from sklearn.metrics import roc_auc_score
# per (predictor, comparison): drop NaN in THIS predictor's column, keep both classes
mask = df[[pred_col]].notna().all(axis=1)
auc = roc_auc_score(df.loc[mask, "label"], df.loc[mask, pred_col])
```

- **Handle NaN per predictor-comparison pair** (different predictors miss different proteins).
- **Verify score orientation** — higher score should mean more PS-prone; if a predictor is
  reverse-scored, negate it. AUC ≈ 0.5 is random; < 0.5 usually means flipped orientation.
- For **multiple positive datasets vs a control group** (e.g. MLO participants vs membrane-bound
  controls): compute AUC for every dataset×predictor, then compare groups with a **paired test**
  across predictors (e.g. one-sided Wilcoxon) and aggregate. See `predictor_benchmarking.md`.

### 7. Interpret & ground

Tie composition and AUC patterns back to sticker-spacer / prion-like biology, cite the predictor
papers, and state which predictor discriminates which PS-type best. Inspect any ROC or
composition plot before it backs a claim.

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
