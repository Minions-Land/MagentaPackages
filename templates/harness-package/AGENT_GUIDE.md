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
4. [Add a source to a package (merge package)](#add-a-source)
5. [Cut a versioned release](#cut-a-release)
6. [Validate your changes](#validate)
7. [Troubleshooting](#troubleshooting)

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
    * Isomorphic to the host's tools/<tool>/<source>/HcpMagnet.ts. This is a
    * descriptor-backed tool: the magnet resolves its own descriptor (.toml)
    * relative to this file and hands it to the host tool runtime, which reads
    * the toml and builds the AgentTool using the host's sandbox/runtime infra.
    */
   export class HcpMagnet {
       static readonly module = "tools/rosetta-dock";
       static readonly kind = "tool";
       static readonly source = "QuantumChem";
       static build(context: unknown) {
           return new HcpMagnet(context);
       }

       readonly kind = "tool";
       readonly source = "QuantumChem";
       readonly descriptorPath = join(dirname(fileURLToPath(import.meta.url)), "rosetta-dock.toml");
       private readonly context: unknown;

       constructor(context: unknown) {
           this.context = context;
       }

       descriptor() {
           return {
               kind: "tool" as const,
               name: "rosetta-dock",
               source: "QuantumChem",
               descriptorPath: this.descriptorPath,
           };
       }
   }
   ```
   **Key points**:
   - Tool magnets are **descriptor providers**, not AgentTool builders.
   - `descriptor()` returns `{ kind, name, source, descriptorPath }`.
   - The host reads the toml at `descriptorPath` and runs its own tool-build
     chain (`createPackageToolProduct`) to make the `AgentTool`.

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
   matches the manifest, builds a relocatable `tar.gz` + SHA256, and publishes
   a GitHub Release under the tag `AutOmicScience-v1.1.0`.

5. **Verify the release** on GitHub:
   - Go to `https://github.com/Minions-Land/MagentaPackages/releases`.
   - Confirm the release `AutOmicScience v1.1.0` exists with the `tar.gz` artifact.

**Users load it with**:
```bash
magenta --harness-package github:Minions-Land/MagentaPackages/AutOmicScience@1.1.0
```

The acquisition layer resolves that to the release artifact and downloads it
into `~/.magenta/harness-packages/AutOmicScience@1.1.0/`.

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
(`toResource()` or `descriptor()`), and save it as
`<module>/<source>/HcpMagnet.ts`.

### "Validator says 'skill path lacks SKILL.md'"

The skill source directory exists but has no `SKILL.md`. Write one or move it
from the wrong location. Remember: in v2, `SKILL.md` lives **inside the source
dir** (e.g. `skills/single-cell/AutOmicScience/SKILL.md`), not at
`skills/single-cell/SKILL.md`.

### "Tool magnet: should I call `toTool()` or `descriptor()`?"

Tools call `descriptor()`, not `toTool()`. The magnet is a descriptor provider;
the host builds the `AgentTool`. Skills/brands/system-prompts call
`toResource()`.

### "How do I know if it's an item-type module (4 layers) or direct-type (3 layers)?"

- **Item-type** (4 layers: `<module>/<item>/<source>/`): `tools`, `skills`.
  Each tool or skill is a separate item with its own `HcpServer` in the host.
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
