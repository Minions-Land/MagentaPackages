# Reference — Metabolite / Lipid Annotation

**Maturity: mixed.** ID→info lookups run through the registered **`biofetch`** tool (grounded,
evidence recorded automatically). Name→ID search and LIPID MAPS are **REFERENCE** — hand-rolled
`requests` calls, because `biofetch` does not expose those operations.

Annotate metabolite/lipid IDs to names, formulas and pathways.

## Which route

`biofetch` wraps KEGG and PubChem, but only their **ID → record** operations:

| Step | Route | Why |
|---|---|---|
| KEGG ID → compound record (names, formula, pathways) | `biofetch_kegg_get(entry_id="cpd:C00249")` | grounded; evidence recorded |
| PubChem CID → properties (formula, weight, names) | `biofetch_pubchem_compound(cid="985")` | grounded; evidence recorded |
| **name → KEGG ID / PubChem CID** | hand-rolled REST (below) | `kegg_find` / `pubchem_search_by_name` are **not** exposed over MCP |
| LIPID MAPS ID → lipid record | hand-rolled REST (below) | not in `biofetch` |
| HMDB ID → record | **no working programmatic route** — see below | |

So a metabolomics table that starts from **names** needs one hand-rolled search call to get an ID,
then goes through `biofetch` for the record itself. Do not hand-roll the second step.

## Name → ID (REFERENCE)

```python
import requests

def pubchem_cids(name):
    """All CIDs for a name. [] = genuinely unknown; anything else raises."""
    r = requests.get(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/cids/JSON",
                     timeout=10)
    if r.status_code == 404:
        return []                       # PubChem's "no such compound" — a real answer
    r.raise_for_status()                # 5xx / rate-limit: a failure, not an empty result
    return r.json()["IdentifierList"]["CID"]

def kegg_compound_ids(name):
    """All KEGG compound ids for a name. [] = genuinely unknown; anything else raises."""
    r = requests.get(f"https://rest.kegg.jp/find/compound/{name.replace(' ', '+')}", timeout=10)
    r.raise_for_status()                # KEGG returns 200 + empty body for "not found"
    # tab-separated "C00249\tHexadecanoic acid; Palmitic acid; ..." — first field is the id
    return [line.split("\t")[0] for line in r.text.strip().splitlines() if line]
```

**Do not collapse "not found" and "the request failed" into the same value.** A `None`-on-any-error
wrapper makes a rate-limited run look like a table of unknown metabolites, and the annotation step
reports 0% coverage as if that were the data. Let transport errors raise; return an empty list only
when the database actually said "no match".

Returning **all** candidates rather than the first is deliberate — see the ambiguity note below.

Name search is **ambiguous by construction**: `find/compound/palmitic acid` also returns
`C11849` (3-hydroxy-palmitic acid methyl ester) and `C13948` (16-fluoropalmitic acid). Taking the
first hit is a guess — prefer matching on **InChIKey** when the platform reports one, and report how
many candidates each name returned.

## ID → record (READY, via `biofetch`)

```
biofetch_kegg_get(entry_id="cpd:C00249")        # names, formula, and the PATHWAY block
biofetch_pubchem_compound(cid="985")            # formula, weight, IUPAC name
```

`kegg_get` on a compound returns its `PATHWAY` block — that is where the pathway annotation the
`report` asks for comes from; there is no separate enrichment step in this doc.

## LIPID MAPS (REFERENCE)

```python
def lipidmaps_record(lmid):
    """LIPID MAPS record for an LM_ID. None = no such id; anything else raises."""
    r = requests.get(f"https://www.lipidmaps.org/rest/compound/lm_id/{lmid}/all/json", timeout=10)
    if r.status_code == 404:
        return None                     # a real answer
    r.raise_for_status()                # 5xx / rate-limit: a failure, not an empty record
    return r.json()
# Verified fields: lm_id, name, sys_name, synonyms, abbrev ("FA 16:0"), core ("Fatty Acyls [FA]"),
# main_class — `abbrev` is the shorthand that matches lipid_nomenclature.md's parser.
```

