---
kind: skill
name: diagnosis-analysis
source: Cardiomni
display_name: Cardiovascular Diagnosis Analysis
description: Autonomous CTA/DSA DICOM reading workflow for coronary artery disease diagnosis — anatomy identification, stenosis quantification, cross-modal fusion, CAD-RADS/SYNTAX scoring, clinical decision support with capability-boundary awareness.
version: 0.1.0
license: MIT
profiles: [imaging, clinical]
---

# Cardiovascular Diagnosis Analysis

This skill implements the autonomous clinical reading workflow for paired CTA+DSA coronary imaging. It guides the agent through the complete diagnostic chain from DICOM loading to evidence-anchored clinical decisions.

## Core Workflow: 5-Stage Clinical Reading

### Stage 0: Anatomy & Dominance

**Objective**: Establish coronary anatomy baseline before pathology assessment.

**Actions**:
1. Load CTA series: `cardio_imaging_tools.load_dicom_series(path)` → returns 3D volume with HU values, pixel spacing, slice thickness
2. Apply cardiac window: `cardio_imaging_tools.apply_cardiac_window(volume, preset="soft_tissue")` → enhances vessel contrast
3. Extract vessel centerlines: `cardio_imaging_tools.extract_vessel_centerlines(volume)` → identifies vessel topology
4. Determine dominance: identify PDA origin from RCA (right-dominant, 70%), LCx (left-dominant, 10%), or both (co-dominant, 20%)
5. Consult the bundled anatomy reference `assets/references/coronary_anatomy.md` (dominance classification, AHA/SYNTAX segment map). For SYNTAX segment weights use `cardiofetch_standards_lookup(standard="syntax")`.

**Output**: Coronary anatomy map with dominance type, vessel segments identified per AHA 17-segment model (or SYNTAX 16-segment refinement).

**Capability boundaries**: If severe tortuosity or anatomical variants prevent clear identification, document uncertainty. Consult `assets/references/coronary_anatomy.md` for variant patterns before declaring "anomalous"; if still unresolved, search the literature (`cardiofetch_pubmed_search`) rather than guessing.

### Stage 1a: CTA Perception

**Objective**: Identify stenoses, plaques, and calcification from CTA.

**Actions**:
1. Preprocess CTA: `cardio_imaging_tools.preprocess_cta(volume)` → standardizes HU, reduces noise
2. For each vessel segment:
   - Measure minimum lumen diameter at suspected stenosis: `cardio_imaging_tools.calculate_diameter_stenosis(volume, segment_id, method="diameter")`
   - Measure reference diameter from adjacent normal segment
   - Calculate stenosis percentage: `(1 - Dmin/Dref) × 100`
   - Document HU values: HU > 130 = calcified plaque, 30-130 = soft/mixed plaque
3. Note calcification severity: mild/moderate/heavy blooming (heavy blooming degrades CTA stenosis accuracy)
4. Consult the bundled reference `assets/references/stenosis_quantification_methods.md` for diameter/area method guidelines. For CAD-RADS stenosis grade bands use `cardiofetch_standards_lookup(standard="cad-rads")`.

**Output**: Per-segment stenosis percentages, plaque characterization (calcified/soft/mixed), calcification severity notes.

**Capability boundaries**: Heavy calcification (blooming artifact) → CTA may overestimate stenosis; flag for DSA confirmation. Non-diagnostic image quality (motion, contrast timing) → document limitation, proceed to DSA.

### Stage 1b: DSA Perception

**Objective**: Quantify stenoses from invasive angiography (gold standard for lumen).

**Actions**:
1. Load DSA cine: `cardio_imaging_tools.load_dsa_cine(path)` → multi-frame contrast sequence
2. Identify optimal projection angles per vessel (RAO/LAO/cranial/caudal) to avoid foreshortening
3. For each lesion:
   - Measure minimum lumen diameter at peak contrast opacification
   - Measure reference diameter from proximal/distal normal segment
   - Calculate stenosis: `cardio_imaging_tools.calculate_diameter_stenosis(frames, segment_id, method="qca")`
