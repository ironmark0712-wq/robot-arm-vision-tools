"""Existing nine offline check groups, adapted to unittest.

All labels, boxes and update inputs are synthetic. No device, model, image,
feature library or original experiment report is opened or created.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import sys
import unittest

# Supports direct execution as well as unittest discovery from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from robot_tools import object_library as library

def rejects(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except ValueError:
        return
    raise AssertionError(f'Expected ValueError: {function.__name__} {args!r}')


def check_all(checks):
    old = ['面包板', 'SG90舵机', '逻辑分析仪']
    old_copy = deepcopy(old)
    new = ['六角螺母']
    new_copy = deepcopy(new)
    planned = library.plan_update(old, new, 'append')
    assert planned['merged_labels'] == old + new
    assert [(row['source'], row['index']) for row in planned['rows']] == [
        ('existing', 0), ('existing', 1), ('existing', 2), ('incoming', 0)]
    assert [row['code'] for row in planned['rows']] == ['C1', 'C2', 'C3', 'C4']
    assert old == old_copy and new == new_copy
    checks.append('THREE_PLUS_ONE_APPEND_PRESERVES_OLD_IDS_AND_INPUTS')

    replaced = library.plan_update(old, ['逻辑分析仪', 'ｓｇ９０舵机'], 'replace_selected')
    assert replaced['merged_labels'] == old
    assert [(row['source'], row['index']) for row in replaced['rows']] == [
        ('existing', 0), ('incoming', 1), ('incoming', 0)]
    rejects(library.plan_update, old, ['逻辑分析其'], 'replace_selected')
    rejects(library.plan_update, old, ['sg90舵机'], 'append')
    rejects(library.plan_update, old, [' SG90舵机 ', 'ｓｇ９０舵机'], 'replace_selected')
    checks.append('SAME_NAME_REPLACEMENT_KEEPS_IDS_AND_UNSELECTED_CLASSES_REJECTS_TYPOS')

    reset = library.plan_update(old, ['垫片', '齿轮'], 'replace_all')
    assert reset['merged_labels'] == ['垫片', '齿轮']
    assert reset['rows'] == [dict(class_id=0, code='C1', label='垫片', source='incoming', index=0),
                             dict(class_id=1, code='C2', label='齿轮', source='incoming', index=1)]
    assert library.plan_update([], ['首类'], 'append')['rows'][0]['class_id'] == 0
    rejects(library.plan_update, [], ['首类'], 'replace_selected')
    rejects(library.plan_update, old, [], 'replace_all')
    rejects(library.plan_update, old, ['首类'], 'delete')
    rejects(library.plan_update, '非列表', ['首类'], 'append')
    rejects(library.plan_update, old, ['首类'], [])
    checks.append('REPLACE_ALL_RESTARTS_C1_AND_INVALID_MODES_OR_EMPTY_UPDATES_REFUSED')

    names = [f'零件{i + 1}' for i in range(32)]
    complete = library.plan_update(names[:3], names[3:], 'append')
    assert len(complete['rows']) == 32 and complete['rows'][-1]['code'] == 'C32'
    rejects(library.plan_update, names, ['第33类'], 'append')
    rejects(library.plan_update, [], names + ['第33类'], 'replace_all')
    expanded = library.plan_update(names, ['第33类'], 'append', max_count=33)
    assert expanded['rows'][-1]['code'] == 'C33'
    assert library.plan_update(names, ['只保留一个'], 'replace_all', max_count=1)['merged_labels'] == ['只保留一个']
    for bad_count in (True, False, 0, -1, 3.5, '32'):
        rejects(library.plan_update, old, ['新增'], 'append', max_count=bad_count)
    checks.append('32_CLASS_CAPACITY_DEFAULT_AND_EXPLICIT_HIGHER_UI_CAPACITY_NO_MODEL_CLAIMS')

    assert library.normalize_label('  ＳＧ９０舵机  ') == 'SG90舵机'
    for bad in ('', '  ', 'x' * 41, 'SG\n90', '\tSG90', 'SG90\r', 'A\x7fB',
                'A\x85B', 'A\u200bB', 'A\u202eB', 'A\u2028B', 'A\u2029B', 'A\ud800B', None, 17):
        rejects(library.normalize_label, bad)
    rejects(library.plan_update, ['Straße', 'STRASSE'], ['新增'], 'append')
    rejects(library.plan_update, old, ['Ａ', 'A'], 'replace_all')
    checks.append('NFKC_STRIP_CASEFOLD_DUPLICATES_AND_UNICODE_CONTROLS_REFUSED')

    samples = [dict(label=label, box=[10, 20, 120, 140]) for label in names]
    originals = deepcopy(samples)
    normalized = library.validate_batch(samples, 640, 480)
    assert len(normalized) == 32 and normalized[-1]['class_id'] == 31
    assert normalized[-1]['code'] == 'C32'
    assert samples == originals and normalized[0] is not samples[0]
    assert normalized[0]['box'] is not samples[0]['box']
    normalized[0]['box'][0] = 55
    assert samples == originals
    assert len(library.validate_batch(samples[:1], 640, 480)) == 1
    assert library.validate_batch([dict(label='Ａ', box=[0, 0, 8, 8])], 8, 8)[0]['label'] == 'A'
    assert len(library.validate_batch(samples + [dict(label='额外', box=[0, 0, 8, 8])], 640, 480, max_count=33)) == 33
    rejects(library.validate_batch, samples + [dict(label='额外', box=[0, 0, 8, 8])], 640, 480)
    rejects(library.validate_batch, samples[:1], 640, 480, min_count=2)
    rejects(library.validate_batch, [], 640, 480)
    rejects(library.validate_batch, {}, 640, 480)
    rejects(library.validate_batch, [None], 640, 480)
    rejects(library.validate_batch, samples[:1], 640, 480, min_count=3, max_count=2)
    rejects(library.validate_batch, samples[:1], 640, 480, min_count=True)
    checks.append('BATCH_ACCEPTS_ONE_TO_32_MIN_8PX_FRESH_ROWS_AND_INPUTS_UNCHANGED')

    invalid_boxes = [None, [], [0, 0, 20], (0, 0, 20, 20),
                     [-1, 0, 20, 20], [0, 0, 641, 20], [0, 0, 20, 481],
                     [0, 0, 7, 20], [0, 0, 20, 7.9], [20, 0, 0, 20],
                     [0, 0, float('nan'), 20], [0, 0, float('inf'), 20],
                     [False, 0, 20, 20], [0, True, 20, 20], [0, 0, '20', 20],
                     [0, 0, 10 ** 400, 20]]
    for box in invalid_boxes:
        rejects(library.validate_batch, [dict(label='零件', box=box)], 640, 480)
    for width, height in ((True, 480), (640, False), (0, 480), (640, -1),
                          (float('inf'), 480), (640, float('nan')), ('640', 480),
                          (10 ** 400, 480)):
        rejects(library.validate_batch, samples[:1], width, height)
    rejects(library.validate_batch, [dict(label='Ａ', box=[0, 0, 20, 20]),
                                     dict(label='a', box=[30, 30, 50, 50])], 640, 480)
    checks.append('BOX_BOUNDS_NONFINITE_BOOLEAN_TYPES_AND_BAD_IMAGE_DIMENSIONS_REJECTED')

    # Failed calls must not partially change caller-owned lists either.
    bad_batch = deepcopy(samples[:2])
    bad_batch[1]['box'] = [0, 0, 1, 1]
    before = deepcopy(bad_batch)
    rejects(library.validate_batch, bad_batch, 640, 480)
    assert bad_batch == before and old == old_copy and new == new_copy
    planned['merged_labels'][0] = '输出更改'
    planned['rows'][0]['label'] = '输出更改'
    assert old == old_copy
    checks.append('SUCCESS_FAILURE_AND_OUTPUT_EDITS_CANNOT_MUTATE_CALLER_INPUTS')

    source = Path(library.__file__).read_text(encoding='utf-8')
    modules = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append((node.module or '').split('.')[0])
    assert all(module in sys.stdlib_module_names for module in modules), modules
    assert not any(term in modules for term in ('cv2', 'numpy', 'torch', 'scservo_sdk', 'serial', 'mujoco'))
    checks.append('LIBRARY_IMPORTS_STDLIB_ONLY_NO_MODEL_CAMERA_ROBOT_OR_FILESYSTEM_IMPORTS')

EXPECTED_CHECK_GROUPS = ['THREE_PLUS_ONE_APPEND_PRESERVES_OLD_IDS_AND_INPUTS', 'SAME_NAME_REPLACEMENT_KEEPS_IDS_AND_UNSELECTED_CLASSES_REJECTS_TYPOS', 'REPLACE_ALL_RESTARTS_C1_AND_INVALID_MODES_OR_EMPTY_UPDATES_REFUSED', '32_CLASS_CAPACITY_DEFAULT_AND_EXPLICIT_HIGHER_UI_CAPACITY_NO_MODEL_CLAIMS', 'NFKC_STRIP_CASEFOLD_DUPLICATES_AND_UNICODE_CONTROLS_REFUSED', 'BATCH_ACCEPTS_ONE_TO_32_MIN_8PX_FRESH_ROWS_AND_INPUTS_UNCHANGED', 'BOX_BOUNDS_NONFINITE_BOOLEAN_TYPES_AND_BAD_IMAGE_DIMENSIONS_REJECTED', 'SUCCESS_FAILURE_AND_OUTPUT_EDITS_CANNOT_MUTATE_CALLER_INPUTS', 'LIBRARY_IMPORTS_STDLIB_ONLY_NO_MODEL_CAMERA_ROBOT_OR_FILESYSTEM_IMPORTS']

class ObjectLibraryTests(unittest.TestCase):
    def test_existing_nine_offline_check_groups(self):
        checks = []
        check_all(checks)
        self.assertEqual(checks, EXPECTED_CHECK_GROUPS)


if __name__ == "__main__":
    unittest.main()
