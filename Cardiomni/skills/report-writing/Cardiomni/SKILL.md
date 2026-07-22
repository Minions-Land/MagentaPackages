---
kind: skill
name: report-writing
source: Cardiomni
display_name: Cardiovascular Diagnostic Report Writing
description: Standard structured diagnostic report format for coronary CTA/DSA findings — vessel segment documentation, CAD-RADS grading, SYNTAX scoring, cross-modal fusion reasoning, clinical decision support, and explicit capability boundaries.
version: 0.1.0
license: MIT
profiles: [clinical]
---

# Cardiovascular Diagnostic Report Writing

This skill defines the standard format for autonomous cardiovascular diagnostic reports. Reports must be structured, evidence-anchored, and explicitly state capability boundaries.

## Report Structure (Required Sections)

### 1. Clinical Context
- Patient identifier (anonymized ID if research/benchmark)
- Indication for imaging (e.g., chest pain, pre-op clearance, post-PCI surveillance)
- Imaging modalities: CTA and/or DSA acquisition details

### 2. Coronary Anatomy
**Dominance**: Right-dominant / Left-dominant / Co-dominant

**Vessel segments identified** (use SYNTAX 16-segment nomenclature based on AHA):
- RCA: segments 1 (proximal), 2 (mid), 3 (distal), 4 (PDA), 4a (posterolateral)
- LAD: segments 5 (proximal), 6 (mid), 7 (distal), 9 (D1), 10 (D2)
- LCx: segments 11 (proximal), 13 (mid), 15 (distal), 12 (OM1), 14 (OM2), 14a (posterolateral)
- LM: segment 6

**Anatomical variants** (if present): Document any anomalous origins, myocardial bridging, or non-standard branching.

### 3. Per-Segment Findings

For each vessel segment, report:
- **Segment ID & name**: e.g., "Segment 5 (Proximal LAD)"
- **Stenosis severity**: Percentage (%) with method (diameter/area/visual)
  - CTA measurement: X%
  - DSA measurement: Y% (if available)
  - Final grade: Z% (explain if fusion rule applied)
- **CAD-RADS grade**: 0/1/2/3/4A/4B/5
- **Plaque characterization** (CTA): None / Soft / Mixed / Calcified (with HU range if calcified)
- **Calcification severity**: None / Mild / Moderate / Heavy (note blooming if present)
- **TIMI flow** (DSA): 0/1/2/3 (if assessed)
- **Lesion features** (for SYNTAX scoring): Length, bifurcation (Medina class), ostial, tortuosity, CTO characteristics

**Example**:
```
Segment 5 (Proximal LAD):
- Stenosis: CTA 75% (diameter method), DSA 68% (QCA) → Final: 68% (DSA used, heavy calcification on CTA)
- CAD-RADS: 4A
- Plaque: Heavily calcified (HU 400-800), blooming artifact noted
- Calcification: Heavy
- TIMI flow: 2 (slow flow)
- Lesion features: Length 15mm, no bifurcation involvement, moderate tortuosity
```

### 4. Cross-Modal Fusion Reasoning

**Modality agreement**:
- Segments where CTA and DSA agree (within ±10%): [list]
- Segments where CTA overestimated (calcium blooming): [list, explain DSA correction]
- Segments assessed by CTA only: [list, state reason]
- Segments assessed by DSA only: [list, state reason]

**Fusion decisions**: Explicitly document which modality's measurement was used for final grading and why.

**Example**:
```
CTA and DSA agreed within 5% for RCA segments 1-3. Segment 5 (proximal LAD) showed discordance: CTA 75% vs DSA 68%. Heavy calcification caused blooming artifact on CTA. DSA measurement used for final grading per fusion protocol.
```

### 5. Scoring & Risk Stratification

**Per-Patient CAD-RADS**: [0/1/2/3/4A/4B/5] — highest grade among all segments

**SYNTAX Score Calculation**:
- Dominance: [Right/Left/Co-dominant]
- Lesions included (≥50% stenosis, vessel ≥1.5mm): [count]
- Per-lesion scores:
  - Segment X: base score [value] + modifiers [list] = subtotal
  - Segment Y: ...
