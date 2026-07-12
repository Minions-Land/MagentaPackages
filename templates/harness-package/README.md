# Harness Package Template (schema v2, HCP-isomorphic)

This directory is intentionally README-only. Do not copy a scaffold — build the
package directly and follow the live layout below, using `AutOmicScience/` as
the executable reference.

If you are an agent maintaining or extending packages in this repo, read
[`AGENT_GUIDE.md`](./AGENT_GUIDE.md) first: it is the step-by-step playbook for
the common tasks (new package, add a skill, add a tool, add a source, cut a
release). This README is the conceptual reference behind that playbook.

## The core idea

A package is an **externalized slice of the Magenta HarnessComponentProtocol
(HCP) tree**. Its on-disk shape mirrors the host harness exactly, so the same
assembly machinery loads a downloaded package and a built-in component with no
special-casing.

The host harness (in `Magenta3/HarnessComponentProtocol/`) organizes every
capability as:

```text
<module>/<source>/HcpMagnet.ts        # e.g. tools/write/magenta/HcpMagnet.ts
```

A package reproduces that exact structure. The only difference is the `source`
segment: instead of `magenta`, a package uses its own name as the source.

```text
<PackageName>/
  package.toml                        # manifest: id, version, source, components
  skills/<skill>/<PackageName>/
    HcpMagnet.ts                      # skill Source magnet
    SKILL.md                          # skill content
    assets/ ...                       # optional skill-local assets
  tools/<tool>/<PackageName>/
    HcpMagnet.ts                      # tool Source magnet
    <tool>.toml                       # tool descriptor
  brand/<PackageName>/
    HcpMagnet.ts                      # brand Source magnet
    brand.toml
  system-prompt/<PackageName>/
    HcpMagnet.ts                      # system-prompt Source magnet
    system-prompt.toml
    SYSTEM.md
```

- `<module>` is the host module name: `skills`, `tools`, `brand`,
  `system-prompt`, `theme`, `prompt-templates`. Match them exactly (note
  `brand` is singular).
- `<source>` is the package name. It is the same for every component in a
  single-source package.
- `tools` and `skills` are **item-type** modules: one item per directory, one
  `HcpServer`/tool per item. Keep one tool per `tools/<tool>/`.

### Merge packages (multiple sources)

`source` is per-component, not per-package. A package that aggregates multiple
upstreams adds sibling `<module>/<other-source>/` directories, each with its
own `HcpMagnet`:

```text
tools/agent-cli/claude-code/HcpMagnet.ts    # source = claude-code
tools/agent-cli/codex/HcpMagnet.ts          # source = codex
```

Adding a source is literally adding one more real `HcpMagnet`. The assembly
layer merges same-`kind:name` components by source, last-writer-wins for
`replace` resources.

## The HcpMagnet contract

Every component ships a `HcpMagnet.ts`. Per HCP spec §2 it is a **bare class**
named `HcpMagnet` whose shape is validated structurally — it imports **no**
harness interface, so a package stays dependency-free and compiles standalone.

Required members:

| Member | Purpose |
|---|---|
| `static readonly module` | Host module path, e.g. `"skills/single-cell"`, `"tools/bio-api"`. |
| `static readonly kind` | Component kind: `"skill"`, `"tool"`, `"brand"`, `"system-prompt"`. |
| `static readonly source` | The source id = package name. |
| `static build(context)` | Single construction entry point. Returns an instance. |
| one product method | `toResource()` for resources, `descriptor()` for tools. |

Two product shapes only:

**Resource magnets** (skill / brand / system-prompt) are self-sufficient. They
resolve their own content path relative to the magnet file and return the
resource inline:

```typescript
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export class HcpMagnet {
	static readonly module = "skills/single-cell";
	static readonly kind = "skill";
	static readonly source = "AutOmicScience";
	static build(_context: unknown) {
		return new HcpMagnet();
	}

	readonly kind = "resource:skill";
	readonly source = "AutOmicScience";

	toResource() {
		return {
			kind: "skill",
			name: "single-cell",
			source: "AutOmicScience",
			mergeMode: "replace" as const,
			contentPath: join(dirname(fileURLToPath(import.meta.url)), "SKILL.md"),
		};
	}
}
```

