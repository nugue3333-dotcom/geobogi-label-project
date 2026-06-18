from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TypeAlias

from PIL import Image, ImageDraw, ImageFont

from .config import BarcodeConfig
from .excel_reader import LabelRow
from .sanitizer import sanitize_barcode, sanitize_slcs_text, sanitize_tspl_text, sanitize_zpl_text

CommandPayload: TypeAlias = str | bytes
ONE_D_BARCODE_TYPES = {"code128", "code39", "ean13", "ean8", "upca", "itf"}


def mm_to_dots(mm: int | float, dpi: int) -> int:
    return round(float(mm) / 25.4 * dpi)


def default_barcode_config(one_d_wide: int = 2) -> BarcodeConfig:
    return BarcodeConfig(
        barcode_type="code128",
        auto_layout=True,
        x=130,
        y=115,
        rotation=0,
        one_d_height=80,
        one_d_narrow=2,
        one_d_wide=one_d_wide,
        one_d_human_readable=True,
        qr_model=2,
        qr_ecc="M",
        qr_cell_size=4,
        datamatrix_cell_size=4,
        pdf417_rows=30,
        pdf417_columns=5,
        pdf417_security_level=2,
        pdf417_module_width=3,
        pdf417_module_height=10,
    )


def render_slcs(
    row: LabelRow,
    width_mm: int = 60,
    height_mm: int = 40,
    dpi: int = 203,
    gap_mm: int | float = 3,
    print_method: str = "direct_thermal",
    barcode_config: BarcodeConfig | None = None,
    print_speed: int | None = None,
    print_density: int | None = None,
    media_handling: str = "tear_off",
) -> str:
    config = barcode_config or default_barcode_config(one_d_wide=6)
    width_dot = mm_to_dots(width_mm, dpi)
    height_dot = mm_to_dots(height_mm, dpi)
    gap_dot = mm_to_dots(gap_mm, dpi)

    item_name = sanitize_slcs_text(row.item_name)
    item_code = sanitize_slcs_text(row.item_code)
    barcode = sanitize_barcode(row.barcode)
    lot_no = sanitize_slcs_text(row.lot_no)

    speed = 3 if print_speed is None else print_speed
    density = 20 if print_density is None else print_density
    layout = _auto_label_layout(width_dot, height_dot, config, barcode)
    positioned_config = _auto_positioned_barcode_config("slcs", width_dot, height_dot, barcode, config, layout)

    return (
        "CB\n"
        f"SS{speed}\n"
        f"SD{density}\n"
        "CS13,0\n"
        f"{_slcs_print_method_command(print_method)}"
        f"{_slcs_media_handling_command(media_handling)}"
        f"SW{width_dot}\n"
        f"SL{height_dot},{gap_dot},G\n"
        "SOT\n"
        f"T{_centered_text_x(width_dot, layout['text_width'], f'ITEM: {item_name}', layout['item_font'])},{layout['item_y']},b,1,1,0,0,N,N,'ITEM: {item_name}'\n"
        f"T{_centered_text_x(width_dot, layout['text_width'], f'CODE: {item_code}', layout['code_font'])},{layout['code_y']},c,1,1,0,0,N,N,'CODE: {item_code}'\n"
        f"{_render_slcs_barcode(barcode, positioned_config)}"
        f"T{_centered_text_x(width_dot, layout['text_width'], f'LOT: {lot_no} / QTY: {row.qty}', layout['lot_font'])},{layout['lot_y']},c,1,1,0,0,N,N,'LOT: {lot_no} / QTY: {row.qty}'\n"
        f"P{row.print_qty}\n"
    )


