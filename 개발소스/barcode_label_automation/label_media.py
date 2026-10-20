"""Shared paper dimensions; preserve the other customer settings."""
from __future__ import annotations

import math
import os
import tempfile
from configparser import ConfigParser
from pathlib import Path

from .config import load_config
from .errors import ConfigError


def read_label_size(path: Path) -> tuple[float, float]:
    try:
        config = load_config(path)
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc
    width, height = config.label.width_mm, config.label.height_mm
    if not (0 < width <= 300 and 0 < height <= 300):
        raise ValueError('라벨 가로·세로는 0보다 크고 300mm 이하여야 합니다.')
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
        if not math.isfinite(number) or not 0 < number <= 300:
            raise ValueError('공통 용지 규격은 0보다 크고 300mm 이하인 숫자로 입력하세요.')
        values.append(number)
    parser = ConfigParser()
    if not path.is_file():
        raise FileNotFoundError('프린터 설정 파일이 없습니다. 프린터 설정에서 먼저 저장하세요.')
    parser.read(path, encoding='utf-8-sig')
    dpi = parser.getint('label', 'dpi', fallback=203)
    if any(round(value / 25.4 * dpi) < 1 for value in values):
        raise ValueError('용지 규격은 현재 DPI에서 최소 1도트여야 합니다.')
    if not parser.has_section('label'):
        parser.add_section('label')
    parser.set('label', 'width_mm', str(values[0]))
    parser.set('label', 'height_mm', str(values[1]))
    _check_gap_offset_for_height(parser, values[1])
    write_config_atomic(path, parser)


def outside_elements(elements: list[dict[str, object]], width: float, height: float) -> list[dict[str, object]]:
    return [e for e in elements if float(e.get('x', 0)) < -.01 or float(e.get('y', 0)) < -.01
            or float(e.get('x', 0)) + float(e.get('width', 1)) > width + .01
            or float(e.get('y', 0)) + float(e.get('height', 1)) > height + .01]


def read_document_media(path: Path) -> dict:
    """Document dimensions are the logical canvas; stock dimensions stay physical."""
    from .media_geometry import logical_size
    config = load_config(path)
    width, height = logical_size(config.label.width_mm, config.label.height_mm,
                                 config.printer.print_orientation)
    return {"width_mm": width, "height_mm": height,
            "print_orientation": config.printer.print_orientation}


def save_document_media(path: Path, label: dict) -> None:
    from .media_geometry import logical_size
    orientation = str(label.get("print_orientation", "normal"))
    width, height = logical_size(label["width_mm"], label["height_mm"], orientation)
    if not path.is_file():
        raise FileNotFoundError("프린터 설정 파일이 없습니다. 먼저 프린터 설정을 저장하세요.")
    parser = ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8-sig")
    dpi = parser.getint("label", "dpi", fallback=203)
    for value in (width, height):
        if isinstance(value, bool) or not math.isfinite(float(value)) or not 0 < float(value) <= 300:
            raise ValueError("용지 규격은 0보다 크고 300mm 이하인 숫자여야 합니다.")
        if round(float(value) / 25.4 * dpi) < 1:
            raise ValueError("용지 규격은 현재 DPI에서 최소 1도트여야 합니다.")
    parser.set("label", "width_mm", str(width))
    parser.set("label", "height_mm", str(height))
    parser.set("printer", "print_orientation", orientation)
    _check_gap_offset_for_height(parser, float(height))
    write_config_atomic(path, parser)


def _check_gap_offset_for_height(parser: ConfigParser, height: float) -> None:
    from .printer_offsets import validate_offsets
    raw = parser.get("label", "gap_offset_mm", fallback="0").strip().lower()
    if raw == "auto":
        return
    offset = float(raw)
    brand = parser.get("printer", "brand", fallback="bixolon")
    language = {"bixolon": "slcs", "tsc": "tspl", "zebra": "zpl", "sewoo": "zpl"}.get(brand)
    validate_offsets(language, parser.get("label", "media_type", fallback="gap"), height,
                     parser.getint("label", "dpi", fallback=203), offset, None, brand=brand)
