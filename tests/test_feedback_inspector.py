"""Synthetic edge cases are copies of saved samples, never new robot data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robot_tools.feedback_inspector import ValidationError, analyze_case, load_case, main, render_html, validate_case


class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.empty = load_case(ROOT / "samples/empty_grasp_13.json")
        cls.static = load_case(ROOT / "samples/static_conversion_summary.json")

    def synthetic(self, sample):
        result = copy.deepcopy(sample)
        result["data_kind"] = "synthetic_test"
        return result

    def test_real_empty_grasp_observations(self):
        result = analyze_case(self.empty)
        codes = {f["code"] for f in result["findings"]}
        self.assertIn("CLOSURE_FEEDBACK_UNCHANGED", codes)
        self.assertIn("LIFT_WITHOUT_GRASP_VERIFICATION", codes)
        self.assertEqual(result["metrics"]["closure_sample_count"], 12)
        self.assertEqual(result["metrics"]["closure_actual_min_raw"], 2014)
        self.assertTrue(result["review_required"])

    def test_real_static_recording_does_not_become_motor_fault_or_success(self):
        result = analyze_case(self.static)
        codes = {f["code"] for f in result["findings"]}
        self.assertIn("RECORDING_WITHOUT_COMMANDS", codes)
        self.assertIn("REPORTED_ALIGNMENT_CHECKS_PASSED", codes)
        self.assertIn("NOT_TRAINING_READY", codes)
        self.assertIn("TASK_OUTCOME_UNKNOWN", codes)
        self.assertNotIn("CLOSURE_FEEDBACK_UNCHANGED", codes)
        self.assertFalse(result["metrics"]["training_ready"])
        self.assertIsNone(result["metrics"]["success"])
        self.assertFalse(result["review_required"])

    def test_synthetic_observed_closure_does_not_raise_unchanged_feedback(self):
        case = self.synthetic(self.empty)
        for row in case["samples"]:
            row["actual_raw"]["gripper"] = row["goal_raw"]["gripper"]
        codes = {f["code"] for f in analyze_case(case)["findings"]}
        self.assertNotIn("CLOSURE_FEEDBACK_UNCHANGED", codes)

    def test_zero_commands_does_not_override_a_human_outcome_label(self):
        case = self.synthetic(self.static)
        case["conversion_summary"]["success"] = True
        case["conversion_summary"]["outcome_source"] = "human_observation"
        result = analyze_case(case)
        self.assertTrue(result["metrics"]["success"])
        self.assertEqual(result["metrics"]["outcome_source"], "human_observation")
        self.assertTrue(result["metrics"]["check_only"])
        self.assertFalse(result["metrics"]["controller_entry_called"])
        self.assertIn("action_definition", result["metrics"])
        self.assertFalse(result["review_required"])
        self.assertIn("SOURCE_TASK_OUTCOME_RECORDED", {f["code"] for f in result["findings"]})

    def test_synthetic_unchanged_goal_is_not_treated_as_failed_movement(self):
        case = self.synthetic(self.empty)
        for row in case["samples"]:
            row["goal_raw"]["gripper"] = 2014
        self.assertNotIn("CLOSURE_FEEDBACK_UNCHANGED", {f["code"] for f in analyze_case(case)["findings"]})

    def test_reject_duplicate_and_backwards_times(self):
        for bad_time in (self.empty["samples"][0]["elapsed_seconds"], 0):
            case = self.synthetic(self.empty)
            case["samples"][1]["elapsed_seconds"] = bad_time
            with self.assertRaises(ValidationError):
                validate_case(case)

    def test_reject_boolean_nonfinite_and_negative_times(self):
        for value in (True, float("nan"), float("inf"), -1, "2.0"):
            case = self.synthetic(self.empty)
            case["samples"][0]["elapsed_seconds"] = value
            with self.assertRaises(ValidationError):
                validate_case(case)

    def test_reject_noninteger_negative_and_boolean_position_counts(self):
        for value in (2014.0, 1.5, -1, True, "2014"):
            case = self.synthetic(self.empty)
            case["samples"][0]["actual_raw"]["gripper"] = value
            with self.assertRaises(ValidationError):
                validate_case(case)

    def test_reject_unsupported_units(self):
        case = self.synthetic(self.empty)
        case["units"]["position"] = "degrees"
        with self.assertRaises(ValidationError):
            validate_case(case)

    def test_reject_missing_feedback_and_bad_indices(self):
        case = self.synthetic(self.empty)
        del case["samples"][0]["actual_raw"]
        with self.assertRaises(ValidationError):
            validate_case(case)
        case = self.synthetic(self.empty)
        case["selection"]["indices_zero_based"][0] = 0
        with self.assertRaises(ValidationError):
            validate_case(case)

    def test_reject_invalid_source_sha_and_local_paths(self):
        for field, value in (("sha256", "not-a-hash"), ("file_name", "C:/private/report.json")):
            case = self.synthetic(self.empty)
            case["sources"][0][field] = value
            with self.assertRaises(ValidationError):
                validate_case(case)

    def test_reject_noninteger_quality_counts_and_inconsistent_raw_counts(self):
        for field, value in (("rows", 27.0), ("quality_flagged_rows", True), ("quality_flagged_rows", 28), ("raw_states", 46)):
            case = self.synthetic(self.static)
            case["conversion_summary"][field] = value
            with self.assertRaises(ValidationError):
                validate_case(case)

    def test_check_only_cannot_become_training_ready(self):
        case = self.synthetic(self.static)
        case["conversion_summary"]["training_ready"] = True
        with self.assertRaises(ValidationError):
            validate_case(case)

    def test_threshold_exceedance_is_reported_even_with_zero_flags(self):
        case = self.synthetic(self.static)
        case["conversion_summary"]["max_image_offset_s"] = 0.3
        self.assertIn("REPORTED_THRESHOLD_EXCEEDED", {f["code"] for f in analyze_case(case)["findings"]})

    def test_json_loader_rejects_nonfinite_constants_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic_invalid.json"
            for content in ('{"x":NaN}', '{"x":1,"x":2}'):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValidationError):
                    load_case(path)

    def test_html_escapes_untrusted_text(self):
        case = self.synthetic(self.static)
        case["source_field_map"]["synthetic"] = "<script>alert(1)</script>"
        output = render_html(case, analyze_case(case))
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)

    def test_cli_emits_both_reports_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            args = [str(ROOT / "samples/empty_grasp_13.json"), "--output-dir", directory]
            self.assertEqual(main(args), 0)
            self.assertEqual(len(list(Path(directory).glob("*.report.*"))), 2)
            self.assertEqual(main(args), 2)


if __name__ == "__main__":
    unittest.main()
