"""Regression tests for functional wrappers (codex_bugs.md section G).

Covers ORA universe (F01), wsum!=zscore (F02), use_raw/layer exclusivity (F03),
empty-row alignment (F05), single-obs strict JSON (F06), and the GSEA CLI choice
(F07b). The network resource fetch is monkeypatched; runtime code is never modified.

F04 is moot: the `perturbation` subcommand it covered was removed — perturbation
DE is now a REFERENCE hand-rolled path (single-cell rna skill, functional.md).
"""

import json
import types

import numpy as np
import pandas as pd
import pytest
import anndata as ad

from aose_omics_runtime.functional import (
    decoupler_enrichment as E,
    decoupler_pathway_activity as PA,
)

_NET = pd.DataFrame({"source": ["S", "S"], "target": ["g0", "g1"], "weight": [1.0, 2.0]})


def _pa_args(tmp_path, adata_path, method="wsum", use_raw=False, layer=None):
    return types.SimpleNamespace(
        adata=str(adata_path), output=str(tmp_path / "out.h5ad"), resource="progeny",
        organism="human", method=method, use_raw=use_raw, layer=layer, min_size=1,
    )


def _write(tmp_path, X, var, obs, name="in.h5ad"):
    a = ad.AnnData(np.asarray(X, dtype=float))
    a.var_names = var
    a.obs_names = obs
    p = tmp_path / name
    a.write_h5ad(p)
    return p


def test_f01_ora_universe_independent_of_query(monkeypatch):
    monkeypatch.setattr(E.dc.op, "hallmark",
                        lambda organism=None: pd.DataFrame({"source": ["P", "P", "Q"], "target": ["A", "B", "C"]}),
                        raising=False)
    args = types.SimpleNamespace(gene_list="X,Y", resource="hallmark", organism="human",
                                 method="ora", output="/tmp/ignore_ora.json", padj_threshold=0.05, top_n=50)
    with pytest.raises(ValueError, match="present in the resource"):
        E.run_decoupler_enrichment(args)


def test_f02_wsum_runs_real_weighted_sum_not_zscore(tmp_path, monkeypatch):
    import decoupler as dc
    monkeypatch.setattr(PA.dc.op, "progeny", lambda organism=None, top=100: _NET, raising=False)
    p = _write(tmp_path, [[1.0, 2.0, 3.0], [2.0, 1.0, 0.0]], ["g0", "g1", "g2"], ["c0", "c1"])
    PA.run_decoupler_pathway_activity(_pa_args(tmp_path, p, method="wsum"))
    out = ad.read_h5ad(tmp_path / "out.h5ad")
    got = float(np.asarray(out.obsm["pathway_wsum"])[0, 0])
    ref = ad.AnnData(np.array([[1.0, 2.0, 3.0], [2.0, 1.0, 0.0]]))
    ref.var_names = ["g0", "g1", "g2"]
    dc.mt.waggr(ref, _NET, fun="wsum", tmin=1)
    assert got == pytest.approx(float(ref.obsm["score_waggr"].iloc[0, 0]))
    assert got != pytest.approx(-0.4714, abs=1e-3)  # not the zscore alias


def test_f03_use_raw_without_raw_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setattr(PA.dc.op, "progeny", lambda organism=None, top=100: _NET, raising=False)
    p = _write(tmp_path, [[1.0, 2.0, 3.0], [2.0, 1.0, 0.0]], ["g0", "g1", "g2"], ["c0", "c1"])
    with pytest.raises(ValueError, match="adata.raw is None"):
        PA.run_decoupler_pathway_activity(_pa_args(tmp_path, p, method="mlm", use_raw=True))


def test_f03_use_raw_and_layer_mutually_exclusive(tmp_path, monkeypatch):
    monkeypatch.setattr(PA.dc.op, "progeny", lambda organism=None, top=100: _NET, raising=False)
    p = _write(tmp_path, [[1.0, 2.0, 3.0], [2.0, 1.0, 0.0]], ["g0", "g1", "g2"], ["c0", "c1"])
    with pytest.raises(ValueError, match="mutually exclusive"):
        PA.run_decoupler_pathway_activity(_pa_args(tmp_path, p, method="mlm", use_raw=True, layer="counts"))