- **Total SYNTAX Score**: [value]
- **Risk tier**: Low (≤22) / Intermediate (23-32) / High (≥33)

**Example**:
```
SYNTAX Score: 28 (Intermediate risk)
- Segment 5 (proximal LAD): 6 (weight 3.5 × 2 non-occlusive) + 1 (heavy calc) + 1 (length >20mm) = 8
- Segment 2 (mid RCA): 2 (weight 1 × 2) + 1 (CTO blunt stump) + 1 (collateral Rentrop 2) = 4
...
Total: 28 → Intermediate-risk anatomy
```

### 6. Clinical Interpretation & Decision Support

**Revascularization recommendation**:
- Medical management only
- Functional testing (FFR/stress) for intermediate lesions
- PCI consideration (specify target vessels)
- CABG consideration (if SYNTAX high or left main disease)
- Hybrid approach (if mixed complexity)

**Additional testing needs**:
- FFR-CT or invasive FFR for stenoses 40-70%
- IVUS/OCT for ambiguous plaque assessment
- Viability study for CTO territories
- Repeat imaging with optimized protocol if non-diagnostic quality

**Medical optimization**: Statin, antiplatelet therapy, BP control, diabetes management (standard regardless of revascularization).

**Example**:
```
Recommendation: Revascularization indicated for proximal LAD severe stenosis (CAD-RADS 4A, SYNTAX 28 intermediate). PCI vs CABG decision requires Heart Team discussion; intermediate SYNTAX favors either approach. Additional FFR recommended for mid RCA lesion (55%, functionally borderline).
```

### 7. Capability Boundaries & Limitations

**Explicit statement of what the report CANNOT determine**:
- Functional significance of intermediate stenoses (requires FFR)
- Myocardial viability in CTO territories (requires PET/MRI)
- Microvascular disease (not visible on CTA/DSA)
- Precise plaque composition within mixed lesions (requires IVUS/OCT)
- Long-term prognosis (requires clinical context, biomarkers, comorbidities)

**Image quality limitations** (if any):
- Motion artifact in specific segments
- Suboptimal contrast timing
- Heavy calcification obscuring lumen
- Non-diagnostic DSA projection angles

**Example**:
```
Capability boundaries: This report quantifies anatomical stenosis severity but does not assess functional significance. FFR is required to determine if the 55% mid-RCA lesion causes ischemia. CTO chronicity and viability are unknown and require clinical history and viability imaging for decision-making.
```

### 8. Clinical Reasoning Trace

**Mandatory section**: Document the reasoning chain that led to conclusions. This ensures transparency and allows verification against clinical standards.

**Include**:
- Why specific segments were flagged as significant
- How fusion decisions were made (CTA vs DSA discrepancies)
- How SYNTAX complexity modifiers were assigned
- Why specific additional tests are recommended
- Which clinical guidelines informed the decision (reference by name: ACC/AHA, ESC, etc.)

**Example**:
```
Reasoning: Proximal LAD stenosis graded 68% (DSA) meets ≥70% threshold for "severe" per ACC/AHA guidelines, though marginal. However, combined with TIMI 2 flow (functional impairment) and LAD territory size (large myocardium at risk), revascularization is indicated. SYNTAX score 28 is intermediate; per SYNTAX trial outcomes, both PCI and CABG have comparable results in this range, thus Heart Team discussion is appropriate rather than prescriptive recommendation.
```

## Worked Example: Synthetic Case

**Clinical Context**:
- Patient ID: SYNTH-001
- Indication: Stable angina, positive stress test
- Imaging: CTA (64-slice) + DSA (biplane)

**Coronary Anatomy**:
- Dominance: Right-dominant
- All standard segments identified, no variants

**Per-Segment Findings**:

*Segment 5 (Proximal LAD)*:
- Stenosis: CTA 78%, DSA 71% → Final: 71% (heavy calcification on CTA)
- CAD-RADS: 4A
- Plaque: Mixed (calcified HU 350-600, soft component HU 40-80)
- Calcification: Heavy
- TIMI flow: 3 (normal)
- Features: Length 12mm, no bifurcation, minimal tortuosity

*Segment 2 (Mid RCA)*:
- Stenosis: CTA 55%, DSA 52% → Final: 53% (consensus)
- CAD-RADS: 3
- Plaque: Soft (HU 35-70)
- Calcification: None
- TIMI flow: 3
- Features: Length 8mm, no complexity