4. Assess TIMI flow grade (0=no flow, 1=penetrates but no distal fill, 2=slow, 3=normal)
5. For CTO lesions: document occlusion duration (if known), stump morphology, collateral grade (Rentrop 0-3)
6. Query flow grading criteria: `cardiofetch_standards_lookup(standard="timi-flow")` (add `grade=2` for a specific grade's definition)

**Output**: Per-lesion QCA stenosis percentages, TIMI flow grades, CTO characteristics.

**Capability boundaries**: Overlapping vessels in single projection → use orthogonal views; if still ambiguous, document uncertainty. Heavily calcified vessels may obscure DSA lumen → combine with CTA 3D anatomy.

### Stage 2: Cross-Modal Fusion

**Objective**: Synthesize CTA and DSA findings into unified assessment.

**Fusion rules**:
1. **Stenosis quantification**: 
   - If CTA and DSA agree (within ±10%) → report consensus
   - If CTA > DSA by >20% AND heavy calcification present → use DSA (calcium blooming correction)
   - If DSA unavailable for segment → use CTA with confidence qualifier
2. **Plaque characterization**: CTA provides tissue composition (HU values), DSA provides functional impact (flow)
3. **Lesion localization**: CTA 3D anatomy + DSA dynamic flow → precise SYNTAX segment assignment
4. **Collateral assessment**: DSA Rentrop grade + CTA vessel course → viability estimation for CTO territories

**Output**: Unified stenosis grade per segment, plaque nature, functional significance.

**Capability boundaries**: If modalities contradict beyond explainable artifacts, document discrepancy and recommend additional imaging (IVUS/OCT for ambiguous lesions, FFR-CT/invasive FFR for intermediate stenoses 40-70%).

### Stage 3: SYNTAX & CAD-RADS Scoring

**Objective**: Map findings to standardized clinical grading systems.

**CAD-RADS 2.0 grading** (per-lesion and per-patient):
- 0: No stenosis (0%)
- 1: Minimal (1-24%)
- 2: Mild (25-49%)
- 3: Moderate (50-69%)
- 4A: Severe single/dual-vessel (70-99%)
- 4B: Severe left main or three-vessel (>70%)
- 5: Total occlusion (100%)

**Per-patient grade** = highest individual lesion grade. Threshold for "significant stenosis" = ≥50% in vessel ≥1.5mm diameter.

Query: `cardiofetch_standards_lookup(standard="cad-rads")` (add `grade="3"` for one grade's definition)

**SYNTAX Score calculation** (only for lesions ≥50% in vessels ≥1.5mm):
1. Confirm dominance (from Stage 0) — **no balanced dominance** in SYNTAX
2. For each significant lesion:
   - Base score = segment weight × multiplier (×2 non-occlusive, ×5 occlusive)
   - Left main has highest weight
3. Add complexity modifiers:
   - CTO: +1 per CTO, +1 if blunt stump, +1 if side-branch involvement, +collateral grade adjustment
   - Bifurcation: +1 (bifurcation), +2 (trifurcation), classify by Medina notation
   - Additional: +1 each for ostial, severe tortuosity, length >20mm, heavy calcification, thrombus, diffuse disease
4. Sum all lesion scores → total SYNTAX score
5. Risk stratification: ≤22 (low), 23-32 (mid), ≥33 (high, favor CABG over PCI)

Query: `cardiofetch_standards_lookup(standard="syntax")` (returns segments, scoring, and risk tiers)

**Output**: Per-lesion CAD-RADS grades, per-patient CAD-RADS, total SYNTAX score with risk tier.

**Capability boundaries**: SYNTAX scoring requires angiographic expertise for feature recognition (e.g., Medina classification, CTO duration estimation). If features are ambiguous, score conservatively and flag uncertainty.

### Stage 4: Clinical Decision Support

**Objective**: Translate scores into evidence-based recommendations.

**Decision algorithm**:
1. **Revascularization need**:
   - CAD-RADS 0-2 → medical management
   - CAD-RADS 3 → functional testing (FFR, stress test) if symptomatic
   - CAD-RADS 4A-5 or left main ≥50% → revascularization consideration
   - SYNTAX low (≤22) → PCI reasonable
   - SYNTAX high (≥33) + multi-vessel → CABG preferred
2. **Additional testing triggers**:
   - Intermediate stenosis (40-70%) → FFR-CT or invasive FFR
   - Ambiguous plaque burden → IVUS/OCT
   - CTO with viable territory → viability study (PET, cardiac MRI)
   - Discordant CTA/DSA → hybrid imaging or repeat with optimized protocol
3. **Medical optimization**: Regardless of revascularization, optimize statin, antiplatelet, blood pressure, diabetes control

Retrieve guideline evidence from the literature rather than a hardcoded table: `cardiofetch_pubmed_search(query="2021 ACC/AHA coronary revascularization guideline")` or `cardiofetch_clinicaltrials_search(query="SYNTAX PCI CABG left main")` for the landmark trials (SYNTAX, EXCEL, NOBLE, FAME) behind the PCI-vs-CABG decision. Cross-check DOIs with `cardiofetch_crossref_lookup`.

**Output**: Clinical recommendation with evidence basis (guideline references), additional testing needs, medical therapy plan.

**Capability boundaries**: This is **decision support**, not autonomous prescription. Final treatment decisions require multidisciplinary heart team discussion, patient comorbidities, surgical risk assessment, and shared decision-making. Always state: "Recommendations are preliminary and require heart team review."

## Tool Reference

### cardio_imaging_tools (Python runtime)

```python
# Load DICOM data
load_dicom_series(path: str) -> Dict[str, Any]
# Returns: {volume: ndarray, hu_values: ndarray, pixel_spacing: tuple, slice_thickness: float, metadata: dict}

load_dsa_cine(path: str) -> Dict[str, Any]
# Returns: {frames: ndarray, frame_rate: float, pixel_spacing: tuple, metadata: dict}

# Preprocessing & windowing
apply_cardiac_window(volume: ndarray, preset: str = "soft_tissue") -> ndarray
# Presets: "soft_tissue" (W:400 L:40), "bone" (W:1500 L:450), "lung" (W:1500 L:-600)

preprocess_cta(volume: ndarray) -> ndarray
# Standardizes HU, reduces noise, enhances vessel contrast

# Vessel analysis
extract_vessel_centerlines(volume: ndarray) -> Dict[str, Any]
# Returns: {centerlines: List[ndarray], segment_ids: List[str], topology: dict}

# Stenosis quantification
calculate_diameter_stenosis(
    image_data: Union[ndarray, Dict], 
    segment_id: str, 
    method: str = "diameter"  # "diameter" or "area"
) -> Dict[str, float]
# Returns: {min_diameter: float, ref_diameter: float, stenosis_pct: float, confidence: float}

calculate_area_stenosis(volume: ndarray, segment_id: str) -> Dict[str, float]
# Returns: {min_area: float, ref_area: float, stenosis_pct: float}

# Synthetic data generation (for testing)
make_synthetic_dicom(
    modality: str,  # "CT" or "XA"
    output_path: str,
    stenosis_severity: float = 0.7,
    calcification: str = "moderate"
) -> str
# Returns: path to generated synthetic DICOM

# Evaluation against expert annotations
evaluate_against_expert(
    predicted: Dict[str, float],
    ground_truth: Dict[str, float],
    tolerance: float = 10.0
) -> Dict[str, Any]
# Returns: {accuracy: float, mae: float, per_segment_errors: dict}
```

### cardio_api (MCP server)

The cardio-api MCP server exposes 8 atomic tools (namespaced `cardiofetch_*`). LOCAL tools are offline and deterministic; LITERATURE tools need network and return an error payload (never crash) on failure or rate-limit — the agent orchestrates which source to call and how to fall back.

```python
# --- LOCAL (offline, bundled KB) ---

# Clinical grading standards. `standard` MUST be one of:
#   "cad-rads", "syntax", "timi-flow", "timi-thrombus",
#   "rentrop", "acc-aha", "agatston", "high-risk-plaque"
# Optional `grade` returns one grade's definition (cad-rads/timi-flow/timi-thrombus/rentrop).
cardiofetch_standards_lookup(standard: str, grade: str | int | None = None) -> Dict[str, Any]

# Cardiovascular drug reference. Provide `drug` (name) OR `class`.
cardiofetch_drug_reference(drug: str = None, class: str = None) -> Dict[str, Any]

# Cardiovascular ICD-10 codes. Provide `code` (exact) OR `search` (term).
cardiofetch_icd_lookup(code: str = None, search: str = None) -> Dict[str, Any]

# --- LITERATURE & TRIALS (network; each is a single atomic source) ---

# NCBI PubMed — MeSH-indexed biomedical abstracts.
cardiofetch_pubmed_search(query: str, max_results: int = 10) -> Dict[str, Any]

# Europe PMC — papers + preprints + guidelines + OA full text (wider than PubMed).
cardiofetch_europepmc_search(query: str, max_results: int = 10) -> Dict[str, Any]

# ClinicalTrials.gov v2 — landmark cardiovascular RCTs (SYNTAX, FAME, COURAGE, ISCHEMIA, EXCEL).
cardiofetch_clinicaltrials_search(query: str, max_results: int = 10) -> Dict[str, Any]

# Crossref — resolve a DOI to metadata (citation verification) OR free-text search.
cardiofetch_crossref_lookup(doi: str = None, query: str = None, max_results: int = 10) -> Dict[str, Any]

# Semantic Scholar — semantic ranking + citation graph (throttles unauthenticated traffic → may 429).
cardiofetch_semantic_scholar_search(query: str, max_results: int = 10) -> Dict[str, Any]
```

**Orchestration note (atomic-first design):** these tools do not fall back internally. When a literature source is rate-limited or offline, read the returned `hint` and call a different source yourself (e.g. PubMed → Europe PMC), then cross-check a DOI via `cardiofetch_crossref_lookup`. Never fabricate a citation, PMID, DOI, trial ID, or clinical standard value — if a lookup fails, report the gap.

## Example: Complete Diagnostic Workflow

```python
# Stage 0: Anatomy
cta_data = cardio_imaging_tools.load_dicom_series("/data/patient123/cta/")
cta_windowed = cardio_imaging_tools.apply_cardiac_window(cta_data["volume"])
vessels = cardio_imaging_tools.extract_vessel_centerlines(cta_windowed)

# Determine dominance by identifying PDA origin
dominance = "right"  # Based on PDA arising from RCA
# Anatomy/segment map comes from the bundled reference asset, not a KB tool call:
#   assets/references/coronary_anatomy.md
syntax_segments = cardiofetch_standards_lookup(standard="syntax")  # segment weights + numbering

# Stage 1a: CTA perception
cta_preprocessed = cardio_imaging_tools.preprocess_cta(cta_data["volume"])
lad_proximal_stenosis = cardio_imaging_tools.calculate_diameter_stenosis(
    cta_preprocessed, segment_id="LAD_5", method="diameter"
)
# Result: {min_diameter: 1.2, ref_diameter: 3.5, stenosis_pct: 65.7, confidence: 0.85}
# Note: Moderate calcification present (HU=300), may overestimate

# Stage 1b: DSA perception
dsa_data = cardio_imaging_tools.load_dsa_cine("/data/patient123/dsa/lad_rao_cranial.dcm")
lad_dsa_stenosis = cardio_imaging_tools.calculate_diameter_stenosis(
    dsa_data, segment_id="LAD_5", method="qca"
)
# Result: {min_diameter: 1.5, ref_diameter: 3.5, stenosis_pct: 57.1, confidence: 0.95}
# TIMI 3 flow observed

# Stage 2: Fusion
# CTA 65.7% vs DSA 57.1% → 8.6% difference, within acceptable range given calcification
# Final: 57% stenosis (favor DSA due to calcification blooming on CTA)

# Stage 3: Grading
cadrads_criteria = cardiofetch_standards_lookup(standard="cad-rads")
# Proximal LAD 57% → CAD-RADS 3 (moderate, 50-69%)

syntax_algorithm = cardiofetch_standards_lookup(standard="syntax")
# Proximal LAD (segment 5), 57% stenosis, non-occlusive, moderate calcification
# Base: segment_weight(5) × 2 = 7 × 2 = 14
# Modifiers: +1 (calcification) = 15
# Total SYNTAX = 15 (low risk)

# Stage 4: Decision
# Guideline evidence comes from the literature, not a hardcoded KB table:
guidelines = cardiofetch_pubmed_search(query="2021 ACC/AHA coronary revascularization guideline PCI CABG")
trials = cardiofetch_clinicaltrials_search(query="SYNTAX trial PCI versus CABG")
# CAD-RADS 3 → Functional testing recommended (FFR or stress imaging)
# SYNTAX 15 (low) → If revascularization needed, PCI reasonable
# Recommendation: "FFR-CT or invasive FFR for hemodynamic significance assessment. 
#                  If FFR ≤0.80, PCI of proximal LAD with drug-eluting stent is appropriate.
#                  Continue statin, aspirin, optimize medical therapy."
```

## Capability Boundary Awareness

**When to declare limitations** (never hallucinate these):
- **Hemodynamic significance**: Stenosis 40-70% → "Requires FFR to assess flow limitation"
- **Plaque vulnerability**: Cannot assess thin-cap fibroatheroma without OCT/IVUS
- **Viability**: CTO territories → "Requires viability study (PET/MRI) before revascularization"
- **Microvascular disease**: Normal epicardial arteries with angina → "Consider coronary flow reserve or microvascular assessment"
- **Image quality**: Motion artifacts, poor contrast, heavy calcification → Document degraded confidence
- **Clinical context**: Lab values (troponin, BNP), ECG, symptoms, comorbidities → "Requires integration with clinical data"

**Standard phrasing for boundaries**:
> "Based on imaging findings, [conclusion]. However, [specific limitation] prevents definitive assessment of [aspect]. Recommend [specific additional test] for complete evaluation."

## Reference Assets

See `assets/references/` for detailed anatomical and methodological references:
- `coronary_anatomy.md`: AHA 17-segment model, coronary dominance, anatomical variants, territory-at-risk
- `stenosis_quantification_methods.md`: Diameter vs area methods, QCA protocols, CTA-DSA fusion rules, reporting standards

## Integration with Other Skills

- **report-writing**: Use this skill's output to populate the structured diagnostic report template
- **evaluation-rubric**: Self-check adherence to standards and evidence-anchoring before finalizing

## Version & Maintenance

- **Version**: 0.1.0
- **Last updated**: 2026-07-21
- **Standards basis**: CAD-RADS 2.0 (2022), SYNTAX Score (Sianos 2005, updated SYNTAX II 2024), TIMI flow (1985), Rentrop collateral (1985)
- **Contact**: Submit issues to Cardiomni package repository