def test_f05_empty_observation_aligned(tmp_path, monkeypatch):
    monkeypatch.setattr(PA.dc.op, "progeny", lambda organism=None, top=100: _NET, raising=False)
    p = _write(tmp_path, [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]], ["g0", "g1", "g2"], ["empty", "c1"])
    PA.run_decoupler_pathway_activity(_pa_args(tmp_path, p, method="wsum"))
    out = ad.read_h5ad(tmp_path / "out.h5ad")
    assert out.n_obs == 1
    assert out.uns["pathway_analysis"]["n_dropped_empty_obs"] == 1


def test_f06_single_observation_report_is_strict_json(tmp_path, monkeypatch):
    monkeypatch.setattr(PA.dc.op, "progeny", lambda organism=None, top=100: _NET, raising=False)
    p = _write(tmp_path, [[1.0, 2.0, 3.0]], ["g0", "g1", "g2"], ["c0"])
    result = PA.run_decoupler_pathway_activity(_pa_args(tmp_path, p, method="wsum"))
    json.dumps(result, allow_nan=False)  # must not raise (no NaN std)


def _unified_parser():
    """The real unified CLI parser (not a source-text grep)."""
    import argparse
    import aose_omics_runtime.__main__ as m

    # main() builds the parser then parses argv; rebuild it here by parsing a
    # known-good argv and catching the dispatch, so we inspect the true schema.
    import contextlib
    import io
    holder = {}
    real_parse = argparse.ArgumentParser.parse_args

    def capture(self, *a, **k):
        holder.setdefault("parser", self)
        raise SystemExit(0)

    argparse.ArgumentParser.parse_args = capture
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.suppress(SystemExit):
            m.main()
    finally:
        argparse.ArgumentParser.parse_args = real_parse
    return holder["parser"]


def _reject(parser, argv):
    """True if the real parser rejects argv."""
    import contextlib
    import io
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            parser.parse_args(argv)
            return False
        except SystemExit:
            return True


def test_f07b_unified_cli_rejects_gsea_enrichment():
    # Assert against the REAL parser, not a source-string grep: GSEA needs ranked
    # scores, which this subcommand's schema cannot express, so it must be rejected.
    parser = _unified_parser()
    assert _reject(parser, ["enrichment", "--gene-list", "A", "--output", "o.json",
                            "--method", "gsea"])
    assert not _reject(parser, ["enrichment", "--gene-list", "A", "--output", "o.json",
                                "--method", "ora"])


def test_f03_unified_cli_rejects_use_raw_with_layer():
    parser = _unified_parser()
    assert _reject(parser, ["pathway_activity", "--adata", "a.h5ad", "--output", "o.h5ad",
                            "--use-raw", "--layer", "counts"])


def test_f03_standalone_parsers_also_reject_use_raw_with_layer():
    # The standalone module parsers must carry the same exclusivity as the unified CLI.
    # Run them as real subprocesses so this asserts the shipped CLI, not an in-process shim.
    import subprocess
    import sys
    for mod, argv in [
        ("aose_omics_runtime.functional.decoupler_pathway_activity",
         ["--adata", "a", "--output", "o", "--use-raw", "--layer", "counts"]),
    ]:
        r = subprocess.run([sys.executable, "-m", mod] + argv, capture_output=True, text=True)
        assert r.returncode != 0, f"{mod} accepted --use-raw with --layer"
        assert "not allowed with" in r.stderr, r.stderr[-200:]


def test_f02_provenance_records_real_decoupler_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(PA.dc.op, "progeny", lambda organism=None, top=100: _NET, raising=False)
    p = _write(tmp_path, [[1.0, 2.0, 3.0], [2.0, 1.0, 0.0]], ["g0", "g1", "g2"], ["c0", "c1"])
    PA.run_decoupler_pathway_activity(_pa_args(tmp_path, p, method="wsum"))
    uns = ad.read_h5ad(tmp_path / "out.h5ad").uns["pathway_analysis"]
    assert uns["method"] == "wsum"
    assert uns["decoupler_backend"] == "dc.mt.waggr"   # the real backend, not zscore
    assert uns["decoupler_fun"] == "wsum"
    assert uns["score_key"] == "score_waggr"
