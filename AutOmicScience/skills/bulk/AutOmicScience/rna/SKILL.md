---
name: bulk-rna
disable-model-invocation: true
---

# Bulk RNA-seq Analysis

> Subskill of `bulk`. Enter here from the parent skill when the data is a bulk (or pseudobulk) gene-count matrix with sample metadata. Read the parent (`../SKILL.md`) and the always-loaded `omics-shared` skill first — their evidence/grounding rules apply.

**Reuse existing
`omics_compute` subcommands wherever they apply** — dataset load/summary (`load_dataset`, `summarize`),
gene-set **enrichment** (`enrichment --method ora`), and **pathway/TF activity** (`pathway_activity`,
decoupler) all run through the tool and are grounded automatically.
Those subcommands take an h5ad, so `load_dataset` your count matrix (samples × genes) into AnnData first.

**Pass `modality="scrna"`.** There is no `bulk` modality — `modality` is an *execution-layer environment
selector* (`scrna`→`task1`), not a claim about your data, and `task1` is where the bulk stack (pydeseq2,
decoupler, scipy, statsmodels) lives. `omics_preflight(modality="scrna")` **checks** the env (it is
read-only); `omics_install_env(environment="task1")` **provisions** it.

The count-model steps that have **no** subcommand — normalization, DESeq2/edgeR/limma DE, WGCNA — are
**REFERENCE**: hand-write them in a Python script you run — e.g. via `bash` (`python - <<'PY' … PY` /
`Rscript -e '…'`) — and emit a trailing JSON `report` for grounding, then cite the numbers.

Bulk RNA-seq is **counts-first tabular** analysis (a gene × sample count matrix + a sample metadata table),
not AnnData/scanpy. Use a count-based statistical model — this is the standard of the field (see the DESeq2
/ edgeR / limma-voom vignettes). The conventions below are ordinary bulk RNA-seq best practice.

## Prerequisites

1. A **raw integer count** matrix (genes × samples) — do not start DE from TPM/FPKM/normalized values.
2. A **sample metadata** table aligning each column to its condition + covariates (batch, sex, age, RIN, …).
3. **What is actually in `task1`** (verified): **Python** `pydeseq2` 0.5.4, `decoupler` 2.1.6,
   `statsmodels`, `pandas`, `scipy`, `numpy`. That is enough for the whole default path — count-model DE,
   VST, pseudobulk, ORA, and pre-ranked GSEA.
