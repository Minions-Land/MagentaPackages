# Evidence Grounding

Grounding = every quantitative or biological claim in a conclusion traces to something you actually
computed or to a named source — never to memory or to a pre-existing label copied forward. This is
the most load-bearing habit for a research agent, and it maps directly onto how an expert reviewer
reads an analysis (traceable numbers, real identifiers, stated limitations).

## The rule

- **Numbers come from computation.** Any count, proportion, p-value, metric, threshold, or effect
  size in a conclusion must come from code you ran in this analysis. If you can't point at the
  computation that produced a number, don't state it.
- **Identifiers come from named sources.** Gene / protein / sample / pathway names come from the
  dataset itself or a named database (HGNC, UniProt, MSigDB, KEGG, Ensembl) — not from recall.
- **Method names match what ran.** Say "Wilcoxon rank-sum (scanpy `rank_genes_groups`)" only if that
  is what you called; don't describe a method you didn't run.
- **Interpretations cite real references.** Biological/clinical claims get an identifiable citation
  (author + year, DOI/PMID, or a named DB), not "the literature shows".

## Make each number inspectable

When a step does real work (filter, aggregation, join, test, transformation), print its inputs and
outputs so the result is reproducible from the trace:

```python
print(f"cells: {adata.n_obs} -> {adata_qc.n_obs} after QC (min_genes=200, max_pct_mt=15)")
report = {"n_clusters": int(adata.obs["leiden"].nunique()), "resolution": 1.0, "n_cells": int(adata.n_obs)}
print(report)   # a trailing dict makes the step's numbers + parameters explicit
```

`omics_compute` subcommands already return a `report` dict — cite its fields. For hand-written
(`REFERENCE`) methods, emit the same kind of report yourself.

## Inspect figures before trusting them

A figure only backs a claim after you've looked at it. Before citing a plot, check for: **artifacts**
(stripes, all-one-color), **wrong scale** (saturated/empty colorbar), **empty or mislabeled axes**,
and **unexpected structure** (one giant blob where you expected clusters; clusters that track a QC
metric rather than biology). If it looks wrong, fix the upstream step and re-plot before reporting.

## Pitfalls

- **Silent numbers.** "Found 12 clusters" with no code/report behind it — show the computation and
  its parameters (resolution, thresholds).
- **Forgetting parameters.** A result without its method variant + input/output shapes isn't
  reproducible — state them next to the number.
- **Copying instead of computing (anti-circular).** If `obs["cell_type"]` already exists, that is
  *prior annotation*: compare against it (ARI/NMI), never repeat it as your own finding.
- **Ignoring transformations.** If you subset/filter/rescale before a claim, report on the same
  object you analyzed and say what the transformation was — don't quote a fraction from a different
  subset than the one you computed on.
- **Missing dataset context.** Summarize the dataset once after load (dimensions, layers, obs
  columns, study design) and carry that context into every downstream decision.

## Honesty boundaries

- **Data doesn't match the claim** — if the study describes groups no column encodes (e.g. healthy
  vs disease with no such `obs` field), flag the mismatch and list the available columns; don't
  assume a mapping.
- **Can't explain a result** — a cluster with no significant markers is "unknown", not a guessed
  "likely doublets". State what you observe and that the cause is undetermined.
- **Weak evidence** — 2/150 cells positive for a marker is insufficient for an assignment; report the
  fraction and defer rather than overclaim.

## Checklist

- [ ] Every conclusion number traces to a computation in this analysis.
- [ ] Parameters/thresholds/methods are stated next to their results.
- [ ] Dataset shape and context are stated upfront.
- [ ] Transformations are logged (and flagged if the claim is over a subset).
- [ ] Pre-existing labels are treated as prior, not re-reported as findings.
- [ ] Figures were inspected before they backed a claim.
- [ ] Biological interpretations carry checkable citations.
- [ ] Limitations / what the analysis cannot conclude are stated.
