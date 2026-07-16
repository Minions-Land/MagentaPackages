# Compositional Analysis — Did cell-type abundance shift?

**Maturity: REFERENCE** — no compute subcommand. §1/§2 (the inferential tests) run in a Python script
with `pertpy` — install it for the task. §3 (Ro/e) is descriptive and needs only pandas + scipy, both
already in the pinned env. Emit a `report` dict and `print(report)` to stay grounded.

**This doc owns abundance only.** For "which *genes* changed between conditions" see
`markers_de.md` (Part B, pseudobulk + PyDESeq2 — already in the pinned env). Both can be true at
once: a cell type can expand while its genes go down.

## Goal / When to Use

Test whether the **proportion of a cell type** (or the density of a transcriptional neighbourhood)
differs between conditions. Requires an annotation you trust and, critically, **biological
replicates** — several samples per condition, not several cells.

## Decision Criteria

- **Discrete, trusted cell types + sample-level design** → **scCODA** (`pt.tl.Sccoda`). Bayesian,
  models counts as compositional, reports credible effects against a reference type.
- **No trustworthy discretisation, or shifts inside a cell type** → **Milo** (`pt.tl.Milo`). Tests
  differential abundance over kNN neighbourhoods, so it catches a subpopulation shifting without
  needing a cluster label for it. Needs `pertpy[milo-edger]` **and a working R** (it calls edgeR
  through rpy2).
- **Per-type proportion tests** (Mann-Whitney/WLS on proportions, + BH) — the compositional caveat and
  when it binds, below.
- **Only *describing* which types sit in which tissue** (a TME-atlas style figure) → **Ro/e** (§3).
  Descriptive only: no p-value, no inference, not a substitute for §1/§2.

**`pertpy` is in no pinned env** — provision it per `omics-shared`'s
`assets/references/AOSE_nonStandard_env.md` (§A: a `pertpy` feature + env with its own `solve-group`;
spec `pertpy` for scCODA, `pertpy[milo-edger]` for Milo). Never a bare `pip install` — it can land in
`base`. Verified absent from `pixi.toml`/`pixi.lock`; a stale copy may linger in an un-rebuilt
`.pixi/envs/task1`, so check the import in the env you actually run, not a previous session's.
Tools are in `pt.tl`; **plots are methods on the tool object**, not in `pt.pl`.

### The compositional caveat, and when it binds

Proportions sum to 1, so one type expanding mechanically shrinks every other. A per-type test can
score that artifact as a real effect — classically, several types "changing" in opposite directions
when only one moved. scCODA exists because of this: it models the counts as compositional against a
reference type.

That failure is worst where it is easiest to hit: **few samples, two conditions, one large type
dominating the shift.** It weakens as the design gets wider — with a few hundred donors and BH across
types, a per-type screen is standard practice in the field and is what much of the published
literature reports.

So this is a judgement, not a rule. What the two paths actually give you differs, and that usually
decides it:

- **scCODA** returns credible effects against a reference type — **no FDR-adjusted p-value per type**
  (see the "credible ≠ significant" note below). If the question asks for per-type p and q, it cannot
  answer it, however correct it is.
- **A per-type screen** (WLS weighted by donor cell count, or Mann-Whitney; + BH) returns exactly that
  table, and carries the compositional caveat with it — which belongs in the interpretation, not in a
  refusal to run.

Say which you ran and why, and report the caveat alongside the numbers.

## 1. scCODA — sample-level compositional test

```python
import pertpy as pt

sccoda = pt.tl.Sccoda()
mdata = sccoda.load(
    adata, type="cell_level", generate_sample_level=True,
    cell_type_identifier="cell_type",   # obs column with the annotation
    sample_identifier="sample_id",      # obs column with the biological replicate
    covariate_obs=["condition"],        # obs columns to carry to the sample level
)
mdata = sccoda.prepare(mdata, formula="condition", reference_cell_type="automatic")
sccoda.run_nuts(mdata, rng_key=0)       # MCMC; rng_key makes it reproducible

credible = sccoda.credible_effects(mdata)   # Series: (covariate, cell type) -> bool
effects = sccoda.get_effect_df(mdata)       # effect sizes / log2-fold changes
sccoda.plot_effects_barplot(mdata, covariates="condition")
```

Every argument after `data` is keyword-only — `plot_effects_barplot(mdata, "condition")` binds
`"condition"` to `modality_key` and raises `TypeError: takes 2 positional arguments but 3 were
given`.