def render_tspl(
    row: LabelRow,
    width_mm: int = 60,
    height_mm: int = 40,
    dpi: int = 203,
    gap_mm: int | float = 3,
    print_method: str = "direct_thermal",
    barcode_config: BarcodeConfig | None = None,
    command_encoding: str = "utf-8",
    print_speed: int | None = None,
    print_density: int | None = None,
    media_handling: str = "tear_off",
) -> bytes:
    config = barcode_config or default_barcode_config(one_d_wide=2)
    width_dot = mm_to_dots(width_mm, dpi)
    height_dot = mm_to_dots(height_mm, dpi)
    item_name = sanitize_tspl_text(row.item_name)
    item_code = sanitize_tspl_text(row.item_code)
    barcode = sanitize_barcode(row.barcode)
    lot_no = sanitize_tspl_text(row.lot_no)
    layout = _auto_label_layout(width_dot, height_dot, config, barcode)
    positioned_config = _auto_positioned_barcode_config("tspl", width_dot, height_dot, barcode, config, layout)
    barcode_command = _render_tspl_barcode(barcode, positioned_config).encode("ascii")
    speed = 4 if print_speed is None else print_speed
    density = 8 if print_density is None else print_density
    header = (
        f"SIZE {width_mm} mm,{height_mm} mm\n"
        f"GAP {gap_mm} mm,0 mm\n"
        f"{_tspl_codepage_command(command_encoding)}"
        f"DENSITY {density}\n"
        f"SPEED {speed}\n"
        f"{_tspl_print_method_command(print_method)}"
        f"{_tspl_media_handling_command(media_handling)}"
        "DIRECTION 1\n"
        "REFERENCE 0,0\n"
        "CLS\n"
    ).encode("ascii")

    return b"".join(
        [
            header,
            _tspl_text_bitmap(
                layout["margin_x"],
                layout["item_y"],
                f"ITEM: {item_name}",
                layout["text_width"],
                layout["item_font"],
                "center",
            ),
            _tspl_text_bitmap(
                layout["margin_x"],
                layout["code_y"],
                f"CODE: {item_code}",
                layout["text_width"],
                layout["code_font"],
                "center",
            ),
            barcode_command,
            _tspl_text_bitmap(
                layout["margin_x"],
                layout["lot_y"],
                f"LOT: {lot_no} / QTY: {row.qty}",
                layout["text_width"],
                layout["lot_font"],
                "center",
            ),
            f"PRINT 1,{row.print_qty}\n".encode("ascii"),
        ]
    )


def render_zpl(
    row: LabelRow,
    width_mm: int = 60,
    height_mm: int = 40,
    dpi: int = 203,
    gap_mm: int | float = 3,
    print_method: str = "direct_thermal",
    barcode_config: BarcodeConfig | None = None,
    command_encoding: str = "utf-8",
    print_speed: int | None = None,
    print_density: int | None = None,
    media_handling: str = "tear_off",
) -> str:
    config = barcode_config or default_barcode_config(one_d_wide=2)
    width_dot = mm_to_dots(width_mm, dpi)
    height_dot = mm_to_dots(height_mm, dpi)

    item_name = sanitize_zpl_text(row.item_name)
    item_code = sanitize_zpl_text(row.item_code)
    barcode = sanitize_barcode(row.barcode)
    lot_no = sanitize_zpl_text(row.lot_no)
    speed = 4 if print_speed is None else print_speed
    density = 10 if print_density is None else print_density
    layout = _auto_label_layout(width_dot, height_dot, config, barcode)
    positioned_config = _auto_positioned_barcode_config("zpl", width_dot, height_dot, barcode, config, layout)

    return (
        "^XA\n"
        "^CI28\n"
        f"{_zpl_print_method_command(print_method)}"
        f"{_zpl_media_handling_command(media_handling)}"
        f"^PR{speed}\n"
        f"^MD{density}\n"
        f"^PW{width_dot}\n"
        f"^LL{height_dot}\n"
        f"^FO{layout['margin_x']},{layout['item_y']}^FB{layout['text_width']},1,0,C,0^A0N,{layout['item_font']},{layout['item_font']}^FDITEM: {item_name}^FS\n"
        f"^FO{layout['margin_x']},{layout['code_y']}^FB{layout['text_width']},1,0,C,0^A0N,{layout['code_font']},{layout['code_font']}^FDCODE: {item_code}^FS\n"
        f"{_render_zpl_barcode(barcode, positioned_config)}"
        f"^FO{layout['margin_x']},{layout['lot_y']}^FB{layout['text_width']},1,0,C,0^A0N,{layout['lot_font']},{layout['lot_font']}^FDLOT: {lot_no} / QTY: {row.qty}^FS\n"
        f"^PQ{row.print_qty}\n"
        "^XZ\n"
    )


