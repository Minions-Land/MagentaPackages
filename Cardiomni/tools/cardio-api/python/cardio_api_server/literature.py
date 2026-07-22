"""Atomic literature & database query capabilities for cardio-api.

Design principle (Bitter Lesson): each function is a STRICTLY ATOMIC capability
— one data source, single responsibility, structured output. Cross-source
orchestration (which source to try, how to fall back, how to dedupe/merge,
DOI cross-checking) is left to the LLM agent, NOT baked in here. Every function
degrades gracefully on network failure: it returns {"error": ..., "source": ...}
instead of raising, so an agent can read the failure and decide the next step.

Sources (all free, public, no API key required):
  - PubMed (NCBI E-utilities)      — biomedical abstracts, MeSH-indexed
  - Europe PMC                     — broader: abstracts + full text + preprints + guidelines
  - ClinicalTrials.gov (API v2)    — clinical trials (landmark cardiovascular RCTs)
  - Crossref                       — DOI metadata resolution, citation counts
  - Semantic Scholar (Graph API)   — semantic ranking, citation graph

Each returns: {"source", "query", "count", "results": [...]} on success,
or {"source", "query", "error", "hint"} on failure.
"""

import json
from typing import Any
from urllib import request, parse, error

# Polite identification for public APIs (Crossref/Europe PMC etiquette).
_USER_AGENT = "Cardiomni-cardio-api/0.1 (cardiovascular research agent; mailto:cardiomni@example.org)"
_DEFAULT_TIMEOUT = 30


def _http_get_json(url: str, timeout: int = _DEFAULT_TIMEOUT) -> Any:
    """GET a URL and parse JSON. Raises on failure; callers wrap for graceful handling."""
    req = request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _net_error(source: str, query: str, exc: Exception) -> dict[str, Any]:
    """Uniform graceful-failure payload so the agent can decide the next rung itself.

    Distinguishes rate-limiting (429, retry/switch source) from network outage so
    the orchestrating agent picks the right recovery. This tool is atomic; it never
    retries or falls back internally — that is the agent's job.
    """
    msg = str(exc)
    if "429" in msg or "Too Many Requests" in msg:
        hint = (f"{source} rate-limited this request (HTTP 429). This source throttles "
                f"unauthenticated traffic. Either back off and retry, or query a different "
                f"source (e.g. pubmed_search / europepmc_search) — the agent orchestrates fallback.")
    else:
        hint = (f"{source} query failed (likely no network connectivity). Try another source "
                f"(this tool is atomic; the agent orchestrates fallback).")
    return {
        "source": source,
        "query": query,
        "error": msg,
        "hint": hint,
        "results": [],
        "count": 0,
    }


def _cap(n: Any, default: int = 10, hard_max: int = 25) -> int:
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, hard_max))


