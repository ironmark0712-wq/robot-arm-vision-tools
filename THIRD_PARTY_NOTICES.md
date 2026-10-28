# Sources and third-party notices

Project-specific Python tools, adapted checks, documentation and included sample excerpts are distributed under the root MIT license. This does not relicense external frameworks, models, assets, or packages.

## Wider robotics practice

- SO-ARM100 / SO101: https://github.com/TheRobotStudio/SO-ARM100 — robot design and upstream simulation resources used in the wider bench project. The upstream repository has an Apache-2.0 license. No model, STL, CAD, or simulator asset is copied into this release.
- LeRobot: https://github.com/huggingface/lerobot and the Seeed integration https://github.com/Seeed-Projects/lerobot — used in the wider collection/replay workflow. This release includes a selected conversion **summary**, not LeRobot source or a dataset export.
- Ultralytics / YOLOE: https://github.com/ultralytics/ultralytics — used by the wider vision application. This release's label/box management module does not import or bundle Ultralytics, features, checkpoints or weights.
- NumPy and OpenCV are optional geometry dependencies installed separately. Their own distributions and licenses remain applicable.

## Included samples

The two JSON sample files contain selected numeric feedback records or selected report fields from the author's SO101 bench practice. Supervisor approval to share the current work was relayed on 2026-10-28. File names, original SHA-256 identifiers, selection rules and field mappings are retained; workstation paths, full media and private calibration are omitted.

Synthetic examples and synthetic variants in tests are explicitly marked. They are not additional physical experiments. Raw source files are retained by the project holder; their checksums alone do not independently authenticate a physical result.
