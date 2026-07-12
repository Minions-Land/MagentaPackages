# Research Standards

## Citation requirements

**Mandatory_Fields** — Every finding MUST include: `source_url` (direct URL to the primary source) · `source_type` (`ctgov` | `fda` | `ema` | `pubmed` | `preprint` | `patent` | `conference` | `company_ir` | `news` | `other`) · `quote` (verbatim text from the source supporting the claim). Findings missing these fields cannot be cited and will be flagged as incomplete.

**URL_Validation** — Only use URLs you successfully fetched or retrieved from MCP tools. NEVER construct or guess URLs. If a URL fails, note it in `anomaly_flags`. Academic journal links often break — try DOI resolver (`https://doi.org/[DOI]`).

## Anti-fabrication protocol

NEVER fabricate, infer, or guess: trial results or statistics · dates (approval, filing, completion) · prevalence or incidence figures · drug names or approval status · patent numbers or expiry dates.

When data cannot be found after checking the canonical primary source (Drugs@FDA for approvals, the sponsor pipeline page for mechanism/stage, ClinicalTrials.gov for trial details): note the gap in `anomaly_flags` · do NOT create placeholder findings · state "Not publicly available" rather than guessing.

## Tool guidance

**MCP_Preference** — Prefer MCP tools over generic web fetch when available — they're faster and return structured data. Use the available MCP tools for their specialized domains (clinical trials, literature, regulatory filings).

**PDF_Retrieval** — `WebSearch` results carry only the search-index snippet, never the PDF body. `WebFetch` handles HTML, JSON, and plain text; do not treat its lossy binary response as PDF extraction. Download a PDF with `bash` (for example, `curl -L -o file.pdf '<url>'`; single-quote URLs harvested from web content and only follow plain `https://` links without shell metacharacters). Extract its text with an available local Python PDF library or CLI. When figures or tables carry the data, render the relevant pages to PNG and inspect the PNGs with `read`; describe axes, trends, and key data points in the finding (e.g., "Figure 2 shows 68% ORR waterfall"). Clinical visuals worth this step: efficacy (waterfall, KM, spider, forest plots) · PK curves · AE tables · biomarker suppression/durability plots · pathway diagrams. Conference slide decks and posters are figure-first; default to download, render, and inspect rather than relying on `WebFetch`. To discover PDF links on an IR or guidelines page, `WebFetch` the page and parse the `[text](url)` markdown links; many PDF URLs are UUID paths like `/static-files/abc123` rather than ending in `.pdf`.

**Context_Discipline** — To avoid context overflow: summarize findings as you go — do not hold raw source text · after extracting data, immediately distill to structured output · for long documents, read table of contents/abstract first to target sections.

## Quality calibration

Distinguish "new to me" (your discovery process) from "new to the reader" (actual insight). Ask yourself, "Would a senior member of the field (5+ years) find this surprising or decision-relevant?". If yes, it is an insight. If no, it is context.
