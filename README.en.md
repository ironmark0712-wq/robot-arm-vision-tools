# Robot Arm Vision Tools

[中文](README.md)

Offline tools extracted from an SO101 robot-arm practice project: stable visual-class updates, pixel-to-known-plane geometry, and saved feedback/data-quality inspection.

Author: Guancheng Liu, a mechanical-engineering undergraduate at Shaanxi University of Science and Technology. This independent robotics practice receives guidance and equipment support from Prof. Xiang Li, School of Mechanical Engineering, Xi'an Jiaotong University. The supervisor has approved sharing the current work and acknowledging his guidance. [Official faculty page](https://faculty.xjtu.edu.cn/lixiang/zh_CN/index.htm)

## Run

Python 3.10+; the class-library and feedback tools use only the standard library:

```bash
python examples/object_library_demo.py
python -m robot_tools.feedback_inspector samples/empty_grasp_13.json --output-dir artifacts/empty
python -m robot_tools.feedback_inspector samples/static_conversion_summary.json --output-dir artifacts/static
```

For the synthetic geometry demo, use an isolated Python 3.12+ environment and install the tested dependencies (the pinned NumPy requires Python 3.12+):

```bash
python -m pip install -r requirements-geometry.txt
python examples/geometry_demo.py
python -m unittest discover -s tests -v
```

Tests explicitly skip geometry when its dependencies are absent. A skip is not a pass. See [validation](VALIDATION.md) and the Chinese README for full field definitions and commands.

## Evidence and scope

- Class management: validates labels and boxes, appends/replaces classes while keeping existing IDs stable. Demo inputs are synthetic.
- Geometry: intersects an undistorted pixel ray with a plane at a **given height**, then applies a known rigid transform. Synthetic round trips do not measure physical accuracy or recover unknown depth.
- Feedback: thirteen real saved records show changing gripper goals and unchanged measured position before a lift-labelled stage. Raw counts are not force or torque; the log does not establish a hardware root cause.
- A real stationary conversion summary has zero commands, 27 rows/frames, no reported alignment flags, an unknown outcome, and `training_ready=false`. Reading the summary does not rerun conversion, decode video, or validate a completed task.

The repository has no hardware-control entry point, model weights, private calibration, complete training dataset, or claim of verified end-to-end grasp/place performance. Time stamps are host/program times rather than hardware synchronization.

## Contributions and license

The author advances the local project, operates the bench, observes problems, defines checking requirements, and performs follow-up observations. Engineering code and analysis are AI-assisted. Existing frameworks and general methods are acknowledged rather than presented as original algorithms.

Included project code and examples use the [MIT license](LICENSE). External dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). The full SO-ARM100, LeRobot, YOLOE, simulator assets, and weights are not bundled here.
