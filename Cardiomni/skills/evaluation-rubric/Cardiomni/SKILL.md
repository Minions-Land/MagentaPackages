---
kind: skill
name: evaluation-rubric
source: Cardiomni
display_name: Cardiovascular Diagnosis Evaluation Rubric
description: Evidence-anchored evaluation framework for cardiovascular diagnostic reports — 6-dimensional rubric (data handling, perception accuracy, fusion reasoning, clinical interpretation, scientific reasoning, source reliability) with A/B/C grading anchored to CAD-RADS/SYNTAX/TIMI standards and anti-hallucination checks.
version: 0.1.0
license: MIT
profiles: [clinical]
---

# Cardiovascular Diagnosis Evaluation Rubric

This skill defines the evaluation framework for assessing autonomous cardiovascular diagnostic reports. Use this rubric as a **self-check before finalizing reports** and for systematic evaluation in benchmark settings.

## Rubric Overview

The rubric comprises **6 dimensions** with weighted contributions to overall score:

| Dimension | Weight | Focus |
|-----------|--------|-------|
| Data Handling | 0.10 | Correct DICOM parsing, preprocessing, modality recognition |
| Perception Accuracy | 0.25 | Stenosis quantification, anatomy identification, plaque characterization |
| Fusion Reasoning | 0.20 | Cross-modal integration logic, discrepancy resolution |
| Clinical Interpretation | 0.20 | CAD-RADS/SYNTAX scoring accuracy, decision support appropriateness |
| Scientific Reasoning | 0.15 | Evidence anchoring, standard adherence, reasoning transparency |
| Source Reliability | 0.10 | Citation accuracy, hallucination detection (CAN BE NEGATIVE) |

**Total score**: Weighted sum of dimension scores. Source Reliability can penalize hallucinated claims, pulling total score negative if egregious.

**Grade mapping**:
- **A (Excellent)**: ≥0.85 — Report meets clinical standard, minimal errors, well-reasoned
- **B (Acceptable)**: 0.70–0.84 — Report usable with minor corrections, some imprecision
- **C (Inadequate)**: <0.70 — Report has significant errors, misleading conclusions, or fabrications

---

## Dimension 1: Data Handling (Weight: 0.10)

**What it measures**: Correct interpretation of DICOM metadata, appropriate preprocessing, recognition of imaging modality constraints.

### Grading Criteria

**A (0.9–1.0)**:
- Correctly extracts HU values, pixel spacing, slice thickness from CTA DICOM
- Properly loads multi-frame DSA cine sequences with temporal ordering
- Applies appropriate cardiac windowing (e.g., soft tissue preset for vessels)
- Recognizes and handles synthetic/simulated DICOM (if applicable)
- No errors in coordinate system or orientation

**B (0.7–0.89)**:
- Minor preprocessing issues (e.g., non-optimal windowing but still interpretable)
- Metadata partially used (e.g., ignores slice thickness but quantifies correctly)
- Single-frame DSA processed when multi-frame available (suboptimal but functional)

**C (<0.7)**:
- HU values not used (treats CTA as grayscale image, cannot distinguish calcification)
- DSA temporal sequence ignored (uses single frame, misses flow dynamics)
- Wrong modality assumed (e.g., treats CTA as MRI)
- Coordinate system errors leading to incorrect anatomy labels

**Failure modes to check**:
- Did the report use HU thresholds to classify plaques? (HU >130 = calcified)
- Did the report account for pixel spacing in diameter measurements?
- Did the report use multiple DSA frames or just one?

---

## Dimension 2: Perception Accuracy (Weight: 0.25)

**What it measures**: Correctness of stenosis quantification, vessel segment identification, and plaque characterization compared to ground truth (expert annotations or gold standard).

### Grading Criteria

**A (0.9–1.0)**:
- Stenosis measurements within ±10% of expert QCA for all significant lesions (≥50%)
- All significant lesions (≥50%, vessel ≥1.5mm) correctly identified
- Vessel segment labels match SYNTAX/AHA nomenclature (no LAD/LCx confusion)
- Plaque type (calcified/soft/mixed) matches expert assessment
- Calcification severity accurately graded (mild/moderate/heavy)
- TIMI flow grade matches invasive assessment (if DSA available)

