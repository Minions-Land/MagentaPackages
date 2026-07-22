"""
Synthetic DICOM generation for testing without patient data.

Generates simulated CTA volumes and DSA cine sequences as valid DICOM files.
"""

import datetime
from pathlib import Path
from typing import Tuple, Dict

import numpy as np

try:
    import pydicom
    from pydicom.dataset import FileDataset, Dataset
    from pydicom.uid import generate_uid
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False


def make_synthetic_cta_dicom(
    output_dir: str,
    shape: Tuple[int, int, int] = (64, 256, 256),
    slice_thickness: float = 1.0,
    pixel_spacing: Tuple[float, float] = (0.5, 0.5)
) -> None:
    """
    Generate a synthetic CTA DICOM series.

    Creates a multi-slice CT series with synthetic grayscale data simulating
    coronary CTA. Each slice is saved as a separate DICOM file.

    Args:
        output_dir: Directory to save DICOM files
        shape: Volume shape (Z, Y, X) - number of slices and dimensions
        slice_thickness: Slice thickness in mm
        pixel_spacing: Pixel spacing (row, column) in mm

    Raises:
        ImportError: If pydicom is not installed
    """
    if not PYDICOM_AVAILABLE:
        raise ImportError("pydicom required for DICOM generation")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    num_slices, rows, cols = shape

    # Generate synthetic volume with vessel-like structures
    # Simulate cardiac CT with blood pool ~300-400 HU, myocardium ~50 HU, background ~-50 HU
    volume = np.random.normal(-50, 30, shape).astype(np.int16)

    # Add vessel-like bright structures
    for z in range(num_slices):
        # Simulate vessels as bright tubular structures
        center_y = rows // 2 + int(10 * np.sin(z * 0.1))
        center_x = cols // 2 + int(10 * np.cos(z * 0.1))

        y, x = np.ogrid[:rows, :cols]
        mask = ((y - center_y)**2 + (x - center_x)**2) < 64  # Circular vessel
        volume[z, mask] = np.random.normal(350, 50, mask.sum()).astype(np.int16)

    # Create series metadata
    study_uid = generate_uid()
    series_uid = generate_uid()
    now = datetime.datetime.now()

    for slice_idx in range(num_slices):
        # Create file meta information
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'  # CT Image Storage
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'  # Explicit VR Little Endian

        # Create the FileDataset instance
        ds = FileDataset(
            None, {},
            file_meta=file_meta,
            preamble=b"\0" * 128
        )

        # Patient module
        ds.PatientName = "SYNTHETIC^CTA"
        ds.PatientID = "SYNTH001"
        ds.PatientBirthDate = "19700101"
        ds.PatientSex = "M"
        ds.PatientAge = "055Y"

        # Study module
        ds.StudyDate = now.strftime("%Y%m%d")
        ds.StudyTime = now.strftime("%H%M%S")
        ds.AccessionNumber = "ACC001"
        ds.StudyDescription = "CARDIAC CTA SYNTHETIC"
        ds.StudyInstanceUID = study_uid
        ds.StudyID = "1"

        # Series module
        ds.SeriesDate = now.strftime("%Y%m%d")
        ds.SeriesTime = now.strftime("%H%M%S")
        ds.Modality = "CT"
        ds.SeriesDescription = "CTA Coronary Synthetic"
        ds.SeriesInstanceUID = series_uid
        ds.SeriesNumber = 1

        # Image module
        ds.InstanceNumber = slice_idx + 1
        ds.ImagePositionPatient = [0.0, 0.0, float(slice_idx * slice_thickness)]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.SliceThickness = slice_thickness
        ds.SliceLocation = float(slice_idx * slice_thickness)

        # Image Pixel module
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows = rows
        ds.Columns = cols
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1  # Signed

        # CT-specific
        ds.PixelSpacing = list(pixel_spacing)
        ds.RescaleIntercept = 0
        ds.RescaleSlope = 1
        ds.KVP = 120

        # Set pixel data
        ds.PixelData = volume[slice_idx].tobytes()

        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID

        # Save
        filename = output_path / f"slice_{slice_idx:04d}.dcm"
        ds.save_as(str(filename), write_like_original=False)


