---
name: figure-styling
description: Aesthetic guidelines for scientific figure production. Each style file
  specifies palettes, typography, layout, and domain-specific sub-styles for a given
  target venue (NeurIPS, Nature, IEEE, etc.) and figure class (methodology diagram
  vs. statistical plot). Use from the current session or a delegated visualization worker.
tags: []
source: PantheonOS
license: BSD-2-Clause
---

# Figure Styling Skills

Resources for the current session or a delegated visualization worker. Record `aesthetic_guide: <style_id>` in `style_card.json`; the producing session then loads the matching style file below.

## Available styles

| Style ID | File | Target | Figure class |
|---|---|---|---|
| `neurips_diagram` | [styles/neurips_diagram.md](assets/references/styles/neurips_diagram.md) | NeurIPS / top ML venues | Methodology / framework / pipeline diagrams |
| `neurips_plot` | [styles/neurips_plot.md](assets/references/styles/neurips_plot.md) | NeurIPS / top ML venues | Statistical plots (bar, line, scatter, heatmap, …) |

## How to use

1. The current session sets `aesthetic_guide: "<style_id>"` in `{workdir}/inputs/style_card.json`.
2. The producing session reads this skill index and the style file whose id matches `aesthetic_guide`. For independent or parallel figure work, delegate with `sub_agent` and include the style-card and artifact paths in its task.
3. Apply the guidance alongside `style_card.json`. Priority chain for conflicts:
   **user references > style_card.json > figure-styling/<style_id> > internal defaults**.

If `aesthetic_guide` is `custom` or `null`, do not load a file from this skill; rely on `style_card.json` and task-specific requirements.

## Custom styles

Users can drop additional `.md` files into `styles/` (e.g. `nature_figure.md`, `ieee_figure.md`, `my_lab_style.md`) following the same section structure as the NeurIPS guides. Set `aesthetic_guide: "<new_style_id>"` in `style_card.json` to activate.
