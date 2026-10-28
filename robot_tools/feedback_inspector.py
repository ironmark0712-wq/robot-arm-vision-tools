"""Inspect saved robot feedback excerpts without importing robot software.

Standard library only. This program does not open a camera, serial port,
controller, simulator, network connection, or training framework.
"""
from __future__ import annotations

import argparse
from collections import Counter
import html
import json
import math
from pathlib import Path
import re
import sys

SCHEMA = "robot-feedback-inspector.case.v1"
POSITION_UNIT = "native_servo_position_counts"


class ValidationError(ValueError):
    """The supplied data cannot be interpreted under the declared schema."""


def _object(value, name):
    if not isinstance(value, dict):
        raise ValidationError(f"{name}: expected an object")
    return value


def _keys(value, names, name):
    _object(value, name)
    missing = set(names) - set(value)
    if missing:
        raise ValidationError(f"{name}: missing {', '.join(sorted(missing))}")


def _number(value, name, minimum=None, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValidationError(f"{name}: expected a finite number, not a boolean")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{name}: must be >= {minimum}")
    if positive and value <= 0:
        raise ValidationError(f"{name}: must be > 0")
    return value


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValidationError(f"{name}: expected an integer >= {minimum}")
    return value


def _boolean(value, name, nullable=False):
    if type(value) is not bool and not (nullable and value is None):
        raise ValidationError(f"{name}: expected {'boolean or null' if nullable else 'boolean'}")


def _string(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name}: expected a nonempty string")
    return value


def _sources(value):
    if not isinstance(value, list) or not value:
        raise ValidationError("sources: expected a nonempty list")
    for i, source in enumerate(value):
        name = f"sources[{i}]"
        _keys(source, ("file_name", "sha256", "role"), name)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", _string(source["file_name"], name + ".file_name")):
            raise ValidationError(name + ".file_name: use a basename without a local path")
        if not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
            raise ValidationError(name + ".sha256: expected 64 lowercase hexadecimal characters")
        _string(source["role"], name + ".role")


def validate_case(case):
    _keys(case, ("schema_version", "case_id", "case_type", "data_kind", "sources", "source_field_map"), "case")
    if case["schema_version"] != SCHEMA:
        raise ValidationError("unsupported schema_version")
    if not isinstance(case["case_id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", case["case_id"]):
        raise ValidationError("case_id: expected a portable lowercase identifier")
    if case["data_kind"] not in ("real_excerpt", "real_report_summary", "synthetic_test"):
        raise ValidationError("data_kind: unsupported provenance category")
    _sources(case["sources"])
    mapping = _object(case["source_field_map"], "source_field_map")
    if not mapping or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items()):
        raise ValidationError("source_field_map: expected nonempty string-to-string mapping")
    if case["case_type"] == "execution_excerpt":
        _validate_execution(case)
    elif case["case_type"] == "conversion_summary":
        _validate_conversion(case)
    else:
        raise ValidationError("case_type: unsupported case")
    return case


def _validate_execution(case):
    _keys(case, ("units", "selection", "context", "samples"), "execution case")
    if case["units"] != {"position": POSITION_UNIT, "time": "seconds_since_run_start"}:
        raise ValidationError("units: this adapter accepts native position counts and elapsed seconds only")
    selection = case["selection"]
    _keys(selection, ("array", "indices_zero_based", "original_sample_count"), "selection")
    if selection["array"] != "samples":
        raise ValidationError("selection.array: expected samples")
    total = _integer(selection["original_sample_count"], "original_sample_count", 1)
    indices = selection["indices_zero_based"]
    samples = case["samples"]
    if not isinstance(samples, list) or len(samples) < 2:
        raise ValidationError("samples: expected at least two records")
    if not isinstance(indices, list) or len(indices) != len(samples):
        raise ValidationError("selection indices must match the extracted record count")
    previous_time, previous_index = None, -1
    for i, row in enumerate(samples):
        name = f"samples[{i}]"
        _keys(row, ("source_sample_index", "elapsed_seconds", "stage", "goal_raw", "actual_raw"), name)
        idx = _integer(row["source_sample_index"], name + ".source_sample_index")
        _integer(indices[i], f"selection.indices_zero_based[{i}]")
        if idx != indices[i] or idx <= previous_index or idx >= total:
            raise ValidationError(name + ": source indices must match, increase, and stay inside the source array")
        timestamp = _number(row["elapsed_seconds"], name + ".elapsed_seconds", 0)
        if previous_time is not None and timestamp <= previous_time:
            raise ValidationError(name + ": timestamps must strictly increase; duplicates are not silently removed")
        if not isinstance(row["stage"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", row["stage"]):
            raise ValidationError(name + ".stage: invalid stage identifier")
        for field in ("goal_raw", "actual_raw"):
            if not isinstance(row[field], dict) or set(row[field]) != {"gripper"}:
                raise ValidationError(name + "." + field + ": this excerpt adapter expects only gripper")
            _integer(row[field]["gripper"], name + "." + field + ".gripper")
        previous_time, previous_index = timestamp, idx
    context = case["context"]
    _keys(context, ("grasp_verified", "place_verified", "gripper_contact_candidate"), "context")
    _boolean(context["grasp_verified"], "context.grasp_verified", True)
    _boolean(context["place_verified"], "context.place_verified", True)
    candidate = context["gripper_contact_candidate"]
    _keys(candidate, ("goal_raw", "actual_raw", "physically_verified"), "gripper_contact_candidate")
    _integer(candidate["goal_raw"], "candidate.goal_raw")
    _integer(candidate["actual_raw"], "candidate.actual_raw")
    _boolean(candidate["physically_verified"], "candidate.physically_verified", True)


def _validate_conversion(case):
    _keys(case, ("recording_summary", "conversion_summary"), "conversion case")
    recording = case["recording_summary"]
    _keys(recording, ("check_only", "controller_entry_called", "counts", "recording_complete",
                      "physical_grasp_or_place_inferred_from_program"), "recording_summary")
    for field in ("check_only", "controller_entry_called", "recording_complete", "physical_grasp_or_place_inferred_from_program"):
        _boolean(recording[field], "recording_summary." + field)
    _keys(recording["counts"], ("frames", "states", "commands"), "counts")
    for field in ("frames", "states", "commands"):
        _integer(recording["counts"][field], "counts." + field)
    summary = case["conversion_summary"]
    required = ("result", "training_ready", "originals_modified", "rows", "video_frames", "raw_frames", "raw_states",
                "fps", "quality_flagged_rows", "max_image_offset_s", "max_state_interpolation_gap_s", "outcome_source",
                "success", "state_units", "action_definition", "alignment_policy")
    _keys(summary, required, "conversion_summary")
    for field in ("training_ready", "originals_modified"):
        _boolean(summary[field], "conversion_summary." + field)
    _boolean(summary["success"], "conversion_summary.success", True)
    for field in ("rows", "video_frames", "raw_frames", "raw_states", "quality_flagged_rows"):
        _integer(summary[field], "conversion_summary." + field)
    if summary["quality_flagged_rows"] > summary["rows"]:
        raise ValidationError("quality_flagged_rows cannot exceed rows")
    for field in ("max_image_offset_s", "max_state_interpolation_gap_s"):
        _number(summary[field], "conversion_summary." + field, 0)
    _number(summary["fps"], "conversion_summary.fps", positive=True)
    for field in ("result", "outcome_source", "state_units", "action_definition"):
        _string(summary[field], "conversion_summary." + field)
    if summary["raw_frames"] != recording["counts"]["frames"] or summary["raw_states"] != recording["counts"]["states"]:
        raise ValidationError("raw frame/state counts disagree between source summaries")
    policy = summary["alignment_policy"]
    _keys(policy, ("grid_origin_raw_time_s", "last_observation_dropped_no_next_action", "max_image_offset_s",
                   "max_state_interpolation_gap_s", "max_state_read_duration_s"), "alignment_policy")
    _boolean(policy["last_observation_dropped_no_next_action"], "last_observation_dropped_no_next_action")
    for field in ("grid_origin_raw_time_s", "max_image_offset_s", "max_state_interpolation_gap_s", "max_state_read_duration_s"):
        _number(policy[field], "alignment_policy." + field, 0)
    if summary["training_ready"] and recording["check_only"]:
        raise ValidationError("a check-only recording cannot be labelled training_ready")


def _reject_constant(value):
    raise ValidationError("nonfinite JSON constant is not accepted: " + value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON key: " + key)
        result[key] = value
    return result


def load_case(path):
    try:
        raw = Path(path).read_text(encoding="utf-8")
        case = json.loads(raw, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON at line {exc.lineno}, column {exc.colno}") from exc
    return validate_case(case)


def analyze_case(case):
    validate_case(case)
    report = {"report_schema": "robot-feedback-inspector.report.v1", "case_id": case["case_id"],
              "case_type": case["case_type"], "data_kind": case["data_kind"], "sources": case["sources"],
              "scope": "Offline inspection of saved excerpts; no new robot experiment or hardware diagnosis.",
              "findings": [], "metrics": {}}
    def finding(code, level, message):
        report["findings"].append({"code": code, "level": level, "message": message})
    if case["case_type"] == "execution_excerpt":
        samples = case["samples"]
        close = [row for row in samples if row["stage"].startswith("CLOSE")]
        if len(close) >= 2:
            goals = [row["goal_raw"]["gripper"] for row in close]
            actual = [row["actual_raw"]["gripper"] for row in close]
            report["metrics"] = {"closure_sample_count": len(close), "closure_goal_min_raw": min(goals),
                "closure_goal_max_raw": max(goals), "closure_actual_min_raw": min(actual), "closure_actual_max_raw": max(actual),
                "closure_duration_s": close[-1]["elapsed_seconds"] - close[0]["elapsed_seconds"],
                "position_unit": POSITION_UNIT, "stages_in_excerpt": dict(Counter(row["stage"] for row in samples))}
            if max(goals) > min(goals) and max(actual) == min(actual):
                finding("CLOSURE_FEEDBACK_UNCHANGED", "review",
                        "Closing goals changed, but recorded gripper feedback showed no displacement. Review the observation and feedback; this does not identify a motor, friction, torque, or contact cause.")
            after_close = [row for row in samples if row["source_sample_index"] > close[-1]["source_sample_index"]]
            if any(row["stage"].startswith("LIFT") for row in after_close) and case["context"]["grasp_verified"] is not True:
                finding("LIFT_WITHOUT_GRASP_VERIFICATION", "review",
                        "The excerpt enters a lift-labelled stage while the source report does not confirm grasping. A stage name is not proof of physical lift distance.")
        finding("TASK_RESULT_NOT_INFERRED", "info", "Commands and completed stage labels do not establish physical grasp or placement success.")
    else:
        recording, summary = case["recording_summary"], case["conversion_summary"]
        report["metrics"] = {key: summary[key] for key in ("rows", "video_frames", "raw_frames", "raw_states", "quality_flagged_rows", "max_image_offset_s", "max_state_interpolation_gap_s", "training_ready", "success", "outcome_source", "state_units", "action_definition")}
        report["metrics"]["command_count"] = recording["counts"]["commands"]
        report["metrics"]["recording_complete"] = recording["recording_complete"]
        report["metrics"]["check_only"] = recording["check_only"]
        report["metrics"]["controller_entry_called"] = recording["controller_entry_called"]
        if recording["counts"]["commands"] == 0:
            finding("RECORDING_WITHOUT_COMMANDS", "info", "The recording contains zero commands. Stationary feedback in this case is not treated as an actuator fault.")
        if summary["quality_flagged_rows"] == 0:
            finding("REPORTED_ALIGNMENT_CHECKS_PASSED", "info", "The source conversion report flags zero aligned rows. This inspector summarizes that report; it does not rerun conversion or decode video.")
        else:
            finding("REPORTED_ALIGNMENT_FLAGS", "review", "The source conversion report contains flagged alignment rows; inspect their original details.")
        if not summary["training_ready"]:
            finding("NOT_TRAINING_READY", "info", "The source explicitly marks training_ready=false. Zero quality flags and recording_complete=true do not override that status.")
        if summary["success"] is None:
            finding("TASK_OUTCOME_UNKNOWN", "info", "The source task outcome is unlabelled/unknown; no successful robot task is inferred.")
        else:
            finding("SOURCE_TASK_OUTCOME_RECORDED", "info", f"The source records success={str(summary['success']).lower()} with outcome_source={summary['outcome_source']}. This inspector preserves that label without independently verifying it.")
        if summary["rows"] != summary["video_frames"]:
            finding("ROW_VIDEO_COUNT_MISMATCH", "review", "The reported row and video-frame counts differ.")
        if summary["max_image_offset_s"] > summary["alignment_policy"]["max_image_offset_s"] or summary["max_state_interpolation_gap_s"] > summary["alignment_policy"]["max_state_interpolation_gap_s"]:
            finding("REPORTED_THRESHOLD_EXCEEDED", "review", "A reported maximum exceeds the declared alignment policy; recheck source records.")
    report["review_required"] = any(item["level"] == "review" for item in report["findings"])
    return report


def _svg(case):
    rows = case.get("samples", [])
    if not rows:
        return "<p>No action trace is bundled for this report-summary case.</p>"
    times = [r["elapsed_seconds"] for r in rows]
    goals = [r["goal_raw"]["gripper"] for r in rows]
    actual = [r["actual_raw"]["gripper"] for r in rows]
    low, high = min(goals + actual) - 1, max(goals + actual) + 1
    def points(values):
        return " ".join(f"{65 + 690 * (t-times[0])/(times[-1]-times[0]):.2f},{240 - 190 * (v-low)/(high-low):.2f}" for t, v in zip(times, values))
    return (f'<svg viewBox="0 0 820 305" role="img" aria-label="Gripper goal and measured feedback in native servo counts">'
        '<rect width="820" height="305" fill="#fff"/><path d="M65 35V240H755" fill="none" stroke="#64748b"/>'
        f'<polyline points="{points(goals)}" fill="none" stroke="#2563eb" stroke-width="3"/>'
        f'<polyline points="{points(actual)}" fill="none" stroke="#dc2626" stroke-width="3"/>'
        '<text x="65" y="25" font-size="15">Gripper position: native servo counts</text>'
        f'<text x="8" y="50">{high}</text><text x="8" y="242">{low}</text>'
        f'<text x="65" y="263">{times[0]:.3f} s</text><text x="690" y="263">{times[-1]:.3f} s</text>'
        '<text x="65" y="291" fill="#2563eb">Blue: goal</text><text x="230" y="291" fill="#dc2626">Red: feedback</text>'
        '<text x="430" y="291">Elapsed time, not exposure timestamps</text></svg>')


def render_html(case, report):
    esc = lambda value: html.escape(str(value), quote=True)
    findings = "".join(f'<li class="{esc(item["level"])}"><strong>{esc(item["code"])}</strong><p>{esc(item["message"])}</p></li>' for item in report["findings"])
    sources = "".join(f'<tr><td>{esc(src["role"])}</td><td>{esc(src["file_name"])}</td><td><code>{esc(src["sha256"])}</code></td></tr>' for src in case["sources"])
    return ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f'<title>{esc(case["case_id"])} — Robot Feedback Inspector</title>'
        '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1000px;margin:32px auto;padding:0 20px;color:#172033;background:#f8fafc}h1{line-height:1.2}section{background:white;padding:20px;margin:20px 0;border:1px solid #dbe3ee;border-radius:10px}li{margin:14px 0}.review{border-left:4px solid #d97706;padding-left:12px}.info{border-left:4px solid #2563eb;padding-left:12px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #dbe3ee;padding:8px;text-align:left;overflow-wrap:anywhere}code,pre{font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}svg{width:100%;height:auto}.note{color:#475569}</style>'
        '<h1>Robot Feedback Inspector</h1><p>Local release candidate · saved data only</p>'
        f'<p><strong>{esc(case["case_id"])}</strong> · {esc(case["data_kind"])} · review required: {esc(str(report["review_required"]).lower())}</p>'
        '<p class="note">Native position counts are not torque, angle, millimetres, or gripping force. This page does not certify hardware safety, successful grasping, or a complete task.</p>'
        f'<section><h2>Observed evidence</h2>{_svg(case)}<pre>{esc(json.dumps(report["metrics"], ensure_ascii=False, indent=2, allow_nan=False))}</pre></section>'
        f'<section><h2>Inspection findings</h2><ul>{findings}</ul></section>'
        f'<section><h2>Original source checksums</h2><p>The checksum identifies the original file used for extraction. It is not a digital signature or independent authentication.</p><table><thead><tr><th>Role</th><th>Source file</th><th>SHA-256</th></tr></thead><tbody>{sources}</tbody></table></section>'
        f'<section><h2>Field mapping</h2><pre>{esc(json.dumps(case["source_field_map"], ensure_ascii=False, indent=2))}</pre></section>'
        '<p class="note">Real samples are limited case studies. Synthetic tests are separate. No new robot experiment, model training, or algorithm-performance claim is made.</p></html>')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="Saved sample JSON")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        case = load_case(args.case)
        report = analyze_case(case)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = args.output_dir / (case["case_id"] + ".report.json")
        html_path = args.output_dir / (case["case_id"] + ".report.html")
        if json_path.exists() or html_path.exists():
            raise ValidationError("report files already exist; choose a fresh output directory")
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        html_path.write_text(render_html(case, report), encoding="utf-8")
    except (ValidationError, OSError) as exc:
        print("Inspection failed: " + str(exc), file=sys.stderr)
        return 2
    print(f"{case['case_id']}: {len(report['findings'])} findings; review_required={report['review_required']}")
    print("Wrote " + json_path.name + " and " + html_path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
