# Pathway enrichment — pre-ranked GSEA & over-representation (ORA)

**Maturity: mixed.** ORA and per-sample pathway activity are **READY** (`omics_compute` subcommands — pass
`modality="scrna"`, the environment selector for `task1`; it is not a claim about your data). Pre-ranked
GSEA is **REFERENCE** and **runs on the pinned stack** via `decoupler` 2.1.6, which is in `task1`. API
verified against decoupler 2.1.6 (executed).

Two distinct methods for two distinct questions. Do not mix them up.

**Standard path — reuse the grounded subcommands** (deterministic, auto-recorded evidence):
`omics_compute(subcommand="enrichment", modality="scrna", args={"gene-list": "CD3D,CD3E,GZMB,...", "method": "ora", "resource": "msigdb"})` (ORA over a comma-separated gene set) and
`omics_compute(subcommand="pathway_activity", modality="scrna", args={"adata": "processed.h5ad", "resource": "msigdb"|"progeny"|"collectri", "method": "ulm"|"mlm"|"gsea"})` (per-cell activity over an expression matrix).
For `pathway_activity`, load the expression matrix into an h5ad first (`omics_compute load_dataset`); `enrichment` takes the comma-separated gene list directly. Use these for the
standard run. Drop to the **hand-rolled recipes below** only when you need control the subcommand doesn't
expose — a custom ranking metric, a specific `.gmt`, a defined ORA background universe, or per-instance output.
Either way, the judgment (what to rank by, which collection, thresholds, interpretation) is yours to make.

- **GSEA (pre-ranked)** — uses the *whole ranked gene list* (every gene, ranked by a continuous statistic);
  asks whether a gene set is concentrated at the top/bottom. Use when you have a full DE result.
- **ORA (over-representation)** — uses a *thresholded gene set* (e.g. the significant DE genes); asks
  whether that set overlaps a pathway more than chance (Fisher's exact / hypergeometric).

## Pre-ranked GSEA (decoupler — runs on `task1`)

Rank by **log2FoldChange** (or shrunken LFC); score against MSigDB **Hallmark (H)**. `decoupler` is already
the package this skill uses for `pathway_activity`, and it ships GSEA — so pre-ranked GSEA needs **no new
dependency**.

```python
import pandas as pd, json, decoupler as dc

res = pd.read_csv("de_results.csv", index_col=0)                 # from de.md (shrunken LFCs)
hallmark = dc.op.hallmark(organism="human")                      # 50 sets; columns: source, target

# decoupler scores one row = one observation. A single-row frame of the DE statistic IS the pre-ranked
# list — no sorting needed; GSEA ranks internally.
rnk = res["log2FoldChange"].dropna().to_frame().T
rnk.index = ["treated_vs_control"]                               # name the contrast; it labels the output

nes, padj = dc.mt.gsea(data=rnk, net=hallmark, tmin=15)          # returns a TUPLE: (scores, p-values)
out = pd.DataFrame({"NES": nes.iloc[0], "padj": padj.iloc[0]})
sig = out[out.padj < 0.05]
print(json.dumps({
    "n_sets_tested": int(len(out)),
    "activated":  sig[sig.NES > 0].sort_values("NES", ascending=False).head(10).index.tolist(),
    "suppressed": sig[sig.NES < 0].sort_values("NES").head(10).index.tolist(),
}))
```

Three things about `dc.mt.gsea`'s contract, each verified in source rather than assumed:

- **It returns a 2-tuple, not a DataFrame** — `(scores, p-values)`, one row per input observation.
- **The score is NES, not raw ES** — but only because `times` (permutations) defaults to **1000**; the
  implementation returns raw ES when `times <= 1`. Leave `times` alone, or you silently change what the
  first return value means.
- **The p-values are already BH-adjusted** across gene sets (decoupler applies FDR internally for `gsea`).
  Do **not** BH them a second time; treat the second return value as `padj`.

`tmin=15` sets the minimum set size (decoupler's default is 5, which is small for Hallmark). There is no
`tmax` — if you need an upper size bound, filter `hallmark` before passing it.

**`dc.op.hallmark()` fetches over the network** (OmniPath), like `sq.gr.ligrec`'s resource. It is versioned
by fetch date, not by a pin — record when you fetched it, or pass your own `.gmt`-derived
`source`/`target` frame for a reproducible run.

Report **NES + padj**; a set is "suppressed/down" when NES < 0 at padj < 0.05. Ranking metric matters:
log2FC (effect direction/size) is the common default; a signed-statistic or t-statistic ranking answers a
slightly different question — pick and state one.

> **`gseapy` is not installed here, and the recipe above does not need it.** Reach for it only if you
> specifically need Subramanian/fgsea parity (e.g. reproducing a paper's exact `prerank` output). It is a
> **PARTIAL** method: provision it into its own env per `omics-shared`'s
> `assets/references/AOSE_nonStandard_env.md` (§A — that doc names `gseapy` as an example), never a bare
> `pip install`. Note the numbers are **not interchangeable** with decoupler's: the two implement the same
> idea with different normalization and permutation schemes, so report which one produced the NES.

## ORA — Fisher's exact / hypergeometric

Requires an explicitly-defined **background universe** (M). The universe is the set of genes that *could*
have been tested — usually all genes in the annotation, or all expressed/background genes in your matrix.
State it; the wrong universe shifts every p-value.

```python
from scipy.stats import hypergeom
import pandas as pd
sig_genes = set(pd.read_csv("sig_genes.txt", header=None)[0])     # your thresholded DE set
universe  = set(background_genes)                                  # M — state how you defined it
for term, pathway in gene_sets.items():                           # {term: set(genes)}
    P = set(pathway) & universe
    k = len(sig_genes & P)                                         # overlap
    # P(X >= k) under hypergeometric(M=|universe|, n=|P|, N=|sig_genes ∩ universe|)
    p = hypergeom.sf(k-1, len(universe), len(P), len(sig_genes & universe))
# → collect p per term, apply Benjamini-Hochberg FDR across terms, report overlap counts + padj
```
Always report the **overlap counts** (e.g. 37/200), the p-value, and the BH-FDR.

Two shortcuts, and they are **not** the same thing:
- **`omics_compute enrichment --method ora`** (READY) — the grounded path; use it unless you need a
  universe or collection it doesn't expose. That is what the hand-rolled version above is for.
- **`gseapy.enrich` / `enrichr`** — *not* equivalent to the hypergeometric above. Given a bare Enrichr
  library name, `enrich` routes to the **Enrichr web API**, not a local test: different universe, network
  round-trip, and results that move when Enrichr updates. Only a dict/`.gmt` gene set takes its offline
  path. gseapy is also not installed here (PARTIAL — see the provisioning note above). If you report
  "ORA", say which of these three produced it.

## Gene-id namespace

Align the gene ids in your ranked list / DE set to the gene-set namespace (HGNC symbol vs Ensembl vs
Entrez) before enrichment, or every pathway will look empty.

## Sources

- Subramanian et al. 2005, *PNAS* 102:15545 — GSEA. · Korotkevich et al. 2021 (fgsea) — fast pre-ranked GSEA.
- Liberzon et al. 2015, *Cell Systems* 1:417 — MSigDB **Hallmark** gene sets.
- `gseapy` docs (Fang et al. 2023, *Bioinformatics*). · Yu et al. 2012, *OMICS* — clusterProfiler (ORA/GSEA).
- Hypergeometric/Fisher ORA: standard; e.g. Boyle et al. 2004, *Bioinformatics* (GO::TermFinder).
