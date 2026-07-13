# MagentaWithPantheonOS

`MagentaWithPantheonOS` is a schema-v2, HCP-isomorphic package that brings the
small set of execution tools expected by PantheonOS-derived scientific skills
to Magenta. Version `0.1.0` exposes four model-visible tools:

| Tool | Contract |
|---|---|
| `run_python` | Run code in a new Python subprocess for every call and return `stdout`, `stderr`, and `exitCode`. |
| `create_notebook` | Atomically create an nbformat 4.5 notebook. |
| `add_cell` | Atomically append or insert a code, Markdown, or raw cell with a stable id. |
| `observe_figure` | Pixel-preflight an image, then obtain a validated PASS/WARN/FAIL from a controlled Magenta CLI vision evaluator. |

## Load

Load the bridge alone for tool development:

```bash
magenta --harness-package MagentaWithPantheonOS
```

Normal PantheonOS workflows load both packages in the same session:

```bash
magenta --harness-package PantheonOS --harness-package MagentaWithPantheonOS
```

After public release, the versioned selectors are:

```bash
magenta \
  --harness-package github:Minions-Land/Magenta-CLI/PantheonOS@0.1.0 \
  --harness-package github:Minions-Land/Magenta-CLI/MagentaWithPantheonOS@0.1.0
```

The host builds every package Tool through the injected
`HcpClientbuildtools` hook. The four real package `HcpMagnet` Sources retain
`source = "MagentaWithPantheonOS"` and wrap the host-created tools through
`toTool()`.

## Runtime

All tools use the shared `magenta_with_pantheon_runtime` Python component and
the locked wrapper Pixi environment in `tools/run-python/`. Each model call
starts a fresh `python -m ...` process through Magenta. `run_python` starts one
further fresh interpreter for the supplied code and never retains globals,
imports, or other interpreter state between calls. The default timeout is 60
seconds. A timeout kills the spawned process group, returns `exitCode = -1`,
and appends `[Process killed: timeout after Nms]` to `stderr`.

`run_python.env` is a Pixi environment selector, not an operating-system
environment overlay. Omitted or `default` uses the package's locked wrapper
runtime. Any named selector is resolved against the current project/workspace
`pixi.toml` and requires its adjacent `pixi.lock`. When no literal environment
with the selector exists, aliases resolve `sc-rna` to `task1`, `spatial` to
`task2`, `sc-multiome` to `task3`, and `sc-atac` to `task4`. Missing manifests,
locks, and environment names fail loudly. The package does not pretend its
lightweight wrapper contains project omics dependencies. Inline `code` and cell
`source` are capped at 16,000 characters for Windows/POSIX argv portability;
larger programs should be saved as scripts and invoked by a short loader.

Notebook writes use a persistent adjacent OS file lock, a same-directory
temporary file, `fsync`, and atomic publication. Create-only publication uses a
hard link so an external writer cannot be overwritten between the existence
check and publish step. Existing notebook symlinks are rejected.
When supplied, `title` is stored in metadata and added as the first Markdown
cell. New cells receive deterministic, collision-resistant ids and all output
is validated as nbformat 4.5 before replacement.

## Figure vision path

`observe_figure` first opens the file with Pillow and rejects unreadable, empty,
fully transparent, effectively uniform, and over-16-megapixel images before
large pixel buffers are allocated. It then creates a bounded PNG preview and
invokes an ephemeral evaluator:

```bash
magenta --print --no-session --no-extensions --no-skills \
  --no-prompt-templates --no-context-files --thinking low --no-tools --no-approve \
  --system-prompt <strict-one-line-qc-prompt> @<preview.png> <question>
```

The evaluator must return exactly one `PASS:`, `WARN:`, or `FAIL:` line whose
reason contains at least two semicolon-separated image-visible details. Empty
output, extra protocol text, malformed output, text-only-model
responses, attachment placeholders, unavailable credentials, missing CLI,
recursion, timeout, or nonzero exit all make the package tool exit nonzero with
`VISION_UNAVAILABLE`. They are never converted into a semantic `WARN` or a fake
`PASS`. Successful results set `visionBacked = true`, return the AOSE-compatible
top-level fields `verdict` (the bare enum), `analysis`, `file_path`, and `model`,
and include deterministic pixel metrics. The evaluator receives the preview as
a direct image attachment with no tools, and the global default provider/model
are pinned on the child command so `model` reports actual provenance. The reason
is never concatenated into `verdict`.

## Development

```bash
cd tools/run-python
pixi run test

cd /path/to/MagentaPackages
python3 scripts/validate_packages.py --package MagentaWithPantheonOS
```

The runtime is derived from the execution and notebook semantics in PantheonOS,
while remaining dependency-light and relocatable inside Magenta's package
cache.