*All other segments*: CAD-RADS 0-1, no significant disease

**Cross-Modal Fusion**:
CTA overestimated proximal LAD by 7% due to calcium blooming. DSA measurement used. Mid RCA showed modality agreement; CTA measurement retained.

**Scoring**:
- Per-Patient CAD-RADS: 4A (proximal LAD grade)
- SYNTAX Score: 7 (Low risk)
  - Proximal LAD: 3.5 (weight) × 2 (non-occlusive) + 1 (heavy calc) = 8
  - Mid RCA: excluded (< 50% threshold)
  - Total: 8 → Low-risk anatomy

**Clinical Interpretation**:
Revascularization recommended for proximal LAD (≥70% stenosis, large territory). Low SYNTAX score (8) favors PCI. Mid RCA lesion (53%) is borderline; FFR recommended to assess functional significance before intervention.

**Capability Boundaries**:
This report establishes anatomical stenosis severity but does not determine if mid RCA lesion causes ischemia (requires FFR). Patient-specific surgical risk and comorbidities (not assessed here) must be incorporated into final Heart Team decision.

**Reasoning Trace**:
Proximal LAD 71% exceeds 70% severe threshold and supplies large anterior wall territory, justifying revascularization per ACC/AHA Class I indication. SYNTAX 8 is low-risk, and PCI is preferred for single-vessel disease per ESC guidelines. Mid RCA at 53% falls in gray zone (50-70% moderate stenosis); ACC appropriate use criteria recommend FFR for such lesions to avoid unnecessary intervention. DSA showed TIMI 3 flow, suggesting lesion may not be flow-limiting, further supporting FFR before PCI decision.

## Anti-Patterns (DO NOT Do This)

❌ **Vague quantification**: "Moderate stenosis in LAD" → ✅ "68% stenosis in segment 5 (proximal LAD), CAD-RADS 3"

❌ **Copying labels without measurement**: "Severe disease" → ✅ "Measured 72% diameter stenosis, CAD-RADS 4A"

❌ **Ignoring modality discrepancies**: Reporting CTA value when DSA differs → ✅ Document both, explain which used and why

❌ **Hallucinating features**: Claiming FFR was performed when only anatomical imaging available → ✅ State "FFR not performed; anatomical stenosis only"

❌ **Omitting capability boundaries**: Acting like anatomical imaging determines functional significance → ✅ Explicitly state "functional assessment requires FFR"

❌ **Generic recommendations**: "Consider revascularization" → ✅ "PCI recommended for proximal LAD per ACC/AHA Class I indication; SYNTAX low-risk favors PCI over CABG"

## Template (Copy & Fill)

```markdown
# Cardiovascular Diagnostic Report

## Clinical Context
- Patient ID: 
- Indication: 
- Imaging: CTA [details], DSA [details]

## Coronary Anatomy
- Dominance: 
- Segments identified: 
- Variants: 

## Per-Segment Findings

### [Segment ID & Name]
- Stenosis: CTA __%, DSA __% → Final: __%
- CAD-RADS: 
- Plaque: 
- Calcification: 
- TIMI flow: 
- Features: 

[Repeat for all segments with findings]

## Cross-Modal Fusion Reasoning
- Agreement: 
- Discrepancies: 
- Fusion decisions: 

## Scoring & Risk Stratification
- Per-Patient CAD-RADS: 
- SYNTAX Score: __ ([Low/Intermediate/High] risk)
  - [Per-lesion breakdown]

## Clinical Interpretation
- Revascularization: 
- Additional testing: 
- Medical optimization: 

## Capability Boundaries
[Explicit statement of what report cannot determine]

## Clinical Reasoning Trace
[Step-by-step justification of conclusions]
```

## References for Standards

Use `cardiofetch_standards_get` to retrieve authoritative definitions during report writing:
- `standard="CAD-RADS"` → grading table
- `standard="SYNTAX"` → scoring algorithm
- `standard="TIMI"` → flow grading
- `standard="ACC_AHA_guidelines"` → revascularization indications
- `standard="stenosis_quantification"` → measurement methods
