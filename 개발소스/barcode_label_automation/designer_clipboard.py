"""Validated object clipboard data and geometry preserving copies."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from uuid import uuid4

PREFIX = 'CHAEUMLAB_LABEL_OBJECTS_V1\n'
TYPES = {'text', 'field', 'multiline_text', 'barcode', 'qr', 'image', 'box', 'line', 'table'}


def encode_objects(elements: list[dict[str, object]], base_dir: Path) -> str:
    snapshots = copy.deepcopy(elements)
    for element in snapshots:
        for key in ('image_path', 'review_image_path'):
            if element.get(key):
                path = Path(str(element[key]))
                element[key] = str((path if path.is_absolute() else base_dir / path).resolve())
    return PREFIX + json.dumps(snapshots, ensure_ascii=False, allow_nan=False)


def decode_objects(value: str) -> list[dict[str, object]]:
    if not value.startswith(PREFIX):
        raise ValueError('복사한 채움랩 개체가 없습니다. 개체를 선택하고 Ctrl+C를 누르세요.')
    if len(value) > 8_000_000:
        raise ValueError('복사한 개체 정보가 너무 큽니다. 개체를 나누어 복사하세요.')
    try:
        def reject_constant(value: str):
            raise ValueError(f'Invalid numeric constant: {value}')
        elements = json.loads(value[len(PREFIX):], parse_constant=reject_constant)
        if not isinstance(elements, list) or not elements:
            raise ValueError
        for element in elements:
            if not isinstance(element, dict) or element.get('type') not in TYPES:
                raise ValueError
            for key in ('x', 'y', 'width', 'height'):
                number = element[key]
                if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                    raise ValueError
                if key in ('width', 'height') and number <= 0:
                    raise ValueError
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise ValueError('복사한 개체 정보가 올바르지 않습니다. 원본에서 다시 복사하세요.') from exc
    return elements


def clone_objects(elements: list[dict[str, object]], width: float, height: float,
                  offset: float = 2) -> list[dict[str, object]]:
    if not elements:
        return []
    left = min(float(e['x']) for e in elements)
    top = min(float(e['y']) for e in elements)
    right = max(float(e['x']) + float(e['width']) for e in elements)
    bottom = max(float(e['y']) + float(e['height']) for e in elements)
    if right - left > width + .001 or bottom - top > height + .001:
        raise ValueError('복사한 개체가 현재 라벨보다 큽니다. 용지 규격을 확인하세요.')
    dx = max(-left, min(offset, width - right))
    dy = max(-top, min(offset, height - bottom))
    groups: dict[str, str] = {}
    copies = copy.deepcopy(elements)
    for element in copies:
        element['id'] = uuid4().hex
        element['locked'] = False
        element['x'] = round(float(element['x']) + dx, 4)
        element['y'] = round(float(element['y']) + dy, 4)
        group = str(element.get('group_id', ''))
        if group:
            element['group_id'] = groups.setdefault(group, uuid4().hex)
    return copies
