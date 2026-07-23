# Co-expression networks (WGCNA) & module coherence

## WGCNA — weighted gene co-expression network analysis (R)

**Maturity: PARTIAL — needs provisioning.** `WGCNA` is **not installed in any environment** here: `r-env`
ships `r-base` + `r-essentials` (no Bioconductor DE stack, no WGCNA), and `omics_install_env` only
materializes envs already declared in `pixi.toml`/`pixi.lock`. Stand up your own R env beside your
analysis outputs per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`:

```toml
# pixi.toml, at your analysis root
[workspace]
name = "wgcna"
channels = ["conda-forge", "bioconda"]
platforms = ["linux-64"]

[dependencies]
r-base = ">=4.3"
r-wgcna = "*"
```
```bash
pixi lock && pixi install --locked
pixi run --frozen Rscript wgcna.R
```

Those two dependencies are the **whole** module-detection pipeline — `r-wgcna` pulls `impute`,
`preprocessCore`, `AnnotationDbi`, `fastcluster`, and `dynamicTreeCut` transitively, so
`pickSoftThreshold → blockwiseModules → moduleEigengenes → module–trait` all run as-is (verified).
**Do not add `bioconductor-go.db`** (or an `org.*.eg.db`) by reflex: `library(WGCNA)` loads and every
function above works without it. GO.db is a Bioconductor **data** package needed *only* if you call
WGCNA's built-in `GOenrichmentAnalysis` — and you rarely should, because module functional annotation
is normally done separately (enrichment against pathway sets, or against marker sets the task provides).
Adding GO.db when nothing calls it just pulls in a data package the analysis never reads.

If that solve fails, drop to a **named** conda env and record the versions, since conda envs are not in
any lock. **There is no Python substitute for WGCNA here:** do not fall back to the coherence shortcut
below, and do not hand-write your own adjacency → TOM → clustering → eigengene pipeline, and then report
either one as WGCNA. Provision the R package and run it; if it genuinely cannot be installed, that is a
blocker to report, not a cue to substitute.

The recipe was **verified against WGCNA 1.74 source (CRAN), not executed** (no R + WGCNA available
here) — signatures and defaults are cited from source; treat runtime behaviour as unconfirmed.

Standard pipeline on **variance-stabilized** expression (VST / TMM-logCPM), genes in columns, samples in rows.

```r
suppressMessages(library(WGCNA))     # NB: WGCNA exports its own cor(), masking stats::cor

datExpr <- t(vst_matrix)                                   # samples x genes (VST/logCPM, filtered)

# 1. Pick soft-threshold power by scale-free topology fit.
#    The default RsquaredCut is 0.85 and the test is a STRICT ">", not ">= 0.8".
#    Signed networks need HIGHER powers than unsigned: signed adjacency is ((1+cor)/2)^power, which floors
#    at 0.5^power for uncorrelated pairs, so the fit needs a bigger exponent. powerVector=1:20 cannot
#    reach past 20; blockwiseModules accepts up to 30.
#    pickSoftThreshold print()s its fit table unconditionally — verbose=0 does NOT silence it, so capture
#    it or the JSON report below is not the only thing on stdout.
invisible(capture.output(
  sft <- pickSoftThreshold(datExpr, powerVector=c(1:10, seq(12, 30, by=2)),
                           networkType="signed", RsquaredCut=0.85, verbose=0)
))
power <- sft$powerEstimate
# powerEstimate is NA when NO power exceeds RsquaredCut. Passing NA into blockwiseModules dies at its
# `if ((power<1) | (power>30))` guard with the opaque "missing value where TRUE/FALSE needed".
if (is.na(power))
  stop("pickSoftThreshold: no power exceeded RsquaredCut. Inspect sft$fitIndices and choose deliberately.")

# 2. Blockwise module detection on a SIGNED network + TOM.
#    maxBlockSize DEFAULTS TO 5000. Above that, genes are pre-clustered into blocks and modules are
#    detected PER BLOCK — two genes in different blocks can never share a module. With verbose=0 this is
#    silent. A typical 15-20k-gene matrix becomes 3-4 blocks whose modules are NOT comparable to a
#    single-block run. Set it explicitly and report it.
net <- blockwiseModules(datExpr, power=power, networkType="signed", TOMType="signed",
                        maxBlockSize=ncol(datExpr),        # single block; needs RAM (~8k genes/4GB)
                        minModuleSize=30, mergeCutHeight=0.25, numericLabels=TRUE, verbose=0)

