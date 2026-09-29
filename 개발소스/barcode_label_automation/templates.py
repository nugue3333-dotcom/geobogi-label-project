from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TypeAlias

from PIL import Image, ImageDraw, ImageFont

from .config import BarcodeConfig, SUPPORTED_MEDIA_HANDLING_BY_LANGUAGE
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
    media_type: str = "gap",
    print_orientation: str = "normal",
) -> str:
    config = barcode_config or default_barcode_config(one_d_wide=6)
    width_dot = mm_to_dots(width_mm, dpi)
    height_dot = mm_to_dots(height_mm, dpi)
    gap_dot = mm_to_dots(gap_mm, dpi)

    barcode = sanitize_barcode(row.barcode)
    text_lines = _display_text_lines(row, sanitize_slcs_text, _max_text_lines(height_mm))

    speed = 3 if print_speed is None else print_speed
    density = 20 if print_density is None else print_density
    large_label = width_mm >= 80 and height_mm >= 80
    layout = _auto_label_layout(
        width_dot,
        height_dot,
        config,
        barcode,
        len(text_lines),
        max_text_chars=max(map(len, text_lines), default=1),
        large_label=large_label,
    )
    positioned_config = _auto_positioned_barcode_config("slcs", width_dot, height_dot, barcode, config, layout)
    text_commands = "".join(
        _slcs_text_command(
            layout["margin_x"],
            y,
            line,
            index,
            layout,
            use_vector_font=large_label,
        )
        for index, (line, y) in enumerate(zip(text_lines, layout["text_line_ys"], strict=False))
    )

    return (
        "CB\n"
        f"SS{speed}\n"
        f"SD{density}\n"
        "CS13,0\n"
        f"{_slcs_print_method_command(print_method)}"
        f"{_slcs_media_handling_command(media_handling)}"
        f"SW{width_dot}\n"
        f"{_slcs_media_type_command(height_dot, gap_dot, media_type)}"
        f"{print_orientation_command('slcs', print_orientation)}"
        f"{text_commands}"
        f"{_render_slcs_barcode(barcode, positioned_config)}"
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
    media_type: str = "gap",
    print_orientation: str = "normal",
) -> bytes:
    config = barcode_config or default_barcode_config(one_d_wide=2)
    width_dot = mm_to_dots(width_mm, dpi)
    height_dot = mm_to_dots(height_mm, dpi)
    barcode = sanitize_barcode(row.barcode)
    text_lines = _display_text_lines(row, sanitize_tspl_text, _max_text_lines(height_mm))
    layout = _auto_label_layout(
        width_dot,
        height_dot,
        config,
        barcode,
        len(text_lines),
        max_text_chars=max(map(len, text_lines), default=1),
        large_label=width_mm >= 80 and height_mm >= 80,
    )
    positioned_config = _auto_positioned_barcode_config("tspl", width_dot, height_dot, barcode, config, layout)
    barcode_command = _render_tspl_barcode(barcode, positioned_config).encode("ascii")
    speed = 4 if print_speed is None else print_speed
    density = 8 if print_density is None else print_density
    header = (
        f"SIZE {width_mm} mm,{height_mm} mm\n"
        f"{_tspl_media_type_command(gap_mm, media_type)}"
        f"{_tspl_codepage_command(command_encoding)}"
        f"DENSITY {density}\n"
        f"SPEED {speed}\n"
        f"{_tspl_print_method_command(print_method)}"
        f"{print_orientation_command('tspl', print_orientation)}"
        "REFERENCE 0,0\n"
        "CLS\n"
    ).encode("ascii")

    return b"".join(
        [
            header,
            *[
                _tspl_text_bitmap(layout["margin_x"], y, line, layout["text_width"], layout["text_font"], "left")
                for line, y in zip(text_lines, layout["text_line_ys"], strict=False)
            ],
            barcode_command,
            _tspl_media_handling_command(media_handling).encode("ascii"),
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
    media_type: str = "gap",
    print_orientation: str = "normal",
) -> str:
    config = barcode_config or default_barcode_config(one_d_wide=2)
    width_dot = mm_to_dots(width_mm, dpi)
    height_dot = mm_to_dots(height_mm, dpi)

    barcode = sanitize_barcode(row.barcode)
    text_lines = _display_text_lines(row, sanitize_zpl_text, _max_text_lines(height_mm))
    speed = 4 if print_speed is None else print_speed
    density = 10 if print_density is None else print_density
    layout = _auto_label_layout(
        width_dot,
        height_dot,
        config,
        barcode,
        len(text_lines),
        max_text_chars=max(map(len, text_lines), default=1),
        large_label=width_mm >= 80 and height_mm >= 80,
    )
    positioned_config = _auto_positioned_barcode_config("zpl", width_dot, height_dot, barcode, config, layout)
    text_commands = "".join(
        f"^FO{layout['margin_x']},{y}^FB{layout['text_width']},1,0,L,0^A0N,{layout['text_font']},{layout['text_font']}^FD{line}^FS\n"
        for line, y in zip(text_lines, layout["text_line_ys"], strict=False)
    )

    return (
        "^XA\n"
        "^CI28\n"
        f"{print_orientation_command('zpl', print_orientation)}"
        f"{_zpl_print_method_command(print_method)}"
        f"{_zpl_media_handling_command(media_handling)}"
        f"{_zpl_media_type_command(media_type)}"
        f"^PR{speed}\n"
        f"^MD{density}\n"
        f"^PW{width_dot}\n"
        f"^LL{height_dot}\n"
        f"{text_commands}"
        f"{_render_zpl_barcode(barcode, positioned_config)}"
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
    media_type: str = "gap",
    print_orientation: str = "normal",
) -> CommandPayload:
    if language == "slcs":
        return render_slcs(
            row,
            width_mm,
            height_mm,
            dpi,
            gap_mm,
            print_method,
            barcode_config,
            print_speed,
            print_density,
            media_handling,
            media_type,
            print_orientation,
        )
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
            media_type,
            print_orientation,
        )
    if language == "zpl":
        return render_zpl(
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
            media_type,
            print_orientation,
        )
    raise ValueError("language must be 'slcs', 'tspl', or 'zpl'")