**B (0.7–0.89)**:
- Stenosis measurements within ±20% of expert for significant lesions
- Missed 1 minor lesion (<50% stenosis) OR misclassified 1 lesion by 1 CAD-RADS grade
- Segment labeling has 1-2 minor errors (e.g., proximal vs mid boundary off by 5mm)
- Plaque type correct for major lesions, imprecise for minor ones

**C (<0.7)**:
- Stenosis measurements differ by >20% from expert
- Missed ≥2 significant lesions (≥50%)
- Major segment misidentification (e.g., RCA lesion labeled as LAD)
- Plaque type systematically wrong (e.g., all calcified plaques called soft)
- Fabricated lesions not present in images

**Anchoring to standards**:
- Use expert-annotated stenosis percentages as ground truth
- Cross-reference segment IDs with SYNTAX trial definitions
- Validate TIMI grades against invasive reports (if available)

**Self-check questions**:
- Did I measure reference diameters from visibly normal segments?
- Did I account for projection angle in DSA (avoid foreshortened views)?
- Did I document measurement method (diameter/area/visual)?

---

## Dimension 3: Fusion Reasoning (Weight: 0.20)

**What it measures**: Appropriateness of cross-modal integration logic when combining CTA and DSA findings.

### Grading Criteria

**A (0.9–1.0)**:
- Correctly applies fusion rules: DSA used when CTA has heavy calcification blooming
- Discrepancies between modalities explicitly documented with reasoning
- 3D CTA anatomy correctly registered to 2D DSA projections
- Collateral assessment integrates DSA flow (Rentrop) with CTA vessel course
- No contradictions between stated CTA and DSA measurements in final report

**B (0.7–0.89)**:
- Fusion logic generally sound but not explicitly documented
- Minor inconsistencies (e.g., CTA overestimate noted but still used in CAD-RADS grading)
- Modality strengths partially leveraged (e.g., CTA plaque + DSA stenosis, but not explained)

**C (<0.7)**:
- Fusion rules ignored (e.g., uses CTA stenosis despite heavy calcification when DSA available)
- Contradictory statements (e.g., "CTA shows 80%, DSA shows 60%, final grade 80%" with no justification)
- Modalities treated independently rather than synergistically
- Hallucinated "agreement" when modalities actually conflict

**Fusion protocol checklist** (from diagnosis-analysis skill):
- CTA–DSA agreement within ±10% → consensus
- CTA > DSA by >20% + heavy calcification → use DSA
- DSA unavailable → use CTA with qualifier
- Contradictions beyond artifacts → flag for additional imaging

**Self-check questions**:
- Did I explain why I chose DSA over CTA (or vice versa) for each discrepancy?
- Did I note which segments lack DSA and rely on CTA alone?
- Did I avoid averaging CTA and DSA without justification?

---

## Dimension 4: Clinical Interpretation (Weight: 0.20)

**What it measures**: Accuracy of CAD-RADS grading, SYNTAX score calculation, and appropriateness of clinical recommendations.

### Grading Criteria

**A (0.9–1.0)**:
- CAD-RADS grades match expert for per-lesion and per-patient assessment
- SYNTAX score calculation correct:
  - Dominance correctly determined (no "balanced" in SYNTAX)
  - Only lesions ≥50% in vessels ≥1.5mm included
  - Segment weights from official SYNTAX table
  - Complexity modifiers (CTO, bifurcation, calcification) correctly applied
  - Risk tier (low/mid/high) matches calculated score
- Revascularization recommendations align with guidelines (PCI for low SYNTAX, CABG consideration for high SYNTAX + multi-vessel)
- Additional testing recommendations appropriate (FFR for 40-70%, IVUS for ambiguous plaques)

**B (0.7–0.89)**:
- CAD-RADS off by 1 grade for 1-2 lesions (e.g., graded 3 instead of 4A)
- SYNTAX score within ±3 points of expert (minor weight/modifier errors)
- Recommendations reasonable but not optimally specific (e.g., "consider revasc" without PCI vs CABG guidance)

