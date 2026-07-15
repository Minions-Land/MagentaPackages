"""Decoupler enrichment analysis implementation."""

import json
from datetime import datetime, UTC
from pathlib import Path
import decoupler as dc
import pandas as pd


def run_decoupler_enrichment(args):
    """
    Run gene set enrichment analysis using decoupler.

    Args:
        args: Argparse namespace with parameters

    Returns:
        dict: Result with enrichment scores, evidence metadata, and provenance
    """
    start_time = datetime.now(UTC)

    # Parse gene list
    gene_list = [g.strip() for g in args.gene_list.split(',') if g.strip()]
    if len(gene_list) == 0:
        raise ValueError("Empty gene list provided")

    # Get gene set resource
    resource_name = args.resource.lower()
    organism = args.organism.lower()

    try:
        if resource_name == "msigdb" or resource_name == "hallmark":
            net = dc.op.hallmark(organism=organism)
        elif resource_name == "progeny":
            net = dc.op.progeny(organism=organism, top=100)
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

    # Run enrichment analysis
    method = args.method.lower()

    if method == "gsea":
        # GSEA needs a ranked (gene, score) list, which this gene-list subcommand
        # does not accept. Fail loud rather than silently degrade.
        raise ValueError(
            "GSEA needs a ranked gene list (gene, score pairs), which the "
            "'enrichment' subcommand does not accept; use method='ora'."
        )
    if method != "ora":
        raise ValueError(f"Unknown enrichment method: {method}")

    # Over-representation analysis: the classic one-tailed hypergeometric (Fisher)
    # test of the query gene set against each source in the network. The gene sets
    # come from decoupler 2.x (dc.op.* above); dc.mt.ora itself is a per-observation
    # matrix method (top-n_up features per cell) and a poor fit for a single explicit
    # gene list, so the standard ORA test is run directly over the sets.
    import numpy as np
    from scipy.stats import hypergeom

    sets = net.groupby("source")["target"].apply(lambda s: set(s))
    universe = set().union(*sets.to_list()) if len(sets) else set()
    query_all = set(gene_list)
    # Background (universe) is the resource, independent of the query. Folding the
    # query in would inflate N/n and make the "no input genes present" check dead.
    query = query_all & universe
    N, n = len(universe), len(query)
    n_query_unmapped = len(query_all) - n
    if n == 0:
        raise ValueError(
            f"None of the {len(query_all)} input genes are present in the resource background "
            f"(universe size {N}); cannot run ORA."
        )

    rows = []
    for source, targets in sets.items():
        K = len(targets)  # targets are within the universe by construction
        k = len(query & targets)
        rows.append({
            "source": source,
            "overlap": k,
            "pathway_size": K,
            "pval": float(hypergeom.sf(k - 1, N, K, n)),   # P(overlap >= k)
        })
    enrich_results = pd.DataFrame(rows)

    # Benjamini-Hochberg FDR across sources.
    pv = enrich_results["pval"].to_numpy()
    m = len(pv)
    order = np.argsort(pv)
    adj = np.empty(m)
    adj[order] = np.minimum.accumulate((pv[order] * m / (np.arange(m) + 1))[::-1])[::-1]
    enrich_results["padj"] = np.clip(adj, 0.0, 1.0)

    # Filter by adjusted p-value and rank by significance.
    significant = enrich_results[enrich_results["padj"] < args.padj_threshold].copy()
    significant = significant.sort_values("padj")

    top_pathways = significant.head(args.top_n)

    # Build result dictionary
    enrichment_data = {
        'method': method,
        'resource': resource_name,
        'organism': organism,
        # n_input_genes counts the raw list; the unique count is what maps, so
        # n_input_unique == n_query_mapped + n_query_unmapped always reconciles.
        'n_input_genes': len(gene_list),
        'n_input_unique': len(query_all),
        'n_query_mapped': n,
        'n_query_unmapped': n_query_unmapped,
        'universe_size': N,
        'n_pathways_tested': len(enrich_results),
        'n_significant_pathways': len(significant),
        'padj_threshold': args.padj_threshold,
        'top_pathways': top_pathways.to_dict('records'),
        'all_results': enrich_results.to_dict('records'),
        'timestamp': datetime.now(UTC).isoformat(),
    }

    # Save output (atomic; creates parent dir)
    from ..shared.io import atomic_write
    output_path = atomic_write(
        args.output,
        lambda tmp: tmp.write_text(json.dumps(enrichment_data, indent=2, allow_nan=False)),
    )

    end_time = datetime.now(UTC)
    elapsed_ms = int((end_time - start_time).total_seconds() * 1000)

    # Build evidence record
    evidence = {
        "source": f"decoupler {dc.__version__}",
        "source_type": "computation",
        "query": f"{method} enrichment analysis",
        "description": f"Found {len(significant)} significant pathways from {len(gene_list)} genes using {method} on {resource_name}",
        "timestamp": end_time.isoformat(),
        "metadata": {
            "method": method,
            "resource": resource_name,
            "organism": organism,
            "n_input_genes": len(gene_list),
            "n_pathways_tested": len(enrich_results),
            "n_significant": len(significant),
            "padj_threshold": args.padj_threshold,
        }
    }

    # Build trace step
    trace = {
        "tool": "bio_decoupler_enrichment",
        "status": "success",
        "input": {
            "n_genes": len(gene_list),
            "method": method,
            "resource": resource_name,
            "organism": organism,
        },
        "output": {
            "n_pathways_tested": len(enrich_results),
            "n_significant": len(significant),
            "output_file": str(output_path),
        },
        "duration_ms": elapsed_ms,
        "timestamp": end_time.isoformat(),
    }

    # Extract top pathway info for summary
    top_5_pathways = []
    for idx, row in top_pathways.head(5).iterrows():
        pathway_info = {
            'name': row['source'],
            'pvalue': float(row.get('padj', 1.0)),
        }
        # Try to get overlap/gene count
        for col in ['Overlap', 'n_genes', 'size', 'overlap']:
            if col in row:
                pathway_info['n_genes'] = int(row[col]) if pd.notna(row[col]) else 0
                break
        top_5_pathways.append(pathway_info)

    # Build result
    result = {
        "success": True,
        "output": str(output_path),
        "n_input_genes": len(gene_list),
        "n_input_unique": len(query_all),
        "n_query_mapped": n,
        "n_query_unmapped": n_query_unmapped,
        "universe_size": N,
        "n_pathways_tested": len(enrich_results),
        "n_significant_pathways": len(significant),
        "method": method,
        "resource": resource_name,
        "organism": organism,
        "top_pathways": top_5_pathways,
        "evidence": [evidence],
        "trace": [trace],
        "elapsed_ms": elapsed_ms,
    }

    return result


def main(args):
    """CLI entry for enrichment subcommand."""
    import json

    result = run_decoupler_enrichment(args)

    # Print summary
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Gene set enrichment analysis using decoupler')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--gene-list', required=True, help='Comma-separated gene list')
    parser.add_argument('--resource', default='msigdb', help='Gene set resource (msigdb, hallmark, progeny, dorothea, collectri)')
    parser.add_argument('--method', default='ora', choices=['ora'],
                        help='Enrichment method (ORA; GSEA needs ranked scores, not supported here)')
    parser.add_argument('--organism', default='human', help='Organism (human, mouse)')
    parser.add_argument('--padj-threshold', type=float, default=0.05, help='Adjusted p-value threshold')
    parser.add_argument('--top-n', type=int, default=50, help='Number of top pathways to report')
    args = parser.parse_args()
    main(args)
