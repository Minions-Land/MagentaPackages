# Non-Standard Environments — provisioning packages outside `task1–4`

Read this whenever an analysis needs a package that is **not** in the pinned
`task1–4` envs: a **PARTIAL / REFERENCE** method (MultiVelo, SpaGCN, cell2location,
pySCENIC/SCENIC+, scArches, gseapy, lifelines, scirpy, gwaslab …) **or any package
the user explicitly names**. This is the operational how-to for standing that
environment up **reproducibly and in isolation** — never by polluting `task1–4`
or `base`.

## The environment you build belongs to the analysis, not to the package

AutOmicScience is normally **installed**, not checked out: the harness downloads a
release archive, verifies its SHA-256, and extracts it to
`~/.magenta/harness-packages/…`. When the version or origin no longer matches, the host
**deletes that directory wholesale** and re-downloads it.

So `tools/omics-environment/pixi.toml` is not yours to edit during an analysis. An env you
add there looks fine today and is **gone** after the next package fetch — silently, with no
error, taking your dependency declaration with it. It also entangles a one-off dependency
with the package's published lock, and detaches the package from its provenance record.

Build the environment **next to your analysis outputs** instead. It then lives as long as
the analysis does, travels with it, and is reproducible from its own lock.

## One workflow, one environment

A workflow whose steps are **partly pinned and partly PARTIAL still needs a single
provisioned env for the whole thing** — not `task1` for some steps and a side env for the
rest. Microbiome is the worked example: loading and CLR run on scipy/pandas, DESeq2 on
pydeseq2, but diversity needs `scikit-bio` and per-taxon Cox needs `lifelines`, neither of
which is in `task1–4`. Splitting that across two envs means writing intermediates to disk
and re-reading them in the other interpreter, and the two halves can silently disagree on
library versions.

Build **one** env that has the stack you import **plus** the extras, and run every step
there. Reading an `.h5ad` that `omics_compute` produced in `task1` is fine — that is a file
hand-off, not a split workflow.

## Decision flow

```
Need a package not in the modality env?
│
├─ Already importable in the task env?  → yes: just use it (you're done).
│
├─ One-off exploration, nothing to reproduce?
│      → `pixi exec --spec <pkg> --spec scanpy -- python probe.py`
│        (ephemeral, not in any lock — record the resolved versions yourself)
│
├─ A real analysis that must reproduce?
│      → a task-owned Pixi env, below.        ← the default
│
├─ Pixi can't do it? (Julia · a specific CUDA build · source builds · solve fails)
│      → a named conda env, below.
│
└─ You are developing AutOmicScience itself and want this to become a
   permanent package capability?
       → editing the package manifest, below — needs the user's say-so.
```

## A task-owned Pixi environment (the default)

Write a `pixi.toml` **beside your analysis outputs** and declare what you import. Put it at
the analysis root and `pixi run` finds it by itself — no `--manifest-path` needed.

```toml
# ~/analysis/spagcn-domains/pixi.toml
[workspace]
name = "spagcn-domains"
channels = ["conda-forge", "bioconda"]   # bioconda only if you actually need it
platforms = ["linux-64"]                 # your machine's platform; adding one you are not
                                         # on makes the solve satisfy both, and fails if the
                                         # package has no build for it

[dependencies]
scanpy = "*"        # pulls pandas / numpy / scipy transitively — declare what you import,
h5py = "*"          # not every transitive dependency

[pypi-dependencies]
SpaGCN = "*"
torch = "*"
```

```bash
cd ~/analysis/spagcn-domains
pixi lock                       # solve → writes pixi.lock
pixi install --locked           # materialise exactly what the lock says
pixi run --frozen python spagcn_domains.py
```

**Provision the method's real package — don't skip it and hand-roll a substitute in its place.**
Writing your own approximation of a PARTIAL / REFERENCE method and reporting it as that method is
exactly the failure this document exists to prevent. (A package that genuinely *cannot* be
provisioned is a different case — a blocker to report, per "Fail loud on absence" below.) If you do
legitimately run a different method, name it as what it is in the `report`, never as the method you
did not run.

**Declare what you import, not a copy of `task1`.** The solver brings in transitive
dependencies: `scanpy` gets you pandas, numpy and scipy. There is no list to reproduce and
nothing to look up.

You may end up on different versions than `task1–4` — that is expected and usually
harmless, because the whole workflow runs in this one env and data crosses env boundaries
as `.h5ad`/`.h5mu`/Zarr, not as live objects. If you *do* want to match a task env, ask
`omics_environment` what it declares (`dependencies`, `pypi_dependencies`, `channels`) and
pin accordingly — useful occasionally, not a required step.

