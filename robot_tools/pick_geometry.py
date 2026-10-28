"""Offline geometry only. No camera/serial access; all spatial units are mm.

Board +Z is a signed normal, NOT automatically the upward tabletop direction.
Physical transforms and object grasp heights must be measured separately.
Adapted from the existing project module; numerical functions are unchanged.
The release CLI prints synthetic checks or writes an explicitly chosen file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def finite_array(value, shape, name):
    result = np.asarray(value, dtype=np.float64)
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f"{name}: invalid shape or nonfinite values")
    return result


def rotation(value):
    result = finite_array(value, (3, 3), "rotation")
    if not np.allclose(result.T @ result, np.eye(3), atol=1e-7) or not np.isclose(
        np.linalg.det(result), 1.0, atol=1e-7
    ):
        raise ValueError("rotation must be a proper orthonormal rotation")
    return result


def rigid_transform(value):
    result = finite_array(value, (4, 4), "transform")
    rotation(result[:3, :3])
    if not np.allclose(result[3], [0, 0, 0, 1], atol=1e-10):
        raise ValueError("invalid homogeneous transform bottom row")
    return result


def pixel_at_board_height(pixel_uv, camera_matrix, distortion, board_to_camera,
                          board_origin_camera_mm, signed_board_z_mm, image_size):
    """Intersect an undistorted pixel ray with board Z=specified height.

    This does not recover unknown depth from YOLO. The height must be supplied
    for the actual selected visible grasp point; a bounding-box centre alone
    does not guarantee such a point, especially for irregular toys.
    """
    uv = finite_array(pixel_uv, (2,), "pixel")
    size = finite_array(image_size, (2,), "image size")
    if np.any(size <= 0) or np.any(size != np.floor(size)):
        raise ValueError("image dimensions must be positive integers")
    if np.any(uv < 0) or np.any(uv >= size):
        raise ValueError("pixel outside image")
    k = finite_array(camera_matrix, (3, 3), "camera matrix")
    if k[0, 0] <= 0 or k[1, 1] <= 0 or not np.allclose(k[2], [0, 0, 1]):
        raise ValueError("invalid camera matrix")
    d = np.asarray(distortion, dtype=np.float64)
    if d.size not in (4, 5, 8, 12, 14) or not np.isfinite(d).all():
        raise ValueError("invalid distortion coefficients")
    r = rotation(board_to_camera)
    t = finite_array(board_origin_camera_mm, (3,), "translation")
    z = float(signed_board_z_mm)
    if not np.isfinite(z):
        raise ValueError("invalid signed plane height")
    normalized = cv2.undistortPoints(uv.reshape(1, 1, 2), k, d)[0, 0]
    origin = -r.T @ t
    ray = r.T @ np.array([*normalized, 1.0])
    if abs(ray[2]) < 1e-9:
        raise ValueError("pixel ray parallel to requested plane")
    distance = (z - origin[2]) / ray[2]
    if distance <= 0:
        raise ValueError("intersection behind camera")
    point = origin + distance * ray
    point[2] = z
    return point


def board_point_to_base(point_board_mm, board_to_base_mm):
    transform = rigid_transform(board_to_base_mm)
    point = finite_array(point_board_mm, (3,), "board point")
    return (transform @ np.r_[point, 1.0])[:3]


def self_check():
    k = np.array([[580., 0., 320.], [0., 590., 240.], [0., 0., 1.]])
    d = np.array([-.1, .025, .001, -.001, 0.])
    rvec = np.array([.22, -.17, .06])
    r = cv2.Rodrigues(rvec)[0]
    t = np.array([-65., -40., 520.])
    transform = np.eye(4)
    transform[:3, :3] = cv2.Rodrigues(np.array([0., 0., .35]))[0]
    transform[:3, 3] = [100., -70., 20.]
    cases = []
    for point in ([25., 30., 0.], [90., 50., -40.], [60., 45., 40.]):
        point = np.array(point)
        uv = cv2.projectPoints(point.reshape(1, 3), rvec, t, k, d)[0].reshape(2)
        mapped = pixel_at_board_height(uv, k, d, r, t, point[2], (640, 480))
        error = float(np.linalg.norm(mapped - point))
        assert error < 1e-5, error
        actual_base = board_point_to_base(mapped, transform)
        expected_base = transform[:3, :3] @ point + transform[:3, 3]
        assert np.linalg.norm(actual_base - expected_base) < 1e-5
        assumed_table = pixel_at_board_height(uv, k, d, r, t, 0., (640, 480))
        cases.append({"synthetic_point_board_mm": point.tolist(),
                      "pixel_uv": uv.tolist(), "roundtrip_error_mm": error,
                      "wrong_table_assumption_xy_error_mm": float(
                          np.linalg.norm(assumed_table[:2] - point[:2]))})
    rejected = []
    bad_transform = np.eye(4)
    bad_transform[0, 0] = -1
    for name, action in (
        ("nonfinite", lambda: pixel_at_board_height([float('nan'), 2], k, d, r, t, 0, (640, 480))),
        ("outside_image", lambda: pixel_at_board_height([640, 2], k, d, r, t, 0, (640, 480))),
        ("behind_camera", lambda: pixel_at_board_height([320, 240], k, d, np.eye(3), [0, 0, 500], -600, (640, 480))),
        ("parallel_ray", lambda: pixel_at_board_height([320, 240], k, np.zeros(5), cv2.Rodrigues(np.array([0., np.pi / 2, 0.]))[0], t, 0, (640, 480))),
        ("reflected_transform", lambda: board_point_to_base([0, 0, 0], bad_transform)),
    ):
        try:
            action()
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(f"unsafe input accepted: {name}")
    return {"result": "SYNTHETIC_HEIGHT_GEOMETRY_PASSED_NOT_PHYSICAL",
            "cases": cases, "rejected_inputs": rejected, "motion_sent": False,
            "physical_mapping_verified": False,
            "limitations": ["Synthetic roundtrip is not physical accuracy",
                            "Board normal sign must be physically established",
                            "Measured grasp point height and board-to-base transform required",
                            "Current observation pose and camera rigidity must be verified"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", required=True)
    parser.add_argument(
        "--output", type=Path,
        help="Optional new JSON file. Default: stdout. Existing files are never overwritten.",
    )
    args = parser.parse_args(argv)
    report = self_check()
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
