# Amino-acid composition & fold-change for LLPS

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

Goal: quantify how the residue composition of phase-separating proteins differs from non-PS
controls, at whole-sequence and IDR resolution, in a way that is comparable across sets.

## 1. Pooled (set-level) composition

Composition is a property of the **set of residues**, so pool residues across all proteins in the
set, then normalize once. Do **not** average per-protein fractions — short proteins would be
over-weighted.

```python
from collections import Counter
import pandas as pd

AA = list("ACDEFGHIKLMNPQRSTVWY")   # 20 standard amino acids, fixed order

def pooled_composition(seqs):
    """Return (dict aa->fraction summing to ~1.0, total_residues)."""
    c, total = Counter(), 0
    for s in seqs:
        s = "".join(ch for ch in str(s).upper() if ch in set(AA))  # drop X/B/Z/U/*/gaps
        c.update(s); total += len(s)
    if total == 0:
        raise ValueError("no valid residues in set")
    return {a: c.get(a, 0) / total for a in AA}, total
```

Sanity checks: fractions sum to ≈1.0 (±rounding); every set reports its `total_residues` and
protein count. Non-standard characters are dropped explicitly, not silently coerced.

## 2. Fold-change vs the non-PS reference

Enrichment is a **ratio** of the positive-set fraction to the reference-set fraction, with a small
stabilizer to avoid divide-by-zero for rare residues (W, C):

```python
import numpy as np
def fold_change(pos, neg, eps=1e-9):
    fc   = {a: (pos[a] + eps) / (neg[a] + eps) for a in AA}
    log2 = {a: float(np.log2(fc[a]))          for a in AA}
    return fc, log2
```

`fc[a] > 1` → residue enriched in the positive set. Report both raw and log2. Never use
`pos[a] - neg[a]` — a difference of fractions is not a fold-change.

## 3. Property-based ordering

Present amino acids in a **physicochemically meaningful order**, identical across every set, so the
enrichment pattern is legible. Pick one defensible basis and justify it:

- **Disorder / IDR propensity** (e.g. TOP-IDP, Campen 2008): S, P, E, K, Q, G … at the
  disorder-promoting end; W, F, Y, I, L … at the order-promoting end.
- **Charge**: acidic (D, E), basic (K, R, H), then polar/uncharged, then hydrophobic.
- **Aromaticity / stickers**: highlight F, Y, W (and R for cation-π).
- **Prion-like**: highlight Q, N, G, S, Y.

You may also derive the order **empirically** from IDR frequencies (section 4): rank amino acids
by their pooled IDR frequency (high→low) and reuse that order everywhere. State the chosen basis
and why it is relevant to phase separation (disorder + stickers drive condensation).

## 4. IDR-restricted composition

If per-protein IDR intervals are available, repeat the composition/fold-change analysis using only
IDR residues — LLPS grammar lives disproportionately in disordered regions.

Coordinate convention: IDR start/end from UniProt, MobiDB, IUPred2A, D2P2 are **1-based inclusive**.
Python slicing is 0-based, end-exclusive, so:

```python
def extract_idr(seq, intervals):
    """intervals: list of (start, end), 1-based inclusive. Returns concatenated IDR string."""
    out = []
    for start, end in intervals:
        out.append(seq[start - 1 : end])   # subtract 1 from START only; END already exclusive-correct
    return "".join(out)
```

- A protein can have multiple IDR intervals — concatenate all of them.
- Report and exclude proteins with **no IDR annotation** or **missing sequence** (don't drop silently).
- Recompute pooled composition + fold-change on the IDR-only strings; compare to whole-sequence.

## 5. Reporting

- Table: 20-AA fraction per set (whole-sequence and IDR), fold-change + log2FC vs reference.
- The property-ordering basis and rationale (one sentence tying it to sticker-spacer / disorder).
- Set sizes (proteins and residues); counts of proteins dropped for non-standard sequence / no IDR.
- One or two sentences interpreting the top enriched/depleted residues per PS-type
  (e.g. aromatics/Gly for self-assembly; charge shifts for partner-dependent).
