from __future__ import annotations

import io
import re
from types import SimpleNamespace

from dataclasses import replace
from pathlib import Path
from typing import TypeAlias

from PIL import Image, ImageDraw, ImageFont

from .barcode_catalog import BARCODE_1D_TYPES, GS1_TYPES, option_definitions
from .barcode_engine import render_barcode
from .config import BarcodeConfig, SUPPORTED_MEDIA_HANDLING_BY_LANGUAGE
from .excel_reader import LabelRow
from .sanitizer import sanitize_barcode, sanitize_slcs_text, sanitize_tspl_text, sanitize_zpl_text
from .printer_offsets import validate_offsets, slcs_media_commands, zebra_feed_command

CommandPayload: TypeAlias = str | bytes
ONE_D_BARCODE_TYPES = BARCODE_1D_TYPES
NATIVE_1D_TYPES = {"code128", "code39", "ean13", "ean8", "upca", "itf"}
_DEFAULT_GAP_OFFSET = object()


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
    *, gap_offset_mm: float | None = None, feed_offset_mm: float | None = None,
    bixolon_extended_stop: bool = False,
) -> CommandPayload:
    config = barcode_config or default_barcode_config(one_d_wide=6)
    if _needs_compact_auto(row, height_mm, config):
        return render_label('slcs', row, width_mm, height_mm, dpi, gap_mm, print_method, config,
                            print_speed=print_speed, print_density=print_density, media_handling=media_handling,
                            media_type=media_type, print_orientation=print_orientation,
                            gap_offset_mm=gap_offset_mm, feed_offset_mm=feed_offset_mm,
                            bixolon_extended_stop=bixolon_extended_stop)
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
    positioned_config = config if _graphics_required(barcode, config) else _auto_positioned_barcode_config("slcs", width_dot, height_dot, barcode, config, layout)
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

    barcode_command = _barcode_output("slcs", barcode, positioned_config, width_dot, height_dot, layout)
    header = (
        "CB\n"
        f"SS{speed}\n"
        f"SD{density}\n"
        "CS13,0\n"
        f"{_slcs_print_method_command(print_method)}"
        f"{_slcs_media_handling_command(media_handling)}"
        f"SW{width_dot}\n"
        f"{slcs_media_commands(height_dot, gap_dot, media_type, dpi, gap_offset_mm, feed_offset_mm, preserve_settings=media_handling == 'printer_default', extended_stop=bixolon_extended_stop)}"
        f"{print_orientation_command('slcs', print_orientation)}"
        f"{text_commands}"
    )
    if isinstance(barcode_command, bytes):
        return header.encode("cp949") + barcode_command + f"P{row.print_qty}\n".encode("ascii")
    return header + barcode_command + f"P{row.print_qty}\n"


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
    if _needs_compact_auto(row, height_mm, config):
        return render_label('tspl', row, width_mm, height_mm, dpi, gap_mm, print_method, config,
                            command_encoding, print_speed, print_density, media_handling, media_type, print_orientation)
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
    positioned_config = config if _graphics_required(barcode, config) else _auto_positioned_barcode_config("tspl", width_dot, height_dot, barcode, config, layout)
    barcode_command = _barcode_output("tspl", barcode, positioned_config, width_dot, height_dot, layout)
    if isinstance(barcode_command, str):
        barcode_command = barcode_command.encode("ascii")
    speed = 4 if print_speed is None else print_speed
    density = 8 if print_density is None else print_density
    header = (
        f"SIZE {width_mm:g} mm,{height_mm:g} mm\n"
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
    *, feed_offset_mm: float | None = None,
) -> CommandPayload:
    config = barcode_config or default_barcode_config(one_d_wide=2)
    if _needs_compact_auto(row, height_mm, config):
        return render_label('zpl', row, width_mm, height_mm, dpi, gap_mm, print_method, config,
                            command_encoding, print_speed, print_density, media_handling, media_type, print_orientation,
                            feed_offset_mm=feed_offset_mm)
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
    positioned_config = config if _graphics_required(barcode, config) else _auto_positioned_barcode_config("zpl", width_dot, height_dot, barcode, config, layout)
    text_commands = "".join(
        f"^FO{layout['margin_x']},{y}^FB{layout['text_width']},1,0,L,0^A0N,{layout['text_font']},{layout['text_font']}^FD{line}^FS\n"
        for line, y in zip(text_lines, layout["text_line_ys"], strict=False)
    )

    return (
        zebra_feed_command(dpi, feed_offset_mm)
        + "^XA\n"
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
        f"{_barcode_output('zpl', barcode, positioned_config, width_dot, height_dot, layout)}"
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
    *,
    offset_x_mm: float = 0,
    offset_y_mm: float = 0,
    gap_offset_mm: float | None | object = _DEFAULT_GAP_OFFSET,
    feed_offset_mm: float | None = None,
    bixolon_extended_stop: bool = False,
) -> CommandPayload:
    # Omitted arguments retain the historical vendor command. Explicit None
    # means inherit; explicit zero must remain available to reset the device.
    if gap_offset_mm is _DEFAULT_GAP_OFFSET:
        gap_offset_mm = 0 if language == "tspl" else None
    from .media_geometry import logical_size
    logical_height = logical_size(width_mm, height_mm, print_orientation)[1]
    compact = _needs_compact_auto(row, logical_height, barcode_config or default_barcode_config())
    if compact or print_orientation in {"landscape", "landscape_180"} or offset_x_mm or offset_y_mm:
        config = SimpleNamespace(
            label=SimpleNamespace(width_mm=width_mm, height_mm=height_mm, dpi=dpi, gap_mm=gap_mm,
                                  media_type=media_type, offset_x_mm=offset_x_mm, offset_y_mm=offset_y_mm,
                                  gap_offset_mm=gap_offset_mm, feed_offset_mm=feed_offset_mm,
                                  bixolon_extended_stop=bixolon_extended_stop),
            printer=SimpleNamespace(language=language, print_method=print_method,
                                    print_speed=print_speed, print_density=print_density,
                                    media_handling=media_handling, print_orientation=print_orientation,
                                    command_encoding=command_encoding))
        from .media_geometry import transform_image
        image = render_auto_page(row, width_mm, height_mm, dpi, barcode_config, print_orientation, language)
        return render_media_bitmap(transform_image(image, config), config, row.print_qty)
    validate_offsets(language, media_type, height_mm, dpi, gap_offset_mm, feed_offset_mm,
                     extended_stop=bixolon_extended_stop)
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
            gap_offset_mm=gap_offset_mm, feed_offset_mm=feed_offset_mm,
            bixolon_extended_stop=bixolon_extended_stop,
        )
    if language == "tspl":
        command = render_tspl(
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
        old_media = _tspl_media_type_command(gap_mm, media_type).encode("ascii")
        new_media = tspl_media_commands(gap_mm, media_type, gap_offset_mm, feed_offset_mm).encode("ascii")
        return command.replace(old_media, new_media, 1)
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
            feed_offset_mm=feed_offset_mm,
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
    legacy_width = _barcode_module_count(barcode_type, barcode) * max(1, config.one_d_narrow)
    actual_width = render_barcode(barcode_type, barcode, _encoder_settings(config)).width
    return max(legacy_width, actual_width)


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
    if media_handling == "printer_default":
        return ""
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


def tspl_media_commands(gap_mm, media_type, gap_offset_mm=None, feed_offset_mm=None):
    """None retains the device media/feed setup; zero explicitly sets no extra feed."""
    import math
    if media_type not in {"gap", "black_mark", "continuous"}:
        raise ValueError("지원하지 않는 용지 종류입니다.")
    if gap_offset_mm is not None and (
        isinstance(gap_offset_mm, bool) or not math.isfinite(float(gap_offset_mm)) or gap_offset_mm < 0
    ):
        raise ValueError("갭·블랙마크 추가 이송은 0 이상의 유한한 숫자여야 합니다.")
    if media_type == "continuous":
        if gap_offset_mm not in (None, 0):
            raise ValueError("연속 용지는 추가 이송을 사용할 수 없습니다.")
        command = "GAP 0,0\n" if gap_offset_mm is not None else ""
    elif gap_offset_mm is None:
        # TSPL couples the sensor type and extra-feed distance in one command.
        # Omitting it is the only way to preserve both device-side values.
        command = ""
    else:
        name = "BLINE" if media_type == "black_mark" else "GAP"
        extra_feed = float(gap_offset_mm)
        command = f"{name} {gap_mm:g} mm,{extra_feed:g} mm\n"
    if feed_offset_mm is not None:
        if (isinstance(feed_offset_mm, bool) or not math.isfinite(float(feed_offset_mm))
                or abs(float(feed_offset_mm)) > 25.4):
            raise ValueError("공급 오프셋은 -25.4~25.4mm 범위여야 합니다.")
        command += f"OFFSET {float(feed_offset_mm):g} mm\n"
    return command


def render_media_bitmap(image, config, print_qty):
    """Encode an already transformed physical page. Never rotate it again."""
    from .print_quantity import parse_print_quantity
    print_qty = parse_print_quantity(print_qty)
    p, label = config.printer, config.label
    width, height = mm_to_dots(label.width_mm, label.dpi), mm_to_dots(label.height_mm, label.dpi)
    if image.size != (width, height):
        raise ValueError("인쇄 이미지와 실제 용지 크기가 다릅니다.")
    _ensure_media_handling_supported(p.language, p.media_handling)
    validate_offsets(p.language, label.media_type, label.height_mm, label.dpi,
                     getattr(label, "gap_offset_mm", None), getattr(label, "feed_offset_mm", None),
                     brand=getattr(p, "brand", None), model=getattr(p, "model", ""),
                     extended_stop=getattr(label, "bixolon_extended_stop", False))
    image = image.convert("1", dither=Image.Dither.NONE)
    speed = p.print_speed if p.print_speed is not None else (3 if p.language == "slcs" else 4)
    density = p.print_density if p.print_density is not None else {"slcs": 20, "tspl": 8, "zpl": 10}.get(p.language, 8)
    if p.language == "tspl":
        media = tspl_media_commands(label.gap_mm, label.media_type,
                                    getattr(label, "gap_offset_mm", None), getattr(label, "feed_offset_mm", None))
        header = (f"SIZE {label.width_mm:g} mm,{label.height_mm:g} mm\n" + media
                  + _tspl_codepage_command(p.command_encoding)
                  + f"DENSITY {density}\nSPEED {speed}\n" + _tspl_print_method_command(p.print_method)
                  + "DIRECTION 1\nREFERENCE 0,0\nCLS\n")
        return (header.encode("ascii") + _tspl_bitmap_command(0, 0, image)
                + _tspl_media_handling_command(p.media_handling).encode("ascii")
                + f"PRINT 1,{print_qty}\n".encode("ascii"))
    if p.language == "slcs":
        header = (f"CB\nSS{speed}\nSD{density}\nCS13,0\n" + _slcs_print_method_command(p.print_method)
                  + _slcs_media_handling_command(p.media_handling) + f"SW{width}\n"
                  + slcs_media_commands(height, mm_to_dots(label.gap_mm, label.dpi), label.media_type,
                                        label.dpi, getattr(label, "gap_offset_mm", None),
                                        getattr(label, "feed_offset_mm", None),
                                        preserve_settings=p.media_handling == "printer_default",
                                        extended_stop=getattr(label, "bixolon_extended_stop", False)) + "SOT\n")
        data = io.BytesIO()
        image.save(data, format="BMP")
        return header.encode("ascii") + b"BMP0,0\r\n" + data.getvalue() + f"\r\nP{print_qty}\n".encode("ascii")
    if p.language == "zpl":
        width_bytes = (width + 7) // 8
        # Pillow packs white as 1; ZPL graphics pack black as 1.
        # Fill the byte-alignment columns with white before inversion. Pillow's
        # unused trailing bits are zero, which would otherwise become black ink.
        padded = Image.new("1", (width_bytes * 8, height), 1)
        padded.paste(image, (0, 0))
        payload = bytes(value ^ 255 for value in padded.tobytes())
        total = len(payload)
        header = (zebra_feed_command(label.dpi, getattr(label, "feed_offset_mm", None),
                                    brand=getattr(p, "brand", None), model=getattr(p, "model", ""))
                  + "^XA\n^CI28\n^PON\n" + _zpl_print_method_command(p.print_method)
                  + _zpl_media_handling_command(p.media_handling) + _zpl_media_type_command(label.media_type)
                  + f"^PR{speed}\n^MD{density}\n^PW{width}\n^LL{height}\n")
        return (header + f"^FO0,0^GFA,{total},{total},{width_bytes},{payload.hex().upper()}^FS\n"
                + f"^PQ{print_qty}\n^XZ\n").encode("ascii")
    raise ValueError("지원하지 않는 프린터 언어입니다.")


def render_auto_page(row, width_mm, height_mm, dpi, barcode_config=None, orientation="normal", language="tspl"):
    """Rasterize the ordinary DB label on the logical page before paper rotation."""
    from .media_geometry import logical_size
    config = barcode_config or default_barcode_config(one_d_wide=6 if language == "slcs" else 2)
    logical_width, logical_height = logical_size(width_mm, height_mm, orientation)
    if _needs_compact_auto(row, logical_height, config):
        from .compact_auto_layout import render_compact_page
        return render_compact_page(row, logical_width, logical_height, dpi, config, language)
    width, height = mm_to_dots(logical_width, dpi), mm_to_dots(logical_height, dpi)
    barcode = sanitize_barcode(row.barcode)
    lines = _display_text_lines(row, lambda text: text, _max_text_lines(logical_height))
    layout = _auto_label_layout(width, height, config, barcode, len(lines),
                               max_text_chars=max(map(len, lines), default=1),
                               large_label=logical_width >= 80 and logical_height >= 80)
    positioned = (_auto_positioned_barcode_config(language, width, height, barcode, config, layout)
                  if config.auto_layout else config)
    symbol = render_barcode(config.barcode_type, barcode, _encoder_settings(positioned)).convert("RGB")
    if config.barcode_type in ONE_D_BARCODE_TYPES and config.one_d_human_readable:
        display = barcode
        if config.barcode_type in GS1_TYPES:
            from .gs1 import build_gs1, parse_gs1
            display = build_gs1(parse_gs1(barcode)).hri
        font = _fit_font(display, symbol.width, max(14, layout["text_font"] // 2))
        box = font.getbbox(display)
        hri_height = box[3] - box[1] + 6
        combined = Image.new("RGB", (symbol.width, symbol.height + hri_height), "white")
        combined.paste(symbol, (0, 0))
        ImageDraw.Draw(combined).text(((symbol.width - (box[2] - box[0])) // 2 - box[0], symbol.height + 3 - box[1]),
                                     display, font=font, fill="black")
        symbol = combined
    if positioned.rotation not in {0, 90, 180, 270}:
        raise ValueError("바코드 회전은 0, 90, 180, 270도여야 합니다.")
    if positioned.rotation:
        symbol = symbol.rotate(-positioned.rotation, expand=True)
    x = (width - symbol.width) // 2 if config.auto_layout else positioned.x
    y = layout["barcode_y"] if config.auto_layout else positioned.y
    if x < 0 or y < 0 or x + symbol.width > width or y + symbol.height > height:
        raise ValueError("바코드가 라벨 영역을 넘습니다. 라벨 또는 모듈 크기를 확인하세요.")
    page = Image.new("RGB", (width, height), "white")
    page.paste(symbol, (x, y))
    page.info["protected_bounds"] = [(x, y, symbol.width, symbol.height)]
    draw = ImageDraw.Draw(page)
    for text, y in zip(lines, layout["text_line_ys"]):
        font = _fit_font(text, layout["text_width"], layout["text_font"])
        box = draw.textbbox((0, 0), text, font=font)
        if layout["margin_x"] + box[2] - box[0] > width or y + box[3] - box[1] > height:
            raise ValueError("문자가 라벨 영역을 넘습니다. 용지 크기를 확인하세요.")
        draw.text((layout["margin_x"] - box[0], y - box[1]), text, font=font, fill="black")
    return page


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


def _needs_compact_auto(row, height_mm, config):
    return config.auto_layout and bool(row.source_fields) and len(_display_text_lines(row, lambda text: text, None)) > _max_text_lines(height_mm)


def _display_text_lines(row: LabelRow, sanitize_text, max_lines: int | None = 4) -> tuple[str, ...]:
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
    if max_lines is not None and reject_overflow and len(lines) > max_lines:
        raise ValueError(
            f"라벨 높이에 표시 가능한 DB 항목은 최대 {max_lines}개입니다. "
            f"현재 값이 있는 항목은 {len(lines)}개입니다. 템플릿에서 항목을 줄이거나 라벨 높이를 늘리세요."
        )
    return tuple(lines if max_lines is None else lines[:max_lines])


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


def _graphics_required(value: str, config: BarcodeConfig) -> bool:
    return (config.barcode_type not in NATIVE_1D_TYPES or bool(config.encoder_options)
            or not re.fullmatch(r"[A-Za-z0-9 ._/$+%:-]+", value))


def _encoder_settings(config: BarcodeConfig) -> dict[str, object]:
    definitions = option_definitions(config.barcode_type)
    if config.barcode_type in {"qr", "gs1_qr", "hibcqr"} and config.qr_model != 2:
        raise ValueError("공통 QR 출력 엔진은 모델 2를 지원합니다. QR 모델 2로 설정하세요.")
    options: dict[str, object] = {}
    if config.barcode_type in ONE_D_BARCODE_TYPES:
        options["module_width"] = config.one_d_narrow
        options["bar_height"] = max(1, config.one_d_height // max(1, config.one_d_narrow))
    elif config.barcode_type in {"qr", "gs1_qr", "microqr", "rmqr", "hibcqr"}:
        options.update(cell_size=config.qr_cell_size, qr_ecc=config.qr_ecc)
    elif config.barcode_type in {"datamatrix", "gs1_datamatrix", "hibcdatamatrix"}:
        options["cell_size"] = config.datamatrix_cell_size
    elif config.barcode_type in {"pdf417", "compactpdf417", "hibcpdf417"}:
        options.update(cell_size=config.pdf417_module_width, pdf417_rows=config.pdf417_rows,
                       pdf417_columns=config.pdf417_columns, pdf417_security=config.pdf417_security_level,
                       pdf417_module_height=config.pdf417_module_height / max(1, config.pdf417_module_width))
    else:
        options["cell_size"] = 2
    options = {key: value for key, value in options.items() if key in definitions}
    options.update(config.encoder_options)
    return options


def _barcode_output(language: str, value: str, config: BarcodeConfig, width: int, height: int,
                    layout: dict[str, int]) -> CommandPayload:
    if not _graphics_required(value, config):
        # Validate actual symbology semantics before emitting any device command.
        probe = render_barcode(config.barcode_type, value, _encoder_settings(config))
        object_width, object_height = probe.size
        object_width = max(object_width, _estimated_1d_width(config.barcode_type, value, config))
        if config.rotation in {90, 270}:
            object_width, object_height = object_height, object_width
        if config.x < 0 or config.y < 0 or config.x + object_width > width or config.y + object_height > height:
            raise ValueError("바코드가 라벨 영역을 넘습니다. 라벨 또는 모듈 크기를 확인하세요.")
        return {"slcs": _render_slcs_barcode, "tspl": _render_tspl_barcode, "zpl": _render_zpl_barcode}[language](value, config)
    options = _encoder_settings(config)
    image = render_barcode(config.barcode_type, value, options).convert("1")
    if config.barcode_type in ONE_D_BARCODE_TYPES:
        if bool(options.get("human_readable", config.one_d_human_readable)):
            display_value = value
            if config.barcode_type in GS1_TYPES:
                from .gs1 import build_gs1, parse_gs1
                display_value = build_gs1(parse_gs1(value)).hri
            font = _load_label_font(16)
            hri = Image.new("1", (image.width, image.height + 24), 1)
            hri.paste(image, (0, 0))
            draw = ImageDraw.Draw(hri)
            box = draw.textbbox((0, 0), display_value, font=font)
            if box[2] - box[0] > image.width:
                raise ValueError("표시문자가 바코드 폭을 넘습니다. 모듈 크기를 키우거나 표시문자를 끄세요.")
            draw.text(((image.width - box[2] + box[0]) // 2, image.height + 3), display_value, fill=0, font=font)
            image = hri
    if config.rotation not in {0, 90, 180, 270}:
        raise ValueError("바코드 회전은 0, 90, 180, 270도여야 합니다.")
    if config.rotation:
        image = image.rotate(-config.rotation, expand=True)
    x = (width - image.width) // 2 if config.auto_layout else config.x
    y = layout["barcode_y"] if config.auto_layout else config.y
    if x < 0 or y < 0 or x + image.width > width or y + image.height > height:
        raise ValueError(f"바코드가 라벨 영역을 넘습니다 ({image.width}×{image.height}도트). 라벨을 키우거나 모듈/행/열 설정을 줄이세요.")
    if language == "tspl":
        return _tspl_bitmap_command(x, y, image)
    if language == "slcs":
        data = io.BytesIO()
        image.save(data, format="BMP")
        return f"BMP{x},{y}\r\n".encode("ascii") + data.getvalue() + b"\r\n"
    width_bytes = (image.width + 7) // 8
    payload = bytearray()
    pixels = image.load()
    for row in range(image.height):
        for offset in range(width_bytes):
            packed = 0
            for bit in range(8):
                col = offset * 8 + bit
                if col < image.width and pixels[col, row] == 0:
                    packed |= 0x80 >> bit
            payload.append(packed)
    total = len(payload)
    return f"^FO{x},{y}^GFA,{total},{total},{width_bytes},{payload.hex().upper()}^FS\n"
