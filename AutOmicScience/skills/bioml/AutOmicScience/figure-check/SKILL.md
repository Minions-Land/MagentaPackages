---
name: bioml-figure-check
disable-model-invocation: true
---

# BioML Figure Check — Publication-Grade Plotting & Audit

> Subskill of `bioml`. Enter here from the parent skill when you produce or audit figures for a publication, poster, or benchmark submission. Read the parent (`../SKILL.md`) and the always-loaded `omics-shared` skill first — their evidence/grounding rules apply here.

Two responsibilities: **apply matplotlib publication discipline** (rcParams, Type-42 font compliance), and **audit layout honesty** (no empty quadrants, readable labels, proper legend placement).

---

## When to Use

- Before every new figure goes into a shared workspace or submission
- When a figure is rejected for "poor quality" or "formatting issues"
- When auditing a figure's layout / readability before publication
- When choosing the right chart type for a data shape

---

## The Non-Skippable Preamble

**Every `gen_figure.py` starts with this block:**

```python
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt

# Publication rcParams — ALWAYS include this
plt.rcParams.update({
    'pdf.fonttype': 42,        # Type-42 (TrueType) not Type-3 (bitmap)
    'ps.fonttype': 42,
    'font.size': 7,            # Nature/Cell standard body text
    'axes.labelsize': 7,
    'axes.titlesize': 8,
    'xtick.labelsize': 6,
    'ytick.labelsize': 6,
    'legend.fontsize': 6,
    'figure.titlesize': 8,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.linewidth': 0.5,
    'xtick.major.width': 0.5,
    'ytick.major.width': 0.5,
    'xtick.direction': 'out',  # ticks point outward
    'ytick.direction': 'out',
    'axes.spines.top': False,   # remove top/right spines (cleaner)
    'axes.spines.right': False,
})
```

**Why `pdf.fonttype=42` is non-negotiable:** matplotlib's default is `pdf.fonttype: 3` (verified:
`matplotlib.rcParamsDefault['pdf.fonttype'] == 3`), so *every* PDF you save without this block embeds
Type-3 fonts. **Nature, IEEE and ACM reject Type-3 submissions outright** — that is the reason, and it
is enough of one.

Be accurate about *why*, because the usual justification is wrong: Type-3 fonts are **not bitmaps**.
They are vector glyph procedures, and matplotlib emits a ToUnicode map for them, so a Type-3 PDF
renders identically and `pdftotext` extracts exactly the same text as a Type-42 one (checked on
identical figures at both settings). The problem is purely that Type 3 is not a real embedded font
program: journals reject it, and downstream editors cannot treat the glyphs as text. Do not claim it
looks worse on screen or loses text — a reviewer who checks will find it does neither, and then the
rule looks like superstition.

**This setting cannot be skipped**, even for "simple" plots.

> **The font list falls back silently.** `'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans']`
> only gets you Arial if Arial is installed — it usually isn't on Linux, and matplotlib quietly walks
> the list down to DejaVu Sans. The pinned envs here have **no Arial and no Helvetica**, so this block
> produces DejaVu Sans. That is fine for a working figure; it is not "Nature house style". If the
> journal requires Arial, install it and check
> `{f.name for f in matplotlib.font_manager.fontManager.ttflist}` rather than trusting the rcParam.

---

## Chart Type Selection

Pick the chart type that matches your data shape. Common archetypes:

| Data shape | Chart type | When to use |
|------------|------------|-------------|
| 2D continuous (x, y) | **Scatter** | Gene expression, embeddings, correlations |
| 2D + density | **Hexbin** or **2D histogram** | >10k points, avoid overplotting |
| Time series (1 variable) | **Line plot** | Training loss, temporal gene expression |
| Time series (multiple) | **Multi-line** with legend | Compare conditions/models |
| Categorical × continuous | **Box plot** or **violin plot** | Cell-type marker expression, batch effects |
| Part-of-whole | **Stacked bar** | Cell-type composition across samples |
| Heatmap (matrix) | **imshow / pcolormesh** | Gene × sample expression, confusion matrix |
| Network | **networkx layout + edges** | Cell-cell communication, regulatory network |

