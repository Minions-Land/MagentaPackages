# Reference — Druggability Annotation (Pharos / TTD)

**Maturity: REFERENCE** — no `omics_compute` subcommand: the libraries are already in the pinned `task1` env (select it with `modality="scrna"` — an environment selector, not a claim about your data), and you hand-write the script that calls them. Emit a `report` dict and cite its numbers.

Annotating dependency targets with druggability tiers to prioritize actionable vulnerabilities.

## Pharos target-development levels (TDL)

Pharos (from the NIH IDG program) classifies every human protein into a development tier:

| Tier | Meaning | Actionability |
|------|---------|---------------|
| **Tclin** | Has approved drugs with a known mechanism | Highest — repurposing-ready |
| **Tchem** | Has potent small-molecule ligands (not approved) | High — chemical matter exists |
| **Tbio** | Biology known, no drug/ligand yet | Medium — needs discovery |
| **Tdark** | Understudied ("dark") protein | Low — no tool compounds |

**Prioritization:** Tclin + Tchem = "druggable now"; Tbio = "druggable with effort"; Tdark = "not
currently actionable."

## Fetching from Pharos — GraphQL only

Pharos exposes **GraphQL at `https://pharos-api.ncats.io/graphql`**. There is no REST route: a
`GET /targets/{symbol}` returns **HTTP 404** (`Cannot GET /targets/EGFR`). The `pharos.nih.gov` web UI
is separately gated (403 to scripts) — the API host above is the one to call.

```python
import requests

PHAROS = "https://pharos-api.ncats.io/graphql"
_TDL_QUERY = "query targetTDL($sym: String!) { target(q: {sym: $sym}) { sym tdl fam } }"

def pharos_tdl(gene_symbol):
    """TDL tier for an HGNC symbol. None = Pharos has no such target. Anything else raises."""
    r = requests.post(PHAROS, json={"query": _TDL_QUERY, "variables": {"sym": gene_symbol}},
                      timeout=30)
    r.raise_for_status()                     # 4xx/5xx: a failure, not an answer
    payload = r.json()
    if "errors" in payload:                  # GraphQL can 200 with partial errors
        raise RuntimeError(f"Pharos GraphQL error for {gene_symbol}: {payload['errors']}")
    return (payload["data"]["target"] or {}).get("tdl")
```

Verified responses: `EGFR` → `Tclin`, `PRMT5` → `Tchem`, `C1orf141` → `Tdark`; an unknown symbol →
`{"data": {"target": null}}` at HTTP 200 → `None`; a malformed query → **HTTP 400** carrying
`{"errors": [...]}` and *no* `data` key.

That last case is the reason for `raise_for_status()`. Without it, `r.json()` parses the 400 body
happily and a `payload.get("data", {}).get("target")` lookup yields `None` — the *same* value as a
genuine "Pharos has never heard of this gene". Every API change, outage, and typo then reads as a
clean negative result.

> ### Never default a failed lookup to `Tdark`
>
> `Tdark` is not a null — it is the substantive conclusion *"nothing is known to bind this target"*.
> A `try: ... except: return "Tdark"` turns one 404 into "no druggable targets in this screen", a
> conclusion that looks entirely plausible and is entirely an artifact. Let the lookup fail; count the
> unannotated genes and put that count in the `report`.

**Gene symbols must be HGNC.** Pharos queries on the approved symbol, so an alias silently returns
`None` and is indistinguishable from a real miss. `GLUT1`, `HER2`, `p53` are aliases — the symbols are
`SLC2A1`, `ERBB2`, `TP53`. DepMap columns are `SYMBOL (EntrezID)`; strip the suffix before querying
(`col.split(" (")[0]`).

**Batch:** for thousands of genes, take the bulk TCRD (Target Central Resource Database) dump rather
than per-gene calls. Its documented home is `juniper.health.unm.edu/tcrd/download/`; that host
resolved but did not respond when this doc was written, so confirm it (or the
[unmtransinfo/TCRD](https://github.com/unmtransinfo/TCRD) build repo) before planning around it. If
you fall back to the API, respect its rate limits and record how many genes you queried.

## TTD (Therapeutic Target Database)

TTD (`db.idrblab.net/ttd`) provides target–drug relationships:

```python
ttd = pd.read_csv("ttd_target_drug.txt", sep="\t")
# Columns: Target_ID, Gene, Drug_Name, Highest_Status (Approved / Clinical Trial / ...)
approved_targets = set(ttd[ttd.Highest_Status == "Approved"].Gene)
```

## Combining dependency + druggability

`gene_effect` is **cell lines × genes**, and its columns carry Entrez suffixes (`depmap_loading.md`):

```python
# selective_candidates: gene_effect column labels, e.g. 'EGFR (1956)' (dependency_analysis.md)
dep_freq = (gene_effect.loc[gene_effect.index.intersection(cancer_lines), selective_candidates]
            < -0.5).mean(axis=0)                     # axis=0 → fraction of LINES, per gene

tdl = {c: pharos_tdl(c.split(" (")[0]) for c in selective_candidates}

actionable = pd.DataFrame({
    "gene": selective_candidates,
    "dependency_freq": [dep_freq[c] for c in selective_candidates],
    "tdl": [tdl[c] for c in selective_candidates],
})
n_unannotated = actionable.tdl.isna().sum()          # report this — it is not zero
priority = (actionable[actionable.tdl.isin(["Tclin", "Tchem"])]
            .sort_values("dependency_freq", ascending=False))
```

`isin([...])` drops `None` rows, which is correct — but only because the `None`s now mean "Pharos has
no such target" and nothing else. Report `n_unannotated` alongside the priority list so a shrunken
candidate set is visible rather than inferred.

## Interpreting the priority list

A gene that is **selectively dependent** AND **Tclin** (has an approved drug) is a **drug-repurposing
candidate** — an existing drug, a new indication. That is the highest-value finding.

A **Tdark** selective dependency is novel biology, not an immediate lead.

## Pitfalls

- **Defaulting a failed lookup to `Tdark`** — manufactures "nothing is druggable"; fail loud instead
- **Conflating "not in Pharos" with "the request failed"** — `raise_for_status()`, then check `errors`
- **Aliases instead of HGNC symbols** — `GLUT1`/`HER2` silently return `None`; use `SLC2A1`/`ERBB2`
- **Expecting a REST endpoint** — `GET /targets/{sym}` 404s; Pharos is GraphQL
- **Treating Tbio as druggable** — biology is known, chemical matter is not
- **Per-gene API for thousands of genes** — use the bulk TCRD dump; respect rate limits
- **Stale TTD status** — approvals change; record the download date
- **"Has a drug" ≠ "a drug for this cancer"** — an approved drug for target X may not be indicated here

## Grounding

`report`: druggability source (Pharos TDL, query date / TTD version), n genes queried, **n
unannotated**, tier distribution, and the prioritized list with gene + dependency frequency + tier +
any approved drug.

## Sources
- Pharos API: `pharos-api.ncats.io/graphql` (IDG program) · UI: pharos.nih.gov
- TCRD: [unmtransinfo/TCRD](https://github.com/unmtransinfo/TCRD)
- TTD: db.idrblab.net/ttd · DrugBank: go.drugbank.com (licence required for bulk)