`r.json() if r.ok else None` is the same trap this doc warns about two sections down: it maps a 503, a
429 and a genuine miss onto one value, so a rate-limited run reports a table of unannotated lipids and
looks exactly like a real result.

## HMDB has no usable REST route

`https://hmdb.ca/metabolites/HMDB0000122.json` is **behind Cloudflare and returns HTTP 403** with a
browser challenge page, not JSON. A `requests.get(...)` + `if r.ok` wrapper therefore returns `None`
on **every** call, and an "offline fallback" hides that as "network unavailable" — the lookup never
worked, it just failed quietly.

If you have HMDB IDs, either:
- map them to PubChem/KEGG through the InChIKey your platform reports, then use `biofetch`; or
- obtain HMDB's XML dump from hmdb.ca under their licence and query it locally.

Do not write a live HMDB REST call and treat its failure as an offline condition.

## HMDB ID normalisation

Legacy IDs are 5-digit (`HMDB00122`), current ones are 7-digit (`HMDB0000122`). Normalise before any
join, or the same metabolite appears twice:

```python
import re

def normalize_hmdb(hmdb_id):
    """HMDB00122 / HMDB0000122 / hmdb122 -> HMDB0000122. Raises on anything that isn't an HMDB id."""
    m = re.fullmatch(r"HMDB(\d+)", str(hmdb_id).strip().upper())
    if not m:
        raise ValueError(f"not an HMDB id: {hmdb_id!r}")
    return f"HMDB{int(m.group(1)):07d}"

# A metabolomics id column routinely mixes namespaces. Split by namespace, don't map the rest to None:
is_hmdb = df.id.str.upper().str.fullmatch(r"HMDB\d+")
df.loc[is_hmdb, "hmdb"] = df.loc[is_hmdb, "id"].map(normalize_hmdb)
```

> ### Never let this return `None` into a join key
>
> `return None` looks like the safe choice here. It is the opposite: **pandas matches `None` to `None`
> in a merge.** Every identifier that isn't HMDB — a KEGG `C00031`, a LIPID MAPS `LMFA01010001`, a
> typo — collapses to the same `None` key and then **cross-joins with every `None` on the other side**.
>
> Measured: 4 left rows (1 real HMDB + 3 other-namespace) merged against 3 right rows (1 real + 2
> unparseable) returns **7 rows — one correct and six fabricated annotations**. It is N×M, it grows
> with the table, and it produces *more* data rather than less, so nothing about the output looks
> wrong. This is the failure mode `normalize_hmdb` exists to prevent, in a worse form: the docstring
> that motivates it says "normalise before any join, or the same metabolite appears twice".

## Pitfalls

- **Treating a 403/challenge page as "offline"** — HMDB's REST is not a network flake; it is gated.
- **Taking the first name-search hit** — several compounds share a name fragment; report the
  candidate count and prefer InChIKey matching.
- **Legacy vs new HMDB ID mismatch** — normalise first (above).
- **A `None` in a join key** — pandas matches `None` to `None`, so every unparseable id cross-joins
  with every other one and fabricates N×M annotations. Raise, or split by namespace first.
- **Hand-rolling the ID → record call** — `biofetch_kegg_get` / `biofetch_pubchem_compound` record
  evidence for you; a raw `requests.get` does not.
- **Trusting the API response shape** — validate before indexing; PubChem renamed
  `CanonicalSMILES` to `ConnectivitySMILES`, so a hardcoded key can silently KeyError.

## Grounding

`report`: annotation source per feature (`biofetch_kegg_get` / `biofetch_pubchem_compound` /
LIPID MAPS / unmapped), n features annotated vs n input, n names that returned multiple candidates,
and the pathway ids taken from KEGG's `PATHWAY` block. `biofetch` calls are captured automatically;
cite them.
