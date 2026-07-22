"""MCP Server for Cardiovascular Reference Databases."""

import json
import os
from pathlib import Path
from typing import Any
from urllib import request, parse, error

from mcp.server import Server
from mcp.types import Tool, TextContent

from .literature import LITERATURE_OPS


# Load the clinical standards knowledge base at startup
DATA_DIR = Path(__file__).parent / "data"
CLINICAL_STANDARDS_PATH = DATA_DIR / "clinical_standards.json"

with open(CLINICAL_STANDARDS_PATH, "r") as f:
    CLINICAL_STANDARDS = json.load(f)


# Bundled cardiovascular ICD codes (simplified subset)
ICD_CODES = {
    "I20": {"code": "I20", "description": "Angina pectoris", "category": "Ischemic heart diseases"},
    "I21": {"code": "I21", "description": "Acute myocardial infarction", "category": "Ischemic heart diseases"},
    "I25": {"code": "I25", "description": "Chronic ischemic heart disease", "category": "Ischemic heart diseases"},
    "I25.1": {"code": "I25.1", "description": "Atherosclerotic heart disease of native coronary artery", "category": "Ischemic heart diseases"},
    "I25.10": {"code": "I25.10", "description": "Atherosclerotic heart disease without angina", "category": "Ischemic heart diseases"},
    "I25.11": {"code": "I25.11", "description": "Atherosclerotic heart disease with angina", "category": "Ischemic heart diseases"},
    "I25.2": {"code": "I25.2", "description": "Old myocardial infarction", "category": "Ischemic heart diseases"},
    "I25.5": {"code": "I25.5", "description": "Ischemic cardiomyopathy", "category": "Ischemic heart diseases"},
    "I25.7": {"code": "I25.7", "description": "Atherosclerosis of coronary artery bypass graft(s)", "category": "Ischemic heart diseases"},
    "I25.8": {"code": "I25.8", "description": "Other forms of chronic ischemic heart disease", "category": "Ischemic heart diseases"},
    "I50": {"code": "I50", "description": "Heart failure", "category": "Heart failure"},
    "I48": {"code": "I48", "description": "Atrial fibrillation and flutter", "category": "Arrhythmias"},
    "I70.0": {"code": "I70.0", "description": "Atherosclerosis of aorta", "category": "Atherosclerosis"},
}


# Bundled cardiovascular drug reference
DRUG_REFERENCE = {
    "aspirin": {
        "name": "Aspirin",
        "class": "Antiplatelet",
        "indication": "Prevention of thrombotic events in CAD, post-MI, post-PCI",
        "mechanism": "Irreversible COX-1 inhibition, reduces TXA2 production",
    },
    "clopidogrel": {
        "name": "Clopidogrel",
        "class": "Antiplatelet (P2Y12 inhibitor)",
        "indication": "Dual antiplatelet therapy (DAPT) with aspirin post-PCI/ACS",
        "mechanism": "Irreversible P2Y12 receptor antagonist",
    },
    "ticagrelor": {
        "name": "Ticagrelor",
        "class": "Antiplatelet (P2Y12 inhibitor)",
        "indication": "DAPT in ACS, post-PCI",
        "mechanism": "Reversible P2Y12 receptor antagonist",
    },
    "prasugrel": {
        "name": "Prasugrel",
        "class": "Antiplatelet (P2Y12 inhibitor)",
        "indication": "DAPT in ACS undergoing PCI",
        "mechanism": "Irreversible P2Y12 receptor antagonist (more potent than clopidogrel)",
    },
    "atorvastatin": {
        "name": "Atorvastatin",
        "class": "Statin (HMG-CoA reductase inhibitor)",
        "indication": "Lipid lowering, atherosclerosis prevention, post-MI",
        "mechanism": "Inhibits cholesterol synthesis, upregulates LDL receptors",
    },
    "rosuvastatin": {
        "name": "Rosuvastatin",
        "class": "Statin (HMG-CoA reductase inhibitor)",
        "indication": "Lipid lowering, atherosclerosis prevention",
        "mechanism": "Inhibits cholesterol synthesis, high potency",
    },
    "warfarin": {
        "name": "Warfarin",
        "class": "Anticoagulant (Vitamin K antagonist)",
        "indication": "Atrial fibrillation, mechanical valves, VTE",
        "mechanism": "Inhibits vitamin K-dependent clotting factors II, VII, IX, X",
    },
    "apixaban": {
        "name": "Apixaban",
        "class": "Anticoagulant (Direct Xa inhibitor)",
        "indication": "Atrial fibrillation, VTE",
        "mechanism": "Direct factor Xa inhibition",
    },
    "rivaroxaban": {
        "name": "Rivaroxaban",
        "class": "Anticoagulant (Direct Xa inhibitor)",
        "indication": "Atrial fibrillation, VTE, CAD (low dose)",
        "mechanism": "Direct factor Xa inhibition",
    },
    "metoprolol": {
        "name": "Metoprolol",
        "class": "Beta-blocker (selective β1)",
        "indication": "Post-MI, heart failure, hypertension, angina",
        "mechanism": "β1-adrenergic receptor antagonist, reduces heart rate and contractility",
    },
    "nitroglycerin": {
        "name": "Nitroglycerin",
        "class": "Nitrate vasodilator",
        "indication": "Angina relief, acute coronary syndromes",
        "mechanism": "NO donor, venous and arterial dilation, reduces preload",
    },
}