## A named conda env (when Pixi can't)

Reach for conda **only** when Pixi genuinely can't: the Julia ecosystem, a specific CUDA
build, a source build, or a solve Pixi can't satisfy. Always a **named** env — never
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

conda envs are in **no** lock → not automatically reproducible. Record exactly what you
installed (see Hard rules).

## Editing the package's own manifest (package development only)

**Only** when you are developing AutOmicScience itself — i.e. the harness is pointed at a
local checkout with `--harness-packages-root`, this is a git working tree, and the user has
asked for the capability to become a permanent part of the package. In an ordinary analysis
this route does not apply; the edit would be discarded (see the top of this doc).

Here you add a **feature + environment with its own `solve-group`** to
`tools/omics-environment/pixi.toml`, and the change is reviewed, locked and released like
any other package change:

```toml
[feature.spagcn.pypi-dependencies]
SpaGCN = "*"
torch = "*"

[environments]
spagcn = { features = ["core", "singlecell", "spagcn"], solve-group = "spagcn" }
```

**Compose `core` *and* `singlecell`, the way `task1–4` do** — every one of them is
`{ features = ["core", "singlecell", ...] }`. The names mislead: `core` is only
jupyterlab + h5py + mudata + the spreadsheet/BAM readers, while the analysis stack you
actually import (scanpy, and through it pandas / numpy / scipy, plus decoupler and
pydeseq2) lives in **`singlecell`**. An env built as `["core", "spagcn"]` has no pandas and
no scipy, so a script that touches anything beyond the new package fails on its first
import. The dedicated `solve-group` is what keeps its pins from ever touching `task1–4`.

This trap is specific to composing features. A task-owned env declares packages directly,
so it does not arise there.

## Hard rules

- **Never install to `base`, never use the base env.** The machine's `$PATH`
  `python`/`pip` may point at conda `base`; a bare `pip install …` pollutes base
  and can downgrade its `pandas`/`scipy`. Every install goes into an environment you
  declared — a task-owned `pixi.toml`, or `conda create -n aose-<tool>`.
- **Never add a conflicting package to `task1–4`.** Isolate it (a task-owned env, or a
  separate conda env).
- **Never edit an installed package's `pixi.toml` / `pixi.lock`.** They are part of a
  checksum-verified artifact the host may delete and re-fetch at any time, so the edit is
  lost silently. *Exception — materialised environments:* `omics_install_env` writing
  `.pixi/envs/` into the package tree is fine and expected. The test is **rebuildability**:
  `.pixi/` regenerates from the committed lock with one command, so losing it costs a
  reinstall; a manifest edit is a *declaration* and losing it costs your intent. Apply that
  test to anything else you are tempted to write into a package.
- **Run through the environment, never at its interpreter.** `pixi run --frozen …` from the
  directory holding your `pixi.toml` (add `-e <env>` only if you declared named environments), or
  `conda run -n <env> …` — never `.pixi/envs/<env>/bin/python` directly. Executing the
  interpreter by path skips activation, and the shell's own variables survive: `$PATH` still
  leads with the host's `bin`, so a subprocess (R, macs3, samtools) silently resolves to the
  wrong binary; `PIXI_ENVIRONMENT_NAME` is absent; and `CONDA_PREFIX` keeps pointing at
  **whatever conda env the calling shell had active** — not this env, and not necessarily
  `base` either. Anything that locates resources through it (rpy2 → `R_HOME`, GDAL, SSL
  certs) then reads from an unrelated environment. A wrong value is worse than a missing one:
  nothing errors. Plain Python imports still work (`sys.prefix` is derived from the
  interpreter's own path), which is why this stays hidden until something shells out.
- **Record provisioning in the `report`.** For a task-owned env, note its path (its lock
  pins the versions). For a conda env or `pixi exec` (in no lock), record the exact tool +
  versions and say plainly it was external and non-locked — so the run stays auditable.
- **Fail loud on absence.** A package that can be neither imported nor provisioned
  (offline, no GPU, unsolvable) is a **blocker with the install command**, never a
  silent fallback to a different method.
- **Preflight doesn't cover these.** `omics_preflight` only validates `task1–4`;
  after provisioning, sanity-check the import yourself
  (`pixi run --frozen python -c "import <pkg>"` or `conda run -n <env> …`).

`pixi install --locked` refuses a lock that has drifted from the manifest, so `pixi lock`
first whenever you change dependencies.
