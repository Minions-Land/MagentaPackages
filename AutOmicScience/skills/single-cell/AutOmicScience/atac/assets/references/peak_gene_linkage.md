# Peak-Gene Linkage

**Maturity: REFERENCE** — no compute subcommand, but **snapATAC2 owns the algorithm**: build a
CRE→gene network from the annotation, then score its edges. You write the calls; you do not
implement the linkage. `snapatac2` is pinned in `task4` — nothing to install. The **scATAC-only**
path (gene activity as the expression stand-in); for paired multiome with real RNA, see the
**multiome** subskill (SCENIC+ region-gene links, `regulation.md`).

## Goal / When to Use

Connect candidate enhancers (peaks) to target genes for regulatory interpretation / GRN scaffolding.
Use after peak calling and gene activity, when you need peak→gene associations.

## Decision Criteria

- **Distance alone** — `init_network_from_annotation` links every peak within `upstream`/`downstream`
  of a gene TSS (default ±250 kb). That is the candidate set, not evidence of regulation. Report
  distance-only links as candidates.
- **Distance + correlation** — `add_cor_scores` adds a **Spearman** score per edge from the peak and
  gene matrices. This is the default scoring step; it needs many cells.
- **Distance + regression** — `add_regr_scores(method="elastic_net" | "gb_tree")` fits a model per
  gene over its candidate peaks instead of scoring each pair independently, so it accounts for peaks
  competing to explain the same gene. Slower; reach for it when the correlation set is too permissive.
- **Restrict the peak set** before building the network (differential/variable peaks). Every peak ×
  every gene in a ±250 kb window is mostly noise and dominates the runtime.

## How-to

The network's inputs are the two matrices our READY subcommands already produce: the peak matrix
(`peak_calling --create-matrix`) and the gene-activity matrix (`gene_activity`).

```python
import snapatac2 as snap
import anndata as ad

peak_mat = ad.read_h5ad("peaks_matrix.h5ad")     # peak_calling --create-matrix
gene_mat = ad.read_h5ad("gene_activity.h5ad")    # gene_activity subcommand

# snapATAC2's correlation is Rust-side and rejects integer matrices — cast first.
peak_mat.X = peak_mat.X.astype("float32")
gene_mat.X = gene_mat.X.astype("float32")

network = snap.tl.init_network_from_annotation(
    regions=list(peak_mat.var_names),
    anno_file="genes.gtf",
    upstream=250_000, downstream=250_000,        # regulatory domain around each TSS
    id_type="gene_name",                         # must match gene_mat.var_names
    coding_gene_only=True,
)
snap.tl.add_cor_scores(network, gene_mat=gene_mat, peak_mat=peak_mat)
```

`network` is a `rustworkx.PyDiGraph`: nodes carry `.id` / `.type` (`"region"` or `"gene"`), edges
carry `.distance` and `.cor_score`. Read the links out:

```python
links = [
    {"peak": network[src].id, "gene": network[dst].id,
     "cor_score": edge.cor_score, "distance": edge.distance}
    for src, dst in network.edge_list()
    for edge in [network.get_edge_data(src, dst)]
    if edge.cor_score is not None
]
```

Keep only the confident edges with `prune_network` (it drops isolated nodes for you):

```python
strong = snap.tl.prune_network(
    network,
    edge_filter=lambda src, dst, edge: edge.cor_score is not None and edge.cor_score > 0.3,
    remove_isolates=True,
)
```

> **`snap.tl.co_accessibility` and `snap.tl.peak_gene_linkage` do not exist.** If you find a recipe
> calling either, it is fabricated — the real API is `init_network_from_annotation` +
> `add_cor_scores` / `add_regr_scores`, as above.

## Failure Modes

1. **`PanicException: Cannot compute correlation for type uint32`.** *Diagnosis:* `add_tile_matrix`
   / `make_peak_matrix` / `make_gene_matrix` all produce integer counts, and the Rust Spearman needs
   floats. *Fix:* cast both `X` to `float32` before scoring (as above). Do not "fix" it by dropping
   the correlation step.

2. **Every edge has `cor_score = None`.** *Diagnosis:* `gene_mat`/`peak_mat` var_names don't match
   the network's node ids — usually `id_type="gene_name"` against a gene matrix built with
   `id_type="gene"`/gene ids, or a chromosome-naming mismatch upstream. *Fix:* print
   `set(gene_mat.var_names) & {n.id for n in network.nodes() if n.type == "gene"}`; if empty, rebuild
   with matching id types.

3. **The network is enormous / scoring never finishes.** *Diagnosis:* every peak within ±250 kb of
   every gene is a candidate; on a genome-wide peak set that is millions of edges. *Fix:* restrict
   `regions` to differential or variable peaks before `init_network_from_annotation`, and/or narrow
   the window.

4. **Correlation is high but the peak is far and biologically implausible.** *Diagnosis:* both the
   peak and the gene track the same cluster structure, so they correlate through cell type, not
   regulation. *Fix:* this is co-variation, not linkage — check whether the correlation survives
   within a cell type, and never present it as a regulatory claim.

## Figure checkpoints

- **Distance vs `cor_score` scatter** — do strong links concentrate near the TSS, or is the score
  flat with distance? A flat profile means you are picking up cell-type covariation (Failure Mode 4).
- **Network diagram / heatmap of top links** for a few known genes — are the implicated peaks
  plausible (promoter + a few enhancers), or does one gene absorb hundreds of peaks?

Observe each before it backs a claim.

## Grounding

Build the `report` **from the network** (do not hardcode), then `print(report)`:

```python
report = {
    "method": "snapatac2.tl.init_network_from_annotation + add_cor_scores",
    "snapatac2_version": snap.__version__,
    "score": "spearman",
    "upstream": 250_000, "downstream": 250_000,
    "id_type": "gene_name", "coding_gene_only": True,
    "n_regions_in": int(peak_mat.n_vars),
    "n_genes_in_network": sum(1 for n in network.nodes() if n.type == "gene"),
    "n_candidate_links": int(network.num_edges()),
    "cor_threshold": 0.3,
    "n_links_kept": int(strong.num_edges()),
    "top_links": sorted(links, key=lambda x: -abs(x["cor_score"]))[:20],
}
```

Record the **window, the id_type, the score type (Spearman), and both link counts** — a link count
means nothing without the window that generated it.

## Honesty

- **Distance is a candidate, not a link.** "Peak X is within 50 kb of gene Y" is a hypothesis;
  "peak X regulates gene Y" needs functional evidence this analysis cannot provide.
- **Correlation here is against gene *activity*, not expression.** In scATAC-only data the gene
  matrix is a proxy built from the same fragments as the peaks, so peak and gene signal are not
  independent measurements. Say so; with paired multiome use real RNA (`regulation.md`).
- **Co-accessibility is not causality.** A correlated pair can reflect co-regulation by a third
  factor or shared cell-type structure (Failure Mode 4).
- **Apply FDR if you threshold on significance.** Thousands of candidate edges are scored; an
  uncorrected cutoff will pass many false positives.
- **Linkage is a scaffold, not a GRN.** It constrains which peaks *could* regulate which genes; it
  says nothing about which TFs are active or the regulatory logic. For a GRN use `link_tf_to_gene`
  with motif binding (`motif_enrichment.md`) or SCENIC+ on multiome.