def standards_lookup(query: dict[str, Any]) -> dict[str, Any]:
    """Look up clinical grading standard definitions from bundled knowledge base."""
    standard = query.get("standard", "").lower()
    specific_grade = query.get("grade")

    if standard == "cad-rads" or standard == "cadrads":
        data = CLINICAL_STANDARDS.get("cad_rads", {})
        if specific_grade:
            grade_data = data.get("grades", {}).get(str(specific_grade))
            if grade_data:
                return {"standard": "CAD-RADS", "grade": specific_grade, "data": grade_data}
            return {"error": f"Grade {specific_grade} not found in CAD-RADS"}
        return {"standard": "CAD-RADS", "data": data}

    elif standard == "syntax":
        data = CLINICAL_STANDARDS.get("syntax_score", {})
        return {"standard": "SYNTAX Score", "data": data}

    elif standard == "timi-flow" or standard == "timi_flow":
        data = CLINICAL_STANDARDS.get("timi_flow", {})
        if specific_grade is not None:
            grade_data = data.get("grades", {}).get(str(specific_grade))
            if grade_data:
                return {"standard": "TIMI Flow", "grade": specific_grade, "description": grade_data}
            return {"error": f"Grade {specific_grade} not found in TIMI Flow"}
        return {"standard": "TIMI Flow", "data": data}

    elif standard == "timi-thrombus" or standard == "timi_thrombus":
        data = CLINICAL_STANDARDS.get("timi_thrombus", {})
        if specific_grade is not None:
            grade_data = data.get("grades", {}).get(str(specific_grade))
            if grade_data:
                return {"standard": "TIMI Thrombus", "grade": specific_grade, "description": grade_data}
            return {"error": f"Grade {specific_grade} not found in TIMI Thrombus"}
        return {"standard": "TIMI Thrombus", "data": data}

    elif standard == "rentrop":
        data = CLINICAL_STANDARDS.get("rentrop_collaterals", {})
        if specific_grade is not None:
            grade_data = data.get("grades", {}).get(str(specific_grade))
            if grade_data:
                return {"standard": "Rentrop Collaterals", "grade": specific_grade, "description": grade_data}
            return {"error": f"Grade {specific_grade} not found in Rentrop"}
        return {"standard": "Rentrop Collaterals", "data": data}

    elif standard == "acc-aha" or standard == "acc_aha":
        data = CLINICAL_STANDARDS.get("acc_aha_lesion_classification", {})
        return {"standard": "ACC/AHA Lesion Classification", "data": data}

    elif standard == "agatston":
        data = CLINICAL_STANDARDS.get("agatston_score", {})
        return {"standard": "Agatston Score", "data": data}

    elif standard == "high-risk-plaque" or standard == "hrp":
        hrp_features = CLINICAL_STANDARDS.get("cad_rads", {}).get("high_risk_plaque_features", [])
        return {"standard": "High-Risk Plaque Features", "features": hrp_features}

    else:
        return {
            "error": f"Unknown standard: {standard}",
            "available_standards": [
                "cad-rads", "syntax", "timi-flow", "timi-thrombus",
                "rentrop", "acc-aha", "agatston", "high-risk-plaque"
            ]
        }


