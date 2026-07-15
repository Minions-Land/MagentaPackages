# Sticker-spacer & prion-like sequence biophysics

**Maturity: REFERENCE (domain knowledge — no code dependency).** Nothing here can go stale against a library version; it is the interpretive layer the runnable docs feed into.

Interpretive background for reading composition/predictor results in terms of the sequence grammar
of phase separation. Use it to justify a property-based amino-acid ordering and to narrate why a
PS-type looks the way it does. This is domain knowledge for interpretation — not a tool to run.

## Sticker-spacer framework (Choi, Holehouse & Pappu 2020)

- **Stickers** — residues forming the associative, saturable contacts that hold a condensate
  together. In IDRs the dominant stickers are **aromatics** (Tyr > Phe; Trp) via π-π, and **Arg**
  via cation-π (Arg ≫ Lys). Sticker **valence and spacing** matter, not just count.
- **Spacers** — residues between stickers; typically **Gly** (flexible, promotes liquidity) and
  **Ser/Thr/Pro/Gln** (low-complexity). Spacer composition tunes solubility and whether the state
  stays liquid vs hardens.
- Reading: **self-assembling** proteins tend to show high sticker density (aromatics, Arg) and
  Gly-rich low-complexity spacers; **partner-dependent** proteins lean more on **charge**
  (electrostatics with an RNA/protein partner) than on intrinsic aromatic stickers.

## Prion-like domains

Compositionally biased toward **Q/N** (and G, S, Y), low hydrophobicity, low complexity. Enrichment
of Q/N in a positive set is a prion-like signal (this is exactly the bias the PLAAC score captures).

## Intrinsic disorder

LLPS grammar concentrates in **intrinsically disordered regions** — disorder is
necessary-but-not-sufficient. Restricting composition to IDR residues (see `composition_analysis.md`)
usually sharpens the self-assembling vs partner-dependent difference, because the discriminating
residues live in the disordered segments.

## Charge & patterning (Das & Pappu 2013)

- **FCR** (fraction of charged residues) and **NCPR** (net charge per residue) summarize charge.
- **κ** measures charge *patterning* — blocky (+/−) segregation promotes phase separation even at
  fixed FCR. Invoke charge/patterning when charge (not aromatics) is the axis separating the sets —
  common for partner-dependent phase separation.

## Narrating results

- Lead with the **mechanism** (self-assembling vs partner-dependent), then the **residues** that
  separate them (aromatics/Arg/Gly for self-assembly; charge for partner-dependent), then whether
  the pattern is **stronger in IDRs**, then which **predictor** discriminates it best.
- Cite the framework/predictor papers rather than asserting; keep every quantitative claim tied to a
  computed table.