**C (<0.7)**:
- CAD-RADS systematically wrong (e.g., graded 2 when should be 4A)
- SYNTAX score off by >5 points (major calculation errors or wrong dominance)
- Inappropriate recommendations (e.g., medical management for left main disease)
- Hallucinated risk stratification (e.g., claiming "low risk" with SYNTAX 35)

**Standard references** (query with cardiofetch_standards_get):
- CAD-RADS 2.0 grading table (PMC9627235)
- SYNTAX score algorithm (Sianos 2005, online calculator)
- Revascularization guidelines (ACC/AHA, ESC)

**Self-check questions**:
- Did I include only significant lesions (≥50%, ≥1.5mm) in SYNTAX?
- Did I apply the ×5 multiplier for total occlusions (not ×2)?
- Did I classify bifurcations with Medina notation before adding complexity score?
- Did my PCI vs CABG recommendation match the SYNTAX risk tier?

---

## Dimension 5: Scientific Reasoning (Weight: 0.15)

**What it measures**: Transparency of reasoning, adherence to clinical standards, and explicit acknowledgment of evidence vs inference.

### Grading Criteria

**A (0.9–1.0)**:
- Every quantitative claim anchored to measurement (stenosis % from QCA, not memory)
- Clinical standards explicitly cited (e.g., "per CAD-RADS 2.0 criteria")
- Reasoning trace documents decision logic (Stage 0→1a→1b→2→3→4 flow visible)
- Uncertainty explicitly stated where evidence is weak (e.g., "CTO duration unknown")
- No speculation presented as fact

**B (0.7–0.89)**:
- Most claims grounded, but occasional unsupported assertion (e.g., "likely chronic CTO" without timeline evidence)
- Standards referenced generally but not cited per decision
- Reasoning mostly clear but some logical jumps not explained

**C (<0.7)**:
- Ungrounded claims (e.g., "70% stenosis" without measurement documentation)
- No standard references or incorrect standard application
- Reasoning opaque (conclusions stated without supporting logic)
- Speculation treated as established fact

**Evidence hierarchy**:
1. **Direct measurement**: From DICOM pixel data or QCA tool output
2. **Standard lookup**: From CAD-RADS/SYNTAX/TIMI definitions via cardiofetch
3. **Clinical inference**: Derived from above with explicit reasoning
4. **Speculation**: Clearly flagged as hypothesis requiring validation

**Self-check questions**:
- Can I trace every stenosis percentage back to a specific measurement?
- Did I cite which standard (CAD-RADS/SYNTAX/TIMI) each grade comes from?
- Did I use "possibly" / "suggests" / "cannot determine" where appropriate?
- Did I document my reasoning for ambiguous cases?

---

## Dimension 6: Source Reliability (Weight: 0.10, CAN BE NEGATIVE)

**What it measures**: Accuracy of citations, absence of hallucinated information, and appropriate use of standards/literature.

**CRITICAL**: This is the **anti-hallucination dimension**. Fabricated claims score **negative**, penalizing overall score.

### Grading Criteria

**A (0.9–1.0)**:
- All cited standards (CAD-RADS, SYNTAX, TIMI, Rentrop) correctly referenced
- No fabricated measurements or phantom lesions
- Cardiofetch queries used appropriately for standard lookups
- Claims match what imaging actually shows (verifiable from DICOM)

**B (0.7–0.89)**:
- Minor citation imprecision (e.g., correct standard but outdated version)
- All major claims verifiable, but 1-2 minor unsupported details

**C (0.5–0.69)**:
- One hallucinated minor fact (e.g., incorrect year for SYNTAX trial) OR
- One measurement not traceable to imaging but not obviously fabricated

**D (0.0–0.49)**:
- Multiple hallucinated facts OR
- One hallucinated lesion (stenosis claimed but not visible in images)