def icd_lookup(query: dict[str, Any]) -> dict[str, Any]:
    """Look up cardiovascular ICD-10 codes from bundled table."""
    code = query.get("code", "").upper()
    search_term = query.get("search", "").lower()

    if code:
        result = ICD_CODES.get(code)
        if result:
            return {"query": code, "result": result}
        return {"error": f"ICD code {code} not found in cardiovascular subset"}

    elif search_term:
        matches = []
        for icd_code, data in ICD_CODES.items():
            if search_term in data["description"].lower() or search_term in data["category"].lower():
                matches.append(data)
        return {"query": search_term, "matches": matches, "count": len(matches)}

    else:
        return {"error": "Provide 'code' or 'search' parameter", "available_codes": list(ICD_CODES.keys())}


def drug_reference(query: dict[str, Any]) -> dict[str, Any]:
    """Look up cardiovascular drug reference from bundled table."""
    drug_name = query.get("drug", "").lower()
    drug_class = query.get("class", "").lower()

    if drug_name:
        result = DRUG_REFERENCE.get(drug_name)
        if result:
            return {"query": drug_name, "result": result}
        return {"error": f"Drug {drug_name} not found in cardiovascular reference"}

    elif drug_class:
        matches = []
        for name, data in DRUG_REFERENCE.items():
            if drug_class in data["class"].lower():
                matches.append({**data, "key": name})
        return {"query": drug_class, "matches": matches, "count": len(matches)}

    else:
        return {"error": "Provide 'drug' (name) or 'class' parameter", "available_drugs": list(DRUG_REFERENCE.keys())}


# Literature & database search is provided by 5 ATOMIC tools in literature.py
# (pubmed_search, europepmc_search, clinicaltrials_search, crossref_lookup,
# semantic_scholar_search). Each is one source, single responsibility; the agent
# orchestrates which to call and how to fall back / cross-check.


