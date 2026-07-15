# Non-Standard Environments — provisioning packages outside `task1–4`

Read this whenever an analysis needs a package that is **not** in the pinned
`task1–4` envs: a **PARTIAL / REFERENCE** method (MultiVelo, SpaGCN, cell2location,
pySCENIC/SCENIC+, scArches, gseapy, lifelines, scirpy, gwaslab …) **or any package
the user explicitly names**. This is the operational how-to for standing that
environment up **reproducibly and in isolation** — never by polluting `task1–4`
or `base`.

## One workflow, one environment

A workflow whose steps are **partly pinned and partly PARTIAL still needs a single provisioned env
for the whole thing** — not `task1` for some steps and a side env for the rest. Microbiome is the
worked example: loading and CLR run on pinned scipy/pandas, DESeq2 on pinned pydeseq2, but diversity
needs `scikit-bio` and per-taxon Cox needs `lifelines`, neither of which is in `task1–4`. Splitting
that across two envs means writing intermediates to disk and re-reading them in the other
interpreter, and the two halves can silently disagree on library versions.

Build one env that composes the pinned stack **plus** the extras (§A), and run every step there. The
pinned features are the same objects `task1–4` compose, so you are not duplicating anything — you are
adding to them under a separate solve-group.

## Rule of thumb

`task1–4` already covers the standard analysis stack. For anything else:

1. **First choice — a new Pixi environment** (reproducible, recorded in
   `pixi.lock`, isolated solve-group so it never disturbs `task1–4`).
2. **Fall back to a named conda env** only when **Pixi can't do it** — Julia
   toolchains, complex GPU/CUDA stacks, non-conda/PyPI builds, or a solve that
   Pixi simply can't satisfy.

Never install to `base`. Never add a version-conflicting package to `task1–4`.

## Decision flow

```
Need a package not in the modality env?
│
├─ Is it already importable in the task env?  → yes: just use it (you're done).
│
└─ no → Can Pixi provision it? (a conda-forge / PyPI package, standard build,
        solvable pins)
        │
        ├─ YES → §A  New Pixi environment (preferred)
        │
        └─ NO  (Julia · complex GPU/CUDA · non-standard build · Pixi solve fails)
               → §B  Named conda env (fallback)
```

When in doubt, **try §A first**; if `pixi install`/`pixi lock` fails to solve
(e.g. a hard old pin that can't coexist with the reader packages), drop to §B.

## §A — New Pixi environment (preferred, reproducible)

Add a **feature + environment with its own `solve-group`** to the workspace
manifest `tools/omics-environment/pixi.toml`. The dedicated solve-group is what
keeps its pins from ever touching `task1–4`.

```toml
# tools/omics-environment/pixi.toml  — e.g. a SpaGCN env (coexists fine; needs PyTorch)
[feature.spagcn.pypi-dependencies]
SpaGCN = "*"
torch = "*"

[environments]
spagcn = { features = ["core", "singlecell", "spagcn"], solve-group = "spagcn" }
```

**Compose `core` *and* `singlecell`, the way `task1–4` do** — every one of them is
`{ features = ["core", "singlecell", ...] }`. The names are misleading: `core` is only
jupyterlab + h5py + mudata, while the analysis stack you actually import (scanpy, and through it
pandas / numpy / scipy, plus decoupler and pydeseq2) lives in **`singlecell`**. An env built as
`["core", "spagcn"]` has no pandas and no scipy, so a script that touches anything beyond the new
package fails on its first import.

Then provision and run (resolve `--manifest-path` from the package root):

```bash
pixi install --manifest-path tools/omics-environment/pixi.toml -e spagcn
pixi lock    --manifest-path tools/omics-environment/pixi.toml        # updates pixi.lock
pixi run     --manifest-path tools/omics-environment/pixi.toml -e spagcn python spagcn_domains.py
```

- **Isolated `solve-group`** → its versions are solved independently; `task1–4`
  are untouched even if this env pins older/heavier deps.
- **In `pixi.lock`** → the env is reproducible like `task1–4`.
- **One-off / don't want to edit the manifest?** use `pixi exec` for an ephemeral
  env: `pixi exec --spec SpaGCN --spec scanpy -- python spagcn_domains.py`
  (not recorded in the lock — record versions yourself, see Hard rules).

Use §A for PARTIAL/REFERENCE methods whose packages are conda-forge/PyPI and
solvable: SpaGCN, cell2location, Tangram, pySCENIC, gseapy, lifelines, scirpy,
gwaslab, and most user-named Python packages.

## §B — Named conda env (fallback: what Pixi can't do)

Reach for conda **only** when §A can't apply. Always a **named** env — never
`base`, never a `task` env.

```bash
# Julia toolchain (Pixi manages conda/PyPI, not the Julia Pkg ecosystem):
conda create -y -n aose-julia -c conda-forge julia
conda run -n aose-julia julia --project=. -e 'using Pkg; Pkg.instantiate()' 
conda run -n aose-julia julia analysis.jl

# Complex GPU/CUDA stack (specific cudatoolkit + framework matching is cleaner on conda):
conda create -y -n aose-gpu -c conda-forge -c nvidia python=3.10 pytorch pytorch-cuda=12.1
conda run -n aose-gpu pip install <the GPU tool>
conda run -n aose-gpu python gpu_run.py

# A hard version-isolated method Pixi couldn't solve (e.g. MultiVelo's old pins):
conda create -y -n aose-multivelo python=3.10
conda run -n aose-multivelo pip install multivelo scvelo "pandas<=1.4.4" "scipy<1.14" "matplotlib<3.8"
conda run -n aose-multivelo python multivelo_run.py
```

conda envs are **not** in `pixi.lock` → not automatically reproducible. Record
exactly what you installed (see Hard rules).

## Which route for which need

| Need | Route |
|------|-------|
| PARTIAL/REFERENCE conda-forge/PyPI method, solvable (SpaGCN, cell2location, pySCENIC, gseapy, lifelines, scirpy, gwaslab) | **§A** new Pixi env |
| User-named arbitrary Python package | **§A** if Pixi solves it, else **§B** |
| **Julia** toolchain / Julia packages | **§B** conda |
| **Complex GPU / specific CUDA** stack | **§B** conda |
| Non-standard build (source compile, system libs) or Pixi solve **fails** | **§B** conda |

## Hard rules (both routes)

- **Never install to `base`, never use the base env.** The machine's `$PATH`
  `python`/`pip` may point at conda `base`; a bare `pip install …` pollutes base
  and can downgrade its `pandas`/`scipy`. Always a **named** env
  (`-e <pixi env>` or `conda create -n aose-<tool>`).
- **Never add a conflicting package to `task1–4`.** Isolate it (own Pixi
  solve-group in §A, or a separate conda env in §B).
- **Record provisioning in the `report`.** For §A, note the env name (it's in the
  lock). For §B (not in the lock), record the exact tool + versions installed and
  state plainly it was an external, non-locked env — so the run stays auditable.
- **Fail loud on absence.** A package that can be neither imported nor provisioned
  (offline, no GPU, unsolvable) is a **blocker with the install command**, never a
  silent fallback to a different method.
- **Preflight doesn't cover these.** `omics_preflight` only validates `task1–4`;
  after provisioning a §A/§B env, sanity-check the import yourself
  (`pixi run -e <env> python -c "import <pkg>"` or `conda run -n <env> …`).