def render_label(
    language: str,
    row: LabelRow,
    width_mm: int,
    height_mm: int,
    dpi: int,
    gap_mm: int | float = 3,
    print_method: str = "direct_thermal",
    barcode_config: BarcodeConfig | None = None,
    command_encoding: str = "utf-8",
    print_speed: int | None = None,
    print_density: int | None = None,
    media_handling: str = "tear_off",
) -> CommandPayload:
    if language == "slcs":
        return render_slcs(row, width_mm, height_mm, dpi, gap_mm, print_method, barcode_config, print_speed, print_density, media_handling)
    if language == "tspl":
        return render_tspl(
            row,
            width_mm,
            height_mm,
            dpi,
            gap_mm,
            print_method,
            barcode_config,
            command_encoding,
            print_speed,
            print_density,
            media_handling,
        )
    if language == "zpl":
        return render_zpl(row, width_mm, height_mm, dpi, gap_mm, print_method, barcode_config, command_encoding, print_speed, print_density, media_handling)
    raise ValueError("language must be 'slcs', 'tspl', or 'zpl'")


def _render_slcs_barcode(barcode: str, config: BarcodeConfig) -> str:
    x = config.x
    y = config.y
    rotation = _slcs_rotation(config.rotation)
    hri = 1 if config.one_d_human_readable else 0
    if config.barcode_type in {"code128", "code39", "ean13", "ean8", "upca", "itf"}:
        symbology = {
            "code39": 0,
            "code128": 1,
            "itf": 2,
            "ean13": 3,
            "ean8": 4,
            "upca": 5,
        }[config.barcode_type]
        return (
            f"B1{x},{y},{symbology},{config.one_d_narrow},{config.one_d_wide},"
            f"{config.one_d_height},{rotation},{hri},'{barcode}'\n"
        )
    if config.barcode_type == "qr":
        return f"B2{x},{y},Q,{config.qr_model},{config.qr_ecc},{config.qr_cell_size},{rotation},'{barcode}'\n"
    if config.barcode_type == "datamatrix":
        return f"B2{x},{y},D,{config.datamatrix_cell_size},N,{rotation},'{barcode}'\n"
    if config.barcode_type == "pdf417":
        return (
            f"B2{x},{y},P,{config.pdf417_rows},{config.pdf417_columns},{config.pdf417_security_level},"
            f"0,{hri},1,{config.pdf417_module_width},{config.pdf417_module_height},{rotation},'{barcode}'\n"
        )
    raise ValueError(f"unsupported barcode.type: {config.barcode_type}")


def _render_tspl_barcode(barcode: str, config: BarcodeConfig, height: int | None = None) -> str:
    x = config.x
    y = config.y
    rotation = _tspl_rotation(config.rotation)
    hri = 1 if config.one_d_human_readable else 0
    one_d_height = height if height is not None else config.one_d_height
    if config.barcode_type in {"code128", "code39", "ean13", "ean8", "upca", "itf"}:
        symbology = {
            "code128": "128",
            "code39": "39",
            "ean13": "EAN13",
            "ean8": "EAN8",
            "upca": "UPCA",
            "itf": "ITF",
        }[config.barcode_type]
        return (
            f'BARCODE {x},{y},"{symbology}",{one_d_height},{hri},{rotation},'
            f'{config.one_d_narrow},{config.one_d_wide},"{barcode}"\n'
        )
    if config.barcode_type == "qr":
        return f'QRCODE {x},{y},{config.qr_ecc},{config.qr_cell_size},A,{rotation},M{config.qr_model},S7,"{barcode}"\n'
    if config.barcode_type == "datamatrix":
        size = max(24, config.datamatrix_cell_size * 24)
        return f'DMATRIX {x},{y},{size},{size},{config.datamatrix_cell_size},{config.datamatrix_cell_size},"{barcode}"\n'
    if config.barcode_type == "pdf417":
        return (
            f'PDF417 {x},{y},{config.pdf417_module_width},{config.pdf417_module_height},'
            f'{config.pdf417_columns},{config.pdf417_rows},{config.pdf417_security_level},{rotation},"{barcode}"\n'
        )
    raise ValueError(f"unsupported barcode.type: {config.barcode_type}")


