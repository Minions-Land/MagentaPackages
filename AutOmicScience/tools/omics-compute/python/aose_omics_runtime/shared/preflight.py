"""omics_preflight — verify the active Pixi environment is ready for a modality.

Ported from BioAgent AutOmicScience (crates/aose-tools/src/omics_typed.rs).

Key property preserved: this runs *inside* the per-modality isolated Pixi
environment (the harness launcher selects it via --environment <env>), so
`import <pkg>` here probes the exact interpreter that will run the analysis.
A green preflight therefore guarantees no ModuleNotFoundError at run time —
which a `pixi install --dry-run` lockfile check cannot promise.

Emits a single JSON object on stdout: {ready, modality, pythonBin,
blocker?, fix?, missingPackages?, gpuAvailable?, packages?}.
"""

import importlib
import json
import os
import shutil
import sys

# modality -> required import names. Append-only; kept in lockstep with the
# pixi.toml features and the modality->env table in omics-compute.toml.
# Include the packages the STANDARD/default subcommands of each modality import
# (e.g. seurat_v3 HVG -> skmisc, default integrate -> harmonypy), so a green
# preflight covers the default workflow — not just the loader deps. Optional,
# non-default methods (e.g. scanorama) fail loud at their call site.
# (functional subcommands have no isolated modality env; their dep — decoupler —
# fails loud at import.)
MODALITY_REQUIREMENTS = {
    "scrna": ["anndata", "scanpy", "scvi", "leidenalg", "igraph", "skmisc", "harmonypy"],
    "spatial": ["anndata", "scanpy", "squidpy", "spatialdata"],
    "scatac": ["anndata", "scanpy", "muon", "snapatac2"],
    "multiome": ["anndata", "scanpy", "muon", "mudata"],
}

# modality -> the isolated env id it should run in (for fix hints only; the
# harness launcher already selected the env). Mirrors omics-compute.toml.
MODALITY_ENV = {
    "scrna": "task1",
    "spatial": "task2",
    "scatac": "task4",
    "multiome": "task3",
}

# Reverse map: active Pixi env id -> modality. Lets preflight recover the
# modality from PIXI_ENVIRONMENT_NAME when the launcher stripped --modality
# (it uses that arg to select the env, then drops it from argv).
ENV_MODALITY = {env: modality for modality, env in MODALITY_ENV.items()}

# Requirements contributed by a specific subcommand — and by the --method chosen
# within it — on top of the modality baseline, plus any external executable the
# subcommand shells out to. A modality list alone cannot express these, so a green
# modality preflight could still be followed by a ModuleNotFoundError (e.g.
# `integrate --method scanorama`). Passing --subcommand/--method makes a green
# preflight mean "this exact request can run".
SUBCOMMAND_REQUIREMENTS = {
    "preprocess": {"packages": ["skmisc"]},                       # default seurat_v3 HVG
    "integrate": {"methods": {"harmony": ["harmonypy"], "scanorama": ["scanorama"]}},
    # snapATAC2 drives MACS3 as a library (`from MACS3.Signal.PeakDetect import PeakDetect`),
    # so the importable package is the requirement — not the `macs3` executable on PATH.
    "peak_calling": {"packages": ["MACS3"]},
    "atac_qc": {"packages": ["snapatac2"]},
    "gene_activity": {"packages": ["snapatac2"]},
    "pathway_activity": {"packages": ["decoupler"]},
    "enrichment": {"packages": ["decoupler"]},
    "score": {"packages": ["sklearn"]},
}


def _executable_available(name: str) -> bool:
    """True if `name` resolves on PATH (external binaries preflight must cover)."""
    return shutil.which(name) is not None


def _requirements_for(modality, subcommand, method):
    """(packages, executables) this exact request needs: modality baseline plus the
    subcommand's own imports and its selected method's dependency."""
    packages = list(MODALITY_REQUIREMENTS.get(modality) or [])
    spec = SUBCOMMAND_REQUIREMENTS.get(subcommand, {})
    packages += spec.get("packages", [])
    if method:
        packages += spec.get("methods", {}).get(method, [])
    return list(dict.fromkeys(packages)), list(spec.get("executables", []))


def _module_importable(name: str) -> bool:
    """True if `import name` succeeds."""
    try:
        importlib.import_module(name)
        return True
    except Exception:
        # A parent package that raises on import surfaces here → treat as missing.
        return False


def _gpu_available() -> bool:
    """GPU probe: torch.cuda first (scvi/scANVI path), rapids fallback."""
    try:
        import torch

        if bool(torch.cuda.is_available()):
            return True
    except Exception:
        pass
    return _module_importable("rapids_singlecell")


def main(args):
    active_env = os.environ.get("PIXI_ENVIRONMENT_NAME")
    # Prefer the explicit flag; otherwise recover the modality from the active
    # Pixi environment the launcher selected.
    modality = args.modality or ENV_MODALITY.get(active_env)
    required = MODALITY_REQUIREMENTS.get(modality)
    if required is None:
        print(
            json.dumps(
                {
                    "ready": False,
                    "modality": modality,
                    "activeEnv": active_env,
                    "pythonBin": sys.executable,
                    "blocker": (
                        f"Unknown modality: {args.modality}"
                        if args.modality
                        else f"Could not resolve modality from active env {active_env!r}"
                    ),
                    "fix": "Use one of: " + ", ".join(sorted(MODALITY_REQUIREMENTS)),
                }
            )
        )
        return

    env_id = MODALITY_ENV.get(modality)
    # `for_subcommand`, not `subcommand`: the unified CLI already uses the latter
    # dest for the top-level subparser.
    subcommand = getattr(args, "for_subcommand", None)
    method = getattr(args, "method", None)
    required, executables = _requirements_for(modality, subcommand, method)

    missing = [pkg for pkg in required if not _module_importable(pkg)]
    missing_exe = [exe for exe in executables if not _executable_available(exe)]
    gpu_available = _gpu_available() if getattr(args, "check_gpu", False) else None

    result = {
        "modality": modality,
        "subcommand": subcommand,
        "method": method,
        "pythonBin": sys.executable,
        "activeEnv": active_env,
    }
    if gpu_available is not None:
        result["gpuAvailable"] = gpu_available

    if missing or missing_exe:
        result["ready"] = False
        if missing:
            result["missingPackages"] = missing
        if missing_exe:
            result["missingExecutables"] = missing_exe
        scope = f"{modality}/{subcommand}" if subcommand else modality
        result["blocker"] = f"Environment missing requirements for {scope}: " + ", ".join(
            missing + [f"{e} (executable)" for e in missing_exe]
        )
        if env_id:
            result["fix"] = (
                f"Reinstall the Pixi '{env_id}' environment:\n"
                f"  pixi install --manifest-path pixi.toml -e {env_id}\n"
                "If packages are still missing, add them to pixi.toml, then "
                f"`pixi lock` and `pixi install -e {env_id}`."
            )
        else:
            result["fix"] = (
                "Install the required packages into the active Pixi environment; "
                "missing imports: " + " ".join(missing)
            )
    else:
        result["ready"] = True
        result["packages"] = required
        if executables:
            result["executables"] = executables

    print(json.dumps(result))