def _render_slcs_barcode(barcode: str, config: BarcodeConfig) -> str:
    x = config.x
    y = config.y
    rotation = _slcs_rotation(config.rotation)
    hri = _slcs_hri_mode(config)
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


def _slcs_hri_mode(config: BarcodeConfig) -> int:
    if not config.one_d_human_readable:
        return 0
    # SLCS B1 p8 values 1/3/5/7 print the HRI below the bars in
    # progressively larger device fonts.
    if config.one_d_height >= 200:
        return 5
    if config.one_d_height >= 120:
        return 3
    return 1


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
    _ensure_media_handling_supported("slcs", media_handling)
    if media_handling == "cutter":
        return "CUTy\n"
    return "CUTn\n"


def _slcs_media_type_command(height_dot: int, gap_dot: int, media_type: str) -> str:
    if media_type == "gap":
        return f"SL{height_dot},{gap_dot},G\n"
    if media_type == "black_mark":
        return f"SL{height_dot},{gap_dot},B\n"
    if media_type == "continuous":
        return f"SL{height_dot},0,C\n"
    raise ValueError("media_type must be 'gap', 'black_mark', or 'continuous'.")


def _tspl_media_handling_command(media_handling: str) -> str:
    _ensure_media_handling_supported("tspl", media_handling)
    if media_handling == "cutter":
        return "SET PEEL OFF\nSET CUTTER 1\n"
    if media_handling == "peeler":
        return "SET CUTTER OFF\nSET PEEL ON\n"
    return "SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n"


def _tspl_media_type_command(gap_mm: int | float, media_type: str) -> str:
    if media_type == "gap":
        return f"GAP {gap_mm:g} mm,0 mm\n"
    if media_type == "black_mark":
        return f"BLINE {gap_mm:g} mm,0 mm\n"
    if media_type == "continuous":
        return "GAP 0,0\n"
    raise ValueError("media_type must be 'gap', 'black_mark', or 'continuous'.")


