"""Shared paper dimensions; preserve the other customer settings."""
from __future__ import annotations

import os
import tempfile
from configparser import ConfigParser
from pathlib import Path

from .config import load_config
from .errors import ConfigError


def read_label_size(path: Path) -> tuple[int, int]:
    try:
        config = load_config(path)
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc
    width, height = config.label.width_mm, config.label.height_mm
    if not (0 < width <= 300 and 0 < height <= 300):
        raise ValueError('라벨 가로·세로는 1부터 300mm 사이여야 합니다.')
    return width, height


def write_config_atomic(path: Path, parser: ConfigParser) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', dir=path.parent,
                                         prefix='.label-settings-', suffix='.tmp', delete=False) as file:
            name = file.name
            parser.write(file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def save_label_size(path: Path, width: object, height: object) -> None:
    values = []
    for value in (width, height):
        if isinstance(value, bool):
            raise ValueError('용지 규격은 숫자로 입력하세요.')
        number = float(value)
        if not number.is_integer() or not 0 < number <= 300:
            raise ValueError('공통 용지 규격은 1부터 300mm 사이 정수로 입력하세요.')
        values.append(int(number))
    parser = ConfigParser()
    if not path.is_file():
        raise FileNotFoundError('프린터 설정 파일이 없습니다. 프린터 설정에서 먼저 저장하세요.')
    parser.read(path, encoding='utf-8-sig')
    if not parser.has_section('label'):
        parser.add_section('label')
    parser.set('label', 'width_mm', str(values[0]))
    parser.set('label', 'height_mm', str(values[1]))
    write_config_atomic(path, parser)


def outside_elements(elements: list[dict[str, object]], width: float, height: float) -> list[dict[str, object]]:
    return [e for e in elements if float(e.get('x', 0)) < -.01 or float(e.get('y', 0)) < -.01
            or float(e.get('x', 0)) + float(e.get('width', 1)) > width + .01
            or float(e.get('y', 0)) + float(e.get('height', 1)) > height + .01]
