#!/usr/bin/env python3
"""CLI entry point for cardio_imaging_runtime.

Usage: python -m cardio_imaging_runtime <subcommand>

Subcommands expose the runtime's capabilities for DICOM/NIfTI loading,
preprocessing, stenosis analysis, and synthetic data generation.
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="cardio_imaging_runtime",
        description="Cardiovascular imaging runtime for CTA/DSA analysis",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # --- make_synthetic_dicom ---
    sub = subparsers.add_parser(
        "make_synthetic_dicom",
        help="Generate synthetic CTA and DSA DICOM files for testing"
    )
    sub.add_argument("--output-dir", required=True, help="Output directory for synthetic DICOMs")
    sub.add_argument("--cta-shape", default="64,256,256", help="CTA volume shape (Z,Y,X)")
    sub.add_argument("--dsa-frames", type=int, default=30, help="Number of DSA cine frames")
    sub.add_argument("--dsa-shape", default="512,512", help="DSA frame shape (Y,X)")

    # --- load_series ---
    sub = subparsers.add_parser("load_series", help="Load DICOM series and report metadata")
    sub.add_argument("--input", required=True, help="Directory containing DICOM series")
    sub.add_argument("--output", required=True, help="Output JSON file")

    # --- load_dsa ---
    sub = subparsers.add_parser("load_dsa", help="Load DSA cine DICOM and report metadata")
    sub.add_argument("--input", required=True, help="Path to DSA DICOM file")
    sub.add_argument("--output", required=True, help="Output JSON file")

    # --- window ---
    sub = subparsers.add_parser("window", help="Apply cardiac window to volume")
    sub.add_argument("--input", required=True, help="Input .npy volume (HU)")
    sub.add_argument("--output", required=True, help="Output .npy windowed volume")
    sub.add_argument("--center", type=float, default=250, help="Window center (HU)")
    sub.add_argument("--width", type=float, default=700, help="Window width (HU)")

    # --- quantify_stenosis ---
    sub = subparsers.add_parser("quantify_stenosis", help="Quantify stenosis percentage")
    sub.add_argument("--method", required=True, choices=["diameter", "area"], help="Measurement method")
    sub.add_argument("--min-diameter", type=float, help="Minimum diameter (mm) for diameter method")
    sub.add_argument("--ref-diameter", type=float, help="Reference diameter (mm) for diameter method")
    sub.add_argument("--stenotic-area", help="Path to stenotic cross-section .npy for area method")
    sub.add_argument("--reference-area", help="Path to reference cross-section .npy for area method")
    sub.add_argument("--output", required=True, help="Output JSON file")

    # --- evaluate ---
    sub = subparsers.add_parser("evaluate", help="Evaluate AI report against expert annotation")
    sub.add_argument("--ai-report", required=True, help="Path to AI report JSON")
    sub.add_argument("--expert-annotation", required=True, help="Path to expert annotation JSON")
    sub.add_argument("--rubric", help="Path to evaluation rubric JSON (optional)")
    sub.add_argument("--output", required=True, help="Output evaluation JSON")

    args = parser.parse_args()

    try:
        if args.subcommand == "make_synthetic_dicom":
            from .synthetic_dicom import make_synthetic_cta_dicom, make_synthetic_dsa_dicom
            import numpy as np

            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Parse CTA shape
            cta_shape = tuple(int(x) for x in args.cta_shape.split(","))
            if len(cta_shape) != 3:
                parser.error("--cta-shape must be Z,Y,X")

            # Parse DSA shape
            dsa_shape = tuple(int(x) for x in args.dsa_shape.split(","))
            if len(dsa_shape) != 2:
                parser.error("--dsa-shape must be Y,X")

            print(f"Generating synthetic CTA series: shape={cta_shape}")
            cta_dir = output_dir / "cta_series"
            make_synthetic_cta_dicom(str(cta_dir), shape=cta_shape)
            print(f"  → {cta_dir}")

            print(f"Generating synthetic DSA cine: frames={args.dsa_frames}, shape={dsa_shape}")
            dsa_path = output_dir / "dsa_cine.dcm"
            make_synthetic_dsa_dicom(str(dsa_path), frames=args.dsa_frames, shape=dsa_shape)
            print(f"  → {dsa_path}")

            result = {
                "cta_series_dir": str(cta_dir),
                "dsa_cine_path": str(dsa_path),
                "cta_shape": cta_shape,
                "dsa_frames": args.dsa_frames,
                "dsa_shape": dsa_shape,
            }
            print(json.dumps(result, indent=2))

        elif args.subcommand == "load_series":
            from .dicom_loader import load_dicom_series

            volume, metadata = load_dicom_series(args.input)

            result = {
                "shape": volume.shape,
                "dtype": str(volume.dtype),
                "hu_min": float(volume.min()),
                "hu_max": float(volume.max()),
                "hu_mean": float(volume.mean()),
                "hu_std": float(volume.std()),
                "metadata": metadata,
            }

            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

            print(f"Loaded series: shape={volume.shape}, HU=[{volume.min():.1f}, {volume.max():.1f}]")
            print(f"  → {args.output}")

        elif args.subcommand == "load_dsa":
            from .synthetic_dicom import load_dsa_cine

            frames, metadata = load_dsa_cine(args.input)

            result = {
                "num_frames": frames.shape[0],
                "frame_shape": frames.shape[1:],
                "dtype": str(frames.dtype),
                "value_min": float(frames.min()),
                "value_max": float(frames.max()),
                "value_mean": float(frames.mean()),
                "metadata": metadata,
            }

            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

            print(f"Loaded DSA cine: frames={frames.shape[0]}, shape={frames.shape[1:]}")
            print(f"  → {args.output}")

        elif args.subcommand == "window":
            import numpy as np
            from .preprocessing import apply_cardiac_window

            volume = np.load(args.input)
            windowed = apply_cardiac_window(volume, center=args.center, width=args.width)

            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            np.save(args.output, windowed)

            print(f"Applied cardiac window: center={args.center}, width={args.width}")
            print(f"  → {args.output}")

        elif args.subcommand == "quantify_stenosis":
            import numpy as np
            from .stenosis_analysis import calculate_diameter_stenosis, calculate_area_stenosis

            if args.method == "diameter":
                if args.min_diameter is None or args.ref_diameter is None:
                    parser.error("diameter method requires --min-diameter and --ref-diameter")

                stenosis_pct = calculate_diameter_stenosis(args.min_diameter, args.ref_diameter)
                result = {
                    "method": "diameter",
                    "min_diameter_mm": args.min_diameter,
                    "reference_diameter_mm": args.ref_diameter,
                    "stenosis_percentage": stenosis_pct,
                }

            elif args.method == "area":
                if args.stenotic_area is None or args.reference_area is None:
                    parser.error("area method requires --stenotic-area and --reference-area")

                stenotic = np.load(args.stenotic_area)
                reference = np.load(args.reference_area)
                stenosis_pct = calculate_area_stenosis(stenotic, reference)

                result = {
                    "method": "area",
                    "stenotic_area_pixels": int(np.sum(stenotic > 0)),
                    "reference_area_pixels": int(np.sum(reference > 0)),
                    "stenosis_percentage": stenosis_pct,
                }

            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

            print(f"Stenosis: {stenosis_pct:.1f}%")
            print(f"  → {args.output}")

        elif args.subcommand == "evaluate":
            from .evaluation import evaluate_against_expert

            with open(args.ai_report) as f:
                ai_report = json.load(f)

            with open(args.expert_annotation) as f:
                expert_annotation = json.load(f)

            rubric = {}
            if args.rubric:
                with open(args.rubric) as f:
                    rubric = json.load(f)

            result = evaluate_against_expert(ai_report, expert_annotation, rubric)

            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

            print(f"Evaluation complete: overall_score={result['overall_score']:.2f}")
            print(f"  → {args.output}")

        else:
            parser.error(f"Unknown subcommand: {args.subcommand}")

    except ImportError as e:
        print(f"Failed to import module for {args.subcommand}: {e}", file=sys.stderr)
        print(f"Install required dependencies: pip install numpy pydicom", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error executing {args.subcommand}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
