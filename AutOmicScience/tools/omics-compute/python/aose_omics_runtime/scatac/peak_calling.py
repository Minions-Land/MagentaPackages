"""Peak calling for scATAC-seq (snapATAC2 macs3 + merge_peaks)."""

import json
from datetime import datetime, UTC
from pathlib import Path

import anndata as ad
import pandas as pd
import snapatac2 as snap

from ..shared.io import save_h5ad, atomic_write
from . import _snap

_ALGORITHM = "snapatac2.tl.macs3"
_BED_COLUMNS = ["chr", "start", "end", "name", "score"]


def run_peak_calling(args):
    """Call peaks with snapATAC2's MACS3 driver, in bulk or per cluster.

    Bulk pools every cell into one pileup. Pseudobulk calls peaks within each
    ``cluster-column`` group and reconciles them with ``snapatac2.tl.merge_peaks``,
    whose iterative-overlap procedure yields a fixed-width, non-overlapping union —
    a rare cluster's peaks survive instead of being absorbed by an abundant one.
    Fails loud when no peaks are produced rather than emitting an empty "success".

    Args:
        args: Argparse namespace with parameters.

    Returns:
        dict: Result with peak locations, evidence metadata, and provenance.
    """
    start_time = datetime.now(UTC)

    adata = ad.read_h5ad(args.adata)
    _snap.require_fragments(adata, "peak_calling")

    missing_clusters = []
    if args.mode == "pseudobulk":
        if not args.cluster_column:
            raise ValueError(
                "pseudobulk mode requires --cluster-column (the obs column with cluster "
                "labels); refusing to silently fall back to bulk peak calling."
            )
        if args.cluster_column not in adata.obs:
            raise ValueError(
                f"--cluster-column {args.cluster_column!r} is not in obs "
                f"(available: {sorted(adata.obs.columns)[:10]})"
            )
        requested = {str(v) for v in pd.unique(adata.obs[args.cluster_column])}
        with _snap.preserved_tempdir():
            per_group = snap.tl.macs3(
                adata, groupby=args.cluster_column, qvalue=args.qvalue,
                min_len=args.min_length, inplace=False, n_jobs=args.n_jobs,
            )
        missing_clusters = sorted(requested - {str(k) for k in per_group})
        merged = snap.tl.merge_peaks(per_group, _snap.chrom_sizes(adata), half_width=args.half_width)
        peaks_df = _bed_from_merged(merged)
        group_columns = [c for c in merged.columns if c != "Peaks"]
    else:
        with _snap.preserved_tempdir():
            called = snap.tl.macs3(
                adata, groupby=None, qvalue=args.qvalue, min_len=args.min_length, inplace=False,
            )
        peaks_df = _bed_from_macs3(called)
        group_columns = []

    if len(peaks_df) == 0:
        raise RuntimeError(
            "Peak calling produced zero peaks; refusing to report success with an empty peak "
            "set. Check the fragment file, the q-value and min-length parameters, and that "
            "the retained cells carry enough fragments."
        )

    peak_file = Path(args.output)
    atomic_write(peak_file, lambda tmp: peaks_df.to_csv(tmp, sep="\t", index=False, header=False))

    widths = peaks_df["end"].sub(peaks_df["start"])
    peak_stats = {
        "n_peaks": int(len(peaks_df)),
        "mean_width": int(widths.mean()),
        "median_width": int(widths.median()),
        "total_bp": int(widths.sum()),
        "chr_distribution": {
            str(k): int(v) for k, v in list(peaks_df["chr"].value_counts().items())[:10]
        },
    }
    if peaks_df["score"].notna().any():
        peak_stats["mean_score"] = float(peaks_df["score"].mean())
        peak_stats["median_score"] = float(peaks_df["score"].median())

    metadata = {
        "algorithm": _ALGORITHM,
        "snapatac2_version": snap.__version__,
        "mode": args.mode,
        "qvalue": args.qvalue,
        "min_length": args.min_length,
        "half_width": args.half_width if args.mode == "pseudobulk" else None,
        "cluster_column": args.cluster_column if args.mode == "pseudobulk" else None,
        "n_peaks": int(len(peaks_df)),
        "missing_clusters": missing_clusters,
        "peak_file": str(peak_file),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    if args.create_matrix:
        peak_adata = snap.pp.make_peak_matrix(
            adata, use_rep=peaks_df["name"].tolist(), file=None,
            counting_strategy=args.counting_strategy,
        )
        for column in group_columns:
            peak_adata.var[column] = merged[column].to_list()
        peak_adata.uns["peak_calling"] = metadata
        save_meta = save_h5ad(adata=peak_adata, path=f"{peak_file.with_suffix('')}_matrix.h5ad")
        output_path = save_meta["path"]
    else:
        output_path = str(peak_file.resolve())

    end_time = datetime.now(UTC)
    elapsed_ms = int((end_time - start_time).total_seconds() * 1000)

    evidence = {
        "source": f"Peak calling ({_ALGORITHM}, snapATAC2 {snap.__version__})",
        "source_type": "computation",
        "query": f"{args.mode} peak calling",
        "description": (
            f"Called {len(peaks_df)} peaks with {_ALGORITHM} (mode={args.mode}, "
            f"qvalue={args.qvalue})"
        ),
        "timestamp": end_time.isoformat(),
        "metadata": {
            "algorithm": _ALGORITHM, "snapatac2_version": snap.__version__,
            "mode": args.mode, "n_peaks": int(len(peaks_df)),
            "qvalue_cutoff": args.qvalue, "peak_stats": peak_stats,
        },
    }
    trace = {
        "tool": "bio_atac_peak_calling",
        "status": "success",
        "input": {"adata": args.adata, "mode": args.mode,
                  "cluster_column": args.cluster_column},
        "output": {"n_peaks": int(len(peaks_df)), "output_file": output_path},
        "duration_ms": elapsed_ms,
        "timestamp": end_time.isoformat(),
    }
    return {
        "success": True,
        "output": output_path,
        "peak_file": str(peak_file),
        "n_peaks": int(len(peaks_df)),
        "mode": args.mode,
        "algorithm": _ALGORITHM,
        "snapatac2_version": snap.__version__,
        "missing_clusters": missing_clusters,
        "peak_stats": peak_stats,
        "evidence": [evidence],
        "trace": [trace],
        "elapsed_ms": elapsed_ms,
    }


def _bed_from_macs3(called):
    """BED frame from a MACS3 narrowPeak-style result (bulk mode, variable width)."""
    df = called.to_pandas()
    out = pd.DataFrame({
        "chr": df["chrom"].astype(str),
        "start": df["start"].astype(int),
        "end": df["end"].astype(int),
        "score": df["score"],
    })
    out["name"] = out["chr"] + ":" + out["start"].astype(str) + "-" + out["end"].astype(str)
    return out[_BED_COLUMNS]


def _bed_from_merged(merged):
    """BED frame from merge_peaks, whose 'Peaks' column holds 'chrom:start-end' strings."""
    peaks = merged["Peaks"].to_list()
    coords = pd.Series(peaks, dtype=str).str.extract(r"^(?P<chr>.+):(?P<start>\d+)-(?P<end>\d+)$")
    if coords.isna().any().any():
        raise ValueError(
            f"merge_peaks returned peak ids this reader cannot parse (first: {peaks[:3]}); "
            "expected 'chrom:start-end'."
        )
    out = pd.DataFrame({
        "chr": coords["chr"],
        "start": coords["start"].astype(int),
        "end": coords["end"].astype(int),
        "name": peaks,
        "score": pd.NA,
    })
    return out[_BED_COLUMNS]


def main(args):
    """CLI entry: run peak calling and print the report as strict JSON."""
    result = run_peak_calling(args)
    print(json.dumps(result, indent=2, allow_nan=False))
    return result
