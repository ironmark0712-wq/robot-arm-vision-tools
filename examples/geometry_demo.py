"""Synthetic known-height pixel-to-board-to-base geometry demonstration.

This does not open an image, camera, robot, simulator, or training framework.
Every calibration/height value below is supplied synthetic data, not a measured
calibration or an estimate of unknown object depth.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from robot_tools.pick_geometry import self_check


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        help="Optional new JSON file; otherwise print to stdout. No implicit runs directory.",
    )
    args = parser.parse_args(argv)
    report = {
        "data_kind": "synthetic_geometry_demo",
        "known_parameters": {
            "image_size_width_height": [640, 480],
            "camera_matrix": [[580., 0., 320.], [0., 590., 240.], [0., 0., 1.]],
            "distortion_coefficients": [-.1, .025, .001, -.001, 0.],
            "board_to_camera_rotation_vector_rad": [.22, -.17, .06],
            "board_origin_camera_mm": [-65., -40., 520.],
            "board_to_base_z_rotation_rad": .35,
            "board_origin_base_mm": [100., -70., 20.],
            "signed_board_z_planes_mm": [0., -40., 40.],
        },
        "interpretation": [
            "Intersect a pixel ray with an explicitly supplied board-Z plane.",
            "Known intrinsics, distortion, extrinsics, and selected-point height are required.",
            "The board-Z normal is signed and is not automatically world-up.",
            "A bounding-box centre does not establish a physical grasp point or unknown depth.",
            "Roundtrip differences are synthetic numerical checks, not real robot accuracy.",
        ],
        "check": self_check(),
    }
    serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output is None:
        print(serialized, end="")
    else:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        except OSError as exc:
            parser.error(f"cannot write requested output: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