**Why these choices:** `formula="condition"` is the design — add covariates as `"condition + batch"`.
`reference_cell_type="automatic"` picks the type with the lowest relative-abundance dispersion that
is present in ≥90% of samples; name a type explicitly if you know one is genuinely unchanged.
`credible_effects` is a **boolean per (covariate, cell type)** — scCODA reports credible intervals,
not p-values, so there is no FDR column to threshold.

**Read the reference back for your report:**

```python
ref = mdata["coda"].uns["scCODA_params"]["reference_cell_type"]
```

**Tune the FDR** with `sccoda.set_fdr(mdata, est_fdr=0.2)` then re-read `credible_effects` — the
default (0.05) is conservative for small sample sizes.

## 2. Milo — neighbourhood-level differential abundance

```python
import scanpy as sc

milo = pt.tl.Milo()
mdata = milo.load(adata)
sc.pp.neighbors(mdata["rna"], n_neighbors=30)          # build the kNN graph first
milo.make_nhoods(mdata["rna"], prop=0.1)               # sample 10% of cells as nhood indices
mdata = milo.count_nhoods(mdata, sample_col="sample_id")
milo.da_nhoods(mdata, design="~condition")             # calls edgeR via rpy2

res = mdata["milo"].var                                # logFC, PValue, SpatialFDR per nhood
milo.annotate_nhoods(mdata, anno_col="cell_type")      # label nhoods by majority cell type
milo.plot_da_beeswarm(mdata)
```

`prop` sets how many cells seed neighbourhoods — 0.1 is the default; lower it for very large
datasets. Milo's unit is a **neighbourhood, not a cell type**, so results are "N neighbourhoods
annotated mostly as X shifted", which is a weaker but more honest claim when the annotation is
uncertain. Filter on `SpatialFDR` (spatially-corrected), not `PValue`.

## 3. Ro/e — descriptive tissue enrichment (not a test)

Ro/e (ratio of observed to expected) is the standard *descriptive* summary of which cell types
concentrate in which tissue or compartment — the TME-atlas convention for tumor vs adjacent-normal vs
blood. It is **not** an alternative to §1/§2: it yields no p-value and makes no inference. Use it to
**describe** composition in a figure; use scCODA/Milo to **test** whether composition shifted.

```python
import pandas as pd, numpy as np
from scipy.stats import chi2_contingency

obs = pd.crosstab(adata.obs["cell_type"], adata.obs["tissue"])   # rows = cell types, cols = tissues
_, _, _, expected = chi2_contingency(obs)          # expected counts under cell-type ⟂ tissue
expected = pd.DataFrame(expected, index=obs.index, columns=obs.columns)

roe = obs / expected                               # >1 enriched in that tissue, <1 depleted
residuals = (obs - expected) / np.sqrt(expected)   # signed Pearson residual = strength of deviation
```

`chi2_contingency` is used **only for its `expected` table** (the independence model
`row_total × col_total / N`). Take the expected counts; discard the χ² statistic and its p-value —
see Failure Mode 6.

**Run it at the finest granularity you trust** (SubCellType, never broad lineage). The signal lives in
the states, not the lineage: SPP1⁺ and FOLR2⁺ macrophages can move in opposite directions and cancel
out once pooled as "Macrophage". TME atlases name tumor-enriched populations `Lineage_StateGene`
(`Mph_SPP1`, `Fibro_FAP`, `Endo_COL4A1`, `CD8_Tex_LAYN`) for exactly this reason.

**Do not "normalize for sampling depth" by hand.** A per-tissue proportion fold-change
`(n_ij / n_·j) / (n_i· / N)` is *algebraically identical* to `obs / expected` — Ro/e already **is** the
depth-normalized quantity. Writing it a second way adds a step, not robustness.

Rare types: `expected < 5` is where the ratio turns unstable (3 expected, 6 observed reads as
Ro/e = 2.0 on almost nothing). Flag them rather than ranking them:

```python
unstable = (expected < 5)     # report alongside roe; don't headline a type flagged here
```

The tumor-specific triple filter (`roe["Tumor"] > 1` & `roe["Normal"] < 1` & `roe["Blood"] < 1`) is a
convention for *shortlisting* candidates, not a test — a type passing it has not been shown to be
significantly tumor-restricted.

## Failure Modes

1. **Too few samples.** *Symptom:* nothing is credible, or scCODA's automatic reference flips
   between runs. *Diagnosis:* compositional tests replicate over **samples**; 100k cells from 2
   donors is n=2. *Fix:* need ≥3 samples/condition; below that, report the comparison as
   underpowered and abstain — do not fall back to a per-cell test, which manufactures significance.

