# Visual sample-library update planning

`object_library.py` is the standard-library core extracted from the robot project's incremental visual sample library. It validates labels and image boxes and plans stable class IDs when appending a class or replacing selected reference rows. It does not extract visual embeddings, load a detector, recognise an object or access hardware.

The core is unchanged from the source version identified by SHA-256:

```text
612491888b9d11f691c1078e98c51e2e8c06a7e58f19fc445e1f5a8b72be4d9a
```

From the repository root:

```sh
python examples/object_library_demo.py
python -m unittest discover -s tests -p test_object_library.py -v
```

The demo uses **synthetic** labels and pixel boxes. It prints JSON showing an append, a same-name selected replacement with stable IDs, and rejection of an out-of-image box. No experiment images, annotations, feature files or model weights are included.

The unittest adapter preserves the original nine offline check groups in one test case, including input immutability, Unicode label handling, class capacity and invalid geometry rejection. The original timestamped report writer has been removed; tests do not create reports containing local source paths.

API:

- `normalize_label(value)`: normalise display labels and reject control/hidden characters.
- `validate_batch(samples, width, height, ...)`: validate synthetic or caller-supplied label/box inputs; boxes are `[x1, y1, x2, y2]` in pixels, inside the image and at least 8 by 8 pixels.
- `plan_update(existing_labels, new_labels, mode, ...)`: return row sources and stable class IDs for `append`, `replace_selected` or `replace_all`. Callers remain responsible for copying the corresponding feature rows.

The default capacity of 32 classes is an application safeguard, not a detector capacity claim. Passing these checks does not establish live recognition accuracy or robot grasp performance. This is an engineering component around an existing vision workflow, not a new detection algorithm.
