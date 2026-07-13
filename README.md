# Magenta Packages

This repository holds Magenta harness overlay packages — domain, brand, and
harness bundles that extend Magenta with domain-specific skills and tools. It is
maintained as a standalone repository, independent of the core Magenta codebase,
so these domain packages can evolve on their own cadence without touching the
coding-agent framework.

A package is a domain, brand, or harness bundle with a root `package.toml`.
Selecting a package loads the components it declares (skills, tools, system
prompts, brand, runtime). Selection names packages — it never loads arbitrary
external paths. Packages that carry many skills expose optional **profiles** so
a session can pull in a focused subset.

## Package layout (schema v2: HCP-isomorphic)

A package is an externalized slice of the Magenta HarnessComponentProtocol
tree. Its on-disk shape mirrors the host exactly: every module has a real
`HcpServer.ts`, and every contributed source lives at `<module>/<source>/`
with a real `HcpMagnet.ts` beside its descriptor or content.

```text
<package-root>/
  package.toml                 # schema_version = magenta.package.v2, version, source
  skills/<skill>/
    HcpServer.ts               # bare class: real Server for this module
    <source>/                  # source = package name (single-source package)
      HcpMagnet.ts             # static build + module/kind/source + toResource
      SKILL.md
  tools/<tool>/
    HcpServer.ts
    <source>/
      HcpMagnet.ts             # Client-built product wrapper + toTool()
      <tool>.toml
  brand/HcpServer.ts , system-prompt/HcpServer.ts
  brand/<source>/ , system-prompt/<source>/   # resource magnets
```

The `source` segment is the package name. A **merge package** aggregating
multiple upstreams would add sibling `<module>/<other-source>/` directories,
each with its own `HcpMagnet`. Each Server and Magnet is a bare class (HCP
spec §2, no imported interface). Each Magnet resolves its own content path relative to itself via
`import.meta.url`, so the package is relocatable when downloaded into the local
cache. The runtime magnet loader imports each `HcpMagnet.ts`, validates the
shape (static `build`, `module`/`kind`/`source`, and the matching
`toTool`/`toCapability`/`toResource` product method), and registers it into the
same `HcpClient` as built-in magnets.

A manifest may offer the same `kind:name` from different Sources; only an exact
duplicate `kind:name:source` is invalid. Source selection resolves those offers
before the session overlay applies its final `kind:name` precedence.

## Loading a package

```bash
# Load an entire package
magenta --harness-package AutOmicScience

# Load only selected profiles (comma-separated, package-defined)
magenta --harness-package ClaudeScience:structure,design

# Combine PantheonOS skills with their execution tools
magenta --harness-package PantheonOS --harness-package MagentaWithPantheonOS
```

The selector grammar is `PackageName[:profile1,profile2,...]`. Parsing and
loading live in the Magenta harness; this repository only owns package content,
manifests, tools, skills, prompts, and package-local runtimes.

## Publishing (monorepo + per-package tags)

This is a monorepo of independently versioned packages. Each package has its
own `version` in `package.toml` and is released on its own cadence via a
prefixed git tag `<PackageName>-v<version>`:

```bash
git tag AutOmicScience-v1.0.0
git push origin AutOmicScience-v1.0.0
```

The [`release`](./.github/workflows/release.yml) workflow parses the package
and version from the tag, validates the manifest, verifies the tag matches the
manifest `version`, and builds one relocatable `tar.gz` + SHA256 for each
Magenta binary platform. Native package tools are compiled into the matching
archive, so downloaded packages do not require a local Rust toolchain. The
private source tag creates the verified source Release. Magenta's
`Promote Harness Package Release` workflow then copies and re-verifies those
assets in the public `Minions-Land/Magenta-CLI` distribution repository,
matching the Magenta binary release model. The acquisition layer resolves
`github:Minions-Land/Magenta-CLI/<Package>@<version>` to that public Release.

For a skill-only Package such as ClaudeScience, the platform archive itself is
the binary Release payload; it is not an executable program. A native
executable is embedded only when the Package declares a native Tool.

Promote a completed private source Release with:

```bash
gh workflow run promote-package-release.yml \
  --repo Minions-Land/Magenta \
  --ref main \
  -f package=AutOmicScience \
  -f version=1.0.0
```

