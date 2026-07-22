"""
Cardiomni Cardiovascular Imaging Runtime

Medical imaging tools for CTA/DSA analysis and stenosis assessment.
"""

from .dicom_loader import load_dicom_series, load_nifti_volume
from .preprocessing import (
    preprocess_cta,
    apply_cardiac_window,
    resample_volume,
    denoise_volume,
)
from .stenosis_analysis import (
    analyze_vessel_stenosis,
    calculate_diameter_stenosis,
    calculate_area_stenosis,
    extract_vessel_centerlines,
)
from .evaluation import evaluate_against_expert
from .synthetic_dicom import (
    make_synthetic_cta_dicom,
    make_synthetic_dsa_dicom,
    load_dsa_cine,
)

__version__ = "0.1.0"

__all__ = [
    # DICOM/NIfTI loading
    "load_dicom_series",
    "load_nifti_volume",
    # Preprocessing
    "preprocess_cta",
    "apply_cardiac_window",
    "resample_volume",
    "denoise_volume",
    # Stenosis analysis
    "analyze_vessel_stenosis",
    "calculate_diameter_stenosis",
    "calculate_area_stenosis",
    "extract_vessel_centerlines",
    # Evaluation
    "evaluate_against_expert",
    # Synthetic data
    "make_synthetic_cta_dicom",
    "make_synthetic_dsa_dicom",
    "load_dsa_cine",
]
