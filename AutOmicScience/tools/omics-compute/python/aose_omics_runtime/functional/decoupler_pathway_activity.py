"""Decoupler pathway activity inference implementation."""

import functools
import json
from datetime import datetime, UTC
import anndata as ad
import decoupler as dc
import pandas as pd

from ..shared.io import save_h5ad


def run_decoupler_pathway_activity(args):
    """
    Infer pathway activity from gene expression using decoupler.

    Args:
        args: Argparse namespace with parameters

    Returns:
        dict: Result with pathway scores, evidence metadata, and provenance
    """
    start_time = datetime.now(UTC)

    # Load input data
    adata = ad.read_h5ad(args.adata)
    input_shape = adata.shape

    # Select the expression source (mutually exclusive; fail loud if unavailable).
    if args.use_raw and args.layer:
        raise ValueError("use_raw and layer are mutually exclusive; choose one expression source")
    if args.use_raw:
        if adata.raw is None:
            raise ValueError("use_raw=True but adata.raw is None; refusing to silently fall back to X")
        expr_data = adata.raw.to_adata()
        expr_source = "raw"
    elif args.layer:
        if args.layer not in adata.layers:
            raise ValueError(f"layer '{args.layer}' not found; available: {list(adata.layers.keys())}")
        expr_data = adata.copy()
        expr_data.X = expr_data.layers[args.layer]
        expr_source = f"layer:{args.layer}"
    else:
        expr_data = adata.copy()
        expr_source = "X"

    # Get pathway resource
    resource_name = args.resource.lower()
    organism = args.organism.lower()

    try:
        if resource_name == "progeny":
            net = dc.op.progeny(organism=organism, top=100)
        elif resource_name == "msigdb" or resource_name == "hallmark":
            # Get MSigDB Hallmark pathways
            net = dc.op.hallmark(organism=organism)
        elif resource_name == "dorothea":
            net = dc.op.dorothea(organism=organism)
        elif resource_name == "collectri":
            net = dc.op.collectri(organism=organism)
        else:
            raise ValueError(
                f"Unsupported resource '{resource_name}'; supported resources are "
                "msigdb/hallmark, progeny, dorothea, collectri"
            )
    except Exception as e:
        raise ValueError(f"Failed to load resource '{resource_name}': {e}")

    # Run pathway activity inference.
    #
    # decoupler 2.x semantics (dc.mt.<method>): when given an AnnData it writes
    # the result in place to obsm["score_<name>"] (and obsm["padj_<name>"] when
    # the method reports p-values) and returns None. `tmin` prunes each source to
    # a minimum number of targets present in the data. expr_data.X already holds
    # the chosen matrix (raw / layer resolved above), so no raw=/layer= is passed.
    method = args.method.lower()
    method_funcs = {
        "mlm": dc.mt.mlm,
        "ulm": dc.mt.ulm,
        "wsum": functools.partial(dc.mt.waggr, fun="wsum"),  # real weighted sum (dc.mt.waggr)
        "gsea": dc.mt.gsea,
        "viper": dc.mt.viper,
        "aucell": dc.mt.aucell,
    }
    # obsm score key each decoupler method writes, and the real decoupler backend
    # behind it (recorded in provenance so 'wsum' can never again mean something else).
    method_score_name = {
        "mlm": "mlm", "ulm": "ulm", "wsum": "waggr",
        "gsea": "gsea", "viper": "viper", "aucell": "aucell",
    }
    method_backend = {
        "mlm": ("dc.mt.mlm", None), "ulm": ("dc.mt.ulm", None),
        "wsum": ("dc.mt.waggr", "wsum"),
        "gsea": ("dc.mt.gsea", None), "viper": ("dc.mt.viper", None),
        "aucell": ("dc.mt.aucell", None),
    }
    if method == "ora":
        raise ValueError(
            "ORA needs a gene list, not an expression matrix; use the 'enrichment' subcommand"
        )
    if method not in method_funcs:
        raise ValueError(f"Unknown method: {method}")

    func = method_funcs[method]
    score_name = method_score_name[method]
    try:
        result = func(expr_data, net, tmin=args.min_size)
        if result is not None:
            expr_data = result
    except Exception as e:
        raise ValueError(f"Failed to run {method}: {e}")

    # Extract the activity scores decoupler wrote in place. `activities` is a
    # DataFrame (index = cells, columns = pathways / TFs).
    score_key = f"score_{score_name}"
    if score_key not in expr_data.obsm:
        raise ValueError(
            f"decoupler did not produce '{score_key}' in obsm; got {list(expr_data.obsm.keys())}"
        )
    activities = expr_data.obsm[score_key]
    pvals = expr_data.obsm.get(f"padj_{score_name}")

    # decoupler may drop all-zero observations; align the output to exactly the
    # cells it scored so the obsm write-back cannot mismatch length.
    n_input = adata.n_obs
    adata = adata[activities.index].copy()
    n_dropped_empty = n_input - adata.n_obs
    adata.obsm[f'pathway_{method}'] = activities.loc[adata.obs_names]
    if pvals is not None:
        adata.obsm[f'pathway_{method}_pvals'] = pvals.loc[adata.obs_names]

    backend, backend_fun = method_backend[method]
    adata.uns['pathway_analysis'] = {
        'method': method,
        'decoupler_backend': backend,
        'decoupler_fun': backend_fun if backend_fun is not None else '',
        'score_key': score_key,
        'resource': resource_name,
        'organism': organism,
        'expression_source': expr_source,
        'n_dropped_empty_obs': n_dropped_empty,
        'min_size': args.min_size,
        'n_pathways': activities.shape[1],
        'pathway_names': list(activities.columns),
        'timestamp': datetime.now(UTC).isoformat(),
    }

    save_meta = save_h5ad(adata=adata, path=args.output)
    output_path = save_meta["path"]

    end_time = datetime.now(UTC)
    elapsed_ms = int((end_time - start_time).total_seconds() * 1000)

    # Build evidence record
    evidence = {
        "source": f"decoupler {dc.__version__}",
        "source_type": "computation",
        "query": f"{method} pathway activity inference",
        "description": f"Inferred activity of {activities.shape[1]} pathways using {method} method on {resource_name} resource",
        "timestamp": end_time.isoformat(),
        "metadata": {
            "method": method,
            "resource": resource_name,
            "organism": organism,
            "n_pathways": activities.shape[1],
            "n_cells": activities.shape[0],
            "min_pathway_size": args.min_size,
            "input_shape": list(input_shape),
            "has_pvalues": pvals is not None,
        }
    }

    # Build trace step
    trace = {
        "tool": "bio_decoupler_pathway_activity",
        "status": "success",
        "input": {
            "adata": args.adata,
            "method": method,
            "resource": resource_name,
            "organism": organism,
        },
        "output": {
            "n_pathways": activities.shape[1],
            "output_file": str(output_path),
        },
        "duration_ms": elapsed_ms,
        "timestamp": end_time.isoformat(),
    }

    # Get pathway statistics
    pathway_stats = {
        'mean_activity': activities.mean().to_dict(),
        # ddof=0 -> 0 (not NaN) for a single observation, keeping the report strict-JSON safe.
        'std_activity': activities.std(ddof=0).to_dict(),
        'min_activity': activities.min().to_dict(),
        'max_activity': activities.max().to_dict(),
    }

    # Build result
    result = {
        "success": True,
        "output": str(output_path),
        "n_pathways": activities.shape[1],
        "n_cells": activities.shape[0],
        "method": method,
        "resource": resource_name,
        "organism": organism,
        "pathway_names": list(activities.columns)[:20],  # First 20 pathways
        "pathway_stats": {k: dict(list(v.items())[:5]) for k, v in pathway_stats.items()},  # First 5 pathways
        "evidence": [evidence],
        "trace": [trace],
        "elapsed_ms": elapsed_ms,
    }

    return result


def main(args):
    """CLI entry for pathway_activity subcommand."""
    import json

    result = run_decoupler_pathway_activity(args)

    # Print summary
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Pathway activity inference using decoupler')
    parser.add_argument('--adata', required=True, help='Input h5ad file')
    parser.add_argument('--output', required=True, help='Output h5ad file with pathway scores')
    parser.add_argument('--resource', default='progeny', help='Pathway resource (progeny, msigdb, dorothea, collectri)')
    parser.add_argument('--method', default='mlm', choices=['mlm', 'ulm', 'wsum', 'gsea', 'viper', 'aucell'],
                        help='Inference method')
    parser.add_argument('--organism', default='human', help='Organism (human, mouse)')
    # Expression source is a single choice — mirrors the unified CLI.
    _src = parser.add_mutually_exclusive_group()
    _src.add_argument('--use-raw', action='store_true', help='Use adata.raw for expression')
    _src.add_argument('--layer', help='Layer to use for expression')
    parser.add_argument('--min-size', type=int, default=5, help='Minimum pathway size')
    args = parser.parse_args()
    main(args)