def _render_zpl_barcode(barcode: str, config: BarcodeConfig) -> str:
    x = config.x
    y = config.y
    rotation = _zpl_rotation(config.rotation)
    hri = "Y" if config.one_d_human_readable else "N"
    if config.barcode_type == "code128":
        return (
            f"^FO{x},{y}^BY{config.one_d_narrow},{config.one_d_wide},{config.one_d_height}"
            f"^BC{rotation},{config.one_d_height},{hri},N,N^FD{barcode}^FS\n"
        )
    if config.barcode_type == "code39":
        return (
            f"^FO{x},{y}^BY{config.one_d_narrow},{config.one_d_wide},{config.one_d_height}"
            f"^B3{rotation},N,{config.one_d_height},{hri},N^FD{barcode}^FS\n"
        )
    if config.barcode_type == "ean13":
        return f"^FO{x},{y}^BE{rotation},{config.one_d_height},{hri},N^FD{barcode}^FS\n"
    if config.barcode_type == "ean8":
        return f"^FO{x},{y}^B8{rotation},{config.one_d_height},{hri},N^FD{barcode}^FS\n"
    if config.barcode_type == "upca":
        return f"^FO{x},{y}^BU{rotation},{config.one_d_height},{hri},N,Y^FD{barcode}^FS\n"
    if config.barcode_type == "itf":
        return (
            f"^FO{x},{y}^BY{config.one_d_narrow},{config.one_d_wide},{config.one_d_height}"
            f"^B2{rotation},{config.one_d_height},{hri},N,N^FD{barcode}^FS\n"
        )
    if config.barcode_type == "qr":
        return f"^FO{x},{y}^BQ{rotation},{config.qr_model},{config.qr_cell_size}^FDLA,{barcode}^FS\n"
    if config.barcode_type == "datamatrix":
        return f"^FO{x},{y}^BX{rotation},{config.datamatrix_cell_size},200^FD{barcode}^FS\n"
    if config.barcode_type == "pdf417":
        return (
            f"^FO{x},{y}^B7{rotation},{config.pdf417_module_height},{config.pdf417_security_level},"
            f"{config.pdf417_columns},{config.pdf417_rows},N^FD{barcode}^FS\n"
        )
    raise ValueError(f"unsupported barcode.type: {config.barcode_type}")


def _auto_positioned_barcode_config(
    language: str,
    width_dot: int,
    height_dot: int,
    barcode: str,
    config: BarcodeConfig,
    layout: dict[str, int],
) -> BarcodeConfig:
    if not config.auto_layout:
        return config
    if _is_one_d(config):
        return _auto_positioned_1d_config(language, width_dot, barcode, config, layout)
    return _auto_positioned_2d_config(width_dot, height_dot, barcode, config, layout)


