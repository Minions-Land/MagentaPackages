"""scATAC-seq quality control (snapATAC2 metrics + our filter/report layer)."""

import json
from datetime import datetime, UTC
from pathlib import Path

import anndata as ad
import numpy as np
import snapatac2 as snap

from ..shared.io import save_h5ad
from . import _snap

_FRIP_KEY = "frip"
# Signac's convention: mononucleosomal (147-294bp) over nucleosome-free (<147bp).
_MONO_RANGE = (147, 294)


def run_atac_qc(args):
    """Compute scATAC-seq QC metrics and optionally filter cells.

    TSS enrichment, FRiP and the fragment-size distribution come from snapATAC2's
    metrics, which read the insertions ``snapatac2.pp.import_fragments`` stores in
    ``obsm``; ``n_fragment`` is written by import_fragments itself and is therefore
    always a true count. Per-cell nucleosome signal is computed here because
    snapATAC2 exposes only a dataset-wide fragment-size distribution.

    Metrics describe the full input (pre-filter); filters are applied afterwards and
    each threshold reports whether it actually ran.

    Args:
        args: Argparse namespace with parameters.

    Returns:
        dict: Result with QC metrics, evidence metadata, and provenance.
    """
    start_time = datetime.now(UTC)

    adata = ad.read_h5ad(args.adata)
    input_shape = adata.shape
    _snap.require_fragments(adata, "atac_qc")

    if adata.n_vars == 0:
        raise ValueError(
            "atac_qc needs a peak/tile matrix to report per-cell feature counts, but this "
            "object has no features. Build one first (snapatac2.pp.add_tile_matrix, or "
            "peak_calling --create-matrix)."
        )

    qc_metrics = {}

    if args.compute_tsse:
        _snap.require_matching_chroms(adata, args.gtf_file)
        snap.metrics.tsse(adata, gene_anno=Path(args.gtf_file))
        qc_metrics['tss_enrichment'] = _summarize(adata.obs['tsse'], method="snapatac2.metrics.tsse")

    if args.compute_fragment_size:
        snap.metrics.frag_size_distr(adata, max_recorded_size=args.max_fragment_size)
        adata.obs['nucleosome_signal'] = _nucleosome_signal(adata)
        qc_metrics['fragment_size'] = {
            'distribution_key': 'frag_size_distr',
            'distribution_method': 'snapatac2.metrics.frag_size_distr',
            'nucleosome_signal': _summarize(
                adata.obs['nucleosome_signal'], method="mononucleosomal_over_nucleosome_free"
            ),
        }

    qc_metrics['n_fragment'] = _summarize(adata.obs['n_fragment'], method="import_fragments")

    if args.compute_frip:
        regions = str(args.peak_bed) if args.peak_bed else list(adata.var_names)
        snap.metrics.frip(adata, {_FRIP_KEY: regions}, normalized=True)
        qc_metrics['frip'] = _summarize(
            adata.obs[_FRIP_KEY],
            method="snapatac2.metrics.frip",
            regions="peak_bed" if args.peak_bed else "var_names",
        )

    adata.obs['n_peaks'] = np.asarray((adata.X > 0).sum(axis=1)).ravel()
    qc_metrics['n_peaks'] = _summarize(adata.obs['n_peaks'], method="feature_matrix")

    n_cells_before = adata.n_obs
    filter_report = None
    if args.filter:
        adata, filter_report = apply_qc_filters(
            adata,
            min_fragments=args.min_fragments, max_fragments=args.max_fragments,
            min_tsse=args.min_tsse, max_nucleosome_signal=args.max_nucleosome_signal,
            min_frip=args.min_frip,
        )
    n_cells_after = adata.n_obs
    cells_removed = n_cells_before - n_cells_after

    adata.uns['atac_qc'] = {
        'snapatac2_version': snap.__version__,
        'metrics': qc_metrics,
        'metrics_stage': 'pre_filter',
        'filters_requested': args.filter,
        # True only if a threshold actually ran — requesting --filter while every
        # gating column is missing must not read as "filters were applied".
        'filters_applied': bool(filter_report and filter_report['applied']),
        'filter_report': filter_report,
        'filter_params': {
            'min_fragments': args.min_fragments,
            'max_fragments': args.max_fragments,
            'min_tsse': args.min_tsse,
            'max_nucleosome_signal': args.max_nucleosome_signal,
            'min_frip': args.min_frip,
        } if args.filter else None,
        'cells_before_filter': n_cells_before,
        'cells_after_filter': n_cells_after,
        'cells_removed': cells_removed,
        'timestamp': datetime.now(UTC).isoformat(),
    }

    save_meta = save_h5ad(adata=adata, path=args.output)
    output_path = save_meta["path"]

    end_time = datetime.now(UTC)
    elapsed_ms = int((end_time - start_time).total_seconds() * 1000)

    evidence = {
        "source": f"scATAC-seq QC (snapATAC2 {snap.__version__} metrics)",
        "source_type": "computation",
        "query": "ATAC QC metrics",
        "description": (
            f"Computed QC metrics on {n_cells_before} cells (pre-filter); "
            f"{cells_removed} removed by filtering, {n_cells_after} retained"
        ),
        "timestamp": end_time.isoformat(),
        "metadata": {
            "snapatac2_version": snap.__version__,
            "metrics_computed": list(qc_metrics.keys()),
            "cells_before": n_cells_before,
            "cells_after": n_cells_after,
            "n_peaks": adata.n_vars,
            "filters_requested": args.filter,
            "filters_applied": bool(filter_report and filter_report['applied']),
            "filter_report": filter_report,
        },
    }
    trace = {
        "tool": "bio_atac_qc",
        "status": "success",
        "input": {"adata": args.adata, "gtf_file": args.gtf_file},
        "output": {"n_cells": n_cells_after, "n_peaks": adata.n_vars, "output_file": output_path},
        "duration_ms": elapsed_ms,
        "timestamp": end_time.isoformat(),
    }
    return {
        "success": True,
        "output": output_path,
        "snapatac2_version": snap.__version__,
        "n_cells_before": n_cells_before,
        "n_cells_after": n_cells_after,
        "cells_removed": cells_removed,
        "n_peaks": adata.n_vars,
        "input_shape": list(input_shape),
        "qc_metrics": qc_metrics,
        "evidence": [evidence],
        "trace": [trace],
        "elapsed_ms": elapsed_ms,
    }