**F (Negative, e.g., -0.5 to -1.0)**:
- Systematic hallucination (multiple phantom lesions, fabricated measurements throughout)
- Fabricated "standards" (e.g., claiming "AHA 2025 guidelines" that don't exist)
- Dangerous misinformation (e.g., claiming benign when actually severe disease)

**Hallucination detection checklist**:
- Cross-check stenosis percentages against DICOM pixel measurements
- Verify cited standard versions exist (CAD-RADS 2.0 = 2022, SYNTAX = 2005)
- Confirm all vessel segments mentioned are actually visible in images
- Validate numerical claims (e.g., SYNTAX weight tables) against official sources

**Self-check questions**:
- Did I fabricate any measurements I couldn't derive from the images?
- Did I cite standards I didn't actually query or verify?
- Did I "remember" a stenosis percentage from a previous case?
- Can every vessel segment I listed be pointed to in the DICOM?

---

## Using the Rubric: Self-Check Protocol

Before finalizing any diagnostic report, run this self-check:

1. **Data handling check**: Did I extract and use all relevant DICOM metadata (HU, spacing, multi-frame)?
2. **Perception check**: Can I trace every stenosis measurement back to a specific image slice/frame?
3. **Fusion check**: Did I document why I chose DSA over CTA (or vice versa) for each discrepant finding?
4. **Clinical check**: Did I verify my SYNTAX calculation (dominance, weights, modifiers)?
5. **Reasoning check**: Did I cite the standard for every CAD-RADS/SYNTAX/TIMI grade?
6. **Reliability check**: Did I hallucinate anything I can't verify from the images?

If any check fails, revise the report before declaring it final.

---

## Benchmark Application

In CardiomniBench-VD evaluation:
- Each dimension is scored 0.0–1.0 (Source Reliability can go negative)
- Weighted sum produces total score
- A/B/C grade assigned per thresholds above
- Expert gold standard provides ground truth for dimensions 2, 4
- Dimensions 1, 3, 5, 6 assessed by protocol adherence and verifiability

**Scoring example**:
```
Data Handling: 0.95 (all metadata used correctly)
Perception Accuracy: 0.80 (stenosis within ±15% expert, 1 minor lesion missed)
Fusion Reasoning: 0.90 (DSA used for calcified lesions, well-documented)
Clinical Interpretation: 0.75 (SYNTAX off by 2 points, recs appropriate)
Scientific Reasoning: 0.85 (mostly grounded, one inference not explained)
Source Reliability: 0.90 (all standards correct, no hallucinations)

Total = 0.10×0.95 + 0.25×0.80 + 0.20×0.90 + 0.20×0.75 + 0.15×0.85 + 0.10×0.90
      = 0.095 + 0.200 + 0.180 + 0.150 + 0.128 + 0.090
      = 0.843
Grade: B (Acceptable)
```

---

## Capability Boundary Awareness in Rubric

The rubric **rewards** explicit capability boundary statements and **penalizes** overconfident claims:

**Examples of good boundary awareness** (scored positively in Dimension 5):
- "Functional significance of this 55% lesion cannot be determined without FFR"
- "CTO chronicity unknown; clinical history required for decision-making"
- "Image quality limits precise quantification; recommend repeat with optimal protocol"

**Examples of poor boundary awareness** (scored negatively in Dimension 6):
- Claiming "hemodynamically significant" without FFR data (hallucinated functional assessment)
- Providing prognosis without clinical context (overstepping anatomical diagnosis)
- Asserting "definitely chronic CTO" without timeline evidence (speculation as fact)

The rubric enforces the principle: **better to say "I cannot determine" than to hallucinate an answer**.

---

## References

This rubric design mirrors:
- BiomniBench process-level evaluation (Stanford, 2026)
- DrugDiscoveryBench annotation protocol (Scale AI, 2024)
- MedAgentBoard multi-agent evaluation framework (2025)

Clinical anchors:
- CAD-RADS 2.0 consensus document (PMC9627235)
- SYNTAX Score algorithm (Sianos et al. 2005, EuroIntervention)
- TIMI flow grading (Thrombolysis in Myocardial Infarction trial, 1985)
- Rentrop collateral grading (Circulation 1985)

Query all standards via: `cardiofetch_standards_get(standard="<name>", query="<detail>")`