# 3. Module eigengenes. With numericLabels=TRUE, label 0 is the "grey" UNASSIGNED bin, not a module —
#    and moduleEigengenes keeps it (excludeGrey=FALSE by default), so ME0 would enter the trait table
#    as a bogus module.
MEs <- moduleEigengenes(datExpr, net$colors)$eigengenes
MEs <- MEs[, colnames(MEs) != "ME0", drop=FALSE]

# 4. ALIGN traits to datExpr before correlating. cor() matches by POSITION, not by rownames: a trait
#    table in a different row order silently produces wrong correlations with no error.
trait <- read.csv("trait.csv", row.names=1)                # numeric/ordinal sample traits
stopifnot(all(rownames(datExpr) %in% rownames(trait)))
trait <- trait[rownames(datExpr), , drop=FALSE]
stopifnot(all(vapply(trait, is.numeric, logical(1))))      # WGCNA::cor as.matrix-coerces; a character
                                                           # column fails in C rather than cleanly

# 5. corPvalueStudent(cor, nSamples) assumes every correlation used nSamples observations. That is only
#    true with complete data — "pairwise.complete.obs" would make the per-pair n SMALLER, and passing
#    nrow(datExpr) anyway inflates df and makes p-values too small.
stopifnot(!anyNA(trait), !anyNA(MEs))
mtCor <- cor(MEs, as.matrix(trait), use="all.obs")
mtP   <- corPvalueStudent(mtCor, nrow(datExpr))            # p per (module, trait)

n_modules <- sum(unique(net$colors) != 0)                  # exclude the grey/unassigned label
cat(sprintf('{"power":%d,"n_modules":%d,"n_blocks":%d}\n',
            power, n_modules, length(unique(net$blocks))))
```

Key conventions: **signed** network + **signed TOM** (preserves direction of co-expression); choose the
soft power from the scale-free-fit curve (do not hard-code); summarize each module by its **eigengene**
(1st PC) and relate modules to traits via eigengene–trait correlation with a p-value.

**The four defects above are all silent** — block-splitting, unaligned traits, ME0-as-a-module, and the
0.8-vs-0.85 mismatch each change the reported numbers without raising. Report `power`, `n_modules`
(grey excluded), and `n_blocks` so a reader can tell which regime the run was in.

### Module → cell-type / gene-set enrichment
Test each module's gene membership against marker/annotation gene sets with **Fisher's exact + BH-FDR**
(same math as `enrichment.md` ORA), using the analysed genes as the background universe.

## Lightweight "co-expression coherence" (no full WGCNA) — runs on `task1`

**This is not a WGCNA substitute.** It answers a narrower question — how tightly an *already-defined* gene
set co-varies — and discovers no modules. It needs only pandas/numpy, so unlike the recipe above it runs on
the pinned stack. If the ask was "find co-expression modules", this does not answer it; report WGCNA as a
blocker instead of quietly shipping this.

When the question is how tightly a defined gene set co-varies:

```python
import pandas as pd, numpy as np
# 1. define the set (e.g. top-N genes by |correlation| with a score), 2. within-set pairwise Spearman
sub = expr[gene_set]                                       # samples x genes (log/VST)
r   = sub.corr(method="spearman").values
np.fill_diagonal(r, np.nan)
mean_within = np.nanmean(r)                                # module coherence
per_gene    = pd.Series(np.nanmean(r, axis=1), index=gene_set)   # per-gene mean r
low_coh     = per_gene[per_gene < 0.2].index.tolist()      # weakly-coherent members
```
Report the mean within-set correlation and, if asked, flag low-coherence members by a stated threshold.

## Sources

- Langfelder & Horvath 2008, *BMC Bioinformatics* 9:559 — WGCNA. · Zhang & Horvath 2005, *SAGMB* — weighted
  network / soft-thresholding. · The official WGCNA tutorials (Horvath lab) for the signed-network defaults.
- Module eigengene: Langfelder & Horvath 2007, *BMC Syst Biol* (eigengene networks).
- Langfelder & Horvath, *WGCNA FAQ* (Horvath lab) — the signed-network soft-power recommendation table and
  the `maxBlockSize` / blockwise-vs-single-block caveat. Defaults above (`maxBlockSize=5000`,
  `RsquaredCut=0.85`, `excludeGrey=FALSE`) read from WGCNA **1.74** source.
