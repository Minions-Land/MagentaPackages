"""
MuData assembly for multiome (RNA + ATAC) datasets.

Handles:
- Loading paired RNA/ATAC modalities into MuData
- Fragment file integration for ATAC
- Quality metric computation across modalities
- Joint filtering on the MuData

Environment: sc-multiome (muon, scanpy)
"""

import json
from typing import Optional

import muon as mu
import scanpy as sc

from ..shared.io import save_h5mu
from ..shared.conventions import LAYER_COUNTS
from ..shared.preprocess import _looks_like_counts


def _ensure_raw_counts(mod, name):
    """Guarantee a validated raw-counts source for a modality: reset X from a
    canonical counts layer (authoritative), else copy a counts-like X into the
    layer, else fail loud. QC and the saved object then use raw counts."""
    if LAYER_COUNTS in mod.layers:
        mod.X = mod.layers[LAYER_COUNTS].copy()
    elif _looks_like_counts(mod.X):
        mod.layers[LAYER_COUNTS] = mod.X.copy()
    else:
        raise ValueError(
            f"{name} modality: X is not raw counts and layers['{LAYER_COUNTS}'] is absent. "
            "Multiome assembly must preserve raw counts per modality; provide raw counts."
        )


def load_multiome(
    rna_path: str,
    atac_path: str,
    fragments_path: Optional[str] = None,
    output_path: Optional[str] = None,
    min_genes: int = 200,
    min_peaks: int = 500,
    max_pct_mito: float = 20.0,
    min_overlap: float = 0.5,
) -> dict:
    """
    Load paired RNA and ATAC modalities into a MuData object, then QC + filter
    on the MuData itself (MuData-first: assemble → intersect → joint filter).

    Args:
        rna_path: Path to RNA AnnData (.h5ad)
        atac_path: Path to ATAC AnnData (.h5ad)
        fragments_path: Optional path to fragments file (.tsv.gz) for ATAC
        output_path: Optional path to save assembled MuData (.h5mu)
        min_genes: Minimum genes per cell (RNA)
        min_peaks: Minimum peaks per cell (ATAC)
        max_pct_mito: Maximum mitochondrial percentage (RNA)
        min_overlap: Minimum RNA/ATAC barcode overlap rate (vs the larger side) to
            accept as paired multiome; below this the join fails loud.

    Returns:
        dict with n_cells_{rna,atac,joint,filtered}, overlap_rate, n_dropped_{rna,atac},
        n_genes, n_peaks, mdata_path
    """
    rna = sc.read_h5ad(rna_path)
    atac = sc.read_h5ad(atac_path)
    n_cells_rna_orig = rna.n_obs
    n_cells_atac_orig = atac.n_obs

    if fragments_path:
        atac.uns["files"] = {"fragments": fragments_path}

    # Validate/establish a raw-counts source per modality; QC uses raw counts.
    _ensure_raw_counts(rna, "rna")
    _ensure_raw_counts(atac, "atac")

    # Keep a caller-provided var['mt']; only derive from prefix when absent (never
    # clobber a validated annotation — Ensembl var_names would collapse mt% to 0).
    if "mt" not in rna.var.columns:
        rna.var["mt"] = rna.var_names.str.startswith("MT-") | rna.var_names.str.startswith("mt-")
    sc.pp.calculate_qc_metrics(rna, qc_vars=["mt"], percent_top=None, inplace=True)
    sc.pp.calculate_qc_metrics(atac, percent_top=None, inplace=True)

    # Assemble the MuData first, then intersect to the shared cells (MuData-first).
    mdata = mu.MuData({"rna": rna, "atac": atac})
    mu.pp.intersect_obs(mdata)
    n_cells_joint = mdata.n_obs
    # Rate against the larger side, so loss on either side is reflected.
    denom = max(n_cells_rna_orig, n_cells_atac_orig, 1)
    overlap_rate = n_cells_joint / denom

    if n_cells_joint == 0:
        raise ValueError(
            f"RNA and ATAC barcodes do not overlap (RNA={n_cells_rna_orig}, "
            f"ATAC={n_cells_atac_orig}, joint=0): not paired multiome cells, or barcode "
            "conventions differ. Refusing to write an empty MuData."
        )
    if overlap_rate < min_overlap:
        raise ValueError(
            f"RNA/ATAC barcode overlap is only {n_cells_joint}/{denom} (rate {overlap_rate:.2f} "
            f"< {min_overlap}): these are unlikely to be paired multiome cells. Refusing to force "
            "a join; check barcode conventions or lower min_overlap deliberately."
        )

    # Joint QC filter, applied to the MuData (propagates to both modalities).
    rna_keep = (mdata["rna"].obs["n_genes_by_counts"] >= min_genes) & (
        mdata["rna"].obs["pct_counts_mt"] <= max_pct_mito
    )
    atac_keep = mdata["atac"].obs["n_genes_by_counts"] >= min_peaks
    keep = rna_keep.reindex(mdata.obs_names) & atac_keep.reindex(mdata.obs_names)
    mu.pp.filter_obs(mdata, keep.to_numpy())
    n_cells_filtered = mdata.n_obs

    if n_cells_filtered == 0:
        raise ValueError(
            f"Joint QC removed all {n_cells_joint} cells (min_genes={min_genes}, "
            f"min_peaks={min_peaks}, max_pct_mito={max_pct_mito}). Adjust thresholds."
        )

    result = {
        "n_cells_rna": n_cells_rna_orig,
        "n_cells_atac": n_cells_atac_orig,
        "n_cells_joint": n_cells_joint,
        "n_cells_filtered": n_cells_filtered,
        "overlap_rate": round(float(overlap_rate), 4),
        "n_dropped_rna": n_cells_rna_orig - n_cells_joint,
        "n_dropped_atac": n_cells_atac_orig - n_cells_joint,
        "n_genes": mdata["rna"].n_vars,
        "n_peaks": mdata["atac"].n_vars,
    }

    if output_path:
        save_meta = save_h5mu(mdata=mdata, path=output_path)
        result["mdata_path"] = save_meta["path"]

    return result


def main(args):
    """CLI entry for the `load_multiome` subcommand (--rna / --atac / --output)."""
    result = load_multiome(
        rna_path=args.rna,
        atac_path=args.atac,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2, default=str, allow_nan=False))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load multiome RNA+ATAC into MuData")
    parser.add_argument("--rna", required=True, help="RNA AnnData path (.h5ad)")
    parser.add_argument("--atac", required=True, help="ATAC AnnData path (.h5ad)")
    parser.add_argument("--output", required=True, help="Output MuData path (.h5mu)")
    main(parser.parse_args())
