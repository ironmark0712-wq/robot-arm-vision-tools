"""Pure-standard-library validation and stable class-row update planning.

No files, cameras, robot motors, models or arrays are opened by this module.
The default limit of 32 classes is an application/UI safeguard, not a YOLO
model limit. Callers may explicitly supply another ``max_count``.
"""
from __future__ import annotations

import math
import unicodedata

DEFAULT_MAX_COUNT = 32
_FORBIDDEN_NAME_CATEGORIES = frozenset(('Cc', 'Cf', 'Cs', 'Zl', 'Zp'))


def normalize_label(value):
    """Return a display label; reject controls before stripping whitespace.

    Comparison keys are ``normalize_label(value).casefold()``. NFKC makes,
    for example, full-width Latin names match their ordinary Latin spelling.
    No fuzzy matching is performed: replacing a misspelled name is refused.
    """
    if not isinstance(value, str):
        raise ValueError('物品名称必须是文字')
    if any(unicodedata.category(char) in _FORBIDDEN_NAME_CATEGORIES for char in value):
        raise ValueError('名称不可包含控制字符、隐藏格式字符或换行')
    label = unicodedata.normalize('NFKC', value).strip()
    if (not 1 <= len(label) <= 40 or
            any(unicodedata.category(char) in _FORBIDDEN_NAME_CATEGORIES for char in label)):
        raise ValueError('每种物品名称规范化后需为1～40字，且不可含控制字符')
    return label


def _capacity(value, name='max_count'):
    if type(value) is not int or value < 1:
        raise ValueError(f'{name}必须是正整数')
    return value


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        # Arbitrary-size Python integers may not fit the float/image backend.
        return False


def _labels(values, *, allow_empty):
    if not isinstance(values, list) or (not allow_empty and not values):
        raise ValueError('名称必须组成列表，待提交列表不能为空')
    normalized, seen = [], set()
    for value in values:
        label = normalize_label(value)
        key = label.casefold()
        if key in seen:
            raise ValueError(f'名称重复（不区分大小写及全半角）：{label}')
        seen.add(key)
        normalized.append(label)
    return normalized


def validate_batch(samples, width, height, min_count=1, max_count=DEFAULT_MAX_COUNT):
    """Validate one image's samples and return fresh sequential class rows.

    ``box`` is [x1, y1, x2, y2] in pixels, entirely inside this image and at
    least 8 by 8 pixels. Booleans, NaN and infinity are not coordinates.
    Existing input dictionaries/lists are never modified or returned by
    reference. IDs here are incoming-batch IDs; ``plan_update`` chooses final
    stable IDs when this batch is appended to or replaces library rows.
    """
    minimum = _capacity(min_count, 'min_count')
    maximum = _capacity(max_count)
    if minimum > maximum:
        raise ValueError('min_count不能大于max_count')
    if any(not _finite_number(v) or v <= 0
           for v in (width, height)):
        raise ValueError('画面宽高必须是有限的正数，不能是布尔值')
    if not isinstance(samples, list) or not minimum <= len(samples) <= maximum:
        raise ValueError(f'本次请登记{minimum}～{maximum}类；这是页面容量保护，不是YOLO类别极限')
    if any(not isinstance(sample, dict) for sample in samples):
        raise ValueError('样例格式无效')
    labels = _labels([sample.get('label') for sample in samples], allow_empty=False)
    result = []
    for class_id, (sample, label) in enumerate(zip(samples, labels)):
        box = sample.get('box')
        if (not isinstance(box, list) or len(box) != 4 or
                any(not _finite_number(v) for v in box)):
            raise ValueError('框选坐标必须是四个有限数字，不能是布尔值')
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height and
                x2 - x1 >= 8 and y2 - y1 >= 8):
            raise ValueError('框需在画面内，且至少8×8像素；太小的零件先不用')
        result.append(dict(class_id=class_id, code=f'C{class_id + 1}', label=label,
                           box=[float(v) for v in box]))
    return result


def plan_update(existing_labels, new_labels, mode, max_count=DEFAULT_MAX_COUNT):
    """Plan class identities and feature-row sources without touching models.

    Returns ``{'mode', 'merged_labels', 'rows'}``. Every output row contains
    its final zero-based ``class_id``, C1-based ``code``, display ``label``,
    ``source`` (``existing``/``incoming``), and zero-based ``index`` into that
    source's original label/feature rows. Callers must copy the matching
    feature rows themselves; this function assumes no NPZ/array format.

    * append: preserve every old row and add genuinely new names at the end.
    * replace_selected: each incoming name must match an existing name;
      matched rows retain old IDs, unselected rows are kept unchanged.
    * replace_all: start C1 again using the incoming order.

    Names are matched by NFKC + strip + casefold. Existing display names
    (after normalization) are retained for a selected replacement.
    """
    maximum = _capacity(max_count)
    if not isinstance(mode, str) or mode not in ('append', 'replace_selected', 'replace_all'):
        raise ValueError('更新模式必须是append、replace_selected或replace_all')
    existing = _labels(existing_labels, allow_empty=True)
    incoming = _labels(new_labels, allow_empty=False)
    old_by_key = {label.casefold(): i for i, label in enumerate(existing)}
    new_by_key = {label.casefold(): i for i, label in enumerate(incoming)}
    if mode == 'append':
        duplicates = [label for label in incoming if label.casefold() in old_by_key]
        if duplicates:
            raise ValueError('新增名称已存在，请选择替换同名样例：' + '、'.join(duplicates))
        selected = [(label, 'existing', i) for i, label in enumerate(existing)]
        selected.extend((label, 'incoming', i) for i, label in enumerate(incoming))
    elif mode == 'replace_selected':
        unknown = [label for label in incoming if label.casefold() not in old_by_key]
        if unknown:
            raise ValueError('待替换名称不在旧库中；请检查拼写，不自动猜测：' + '、'.join(unknown))
        selected = []
        for i, label in enumerate(existing):
            incoming_index = new_by_key.get(label.casefold())
            if incoming_index is None:
                selected.append((label, 'existing', i))
            else:
                selected.append((label, 'incoming', incoming_index))
    else:
        selected = [(label, 'incoming', i) for i, label in enumerate(incoming)]
    if len(selected) > maximum:
        raise ValueError(f'更新后共{len(selected)}类，超过本页面配置上限{maximum}类；不是YOLO类别极限')
    rows = [dict(class_id=i, code=f'C{i + 1}', label=label, source=source, index=index)
            for i, (label, source, index) in enumerate(selected)]
    return dict(mode=mode, merged_labels=[row['label'] for row in rows], rows=rows)
