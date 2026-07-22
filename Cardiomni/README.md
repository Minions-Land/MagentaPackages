# Cardiomni Package

Cardiomni is a cardiovascular AI agent package for Magenta3, designed to analyze CTA (Computed Tomography Angiography) and DSA (Digital Subtraction Angiography) images to assess coronary vessel stenosis and blockage percentage.

## Overview

This package addresses a critical clinical challenge: accurate assessment of coronary vessel stenosis from medical imaging. Currently, this task relies primarily on expert visual inspection without algorithmic support. The challenge includes:

- **Image noise**: Calcification and stenosis appear similar in images but require different clinical interpretation
- **Expert-level difficulty**: Some cases require wet-lab experiments for accurate differentiation
- **Multi-vessel complexity**: Identifying and assessing multiple vessels in a single cardiac study

## Task Definition

- **Input**: High-quality CTA and DSA images from multi-center datasets with expert annotations (20-50 tasks)
- **Output**: 
  - Number of coronary vessels identified
  - Stenosis percentage for each vessel
  - Clinical reasoning trace with interpretability
- **Evaluation**: Expert-authored LLM evaluation rubric assessing:
  - Vessel count accuracy
  - Stenosis percentage accuracy
  - Clinical reasoning quality and interpretability

## Skills

### `cardio-imaging`

Multimodal workflow for reading and interpreting CTA/DSA medical images:

- DICOM and medical imaging format parsing
- Image preprocessing and enhancement
- Vessel segmentation guidance
- Multi-modal image correlation (CTA + DSA)

### `stenosis-analysis`

Clinical assessment workflow for vessel stenosis quantification:

- Vessel identification and tracking
- Stenosis percentage estimation methods
- Differentiation between calcification and true stenosis
- Clinical reporting with reasoning traces

## Tools

### `cardio_imaging_tools`

Executable utilities for medical imaging:

- Medical imaging format readers (DICOM, NIfTI, etc.)
- Image preprocessing and enhancement functions
- Vessel segmentation utilities
- Scientific computing tools for cardiac analysis

## Scientific Contribution

Cardiomni represents a BiomniBench-style contribution:

- **Novel benchmark**: Multi-center expert-annotated coronary stenosis assessment dataset
- **Domain agent**: Specialized cardiovascular AI agent with multimodal reasoning
- **Baselines**: Compared against coding agents, multimodal agents, and deep vision models

## Package Layout

```text
Cardiomni/
├── package.toml
├── README.md
├── reference.md                    # Original task specification
├── brand/
│   └── Cardiomni/
│       ├── README.md
│       ├── brand.toml
│       └── Cardiomni.brand.ts
├── skills/
│   ├── cardio-imaging/
│   │   └── Cardiomni/
│   │       ├── SKILL.md
│   │       └── assets/
│   └── stenosis-analysis/
│       └── Cardiomni/
│           ├── SKILL.md
│           └── assets/
└── tools/
    └── cardio-imaging-tools/
        └── Cardiomni/
            ├── cardio-imaging-tools.toml
            └── python/
                ├── cardio_imaging_runtime/
                └── tests/
```

## Usage

Load the full cardiovascular agent:

```bash
magenta --harness-package Cardiomni
```

Load only imaging analysis:

```bash
magenta --harness-package Cardiomni:imaging
```

Load clinical assessment:

```bash
magenta --harness-package Cardiomni:clinical
```

## Requirements

### Python Dependencies

Core requirements:
- `numpy`, `pandas` for data handling
- `pydicom` for DICOM format reading
- `nibabel` for NIfTI format
- `SimpleITK` or `opencv-python` for image processing
- `scipy` for scientific computing

Optional dependencies for advanced features:
- `scikit-image` for segmentation
- `monai` for medical imaging AI
- `vtk` for 3D visualization
- Claude API access for multimodal reasoning

### Data Requirements

Medical imaging datasets (not bundled):
- Multi-center CTA/DSA image datasets
- Expert annotations for vessel count and stenosis percentage
- Evaluation rubrics from clinical experts

## Clinical Safety Note

This package is for research purposes only. Clinical use requires:
- Regulatory approval (FDA, CE marking, etc.)
- Clinical validation studies
- Expert radiologist oversight
- Institutional review board approval

## Related Packages

- [AutOmicScience](../AutOmicScience/) — Omics analysis harness
- [Biomni](../Biomni/) — Biomedical AI toolkit
- [ClaudeScience](../ClaudeScience/) — Computational biology research

## Citation

If you use Cardiomni in your research, please cite:

```text
Cardiomni: A Cardiovascular AI Agent for Stenosis Assessment
[Publication details pending]
```
