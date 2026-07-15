"""Gene activity scores from scATAC-seq fragments (snapATAC2 make_gene_matrix)."""

import json
from datetime import datetime, UTC
from pathlib import Path

import anndata as ad
import numpy as np
import snapatac2 as snap

from ..shared.io import save_h5ad
from . import _snap

_ALGORITHM = "snapatac2.pp.make_gene_matrix"


def run_gene_activity(args):
    """Compute a cell x gene activity matrix with snapATAC2's make_gene_matrix.

    Counts TN5 insertions in each gene's regulatory domain — the gene body when
    ``include_gene_body`` is set, otherwise the TSS — extended by ``upstream`` and
    ``downstream`` base pairs. Insertions are read from the fragments that
    ``snapatac2.pp.import_fragments`` stores in ``obsm``, not from ``X``, so a plain
    peak matrix is rejected rather than silently scored.

    Args:
        args: Argparse namespace with parameters.

    Returns:
        dict: Result with gene activity scores, evidence metadata, and provenance.
    """
    start_time = datetime.now(UTC)

    adata = ad.read_h5ad(args.adata)
    _snap.require_fragments(adata, "gene_activity")
    _snap.require_matching_chroms(adata, args.gtf_file)

    gene_adata = snap.pp.make_gene_matrix(
        adata,
        gene_anno=Path(args.gtf_file),
        file=None,
        upstream=args.upstream,
        downstream=args.downstream,
        include_gene_body=args.include_gene_body,
        id_type=args.id_type,
        counting_strategy=args.counting_strategy,
    )

    gene_scores = gene_adata.X
    if gene_scores.nnz == 0:
        raise ValueError(
            f"Gene activity is all zero for {gene_adata.n_vars} genes: no insertion fell in any "
            "gene's regulatory domain. Chromosome naming matches, so check that the annotation "
            "covers the fragment file's contigs and that upstream/downstream are not degenerate. "
            "Refusing to write an empty gene matrix."
        )

    per_cell = np.asarray((gene_scores > 0).sum(axis=1)).ravel()
    gene_stats = {
        'n_genes': int(gene_adata.n_vars),
        'n_cells': int(gene_adata.n_obs),
        'mean_genes_per_cell': float(per_cell.mean()),
        'median_genes_per_cell': float(np.median(per_cell)),
        'sparsity': float(1 - (gene_scores.nnz / (gene_adata.n_obs * gene_adata.n_vars))),
        'n_genes_with_signal': int((np.asarray(gene_scores.sum(axis=0)).ravel() > 0).sum()),
    }

    metadata = {
        'algorithm': _ALGORITHM,
        'snapatac2_version': snap.__version__,
        'gtf_file': str(args.gtf_file),
        'n_genes': int(gene_adata.n_vars),
        'parameters': {
            'upstream': args.upstream,
            'downstream': args.downstream,
            'include_gene_body': args.include_gene_body,
            'id_type': args.id_type,
            'counting_strategy': args.counting_strategy,
        },
        'timestamp': datetime.now(UTC).isoformat(),
    }
    gene_adata.uns['gene_activity'] = metadata

    save_meta = save_h5ad(adata=gene_adata, path=args.output)
    output_path = save_meta["path"]

    end_time = datetime.now(UTC)
    elapsed_ms = int((end_time - start_time).total_seconds() * 1000)

    evidence = {
        "source": f"Gene activity ({_ALGORITHM}, snapATAC2 {snap.__version__})",
        "source_type": "computation",
        "query": "TN5 insertions per gene regulatory domain",
        "description": (
            f"Computed gene activity for {gene_adata.n_vars} genes across {gene_adata.n_obs} cells "
            f"via {_ALGORITHM} (counting_strategy={args.counting_strategy}, "
            f"include_gene_body={args.include_gene_body}, upstream={args.upstream})"
        ),
        "timestamp": end_time.isoformat(),
        "metadata": {
            "algorithm": _ALGORITHM, "snapatac2_version": snap.__version__,
            "n_genes": int(gene_adata.n_vars), "n_cells": int(gene_adata.n_obs),
            "gene_stats": gene_stats,
        },
    }
    trace = {
        "tool": "bio_atac_gene_activity",
        "status": "success",
        "input": {"adata": args.adata, "gtf_file": args.gtf_file,
                  "counting_strategy": args.counting_strategy},
        "output": {"n_genes": int(gene_adata.n_vars), "n_cells": int(gene_adata.n_obs),
                   "output_file": output_path},
        "duration_ms": elapsed_ms,
        "timestamp": end_time.isoformat(),
    }
    return {
        "success": True,
        "output": output_path,
        "n_genes": int(gene_adata.n_vars),
        "n_cells": int(gene_adata.n_obs),
        "algorithm": _ALGORITHM,
        "snapatac2_version": snap.__version__,
        "gene_stats": gene_stats,
        "evidence": [evidence],
        "trace": [trace],
        "elapsed_ms": elapsed_ms,
    }


def main(args):
    """CLI entry: run gene activity and print the report as strict JSON."""
    result = run_gene_activity(args)
    print(json.dumps(result, indent=2, allow_nan=False))
    return result