## Repository maintenance

Run the repository validator before pushing (requires Python >= 3.11):

```bash
python3 scripts/validate_packages.py
```

The validator parses TOML, verifies package component paths and profile graphs,
checks every real HcpServer/HcpMagnet shape and product method, checks skill
entry points, and prevents generated environments/build outputs from being committed.
The bio-API Rust workspace can be checked independently:

```bash
cargo test --locked --manifest-path AutOmicScience/tools/bio-api/rust/Cargo.toml --workspace
```

Generated directories such as `.pixi/`, `target/`, `__pycache__/`, and
`node_modules/` are intentionally excluded from source control. Release jobs
rebuild declared native tools and embed only their final executable.

## Packages in this repository

| Package | Domain | Shape | What it adds |
|---|---|---|---|
| [`AutOmicScience`](./AutOmicScience/) | Single-cell / spatial / bulk omics, cancer & clinical genomics | 14 skills · 5 tools · system prompt · brand · Python/Pixi runtime | Production omics analysis grounded in a real compute tool (`omics_compute`) |
| [`Biomni`](./Biomni/) | Biomedical AI (Stanford SNAP Lab) | 3 skills bundling executable tools | CRISPR sgRNA design, single-cell annotation, and a broad biomedical toolkit copied in-tree |
| [`ClaudeScience`](./ClaudeScience/) | Computational biology research | 20 skills · 6 profiles | Structure/docking, protein design, sequence models, single-cell, research, and publishing — selected by profile |
| [`PantheonOS`](./PantheonOS/) | Bioinformatics workflow best practices | 11 skills · 3 profiles | Magenta-native scverse/nf-core workflow discipline, image analysis, and scientific publishing |
| [`MagentaWithPantheonOS`](./MagentaWithPantheonOS/) | PantheonOS execution bridge | 4 tools · locked Python/Pixi runtime | Stateless Python, atomic nbformat editing, and real vision-backed figure QA |

AutOmicScience remains the **canonical full-stack reference package** because it
ships tools, a system prompt, a brand, and a pinned domain runtime. Use
MagentaWithPantheonOS as the compact executable-tool reference, and treat
Biomni, ClaudeScience, and PantheonOS as skill-led knowledge packages.

### Choosing between them

- **Production omics analysis** → `AutOmicScience` (grounded, tool-backed).
- **Wet-lab / biomedical breadth** → `Biomni` (executable tools across 20+ domains).
- **Model-heavy research** (folding, design, biological sequence models) → `ClaudeScience`, by profile.
- **Workflow / best-practice guidance** → `PantheonOS`.
- **PantheonOS Python/notebook/figure execution** → load `MagentaWithPantheonOS` with `PantheonOS`.

They compose. The normal Pantheon stack loads `PantheonOS` for workflow
discipline together with `MagentaWithPantheonOS` for the four execution tools;
`AutOmicScience` can still be added when its grounded omics capabilities are
needed.

## Creating a new package

Follow [`templates/harness-package/README.md`](./templates/harness-package/README.md).
The template is README-only on purpose — copy the current, executable rules
rather than a stale scaffold:

- Keep skills under `skills/<capability>/<source>/SKILL.md` with a sibling
  `HcpMagnet.ts`, plus `skills/<capability>/HcpServer.ts` for the real module.
- Put system prompts under `system-prompt/<source>/` with a `system-prompt.toml`,
  `SYSTEM.md`, and `HcpMagnet.ts`; the Resource exposes `SYSTEM.md` through
  `contentPath`. Add `system-prompt/HcpServer.ts`.
- Put tool descriptors under `tools/<tool>/<source>/` (one tool per item) with
  their `<tool>.toml` and an `HcpMagnet.ts`; keep shared implementation assets
  (Rust/Python runtimes, pixi env) at the tool-item or package-infra level.
- Give the package a `version` and mark `schema_version = "magenta.package.v2"`.
- Keep the package root itself limited to `package.toml`, `README.md`, and the
  convention directories — no scratch notes or migration reports.

Keep manifest changes aligned with Magenta's package loader before changing
schema names, component kinds, or path resolution semantics.
