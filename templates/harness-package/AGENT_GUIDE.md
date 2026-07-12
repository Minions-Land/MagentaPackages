# Agent Guide: Maintaining MagentaPackages (v2 HCP-isomorphic)

This is the operational playbook for agents maintaining this repository. If you
are an agent asked to "add a skill to Biomni" or "create a new package for X
domain" or "cut a release for AutOmicScience v1.1.0", this guide is your
step-by-step checklist.

Read [`README.md`](./README.md) first for the conceptual model. This guide is
the how-to.

## Table of Contents

1. [Create a new package from scratch](#create-a-new-package)
2. [Add a skill to an existing package](#add-a-skill)
3. [Add a tool to an existing package](#add-a-tool)
4. [Tool descriptor variants (process / mcp / python-runtime)](#tool-descriptor-variants)
5. [Tool naming: the three name layers](#tool-naming)
6. [Package-local infrastructure (runtimes, envs, locks)](#package-infra)
7. [Add a source to a package (merge package)](#add-a-source)
8. [Cut a versioned release](#cut-a-release)
9. [Validate your changes](#validate)
10. [Troubleshooting](#troubleshooting)

---

## Create a new package

**Scenario**: User asks "Create a new package for quantum chemistry workflows."

**Steps**:

1. **Pick a name** following the host's `TitleCase` convention (e.g.
   `QuantumChem`). The package name becomes the source id.

2. **Create the package directory** under repo root:
   ```bash
   cd /Users/mjm/MagentaPackages
   mkdir QuantumChem
   cd QuantumChem
   ```

3. **Write `package.toml`**:
   ```toml
   schema_version = "magenta.package.v2"
   id = "QuantumChem"                # must match directory name
   name = "QuantumChem"
   version = "0.1.0"                 # start at 0.1.0, increment for releases
   kind = "domain"
   domain = "quantum-chemistry"
   description = "Quantum chemistry workflow skills for DFT, MD, and docking."
   source = "QuantumChem"            # package-wide source = package name

   default_profiles = []             # load everything by default

   # Add [[profiles]] if the package has many skills and users need subsets
   # Add [[components]] as you create skills/tools below
   ```

4. **Create the module structure** (start with skills as the common case):
   ```bash
   mkdir -p skills/dft-workflows/QuantumChem
   ```

   Add `skills/dft-workflows/HcpServer.ts` with a bare `HcpServer` whose
   `moduleName` is exactly `"skills/dft-workflows"`.

5. **Write the first skill**:
   - `skills/dft-workflows/QuantumChem/SKILL.md` — the skill content.
   - `skills/dft-workflows/QuantumChem/HcpMagnet.ts` — copy from an existing
     skill magnet (e.g. `AutOmicScience/skills/single-cell/AutOmicScience/HcpMagnet.ts`),
     then update:
     - `module = "skills/dft-workflows"`
     - `kind = "skill"`
     - `source = "QuantumChem"`
     - `toResource()` returns `name: "dft-workflows"` and resolves `SKILL.md`
       relative to the magnet via `import.meta.url`.

6. **Declare the skill in `package.toml`**:
   ```toml
   [[components]]
   kind = "skill"
   name = "dft-workflows"
   source = "QuantumChem"
   path = "skills/dft-workflows/QuantumChem"
   include_in_context = true
   ```

7. **Validate**:
   ```bash
   cd /Users/mjm/MagentaPackages
   python3 scripts/validate_packages.py --package QuantumChem
   ```

8. **Commit**:
   ```bash
   git add QuantumChem
   git commit -m "Add QuantumChem package with dft-workflows skill"
   ```

**Reference**: See `Biomni/` for a minimal skill-only package.

---

## Add a skill

**Scenario**: User asks "Add a protein-folding skill to ClaudeScience."

**Steps**:

1. **Navigate**:
   ```bash
   cd /Users/mjm/MagentaPackages/ClaudeScience
   ```

2. **Create the skill source directory**:
   ```bash
   mkdir -p skills/protein-folding/ClaudeScience
   ```

   Also create `skills/protein-folding/HcpServer.ts`:
   ```typescript
   export class HcpServer {
       readonly moduleName = "skills/protein-folding";
       readonly description = "Protein-folding package skill.";
   }
   ```

3. **Write the skill content**:
   - `skills/protein-folding/ClaudeScience/SKILL.md` — knowledge, tools,
     references, examples. Use Markdown headers, code blocks, and links.
   - Optional: `skills/protein-folding/ClaudeScience/assets/references/` for
     linked docs.

4. **Write the skill magnet** (`skills/protein-folding/ClaudeScience/HcpMagnet.ts`):
   ```typescript
   import { dirname, join } from "node:path";
   import { fileURLToPath } from "node:url";

   /**
    * Skill Source magnet for the ClaudeScience package (source = "ClaudeScience").
    *
    * Isomorphic to the host's skills/<skill>/<source>/HcpMagnet.ts (bare class,
    * static build, toResource). SKILL.md is resolved relative to this file so
    * the package is relocatable when downloaded into the local cache.
    */
   export class HcpMagnet {
       static readonly module = "skills/protein-folding";
       static readonly kind = "skill";
       static readonly source = "ClaudeScience";
       static build(_context: unknown) {
           return new HcpMagnet();
       }

       readonly kind = "resource:skill";
       readonly source = "ClaudeScience";

       toResource() {
           return {
               kind: "skill",
               name: "protein-folding",
               source: "ClaudeScience",
               mergeMode: "replace" as const,
               contentPath: join(dirname(fileURLToPath(import.meta.url)), "SKILL.md"),
           };
       }
   }
   ```
   **Key points**:
   - `module` path = `"skills/<skill-name>"` (match the directory).
   - `kind` and `source` are static readonly strings.
   - `contentPath` uses `import.meta.url` to resolve relative to the magnet itself.

5. **Declare in `package.toml`**:
   ```toml
   [[components]]
   kind = "skill"
   name = "protein-folding"
   source = "ClaudeScience"
   path = "skills/protein-folding/ClaudeScience"
   include_in_context = false          # or true if it's foundational
   profiles = ["structure"]            # optional profile tag
   ```

6. **Validate**:
   ```bash
   cd /Users/mjm/MagentaPackages
   python3 scripts/validate_packages.py --package ClaudeScience
   ```

7. **Commit**:
   ```bash
   git add ClaudeScience/skills/protein-folding ClaudeScience/package.toml
   git commit -m "Add protein-folding skill to ClaudeScience"
   ```

**Reminder**: Skills with sub-skills (like `bioml/coding/`, `bioml/deep-models/`)
put sub-skill directories **under the source dir** (e.g.
`skills/bioml/AutOmicScience/coding/SKILL.md`), not as sibling skill items.

---

## Add a tool

**Scenario**: User asks "Add a Rosetta docking tool to QuantumChem."

**Tools are harder than skills** because they involve:
- A tool descriptor (`.toml` declaring `runtime`, `command`, parameters schema).
- Often a backing implementation (Rust binary, Python script, MCP server).
- Possibly shared runtimes or environments.

**Steps**:

1. **Create the tool source directory**:
   ```bash
   cd /Users/mjm/MagentaPackages/QuantumChem
   mkdir -p tools/rosetta-dock/QuantumChem
   ```

   Add `tools/rosetta-dock/HcpServer.ts` with
   `moduleName = "tools/rosetta-dock"` before adding its source Magnet.

2. **Write the tool descriptor** (`tools/rosetta-dock/QuantumChem/rosetta-dock.toml`):
   ```toml
   kind = "tool"
   name = "rosetta_dock"
   description = "Run Rosetta docking protocol on a protein-ligand complex."
   runtime = "process"                 # or "mcp", or a python-runtime name
   command = "rosetta_scripts"
   args = ["-parser:protocol", "docking.xml"]
   operation = "execute"
   read_only = false
   destructive = false
   timeout_ms = 300000

   [metadata]
   package = "QuantumChem"
   origin = "..."

   [parameters]
   type = "object"
   required = ["pdb_input"]

   [parameters.properties.pdb_input]
   type = "string"
   description = "Path to input PDB structure."
   ```
   **Key fields**:
   - `runtime`: `"process"` (shell command), `"mcp"` (MCP server), or a
     `python-runtime` component name (for Python module tools).
   - `command` + `args`: what to execute.
   - `[parameters]`: JSON Schema for tool inputs (LLM fills this).

3. **Write the tool magnet** (`tools/rosetta-dock/QuantumChem/HcpMagnet.ts`):
   ```typescript
   import { dirname, join } from "node:path";
   import { fileURLToPath } from "node:url";

   /**
    * Tool Source magnet for the QuantumChem package (source = "QuantumChem").
    *
    * Isomorphic to the host's tools/<tool>/<source>/HcpMagnet.ts. The package
    * Source calls the injected Client builder and wraps its host-backed product.
    */
   export class HcpMagnet {
       static readonly module = "tools/rosetta-dock";
       static readonly kind = "tool";
       static readonly source = "QuantumChem";
       static async build(context: HcpMagnetBuildContext) {
           const descriptorPath = join(dirname(fileURLToPath(import.meta.url)), "rosetta-dock.toml");
           const products = await context.settings.HcpClientbuildtools(
               { kind: "tool", name: "rosetta-dock", source: "QuantumChem", descriptorPath },
               context,
           );
           return products.map((product) => new HcpMagnet(product));
       }

       readonly kind: string;
       readonly source = "QuantumChem";
       private readonly product: HcpMagnettoolproduct;

       constructor(product: HcpMagnettoolproduct) {
           this.product = product;
           this.kind = product.kind;
       }

       toTool() {
           return this.product.toTool();
       }

       async dispose() {
           await this.product.close?.();
       }
   }
   ```
   **Key points**:
   - `static build()` calls the injected `HcpClientbuildtools` hook.
   - The package's real Magnet wraps each returned host product with `toTool()`.
   - `dispose()` delegates to the product's optional `close()`.
   - Copy the structural helper types from a current Package Tool magnet.

4. **If the tool needs a backing implementation** (Rust binary, Python module):
   - **Rust**: Keep the workspace under `tools/rosetta-dock/rust/`, vendor the
     binary or build in CI, reference it in the toml `command` path.
   - **Python**: Declare a `python-runtime` component in `package.toml` pointing
     at the module directory, then set `runtime = "<runtime-name>"` in the tool
     toml.
   - **MCP**: Set `runtime = "mcp"`, `command = "<path-to-mcp-binary>"` in the
     toml. The host spawns the server and discovers its tools at load time.

5. **Declare in `package.toml`**:
   ```toml
   [[components]]
   kind = "tool"
   name = "rosetta_dock"
   source = "QuantumChem"
   path = "tools/rosetta-dock/QuantumChem"
   ```

6. **If you declared a python-runtime or env, add those too**:
   ```toml
   [[components]]
   kind = "python-runtime"
   name = "quantumchem_runtime"
   source = "QuantumChem"
   path = "tools/rosetta-dock/python/quantumchem_runtime"
   ```

7. **Validate**:
   ```bash
   cd /Users/mjm/MagentaPackages
   python3 scripts/validate_packages.py --package QuantumChem
   ```

8. **Commit**:
   ```bash
   git add QuantumChem/tools/rosetta-dock QuantumChem/package.toml
   git commit -m "Add rosetta-dock tool to QuantumChem"
   ```

**Reference**: See `AutOmicScience/tools/bio-api/` (MCP tool with Rust backend)
or `AutOmicScience/tools/omics-compute/` (Python-runtime tool).

---

<a id="tool-descriptor-variants"></a>
## Tool descriptor variants (process / mcp / python-runtime)

The fictional `rosetta-dock.toml` above shows the *shape*. In practice a tool
descriptor comes in one of **three real flavors**, distinguished by its
`runtime` field. The magnet is identical in all three (it only hands over the
descriptor path — see [Add a tool](#add-a-tool)); the descriptor `.toml` is what
changes. All examples below are the live descriptors under
`AutOmicScience/tools/`, so copy from them rather than the placeholder.

### 1. `runtime = "process"` — run a shell command

The host runs `command` + `args` in the sandbox. Use for CLI tools.

```toml
# AutOmicScience/tools/omics-environment/AutOmicScience/omics-environment.toml
kind = "tool"
name = "omics_environment"          # LLM-facing tool name (see Tool naming)
description = "Describe the Pixi environments ... via `pixi info --json`."
runtime = "process"
command = "pixi"
args = ["info", "--json"]
operation = "read"                   # read | execute
read_only = true
destructive = false
timeout_ms = 60000

[metadata]
package = "AutOmicScience"

[parameters]                         # JSON Schema the LLM fills
type = "object"
```

A **privileged** process tool (network + workspace write) additionally sets
`tags = ["trusted"]` and a long `timeout_ms` — see
`omics-install/AutOmicScience/omics-install.toml` (`pixi install --locked`,
`timeout_ms = 600000`).

### 2. `runtime = "mcp"` — spawn an MCP server, import its tools

The host spawns `command` as an MCP server over stdio and discovers every tool
it exposes. `name_prefix` namespaces those remote tool names into the local
tool address space so they never collide with built-ins.

```toml
# AutOmicScience/tools/bio-api/AutOmicScience/bio-api.toml
kind = "tool"
name = "biofetch"                    # remote tools surface as biofetch_<db>_<op>
description = "BioFetch: read-only access to bioinformatics databases over MCP."
runtime = "mcp"
command = "../rust/target/release/aose-bio-mcp"
command_windows = "../rust/target/release/aose-bio-mcp.exe"
args = []
name_prefix = "biofetch"             # ensembl_search -> biofetch_ensembl_search
timeout_ms = 60000

# Optional gated clients: set keys under [env] to unlock extra tools.
# [env]
# DRUGBANK_API_KEY = "..."

[metadata]
package = "AutOmicScience"
```

Notes:
- A relative `command` is resolved from the tool descriptor directory and must
  stay inside the package root. Use descriptor-relative paths such as
  `../rust/target/release/aose-bio-mcp`; never hard-code a checkout or cache path.
- With `name_prefix = "biofetch"`, a remote tool `ensembl_search` reaches the
  LLM as `biofetch_ensembl_search`. The prefix stacks on top of the remote
  name — factor it in when you document tool names.

### 3. `runtime = "<python-runtime-name>"` — dispatch into a package-local Python module

Set `runtime` to the **name of a `python-runtime` infra component** (not the
literal string `python`), plus `module` (the importable package) and optionally
`pixi_environment` (which pinned env to run in). See
[Package-local infrastructure](#package-infra) for declaring the runtime.

```toml
# AutOmicScience/tools/omics-compute/AutOmicScience/omics-compute.toml
kind = "tool"
name = "omics_compute"
description = "Run package-local omics compute subcommands ..."
runtime = "aose_omics_runtime"       # = the python-runtime component name
module = "aose_omics_runtime"        # importable module dispatched by subcommand
pixi_environment = "default"
operation = "execute"
read_only = false
destructive = false

[metadata]
package = "AutOmicScience"

[metadata.pixi_environment_by_modality]  # optional: map modality -> pinned env
scrna = "task1"
spatial = "task2"

[parameters]
type = "object"
required = ["subcommand"]

[parameters.properties.subcommand]
type = "string"
enum = ["load_dataset", "summarize", "preprocess"]  # your dispatch table
```

### Which variant do I want?

| You have... | Use | Extra fields | Backing infra needed |
|---|---|---|---|
| A shell command / CLI | `runtime = "process"` | `command`, `args`, `read_only`, `timeout_ms` | none |
| An MCP server (any language) | `runtime = "mcp"` | `command`, `name_prefix`, optional `[env]` | the server binary (vendor / build) |
| A Python module you ship | `runtime = "<runtime-name>"` | `module`, `pixi_environment` | a `python-runtime` + `env`/`env-lock` (next section) |

**Frozen contract (aligned with the host):** in all three cases the package's
real Tool Magnet calls `context.settings.HcpClientbuildtools` from `static
build()`, wraps every returned host product, exposes it through `toTool()`, and
delegates cleanup through `dispose()`. The package must not construct the
`AgentTool` or duplicate sandbox/runtime wiring itself.

---

<a id="tool-naming"></a>
## Tool naming: the three name layers

A tool carries **three names that are allowed to differ**, each with a distinct
job. This trips up agents who assume they must match — they must not. Live
evidence from `AutOmicScience`:

| Tool dir (`tools/<dir>/`) | Magnet build descriptor `name` | `<tool>.toml` `name` | `package.toml` component `name` |
|---|---|---|---|
| `bio-api` | `bio-api` | `biofetch` | `bio_api` |
| `omics-compute` | `omics-compute` | `omics_compute` | `omics_compute` |
| `omics-environment` | `omics-environment` | `omics_environment` | `omics_environment` |
| `omics-install` | `omics-install` | `omics_install_env` | `omics_install` |
| `omics-preflight` | `omics-preflight` | `omics_preflight` | `omics_preflight` |

Note `bio-api`: all three names differ, and none of them is what the LLM calls.

The three layers:

1. **Locator name** = the `tools/<dir>/` directory name = the descriptor `name`
   passed by the Magnet to `HcpClientbuildtools`. Hyphen-style by convention. The loader uses it to find
   the magnet and its descriptor on disk. Keep the magnet name equal to its
   directory.
2. **Manifest name** = `package.toml` component `name`. Underscore-style by
   convention. How the manifest and profiles refer to the component. Also what
   the validator reports in errors.
3. **Tool name** = the `name` inside `<tool>.toml`. **This is the only name the
   LLM sees** and calls. Choose it for the model, independent of directory or
   manifest naming.

For `runtime = "mcp"`, the tool name is a **prefix**, not the final name: with
`name_prefix = "biofetch"` the MCP server's `ensembl_search` reaches the LLM as
`biofetch_ensembl_search`. So an MCP descriptor contributes a *family* of tools
all sharing the prefix, not a single tool.

**Practical rule:** keep dir = magnet name (locator), pick a clear manifest
name, and set the `.toml` `name` to whatever reads best to the model. Don't
rename one layer expecting the others to follow — they're independent.

---

<a id="package-infra"></a>
## Package-local infrastructure (runtimes, envs, locks)

Some assets **back** tools but are **not** module/source/magnet components:
a Python runtime, its tests, a pinned Pixi env, and its lockfile. They ship
inside the package and are referenced by tool descriptors — but they have **no
`HcpMagnet.ts`**. The loader preserves their declarations in the package tool
context/component map so descriptors can resolve them; it does not assemble
them as HCP products. The validator checks that their `path` exists (these kinds are outside
`MODULE_SOURCE_KINDS`, so the HcpMagnet.ts / descriptor rules do not apply).

The four infra kinds (from `AutOmicScience/package.toml`):

| kind | `path` points at | Referenced by |
|---|---|---|
| `python-runtime` | a directory (the importable module) | tool `.toml` `runtime = "<name>"` + `module = "<name>"` |
| `runtime-tests` | a directory (pytest suite for the runtime) | CI / `cargo`/`pytest` runs, not loaded at session time |
| `env` | a file (`pixi.toml`) | tool `.toml` `metadata.env_manifest` |
| `env-lock` | a file (`pixi.lock`) | tool `.toml` `metadata.env_lock` |

Declare them alongside the tools they serve:

```toml
# python module the python-runtime tool dispatches into
[[components]]
kind = "python-runtime"
name = "aose_omics_runtime"
source = "AutOmicScience"
path = "tools/omics-compute/python/aose_omics_runtime"

# its test suite (kept in-tree, run in CI)
[[components]]
kind = "runtime-tests"
name = "aose_omics_runtime_tests"
source = "AutOmicScience"
path = "tools/omics-compute/python/tests"

# pinned environment manifest + lock
[[components]]
kind = "env"
name = "pixi"
source = "AutOmicScience"
path = "tools/omics-environment/pixi.toml"

[[components]]
kind = "env-lock"
name = "pixi"
source = "AutOmicScience"
path = "tools/omics-environment/pixi.lock"
```

How they wire together (frozen alignment with the main session):
- A `runtime = "aose_omics_runtime"` tool descriptor names a `python-runtime`
  component. The host resolves the runtime, imports its `module`, and dispatches
  the tool call — the package ships no `AgentTool`, only the module + descriptor.
- `metadata.env_manifest = "pixi.toml"` / `env_lock = "pixi.lock"` tie the tool
  to the pinned `env` / `env-lock`, so the host provisions the right
  environment before running.
- Keep these assets **beside the tool item** (`tools/omics-compute/python/`,
  `tools/omics-environment/pixi.toml`), not at package root.

**Do not** give infra components an `HcpMagnet.ts` or a `<source>/` directory —
they are plain paths, not magnets. Adding one will not break the validator but
misrepresents them as HCP components.

**Reference**: `AutOmicScience/` is the only package that ships infra; mirror
its `tools/omics-compute/python/` + `tools/omics-environment/` layout.

---

## Add a source

**Scenario**: User asks "Biomni should also include Codex bioinformatics tools as
a second source."

This creates a **merge package**: one package aggregating multiple sources. Each
source has its own `<module>/<source>/HcpMagnet.ts` tree.

**Steps**:

1. **Navigate**:
   ```bash
   cd /Users/mjm/MagentaPackages/Biomni
   ```

2. **Create the new source directories**:
   ```bash
   mkdir -p skills/genomic-pipelines/codex
   mkdir -p tools/seq-align/codex
   ```

3. **Write content + magnets** for each component in the new source, following
   the same structure as the existing `Biomni` source but with `source = "codex"`.

4. **Declare components in `package.toml`**:
   ```toml
   [[components]]
   kind = "skill"
   name = "genomic-pipelines"
   source = "codex"                    # different source
   path = "skills/genomic-pipelines/codex"

   [[components]]
   kind = "tool"
   name = "seq_align"
   source = "codex"
   path = "tools/seq-align/codex"
   ```

5. **Validate**:
   ```bash
   cd /Users/mjm/MagentaPackages
   python3 scripts/validate_packages.py --package Biomni
   ```

6. **Commit**:
   ```bash
   git add Biomni
   git commit -m "Add codex source to Biomni (merge package)"
   ```

**Merge behavior**: When the host loads a merge package, same-`kind:name`
components from different sources compete for selection. The host's source
selection logic (or explicit `source=` overrides) picks one. Resources with
`mergeMode = "append"` (like system prompts) stack; `"replace"` resources are
last-writer-wins.

---

## Cut a release

**Scenario**: User asks "Release AutOmicScience v1.1.0."

**Steps**:

1. **Verify the version in `package.toml` matches**:
   ```bash
   cd /Users/mjm/MagentaPackages
   python3 scripts/package_version.py AutOmicScience
   # Should print "1.1.0"
   ```
   If it doesn't, update `package.toml`'s `version = "1.1.0"` and commit.

2. **Validate the package**:
   ```bash
   python3 scripts/validate_packages.py --package AutOmicScience
   ```

3. **Tag the release** (pattern: `<PackageName>-v<version>`):
   ```bash
   git tag AutOmicScience-v1.1.0
   git push origin AutOmicScience-v1.1.0
   ```

4. **Wait for CI**: The `.github/workflows/release.yml` workflow triggers on
   the tag push, parses the package name and version, validates that the tag
   matches the manifest, builds one relocatable `tar.gz` + SHA256 per Magenta
   binary platform, and publishes a private source Release under the tag
   `AutOmicScience-v1.1.0`.

5. **Promote the verified Release** with the Magenta repository's
   `Promote Harness Package Release` workflow, passing Package
   `AutOmicScience` and version `1.1.0`. That workflow re-verifies all four
   archives and publishes them to the public distribution repository without
   changing the Magenta CLI `latest` Release.

6. **Verify the public Release** on GitHub:
   - Go to `https://github.com/Minions-Land/Magenta-CLI/releases`.
   - Confirm the release `AutOmicScience v1.1.0` contains all four platform archives.

**Users load it with**:
```bash
magenta --harness-package github:Minions-Land/Magenta-CLI/AutOmicScience@1.1.0
```

The acquisition layer resolves that to the current platform archive and
downloads it into Magenta's origin-, version-, and platform-scoped cache.

---

## Validate

**Before every commit**, run:

```bash
cd /Users/mjm/MagentaPackages
python3 scripts/validate_packages.py
```

This checks:
- All `package.toml` files parse as TOML.
- Each package has a `version` (v2 requirement).
- Each component declares a `source` (v2 requirement).
- Each component's `path` points at an existing `<module>/<source>` directory.
- Each skill source has a `SKILL.md`.
- Each tool source has a `.toml` descriptor.
- Each brand source has a `brand.toml`.
- Each system-prompt source has a `system-prompt.toml`.
- Each v2 component source has an `HcpMagnet.ts`.
- Each module has a real `HcpServer.ts` with the exact module path.
- Magnets expose the required product method, and Resource magnets expose
  `contentPath`/`content` rather than a tool-only descriptor pointer.
- No build outputs (`target/`, `__pycache__/`, `.pixi/`, `node_modules/`) are
  committed (the validator scans git-visible files and flags them).

**For a single package**:
```bash
python3 scripts/validate_packages.py --package <PackageName>
```

**If validation fails**, the error message tells you which rule broke and where.
Fix it before pushing.

---

## Troubleshooting

### "Validator says 'v2 component lacks HcpMagnet.ts'"

You created the `<module>/<source>` directory and wrote the `SKILL.md` /
`.toml` but forgot the magnet. Copy an existing `HcpMagnet.ts` from a
similar component, update the `module`, `kind`, `source`, and product method
(`toResource()` or `toTool()`), and save it as
`<module>/<source>/HcpMagnet.ts`.

### "Validator says the module lacks HcpServer.ts"

Create `<module>/HcpServer.ts` beside the source directories. It must export a
bare `class HcpServer` and its `moduleName` must exactly match the module path.
Do not route an item module through a generic parent Server.

### "Validator says 'skill path lacks SKILL.md'"

The skill source directory exists but has no `SKILL.md`. Write one or move it
from the wrong location. Remember: in v2, `SKILL.md` lives **inside the source
dir** (e.g. `skills/single-cell/AutOmicScience/SKILL.md`), not at
`skills/single-cell/SKILL.md`.

### "Tool magnet: should I call `toTool()` or `descriptor()`?"

Tools call `HcpClientbuildtools` in `static build()`, wrap the returned host
product, and expose it through `toTool()`. They do not implement `descriptor()`
or construct the `AgentTool` themselves. Skills/brands/system-prompts call
`toResource()`.

### "How do I know if it's an item-type module (4 layers) or direct-type (3 layers)?"

- **Item-type** (4 layers: `<module>/<item>/<source>/`): `tools`, `skills`.
  Each tool or skill is a separate item with its own package `HcpServer.ts`.
- **Direct-type** (3 layers: `<module>/<source>/`): `brand`, `system-prompt`,
  `theme`, `prompt-templates`. Only one of each per package.

Match the host structure. Check
`/Users/mjm/Magenta3/HarnessComponentProtocol/<module>/` to see how the host
organizes that module.

### "My magnet imports a harness interface and the validator complains"

Remove the import. HCP spec §2 says magnets are **bare classes** validated
structurally, so they import **no** harness code. If you need to parse TOML,
resolve capability dependencies, or access sandbox/runtime, those are the
**host's job** at assembly time — your magnet only declares its identity and
hands over content/descriptor paths. The host does the heavy lifting.

### "Can I add a `README.md` inside a skill source dir?"

Yes, but it won't be loaded as skill content. The host looks for `SKILL.md`.
Use README for developer notes or migration logs. Keep user-facing skill content
in `SKILL.md` and optionally link to `assets/references/*.md` from within it.

---

**Still stuck?** Read the live reference package
(`/Users/mjm/MagentaPackages/AutOmicScience/`) and compare your structure to
it. Or grep the repo for an example of what you're trying to do — the four
packages cover skills, tools (process/mcp/python), brands, system prompts, and
package-local runtimes/envs.