4. **What is NOT installed, in any environment** — `gseapy`, and the entire R stack (`DESeq2`, `edgeR`,
   `limma`, `WGCNA`, `apeglm`, `rpy2`). `r-env` ships `r-base` + `r-essentials` only. `omics_install_env`
   only materializes envs already declared in `pixi.toml`/`pixi.lock`, so it cannot add them — but that is
   **not** a dead end: these are **PARTIAL** methods, and you provision them into their **own** environment
   per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md` (§A a new Pixi env with an isolated
   `solve-group`; §B a **named** conda env if the solve fails). Never bare-`pip install` (it can land in
   `base`), never add pins to `task1–4`, and record the env + versions in the report.
   **Check first whether you need them at all**: the Python path covers DE, VST, pseudobulk, ORA, and
   pre-ranked GSEA with zero provisioning. Only WGCNA has no Python equivalent here. Do **not** silently
   downgrade to a t-test on log-CPM.

## Capability menu (read the method doc first)

| Capability | Maturity | How | Method doc |
|---|---|---|---|
| Load any-format matrix → h5ad; dataset summary/context | **READY** | `omics_compute load_dataset` / `summarize` (`modality="scrna"`) | `../../../omics-shared/AutOmicScience/assets/references/data_context.md` |
| Gene-set **enrichment** — ORA vs a collection (e.g. Hallmark) | **READY** | `omics_compute enrichment --method ora` (`modality="scrna"`) | `assets/references/enrichment.md` |
| Pathway / TF activity per sample (decoupler; progeny / msigdb / collectri) | **READY** | `omics_compute pathway_activity` (`modality="scrna"`) | `assets/references/enrichment.md` |
| Gene-set **enrichment** — pre-ranked GSEA | **REFERENCE** | hand-rolled `decoupler` `dc.mt.gsea` — **runs on `task1`**, no new dependency (the `enrichment` subcommand takes a gene list, not ranked scores, so it is ORA-only) | `assets/references/enrichment.md` |
| Count normalization + low-expression filtering (VST; filterByExpr-style) | **REFERENCE** | Python (`pydeseq2.vst`) — **runs on `task1`**; `rlog`/TMM need R (absent) | `assets/references/normalization.md` |
| Differential expression + covariate design + **LFC shrinkage** + FDR | **REFERENCE** | Python (`pyDESeq2`) — **runs on `task1`**; DESeq2/edgeR/limma-voom in R are **PARTIAL** (absent) | `assets/references/de.md` |
| Pseudobulk DE (sum raw counts per sample/donor → count-based DE) | **REFERENCE** | Python — **runs on `task1`** | `assets/references/de.md` |
| Co-expression networks (**WGCNA**: soft-power, signed TOM, module eigengenes, module–trait) | **PARTIAL** | `Rscript` (WGCNA) — **not installed**; verified against source, not executed | `assets/references/coexpression.md` |

**READY** = call the grounded `omics_compute` subcommand — a deterministic, standardized step where a tested
function beats re-writing boilerplate. **REFERENCE** = the DE-model design, contrasts, normalization choice,
and network parameters are **study-specific judgment calls**, so read the method doc and **write code adapted
to this dataset** — these are deliberately *not* canned functions; the library is present, you write the
script that calls it. **PARTIAL** = the library is **not in any environment here** — install it into a side
env or report it as a blocker. Always read the method doc first (it carries the judgment: ranking metric,
collection, thresholds, interpretation) even when a subcommand exists.

**The whole default path is READY or REFERENCE** — it runs on `task1` today. Only the R-based alternatives
(DESeq2/edgeR/limma) and WGCNA are PARTIAL, and only WGCNA has no Python substitute here.

## Standard workflow

1. **Load & align** — read the count matrix + metadata; confirm samples align (same order/ids); drop
   feature-summary rows (e.g. HTSeq `__no_feature`); confirm counts are **raw integers**. Summarize dims +
   group sizes and thread them forward (`../../../omics-shared/AutOmicScience/assets/references/data_context.md`).
2. **Filter & normalize** — low-expression filter (`filterByExpr`-style) → the *right* normalization for
   the goal: **VST/rlog** for clustering/PCA/heatmaps; **size-factors / TMM+logCPM** as the model input for
   DE. Do not z-score raw counts, and do not feed log-CPM to a t-test as the primary DE. (`assets/references/normalization.md`)
3. **Differential expression** — a count-based model (DESeq2/pyDESeq2/edgeR/limma-voom) with a **design
   matrix that includes the relevant covariates**; apply **LFC shrinkage** (apeglm/ashr); BH-FDR; when the
   question is "which genes change most", rank by **shrunken |log2FC| (effect size)** with an FDR gate.
   For single-cell-derived data, **pseudobulk** = sum raw counts per donor first. (`assets/references/de.md`)
4. **Enrichment** — **pre-ranked GSEA** (rank by log2FC or shrunken LFC) against **MSigDB Hallmark (H)**,
   report NES + adjusted-p; or **ORA** (Fisher/hypergeometric) with an explicitly-stated background universe
   + BH-FDR. (`assets/references/enrichment.md`)
5. **Networks (if asked)** — WGCNA on VST/TMM-logCPM data: justified soft-power, signed adjacency, TOM,
   module eigengenes, module–trait association. **WGCNA is not installed here** — say so rather than
   substituting the within-set correlation shortcut, which finds no modules.
   (`assets/references/coexpression.md`)
6. **Ground** — cite exact numbers (log2FC, padj, NES, module sizes) from the emitted report; inspect
   any volcano/MA/heatmap before it backs a claim.

## Bulk-RNA best practice (on top of omics-shared)

- **Use a count-based DE model.** DESeq2/edgeR/limma-voom (negative-binomial / voom variance modeling) are
  the field standard. A Welch t-test or OLS on log-CPM is statistically weaker (it ignores the count
  mean–variance relationship); use a count model when one can run, and note it if you cannot.
- **Shrink the fold changes** (apeglm/ashr) before ranking or GSEA; unshrunk LFC over-weights low-count genes.
- **Rank by effect size when asked "which change most"** — sort by shrunken |log2FC| (with an FDR gate),
  not by adjusted p; effect size and significance are separate axes, so report both.
- **Model the covariates in the design** — batch/sex/age/RIN/library-prep/site/genotype-PCs when present;
  an unmodeled confound is the most common silent error.
- **Pseudobulk before DE** for single-cell data: sum **raw** counts per (donor × group), then run a
  count-based model on the pseudobulk matrix — not a per-cell test.
- **State your conventions** — normalization, shrinkage estimator, ranking metric, FDR method, background
  universe. A result is only interpretable and reproducible alongside its method.
- **GSEA ranks by log2FoldChange** (or shrunken LFC), and use the **Hallmark (H)** collection when Hallmark
  pathways are requested.
- **ORA background = the tested universe** (whole genome, or all expressed/background genes) — state which;
  the wrong universe shifts every p-value.

## When things go wrong

- **`KeyError` on `lfc_shrink(coeff=...)`** → an R-DESeq2 coefficient name was passed to pydeseq2. Its
  columns are formulaic-style (`condition[T.treated]`); read the name off `dds.varm["LFC"].columns`.
- **`AttributeError: 'NoneType' has no attribute 'log2FoldChange'`** → `res = st.summary()`. `summary()`
  returns `None` and populates `st.results_df`; call it, then read the attribute.
- **All genes significant / p-values look uniform** → normalized values were fed to a count model, or the
  design is missing covariates; re-check the input is raw counts + the model formula.
- **Volcano one-sided / FC orientation wrong** → verify the contrast direction (which level is numerator):
  DESeq2 `contrast=(factor, test, ref)` → positive = up in `test`.
- **Infinite / NA log2FC** → a group has zero counts; report it explicitly (name the gene) rather than
  dropping it silently.
- **GSEA returns nothing / all NES ≈ 0** → ranking metric or gene-id namespace mismatch (symbol vs Ensembl);
  align ids to the gene-set namespace first.
- **WGCNA collapses to one giant module** → soft-power too low or unsigned network; re-pick power via
  `pickSoftThreshold` scale-free fit, use a signed TOM.

## Provenance

Every recipe here is standard bulk RNA-seq methodology traceable to external field authorities (DESeq2 /
edgeR / limma vignettes, the GSEA/MSigDB and WGCNA papers) — see the `## Sources` block in each method doc.

