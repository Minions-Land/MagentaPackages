# Phase 4 — Regulatory & trials research

**When:** `waypoints/biology_soc.json` exists, `waypoints/regulatory_trials.json` doesn't.

## Objective

Understand how to run clinical trials for this indication: what endpoints
regulators accept, what trials have shaped the field, and what failed.
This covers Sections 4 (Regulatory Path) and 5 (Key Trials).

## Actions

**Step 1: FDA/EMA accepted endpoints**
- WebSearch site:fda.gov for guidance documents specific to this indication
  (e.g., `"FDA guidance" "[indication]" clinical trial endpoints`)
- Identify primary endpoints used in successful registrational trials
- Distinguish: clinical endpoints vs. surrogate endpoints vs. PROs
- Note any endpoints that are "reasonably likely to predict clinical benefit"
  (accelerated approval pathway)
- For indications without FDA guidance: note this — it means novel regulatory territory

**Step 2: Regulatory precedents**
- WebSearch site:fda.gov for approval packages related to this indication
- What endpoints led to approval? What trial designs were accepted?
- Any breakthrough therapy designations, fast track, or priority review precedents?
- Relevant advisory committee discussions or Complete Response Letters

**Step 3: Trial design parameters**
- If a ClinicalTrials.gov MCP is connected, use its advertised schema to search
  Phase 3 trials; otherwise use `WebSearch` against clinicaltrials.gov
- Typical trial sizes (enrollment targets)
- Typical trial durations (primary endpoint assessment timepoints)
- Common comparator arms (placebo, active comparator, SOC)
- Estimate per-patient costs if available from literature

**Step 4: Landmark trials**
- Identify the 3-5 most important trials that shaped current SOC
- For each: NCT ID, drug, sponsor, phase, key results, impact on practice
- Search available ClinicalTrials.gov and PubMed/literature MCPs for these
  trials; use the corresponding public sites through `WebSearch` when absent
- For active sponsors in this indication, WebFetch their `/investors/presentations`
  or `/pipeline` page and pull recent conference decks; download them, render
  relevant pages to PNG, and inspect the PNGs with `read` (slide decks are
  figure-first)

**Step 5: Notable failures**
- Identify significant clinical trial failures in this indication
- What mechanism/approach was tested? Why did it fail?
- Lessons learned that inform future trial design
- Search an available PubMed/literature MCP for reviews of failed approaches;
  otherwise use `WebSearch` against pubmed.ncbi.nlm.nih.gov

**Step 6: Write `waypoints/regulatory_trials.json`**
Follow the schema from `references/waypoint-schemas.md`. Include `trial_landscape` counts.

## Guidance

- Regulatory path information varies enormously by indication maturity:
  - Well-established (e.g., IPF, MASH): detailed FDA guidance exists
  - Emerging (e.g., sarcopenia): limited or no formal guidance
  - Novel (e.g., ageing): no regulatory framework at all
- Be explicit about which category this indication falls into
- For landmark trials: prioritize trials that changed practice, not just
  the most recent ones
- For failures: focus on mechanism-level lessons, not just "this drug didn't work"
- When configured and useful, use `sub_agent` for independent regulatory,
  trial-pattern, and literature threads; otherwise run them sequentially