def make_synthetic_dsa_dicom(
    output_path: str,
    frames: int = 30,
    shape: Tuple[int, int] = (512, 512),
    frame_time: float = 33.33  # ms, ~30 fps
) -> None:
    """
    Generate a synthetic DSA cine DICOM file.

    Creates a multi-frame XA (X-Ray Angiography) DICOM with synthetic
    grayscale frames simulating digital subtraction angiography.

    Args:
        output_path: Path to save DICOM file
        frames: Number of cine frames
        shape: Frame shape (rows, cols)
        frame_time: Time between frames in milliseconds

    Raises:
        ImportError: If pydicom is not installed
    """
    if not PYDICOM_AVAILABLE:
        raise ImportError("pydicom required for DICOM generation")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    rows, cols = shape

    # Generate synthetic cine with vessel filling
    # Simulate contrast flowing through vessels over time
    cine_data = np.zeros((frames, rows, cols), dtype=np.uint16)

    for frame_idx in range(frames):
        # Background
        frame = np.random.normal(100, 10, shape).astype(np.uint16)

        # Vessel contrast appearance (increases then decreases)
        contrast_phase = np.sin(frame_idx / frames * np.pi)
        if contrast_phase > 0:
            center_y = rows // 2
            center_x = cols // 2

            y, x = np.ogrid[:rows, :cols]
            # Simulate vessel structure
            vessel_mask = ((y - center_y)**2 / 100 + (x - center_x)**2 / 400) < (frame_idx * 2)
            frame[vessel_mask] = np.clip(
                frame[vessel_mask] + int(contrast_phase * 200),
                0, 65535
            ).astype(np.uint16)

        cine_data[frame_idx] = frame

    # Create file meta
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.12.1'  # XA Image Storage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'

    # Create FileDataset
    ds = FileDataset(
        None, {},
        file_meta=file_meta,
        preamble=b"\0" * 128
    )

    # Patient module
    ds.PatientName = "SYNTHETIC^DSA"
    ds.PatientID = "SYNTH002"
    ds.PatientBirthDate = "19700101"
    ds.PatientSex = "M"

    # Study module
    now = datetime.datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")
    ds.AccessionNumber = "ACC002"
    ds.StudyDescription = "DSA CORONARY SYNTHETIC"
    ds.StudyInstanceUID = generate_uid()
    ds.StudyID = "2"

    # Series module
    ds.SeriesDate = now.strftime("%Y%m%d")
    ds.SeriesTime = now.strftime("%H%M%S")
    ds.Modality = "XA"
    ds.SeriesDescription = "DSA Cine Synthetic"
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = 1

    # Multi-frame module
    ds.NumberOfFrames = frames
    ds.FrameTime = frame_time

    # Image Pixel module
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0  # Unsigned

    # Set pixel data (all frames concatenated)
    ds.PixelData = cine_data.tobytes()

    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID

    # Save
    ds.save_as(str(output_path), write_like_original=False)


def load_dsa_cine(dicom_path: str) -> Tuple[np.ndarray, Dict]:
    """
    Load a DSA cine DICOM file.

    Args:
        dicom_path: Path to multi-frame DICOM

    Returns:
        tuple: (frames, metadata)
            - frames: 4D array (num_frames, rows, cols)
            - metadata: dict of DICOM tags

    Raises:
        ImportError: If pydicom is not installed
    """
    if not PYDICOM_AVAILABLE:
        raise ImportError("pydicom required for DICOM loading")

    ds = pydicom.dcmread(dicom_path)

    # Extract number of frames
    num_frames = int(getattr(ds, 'NumberOfFrames', 1))
    rows = int(ds.Rows)
    cols = int(ds.Columns)

    # Reshape pixel data
    pixel_array = np.frombuffer(ds.PixelData, dtype=np.uint16)
    frames = pixel_array.reshape((num_frames, rows, cols))

    metadata = {
        'PatientID': getattr(ds, 'PatientID', 'Unknown'),
        'StudyDescription': getattr(ds, 'StudyDescription', 'Unknown'),
        'SeriesDescription': getattr(ds, 'SeriesDescription', 'Unknown'),
        'Modality': getattr(ds, 'Modality', 'Unknown'),
        'NumberOfFrames': num_frames,
        'Rows': rows,
        'Columns': cols,
        'FrameTime': float(getattr(ds, 'FrameTime', 0)),
    }

    return frames, metadata