**Tool magnets** are *descriptor providers*, not AgentTool builders. Building an
`AgentTool` needs host infrastructure (sandbox, process/python runtime, MCP
discovery), which must not be baked into a package. So a tool magnet only
declares its identity and hands over the absolute path to its descriptor
`.toml`; the host reads that toml and runs its own tool-build chain
(`createPackageToolProduct`) to produce the `AgentTool`.

```typescript
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export class HcpMagnet {
	static readonly module = "tools/bio-api";
	static readonly kind = "tool";
	static readonly source = "AutOmicScience";
	static build(context: unknown) {
		return new HcpMagnet(context);
	}

	readonly kind = "tool";
	readonly source = "AutOmicScience";
	readonly descriptorPath = join(dirname(fileURLToPath(import.meta.url)), "bio-api.toml");

	descriptor() {
		return {
			kind: "tool" as const,
			name: "bio-api",
			source: "AutOmicScience",
			descriptorPath: this.descriptorPath,
		};
	}
}
```

### Why `import.meta.url`, not a harness path

The host's own magnets resolve content with helpers like
`getHarnessSkillsDir()`. A package is downloaded into
`~/.magenta/harness-packages/<pkg>@<version>/` at runtime, so it cannot rely on
harness-internal paths. Resolving relative to `import.meta.url` keeps the
package **relocatable**: it works from wherever it is unpacked.

The runtime magnet loader imports each `HcpMagnet.ts` with `await import()`
(Bun's standalone binary transpiles external `.ts` with its built-in runtime —
no external `tsc`/`node` needed), validates the shape, and registers the magnet
into the **same `HcpClient`** as built-in magnets.

## The manifest (`package.toml`, schema v2)

```toml
schema_version = "magenta.package.v2"
id = "AutOmicScience"          # must equal the directory name
name = "AutOmicScience"
version = "1.0.0"              # release tags derive from this
kind = "domain"
domain = "bioinformatics"
description = "..."
source = "AutOmicScience"      # package-wide default source

default_profiles = []          # empty = load everything on bare selection

[[profiles]]                   # optional: selective loading for big skill sets
name = "single-cell"
description = "..."
extends = []

[[components]]
kind = "skill"
name = "single-cell"
source = "AutOmicScience"
path = "skills/single-cell/AutOmicScience"   # points at <module>/<source> dir
include_in_context = true
profiles = ["single-cell"]

[[components]]
kind = "tool"
name = "bio_api"
source = "AutOmicScience"
path = "tools/bio-api/AutOmicScience"
```

Each `[[components]]` entry points at its `<module>/<source>` **directory**;
the loader finds `HcpMagnet.ts` + descriptor/content there. Give the package a
`version` — the release tag and acquisition version derive from it.

### Package-local infrastructure

Some assets back tools but are not themselves module/source/magnet components:
a Python runtime, its tests, a pinned Pixi env + lock, or a vendored Rust
binary. Keep them beside the tool item (e.g. `tools/omics-compute/python/`,
`tools/omics-environment/pixi.toml`) and declare them with infra kinds
(`python-runtime`, `runtime-tests`, `env`, `env-lock`). They ship inside the
package and are referenced by tool descriptors (`runtime = "..."`,
`env_manifest = "..."`).

## Publishing

Monorepo + per-package tags. Each package versions independently:

```bash
git tag AutOmicScience-v1.0.0
git push origin AutOmicScience-v1.0.0
```

The `.github/workflows/release.yml` workflow parses `<PackageName>-v<version>`,
validates the manifest, verifies the tag matches `package.toml`'s `version`,
builds a relocatable source `tar.gz` + SHA256, and publishes a GitHub Release.
Users load it with:

```bash
magenta --harness-package github:Minions-Land/MagentaPackages/AutOmicScience@1.0.0
```

## Before you push

```bash
python3 scripts/validate_packages.py                    # all packages
python3 scripts/validate_packages.py --package <Name>   # one package
```

The validator enforces the v2 rules: `version` present, per-component `source`,
`<module>/<source>/HcpMagnet.ts` present, and kind-specific content
(`SKILL.md`, `brand.toml`, `<tool>.toml`, `system-prompt.toml`).
