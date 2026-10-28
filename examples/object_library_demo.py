"""Synthetic class-library update demo; no model, camera or robot access."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from robot_tools.object_library import plan_update, validate_batch


def demo():
    # These are invented labels and boxes, not annotations from an experiment.
    existing = ["breadboard", "servo", "hex_key"]
    incoming = [{"label": "nut", "box": [10, 20, 100, 80]}]
    validated = validate_batch(incoming, width=640, height=480)
    appended = plan_update(existing, [row["label"] for row in validated], "append")

    replacement = [{"label": " SERVO ", "box": [30, 40, 90, 120]}]
    replacement_rows = validate_batch(replacement, width=640, height=480)
    replaced = plan_update(appended["merged_labels"],
                           [row["label"] for row in replacement_rows],
                           "replace_selected")
    old_ids_stable = [row["class_id"] for row in appended["rows"][:len(existing)]] == list(range(len(existing)))
    replacement_ids_stable = [(row["class_id"], row["code"], row["label"]) for row in replaced["rows"]] == [
        (row["class_id"], row["code"], row["label"]) for row in appended["rows"]]
    assert old_ids_stable and replacement_ids_stable

    invalid = {"label": "outside_image", "box": [10, 20, 641, 80]}
    try:
        validate_batch([invalid], width=640, height=480)
    except ValueError as exc:
        rejection = {"rejected": True, "reason": str(exc)}
    else:
        raise AssertionError("Invalid synthetic box was accepted")

    return {
        "schema": "object-library-demo.v1",
        "data_source": "synthetic",
        "scope": "Label/box validation and stable class-row planning only",
        "synthetic_input": {"existing_labels": existing, "incoming_samples": incoming,
                            "replacement_samples": replacement, "image_size_px": [640, 480]},
        "append_plan": appended,
        "selected_replacement_plan": replaced,
        "old_ids_stable_after_append": old_ids_stable,
        "ids_and_labels_stable_after_replacement": replacement_ids_stable,
        "invalid_box_example": {"input": invalid, **rejection},
        "model_loaded": False,
        "camera_opened": False,
        "motor_access": False,
        "recognition_accuracy_evaluated": False,
    }


if __name__ == "__main__":
    print(json.dumps(demo(), ensure_ascii=False, indent=2, allow_nan=False))
