---
name: single-cell-atac
disable-model-invocation: true
---

# scATAC-seq Analysis

> Subskill of `single-cell`. Enter here from the parent skill when the data is single-cell ATAC-seq (chromatin accessibility). Read the parent (`../SKILL.md`) and the always-loaded `omics-shared` skill first — their shared workflow, `omics_compute` conventions, and evidence rules apply here.

Run compute through the **`omics_compute`** tool with `modality="scatac"`; it dispatches into the pinned `task4` env and records evidence automatically. Steps without a subcommand are hand-rolled in a Python script with **snapATAC2** (and **pychromVAR** for motifs) — read the method doc first.

## Prerequisites

1. `omics_preflight(modality="scatac")` passes (validates `task4`'s scatac imports). Add
   `for-subcommand` (and `method`) to check that exact request — e.g.
   `omics_preflight(modality="scatac", args={"for-subcommand":"peak_calling"})` also verifies the
   **MACS3 package**, which snapATAC2 drives as a library and a modality-only check cannot see.
2. A fragments file (`fragments.tsv.gz`) — needed **only at import** (step 1), not by the
   subcommands. Every scatac subcommand then takes that import product: the insertions ride in
   `obsm`, so a plain feature matrix is rejected. `atac_qc` additionally needs the object to carry
   a tile/peak matrix, so run `pp.add_tile_matrix` before it.
3. A **GTF/GFF** — required for TSSE (`atac_qc --gtf-file`), gene activity, and peak-gene linkage.
4. A `summarize` report + free-text study description threaded into every biological decision.

## Capability menu (with maturity)

| Capability | Maturity | How | Method doc |
|------------|----------|-----|------------|
| Import fragments → cell×feature matrix | **REFERENCE** | snapATAC2 `pp.import_fragments` | `assets/references/import_fragments.md` |
| ATAC QC (TSSe, fragment size / nucleosome signal, FRiP) | **READY** | `omics_compute atac_qc` | `assets/references/atac_qc.md` |
| Doublet removal | **REFERENCE** | snapATAC2 `pp.scrublet` / `pp.filter_doublets` | `assets/references/atac_qc.md` |
| Feature matrix (tiles / peaks) | **PARTIAL** | snapATAC2 tiles; peaks via `peak_calling` | `assets/references/feature_matrix.md` |
| Peak calling (MACS3, per-cluster) | **READY** | `omics_compute peak_calling` | `assets/references/peak_calling.md` |
| Spectral (LSI) embedding + Leiden | **REFERENCE** | snapATAC2 `tl.spectral` / `tl.leiden` | `assets/references/dimred_cluster.md` |
| Motif activity (chromVAR) | **REFERENCE** | pychromVAR | `assets/references/motif_enrichment.md` |
| Gene activity scores (snapATAC2 `make_gene_matrix`, needs a GTF) | **READY** | `omics_compute gene_activity --gtf-file` | `assets/references/gene_activity.md` |
| Peak–gene linkage (CRE→gene network) | **REFERENCE** | snapATAC2 `tl.init_network_from_annotation` + `tl.add_cor_scores` | `assets/references/peak_gene_linkage.md` |
| Label transfer / integration from scRNA | **REFERENCE** | gene-activity bridge + scRNA recipes | `assets/references/rna_integration.md` |

Read the method doc before running a capability — each gives the opinionated default, exact parameters, failure modes, and grounding.

> **GRN inference is not a pure-scATAC step.** It needs expression: for TF regulons use **scRNA** (`rna`, pySCENIC); for enhancer-driven GRN use the **multiome** subskill (SCENIC+). Do not infer a GRN from accessibility alone.

## Standard workflow

Run each step through `omics_compute` where a subcommand exists; otherwise hand-roll per the method doc. Read the per-step doc for parameters and decisions.

1. **Preflight & import** — `omics_preflight(modality="scatac")`; import the fragments file into a snapATAC2 AnnData, then **add a tile matrix** (`pp.add_tile_matrix`) so the object has features (`assets/references/import_fragments.md`); `omics_compute(subcommand="summarize", modality="scatac", args={"input":"tiles.h5ad"})`. Thread the summary + study description forward.
2. **ATAC QC** — `omics_compute(subcommand="atac_qc", modality="scatac", args={"adata":"tiles.h5ad","output":"qc.h5ad","gtf-file":"genes.gtf","compute-tsse":"true","compute-fragment-size":"true","compute-frip":"true","filter":"true"})`. No `fragment-file`: the insertions travel inside `tiles.h5ad` from step 1. `gtf-file` is **required** for TSSE; FRiP takes its regions from `var_names` (or `peak-bed`). See `assets/references/atac_qc.md` for TSSE / nucleosome / FRiP thresholds and the MAD-vs-fixed decision.
3. **Feature matrix** — tile matrix for a first pass, or call peaks per cluster: `omics_compute(subcommand="peak_calling", modality="scatac", args={"adata":"qc.h5ad","output":"peaks.bed","mode":"pseudobulk","cluster-column":"leiden"})` (`assets/references/feature_matrix.md`, `assets/references/peak_calling.md`).
4. **Embed & cluster** — snapATAC2 spectral (LSI) embedding, then Leiden on `obsm["X_spectral"]`; drop the depth-correlated first component (`assets/references/dimred_cluster.md`). Plot UMAP and inspect the figure.
5. **Gene activity** — `omics_compute(subcommand="gene_activity", modality="scatac", args={"adata":"qc.h5ad","output":"gene_activity.h5ad","gtf-file":"genes.gtf"})` for an expression proxy used in annotation / integration. `gtf-file` is **required** (there is no built-in annotation). The score is SnapATAC2's `make_gene_matrix` — TN5 insertions per gene regulatory domain (`assets/references/gene_activity.md`).
6. **Motif activity (chromVAR)** — per-cell TF motif deviations via pychromVAR (`assets/references/motif_enrichment.md`).
7. **Linkage / integration (as needed)** — peak–gene links from the peak matrix + gene-activity matrix (`assets/references/peak_gene_linkage.md`); label transfer from an scRNA reference via the gene-activity bridge (`assets/references/rna_integration.md`).
8. **Visualize & ground** — plot UMAP colored by clusters / QC / gene-activity markers; inspect each before it backs a claim; cite the `omics_compute` reports as evidence.

## scATAC-specific rules (on top of omics-shared)

- **TSS enrichment is the primary QC axis** — always compute + report TSSE (the insertions are always in the object) and gate filtering on it (`assets/references/atac_qc.md`).
- **Spectral (LSI), not PCA** — ATAC is sparse / near-binary; use snapATAC2 spectral embedding and drop the depth-correlated first component (`assets/references/dimred_cluster.md`).
- **Accessibility ≠ expression** — gene activity is a proxy; validate it against markers and say so; never report it as measured expression.
- **Distance ≠ regulation** — a peak near a gene is a hypothesis, not a regulatory link; ground linkage claims and abstain when correlation is weak (`assets/references/peak_gene_linkage.md`).
- **Abstain over guess** — an ambiguous cluster is "unknown", not an invented label.

## When things go wrong

- **TSSE low across all cells** — library quality or wrong genome annotation; check the fragments file + genome build before filtering (`assets/references/atac_qc.md`).
- **Clusters track total counts / TSSE** — technical variation dominates; revisit feature selection or drop the first spectral component (`assets/references/dimred_cluster.md`).
- **Too few peaks after calling** — pseudobulk per cluster has too few cells, or the q-value is too strict; aggregate more cells or relax (`assets/references/peak_calling.md`).
- **Gene activity is noisy** — expected for a proxy; smooth over neighbors or restrict to confident peak–gene links; do not over-interpret single genes.