def _tspl_codepage_command(command_encoding: str) -> str:
    normalized = command_encoding.strip().replace("_", "-").lower()
    if normalized in {"cp949", "ms949", "949", "ks-c-5601", "ks-c-5601-1987", "euc-kr"}:
        return "CODEPAGE 949\n"
    return "CODEPAGE UTF-8\n"


def _auto_label_layout(
    width_dot: int,
    height_dot: int,
    config: BarcodeConfig,
    barcode: str,
    text_line_count: int = 3,
    *,
    max_text_chars: int = 24,
    large_label: bool = False,
) -> dict[str, object]:
    margin_x = max(18, round(width_dot * 0.05))
    margin_y = max(10, round(height_dot * 0.04))
    text_width = max(120, width_dot - (margin_x * 2))
    line_count = _clamp(text_line_count, 1, 8)
    text_font = max(14, round(height_dot * (0.10 if line_count <= 2 else 0.085)))
    estimated_text_width = max(1, max_text_chars) * text_font * 0.62
    if estimated_text_width > text_width:
        text_font = max(14, round(text_font * text_width / estimated_text_width))
    line_gap = max(3, round(height_dot * 0.018))
    section_gap = max(line_gap * 2, round(height_dot * 0.04))
    hri_ratio = 0.12 if large_label else 0.10
    hri_space = max(18, round(height_dot * hri_ratio)) if _is_one_d(config) and config.one_d_human_readable else line_gap
    content_height = max(1, height_dot - (margin_y * 2))
    minimum_barcode_height = 30

    def text_height_for(font_size: int) -> int:
        return (font_size * line_count) + (line_gap * max(0, line_count - 1))

    text_height = text_height_for(text_font)
    while text_font > 14 and text_height + section_gap + hri_space + minimum_barcode_height > content_height:
        text_font -= 1
        text_height = text_height_for(text_font)

    available_barcode_height = max(
        minimum_barcode_height,
        content_height - text_height - section_gap - hri_space,
    )
    barcode_height = min(_scaled_barcode_height(height_dot, config, large_label=large_label), available_barcode_height)
    if not _is_one_d(config):
        barcode_height = min(_estimated_2d_size(config, barcode), available_barcode_height, text_width)
    # Start text at the printable top margin. Distribute spare vertical space
    # around the barcode so large square labels do not leave one empty band in
    # the middle or press the human-readable text against the lower edge.
    text_y = margin_y
    minimum_barcode_y = text_y + text_height + section_gap
    occupied_height = text_height + section_gap + barcode_height + hri_space
    spare_height = max(0, content_height - occupied_height)
    barcode_y = minimum_barcode_y + round(spare_height * (0.4 if large_label else 0.6))
    text_line_ys = [text_y + ((text_font + line_gap) * index) for index in range(line_count)]
    return {
        "margin_x": margin_x,
        "margin_y": margin_y,
        "text_line_ys": text_line_ys,
        "barcode_y": barcode_y,
        "text_width": text_width,
        "text_font": text_font,
        "barcode_height": barcode_height,
        "barcode_target_width": round(text_width * 0.78) if large_label and _is_one_d(config) else text_width,
        "content_bottom": barcode_y + barcode_height + hri_space,
        "label_bottom": height_dot - margin_y,
    }


def _scaled_barcode_height(height_dot: int, config: BarcodeConfig, *, large_label: bool = False) -> int:
    if not _is_one_d(config):
        return config.one_d_height
    if large_label:
        scaled = round(height_dot * 0.30)
        maximum = max(64, round(height_dot * 0.34))
        return _clamp(max(config.one_d_height, scaled), 64, maximum)
    scaled = round(height_dot * 0.38)
    maximum = max(64, round(height_dot * 0.46))
    return _clamp(max(config.one_d_height, scaled), 64, maximum)


