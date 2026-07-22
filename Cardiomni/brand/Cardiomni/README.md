# Cardiomni Brand

Package-local brand override for the Cardiomni cardiovascular AI agent package.

The palette is inspired by cardiovascular medical imaging and clinical interfaces:

- Primary: `#C41E3A` (Crimson Red - representing arterial blood and cardiovascular focus)
- Accent: `#2E86AB` (Clinical Blue - representing medical imaging and DSA contrast)
- Link/API accent: `#0077BE` (Medical Blue)
- Warning: `#F77F00` (Amber - clinical alerts)
- Error: `#D62828` (Alert Red)
- Success: `#06A77D` (Healthy Green - representing good perfusion)

`brand.toml` is the package-local descriptor. `Cardiomni.brand.ts` mirrors
the root `BrandConfig` shape so future brand activation can consume the package
resource without depending on external dependencies.
