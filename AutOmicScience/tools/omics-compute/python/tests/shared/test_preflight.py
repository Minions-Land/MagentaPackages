"""
Tests for preflight.py — the omics_preflight readiness probe.

preflight.main() runs inside a modality's isolated Pixi env and emits a single
JSON object describing readiness. These tests exercise its pure decision logic
(modality resolution, missing-package detection, GPU gating, error paths) by
faking the import/GPU probes and capturing stdout — no real env needed.
"""

import json
import types

import pytest

from aose_omics_runtime.shared import preflight


def _args(modality=None, check_gpu=False):
    """Mimic the argparse.Namespace preflight.main() receives."""
    return types.SimpleNamespace(modality=modality, check_gpu=check_gpu)


def _run(capsys, args, monkeypatch, *, importable=lambda name: True, gpu=False, active_env=None):
    """Run main() with faked probes and return the parsed JSON result."""
    monkeypatch.setattr(preflight, "_module_importable", importable)
    monkeypatch.setattr(preflight, "_gpu_available", lambda: gpu)
    if active_env is None:
        monkeypatch.delenv("PIXI_ENVIRONMENT_NAME", raising=False)
    else:
        monkeypatch.setenv("PIXI_ENVIRONMENT_NAME", active_env)
    preflight.main(args)
    out = capsys.readouterr().out.strip()
    return json.loads(out)


def test_modality_env_and_requirements_stay_in_lockstep():
    """Every modality with an env must also declare required packages."""
    assert set(preflight.MODALITY_ENV) == set(preflight.MODALITY_REQUIREMENTS)
    # Reverse map must round-trip (no two modalities share an env id).
    assert preflight.ENV_MODALITY == {
        env: mod for mod, env in preflight.MODALITY_ENV.items()
    }
    assert len(preflight.ENV_MODALITY) == len(preflight.MODALITY_ENV)


@pytest.mark.parametrize(
    "modality,env",
    [("scrna", "task1"), ("spatial", "task2"), ("scatac", "task4"), ("multiome", "task3")],
)
def test_modality_env_mapping(modality, env):
    """Modality->env table matches the descriptor's declared mapping."""
    assert preflight.MODALITY_ENV[modality] == env


def test_ready_when_all_packages_importable(capsys, monkeypatch):
    result = _run(capsys, _args(modality="scrna"), monkeypatch, importable=lambda n: True)
    assert result["ready"] is True
    assert result["modality"] == "scrna"
    assert result["packages"] == preflight.MODALITY_REQUIREMENTS["scrna"]
    assert "blocker" not in result
    assert "missingPackages" not in result
    # GPU not requested -> field omitted entirely.
    assert "gpuAvailable" not in result


def test_missing_packages_block_with_fix_hint(capsys, monkeypatch):
    # squidpy missing for spatial.
    result = _run(
        capsys,
        _args(modality="spatial"),
        monkeypatch,
        importable=lambda n: n != "squidpy",
    )
    assert result["ready"] is False
    assert result["missingPackages"] == ["squidpy"]
    assert "squidpy" in result["blocker"]
    # Fix hint must reference the modality's isolated env (task2).
    assert "task2" in result["fix"]


def test_modality_derived_from_active_env_when_flag_absent(capsys, monkeypatch):
    """Launcher strips --modality; main() recovers it from PIXI_ENVIRONMENT_NAME."""
    result = _run(
        capsys,
        _args(modality=None),
        monkeypatch,
        importable=lambda n: True,
        active_env="task4",
    )
    assert result["modality"] == "scatac"
    assert result["ready"] is True
    assert result["activeEnv"] == "task4"


def test_unknown_modality_flag_errors(capsys, monkeypatch):
    result = _run(capsys, _args(modality="bogus"), monkeypatch)
    assert result["ready"] is False
    assert "Unknown modality" in result["blocker"]
    assert "bogus" in result["blocker"]


def test_unresolvable_env_errors(capsys, monkeypatch):
    """No flag and an unrecognized active env -> loud, actionable failure."""
    result = _run(
        capsys,
        _args(modality=None),
        monkeypatch,
        active_env="not-a-task-env",
    )
    assert result["ready"] is False
    assert "not-a-task-env" in result["blocker"]


def test_gpu_probe_included_only_when_requested(capsys, monkeypatch):
    ready_gpu = _run(
        capsys, _args(modality="scrna", check_gpu=True), monkeypatch, gpu=True
    )
    assert ready_gpu["gpuAvailable"] is True

    no_gpu = _run(
        capsys, _args(modality="scrna", check_gpu=True), monkeypatch, gpu=False
    )
    assert no_gpu["gpuAvailable"] is False


# --- Regression: preflight must cover the exact request, not just the modality (S08/R01) ---

def test_requirements_narrow_to_subcommand_and_method():
    from aose_omics_runtime.shared.preflight import _requirements_for

    # A method's dependency is only required when that method is chosen.
    pkgs, _ = _requirements_for("scrna", "integrate", "scanorama")
    assert "scanorama" in pkgs
    pkgs, _ = _requirements_for("scrna", "integrate", "harmony")
    assert "harmonypy" in pkgs and "scanorama" not in pkgs

    # peak_calling drives MACS3 through snapATAC2 as a library, so the requirement is the
    # importable package — an env with MACS3 installed but no `macs3` on PATH is ready.
    pkgs, exes = _requirements_for("scatac", "peak_calling", None)
    assert "MACS3" in pkgs and exes == []

    # Modality-only stays the baseline (no method/executable requirements invented).
    pkgs, exes = _requirements_for("scrna", None, None)
    assert exes == [] and "scanorama" not in pkgs
    assert set(preflight.MODALITY_REQUIREMENTS["scrna"]).issubset(pkgs)


def test_missing_method_dependency_makes_preflight_red(monkeypatch):
    import argparse

    # scanorama absent, everything else present -> modality-only would be green,
    # but the scanorama request must be red.
    monkeypatch.setattr(preflight, "_module_importable", lambda n: n != "scanorama")
    monkeypatch.setattr(preflight, "_executable_available", lambda n: True)

    out = []
    monkeypatch.setattr("builtins.print", lambda s: out.append(s))
    preflight.main(argparse.Namespace(modality="scrna", for_subcommand="integrate",
                                      method="scanorama", check_gpu=False))
    import json
    report = json.loads(out[-1])
    assert report["ready"] is False
    assert report["missingPackages"] == ["scanorama"]
