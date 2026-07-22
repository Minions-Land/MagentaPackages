# Stenosis Quantification Methods

## Overview

Accurate stenosis quantification is critical for clinical decision-making. This reference describes standard methods for measuring coronary artery stenosis from medical imaging.

## Diameter Stenosis Method

### Formula

```
Stenosis% = (1 - Dmin/Dref) × 100
```

Where:
- `Dmin` = minimum luminal diameter at stenosis
- `Dref` = reference diameter from adjacent normal segment

### Procedure

1. **Identify stenotic segment**: Locate the point of maximum narrowing
2. **Select reference segment**: Choose adjacent normal segment (ideally within 1 cm)
3. **Measure diameters**: Use caliper or automated edge detection
4. **Calculate percentage**: Apply formula

### Measurement Guidelines

**Reference segment selection**:
- Should be visibly normal (no plaque or disease)
- Close to stenosis (within 5-10 mm ideally)
- If proximal and distal references differ, use average or larger value
- Avoid post-stenotic dilation as reference

**Diameter measurement**:
- Measure at narrowest point (worst projection)
- Use orthogonal views to confirm
- Measure lumen, not vessel wall
- Average multiple measurements to reduce error

### Advantages
- Simple and widely used
- Good inter-observer agreement (when image quality is good)
- Standard for clinical reporting

### Limitations
- Assumes circular lumen (fails for eccentric stenosis)
- Reference segment selection affects result
- Overestimates stenosis if reference segment has diffuse disease

## Area Stenosis Method

### Formula

```
Stenosis% = (1 - Amin/Aref) × 100
```

Where:
- `Amin` = minimum luminal cross-sectional area
- `Aref` = reference cross-sectional area

### Procedure

1. **Segment vessel**: Extract cross-sectional slices perpendicular to centerline
2. **Identify stenotic slice**: Find minimum luminal area
3. **Select reference slice**: Adjacent normal cross-section
4. **Measure areas**: Manual or automated segmentation
5. **Calculate percentage**: Apply formula

### Advantages
- More accurate than diameter method (especially for eccentric stenosis)
- Better correlation with hemodynamic significance
- Accounts for non-circular lumen shape

### Limitations
- Requires 3D imaging (CTA) or IVUS
- More complex measurement
- Higher inter-observer variability

## Visual Estimation

When quantitative measurement is not feasible:

### Method
- Compare stenotic segment to adjacent normal vessel
- Estimate percentage in 10% increments
- Use standardized visual scales

### Accuracy
- Tends to overestimate mild stenosis
- Tends to underestimate severe stenosis
- Inter-observer variability ±20%

### When to Use
- Poor image quality precludes measurement
- Rapid assessment needed
- Always document as "visual estimate"

## Quantitative Coronary Angiography (QCA)

Automated or semi-automated analysis from DSA:

### Process
1. Define vessel segment
2. Automated edge detection
3. Calibration using catheter diameter
4. Generate diameter profile along vessel
5. Calculate stenosis automatically

### Advantages
- Objective and reproducible
- Standard for clinical trials
- Provides additional parameters (lesion length, MLD)

### Limitations
- Requires high-quality DSA
- Single-plane measurement (use biplane for accuracy)
- Foreshortening and overlap affect accuracy

## Measurement Precision

### Sources of Error

**Image-related**:
- Motion artifact (cardiac, respiratory)
- Calcification blooming (CTA)
- Limited spatial resolution
- Overlapping vessels

**Measurement-related**:
- Reference segment selection
- Projection angle (foreshortening)
- Calibration error
- Inter-observer variability

### Quality Control

To maximize accuracy:

1. **Use optimal projection**: Minimize foreshortening and overlap
2. **Multiple measurements**: Average 2-3 measurements
3. **Consistent reference**: Use same reference for serial studies
4. **Document method**: Note if diameter vs. area, manual vs. automated
5. **Report confidence**: State limitations if present

## Clinical Thresholds

### Diameter Stenosis

Standard thresholds for intervention:

- **<50%**: Non-obstructive, medical therapy
- **50-70%**: Intermediate, consider functional testing
- **70-90%**: Severe, revascularization usually indicated
- **>90%**: Critical, urgent revascularization
- **100%**: Total occlusion

### Special Cases

**Left main**:
- ≥50% is significant
- Lower threshold due to large territory at risk

**Ostial lesions**:
- May appear worse on angiography
- IVUS recommended for accurate assessment

**Bifurcation lesions**:
- Measure parent vessel and both branches
- Document Medina classification

## Fractional Flow Reserve (FFR)

Functional assessment when anatomy is ambiguous:

### Indication
- Intermediate stenosis (50-70%) on angiography
- Discordant findings between modalities
- Uncertain clinical significance

### Interpretation
- FFR ≤0.80: Functionally significant, revascularize
- FFR >0.80: Not functionally significant, medical therapy

### When to Recommend
Include in stenosis report: "Moderate stenosis (55%) - recommend FFR for functional assessment"

## Calcification Handling

Heavy calcification affects CTA measurements:

### Calcium Score Interpretation
- **0-100**: Minimal blooming, CTA reliable
- **100-400**: Moderate blooming, use caution
- **>400**: Severe blooming, CTA may overestimate stenosis

### Strategy
1. Check calcium score
2. If >400, rely on DSA for quantification
3. Document: "CTA measurement limited by calcification"

## Multi-Modal Integration

### CTA + DSA Protocol

When both available:

1. **CTA first**: 
   - 3D anatomy and plaque characterization
   - Identify all stenoses
   - Guide DSA projections

2. **DSA confirmation**:
   - Quantify stenosis percentage (gold standard)
   - Resolve CTA ambiguities (calcification, artifacts)
   - Assess collateral circulation

3. **Final report**:
   - Use DSA measurement as primary
   - Note CTA findings for context
   - Explain any discrepancies

### Discrepancy Resolution

If CTA and DSA differ by >20%:

- **Likely cause**: Calcification blooming on CTA
- **Resolution**: Use DSA measurement
- **Document**: "CTA overestimated due to calcium blooming; DSA used for final quantification"

## Reporting Standards

### Essential Elements

Every stenosis quantification must include:

1. **Method**: Diameter, area, or visual estimate
2. **Measurement location**: Vessel and segment (AHA model)
3. **Values**: Minimum and reference diameters/areas
4. **Percentage**: Calculated stenosis
5. **Image quality**: Document limitations
6. **Confidence**: High/moderate/low

### Example Report Format

```
Vessel: LAD
Segment: Proximal LAD (segment 5)
Method: Diameter stenosis (QCA)
Minimum diameter: 1.0 mm
Reference diameter: 3.5 mm
Stenosis percentage: 71%
Grade: Severe
Confidence: High
Notes: Minimal calcification, excellent image quality
```

## References

- Scanlon PJ, et al. ACC/AHA Guidelines for Coronary Angiography. JACC 1999.
- Gensini GG. Coronary Arteriography. 1975.
- Reiber JH, et al. Quantitative Coronary Arteriography. Kluwer Academic Publishers. 1991.
- White CW, et al. Does visual interpretation of the coronary arteriogram predict the physiologic importance of a coronary stenosis? NEJM 1984.