def _max_text_lines(height_mm: int | float) -> int:
    """Return physical label capacity; the result must not vary by DPI."""
    if height_mm < 30:
        return 2
    if height_mm < 40:
        return 3
    # A connected DB can expose more than the built-in four columns. Scale
    # capacity with physical label height and let the common layout shrink text.
    return _clamp(int(float(height_mm) // 8), 5, 8)


def _display_text_lines(row: LabelRow, sanitize_text, max_lines: int = 4) -> tuple[str, ...]:
    if row.source_fields:
        fields = row.source_fields
        reject_overflow = True
    else:
        fields = (
            ("품명", row.item_name),
            ("코드", row.item_code),
            ("LOT", row.lot_no),
            ("수량", str(row.qty)),
        )
        reject_overflow = False
    lines: list[str] = []
    for header, raw_value in fields:
        value = sanitize_text(str(raw_value))
        if not value:
            continue
        label = sanitize_text(str(header))
        lines.append(f"{label}: {value}" if label else value)
    if not lines:
        lines.append(sanitize_text(row.barcode))
    if reject_overflow and len(lines) > max_lines:
        raise ValueError(
            f"라벨 높이에 표시 가능한 DB 항목은 최대 {max_lines}개입니다. "
            f"현재 값이 있는 항목은 {len(lines)}개입니다. 템플릿에서 항목을 줄이거나 라벨 높이를 늘리세요."
        )
    return tuple(lines[:max_lines])


def _slcs_text_font(index: int) -> str:
    return "b" if index < 2 else "c"


def _slcs_text_command(
    x: int,
    y: int,
    text: str,
    index: int,
    layout: dict[str, object],
    *,
    use_vector_font: bool,
) -> str:
    requested_height = int(layout["text_font"])
    if use_vector_font:
        # SLCS manual 2-1-2: K selects KS5601 text and p4/p5 accept explicit
        # width/height in dots. This keeps 100 mm labels legible while the
        # existing bitmap fonts remain unchanged on compact labels.
        glyph_width = max(16, round(requested_height * 0.62))
        return f"V{x},{y},K,{glyph_width},{requested_height},0,N,N,N,0,L,0,'{text}'\n"
    return f"T{x},{y},{_slcs_text_font(index)},1,1,0,0,N,N,'{text}'\n"


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


def print_orientation_command(language: str, print_orientation: str) -> str:
    """Return the documented whole-label direction command for one language.

    ``normal`` deliberately preserves the legacy output direction used by this
    package. ``rotate_180`` selects the opposite device direction.
    """
    if print_orientation not in {"normal", "rotate_180"}:
        raise ValueError("print_orientation must be 'normal' or 'rotate_180'.")
    if language == "slcs":
        return "SOT\n" if print_orientation == "normal" else "SOB\n"
    if language == "tspl":
        return "DIRECTION 1\n" if print_orientation == "normal" else "DIRECTION 0\n"
    if language == "zpl":
        return "^PON\n" if print_orientation == "normal" else "^POI\n"
    raise ValueError("language must be 'slcs', 'tspl', or 'zpl'.")


def _zpl_media_handling_command(media_handling: str) -> str:
    _ensure_media_handling_supported("zpl", media_handling)
    if media_handling == "cutter":
        return "^MMC\n"
    if media_handling == "peeler":
        return "^MMP\n"
    return "^MMT\n"


def _zpl_media_type_command(media_type: str) -> str:
    if media_type == "gap":
        return "^MNY\n"
    if media_type == "black_mark":
        return "^MNM,0\n"
    if media_type == "continuous":
        return "^MNN\n"
    raise ValueError("media_type must be 'gap', 'black_mark', or 'continuous'.")


def _ensure_media_handling_supported(language: str, media_handling: str) -> None:
    supported = SUPPORTED_MEDIA_HANDLING_BY_LANGUAGE.get(language, {"tear_off"})
    if media_handling in supported:
        return
    if language == "slcs" and media_handling == "peeler":
        raise ValueError("BIXOLON/SLCS peeler command is not supported yet. Use tear_off or cutter.")
    raise ValueError(f"media_handling '{media_handling}' is not supported for {language}.")