2. **Reference cell type drives the result.** *Symptom:* conclusions change when the reference
   changes. *Diagnosis:* every scCODA effect is *relative* to the reference; if the reference itself
   moved, everything else appears to move the other way. *Fix:* test 2–3 references, report the
   sensitivity, and prefer a type with a real biological reason to be stable.

3. **Clusters used instead of annotated types.** *Symptom:* several fine-grained clusters of the
   same cell type split the signal and none is credible. *Diagnosis:* over-clustering fragments one
   population across categories. *Fix:* annotate first (`annotation.md`), or use Milo, which does
   not need a discretisation.

4. **`da_nhoods` fails to import rpy2 / R.** *Symptom:* `ImportError` or an rpy2/R error inside
   `da_nhoods`. *Diagnosis:* Milo's model is edgeR, called through rpy2 — the base pertpy install
   has neither. *Fix:* provision an env with the `pertpy[milo-edger]` spec **and** R + edgeR in it (§A/§B
   of `AOSE_nonStandard_env.md` — Milo's R dependency is a classic §B case);
   if R isn't available, use scCODA instead rather than hand-rolling a proportion test.

5. **Absolute counts compared instead of proportions.** *Symptom:* every type "increases" in the
   condition with more cells sequenced. *Diagnosis:* cell counts reflect loading/recovery depth, not
   biology. *Fix:* both tools model this correctly — feed them counts per sample and let them handle
   the normalization; never compare raw counts across samples yourself.

6. **A p-value attached to Ro/e.** *Symptom:* "cell type X is significantly enriched in tumor,
   χ² p < 1e-10". *Diagnosis:* a χ² test over a cell-type × tissue table treats every **cell** as an
   independent observation — at 100k cells everything deviates from independence, and if each tissue
   came from one patient the test is measuring that patient, not the tissue. It is the per-cell test
   this doc rejects, wearing a different hat. *Fix:* report Ro/e as description (ratio + signed
   residual, no p); if the claim needs inference, run §1/§2 over samples.

## Figure checkpoints

- **Stacked barplot of proportions per sample** (`sccoda.plot_stacked_barplot`) — do replicates
  within a condition look alike? Wild within-condition spread means the test will (correctly) find
  nothing; investigate that first.
- **scCODA effects barplot** — is the credible type's direction consistent with the barplot above?
- **Milo beeswarm** (`milo.plot_da_beeswarm`) — do shifted neighbourhoods cluster within one
  annotated type, or scatter across many? Scattered = the annotation and the shift disagree.
- **Ro/e heatmap** (cell type × tissue) — is the pattern driven by a handful of fine types with tiny
  expected counts? Overlay or mask the `expected < 5` cells before showing it.

Observe each before it backs a claim.

## Grounding

Build the `report` **from the returned objects** (do not hardcode), then `print(report)`:

```python
report = {
    "method": "sccoda",
    "pertpy_version": pt.__version__,
    "formula": "condition",
    "reference_cell_type": mdata["coda"].uns["scCODA_params"]["reference_cell_type"],
    "n_samples_per_condition": adata.obs.drop_duplicates("sample_id")["condition"]
                                    .value_counts().to_dict(),
    "n_cell_types": int(adata.obs["cell_type"].nunique()),
    "credible": credible[credible].index.tolist(),
    "est_fdr": 0.05,
}
report
```

Record the **reference cell type**, the **number of samples per condition**, the design formula, and
the FDR — a credible effect is meaningless without them.

## Honesty

- **Compositional effects are relative.** "Type A expanded" always means *relative to the reference
  type*. Name the reference; never present scCODA output as an absolute abundance change.
- **Credible ≠ significant.** scCODA reports credible intervals under a Bayesian model, not
  frequentist p-values. Say "credible under scCODA at FDR x", not "p < 0.05".
- **Samples are the replicates.** State the number of samples per condition next to any claim; a
  compositional result from 2 donors is anecdote regardless of cell count.
- **Milo's unit is a neighbourhood.** "12 neighbourhoods annotated as CD8 T shifted" is not "CD8 T
  cells expanded" — the shift may involve a subset of that type.
- **Ro/e describes, it does not test.** "Mph_SPP1 has Ro/e 2.3 in tumor" is a description of this
  dataset's composition. It is not evidence that SPP1⁺ macrophages are enriched in tumors as a class —
  that claim needs §1/§2 over biological replicates. Never write "significantly" next to a Ro/e.
- **Abundance and expression are different questions.** A credible compositional shift says nothing
  about which genes changed (`markers_de.md`), and vice versa.
- **Validate orthogonally when the claim matters.** FACS, IF, or a held-out cohort — computational
  abundance shifts are hypotheses about the tissue, filtered through dissociation and sorting bias.