def _summarize(values, **provenance):
    """Summary stats over the finite entries, with ddof=0 so one cell is not NaN."""
    array = np.asarray(values, dtype=float)
    finite = array[np.isfinite(array)]
    summary = dict(provenance)
    summary.update({
        'mean': float(finite.mean()) if finite.size else None,
        'median': float(np.median(finite)) if finite.size else None,
        # ddof=0: population std is defined (0.0) for a single cell, where ddof=1
        # would yield NaN and break the strict-JSON report.
        'std': float(finite.std(ddof=0)) if finite.size else None,
        'min': float(finite.min()) if finite.size else None,
        'max': float(finite.max()) if finite.size else None,
        'n_cells_undefined': int((~np.isfinite(array)).sum()),
    })
    return summary


def _nucleosome_signal(adata):
    """Per-cell mononucleosomal / nucleosome-free fragment ratio.

    snapATAC2 reports only a dataset-wide fragment-size distribution, so this is
    computed here from the paired fragments it stores in obsm, whose values are the
    fragment lengths. Cells with no nucleosome-free fragment get NaN rather than a
    fabricated ratio; `_summarize` counts them and the filter drops them.
    """
    key = next(k for k in _snap.FRAGMENT_KEYS if k in adata.obsm)
    fragments = adata.obsm[key].tocsr()
    lo, hi = _MONO_RANGE
    signal = np.full(adata.n_obs, np.nan, dtype=float)
    for cell in range(adata.n_obs):
        lengths = fragments.data[fragments.indptr[cell]:fragments.indptr[cell + 1]]
        if lengths.size == 0:
            continue
        free = int((lengths < lo).sum())
        mono = int(((lengths >= lo) & (lengths <= hi)).sum())
        if free:
            signal[cell] = mono / free
    return signal


def apply_qc_filters(adata, *, min_fragments=1000, max_fragments=100000,
                     min_tsse=5, max_nucleosome_signal=2.0, min_frip=0.15):
    """Apply QC filters and report which ran.

    Each threshold is applied only when its column exists; skipped thresholds are
    reported with a reason rather than silently recorded as applied.

    Returns:
        (filtered AnnData, {"applied": [...], "skipped": {name: reason}})
    """
    mask = np.ones(adata.n_obs, dtype=bool)
    applied, skipped = [], {}

    mask &= (adata.obs['n_fragment'] >= min_fragments).to_numpy()
    mask &= (adata.obs['n_fragment'] <= max_fragments).to_numpy()
    applied.append('n_fragment')

    def gate(name, threshold, keep, flag):
        if threshold is None:
            return np.ones(adata.n_obs, dtype=bool)
        if name not in adata.obs.columns:
            skipped[name] = f"no {name} column computed (pass {flag})"
            return np.ones(adata.n_obs, dtype=bool)
        applied.append(name)
        return keep(adata.obs[name]).to_numpy()

    mask &= gate('tsse', min_tsse, lambda s: s >= min_tsse, '--compute-tsse')
    mask &= gate('nucleosome_signal', max_nucleosome_signal,
                 lambda s: s <= max_nucleosome_signal, '--compute-fragment-size')
    mask &= gate(_FRIP_KEY, min_frip, lambda s: s >= min_frip, '--compute-frip')

    return adata[mask, :].copy(), {"applied": applied, "skipped": skipped}


def main(args):
    """CLI entry: run QC and print the report as strict JSON."""
    result = run_atac_qc(args)
    print(json.dumps(result, indent=2, allow_nan=False))
    return result