**Avoid:**
- **3D plots** — hard to read, print poorly
- **Pie charts** — use stacked bar instead
- **Dual y-axis** — confusing, use facets

---

## The Standard Workflow

### 1. Generate the plot

```python
fig, ax = plt.subplots(figsize=(3.5, 2.5), dpi=300)  # Nature single-column width ≈ 3.5"

# Your plot:
ax.scatter(x, y, s=2, alpha=0.6, c=colors, cmap='viridis')
ax.set_xlabel("UMAP 1")
ax.set_ylabel("UMAP 2")
ax.set_title("scRNA-seq UMAP", loc='left')  # left-aligned title (journal style)

# Legend (if needed):
handles, labels = ax.get_legend_handles_labels()
ax.legend(handles, labels, loc='upper right', frameon=False)

plt.tight_layout()
plt.savefig("output/umap.pdf", dpi=300, bbox_inches='tight')
plt.close()
```

### 2. Post-save Type-3 verification

**After every `savefig`**, verify no Type-3 font slipped in. This needs nothing beyond the pinned env:

```python
def assert_no_type3(path):
    """Raise if the PDF embeds a Type-3 font (journals reject them)."""
    raw = open(path, "rb").read()
    if b"/Subtype /Type3" in raw or b"/Subtype/Type3" in raw:
        raise AssertionError(f"{path}: Type-3 font embedded — set pdf.fonttype=42 and regenerate")

assert_no_type3("output/umap.pdf")
```

matplotlib writes the font dictionary as a plain object, so the subtype token stays greppable in the
raw bytes. Verified to discriminate correctly across `pdf.fonttype` 42/3 × `pdf.compression` 0/6/9 ×
simple/multi-artist figures — 12/12.

If poppler is installed (`pdffonts` is **not** in `task1–4`, nor declared in `pixi.toml` — it is a
system tool that may simply be absent), this is the equivalent:

```bash
pdffonts output/umap.pdf | tail -n +3 | awk '$2=="Type" && $3=="3" {bad=1} END {exit !bad}' \
  && echo "FAIL: Type-3 fonts" || echo "OK"
```

> **Do not test for the string `Type 42`.** `pdffonts` never prints it. A `pdf.fonttype=42` figure is
> reported as **`CID TrueType`** — "Type 42" is the PostScript name for the TrueType wrapper, not a
> PDF font subtype. The obvious-looking check
> `pdffonts f.pdf | grep -v "Type 42\|Type 1C" && echo FAIL || echo OK` therefore prints **FAIL on a
> correct PDF and FAIL on a broken one** — the header rows alone guarantee a match. A check with no
> discriminating power is worse than none: it trains you to ignore it.

### 3. Visual audit (pixel-level layout check)

Render the PDF to PNG at print resolution and visually inspect:

```bash
# Ghostscript (a system tool — not in task1–4; check it exists first)
gs -sDEVICE=pngalpha -r300 -o output/umap_300dpi.png output/umap.pdf
```

Simpler when the figure is still in hand: save both formats from the same `Figure` object, and skip
the render step entirely.

```python
fig.savefig("output/umap.pdf")                 # the submission artifact
fig.savefig("output/umap_300dpi.png", dpi=300) # the one you inspect
```

This is not just convenience — a `gs` render can differ from what the journal's RIP produces, whereas
the PNG comes from the same draw call as the PDF. Reach for `gs` when you are auditing a PDF you did
not generate. (ImageMagick also works, but v7 renamed `convert` to `magick`, and its default
`policy.xml` blocks PDF on many distributions — treat it as a fallback, not the instruction.)

Open `umap_300dpi.png` and audit for:

| Issue | Check |
|-------|-------|
| **Empty quadrants** | No large blank regions (>20% of canvas). If present, crop or rebalance. |
| **Overlapping labels** | Axis labels don't collide with tick labels or title. |
| **Legend obscures data** | Legend placed in a blank region, not covering points. |
| **Readable labels** | All text ≥6 pt at print size. Zoom to 100% — can you read it? |
| **Axis spans data** | No clipping, no excessive whitespace. |
| **Colorbar labeled** | If using a colormap, include a labeled colorbar. |