# --------------------------------------------------------------------------- #
# 1. PubMed (NCBI E-utilities)
# --------------------------------------------------------------------------- #
def pubmed_search(query: dict[str, Any]) -> dict[str, Any]:
    """Search PubMed via E-utilities esearch + esummary. Abstracts via efetch on request."""
    term = query.get("query", "")
    max_results = _cap(query.get("max_results", 10))
    if not term:
        return {"source": "pubmed", "error": "Provide 'query' parameter"}

    try:
        esearch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + parse.urlencode(
            {"db": "pubmed", "term": term, "retmode": "json", "retmax": max_results}
        )
        pmids = _http_get_json(esearch).get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return {"source": "pubmed", "query": term, "count": 0, "results": []}

        esummary = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + parse.urlencode(
            {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
        )
        summary = _http_get_json(esummary).get("result", {})

        results = []
        for pmid in pmids:
            a = summary.get(pmid, {})
            if not a:
                continue
            doi = next((x.get("value") for x in a.get("articleids", []) if x.get("idtype") == "doi"), None)
            results.append({
                "pmid": pmid,
                "title": a.get("title", ""),
                "authors": [au.get("name", "") for au in a.get("authors", [])[:5]],
                "journal": a.get("source", ""),
                "pubdate": a.get("pubdate", ""),
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        return {"source": "pubmed", "query": term, "count": len(results), "results": results}
    except Exception as e:  # noqa: BLE001 — graceful degradation is the contract
        return _net_error("pubmed", term, e)


# --------------------------------------------------------------------------- #
# 2. Europe PMC — broader coverage (full text, preprints, guidelines)
# --------------------------------------------------------------------------- #
def europepmc_search(query: dict[str, Any]) -> dict[str, Any]:
    """Search Europe PMC REST API. Wider than PubMed: preprints, patents, guidelines, OA full text."""
    term = query.get("query", "")
    max_results = _cap(query.get("max_results", 10))
    if not term:
        return {"source": "europepmc", "error": "Provide 'query' parameter"}

    try:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + parse.urlencode(
            {"query": term, "format": "json", "pageSize": max_results, "resultType": "core"}
        )
        data = _http_get_json(url)
        results = []
        for r in data.get("resultList", {}).get("result", []):
            results.append({
                "id": r.get("id"),
                "source_db": r.get("source"),  # MED, PMC, PPR (preprint), etc.
                "pmid": r.get("pmid"),
                "doi": r.get("doi"),
                "title": r.get("title", ""),
                "authors": r.get("authorString", ""),
                "journal": r.get("journalTitle", "") or r.get("bookOrReportDetails", {}).get("publisher", ""),
                "pubYear": r.get("pubYear", ""),
                "isOpenAccess": r.get("isOpenAccess", "N") == "Y",
                "citedByCount": r.get("citedByCount", 0),
                "abstract": (r.get("abstractText", "") or "")[:1200],
            })
        return {"source": "europepmc", "query": term,
                "count": len(results),
                "total_available": data.get("hitCount", len(results)),
                "results": results}
    except Exception as e:  # noqa: BLE001
        return _net_error("europepmc", term, e)


# --------------------------------------------------------------------------- #
# 3. ClinicalTrials.gov (API v2) — landmark cardiovascular RCTs
# --------------------------------------------------------------------------- #
def clinicaltrials_search(query: dict[str, Any]) -> dict[str, Any]:
    """Search ClinicalTrials.gov v2 for trials. Key for guideline-grade CV evidence
    (SYNTAX, FAME, COURAGE, ISCHEMIA, EXCEL, etc.)."""
    term = query.get("query", "")
    max_results = _cap(query.get("max_results", 10))
    if not term:
        return {"source": "clinicaltrials", "error": "Provide 'query' parameter (condition/intervention/keyword)"}

    try:
        params = {
            "query.term": term,
            "pageSize": max_results,
            "format": "json",
            "fields": "NCTId,BriefTitle,OverallStatus,Phase,Condition,InterventionName,"
                      "PrimaryCompletionDate,EnrollmentCount,StudyType",
        }
        url = "https://clinicaltrials.gov/api/v2/studies?" + parse.urlencode(params)
        data = _http_get_json(url)
        results = []
        for study in data.get("studies", []):
            proto = study.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            cond = proto.get("conditionsModule", {})
            arms = proto.get("armsInterventionsModule", {})
            nct = ident.get("nctId", "")
            results.append({
                "nct_id": nct,
                "title": ident.get("briefTitle", ""),
                "status": status.get("overallStatus", ""),
                "phase": design.get("phases", []),
                "study_type": design.get("studyType", ""),
                "conditions": cond.get("conditions", []),
                "interventions": [i.get("name", "") for i in arms.get("interventions", [])],
                "enrollment": design.get("enrollmentInfo", {}).get("count"),
                "url": f"https://clinicaltrials.gov/study/{nct}" if nct else None,
            })
        return {"source": "clinicaltrials", "query": term,
                "count": len(results),
                "total_available": data.get("totalCount", len(results)),
                "results": results}
    except Exception as e:  # noqa: BLE001
        return _net_error("clinicaltrials", term, e)


# --------------------------------------------------------------------------- #
# 4. Crossref — DOI metadata resolution + citation counts
# --------------------------------------------------------------------------- #
def crossref_lookup(query: dict[str, Any]) -> dict[str, Any]:
    """Resolve a DOI to metadata, OR search Crossref by free text.
    Use `doi` for exact resolution (citation-audit), or `query` for search."""
    doi = query.get("doi", "").strip()
    term = query.get("query", "").strip()
    max_results = _cap(query.get("max_results", 10))

    try:
        if doi:
            url = f"https://api.crossref.org/works/{parse.quote(doi, safe='')}"
            item = _http_get_json(url).get("message", {})
            return {"source": "crossref", "doi": doi, "count": 1 if item else 0,
                    "results": [_crossref_item(item)] if item else []}
        if term:
            url = "https://api.crossref.org/works?" + parse.urlencode(
                {"query": term, "rows": max_results}
            )
            items = _http_get_json(url).get("message", {}).get("items", [])
            return {"source": "crossref", "query": term, "count": len(items),
                    "results": [_crossref_item(i) for i in items]}
        return {"source": "crossref", "error": "Provide 'doi' (exact resolve) or 'query' (search)"}
    except Exception as e:  # noqa: BLE001
        return _net_error("crossref", doi or term, e)


def _crossref_item(item: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for a in item.get("author", [])[:5]:
        name = " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
        if name:
            authors.append(name)
    date_parts = (item.get("issued", {}).get("date-parts", [[None]]) or [[None]])[0]
    return {
        "doi": item.get("DOI", ""),
        "title": (item.get("title", [""]) or [""])[0],
        "authors": authors,
        "journal": (item.get("container-title", [""]) or [""])[0],
        "year": date_parts[0] if date_parts else None,
        "type": item.get("type", ""),
        "citation_count": item.get("is-referenced-by-count", 0),
        "url": item.get("URL", ""),
    }


# --------------------------------------------------------------------------- #
# 5. Semantic Scholar (Graph API) — semantic ranking + citation graph
# --------------------------------------------------------------------------- #
def semantic_scholar_search(query: dict[str, Any]) -> dict[str, Any]:
    """Search Semantic Scholar Graph API. Good for semantic ranking and citation counts."""
    term = query.get("query", "")
    max_results = _cap(query.get("max_results", 10))
    if not term:
        return {"source": "semantic_scholar", "error": "Provide 'query' parameter"}

    try:
        fields = "title,authors,year,venue,abstract,citationCount,externalIds,openAccessPdf"
        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + parse.urlencode(
            {"query": term, "limit": max_results, "fields": fields}
        )
        data = _http_get_json(url)
        results = []
        for p in data.get("data", []):
            ext = p.get("externalIds", {}) or {}
            oa = p.get("openAccessPdf") or {}
            results.append({
                "paper_id": p.get("paperId"),
                "title": p.get("title", ""),
                "authors": [a.get("name", "") for a in (p.get("authors") or [])[:5]],
                "year": p.get("year"),
                "venue": p.get("venue", ""),
                "doi": ext.get("DOI"),
                "pmid": ext.get("PubMed"),
                "citation_count": p.get("citationCount", 0),
                "open_access_pdf": oa.get("url"),
                "abstract": (p.get("abstract") or "")[:1200],
            })
        return {"source": "semantic_scholar", "query": term,
                "count": len(results),
                "total_available": data.get("total", len(results)),
                "results": results}
    except Exception as e:  # noqa: BLE001
        return _net_error("semantic_scholar", term, e)


# Registry of atomic literature capabilities: op-name -> handler.
# The agent picks which source(s) to call and how to combine/fall back.
LITERATURE_OPS = {
    "pubmed_search": pubmed_search,
    "europepmc_search": europepmc_search,
    "clinicaltrials_search": clinicaltrials_search,
    "crossref_lookup": crossref_lookup,
    "semantic_scholar_search": semantic_scholar_search,
}
