"""
Basic tests for cardio_imaging_runtime.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from cardio_imaging_runtime import (
    apply_cardiac_window,
    calculate_diameter_stenosis,
    calculate_area_stenosis,
)

try:
    import pydicom
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False


def test_cardiac_window():
    """Test cardiac windowing function."""
    # Create test volume with known HU values
    volume = np.array([-100, 0, 100, 250, 500, 1000])

    windowed = apply_cardiac_window(volume, center=250, width=700)

    # Check output range
    assert windowed.min() >= 0.0
    assert windowed.max() <= 1.0

    # Center value should be around 0.5
    center_idx = 3  # 250 HU
    assert abs(windowed[center_idx] - 0.5) < 0.1


def test_diameter_stenosis():
    """Test diameter stenosis calculation."""
    # 50% stenosis
    stenosis = calculate_diameter_stenosis(min_diameter=2.0, reference_diameter=4.0)
    assert abs(stenosis - 50.0) < 0.01

    # 75% stenosis
    stenosis = calculate_diameter_stenosis(min_diameter=1.0, reference_diameter=4.0)
    assert abs(stenosis - 75.0) < 0.01

    # No stenosis
    stenosis = calculate_diameter_stenosis(min_diameter=4.0, reference_diameter=4.0)
    assert abs(stenosis - 0.0) < 0.01

    # Total occlusion
    stenosis = calculate_diameter_stenosis(min_diameter=0.0, reference_diameter=4.0)
    assert abs(stenosis - 100.0) < 0.01


def test_area_stenosis():
    """Test area stenosis calculation."""
    # Create mock cross-sections
    reference = np.ones((10, 10))  # 100 pixels
    stenotic = np.ones((5, 5))     # 25 pixels

    stenosis = calculate_area_stenosis(stenotic, reference)

    # Should be 75% stenosis (25/100 remaining area)
    assert abs(stenosis - 75.0) < 1.0


def test_stenosis_edge_cases():
    """Test edge cases."""
    # Zero reference diameter should raise error
    with pytest.raises(ValueError):
        calculate_diameter_stenosis(2.0, 0.0)

    # Negative reference should raise error
    with pytest.raises(ValueError):
        calculate_diameter_stenosis(2.0, -1.0)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


@pytest.mark.skipif(not PYDICOM_AVAILABLE, reason="pydicom not installed")
def test_synthetic_dicom_generation():
    """Test synthetic DICOM generation and loading roundtrip."""
    from cardio_imaging_runtime import (
        make_synthetic_cta_dicom,
        make_synthetic_dsa_dicom,
        load_dicom_series,
        load_dsa_cine,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Generate synthetic CTA series
        cta_dir = tmppath / "cta_series"
        cta_shape = (32, 128, 128)
        make_synthetic_cta_dicom(str(cta_dir), shape=cta_shape)

        # Verify CTA series was created
        assert cta_dir.exists()
        dcm_files = list(cta_dir.glob("*.dcm"))
        assert len(dcm_files) == cta_shape[0]

        # Load it back
        volume, metadata = load_dicom_series(str(cta_dir))
        assert volume.shape == cta_shape
        assert metadata["Modality"] == "CT"
        assert metadata["NumberOfSlices"] == cta_shape[0]

        # Check HU range is reasonable for cardiac CT
        assert -200 < volume.min() < 100  # Background/air
        assert 200 < volume.max() < 600   # Contrast-enhanced vessels

        # Generate synthetic DSA cine
        dsa_path = tmppath / "dsa_cine.dcm"
        dsa_frames = 20
        dsa_shape = (256, 256)
        make_synthetic_dsa_dicom(str(dsa_path), frames=dsa_frames, shape=dsa_shape)

        # Verify DSA was created
        assert dsa_path.exists()

        # Load it back
        frames, dsa_metadata = load_dsa_cine(str(dsa_path))
        assert frames.shape == (dsa_frames, *dsa_shape)
        assert dsa_metadata["Modality"] == "XA"
        assert dsa_metadata["NumberOfFrames"] == dsa_frames
