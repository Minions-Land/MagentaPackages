# ClaudeScience Package

Computational biology package for Magenta with **20 skills across 6 profiles**.
It covers biomolecular structure and design, biological sequence models,
single-cell analysis, scientific research, and publication workflows.

## Profiles

| Profile | Purpose | Skills |
|---|---|---|
| `structure` | Structure prediction and molecular docking | alphafold2, esmfold2, chai1, boltz, openfold3, diffdock |
| `design` | Protein sequence design | proteinmpnn, ligandmpnn, solublempnn |
| `sequence-models` | DNA and protein sequence models | borzoi, evo2, fair-esm2 |
| `single-cell` | Single-cell probabilistic and foundation models | scvi-tools, scgpt |
| `research` | Literature, PDF, and indication research | literature-review, pdf-explore, indication-dossier |
| `publishing` | Paper narrative and scientific figures | paper-narrative, figure-composer, figure-style |

`design` extends `structure`, so selecting `design` loads its three design
skills plus the six structure/docking skills needed to validate designs.

## Usage

```bash
# Load every ClaudeScience skill (default_profiles = [])
magenta --harness-package ClaudeScience

# Load a focused profile
magenta --harness-package ClaudeScience:sequence-models

# Protein design plus its inherited structure-validation skills
magenta --harness-package ClaudeScience:design

# Combine independent profiles
magenta --harness-package ClaudeScience:single-cell,research

# Explicitly load all declared profiles
magenta --harness-package ClaudeScience:all
```

Selectors narrow the model-visible skill catalog. Skill bodies still load on
demand through the `read` tool.

## Skill identity

Every skill has one canonical capability name. These three values must match:

1. component `name` in `package.toml`;
2. skill directory basename under `skills/`;
3. `name` in the `SKILL.md` frontmatter.

Profiles are expressed only through the component's `profiles` list; do not
prefix component names with profile names. For example, the canonical name is
`alphafold2`, not `structure-alphafold2`.

## Cross-skill references

- Reference a same-profile or inherited skill by canonical name.
- Use a relative `../<skill>/SKILL.md` link for an optional cross-profile jump.
- Put a hard dependency in the same loading closure by sharing a profile,
  dual-tagging it, or using profile inheritance.
- Resolve bundled files relative to the directory containing the current
  `SKILL.md`.

The current dependency chain is intentional:

```text
design ──extends──> structure

paper-narrative ──> figure-composer ──> figure-style
      (all three are in publishing)
```

## Execution model

Each skill documents one direct command or Python workflow for the active
workspace. The host owns execution placement: the same skill instructions work
when Magenta's filesystem and shell are local or transparently backed by SSH.
Skills do not embed provider-specific scheduling, volumes, job submission, or
notification protocols. Model-specific dependency, cache, and GPU requirements
remain beside the workflow that needs them.

## Adding a skill

1. Create `skills/<skill-name>/SKILL.md` with matching `name` frontmatter.
2. Reuse an existing profile unless the new category clearly earns a loading
   unit of its own.
3. Register it in `package.toml`:

```toml
[[components]]
kind = "skill"
name = "skill-name"
path = "skills/skill-name"
description = "Brief capability description"
profiles = ["research"]
```

4. Check same-profile and cross-profile references.
5. Run repository validation.

## Reshape notes

The 2026 reshape intentionally made these breaking selector changes:

| Previous | Current |
|---|---|
| `genomics` | `sequence-models`; DiffDock moved to `structure` |
| `singlecell` | `single-cell` |
| `visualization` | `publishing` |
| `compute` | removed; the old Claude Science compute broker is not a Magenta capability |
| `meta` | removed; general platform skills do not belong in this domain package |

Algorithmic art and generic web-artifact building were also removed from the
scientific visualization surface. The package keeps `default_profiles = []`,
so its bare selector still loads every remaining domain skill.

## Validation

From the MagentaPackages repository root:

```bash
python3 scripts/validate_packages.py
```

After structural changes, also check relative links and grep for deleted skill
or profile names.

## License

See each skill's frontmatter and bundled license files for its terms and
third-party model/service disclosures.

## Related packages

- [`AutOmicScience`](../AutOmicScience/) — tool-backed production omics
- [`PantheonOS`](../PantheonOS/) — bioinformatics workflow best practices
- [`Biomni`](../Biomni/) — biomedical AI toolkit with bundled executable tools