def _auto_positioned_1d_config(
    language: str,
    width_dot: int,
    barcode: str,
    config: BarcodeConfig,
    layout: dict[str, int],
) -> BarcodeConfig:
    module_count = _barcode_module_count(config.barcode_type, barcode)
    target_width = layout["barcode_target_width"]
    max_narrow = 6 if language == "slcs" else 4
    narrow = _clamp(round(target_width / module_count), 1, max_narrow)
    wide = _auto_wide_value(language, narrow, config)
    candidate = replace(config, one_d_narrow=narrow, one_d_wide=wide, one_d_height=layout["barcode_height"])
    barcode_width = _estimated_1d_width(candidate.barcode_type, barcode, candidate)
    max_width = width_dot - (max(8, layout["margin_x"] // 2) * 2)
    while barcode_width > max_width and narrow > 1:
        narrow -= 1
        wide = _auto_wide_value(language, narrow, config)
        candidate = replace(candidate, one_d_narrow=narrow, one_d_wide=wide)
        barcode_width = _estimated_1d_width(candidate.barcode_type, barcode, candidate)
    return replace(candidate, x=_centered_object_x(width_dot, barcode_width, layout["margin_x"]), y=layout["barcode_y"])


def _auto_positioned_2d_config(
    width_dot: int,
    height_dot: int,
    barcode: str,
    config: BarcodeConfig,
    layout: dict[str, int],
) -> BarcodeConfig:
    target_size = min(layout["barcode_target_width"], layout["barcode_height"], round(height_dot * 0.38))
    if config.barcode_type == "qr":
        cell_size = _clamp(round(target_size / 29), 2, 10)
        size = cell_size * 29
        return replace(config, qr_cell_size=cell_size, x=_centered_object_x(width_dot, size, layout["margin_x"]), y=layout["barcode_y"])
    if config.barcode_type == "datamatrix":
        cell_size = _clamp(round(target_size / 24), 2, 10)
        size = max(24, cell_size * 24)
        return replace(
            config,
            datamatrix_cell_size=cell_size,
            x=_centered_object_x(width_dot, size, layout["margin_x"]),
            y=layout["barcode_y"],
        )
    if config.barcode_type == "pdf417":
        module_width = _clamp(round(target_size / max(1, config.pdf417_columns * 17)), 2, 6)
        size = config.pdf417_columns * 17 * module_width
        return replace(
            config,
            pdf417_module_width=module_width,
            x=_centered_object_x(width_dot, size, layout["margin_x"]),
            y=layout["barcode_y"],
        )
    return replace(config, x=_centered_object_x(width_dot, _estimated_2d_size(config, barcode), layout["margin_x"]), y=layout["barcode_y"])


def _is_one_d(config: BarcodeConfig) -> bool:
    return config.barcode_type in ONE_D_BARCODE_TYPES


def _auto_wide_value(language: str, narrow: int, config: BarcodeConfig) -> int:
    if language == "zpl":
        return _clamp(config.one_d_wide, 2, 3)
    wide_ratio = 3 if language == "slcs" else 2
    return max(narrow + 1, narrow * wide_ratio)


def _barcode_module_count(barcode_type: str, barcode: str) -> int:
    length = max(1, len(barcode))
    if barcode_type == "code128":
        return max(68, ((length + 3) * 11) + 13)
    if barcode_type == "code39":
        return max(70, (length * 13) + 35)
    if barcode_type == "ean13":
        return 113
    if barcode_type == "ean8":
        return 81
    if barcode_type == "upca":
        return 113
    if barcode_type == "itf":
        return max(70, (length * 9) + 45)
    return max(70, length * 11)


def _estimated_1d_width(barcode_type: str, barcode: str, config: BarcodeConfig) -> int:
    return _barcode_module_count(barcode_type, barcode) * max(1, config.one_d_narrow)


def _estimated_2d_size(config: BarcodeConfig, barcode: str) -> int:
    if config.barcode_type == "qr":
        # Most short label values stay near QR version 1-3. Use a conservative module count for centering.
        modules = 29 if len(barcode) <= 24 else 37
        return modules * config.qr_cell_size
    if config.barcode_type == "datamatrix":
        return max(24, config.datamatrix_cell_size * 24)
    if config.barcode_type == "pdf417":
        return max(60, config.pdf417_columns * 17 * config.pdf417_module_width)
    return 80


def _centered_object_x(width_dot: int, object_width: int, minimum_margin: int) -> int:
    return max(minimum_margin, round((width_dot - object_width) / 2))


def _centered_text_x(width_dot: int, max_width: int, text: str, font_size: int) -> int:
    text_width = min(max_width, _estimated_text_width(text, font_size))
    return _centered_object_x(width_dot, text_width, max(12, round(width_dot * 0.04)))


def _estimated_text_width(text: str, font_size: int) -> int:
    visual_units = sum(2 if ord(char) > 127 else 1 for char in text)
    return max(1, round(visual_units * font_size * 0.33))


def _slcs_rotation(rotation: int) -> int:
    return {0: 0, 90: 1, 180: 2, 270: 3}.get(rotation, rotation)


def _tspl_rotation(rotation: int) -> int:
    return {0: 0, 90: 90, 180: 180, 270: 270}.get(rotation, rotation)


def _zpl_rotation(rotation: int) -> str:
    return {0: "N", 90: "R", 180: "I", 270: "B"}.get(rotation, "N")


def _slcs_print_method_command(print_method: str) -> str:
    if print_method == "thermal_transfer":
        return "STt\n"
    return "STd\n"


def _tspl_print_method_command(print_method: str) -> str:
    if print_method == "thermal_transfer":
        return "SET RIBBON ON\n"
    return "SET RIBBON OFF\n"


def _slcs_media_handling_command(media_handling: str) -> str:
    if media_handling == "cutter":
        return "CUTy\n"
    return "CUTn\n"


def _tspl_media_handling_command(media_handling: str) -> str:
    if media_handling == "cutter":
        return "SET CUTTER 1\nSET PEEL OFF\nSET TEAR OFF\n"
    if media_handling == "peeler":
        return "SET CUTTER OFF\nSET PEEL ON\nSET TEAR OFF\n"
    return "SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n"


def _tspl_codepage_command(command_encoding: str) -> str:
    normalized = command_encoding.strip().replace("_", "-").lower()
    if normalized in {"cp949", "ms949", "949", "ks-c-5601", "ks-c-5601-1987", "euc-kr"}:
        return "CODEPAGE 949\n"
    return "CODEPAGE UTF-8\n"


def _auto_label_layout(width_dot: int, height_dot: int, config: BarcodeConfig, barcode: str) -> dict[str, int]:
    margin_x = max(18, round(width_dot * 0.06))
    margin_y = max(12, round(height_dot * 0.05))
    text_width = max(120, width_dot - (margin_x * 2))
    item_font = _clamp(round(height_dot * 0.08), 20, 38)
    code_font = _clamp(round(height_dot * 0.065), 18, 32)
    lot_font = _clamp(round(height_dot * 0.065), 18, 32)
    line_gap = _clamp(round(height_dot * 0.024), 5, 10)
    hri_space = _clamp(round(height_dot * 0.13), 24, 38) if _is_one_d(config) and config.one_d_human_readable else line_gap
    reserved_height = item_font + code_font + lot_font + (line_gap * 4) + hri_space + (margin_y * 2)
    available_barcode_height = max(34, height_dot - reserved_height)
    barcode_height = min(_scaled_barcode_height(height_dot, config), available_barcode_height)
    if not _is_one_d(config):
        barcode_height = min(_estimated_2d_size(config, barcode), available_barcode_height, text_width)
    total_height = item_font + code_font + barcode_height + hri_space + lot_font + (line_gap * 4)
    item_y = max(margin_y, round((height_dot - total_height) / 2))
    code_y = item_y + item_font + max(8, round(height_dot * 0.025))
    barcode_y = code_y + code_font + line_gap
    lot_y = barcode_y + barcode_height + hri_space + line_gap
    max_lot_y = height_dot - margin_y - lot_font
    if lot_y > max_lot_y:
        shift = lot_y - max_lot_y
        item_y = max(2, item_y - shift)
        code_y = item_y + item_font + line_gap
        barcode_y = code_y + code_font + line_gap
        lot_y = min(max_lot_y, barcode_y + barcode_height + hri_space + line_gap)
    return {
        "margin_x": margin_x,
        "item_y": item_y,
        "code_y": code_y,
        "barcode_y": barcode_y,
        "lot_y": lot_y,
        "text_width": text_width,
        "item_font": item_font,
        "code_font": code_font,
        "lot_font": lot_font,
        "barcode_height": barcode_height,
        "barcode_target_width": text_width,
    }


def _scaled_barcode_height(height_dot: int, config: BarcodeConfig) -> int:
    if not _is_one_d(config):
        return config.one_d_height
    scaled = round(height_dot * 0.26)
    return _clamp(max(config.one_d_height, scaled), 54, 180)


def _tspl_text_bitmap(x: int, y: int, text: str, max_width: int, requested_font_size: int, align: str = "left") -> bytes:
    font = _fit_font(text, max_width, requested_font_size)
    probe = Image.new("L", (1, 1), 255)
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font)
    width = max(1, min(max_width, bbox[2] - bbox[0] + 6))
    height = max(1, bbox[3] - bbox[1] + 8)
    if align == "center":
        x += max(0, (max_width - width) // 2)
    image = Image.new("1", (width, height), 1)
    image_draw = ImageDraw.Draw(image)
    image_draw.text((3 - bbox[0], 4 - bbox[1]), text, fill=0, font=font)
    return _tspl_bitmap_command(x, y, image)


def _fit_font(text: str, max_width: int, requested_size: int) -> ImageFont.ImageFont:
    size = requested_size
    while size >= 14:
        font = _load_label_font(size)
        probe = Image.new("L", (1, 1), 255)
        bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] + 6 <= max_width:
            return font
        size -= 2
    return _load_label_font(14)


def _load_label_font(size: int) -> ImageFont.ImageFont:
    for font_path in (
        Path("C:/Windows/Fonts/malgunbd.ttf"),
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def _tspl_bitmap_command(x: int, y: int, image: Image.Image) -> bytes:
    width, height = image.size
    width_bytes = (width + 7) // 8
    pixels = image.load()
    payload = bytearray()
    for row in range(height):
        for byte_index in range(width_bytes):
            value = 0
            for bit in range(8):
                col = (byte_index * 8) + bit
                if col >= width or pixels[col, row] != 0:
                    value |= 0x80 >> bit
            payload.append(value)
    return f"BITMAP {x},{y},{width_bytes},{height},0,".encode("ascii") + bytes(payload) + b"\n"


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _zpl_print_method_command(print_method: str) -> str:
    if print_method == "thermal_transfer":
        return "^MTT\n"
    return "^MTD\n"


def _zpl_media_handling_command(media_handling: str) -> str:
    if media_handling == "cutter":
        return "^MMC\n"
    if media_handling == "peeler":
        return "^MMP\n"
    return "^MMT\n"
