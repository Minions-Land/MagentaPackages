#!/usr/bin/env python3
"""Unified CLI entry for AOSE omics runtime — python -m aose_omics_runtime SUBCOMMAND.

This is the single entry point that replaces scattered sys.path.insert(...) +
per-script imports. Every omics capability is exposed as a subcommand (matching
the RuntimeSubcommand enum in aose-omics Rust crate), so the Rust side builds
one typed RuntimeRequest instead of constructing fragile per-script argv.

Subcommands are grouped by modality:
  shared: summarize, preprocess, validate_layout
  scrna: marker_table, integrate
  spatial: read_spatial
  scatac: atac_qc, peak_calling, gene_activity
  multiome: load_multiome
  functional: pathway_activity, enrichment
  benchmark: score
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="aose_omics_runtime",
        description="AOSE omics runtime — unified Python entry for scverse analysis",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # --- shared ---
    sub = subparsers.add_parser("load_dataset", help="Universal loader: ANY format → h5ad")
    sub.add_argument("--path", required=True, help="Input file path")
    sub.add_argument("--output", required=True, help="Output .h5ad path")
    sub.add_argument("--format", default="auto", choices=["auto", "csv", "tsv", "txt", "excel", "h5ad", "h5", "mtx", "loom", "zarr"], help="Input format")
    sub.add_argument("--transpose", action="store_true", help="Transpose matrix (genes as rows → cells as rows)")
    sub.add_argument("--obs-names-col", type=int, default=0, help="Column for cell names (0-based)")
    sub.add_argument("--var-names-col", type=int, default=None, help="Column for gene names")
    sub.add_argument("--header", type=int, default=0, help="Row index for header")
    sub.add_argument("--sep", type=str, default=None, help="Column separator (auto-detected)")

    sub = subparsers.add_parser("summarize", help="Dataset summary")
    sub.add_argument("--input", required=True, help="Path to h5ad/h5mu")
    sub.add_argument("--output", help="Output text file (default: stdout)")

    sub = subparsers.add_parser("preprocess", help="Standard QC→PCA→UMAP→Leiden")
    sub.add_argument("--input", required=True)
    sub.add_argument("--output", required=True)
    sub.add_argument("--modality", default="scrna", choices=["scrna", "spatial", "scatac", "multiome"])

    sub = subparsers.add_parser("validate_layout", help="Validate keys vs conventions")
    sub.add_argument("--input", required=True)

    # --- scrna ---
    sub = subparsers.add_parser("marker_table", help="Per-cluster marker genes")
    sub.add_argument("--input", required=True)
    sub.add_argument("--output", required=True)
    sub.add_argument("--groupby", default="leiden")
    sub.add_argument("--min-logfc", type=float, default=0.5)
    sub.add_argument("--min-pct", type=float, default=0.1)

    sub = subparsers.add_parser("integrate", help="Batch integration")
    sub.add_argument("--input", required=True)
    sub.add_argument("--output", required=True)
    sub.add_argument("--batch-key", default="batch")
    sub.add_argument("--method", default="harmony", choices=["harmony", "scanorama"])

    # --- spatial ---
    sub = subparsers.add_parser("read_spatial", help="Read platform-specific spatial")
    sub.add_argument("--input", required=True)
    sub.add_argument("--output", required=True)
    sub.add_argument("--platform", required=True, choices=["visium", "xenium", "merfish"])
    # Generic per-cell CSV options (platform=merfish): override for the actual
    # layout, e.g. Vizgen MERSCOPE cell_by_gene.csv / EntityID / center_x / center_y.
    sub.add_argument("--counts-file", default="counts.csv", help="Counts CSV name (merfish)")
    sub.add_argument("--metadata-file", default="cell_metadata.csv", help="Metadata CSV name (merfish)")
    sub.add_argument("--x-col", default="x", help="Metadata x column (merfish)")
    sub.add_argument("--y-col", default="y", help="Metadata y column (merfish)")
    sub.add_argument("--cell-id-col", default="cell_id", help="Metadata cell-id column (merfish)")
    sub.add_argument("--delimiter", default=",", help="CSV delimiter (merfish)")

    # --- scatac ---
    sub = subparsers.add_parser("atac_qc", help="ATAC QC metrics (snapATAC2)")
    sub.add_argument("--adata", required=True,
                     help="Input h5ad from snapatac2.pp.import_fragments (fragments in obsm)")
    sub.add_argument("--output", required=True, help="Output h5ad file with QC metrics")
    sub.add_argument("--gtf-file", help="GTF/GFF annotation (required with --compute-tsse)")
    sub.add_argument("--compute-tsse", action="store_true", help="Compute TSS enrichment")
    sub.add_argument("--compute-fragment-size", action="store_true",
                     help="Compute fragment size distribution + per-cell nucleosome signal")
    sub.add_argument("--compute-frip", action="store_true", help="Compute fraction of fragments in peaks")
    sub.add_argument("--max-fragment-size", type=int, default=1000,
                     help="Largest fragment size recorded in the distribution")
    sub.add_argument("--peak-bed", help="Peak BED for FRiP regions (default: adata.var_names)")
    sub.add_argument("--filter", action="store_true", help="Apply QC filters")
    sub.add_argument("--min-fragments", type=int, default=1000, help="Minimum fragments per cell")
    sub.add_argument("--max-fragments", type=int, default=100000, help="Maximum fragments per cell")
    sub.add_argument("--min-tsse", type=float, default=5.0, help="Minimum TSS enrichment")
    sub.add_argument("--max-nucleosome-signal", type=float, default=2.0, help="Maximum nucleosome signal")
    sub.add_argument("--min-frip", type=float, default=0.15, help="Minimum FRiP")

    sub = subparsers.add_parser("peak_calling", help="Call peaks for scATAC-seq (snapATAC2)")
    sub.add_argument("--adata", required=True,
                     help="Input h5ad from snapatac2.pp.import_fragments (fragments in obsm)")
    sub.add_argument("--output", required=True, help="Output peak BED file")
    sub.add_argument("--mode", default="bulk", choices=["bulk", "pseudobulk"], help="Peak calling mode")
    sub.add_argument("--cluster-column", help="Column with cluster labels (for pseudobulk)")
    sub.add_argument("--qvalue", type=float, default=0.05, help="Q-value cutoff")
    sub.add_argument("--min-length", type=int, default=None,
                     help="Minimum peak length (default: MACS3 extsize)")
    sub.add_argument("--half-width", type=int, default=250,
                     help="pseudobulk only: fixed half-width for merge_peaks' iterative overlap")
    sub.add_argument("--n-jobs", type=int, default=8,
                     help="pseudobulk only: parallel MACS3 jobs across clusters")
    sub.add_argument("--counting-strategy", default="paired-insertion",
                     choices=["fragment", "insertion", "paired-insertion"],
                     help="How to count reads over a peak when --create-matrix is set")
    sub.add_argument("--create-matrix", action="store_true", help="Create peak x cell matrix")
    sub.add_argument("--outdir", help="Output directory for intermediate files")

    sub = subparsers.add_parser("gene_activity", help="Gene activity from fragments (snapATAC2)")
    sub.add_argument("--adata", required=True,
                     help="Input h5ad from snapatac2.pp.import_fragments (fragments in obsm)")
    sub.add_argument("--output", required=True, help="Output h5ad file with gene scores")
    sub.add_argument("--gtf-file", required=True, help="GTF/GFF annotation file (plain or gzip)")
    sub.add_argument("--upstream", type=int, default=2000,
                     help="Extend the regulatory domain upstream (bp)")
    sub.add_argument("--downstream", type=int, default=0,
                     help="Extend the regulatory domain downstream (bp)")
    sub.add_argument("--no-gene-body", dest="include_gene_body", action="store_false",
                     help="Use the TSS as the regulatory domain instead of the whole gene body")
    sub.add_argument("--id-type", default="gene", choices=["gene", "transcript"],
                     help="Annotate genes or transcripts")
    sub.add_argument("--counting-strategy", default="paired-insertion",
                     choices=["fragment", "insertion", "paired-insertion"],
                     help="How to count reads over a regulatory domain")

    # --- multiome ---
    sub = subparsers.add_parser("load_multiome", help="Assemble MuData from RNA+ATAC")
    sub.add_argument("--rna", required=True)
    sub.add_argument("--atac", required=True)
    sub.add_argument("--output", required=True)

    # --- functional ---
    sub = subparsers.add_parser("pathway_activity", help="decoupler pathway/TF activity")
    sub.add_argument("--adata", required=True, help="Input AnnData h5ad file")
    sub.add_argument("--output", required=True, help="Output h5ad file with pathway scores")
    sub.add_argument("--method", default="mlm", choices=["mlm", "ulm", "wsum", "gsea", "viper", "aucell"],
                     help="Statistical method")
    sub.add_argument("--resource", default="progeny",
                     help="Pathway resource (progeny, msigdb/hallmark, dorothea, collectri)")
    sub.add_argument("--organism", default="human", help="Organism (human or mouse)")
    _src = sub.add_mutually_exclusive_group()
    _src.add_argument("--layer", help="AnnData layer to use")
    _src.add_argument("--use-raw", action="store_true", help="Use adata.raw.X")
    sub.add_argument("--min-size", type=int, default=5, help="Minimum pathway size")

    sub = subparsers.add_parser("enrichment", help="Gene-set enrichment")
    sub.add_argument("--gene-list", required=True, help="Comma-separated gene list")
    sub.add_argument("--output", required=True, help="Output JSON file")
    sub.add_argument("--method", default="ora", choices=["ora"],
                     help="Enrichment method (ORA; GSEA needs ranked scores, unsupported here)")
    sub.add_argument("--resource", default="msigdb", help="Gene set resource")
    sub.add_argument("--organism", default="human", help="Organism (human or mouse)")
    sub.add_argument("--padj-threshold", type=float, default=0.05, help="Adjusted p-value threshold")
    sub.add_argument("--top-n", type=int, default=50, help="Number of top pathways to report")

    # --- benchmark ---
    sub = subparsers.add_parser("score", help="Score predictions vs GOLD reference")
    sub.add_argument("--input", required=True)
    sub.add_argument("--pred-key", required=True, help="predicted labeling (obs column or obsm key)")
    sub.add_argument("--ref-key", required=True, help="GOLD reference labeling (obs column or obsm key)")
    sub.add_argument("--metric", default="ari", choices=["ari", "nmi", "ami", "deconv_corr", "domain_ari"])

    # --- environment ---
    sub = subparsers.add_parser(
        "preflight", help="Verify the active Pixi env has the packages a modality needs"
    )
    # modality is optional: the harness launcher consumes it to select the
    # isolated env (--environment) and strips it from argv, so preflight falls
    # back to deriving the modality from PIXI_ENVIRONMENT_NAME at run time.
    sub.add_argument(
        "--modality", choices=["scrna", "spatial", "scatac", "multiome"], default=None
    )
    # Narrow the check to the exact request: a modality list alone cannot tell
    # whether e.g. `integrate --method scanorama` or peak_calling's macs3 binary
    # is available, so a modality-only green can still precede a runtime failure.
    # NB: not --subcommand — that dest is the top-level subparser's and would be clobbered.
    sub.add_argument("--for-subcommand", default=None,
                     help="Subcommand this preflight is for (adds its imports/executables)")
    sub.add_argument("--method", default=None,
                     help="Method chosen for --for-subcommand (adds that method's dependency)")
    sub.add_argument("--check-gpu", action="store_true", help="Also probe GPU availability")

    args = parser.parse_args()

    # Dispatch to the actual implementation
    try:
        if args.subcommand == "load_dataset":
            from .shared import load_dataset
            load_dataset.main(args)
        elif args.subcommand == "summarize":
            from .shared import summarize
            summarize.main(args)
        elif args.subcommand == "preprocess":
            from .shared import preprocess
            preprocess.main(args)
        elif args.subcommand == "validate_layout":
            from .shared import io
            io.validate_layout(args)
        elif args.subcommand == "marker_table":
            from .scrna import marker_table
            marker_table.main(args)
        elif args.subcommand == "integrate":
            from .scrna import standard_integrate
            standard_integrate.main(args)
        elif args.subcommand == "read_spatial":
            from .spatial import read_spatial
            read_spatial.main(args)
        elif args.subcommand == "atac_qc":
            from .scatac import atac_qc
            atac_qc.main(args)
        elif args.subcommand == "peak_calling":
            from .scatac import peak_calling
            peak_calling.main(args)
        elif args.subcommand == "gene_activity":
            from .scatac import gene_activity
            gene_activity.main(args)
        elif args.subcommand == "load_multiome":
            from .multiome import load_multiome
            load_multiome.main(args)
        elif args.subcommand == "pathway_activity":
            from .functional import decoupler_pathway_activity
            decoupler_pathway_activity.main(args)
        elif args.subcommand == "enrichment":
            from .functional import decoupler_enrichment
            decoupler_enrichment.main(args)
        elif args.subcommand == "score":
            from .shared import score
            score.main(args)
        elif args.subcommand == "preflight":
            from .shared import preflight
            preflight.main(args)
        else:
            parser.error(f"Unknown subcommand: {args.subcommand}")
    except ImportError as e:
        print(f"Failed to import {args.subcommand} module: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error executing {args.subcommand}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
