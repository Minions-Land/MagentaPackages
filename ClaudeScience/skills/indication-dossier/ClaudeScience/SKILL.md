---
name: indication-dossier
description: >
  Generate a therapeutic indication dossier. Covers the patient population,
  epidemiology, disease biology, standard of care, regulatory precedent, and
  landmark clinical trials.
license: Apache-2.0
---

# Indication Dossier

Produces a structured research dossier on a single indication, framed as a
patient population: who they are, what's wrong, how they're treated today,
and how clinical trials can be designed to help them. Runs as five phases
that write resumable waypoint files; after a brief identity check at the end
of Phase 1, the remaining phases run straight through.

## Framing

**Think of an indication as a patient population.** Frame everything
from the patient perspective: "Who are these patients?" not "What is this
disease?"; "How are these patients identified and managed?" not "What causes
this condition?"; population nesting: "all patients in {child} are patients
in {parent}".

Some indications don't map to ICD codes or standard disease definitions:
"immunosenescence" is a biological state, not a billable diagnosis; "ageing"
is not an FDA-accepted indication; "GLP-1 induced sarcopenia" is an
iatrogenic population. Note these distinctions explicitly. They matter for
regulatory path and trial design.

## Inputs

- **`indication`** (required) — indication name (e.g., "sarcopenia",
  "idiopathic pulmonary fibrosis").
- **`additional_context`** (optional) — areas to focus on, parent
  indication, or other framing.
- **`workdir`** (optional) — where to write waypoints and the final report.
  Defaults to `./do_not_commit/indication-dossier-<slug>/`.

## Tools and fallbacks

| Purpose | Tool |
|---|---|
| ClinicalTrials.gov | Optional `clinical-trials` MCP; otherwise `WebSearch` on clinicaltrials.gov |
| Literature | Optional `pubmed` MCP; otherwise `WebSearch` on pubmed.ncbi.nlm.nih.gov |
| Web | `WebSearch`, `WebFetch` — FDA guidance, treatment guidelines (NCCN, AASLD, specialty societies), CDC/WHO epidemiology data |
| Documents | `WebFetch` for HTML/text; use `bash` to download PDFs, then extract text or render PNGs locally; inspect PNGs with `read` |
| Subagents | Optional `sub_agent` for independent evidence threads; otherwise research sequentially |

If a listed MCP isn't connected, say so and fall back to `WebSearch` against
the underlying public source (clinicaltrials.gov, pubmed.ncbi.nlm.nih.gov).

## Output layout

```
<workdir>/
└── waypoints/
    ├── progress.json                 # loop control
    ├── meta.json                     # phase 1
    ├── epidemiology.json             # phase 2
    ├── biology_soc.json              # phase 3
    ├── regulatory_trials.json        # phase 4
    ├── sources_evaluated.json
    ├── research_output.json          # phase 5 — structured output
    └── indication_dossier_report.md  # phase 5 — the deliverable
```

Schemas for every waypoint file are in `references/waypoint-schemas.md`.
Waypoints are the resumable state. If the workdir already has waypoints, read
them, summarize what's done, and ask which phase to resume from.

## Before starting

Read `references/00-research-standards.md`. It governs sourcing and the
anti-fabrication rules for every phase. Then create `<workdir>/waypoints/`.

## Workflow

The dossier is built in five phases. After each phase, write the waypoint
file and emit a ≤200-word summary of what you found and what's uncertain,
then proceed directly to the next phase. The one exception is Phase 1: after
writing `meta.json`, show the resolved indication identity and ask the user to
**Proceed**, **Revise identity**, or **Stop**. End the current turn and wait for
the answer before Phase 2 so a misread indication name cannot propagate.

### Phase 1 — Meta initialization

Read `references/01-meta-initialization.md`. Resolve the indication identity:
clinical definition, ICD codes, aliases, parent indication, and whether it's
a recognized diagnostic entity. Run a quick CT.gov landscape scan. Stand up
`waypoints/meta.json`.

### Phase 2 — Epidemiology research

Read `references/02-epidemiology-research.md`. Characterize the population:
diagnostic criteria, prevalence and incidence, demographics and risk factors,
natural history. When useful, use configured `sub_agent` workers for
independent PubMed and web searches; otherwise run the searches sequentially.
Write `waypoints/epidemiology.json`.

### Phase 3 — Biology & standard-of-care research

Read `references/03-biology-soc-research.md`. Establish pathophysiology,
biomarkers, approved therapies, treatment guidelines, and unmet need. When
useful, use configured `sub_agent` workers for independent biology, guideline,
and approval searches; otherwise research sequentially. Write
`waypoints/biology_soc.json`.

### Phase 4 — Regulatory & trials research

Read `references/04-regulatory-trials-research.md`. Establish FDA/EMA
accepted endpoints, regulatory precedents, typical trial design parameters,
landmark trials, and notable failures. When useful, use configured `sub_agent`
workers for independent FDA, CT.gov, and PubMed searches; otherwise research
sequentially. Write `waypoints/regulatory_trials.json`.

### Phase 5 — Synthesis

Read `references/05-synthesis.md` and `references/06-writing-style.md`. Read
all four consolidated waypoint files. Write
`waypoints/indication_dossier_report.md` — narrative sections in the order
the synthesis reference specifies, with inline citations per the style guide
— and `waypoints/research_output.json`. No new research threads in this
phase. Targeted gap-fills are allowed: a single fetch to resolve a specific
missing value in an existing waypoint field (an approval year, an NCT ID, a
figure from a sponsor pipeline page). Anything broader than that, name as a
gap rather than filling it.

## Resuming

If invoked with a `workdir` that already contains waypoints: list which phases
are complete (waypoint file exists and is non-empty), show the meta summary,
and ask the user which phase to run next. Never overwrite an existing waypoint
without confirmation.
