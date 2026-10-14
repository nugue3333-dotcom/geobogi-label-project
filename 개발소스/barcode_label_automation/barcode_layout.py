"""Print-dot layout in which text can never shrink an encoded matrix symbol.

The caller supplies an unscaled, one-dot encoder image including its quiet
zones. Element width/height describe the complete symbol and HRI group. This
module does not encode data or change legacy templates.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .templates import mm_to_dots

# A product readability policy, not a GS1 minimum size requirement.
MIN_HRI_FONT_PT = 6.0
FontLoader = Callable[[int, str], ImageFont.ImageFont]
Bounds = tuple[int, int, int, int]


@dataclass(frozen=True)
class SymbolGeometry:
    bounds: Bounds
    module_dots: int
    actual_symbol_mm: tuple[float, float]
    hri_position: str
    gap_dots: int


def _number(value: object, label: str, minimum: float = 0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}은 유효한 숫자로 입력하세요.") from exc
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{label}은 {minimum:g} 이상으로 입력하세요.")
    return result


def _floor_mm_dots(mm: float, dpi: int) -> int:
    # Use the project's shared conversion, then enforce a maximum target.
    dots = mm_to_dots(mm, dpi)
    if dots * 25.4 / dpi > mm + 1e-9:
        dots -= 1
    return dots


def symbol_geometry(
    source: Image.Image, element: Mapping[str, object], width: int,
    height: int, dpi: int, *, check_bounds: bool = True,
) -> SymbolGeometry:
    """Compute the immutable symbol geometry without looking at HRI options."""
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0
           for v in (width, height, dpi)):
        raise ValueError("전체 영역과 DPI는 양의 정수 인쇄 도트로 지정하세요.")
    if source.width <= 0 or source.height <= 0:
        raise ValueError("인코딩된 바코드 이미지가 비어 있습니다.")
    if int(source.info.get("module_dots", 1)) != 1:
        raise ValueError("바코드 크기 계산에는 1도트 모듈 원본이 필요합니다.")
    layout = element.get("barcode_layout")
    if not isinstance(layout, Mapping) or layout.get("version") != 2:
        raise ValueError("바코드 크기 우선 배치 버전 2가 필요합니다.")
    mode = layout.get("size_mode", "size")
    position = str(layout.get("hri_position", "right"))
    if position not in {"right", "below"}:
        raise ValueError("표시문자 위치는 오른쪽 또는 아래로 선택하세요.")
    gap = mm_to_dots(_number(layout.get("hri_gap_mm", 1), "문자 간격"), dpi)
    if mode == "module":
        options = element.get("barcode_options", {})
        if not isinstance(options, Mapping):
            raise ValueError("바코드 옵션 형식이 올바르지 않습니다.")
        scale_value = _number(options.get("cell_size", 1), "모듈 도트", 1)
        if not scale_value.is_integer():
            raise ValueError("모듈 도트는 정수로 입력하세요.")
        scale = int(scale_value)
    elif mode == "size":
        target_width = _number(layout.get("symbol_width_mm", 0), "바코드 목표 너비")
        target_height = _number(layout.get("symbol_height_mm", 0), "바코드 목표 높이")
        if target_width == target_height == 0:
            # Default uses the current whole group's smaller dimension;
            # text cannot affect this target, including when it is disabled.
            side = min(width, height)
            scale = min(side // source.width, side // source.height)
        else:
            constraints = []
            if target_width:
                constraints.append(_floor_mm_dots(target_width, dpi) // source.width)
            if target_height:
                constraints.append(_floor_mm_dots(target_height, dpi) // source.height)
            scale = min(constraints)
    else:
        raise ValueError("바코드 크기 방식은 mm 크기 또는 모듈 도트로 선택하세요.")
    if scale < 1:
        raise ValueError("목표 바코드 크기가 1도트 모듈보다 작습니다. 바코드 크기를 키우세요.")
    sw, sh = source.width * scale, source.height * scale
    if check_bounds and (sw > width or sh > height):
        raise ValueError(
            f"바코드 공간이 부족합니다. 바코드에만 {sw}×{sh}도트가 필요합니다. 전체 개체 영역을 키우세요. "
            "바코드 크기를 자동으로 줄이지 않습니다."
        )
    # The symbol origin is stable even when HRI is disabled or moved below.
    x, y = 0, 0
    return SymbolGeometry((x, y, x + sw, y + sh), scale,
                          (sw * 25.4 / dpi, sh * 25.4 / dpi), position, gap)


def _pack_groups(groups: Sequence[str], max_width: int, measure: Callable[[str], int]) -> list[str] | None:
    lines: list[str] = []
    current = ""
    for group in groups:
        if measure(group) > max_width:
            return None
        candidate = current + group
        if current and measure(candidate) > max_width:
            lines.append(current)
            current = group
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render_barcode_first(
    source: Image.Image, element: Mapping[str, object], value: str | Sequence[str],
    width: int, height: int, dpi: int, load_font: FontLoader, *,
    preview_only: bool = False,
) -> Image.Image:
    """Render exact-size symbol, then intact HRI groups, or reject insufficient space.

    ``value`` is display text or already formatted GS1 AI groups. Encoder data
    stays in ``source`` and is never derived from display text. Bounds are
    half-open print-dot coordinates. Quiet zones are part of symbol bounds.
    """
    geometry = symbol_geometry(source, element, width, height, dpi, check_bounds=not preview_only)
    x, y, right, bottom = geometry.bounds
    image = Image.new("1", (max(width, right), max(height, bottom)), 1)
    symbol = source.convert("1").resize((right - x, bottom - y), Image.Resampling.NEAREST)
    image.paste(symbol, (x, y))
    image.info.update(source.info)
    image.info.update(symbol_bounds=geometry.bounds, hri_bounds=None,
                      module_dots=geometry.module_dots, hri_lines=[],
                      actual_symbol_mm=geometry.actual_symbol_mm,
                      hri_layout=geometry.hri_position, actual_hri_font_pt=None)
    options = element.get("barcode_options", {})
    if not isinstance(options, Mapping):
        raise ValueError("바코드 옵션 형식이 올바르지 않습니다.")
    groups = [value] if isinstance(value, str) else list(value)
    if any(not isinstance(group, str) for group in groups):
        raise ValueError("표시문자 값은 문자열이어야 합니다.")
    if not options.get("human_readable", True) or not any(groups):
        return image
    layout = element["barcode_layout"]
    assert isinstance(layout, Mapping)
    font_mode = layout.get("hri_font_mode", "auto")
    if font_mode not in {"auto", "fixed"}:
        raise ValueError("표시문자 글꼴 방식은 자동 또는 고정으로 선택하세요.")
    requested_pt = _number(element.get("font_size", 10), "글자 크기", MIN_HRI_FONT_PT)
    minimum_px = math.ceil(MIN_HRI_FONT_PT * dpi / 72)
    requested_px = max(minimum_px, round(requested_pt * dpi / 72))
    if geometry.hri_position == "right":
        tx, ty, available_width, available_height = right + geometry.gap_dots, 0, width - right - geometry.gap_dots, height
    else:
        tx, ty, available_width, available_height = 0, bottom + geometry.gap_dots, width, height - bottom - geometry.gap_dots
    if available_width <= 0 or available_height <= 0:
        message = "바코드 크기를 유지하면 표시문자 공간이 부족합니다. 전체 영역을 키우거나 문자 위치를 변경하세요."
        if preview_only:
            image.info["layout_error"] = message
            image.info["layout_overflow"] = True
            return image
        raise ValueError(message)
    preferred_px = min(requested_px, max(minimum_px, (bottom - y) // 3))
    sizes = [requested_px] if font_mode == "fixed" else range(preferred_px, minimum_px - 1, -1)
    draw = ImageDraw.Draw(image)
    for size in sizes:
        font = load_font(size, str(element.get("font_name") or "Consolas"))
        def measure(text: str) -> int:
            bounds = draw.textbbox((0, 0), text, font=font)
            return bounds[2] - bounds[0]
        lines = _pack_groups(groups, available_width, measure)
        if not lines:
            continue
        boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
        text_width = max(box[2] - box[0] for box in boxes)
        line_height = max(box[3] - box[1] for box in boxes)
        line_gap = max(1, round(size * 0.15))
        text_height = line_height * len(lines) + line_gap * (len(lines) - 1)
        if text_height <= available_height:
            break
    else:
        message = (
            "바코드 크기와 표시문자 원문을 유지할 공간이 부족합니다. "
            "전체 영역을 키우거나 문자 위치를 변경하세요. 글자를 자르거나 바코드를 줄이지 않습니다."
        )
        if preview_only:
            image.info["layout_error"] = message
            image.info["layout_overflow"] = True
            return image
        raise ValueError(message)
    if geometry.hri_position == "right":
        ty += max(0, (bottom - y - text_height) // 2)
    else:
        tx += max(0, (right - x - text_width) // 2)
    for index, (line, box) in enumerate(zip(lines, boxes)):
        draw.text((tx - box[0], ty + index * (line_height + line_gap) - box[1]),
                  line, font=font, fill=0)
    image.info.update(hri_bounds=(tx, ty, tx + text_width, ty + text_height),
                      hri_lines=lines, actual_hri_font_pt=size * 72 / dpi)
    return image



def measure_barcode_first(
    source: Image.Image, element: Mapping[str, object], value: str | Sequence[str],
    dpi: int, load_font: FontLoader, *, max_width_mm: float,
) -> Image.Image:
    """Render the actual composite bounds without resizing the symbol to fit text.

    ``max_width_mm`` is the available label budget used only for HRI wrapping.
    A single AI group that cannot fit remains whole in the returned image;
    ``layout_overflow``/``layout_error`` tell callers to block strict output.
    Height is the measured symbol/text extent, never a hidden text constraint.
    Target-free legacy values use element width/height as a stable size seed;
    callers should freeze these targets before adopting measured group bounds.
    """
    if isinstance(dpi, bool) or not isinstance(dpi, int) or dpi <= 0:
        raise ValueError("DPI는 양의 정수로 지정하세요.")
    budget_mm = _number(max_width_mm, "현재 라벨의 가용 너비", 0)
    budget = max(0, _floor_mm_dots(budget_mm, dpi))
    seed_width = max(1, mm_to_dots(_number(element.get("width", 10), "전체 너비"), dpi))
    seed_height = max(1, mm_to_dots(_number(element.get("height", 10), "전체 높이"), dpi))
    geometry = symbol_geometry(source, element, seed_width, seed_height, dpi, check_bounds=False)
    sw, sh = geometry.bounds[2:]
    options = element.get("barcode_options", {})
    if not isinstance(options, Mapping):
        raise ValueError("바코드 옵션 형식이 올바르지 않습니다.")
    groups = [value] if isinstance(value, str) else list(value)
    if any(not isinstance(group, str) for group in groups):
        raise ValueError("표시문자 값은 문자열이어야 합니다.")
    base_info = dict(source.info)
    base_info.update(symbol_bounds=geometry.bounds, hri_bounds=None,
                     module_dots=geometry.module_dots, hri_lines=[],
                     actual_symbol_mm=geometry.actual_symbol_mm,
                     hri_layout=geometry.hri_position, actual_hri_font_pt=None,
                     layout_overflow=False, layout_error=None)
    if not options.get("human_readable", True) or not any(groups):
        result = Image.new("1", (sw, sh), 1)
        result.paste(source.convert("1").resize((sw, sh), Image.Resampling.NEAREST), (0, 0))
        result.info.update(base_info)
    else:
        layout = element["barcode_layout"]
        assert isinstance(layout, Mapping)
        mode = layout.get("hri_font_mode", "auto")
        if mode not in {"auto", "fixed"}:
            raise ValueError("표시문자 글꼴 방식은 자동 또는 고정으로 선택하세요.")
        requested_pt = _number(element.get("font_size", 10), "글자 크기", MIN_HRI_FONT_PT)
        minimum_px = math.ceil(MIN_HRI_FONT_PT * dpi / 72)
        requested_px = max(minimum_px, round(requested_pt * dpi / 72))
        preferred_px = min(requested_px, max(minimum_px, sh // 3))
        sizes = [requested_px] if mode == "fixed" else range(preferred_px, minimum_px - 1, -1)
        available = budget - sw - geometry.gap_dots if geometry.hri_position == "right" else budget
        measuring = ImageDraw.Draw(Image.new("1", (1, 1), 1))
        overflow = False
        for size in sizes:
            font = load_font(size, str(element.get("font_name") or "Consolas"))
            def measure(text: str) -> int:
                box = measuring.textbbox((0, 0), text, font=font)
                return box[2] - box[0]
            lines = _pack_groups(groups, available, measure)
            if lines:
                break
        else:
            # Keep every group intact at the smallest allowed font (or the
            # explicitly fixed font). An impossible label budget is an error,
            # not permission to clip, delete data, or shrink the symbol.
            lines = [group for group in groups if group]
            overflow = True
        boxes = [measuring.textbbox((0, 0), line, font=font) for line in lines]
        tw = max(box[2] - box[0] for box in boxes)
        line_height = max(1, max(box[3] - box[1] for box in boxes))
        line_gap = max(1, round(size * 0.15))
        th = line_height * len(lines) + line_gap * (len(lines) - 1)
        if geometry.hri_position == "right":
            width, height = sw + geometry.gap_dots + tw, max(sh, th)
            tx, ty = sw + geometry.gap_dots, max(0, (sh - th) // 2)
        else:
            width, height = max(sw, tw), sh + geometry.gap_dots + th
            tx, ty = max(0, (sw - tw) // 2), sh + geometry.gap_dots
        result = Image.new("1", (width, height), 1)
        result.paste(source.convert("1").resize((sw, sh), Image.Resampling.NEAREST), (0, 0))
        drawing = ImageDraw.Draw(result)
        for index, (line, box) in enumerate(zip(lines, boxes)):
            drawing.text((tx - box[0], ty + index * (line_height + line_gap) - box[1]), line, font=font, fill=0)
        result.info.update(base_info)
        result.info.update(hri_bounds=(tx, ty, tx + tw, ty + th), hri_lines=lines,
                           actual_hri_font_pt=size * 72 / dpi, layout_overflow=overflow)
        if overflow:
            result.info["layout_error"] = (
                "표시문자 원문을 유지할 라벨 너비가 부족합니다. 문자 아래 배치나 라벨 너비를 확인하세요. "
                "필수 값을 자르거나 바코드를 줄이지 않습니다."
            )
    actual_group_mm = (result.width * 25.4 / dpi, result.height * 25.4 / dpi)
    result.info.update(actual_group_mm=actual_group_mm, required_size_mm=actual_group_mm)
    if result.width > budget:
        result.info["layout_overflow"] = True
        if not result.info["layout_error"]:
            result.info["layout_error"] = "바코드와 표시문자가 현재 라벨 너비를 넘습니다. 크기 또는 배치를 조절하세요."
    return result
