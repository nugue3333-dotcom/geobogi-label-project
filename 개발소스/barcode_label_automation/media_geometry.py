"""Physical-paper geometry shared by previews and printer raster output."""
from __future__ import annotations

import math
from PIL import Image, ImageChops

ORIENTATIONS = {"normal": 0, "landscape": 90, "rotate_180": 180, "landscape_180": 270}


def logical_size(width, height, orientation="normal"):
    if orientation not in ORIENTATIONS:
        raise ValueError("지원하지 않는 인쇄 방향입니다.")
    return (height, width) if ORIENTATIONS[orientation] in {90, 270} else (width, height)


def needs_host_transform(config):
    return (config.printer.print_orientation in {"landscape", "landscape_180"}
            or bool(getattr(config.label, "offset_x_mm", 0))
            or bool(getattr(config.label, "offset_y_mm", 0)))


def transform_page(image, physical_size, orientation="normal", offset_x=0, offset_y=0):
    """Rotate without interpolation, then translate in final paper coordinates.

    Reject lost ink instead of silently clipping a shifted barcode or its text.
    White margins may extend outside the paper.
    """
    expected = logical_size(*physical_size, orientation)
    if image.size != expected:
        raise ValueError(f"도안 크기 {image.size}와 인쇄 영역 {expected}가 다릅니다.")
    if not all(math.isfinite(float(v)) for v in (offset_x, offset_y)):
        raise ValueError("인쇄 위치 보정은 유한한 숫자여야 합니다.")
    rotation = ORIENTATIONS[orientation]
    dx, dy = round(offset_x), round(offset_y)
    # Barcode quiet zones are white but must not disappear beyond the stock.
    # Raster producers attach the complete symbol bounds before transformation.
    for x, y, w, h in image.info.get("protected_bounds", ()):
        if rotation == 90:
            x, y, w, h = y, image.width - x - w, h, w
        elif rotation == 180:
            x, y = image.width - x - w, image.height - y - h
        elif rotation == 270:
            x, y, w, h = image.height - y - h, x, h, w
        if x + dx < 0 or y + dy < 0 or x + w + dx > physical_size[0] or y + h + dy > physical_size[1]:
            raise ValueError("보정 후 바코드의 필수 여백이 라벨 영역을 넘습니다. 위치 또는 보정값을 조정하세요.")
    page = image.convert("RGB")
    if rotation:
        page = page.transpose({90: Image.Transpose.ROTATE_90,
                               180: Image.Transpose.ROTATE_180,
                               270: Image.Transpose.ROTATE_270}[rotation])
    ink = ImageChops.difference(page, Image.new("RGB", page.size, "white")).getbbox()
    if ink and (ink[0] + dx < 0 or ink[1] + dy < 0
                or ink[2] + dx > page.width or ink[3] + dy > page.height):
        raise ValueError("인쇄 위치 보정으로 내용이 라벨 영역을 넘습니다. 보정값 또는 도안 여백을 조정하세요.")
    result = Image.new("RGB", physical_size, "white")
    result.paste(page, (dx, dy))
    return result


def transform_image(image, config):
    from .templates import mm_to_dots
    label = config.label
    return transform_page(image,
                          (mm_to_dots(label.width_mm, label.dpi), mm_to_dots(label.height_mm, label.dpi)),
                          config.printer.print_orientation,
                          mm_to_dots(getattr(label, "offset_x_mm", 0), label.dpi),
                          mm_to_dots(getattr(label, "offset_y_mm", 0), label.dpi))
