---
name: paper-writing
description: 'Report and academic templates for HTML/PDF rendering. Each template
  file is self-contained (HTML + CSS or LaTeX in a single markdown file) and can be
  used by the current session or a delegated scientific-reporting worker.'
tags: []
source: PantheonOS
license: BSD-2-Clause
---

# Paper Writing Skills

Resources for the current session or a delegated scientific-reporting worker. Each
template is a self-contained markdown file with the full HTML+CSS or LaTeX content.

## Templates

| Template | File | Style | Use Case |
|----------|------|-------|----------|
| `report_standard` | [report_standard.md](assets/references/report_standard.md) | Professional report (Manus-style), HTML+CSS | Default for all reports |
| `report_academic` | [report_academic.md](assets/references/report_academic.md) | Formal academic paper, HTML+CSS | HTML preview for academic papers |
| `latex_cn` | [latex_cn.md](assets/references/latex_cn.md) | Chinese academic paper, LaTeX | Chinese academic PDF via Tectonic |
| `latex_en` | [latex_en.md](assets/references/latex_en.md) | English academic paper, LaTeX | English academic PDF via Tectonic |

## How to Use

### Report style (default)

1. Read this skill index and `report_standard.md`, which contains the HTML template and CSS.
2. Read `paper.md`, parse its frontmatter, and convert the Markdown body to HTML.
3. Fill the HTML template with metadata, CSS, and content; write the final HTML file.
4. Preview the HTML with `show(url=<html path>)`, correct rendering issues, then export it to PDF with an available browser/print workflow.

### Academic style

1. Read this skill index and the LaTeX template (`latex_cn.md` or `latex_en.md` based on language).
2. Read `paper.md`, parse its frontmatter, and convert the Markdown body to LaTeX.
3. Fill the template with metadata and content, then write the `.tex` file.
4. Run Tectonic to compile the PDF and read `report_academic.md` to generate an HTML preview.
5. Preview the PDF and HTML with `show(url=<artifact path>)`; fix any clipping, missing fonts, or layout defects before delivery.

### Custom templates

Users can add their own `.md` template files to this directory following the
same format (frontmatter + HTML/CSS or LaTeX in code blocks).
