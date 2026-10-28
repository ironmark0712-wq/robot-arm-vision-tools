"""Synthetic checks adapted from the original geometry self-check.

No image capture, robot, simulator, training, or physical accuracy validation.
The dependency skip is explicit: a skipped check is not a passed check.
"""
import importlib.util
import unittest


HAS_GEOMETRY_DEPENDENCIES = all(
    importlib.util.find_spec(name) is not None for name in ("cv2", "numpy")
)
if HAS_GEOMETRY_DEPENDENCIES:
    import cv2
    import numpy as np
    from robot_tools.pick_geometry import (
        board_point_to_base, pixel_at_board_height, rigid_transform, self_check,
    )


@unittest.skipUnless(
    HAS_GEOMETRY_DEPENDENCIES,
    "geometry requires existing NumPy and OpenCV; dependencies were not installed",
)
class PickGeometryTests(unittest.TestCase):
    def setUp(self):
        # All values below are synthetic, matching the original self-check.
        self.k = np.array([[580., 0., 320.], [0., 590., 240.], [0., 0., 1.]])
        self.d = np.array([-.1, .025, .001, -.001, 0.])
        self.rvec = np.array([.22, -.17, .06])
        self.r = cv2.Rodrigues(self.rvec)[0]
        self.t = np.array([-65., -40., 520.])
        self.board_to_base = np.eye(4)
        self.board_to_base[:3, :3] = cv2.Rodrigues(np.array([0., 0., .35]))[0]
        self.board_to_base[:3, 3] = [100., -70., 20.]

    def project(self, point):
        return cv2.projectPoints(
            np.asarray(point, dtype=float).reshape(1, 3),
            self.rvec, self.t, self.k, self.d,
        )[0].reshape(2)

    def intersect(self, pixel, height):
        return pixel_at_board_height(
            pixel, self.k, self.d, self.r, self.t, height, (640, 480),
        )

    def test_known_signed_plane_height_roundtrips_synthetic_points(self):
        # This tolerance checks a numerical identity, not real-world accuracy.
        for point in ([25., 30., 0.], [90., 50., -40.], [60., 45., 40.]):
            with self.subTest(point=point):
                mapped = self.intersect(self.project(point), point[2])
                np.testing.assert_allclose(mapped, point, atol=1e-5, rtol=0)

    def test_board_to_base_transform_matches_declared_synthetic_transform(self):
        point = np.array([60., 45., 40.])
        mapped = board_point_to_base(point, self.board_to_base)
        expected = self.board_to_base[:3, :3] @ point + self.board_to_base[:3, 3]
        np.testing.assert_allclose(mapped, expected, atol=1e-5, rtol=0)

    def test_wrong_assumed_height_does_not_recover_unknown_depth(self):
        point = np.array([60., 45., 40.])
        wrongly_assumed_table = self.intersect(self.project(point), 0.)
        self.assertEqual(wrongly_assumed_table[2], 0.)
        self.assertFalse(np.allclose(wrongly_assumed_table, point, atol=1e-5))

    def test_nonfinite_pixel_is_rejected(self):
        with self.assertRaises(ValueError):
            self.intersect([float("nan"), 2.], 0.)

    def test_pixel_at_exclusive_image_boundary_is_rejected(self):
        with self.assertRaises(ValueError):
            self.intersect([640., 2.], 0.)

    def test_intersection_behind_camera_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "behind camera"):
            pixel_at_board_height(
                [320., 240.], self.k, self.d, np.eye(3),
                [0., 0., 500.], -600., (640, 480),
            )

    def test_parallel_ray_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "parallel"):
            pixel_at_board_height(
                [320., 240.], self.k, np.zeros(5),
                cv2.Rodrigues(np.array([0., np.pi / 2, 0.]))[0],
                self.t, 0., (640, 480),
            )

    def test_reflection_is_not_a_proper_rigid_transform(self):
        reflected = np.eye(4)
        reflected[0, 0] = -1.
        with self.assertRaises(ValueError):
            rigid_transform(reflected)

    def test_original_self_check_preserves_synthetic_evidence_boundary(self):
        result = self_check()
        self.assertEqual(result["result"], "SYNTHETIC_HEIGHT_GEOMETRY_PASSED_NOT_PHYSICAL")
        self.assertEqual(len(result["cases"]), 3)
        self.assertEqual(set(result["rejected_inputs"]), {
            "nonfinite", "outside_image", "behind_camera", "parallel_ray", "reflected_transform",
        })
        self.assertFalse(result["motion_sent"])
        self.assertFalse(result["physical_mapping_verified"])


if __name__ == "__main__":
    unittest.main()