If any issue is present, adjust and regenerate.

### 4. Evidence

Inspect the generated figure before it backs a claim in a result. The figure + its generation script are the audit trail.

---

## ML-Specific Plotting Idioms

### Training curves

```python
ax.plot(epochs, train_loss, label='Train', linewidth=1)
ax.plot(epochs, val_loss, label='Val', linewidth=1, linestyle='--')
ax.set_xlabel("Epoch")
ax.set_ylabel("Loss")
ax.set_yscale('log')  # often clearer for loss
ax.legend(frameon=False)
```

### Confusion matrix

```python
import seaborn as sns
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax, cbar_kws={'label': 'Count'})
ax.set_xlabel("Predicted")
ax.set_ylabel("True")
```

### UMAP / t-SNE (embedding)

```python
for i, label in enumerate(unique_labels):
    mask = (labels == label)
    ax.scatter(embedding[mask, 0], embedding[mask, 1], s=1, alpha=0.6, label=label)
ax.set_xlabel("UMAP 1")
ax.set_ylabel("UMAP 2")
ax.legend(loc='upper right', frameon=False, markerscale=2)
```

### Benchmark comparison (bar chart)

```python
methods = ["Baseline", "scVI", "scANVI", "Our method"]
scores = [0.72, 0.81, 0.85, 0.87]
ax.bar(methods, scores, color='steelblue', edgecolor='black', linewidth=0.5)
ax.set_ylabel("ARI")
ax.set_ylim(0.6, 1.0)  # zoom to relevant range
ax.axhline(0.7, color='red', linestyle='--', linewidth=0.5, label='Pass threshold')
ax.legend(frameon=False)
```

---

## Caption Discipline

A good caption answers: *What is this plot? What do the axes mean? What is the main message?*

```markdown
**Figure 1. scRNA-seq integration with scVI.**
UMAP of 50,000 cells from 3 batches after scVI integration.
Color: cell type (annotated with scANVI).
The model successfully merges batches while preserving cell-type structure (ARI = 0.85).
```

---

## Pitfalls & fixes

| Symptom / mistake | Cause | Fix |
|-------------------|-------|-----|
| `pdffonts` shows Type 3 | `pdf.fonttype=42` not set (matplotlib's default is 3) | Add the rcParams block at the top; verify with `assert_no_type3` |
| Font check says FAIL on a good PDF | Grepping for the string `Type 42` — `pdffonts` prints `CID TrueType` | Test for the *presence of Type 3*, not the absence of "Type 42" |
| `pdffonts: command not found` | poppler is a system tool, not in `task1–4` | Use the pure-Python `assert_no_type3` |
| Text isn't Arial despite the rcParam | Arial/Helvetica not installed; matplotlib walked the list to DejaVu Sans, silently | Check `fontManager.ttflist`; install the font if the journal requires it |
| Labels overlap / text too small | `tight_layout()` not called, axes too small, or default font size (10–12 pt) | `plt.tight_layout()` before save, enlarge figsize; rcParams (7 pt body, 6 pt ticks) |
| Legend obscures data | Auto-placement failed | Set `loc='upper right'`, or place outside with `bbox_to_anchor=(1.05, 1)` |
| Empty quadrant / wasted canvas | Data doesn't span the axes | Crop with `ax.set_xlim` / `ax.set_ylim` |
| Colors uninterpretable | Colormap without a colorbar | Always add a colorbar |
| Not publication-quality | Saved as PNG, or used a 3D plot | Save PDF / SVG (vector); avoid 3D plots |

---

## Evidence & Reporting

Every figure emits:
- The figure file (`.pdf` preferred)
- The generation script (`gen_figure.py`)
- The data source (which `.h5ad` / `.npy` / `.csv` was plotted)
- The Type-3 check result, and **which font was actually embedded** (not which one you asked for)
- The 300 DPI PNG render (for visual audit)

Inspect the figure before it backs a claim. The script + data source are the reproducibility trail.