# Define the MCP server
app = Server("cardio-api")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available cardiovascular reference tools."""
    return [
        Tool(
            name="standards_lookup",
            description=(
                "Look up clinical grading standard definitions from local knowledge base. "
                "Supports: CAD-RADS (0-5 + modifiers), SYNTAX (segments, scoring, risk tiers), "
                "TIMI flow (0-3), TIMI thrombus (0-5), Rentrop collaterals (0-3), "
                "ACC/AHA lesion types (A/B1/B2/C), Agatston score categories, high-risk plaque features."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "standard": {
                        "type": "string",
                        "description": "Standard name: cad-rads, syntax, timi-flow, timi-thrombus, rentrop, acc-aha, agatston, high-risk-plaque",
                    },
                    "grade": {
                        "type": ["string", "number", "null"],
                        "description": "Optional: specific grade/score to retrieve (e.g., '3' for CAD-RADS 3)",
                    },
                },
                "required": ["standard"],
            },
        ),
        Tool(
            name="icd_lookup",
            description="Look up cardiovascular ICD-10 codes from bundled table. Search by code or term.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "ICD-10 code (e.g., 'I25.1')",
                    },
                    "search": {
                        "type": "string",
                        "description": "Search term in description or category (e.g., 'myocardial infarction')",
                    },
                },
            },
        ),
        Tool(
            name="drug_reference",
            description=(
                "Look up cardiovascular drug reference from bundled table. "
                "Includes antiplatelets, statins, anticoagulants, beta-blockers, nitrates."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "drug": {
                        "type": "string",
                        "description": "Drug name (e.g., 'aspirin', 'atorvastatin')",
                    },
                    "class": {
                        "type": "string",
                        "description": "Drug class (e.g., 'antiplatelet', 'statin')",
                    },
                },
            },
        ),
        # --- Literature & database search: 5 ATOMIC tools, one per source ---
        # Each is single-source, single-responsibility. The agent orchestrates
        # which to call, how to fall back, and how to cross-check DOIs.
        Tool(
            name="pubmed_search",
            description=(
                "Search PubMed (NCBI E-utilities) for biomedical literature. MeSH-indexed abstracts. "
                "Returns PMID, title, authors, journal, pubdate, DOI, URL. Network required; returns error payload if offline. "
                "Best for: peer-reviewed clinical/biomedical papers. Atomic — combine with other sources yourself."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "PubMed query (e.g., 'coronary CTA stenosis quantification')"},
                    "max_results": {"type": "number", "description": "Max results (default 10, hard cap 25)", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="europepmc_search",
            description=(
                "Search Europe PMC — broader than PubMed: peer-reviewed papers + preprints + guidelines + OA full text. "
                "Returns id, source_db (MED/PMC/PPR), pmid, doi, title, authors, journal, year, open-access flag, citation count, abstract. "
                "Network required. Best for: wide coverage incl. preprints and clinical guidelines. Atomic."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Europe PMC query (supports field syntax, e.g. 'SYNTAX score AND coronary')"},
                    "max_results": {"type": "number", "description": "Max results (default 10, hard cap 25)", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="clinicaltrials_search",
            description=(
                "Search ClinicalTrials.gov (API v2) for clinical trials — the source of guideline-grade cardiovascular evidence "
                "(landmark RCTs: SYNTAX, FAME, COURAGE, ISCHEMIA, EXCEL, ORBITA). "
                "Returns NCT ID, title, status, phase, study type, conditions, interventions, enrollment, URL. "
                "Network required. Best for: trial evidence behind revascularization / PCI-vs-CABG decisions. Atomic."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Condition/intervention/keyword (e.g., 'coronary artery disease PCI', 'FAME FFR')"},
                    "max_results": {"type": "number", "description": "Max results (default 10, hard cap 25)", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="crossref_lookup",
            description=(
                "Crossref: resolve a DOI to authoritative metadata (for citation verification), OR search by free text. "
                "Returns DOI, title, authors, journal, year, type, citation_count, URL. "
                "Network required. Best for: verifying/completing a citation from a known DOI, or citation counts. Atomic. "
                "Provide 'doi' for exact resolution, or 'query' for search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "doi": {"type": "string", "description": "Exact DOI to resolve (e.g., '10.1093/eurheartj/ehac...')"},
                    "query": {"type": "string", "description": "Free-text search (if no DOI)"},
                    "max_results": {"type": "number", "description": "Max results for query mode (default 10, hard cap 25)", "default": 10},
                },
            },
        ),
        Tool(
            name="semantic_scholar_search",
            description=(
                "Search Semantic Scholar Graph API — semantic ranking + citation graph. "
                "Returns paper_id, title, authors, year, venue, DOI, PMID, citation_count, open-access PDF, abstract. "
                "Network required. Best for: 'what's been done in area X' semantic discovery and finding highly-cited work. Atomic."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic/method query (e.g., 'deep learning coronary stenosis detection')"},
                    "max_results": {"type": "number", "description": "Max results (default 10, hard cap 25)", "default": 10},
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    if name == "standards_lookup":
        result = standards_lookup(arguments)
    elif name == "icd_lookup":
        result = icd_lookup(arguments)
    elif name == "drug_reference":
        result = drug_reference(arguments)
    elif name in LITERATURE_OPS:
        # 5 atomic literature/database tools: pubmed_search, europepmc_search,
        # clinicaltrials_search, crossref_lookup, semantic_scholar_search.
        result = LITERATURE_OPS[name](arguments)
    else:
        result = {"error": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def main():
    """Run the MCP server over stdio."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )
