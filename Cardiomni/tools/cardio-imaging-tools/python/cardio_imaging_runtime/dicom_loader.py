"""
DICOM and NIfTI medical imaging format loaders.
"""

import os
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

try:
    import pydicom
    from pydicom.filereader import dcmread
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False

try:
    import nibabel as nib
    NIBABEL_AVAILABLE = True
except ImportError:
    NIBABEL_AVAILABLE = False


def load_dicom_series(directory_path: str) -> Tuple[np.ndarray, Dict]:
    """
    Load a DICOM series from a directory.

    Args:
        directory_path: Path to directory containing DICOM files

    Returns:
        tuple: (volume, metadata)
            - volume: 3D numpy array (Z, Y, X)
            - metadata: dict of relevant DICOM tags

    Raises:
        ImportError: If pydicom is not installed
        FileNotFoundError: If directory doesn't exist
        ValueError: If no valid DICOM files found
    """
    if not PYDICOM_AVAILABLE:
        raise ImportError(
            "pydicom is required for DICOM loading. "
            "Install with: pip install pydicom"
        )

    directory = Path(directory_path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    # Load all DICOM files
    dicom_files = []
    for file_path in sorted(directory.glob("*.dcm")):
        try:
            ds = dcmread(str(file_path))
            dicom_files.append((ds.ImagePositionPatient[2], ds))
        except Exception as e:
            print(f"Warning: Failed to read {file_path}: {e}")
            continue

    if not dicom_files:
        raise ValueError(f"No valid DICOM files found in {directory_path}")

    # Sort by slice location
    dicom_files.sort(key=lambda x: x[0])

    # Stack into 3D volume
    slices = [ds.pixel_array for _, ds in dicom_files]
    volume = np.stack(slices, axis=0)

    # Apply rescale slope/intercept (for Hounsfield units)
    first_ds = dicom_files[0][1]
    if hasattr(first_ds, 'RescaleSlope') and hasattr(first_ds, 'RescaleIntercept'):
        volume = volume * first_ds.RescaleSlope + first_ds.RescaleIntercept

    # Extract metadata
    metadata = {
        'PatientID': getattr(first_ds, 'PatientID', 'Unknown'),
        'PatientAge': getattr(first_ds, 'PatientAge', 'Unknown'),
        'PatientSex': getattr(first_ds, 'PatientSex', 'Unknown'),
        'StudyDate': getattr(first_ds, 'StudyDate', 'Unknown'),
        'StudyDescription': getattr(first_ds, 'StudyDescription', 'Unknown'),
        'SeriesDescription': getattr(first_ds, 'SeriesDescription', 'Unknown'),
        'Modality': getattr(first_ds, 'Modality', 'Unknown'),
        'SliceThickness': float(getattr(first_ds, 'SliceThickness', 0)),
        'PixelSpacing': [float(x) for x in getattr(first_ds, 'PixelSpacing', [0, 0])],
        'ImagePositionPatient': [float(x) for x in getattr(first_ds, 'ImagePositionPatient', [0, 0, 0])],
        'NumberOfSlices': len(dicom_files),
        'Rows': int(getattr(first_ds, 'Rows', 0)),
        'Columns': int(getattr(first_ds, 'Columns', 0)),
    }

    return volume, metadata


def load_nifti_volume(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load a NIfTI volume file.

    Args:
        file_path: Path to .nii or .nii.gz file

    Returns:
        tuple: (volume, affine)
            - volume: 3D numpy array
            - affine: 4x4 affine transformation matrix

    Raises:
        ImportError: If nibabel is not installed
        FileNotFoundError: If file doesn't exist
    """
    if not NIBABEL_AVAILABLE:
        raise ImportError(
            "nibabel is required for NIfTI loading. "
            "Install with: pip install nibabel"
        )

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Load NIfTI
    nifti_img = nib.load(str(file_path))
    volume = nifti_img.get_fdata()
    affine = nifti_img.affine

    return volume, affine


def extract_dicom_metadata(dicom_file: str) -> Dict:
    """
    Extract metadata from a single DICOM file.

    Args:
        dicom_file: Path to DICOM file

    Returns:
        dict: Extracted metadata
    """
    if not PYDICOM_AVAILABLE:
        raise ImportError("pydicom is required")

    ds = dcmread(dicom_file)

    metadata = {}
    for elem in ds:
        try:
            metadata[elem.name] = str(elem.value)
        except:
            continue

    return metadata
