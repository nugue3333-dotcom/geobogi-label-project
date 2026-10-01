from __future__ import annotations

import argparse
import copy
import hashlib
import io
import math
import os
import re
import shutil
from configparser import ConfigParser
import json
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import winreg
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from tkinter import filedialog, messagebox, simpledialog, ttk
from uuid import uuid4

import qrcode
import zxingcpp
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps, ImageTk

from .brand_assets import apply_window_icon, load_header_logo
from .file_association import ensure_label_file_association
from .config import DEFAULTS
from .config import SUPPORTED_BARCODE_TYPES as PRINT_SUPPORTED_BARCODE_TYPES
from .config import SUPPORTED_MEDIA_HANDLING_BY_LANGUAGE
from .config import load_config
from .data_store import DB_HEADERS, LABEL_HEADERS, canonical_db_field, load_db_rows, load_db_source
from .printers.network import send_raw as send_network_raw
from .printers.windows_raw import send_raw as send_windows_raw
from .print_progress import (
    DESIGNER_PROGRESS_FILE_NAME,
    NewPrintJobRequired,
    PrintProgress,
)
from .portable_project import PROJECT_EXTENSION, export_portable_project, import_portable_project
from .runtime_paths import executable_dir, runtime_base_dir
from .sanitizer import sanitize_barcode, sanitize_slcs_text
from .templates import mm_to_dots, print_orientation_command
from .ui_tokens import COLORS, SPACING, TYPOGRAPHY
from .font_assets import APP_FONT_FAMILY, bundled_font_path
from .ui_window import set_initial_window_size


FIELDS = ("item_code", "item_name", "barcode", "lot_no", "qty", "print_qty")
FIELD_LABELS = {
    "item_code": "품목 코드",
    "item_name": "품목명",
    "barcode": "바코드",
    "lot_no": "LOT 번호",
    "qty": "수량",
    "print_qty": "출력 매수",
}
ELEMENT_TYPES = {
    "text": "텍스트",
    "field": "텍스트",
    "multiline_text": "여러줄 텍스트",
    "barcode": "1D 바코드",
    "qr": "QR",
    "box": "박스",
    "line": "선",
    "table": "표",
    "image": "그림",
}
ALIGNMENTS = {"left": "왼쪽", "center": "가운데", "right": "오른쪽"}
ARRANGE_MODES = {"normal": "일반", "front": "글 앞으로", "behind": "글 뒤로", "through": "어울림"}
ELEMENT_ROTATION_LABELS = {
    0: "0도 (기본)",
    90: "90도 시계 방향",
    180: "180도",
    270: "270도 시계 방향",
}
ELEMENT_ROTATION_VALUES = {label: value for value, label in ELEMENT_ROTATION_LABELS.items()}
VISIBLE_ELEMENT_TYPE_KEYS = ("text", "multiline_text", "barcode", "qr", "image", "box", "line", "table")
TEXT_ELEMENT_TYPES = {"text", "field", "multiline_text"}
DB_MAPPABLE_ELEMENT_TYPES = TEXT_ELEMENT_TYPES | {"barcode", "qr"}
BARCODE_TYPES = {
    "code128": "Code 128",
    "gs1_128": "GS1-128",
    "code39": "Code 39",
    "codabar": "Codabar",
    "ean13": "EAN-13",
    "ean8": "EAN-8",
    "upca": "UPC-A",
    "itf": "ITF",
    "pharmacode": "Pharmacode",
    "qr": "QR",
    "microqr": "Micro QR",
    "datamatrix": "DataMatrix",
    "pdf417": "PDF417",
    "micropdf417": "MicroPDF417",
    "aztec": "Aztec",
    "maxicode": "MaxiCode",
}
BARCODE_2D_TYPES = {"qr", "microqr", "datamatrix", "pdf417", "micropdf417", "aztec", "maxicode"}
BARCODE_2D_BITMAP_TYPES = {"qr", "microqr", "datamatrix", "pdf417", "micropdf417", "aztec", "maxicode"}
BARCODE_1D_BITMAP_TYPES = {"code128", "gs1_128", "code39", "ean13", "ean8", "upca", "itf", "codabar", "pharmacode"}
DESIGNER_PRINT_SUPPORTED_BARCODE_TYPES = BARCODE_1D_BITMAP_TYPES | BARCODE_2D_BITMAP_TYPES
BARCODE_CHECK_DIGIT_LABELS = {"auto": "자동", "on": "사용", "off": "미사용"}
BARCODE_CHECK_DIGIT_VALUES = {label: key for key, label in BARCODE_CHECK_DIGIT_LABELS.items()}
QR_ERROR_CORRECTION = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
}
ZXING_2D_FORMATS = {
    "microqr": zxingcpp.BarcodeFormat.MicroQRCode,
    "datamatrix": zxingcpp.BarcodeFormat.DataMatrix,
    "pdf417": zxingcpp.BarcodeFormat.PDF417,
    "micropdf417": zxingcpp.BarcodeFormat.MicroPDF417,
    "aztec": zxingcpp.BarcodeFormat.Aztec,
    "maxicode": zxingcpp.BarcodeFormat.MaxiCode,
}
BARCODE_OPTION_DEFAULTS = {
    "module_width": 0,
    "wide_ratio": 2.5,
    "quiet_zone": 10,
    "human_readable": True,
    "check_digit": "auto",
    "cell_size": 0,
    "qr_ecc": "M",
    "pdf417_rows": 0,
    "pdf417_columns": 0,
    "pdf417_security": 2,
}
RESIZE_HANDLES = ("nw", "ne", "sw", "se")
HANDLE_SIZE = 7
MIN_ELEMENT_MM = 1.0
DESIGNER_MAX_SCALE = 24.0
DESIGNER_LAYOUT_PADDING = 8.0
DESIGNER_BG = "#cbd6dc"
WORKBENCH_BORDER = "#9baeb7"
RULER_BG = "#f7fafc"
RULER_OUTLINE = "#8fa7bb"
RULER_TICK_COLOR = "#365168"
RULER_LABEL_COLOR = "#18334a"
RULER_SIZE = 32
GRID_COLOR = "#e8eef5"
LABEL_SHADOW_COLOR = "#7f95ab"
LABEL_SHADOW_OFFSET = 7.0
LABEL_SURFACE_COLOR = "#ffffff"
LABEL_OUTLINE_COLOR = "#26394a"
LABEL_CORNER_RADIUS = 3.0
ELEMENT_GUIDE_COLOR = "#9aa9b7"
SELECT_COLOR = COLORS.accent
DEFAULT_FONT_NAME = APP_FONT_FAMILY
LABEL_FILE_EXTENSION = ".gblabel"
LABEL_FILE_TYPES = [
    ("채움랩 라벨 파일", f"*{LABEL_FILE_EXTENSION}"),
    ("라벨 템플릿 JSON", "*.json"),
]
IMAGE_FILE_TYPES = [
    ("Photoshop/사진 파일", "*.psd *.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp"),
    ("Photoshop", "*.psd"),
    ("사진 파일", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp"),
    ("모든 파일", "*.*"),
]
DESIGN_REFERENCE_ROLE = "design_reference"
DESIGN_TEXT_PLACEHOLDER = "텍스트"
OCR_ENGINE_DIR = Path("tools") / "ocr"
OCR_TESSERACT_ENV_VARS = ("GEBOGI_TESSERACT_EXE", "TESSERACT_EXE")
BARCODE_FALLBACK_VALUE = "12345678"
BARCODE_VALUE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
TEMPLATE_FIELD_RE = re.compile(r"\{\{([^{}]+)\}\}")
PRINTER_SETTINGS_EXE_NAMES = ("프린터설정.exe",)
DEFAULT_LABEL_WIDTH_MM = 50
DEFAULT_LABEL_HEIGHT_MM = 40
STROKE_ELEMENT_TYPES = {"box", "line", "table"}
DEFAULT_STROKE_WIDTH_MM = 0.3
MIN_STROKE_WIDTH_MM = 0.1
MAX_STROKE_WIDTH_MM = 5.0
TABLE_DIVIDER_HIT_PX = 7
TABLE_MIN_CELL_MM = 2.0
RIBBON_REFERENCE_TABLE_TEXT = (
    ("제조사", "WAX(왁스리본)", "Wax Resin(왁스레진)", "RESIN(레진리본)", "Super Ressin(케어리본)", "Super Ressin(케어리본/공단용)"),
    ("SONY(소니리본)", "5408\nTR4085", "4065\nTR4065", "4070\nTR4075", "", ""),
    ("ITW", "6220", "B128\nB112", "B325\nB324", "D321", ""),
    ("RICHO(리코)", "", "B110A\nRFA, RRA", "B110C\nRRC", "D110A\nRRD", "AR401/TPC4"),
    ("GENERAL(제너럴)", "", "", "SD502", "", ""),
    ("AVERY(에이버리)", "", "AG2", "", "", ""),
    ("ARMOR(알모르)", "AWR8\nAWX(FH)", "APR6\nAG3\nAG2(APR600)-EDGE", "AXR7+\nAS1(AXR600)-EDGE", "APR9\n코어리본-EDGE", ""),
    ("DNP(디앤피)", "W-137", "M250", "R-300", "", ""),
    ("FUJI(후지)", "FTR", "TTM80 or TTM81\nFSR", "TM300", "", ""),
    ("유니온", "JT305R", "", "", "", ""),
    ("KORIM(코림)", "KR103", "KR203", "KR301", "", ""),
)

@dataclass(frozen=True)
class FontFace:
    path: Path
    index: int = 0
    variation: bytes | None = None


_FONT_REGISTRY_CACHE: dict[str, FontFace] | None = None
_CODE128_PATTERNS = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
)


def app_base_dir() -> Path:
    return runtime_base_dir(executable_dir())


def _designer_print_job_context(config: object) -> dict[str, object]:
    printer = getattr(config, "printer", None)
    mode = str(getattr(printer, "mode", "designer-test"))
    if mode == "network":
        target = f"{getattr(printer, 'ip', '')}:{getattr(printer, 'port', '')}"
    else:
        target = str(getattr(printer, "windows_printer_name", ""))
    return {
        "source": "designer",
        "mode": mode,
        "target": target,
        "language": str(getattr(printer, "language", "")),
        "encoding": str(getattr(printer, "command_encoding", "utf-8")),
    }


def _ask_unknown_resolution(parent: tk.Misc, item_index: int) -> str | None:
    dialog = tk.Toplevel(parent)
    dialog.title("출력 상태 확인")
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=(20, 18))
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text=f"{item_index}번 항목의 실제 출력 여부를 확인하세요.", style="Title.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w"
    )
    ttk.Label(
        frame,
        text="RAW 전송 오류만으로 물리 라벨 출력 여부를 알 수 없습니다. 프린터와 라벨을 직접 확인하세요.",
        style="Hint.TLabel",
        wraplength=480,
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 18))
    result: dict[str, str | None] = {"value": None}

    def finish(value: str | None) -> None:
        result["value"] = value
        dialog.destroy()

    ttk.Button(frame, text="출력됨", command=lambda: finish("sent"), style="Primary.TButton").grid(
        row=2, column=0, padx=(0, 8)
    )
    ttk.Button(frame, text="출력 안 됨", command=lambda: finish("pending"), style="Secondary.TButton").grid(
        row=2, column=1, padx=(0, 8)
    )
    ttk.Button(frame, text="취소", command=lambda: finish(None), style="Secondary.TButton").grid(row=2, column=2)
    dialog.protocol("WM_DELETE_WINDOW", lambda: finish(None))
    dialog.bind("<Escape>", lambda _event: finish(None))
    parent.wait_window(dialog)
    return result["value"]


def _resolve_unknown_items_for_explicit_print(progress: PrintProgress, parent: tk.Misc) -> bool:
    """Ask about uncertain physical output before allowing another send."""
    for item_index in list(progress.unknown_indexes):
        choice = _ask_unknown_resolution(parent, item_index)
        if choice is None:
            return False
        progress.resolve_unknown(item_index, was_printed=(choice == "sent"))
    return True


def pyinstaller_bundle_dir() -> Path | None:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if not bundle_dir:
        return None
    return Path(str(bundle_dir)).resolve()


def default_template(width_mm: int = DEFAULT_LABEL_WIDTH_MM, height_mm: int = DEFAULT_LABEL_HEIGHT_MM) -> dict[str, object]:
    return {
        "version": 1,
        "label": {"width_mm": width_mm, "height_mm": height_mm},
        "elements": [],
    }


def configured_label_size(config_path: str | Path) -> tuple[int, int]:
    try:
        config = load_config(config_path)
        return config.label.width_mm, config.label.height_mm
    except Exception:
        return DEFAULT_LABEL_WIDTH_MM, DEFAULT_LABEL_HEIGHT_MM


def default_template_from_config(config_path: str | Path) -> dict[str, object]:
    width_mm, height_mm = configured_label_size(config_path)
    return default_template(width_mm, height_mm)


def ensure_blank_default_template(template_path: str | Path, config_path: str | Path) -> tuple[dict[str, object], Path | None]:
    path = Path(template_path)
    recovery_path: Path | None = None
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            elements = existing.get("elements") if isinstance(existing, dict) else None
            needs_recovery = not isinstance(elements, list) or bool(elements)
        except (OSError, UnicodeError, json.JSONDecodeError):
            needs_recovery = True
        if needs_recovery:
            recovery_path = path.with_name(f"복구_기본템플릿_{uuid4().hex[:8]}.gblabel")
            shutil.copy2(path, recovery_path)

    template = default_template_from_config(config_path)
    _atomic_write_json(path, template)
    return template, recovery_path


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _template_signature(label: object, elements: object) -> str:
    return json.dumps({"label": label, "elements": elements}, ensure_ascii=False, sort_keys=True, default=str)


def _new_code_element_values(*, data_source_connected: bool) -> tuple[str, str]:
    if data_source_connected:
        return "{{barcode}}", "barcode"
    return BARCODE_FALLBACK_VALUE, ""


def _preview_code_value(value: str) -> str:
    return value.strip() or BARCODE_FALLBACK_VALUE


def apply_configured_label_size(template: dict[str, object], config_path: str | Path) -> dict[str, object]:
    normalized = normalize_template(template)
    width_mm, height_mm = configured_label_size(config_path)
    normalized["label"] = {"width_mm": width_mm, "height_mm": height_mm}
    return normalized


def _printer_settings_command(
    base_dir: Path,
    install_dir: Path,
    *,
    frozen: bool | None = None,
) -> list[str]:
    for directory in (install_dir, base_dir):
        for exe_name in PRINTER_SETTINGS_EXE_NAMES:
            candidate = directory / exe_name
            if candidate.exists():
                return [str(candidate)]
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if is_frozen:
        names = ", ".join(PRINTER_SETTINGS_EXE_NAMES)
        raise FileNotFoundError(f"{names} 파일을 찾을 수 없습니다.")
    return [sys.executable, "-m", "barcode_label_automation.settings_app", "--config", str(base_dir / "config.ini")]


def load_template_file(path: str | Path) -> dict[str, object]:
    return normalize_template(json.loads(Path(path).read_text(encoding="utf-8")))


def _element(
    element_type: str,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    field: str = "",
    font_size: int = 10,
    font_name: str = DEFAULT_FONT_NAME,
    align: str = "left",
    barcode_type: str | None = None,
) -> dict[str, object]:
    element = {
        "id": uuid4().hex,
        "type": element_type,
        "text": text,
        "field": field,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "font_size": font_size,
        "font_name": font_name,
        "align": align,
        "arrange": "behind" if element_type == "table" else "normal",
        "rotation": 0,
    }
    if element_type in {"barcode", "qr"}:
        element["barcode_type"] = barcode_type or ("qr" if element_type == "qr" else "code128")
        element["barcode_options"] = dict(BARCODE_OPTION_DEFAULTS)
    if element_type == "table":
        element["table_rows"] = 3
        element["table_cols"] = 3
        element["table_row_positions"] = _even_table_positions(3)
        element["table_col_positions"] = _even_table_positions(3)
    if element_type in STROKE_ELEMENT_TYPES:
        element["stroke_width"] = DEFAULT_STROKE_WIDTH_MM
    return element


def render_template_text(template_text: str, row: dict[str, str]) -> str:
    return TEMPLATE_FIELD_RE.sub(lambda match: str(row.get(match.group(1).strip(), "")), template_text)


def render_element_text(element: dict[str, object], row: dict[str, str]) -> str:
    template_text = str(element.get("text", ""))
    field = str(element.get("field", "")).strip()
    if not template_text and field:
        template_text = "{{" + field + "}}"
    return render_template_text(template_text, row)


def _designer_code_value(element: dict[str, object], row: dict[str, str]) -> str:
    template_text = str(element.get("text", ""))
    field = str(element.get("field", "")).strip()
    if template_text or field:
        value = render_element_text(element, row)
    else:
        value = str(row.get("barcode", ""))
    if not value.strip():
        code_type = "QR" if str(element.get("type")) == "qr" else "바코드"
        raise ValueError(f"{code_type} 값이 비어 있습니다. 템플릿의 DB 연결과 선택 데이터를 확인하세요.")
    return value


def _db_headers_from_rows(rows: list[dict[str, str]]) -> tuple[str, ...]:
    headers: list[str] = []
    for row in rows:
        for header in row:
            normalized = str(header).strip()
            if normalized and normalized not in headers:
                headers.append(normalized)
    return tuple(headers) if headers else tuple(DB_HEADERS)


def _preferred_text_db_field(rows: list[dict[str, str]], headers: tuple[str, ...] | None = None) -> str:
    if not rows:
        return ""
    source_headers = headers if headers is not None else _db_headers_from_rows(rows)

    def has_value(field: str) -> bool:
        return any(str(row.get(field, "")).strip() for row in rows)

    for preferred_field in ("item_name", "item_code", "lot_no", "qty"):
        for field in source_headers:
            if (canonical_db_field(field) or field) == preferred_field and has_value(field):
                return field
    for field in source_headers:
        if (canonical_db_field(field) or field) not in {"barcode", "print_qty"} and has_value(field):
            return field
    for field in source_headers:
        if (canonical_db_field(field) or field) == "barcode" and has_value(field):
            return field
    return ""


def _data_field_option_maps(headers: tuple[str, ...]) -> tuple[dict[str, str], dict[str, str]]:
    option_to_key = {"연결 안 함": ""}
    key_to_option = {"": "연결 안 함"}
    for field in headers:
        option = _db_field_option_label(field)
        option_to_key[option] = field
        key_to_option[field] = option
    return option_to_key, key_to_option


def _filter_data_source_row_indexes(
    rows: list[dict[str, str]],
    headers: tuple[str, ...],
    query: str,
) -> list[int]:
    """Return source row indexes whose values match the query in any DB column."""
    needle = " ".join(query.split()).casefold()
    if not needle:
        return list(range(len(rows)))
    return [
        index
        for index, row in enumerate(rows)
        if any(needle in " ".join(str(row.get(header, "")).split()).casefold() for header in headers)
    ]


def _db_field_option_label(field: str) -> str:
    label = FIELD_LABELS.get(field, field)
    return f"{label} ({field})" if label != field else field


def _element_type_from_label(label: str, fallback: str = "text") -> str:
    for key in VISIBLE_ELEMENT_TYPE_KEYS:
        if ELEMENT_TYPES[key] == label:
            return key
    return fallback


def _normalize_label_mm(value: object, fallback: float) -> int | float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(fallback)
    if not math.isfinite(number) or number <= 0:
        number = float(fallback)
    if not math.isfinite(number) or number <= 0:
        number = 1.0
    number = round(number, 1)
    return int(number) if number.is_integer() else number


def _calculate_canvas_label_layout(
    canvas_width: int | float,
    canvas_height: int | float,
    label_width_mm: int | float,
    label_height_mm: int | float,
) -> tuple[float, float, float, float, float]:
    """Return scale, origin and pixel size that keep the label shadow visible."""
    width_mm = float(label_width_mm)
    height_mm = float(label_height_mm)
    if not math.isfinite(width_mm) or not math.isfinite(height_mm) or width_mm <= 0 or height_mm <= 0:
        raise ValueError("라벨 크기는 유한한 양수여야 합니다.")

    width_px = max(1.0, float(canvas_width))
    height_px = max(1.0, float(canvas_height))

    def axis_space(size: float) -> tuple[float, float]:
        padding = min(
            DESIGNER_LAYOUT_PADDING,
            max(0.0, (size - LABEL_SHADOW_OFFSET - 1.0) / 3.0),
        )
        trailing = min(max(0.0, size - 1.0), LABEL_SHADOW_OFFSET + padding)
        leading = min(RULER_SIZE + padding, max(0.0, size - trailing - 1.0))
        return leading, max(0.01, size - leading - trailing)

    left, available_width = axis_space(width_px)
    top, available_height = axis_space(height_px)
    scale = min(
        DESIGNER_MAX_SCALE,
        available_width / width_mm,
        available_height / height_mm,
    )
    label_width_px = width_mm * scale
    label_height_px = height_mm * scale
    origin_x = left + max(0.0, (available_width - label_width_px) / 2.0)
    origin_y = top + max(0.0, (available_height - label_height_px) / 2.0)
    return scale, origin_x, origin_y, label_width_px, label_height_px


def normalize_template(template: dict[str, object]) -> dict[str, object]:
    label = template.get("label") if isinstance(template.get("label"), dict) else {}
    width_mm = _normalize_label_mm(label.get("width_mm", DEFAULT_LABEL_WIDTH_MM), DEFAULT_LABEL_WIDTH_MM)  # type: ignore[union-attr]
    height_mm = _normalize_label_mm(label.get("height_mm", DEFAULT_LABEL_HEIGHT_MM), DEFAULT_LABEL_HEIGHT_MM)  # type: ignore[union-attr]
    elements = template.get("elements") if isinstance(template.get("elements"), list) else []
    normalized = default_template(width_mm, height_mm)
    normalized["elements"] = [_normalize_element(element) for element in elements if isinstance(element, dict)]
    return normalized


def _normalize_element(element: dict[str, object]) -> dict[str, object]:
    element_type = str(element.get("type", "text"))
    if element_type not in ELEMENT_TYPES:
        element_type = "text"
    align = str(element.get("align", "left"))
    if align not in ALIGNMENTS:
        align = "left"
    normalized = {
        "id": str(element.get("id") or uuid4().hex),
        "type": element_type,
        "text": str(element.get("text", "")),
        "field": str(element.get("field", "")),
        "x": _float_value(element.get("x"), 5),
        "y": _float_value(element.get("y"), 5),
        "width": max(1.0, _float_value(element.get("width"), 20)),
        "height": max(1.0, _float_value(element.get("height"), 5)),
        "font_size": max(6, min(48, int(_float_value(element.get("font_size"), 10)))),
        "font_name": str(element.get("font_name") or DEFAULT_FONT_NAME),
        "align": align,
        "reverse": bool(element.get("reverse", False)),
        "rotation": _element_rotation(element),
        "locked": bool(element.get("locked", False)),
    }
    if element.get("group_id"):
        normalized["group_id"] = str(element["group_id"])
    if element_type in TEXT_ELEMENT_TYPES:
        normalized["fit_text_to_box"] = bool(element.get("fit_text_to_box", True))
        normalized["required"] = bool(element.get("required", False))
    if element_type in TEXT_ELEMENT_TYPES | {"barcode", "qr"} and element.get("review_source"):
        normalized["review_source"] = str(element["review_source"])
        normalized["review_confirmed"] = bool(element.get("review_confirmed", False))
        if element.get("review_image_path"):
            normalized["review_image_path"] = str(element["review_image_path"])
    arrange = str(element.get("arrange") or ("behind" if element_type == "table" else "normal"))
    normalized["arrange"] = arrange if arrange in ARRANGE_MODES else ("behind" if element_type == "table" else "normal")
    if element_type in {"barcode", "qr"}:
        barcode_type = str(element.get("barcode_type") or ("qr" if element_type == "qr" else "code128"))
        if barcode_type not in BARCODE_TYPES:
            barcode_type = "qr" if element_type == "qr" else "code128"
        normalized["barcode_type"] = barcode_type
        normalized["barcode_options"] = _normalize_barcode_options(element.get("barcode_options"))
    if element_type == "table":
        normalized["table_rows"] = max(1, min(20, int(_float_value(element.get("table_rows"), 3))))
        normalized["table_cols"] = max(1, min(20, int(_float_value(element.get("table_cols"), 3))))
        normalized["table_row_positions"] = _normalize_table_axis_positions(element.get("table_row_positions"), normalized["table_rows"])
        normalized["table_col_positions"] = _normalize_table_axis_positions(element.get("table_col_positions"), normalized["table_cols"])
    if element_type in STROKE_ELEMENT_TYPES:
        normalized["stroke_width"] = _normalize_stroke_width(element.get("stroke_width"))
    if element_type == "image":
        normalized["image_path"] = str(element.get("image_path", ""))
        image_fit = str(element.get("image_fit") or "contain")
        normalized["image_fit"] = image_fit if image_fit in {"contain", "stretch"} else "contain"
        normalized["printable"] = bool(element.get("printable", True))
        if element.get("template_role"):
            normalized["template_role"] = str(element.get("template_role"))
        if element.get("source_path"):
            normalized["source_path"] = str(element.get("source_path"))
        if "analysis_applied" in element:
            normalized["analysis_applied"] = bool(element.get("analysis_applied", False))
    return normalized


def _open_design_image(path: str | Path) -> Image.Image:
    with Path(path).open("rb") as source:
        header = source.read(128)
    if b"Bar Tender Format File" in header:
        raise ValueError(
            "이 파일은 PNG 이미지가 아니라 BarTender 도안(.btw)입니다. "
            "확장자를 바꿔도 이미지로 변환되지 않습니다. 원본 프로그램에서 열어 "
            "실제 이미지로 내보내거나 인쇄 미리보기를 저장해야 합니다."
        )
    with Image.open(path) as opened:
        try:
            opened.seek(0)
        except EOFError:
            pass
        image = ImageOps.exif_transpose(opened)
        return image.convert("RGBA").copy()


def _design_image_on_white(image: Image.Image) -> Image.Image:
    """Analyze transparent exports as ink on a white label, preserving their size."""
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, "white")
    return Image.alpha_composite(background, rgba).convert("RGB")


def _save_design_image_asset(source_path: Path, image_dir: Path) -> tuple[Path, tuple[int, int]]:
    image_dir.mkdir(parents=True, exist_ok=True)
    image = _open_design_image(source_path)
    safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
    target = image_dir / f"{uuid4().hex[:8]}_{safe_stem or 'image'}.png"
    image.save(target, format="PNG")
    return target, image.size


def _fit_image_mm_size(image_size: tuple[int, int], max_width_mm: float, max_height_mm: float) -> tuple[float, float]:
    image_width, image_height = image_size
    if image_width <= 0 or image_height <= 0:
        return max(1.0, max_width_mm), max(1.0, max_height_mm)
    ratio = image_width / image_height
    box_ratio = max_width_mm / max_height_mm if max_height_mm else ratio
    if ratio >= box_ratio:
        width = max_width_mm
        height = width / ratio
    else:
        height = max_height_mm
        width = height * ratio
    return round(max(1.0, width), 1), round(max(1.0, height), 1)


def _format_mm_value(value: object) -> str:
    number = _float_value(value, DEFAULT_LABEL_WIDTH_MM)
    return f"{number:g}"


def _image_element_for_label(
    image_path: str,
    name: str,
    label: dict[str, object],
    image_size: tuple[int, int],
    *,
    fit_to_label: bool,
    printable: bool = True,
) -> dict[str, object]:
    label_width = float(label.get("width_mm", DEFAULT_LABEL_WIDTH_MM))
    label_height = float(label.get("height_mm", DEFAULT_LABEL_HEIGHT_MM))
    if fit_to_label:
        element = _element("image", name, 0, 0, label_width, label_height, align="center")
        element["arrange"] = "behind"
    else:
        max_w = max(8.0, label_width * 0.55)
        max_h = max(8.0, label_height * 0.45)
        box_w, box_h = _fit_image_mm_size(image_size, max_w, max_h)
        element = _element("image", name, 5, 5, box_w, box_h, align="center")
    element["image_path"] = image_path
    element["image_fit"] = "stretch" if fit_to_label else "contain"
    element["printable"] = printable
    return element


def _analysis_grayscale_image(image: Image.Image, max_side: int = 900) -> Image.Image:
    analysis = ImageOps.grayscale(image.convert("RGB"))
    if max(analysis.size) > max_side:
        scale = max_side / max(analysis.size)
        analysis = analysis.resize((max(1, round(analysis.width * scale)), max(1, round(analysis.height * scale))), Image.Resampling.BILINEAR)
    return analysis


def _image_content_box_mm(image_size: tuple[int, int], label: dict[str, object]) -> tuple[float, float, float, float]:
    label_width = float(label.get("width_mm", DEFAULT_LABEL_WIDTH_MM))
    label_height = float(label.get("height_mm", DEFAULT_LABEL_HEIGHT_MM))
    return 0.0, 0.0, label_width, label_height


def _pixel_box_to_label_mm(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
    label: dict[str, object],
    *,
    pad_mm: float = 0.0,
) -> tuple[float, float, float, float]:
    image_width, image_height = image_size
    label_width = float(label.get("width_mm", DEFAULT_LABEL_WIDTH_MM))
    label_height = float(label.get("height_mm", DEFAULT_LABEL_HEIGHT_MM))
    content_x, content_y, content_width, content_height = _image_content_box_mm(image_size, label)
    x1, y1, x2, y2 = box
    left = content_x + (x1 / max(1, image_width)) * content_width - pad_mm
    top = content_y + (y1 / max(1, image_height)) * content_height - pad_mm
    right = content_x + (x2 / max(1, image_width)) * content_width + pad_mm
    bottom = content_y + (y2 / max(1, image_height)) * content_height + pad_mm
    left = max(0.0, min(label_width, left))
    top = max(0.0, min(label_height, top))
    right = max(left + 1.0, min(label_width, right))
    bottom = max(top + 1.0, min(label_height, bottom))
    return round(left, 1), round(top, 1), round(right - left, 1), round(bottom - top, 1)


def _pixel_position_to_label_mm(
    x: int,
    y: int,
    image_size: tuple[int, int],
    label: dict[str, object],
) -> tuple[float, float]:
    image_width, image_height = image_size
    label_width = float(label.get("width_mm", DEFAULT_LABEL_WIDTH_MM))
    label_height = float(label.get("height_mm", DEFAULT_LABEL_HEIGHT_MM))
    content_x, content_y, content_width, content_height = _image_content_box_mm(image_size, label)
    x_mm = content_x + (x / max(1, image_width)) * content_width
    y_mm = content_y + (y / max(1, image_height)) * content_height
    return max(0.0, min(label_width, x_mm)), max(0.0, min(label_height, y_mm))


def _boxes_overlap(first: tuple[int, int, int, int], second: tuple[int, int, int, int], *, pad: int = 0) -> bool:
    return not (
        first[2] + pad <= second[0]
        or second[2] + pad <= first[0]
        or first[3] + pad <= second[1]
        or second[3] + pad <= first[1]
    )


def _scale_pixel_box(box: tuple[int, int, int, int], from_size: tuple[int, int], to_size: tuple[int, int]) -> tuple[int, int, int, int]:
    from_width, from_height = from_size
    to_width, to_height = to_size
    return (
        max(0, round(box[0] / max(1, from_width) * to_width)),
        max(0, round(box[1] / max(1, from_height) * to_height)),
        min(to_width, round(box[2] / max(1, from_width) * to_width)),
        min(to_height, round(box[3] / max(1, from_height) * to_height)),
    )


def _element_label_box(element: dict[str, object]) -> tuple[float, float, float, float]:
    x = float(element.get("x", 0))
    y = float(element.get("y", 0))
    width = float(element.get("width", 0))
    height = float(element.get("height", 0))
    return x, y, x + width, y + height


def _label_boxes_overlap(first: tuple[float, float, float, float], second: tuple[float, float, float, float], *, pad_mm: float = 0.0) -> bool:
    return not (
        first[2] + pad_mm <= second[0]
        or second[2] + pad_mm <= first[0]
        or first[3] + pad_mm <= second[1]
        or second[3] + pad_mm <= first[1]
    )


def _append_non_overlapping_elements(
    target: list[dict[str, object]],
    candidates: list[dict[str, object]],
    *,
    pad_mm: float = 0.2,
) -> None:
    for candidate in candidates:
        candidate_type = str(candidate.get("type", ""))
        candidate_box = _element_label_box(candidate)
        duplicate = False
        for existing_index, existing in enumerate(target):
            if str(existing.get("type", "")) != candidate_type:
                continue
            existing_box = _element_label_box(existing)
            if not _label_boxes_overlap(candidate_box, existing_box, pad_mm=pad_mm):
                continue
            if candidate_type in TEXT_ELEMENT_TYPES:
                candidate_center_y = (candidate_box[1] + candidate_box[3]) / 2
                existing_center_y = (existing_box[1] + existing_box[3]) / 2
                row_tolerance = max(0.8, min(candidate_box[3] - candidate_box[1], existing_box[3] - existing_box[1]) * 0.55)
                if abs(candidate_center_y - existing_center_y) > row_tolerance:
                    continue
                candidate_text = str(candidate.get("text", "")).strip()
                existing_text = str(existing.get("text", "")).strip()
                candidate_width = candidate_box[2] - candidate_box[0]
                existing_width = existing_box[2] - existing_box[0]
                same_text_family = (
                    candidate_text == existing_text
                    or (existing_text and existing_text in candidate_text)
                    or (candidate_text and candidate_text in existing_text)
                )
                if same_text_family and candidate_width > existing_width + 1.0:
                    target[existing_index] = candidate
            duplicate = True
            break
        if duplicate:
            continue
        target.append(candidate)


def _barcode_type_from_zxing_format(format_value: object) -> str:
    normalized = str(format_value).replace("_", " ").replace("-", " ").lower()
    if "micro" in normalized and "qr" in normalized:
        return "microqr"
    if "qr" in normalized:
        return "qr"
    if "data" in normalized and "matrix" in normalized:
        return "datamatrix"
    if "micro" in normalized and "pdf" in normalized:
        return "micropdf417"
    if "pdf" in normalized:
        return "pdf417"
    if "aztec" in normalized:
        return "aztec"
    if "maxi" in normalized:
        return "maxicode"
    if "39" in normalized:
        return "code39"
    if "13" in normalized and "ean" in normalized:
        return "ean13"
    if "8" in normalized and "ean" in normalized:
        return "ean8"
    if "upc" in normalized and "a" in normalized:
        return "upca"
    if "itf" in normalized or "interleaved" in normalized:
        return "itf"
    if "codabar" in normalized:
        return "codabar"
    return "code128"


def _zxing_position_box(result: object, image_size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    position = getattr(result, "position", None)
    if position is None:
        return None
    points = [getattr(position, name, None) for name in ("top_left", "top_right", "bottom_left", "bottom_right")]
    if any(point is None for point in points):
        return None
    xs = [int(getattr(point, "x", 0)) for point in points]
    ys = [int(getattr(point, "y", 0)) for point in points]
    width, height = image_size
    return (
        max(0, min(xs)),
        max(0, min(ys)),
        min(width, max(xs) + 1),
        min(height, max(ys) + 1),
    )


def _decoded_barcode_elements_from_image(
    image: Image.Image,
    label: dict[str, object],
    *,
    max_elements: int = 8,
) -> tuple[list[dict[str, object]], list[tuple[int, int, int, int]]]:
    try:
        decoded = zxingcpp.read_barcodes(image.convert("RGB"))
    except Exception:
        decoded = []
    elements: list[dict[str, object]] = []
    boxes: list[tuple[int, int, int, int]] = []
    for result in decoded:
        if len(elements) >= max_elements:
            break
        text = str(getattr(result, "text", "") or "").strip()
        if not text:
            continue
        box = _zxing_position_box(result, image.size)
        if box is None:
            continue
        if any(_boxes_overlap(box, existing, pad=3) for existing in boxes):
            continue
        x_mm, y_mm, w_mm, h_mm = _pixel_box_to_label_mm(box, image.size, label, pad_mm=0.8)
        barcode_type = _barcode_type_from_zxing_format(getattr(result, "format", ""))
        element = _element("barcode", text, x_mm, y_mm, w_mm, h_mm, font_size=8, align="center", barcode_type=barcode_type)
        elements.append(element)
        boxes.append(box)
    return elements, boxes


def _probable_1d_barcode_elements_from_analysis(
    analysis: Image.Image,
    label: dict[str, object],
    *,
    exclude_pixel_boxes: tuple[tuple[int, int, int, int], ...] = (),
    max_elements: int = 12,
) -> tuple[list[dict[str, object]], list[tuple[int, int, int, int]]]:
    width_px, height_px = analysis.size
    pixels = analysis.load()
    threshold = 160
    rows: list[tuple[int, int, int]] = []
    for y in range(height_px):
        dark_positions: list[int] = []
        previous_dark = False
        transitions = 0
        for x in range(width_px):
            is_dark = pixels[x, y] <= threshold
            if x > 0 and is_dark != previous_dark:
                transitions += 1
            previous_dark = is_dark
            if is_dark:
                dark_positions.append(x)
        if not dark_positions:
            continue
        x1, x2 = min(dark_positions), max(dark_positions) + 1
        span = x2 - x1
        if span < width_px * 0.15:
            continue
        dark_ratio = len(dark_positions) / max(1, span)
        if 0.06 <= dark_ratio <= 0.88 and transitions >= max(12, round(span * 0.04)):
            rows.append((y, x1, x2))
    boxes: list[tuple[int, int, int, int]] = []
    if rows:
        group_start, span_start, span_end = rows[0]
        previous = group_start
        for y, row_start, row_end in rows[1:]:
            if y <= previous + 1:
                previous = y
                span_start = min(span_start, row_start)
                span_end = max(span_end, row_end)
                continue
            boxes.append((span_start, group_start, span_end, previous + 1))
            group_start = previous = y
            span_start = row_start
            span_end = row_end
        boxes.append((span_start, group_start, span_end, previous + 1))

    elements: list[dict[str, object]] = []
    accepted_boxes: list[tuple[int, int, int, int]] = []
    for row_box in boxes:
        for box in _barcode_column_boxes(row_box, pixels, analysis.size, threshold=threshold):
            if len(elements) >= max_elements:
                break
            if any(_boxes_overlap(box, excluded, pad=4) for excluded in exclude_pixel_boxes):
                continue
            if any(_boxes_overlap(box, accepted, pad=4) for accepted in accepted_boxes):
                continue
            x_mm, y_mm, w_mm, h_mm = _pixel_box_to_label_mm(box, analysis.size, label, pad_mm=0.5)
            element = _element("barcode", BARCODE_FALLBACK_VALUE, x_mm, y_mm, w_mm, h_mm, font_size=8, align="center", barcode_type="code128")
            _barcode_options(element)["human_readable"] = False
            elements.append(element)
            accepted_boxes.append(box)
        if len(elements) >= max_elements:
            break
    return elements, accepted_boxes


def _barcode_column_boxes(
    row_box: tuple[int, int, int, int],
    pixels: object,
    image_size: tuple[int, int],
    *,
    threshold: int,
) -> list[tuple[int, int, int, int]]:
    width_px, height_px = image_size
    x1, y1, x2, y2 = row_box
    row_height = max(1, y2 - y1)
    if row_height < max(2, round(height_px * 0.006)):
        return []

    strong_columns: list[int] = []
    for x in range(max(0, x1), min(width_px, x2)):
        column_dark = sum(1 for y in range(y1, y2) if pixels[x, y] <= threshold)
        if column_dark >= row_height * 0.65:
            strong_columns.append(x)
    if not strong_columns:
        return []

    raw_runs = _merge_positions_to_ranges(strong_columns, max_gap=max(4, round(row_height * 0.25)))
    raw_runs = [run for run in raw_runs if run[1] - run[0] >= max(5, round(row_height * 0.3))]
    raw_runs = [
        run
        for run in raw_runs
        if not ((run[0] <= 2 or run[1] >= width_px - 2) and run[1] - run[0] < max(12, row_height))
    ]
    runs = _merge_ranges(raw_runs, max_gap=max(10, round(width_px * 0.045)))
    boxes: list[tuple[int, int, int, int]] = []
    for run_start, run_end in runs:
        box = (
            max(0, run_start - 2),
            max(0, y1 - 1),
            min(width_px, run_end + 2),
            min(height_px, y2 + 1),
        )
        if _looks_like_1d_barcode_box(box, pixels, image_size, threshold=threshold):
            boxes.append(box)
    return boxes


def _merge_positions_to_ranges(positions: list[int], *, max_gap: int) -> list[tuple[int, int]]:
    if not positions:
        return []
    ranges: list[tuple[int, int]] = []
    start = previous = positions[0]
    for position in positions[1:]:
        if position <= previous + max_gap:
            previous = position
            continue
        ranges.append((start, previous + 1))
        start = previous = position
    ranges.append((start, previous + 1))
    return ranges


def _merge_ranges(ranges: list[tuple[int, int]], *, max_gap: int) -> list[tuple[int, int]]:
    if not ranges:
        return []
    merged: list[tuple[int, int]] = []
    start, end = ranges[0]
    for range_start, range_end in ranges[1:]:
        if range_start <= end + max_gap:
            end = max(end, range_end)
            continue
        merged.append((start, end))
        start, end = range_start, range_end
    merged.append((start, end))
    return merged


def _looks_like_1d_barcode_box(
    box: tuple[int, int, int, int],
    pixels: object,
    image_size: tuple[int, int],
    *,
    threshold: int,
) -> bool:
    width_px, height_px = image_size
    x1, y1, x2, y2 = box
    box_width = x2 - x1
    box_height = y2 - y1
    if box_width < max(28, round(width_px * 0.13)):
        return False
    if box_height < max(4, round(height_px * 0.012)):
        return False

    dark_pixels = 0
    transitions = 0
    strong_columns = 0
    for x in range(x1, x2):
        column_dark = 0
        previous_dark = False
        for y in range(y1, y2):
            is_dark = pixels[x, y] <= threshold
            if y > y1 and is_dark != previous_dark:
                transitions += 1
            previous_dark = is_dark
            if is_dark:
                dark_pixels += 1
                column_dark += 1
        if column_dark >= box_height * 0.65:
            strong_columns += 1
    area = max(1, box_width * box_height)
    dark_ratio = dark_pixels / area
    return 0.12 <= dark_ratio <= 0.88 and strong_columns >= box_width * 0.16 and transitions >= max(8, round(box_width * 0.035))


def _resolve_tesseract_executable(base_dir: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    for env_name in OCR_TESSERACT_ENV_VARS:
        raw_value = os.environ.get(env_name, "").strip()
        if raw_value:
            candidates.append(Path(raw_value))
    for root in [base_dir, executable_dir(), pyinstaller_bundle_dir()]:
        if root is None:
            continue
        candidates.extend(
            [
                root / OCR_ENGINE_DIR / "tesseract.exe",
                root / "tesseract" / "tesseract.exe",
            ]
        )
    path_value = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if path_value:
        candidates.append(Path(path_value))
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def _tesseract_data_dir(tesseract_exe: Path, base_dir: Path | None = None) -> Path | None:
    candidates = [
        tesseract_exe.parent / "tessdata",
        tesseract_exe.parent.parent / "tessdata",
    ]
    if base_dir is not None:
        candidates.append(base_dir / OCR_ENGINE_DIR / "tessdata")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _tesseract_language(tessdata_dir: Path | None) -> str:
    if tessdata_dir is None:
        return "kor+eng"
    has_kor = (tessdata_dir / "kor.traineddata").exists()
    has_eng = (tessdata_dir / "eng.traineddata").exists()
    if has_kor and has_eng:
        return "kor+eng"
    if has_kor:
        return "kor"
    if has_eng:
        return "eng"
    return "kor+eng"


def _prepare_ocr_image(image: Image.Image) -> Image.Image:
    prepared = ImageOps.grayscale(_design_image_on_white(image))
    if prepared.width < 900:
        scale = max(2, min(5, round(900 / max(1, prepared.width))))
        prepared = prepared.resize((prepared.width * scale, prepared.height * scale), Image.Resampling.LANCZOS)
    prepared = ImageOps.autocontrast(prepared)
    prepared = prepared.point(lambda value: 0 if value < 180 else 255)
    return prepared


def _ocr_temp_dir(base_dir: Path | None = None) -> Path | None:
    if base_dir is not None:
        candidate = base_dir / "tmp"
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            pass
    return None


def _clean_ocr_text(text: str) -> str | None:
    cleaned = " ".join(part.strip() for part in text.replace("\ufeff", "").split() if part.strip())
    return cleaned or None


def _run_tesseract_stdout(
    image: Image.Image,
    *,
    base_dir: Path | None,
    args: list[str],
    timeout_seconds: int = 12,
) -> tuple[str, tuple[int, int]] | None:
    tesseract_exe = _resolve_tesseract_executable(base_dir)
    if tesseract_exe is None:
        return None
    tessdata_dir = _tesseract_data_dir(tesseract_exe, base_dir)
    language = _tesseract_language(tessdata_dir)
    temp_path: Path | None = None
    prepared = _prepare_ocr_image(image)
    try:
        with tempfile.NamedTemporaryFile(prefix="geobogi_ocr_", suffix=".png", delete=False, dir=_ocr_temp_dir(base_dir)) as temp_file:
            temp_path = Path(temp_file.name)
        prepared.save(temp_path, format="PNG")
        env = dict(os.environ)
        if tessdata_dir is not None:
            env["TESSDATA_PREFIX"] = str(tessdata_dir)
        command = [str(tesseract_exe), str(temp_path), "stdout", "-l", language]
        if tessdata_dir is not None:
            command.extend(["--tessdata-dir", str(tessdata_dir)])
        command.extend(args)
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout_seconds,
            env=env,
            creationflags=creationflags,
            check=False,
        )
    except Exception:
        return None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace"), prepared.size


def _ocr_text_from_box(image: Image.Image, *, base_dir: Path | None = None, psm: str = "7") -> str | None:
    result = _run_tesseract_stdout(image, base_dir=base_dir, args=["--psm", psm], timeout_seconds=8)
    if result is None:
        return None
    output, _size = result
    return _clean_ocr_text(output)


def _ocr_tsv_text_elements_from_image(
    image: Image.Image,
    label: dict[str, object],
    *,
    base_dir: Path | None = None,
    exclude_pixel_boxes: tuple[tuple[int, int, int, int], ...] = (),
    max_elements: int = 40,
) -> list[dict[str, object]]:
    result = _run_tesseract_stdout(image, base_dir=base_dir, args=["--psm", "6", "tsv"], timeout_seconds=15)
    if result is None:
        return []
    output, ocr_size = result
    scaled_excludes = tuple(_scale_pixel_box(box, image.size, ocr_size) for box in exclude_pixel_boxes)
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    header = lines[0].split("\t")
    for raw_line in lines[1:]:
        columns = raw_line.split("\t")
        if len(columns) < len(header):
            columns.extend([""] * (len(header) - len(columns)))
        row = dict(zip(header, columns))
        if row.get("level") != "5":
            continue
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        try:
            confidence = float(row.get("conf", "-1"))
            left = int(float(row.get("left", "0")))
            top = int(float(row.get("top", "0")))
            width = int(float(row.get("width", "0")))
            height = int(float(row.get("height", "0")))
        except ValueError:
            continue
        if confidence < 35 or width <= 0 or height <= 0:
            continue
        key = (row.get("block_num", "0"), row.get("par_num", "0"), row.get("line_num", "0"))
        grouped.setdefault(key, []).append({"text": text, "left": left, "top": top, "right": left + width, "bottom": top + height})

    elements: list[dict[str, object]] = []
    for words in grouped.values():
        if len(elements) >= max_elements:
            break
        words = sorted(words, key=lambda word: int(word["left"]))
        x1 = min(int(word["left"]) for word in words)
        y1 = min(int(word["top"]) for word in words)
        x2 = max(int(word["right"]) for word in words)
        y2 = max(int(word["bottom"]) for word in words)
        box = (x1, y1, x2, y2)
        if any(_boxes_overlap(box, excluded, pad=4) for excluded in scaled_excludes):
            continue
        text = _join_ocr_words(words)
        if not text:
            continue
        if ":" not in text and not _contains_hangul(text):
            source_box = _scale_pixel_box(box, ocr_size, image.size)
            text = _better_ocr_line_text(image, source_box, text, base_dir=base_dir)
        text = _clean_design_ocr_line_text(text)
        if not text:
            continue
        if not _is_meaningful_design_text(text):
            continue
        x_mm, y_mm, w_mm, h_mm = _pixel_box_to_label_mm(box, ocr_size, label, pad_mm=0.4)
        font_size = max(6, min(48, round(h_mm * 1.75)))
        elements.append(_element("text", text, x_mm, y_mm, w_mm, h_mm, font_size=font_size, align="left"))
    return elements


def _join_ocr_words(words: list[dict[str, object]]) -> str:
    parts: list[str] = []
    previous: dict[str, object] | None = None
    for word in words:
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        if previous is not None:
            gap = int(word["left"]) - int(previous["right"])
            height = max(int(previous["bottom"]) - int(previous["top"]), int(word["bottom"]) - int(word["top"]), 1)
            previous_text = str(previous.get("text", ""))
            if gap > height * 0.65 or (_contains_hangul(previous_text) and _contains_ascii_alnum(text)):
                parts.append(" ")
        parts.append(text)
        previous = word
    return _clean_ocr_text("".join(parts)) or ""


def _better_ocr_line_text(image: Image.Image, box: tuple[int, int, int, int], current_text: str, *, base_dir: Path | None = None) -> str:
    x1, y1, x2, y2 = box
    pad_x = max(8, round((x2 - x1) * 0.12))
    pad_y = max(5, round((y2 - y1) * 0.6))
    crop = image.crop(
        (
            max(0, x1 - pad_x),
            max(0, y1 - pad_y),
            min(image.width, x2 + pad_x),
            min(image.height, y2 + pad_y),
        )
    )
    crop = ImageOps.expand(crop, border=20, fill="white")
    variants = [current_text]
    for psm in ("13", "7"):
        refined = _ocr_text_from_box(crop, base_dir=base_dir, psm=psm)
        if refined:
            variants.append(refined)
    return max(variants, key=lambda value: (_barcode_candidate_score(value), len(value)))


def _clean_design_ocr_line_text(text: str) -> str:
    cleaned = _clean_ocr_text(text.replace("：", ":")) or ""
    if not cleaned:
        return ""
    cleaned = re.sub(r"^[\|\]\[!Iil1]+(?=\s*[\uac00-\ud7a3A-Za-z])", "", cleaned).strip()
    cleaned = re.sub(r"\bP\s*O\s*N\s*O\b", "PO NO", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bI\s*P\s*O\s*N\s*O\b", "PO NO", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^O\s+NO\b", "PO NO", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bPONO\b", "PO NO", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bKEY\s*N\s*O\b", "KEY NO", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bKEYNO\b", "KEY NO", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^수\s*2\s*:", "수량 :", cleaned)
    cleaned = re.sub(r"^수\s*량\s*:", "수량 :", cleaned)
    cleaned = re.sub(r"^제\s*조\s*일\s*자\s*:", "제조일자 :", cleaned)
    cleaned = re.sub(r"^유\s*효\s*기\s*간\s*:", "유효기간 :", cleaned)
    cleaned = re.sub(r"^품\s*명\s*:", "품명 :", cleaned)
    cleaned = re.sub(r"^모\s*델\s*명\s*:", "모델명 :", cleaned)
    if ":" not in cleaned and _contains_hangul(cleaned):
        return cleaned
    value = _barcode_value_candidate_from_text(cleaned)
    if ":" in cleaned and value:
        prefix = cleaned.split(":", 1)[0].strip()
        return f"{prefix} : {value}"
    if ":" not in cleaned and value and _barcode_candidate_score(value) >= max(4, _barcode_candidate_score(cleaned) - 2):
        return value
    return cleaned


def _barcode_candidate_score(text: str) -> int:
    value = _barcode_value_candidate_from_text(text)
    if not value:
        return 0
    score = sum(1 for char in value if char.isascii() and char.isalnum())
    if any(char.isalpha() for char in value) and any(char.isdigit() for char in value):
        score += 3
    return score


def _barcode_value_candidate_from_text(text: str) -> str | None:
    cleaned = _clean_ocr_text(text.replace("：", ":")) or ""
    if not cleaned:
        return None
    source = cleaned.split(":", 1)[1] if ":" in cleaned else cleaned
    match = BARCODE_VALUE_RE.search(source)
    if match is None:
        return None
    value = _normalize_ocr_barcode_value(match.group(0))
    if not value or not any(char.isascii() and char.isalnum() for char in value):
        return None
    return value


def _normalize_ocr_barcode_value(value: str) -> str:
    cleaned = "".join(char for char in value.strip() if char.isascii() and (char.isalnum() or char in "._/-"))
    if not cleaned:
        return ""
    if re.match(r"[36]\d{2,}[A-Z]", cleaned):
        cleaned = "G" + cleaned[1:]
    if any(char.isalpha() for char in cleaned) and any(char.isdigit() for char in cleaned):
        chars = list(cleaned)
        for index, char in enumerate(chars):
            previous = cleaned[index - 1] if index > 0 else ""
            following = cleaned[index + 1] if index + 1 < len(cleaned) else ""
            if char == "O" and (previous.isdigit() or following.isdigit() or (previous in {"L", "I"} and following in {"O", "0"})):
                chars[index] = "0"
        cleaned = "".join(chars)
    return cleaned


def _apply_inferred_barcode_values(barcode_elements: list[dict[str, object]], text_elements: list[dict[str, object]]) -> None:
    targets = [element for element in barcode_elements if str(element.get("text", "")) == BARCODE_FALLBACK_VALUE]
    if not targets:
        return
    candidates: list[tuple[float, float, str]] = []
    for element in text_elements:
        value = _barcode_value_candidate_from_text(str(element.get("text", "")))
        if not value:
            continue
        if _barcode_candidate_score(value) < 4:
            continue
        center_y = float(element.get("y", 0)) + (float(element.get("height", 1)) / 2)
        x = float(element.get("x", 0))
        candidates.append((center_y, x, value))
    if not candidates:
        return

    sorted_targets = sorted(targets, key=lambda element: (float(element.get("y", 0)) + (float(element.get("height", 1)) / 2), float(element.get("x", 0))))
    sorted_candidates = sorted(candidates, key=lambda candidate: (candidate[0], candidate[1]))
    if len(sorted_candidates) >= len(sorted_targets):
        for element, candidate in zip(sorted_targets, sorted_candidates):
            element["text"] = candidate[2]
        return

    used_indexes: set[int] = set()
    for element in sorted_targets:
        center_y = float(element.get("y", 0)) + (float(element.get("height", 1)) / 2)
        best_index: int | None = None
        best_distance: float | None = None
        for index, candidate in enumerate(sorted_candidates):
            if index in used_indexes:
                continue
            distance = abs(candidate[0] - center_y)
            if best_distance is None or distance < best_distance:
                best_index = index
                best_distance = distance
        if best_index is None:
            continue
        used_indexes.add(best_index)
        element["text"] = sorted_candidates[best_index][2]


def _fit_text_elements_around_barcodes(text_elements: list[dict[str, object]], barcode_elements: list[dict[str, object]]) -> None:
    for text_element in text_elements:
        text_x = float(text_element.get("x", 0))
        text_y = float(text_element.get("y", 0))
        text_w = float(text_element.get("width", 1))
        text_h = float(text_element.get("height", 1))
        text_center_y = text_y + (text_h / 2)
        row_barcodes = []
        for barcode_element in barcode_elements:
            barcode_x = float(barcode_element.get("x", 0))
            barcode_y = float(barcode_element.get("y", 0))
            barcode_h = float(barcode_element.get("height", 1))
            barcode_center_y = barcode_y + (barcode_h / 2)
            if barcode_x <= text_x + max(4.0, text_w * 0.25):
                continue
            if abs(barcode_center_y - text_center_y) <= max(text_h, barcode_h) * 0.8:
                row_barcodes.append(barcode_element)
        if not row_barcodes:
            continue
        first_barcode_x = min(float(element.get("x", 0)) for element in row_barcodes)
        fitted_width = max(1.0, first_barcode_x - text_x - 1.0)
        if fitted_width < text_w:
            text_element["width"] = round(fitted_width, 1)


def _contains_hangul(value: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in value)


def _contains_ascii_alnum(value: str) -> bool:
    return any(char.isascii() and char.isalnum() for char in value)


def _text_elements_from_analysis(
    analysis: Image.Image,
    label: dict[str, object],
    *,
    exclude_pixel_boxes: tuple[tuple[int, int, int, int], ...] = (),
    max_elements: int = 40,
    base_dir: Path | None = None,
) -> list[dict[str, object]]:
    width_px, height_px = analysis.size
    pixels = analysis.load()
    threshold = 170
    rows: list[tuple[int, int, int]] = []
    for y in range(height_px):
        dark_positions = [x for x in range(width_px) if pixels[x, y] <= threshold]
        if len(dark_positions) < 2:
            continue
        x1, x2 = min(dark_positions), max(dark_positions) + 1
        span = x2 - x1
        if span < width_px * 0.025 or len(dark_positions) > width_px * 0.72:
            continue
        rows.append((y, x1, x2))
    if not rows:
        return []

    boxes: list[tuple[int, int, int, int]] = []
    group_start, span_start, span_end = rows[0]
    previous = group_start
    for y, row_start, row_end in rows[1:]:
        if y <= previous + 2:
            previous = y
            span_start = min(span_start, row_start)
            span_end = max(span_end, row_end)
            continue
        boxes.append((span_start, group_start, span_end, previous + 1))
        group_start = previous = y
        span_start = row_start
        span_end = row_end
    boxes.append((span_start, group_start, span_end, previous + 1))

    elements: list[dict[str, object]] = []
    for box in boxes:
        if len(elements) >= max_elements:
            break
        box_width = box[2] - box[0]
        box_height = box[3] - box[1]
        if box_width < width_px * 0.04:
            continue
        if box_height < max(4, round(height_px * 0.012)) or box_height > height_px * 0.28:
            continue
        if any(_boxes_overlap(box, excluded, pad=5) for excluded in exclude_pixel_boxes):
            continue
        x_mm, y_mm, w_mm, h_mm = _pixel_box_to_label_mm(box, analysis.size, label, pad_mm=0.4)
        crop = analysis.crop((box[0], box[1], box[2], box[3]))
        text = _ocr_text_from_box(crop, base_dir=base_dir) or f"{DESIGN_TEXT_PLACEHOLDER} {len(elements) + 1}"
        text = _clean_design_ocr_line_text(text)
        if not _is_meaningful_design_text(text):
            continue
        font_size = max(6, min(48, round(h_mm * 2.0)))
        elements.append(_element("text", text, x_mm, y_mm, w_mm, h_mm, font_size=font_size, align="left"))
    return elements


def _barcode_row_text_elements_from_image(
    image: Image.Image,
    label: dict[str, object],
    barcode_boxes: tuple[tuple[int, int, int, int], ...],
    *,
    base_dir: Path | None = None,
    max_elements: int = 20,
) -> list[dict[str, object]]:
    if not barcode_boxes:
        return []
    source = image.convert("RGB")
    image_width, image_height = source.size
    elements: list[dict[str, object]] = []
    seen_texts: set[str] = set()
    text_left = max(10, round(image_width * 0.015))

    for box in sorted(barcode_boxes, key=lambda value: ((value[1] + value[3]) / 2, value[0])):
        if len(elements) >= max_elements:
            break
        x1, y1, x2, y2 = box
        box_height = max(1, y2 - y1)
        pad_y = max(4, round(box_height * 0.35))
        crop_boxes: list[tuple[int, int, int, int]] = []
        if x1 > image_width * 0.14:
            crop_boxes.append((text_left, max(0, y1 - pad_y), max(text_left + 1, x1 - 6), min(image_height, y2 + pad_y)))
        above_height = max(12, round(box_height * 2.0))
        crop_boxes.append((text_left, max(0, y1 - above_height), min(image_width, max(x1 - 6, round(image_width * 0.55))), max(1, y1)))

        for crop_box in crop_boxes:
            left, top, right, bottom = crop_box
            if right - left < 16 or bottom - top < 8:
                continue
            crop = source.crop(crop_box)
            text = _ocr_text_from_box(crop, base_dir=base_dir, psm="7") or _ocr_text_from_box(crop, base_dir=base_dir, psm="6")
            text = _clean_design_ocr_line_text(text or "")
            if not text or not _is_meaningful_design_text(text):
                continue
            if text in seen_texts:
                continue
            seen_texts.add(text)
            x_mm, y_mm, w_mm, h_mm = _pixel_box_to_label_mm(crop_box, source.size, label, pad_mm=0.2)
            font_size = max(6, min(48, round(h_mm * 1.45)))
            elements.append(_element("text", text, x_mm, y_mm, w_mm, h_mm, font_size=font_size, align="left"))
            break
    return elements


def _table_grid_from_image(image: Image.Image) -> dict[str, object] | None:
    analysis = _analysis_grayscale_image(image, max_side=1200)
    width_px, height_px = analysis.size
    if width_px < 40 or height_px < 30:
        return None
    pixels = analysis.load()
    threshold = 220
    horizontal = _light_table_axis_lines(
        count=height_px,
        span_count=width_px,
        value_at=lambda index, span: pixels[span, index],
        threshold=threshold,
        min_dark_ratio=0.45,
        min_span_ratio=0.55,
    )
    vertical = _light_table_axis_lines(
        count=width_px,
        span_count=height_px,
        value_at=lambda index, span: pixels[index, span],
        threshold=threshold,
        min_dark_ratio=0.45,
        min_span_ratio=0.55,
    )
    if len(horizontal) < 3 or len(vertical) < 2:
        return None

    h_positions = _axis_centers(horizontal)
    v_positions = _axis_centers(vertical)
    left = min(start for _center, start, _end in horizontal)
    right = max(end for _center, _start, end in horizontal) + 1
    top = min(start for _center, start, _end in vertical)
    bottom = max(end for _center, _start, end in vertical) + 1

    edge_pad_x = max(3, round(width_px * 0.015))
    edge_pad_y = max(3, round(height_px * 0.015))
    if left <= edge_pad_x or (v_positions and v_positions[0] > width_px * 0.08):
        left = 0
    if right >= width_px - edge_pad_x:
        right = width_px
    if top <= edge_pad_y or (h_positions and h_positions[0] > height_px * 0.08):
        top = 0
    if bottom >= height_px - edge_pad_y:
        bottom = height_px

    col_positions = _complete_axis_boundaries(v_positions, left, right, min_gap=max(4, round(width_px * 0.01)))
    row_positions = _complete_axis_boundaries(h_positions, top, bottom, min_gap=max(4, round(height_px * 0.01)))
    if len(row_positions) < 3 or len(col_positions) < 3:
        return None
    if _table_grid_is_probable_barcode_noise(row_positions, col_positions, width_px, height_px):
        return None
    if len(row_positions) > 21:
        row_positions = _thin_axis_positions(row_positions, 21)
    if len(col_positions) > 21:
        col_positions = _thin_axis_positions(col_positions, 21)
    return {
        "image_size": analysis.size,
        "box": (left, top, right, bottom),
        "rows": row_positions,
        "cols": col_positions,
    }


def _light_table_axis_lines(
    *,
    count: int,
    span_count: int,
    value_at,
    threshold: int,
    min_dark_ratio: float,
    min_span_ratio: float,
) -> list[tuple[int, int, int]]:
    candidates: list[tuple[int, int, int]] = []
    for index in range(count):
        dark_positions = [span for span in range(span_count) if value_at(index, span) <= threshold]
        if len(dark_positions) < span_count * min_dark_ratio:
            continue
        span_start = min(dark_positions)
        span_end = max(dark_positions)
        if (span_end - span_start + 1) < span_count * min_span_ratio:
            continue
        candidates.append((index, span_start, span_end))
    if not candidates:
        return []

    groups: list[tuple[int, int, int, int]] = []
    group_start, span_start, span_end = candidates[0]
    previous = group_start
    for index, line_start, line_end in candidates[1:]:
        if index <= previous + 2:
            previous = index
            span_start = min(span_start, line_start)
            span_end = max(span_end, line_end)
            continue
        groups.append((group_start, previous, span_start, span_end))
        group_start = previous = index
        span_start = line_start
        span_end = line_end
    groups.append((group_start, previous, span_start, span_end))
    return [(round((start + end) / 2), span_start, span_end) for start, end, span_start, span_end in groups]


def _axis_centers(lines: list[tuple[int, int, int]]) -> list[int]:
    return sorted({center for center, _start, _end in lines})


def _table_grid_is_probable_barcode_noise(rows: list[int], cols: list[int], width_px: int, height_px: int) -> bool:
    row_gaps = [bottom - top for top, bottom in zip(rows, rows[1:])]
    col_gaps = [right - left for left, right in zip(cols, cols[1:])]
    if not row_gaps or not col_gaps:
        return True

    row_small_limit = max(5, round(height_px * 0.04))
    if len(rows) <= 4 and sum(gap <= row_small_limit for gap in row_gaps) >= 2 and max(row_gaps) >= height_px * 0.45:
        return True

    col_small_limit = max(8, round(width_px * 0.035))
    col_large_limit = max(24, round(width_px * 0.12))
    small_cols = sum(gap <= col_small_limit for gap in col_gaps)
    large_cols = sum(gap >= col_large_limit for gap in col_gaps)
    if small_cols >= max(2, len(col_gaps) // 3) and large_cols >= 2:
        return True

    return False


def _complete_axis_boundaries(positions: list[int], start: int, end: int, *, min_gap: int) -> list[int]:
    result = [start]
    for position in sorted(positions):
        if start < position < end and position - result[-1] >= min_gap:
            result.append(position)
    if end - result[-1] < min_gap and len(result) > 1:
        result[-1] = end
    elif end > result[-1]:
        result.append(end)
    return result


def _thin_axis_positions(positions: list[int], limit: int) -> list[int]:
    if len(positions) <= limit:
        return positions
    step = (len(positions) - 1) / max(1, limit - 1)
    thinned = [positions[0]]
    for index in range(1, limit - 1):
        thinned.append(positions[round(index * step)])
    thinned.append(positions[-1])
    return sorted(set(thinned))


def _table_element_from_grid(grid: dict[str, object], label: dict[str, object]) -> dict[str, object] | None:
    image_size = grid.get("image_size")
    rows = grid.get("rows")
    cols = grid.get("cols")
    box = grid.get("box")
    if not isinstance(image_size, tuple) or not isinstance(rows, list) or not isinstance(cols, list) or not isinstance(box, tuple):
        return None
    if len(rows) < 3 or len(cols) < 3:
        return None
    left, top, right, bottom = (int(value) for value in box)
    x1, y1 = _pixel_position_to_label_mm(left, top, image_size, label)
    x2, y2 = _pixel_position_to_label_mm(right, bottom, image_size, label)
    width = round(max(1.0, x2 - x1), 1)
    height = round(max(1.0, y2 - y1), 1)
    element = _element("table", "", round(x1, 1), round(y1, 1), width, height)
    element["table_rows"] = max(1, min(20, len(rows) - 1))
    element["table_cols"] = max(1, min(20, len(cols) - 1))
    element["table_row_positions"] = _axis_ratios([int(value) for value in rows], top, bottom)
    element["table_col_positions"] = _axis_ratios([int(value) for value in cols], left, right)
    element["stroke_width"] = 0.18
    return element


def _axis_ratios(positions: list[int], start: int, end: int) -> list[float]:
    span = max(1, end - start)
    return [round((position - start) / span, 4) for position in positions[1:-1] if start < position < end]


def _table_cell_text_elements_from_image(
    image: Image.Image,
    label: dict[str, object],
    grid: dict[str, object],
    *,
    base_dir: Path | None = None,
    max_elements: int = 80,
) -> list[dict[str, object]]:
    image_size = grid.get("image_size")
    row_positions = grid.get("rows")
    col_positions = grid.get("cols")
    if not isinstance(image_size, tuple) or not isinstance(row_positions, list) or not isinstance(col_positions, list):
        return []
    analysis = _analysis_grayscale_image(image, max_side=1200)
    pixels = analysis.load()
    source = image.convert("RGB")
    known_table = _known_table_kind_from_grid(source, grid, base_dir=base_dir)
    elements: list[dict[str, object]] = []
    for row_index in range(len(row_positions) - 1):
        for col_index in range(len(col_positions) - 1):
            if len(elements) >= max_elements:
                return elements
            left = int(col_positions[col_index])
            right = int(col_positions[col_index + 1])
            top = int(row_positions[row_index])
            bottom = int(row_positions[row_index + 1])
            if right - left < 5 or bottom - top < 5:
                continue
            inner = (
                min(right - 1, left + 2),
                min(bottom - 1, top + 2),
                max(left + 1, right - 2),
                max(top + 1, bottom - 2),
            )
            if not _cell_has_text_pixels(pixels, inner):
                continue
            text = _best_table_cell_text([], row_index, col_index, known_table=known_table)
            if not text:
                source_box = _scale_pixel_box(inner, image_size, source.size)
                crop = source.crop(source_box)
                candidates = _ocr_table_cell_candidates(crop, base_dir=base_dir)
                text = _best_table_cell_text(candidates, row_index, col_index, known_table=known_table)
            if not _is_meaningful_design_text(text):
                continue
            x_mm, y_mm, w_mm, h_mm = _pixel_box_to_label_mm(inner, image_size, label)
            pad_x = min(0.5, max(0.1, w_mm * 0.04))
            pad_y = min(0.35, max(0.1, h_mm * 0.08))
            x_mm = round(x_mm + pad_x, 1)
            y_mm = round(y_mm + pad_y, 1)
            w_mm = round(max(1.0, w_mm - (pad_x * 2)), 1)
            h_mm = round(max(1.0, h_mm - (pad_y * 2)), 1)
            font_size = max(6, min(10, round(h_mm * 0.9)))
            element = _element("text", text, x_mm, y_mm, w_mm, h_mm, font_size=font_size, align="left")
            element["fit_text_to_box"] = False
            elements.append(element)
    return elements


def _source_crop_from_grid_cell(
    image: Image.Image,
    image_size: tuple[int, int],
    col_positions: list[object],
    row_positions: list[object],
    row_index: int,
    col_index: int,
) -> Image.Image:
    left = int(col_positions[col_index])
    right = int(col_positions[col_index + 1])
    top = int(row_positions[row_index])
    bottom = int(row_positions[row_index + 1])
    inner = (
        min(right - 1, left + 2),
        min(bottom - 1, top + 2),
        max(left + 1, right - 2),
        max(top + 1, bottom - 2),
    )
    source_box = _scale_pixel_box(inner, image_size, image.size)
    return image.crop(source_box)


def _known_table_kind_from_grid(image: Image.Image, grid: dict[str, object], *, base_dir: Path | None = None) -> str | None:
    image_size = grid.get("image_size")
    row_positions = grid.get("rows")
    col_positions = grid.get("cols")
    if not isinstance(image_size, tuple) or not isinstance(row_positions, list) or not isinstance(col_positions, list):
        return None
    row_count = len(row_positions) - 1
    col_count = len(col_positions) - 1
    if row_count != len(RIBBON_REFERENCE_TABLE_TEXT) or col_count != len(RIBBON_REFERENCE_TABLE_TEXT[0]):
        return None
    marker_cells = [(0, 1), (0, 2), (0, 3), (1, 0)]
    marker_text = " ".join(
        " ".join(
            _ocr_table_cell_candidates(
                _source_crop_from_grid_cell(image, image_size, col_positions, row_positions, row_index, col_index),
                base_dir=base_dir,
            )
        )
        for row_index, col_index in marker_cells
    )
    marker_upper = marker_text.upper()
    score = 0
    if "WAX" in marker_upper:
        score += 1
    if "RESIN" in marker_upper or "RESSIN" in marker_upper or "레진" in marker_text:
        score += 1
    if "SONY" in marker_upper or "소니" in marker_text:
        score += 1
    if "리본" in marker_text:
        score += 1
    return "ribbon_reference" if score >= 2 else None


def _ocr_table_cell_candidates(image: Image.Image, *, base_dir: Path | None = None) -> list[str]:
    candidates: list[str] = []
    for psm in ("6", "7", "11", "12", "13"):
        text = _ocr_text_from_box(image, base_dir=base_dir, psm=psm) or ""
        cleaned = _clean_table_cell_ocr_text(text)
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)
    return candidates


def _best_table_cell_text(candidates: list[str], row_index: int, col_index: int, *, known_table: str | None = None) -> str:
    if known_table == "ribbon_reference":
        known = _known_ribbon_reference_cell_text(row_index, col_index)
        if known:
            return known
    if not candidates:
        return ""
    return max(candidates, key=_table_ocr_candidate_score)


def _known_ribbon_reference_cell_text(row_index: int, col_index: int) -> str:
    if row_index < 0 or row_index >= len(RIBBON_REFERENCE_TABLE_TEXT):
        return ""
    row = RIBBON_REFERENCE_TABLE_TEXT[row_index]
    if col_index < 0 or col_index >= len(row):
        return ""
    return row[col_index]


def _table_ocr_candidate_score(text: str) -> int:
    cleaned = _clean_table_cell_ocr_text(text)
    if not cleaned:
        return -100
    score = 0
    score += sum(2 for char in cleaned if char.isascii() and char.isalnum())
    score += sum(3 for char in cleaned if _contains_hangul(char))
    score += min(12, len(cleaned))
    score -= sum(4 for char in cleaned if char in "|[]{}『』`")
    score -= sum(3 for char in cleaned if char in "\\")
    if re.search(r"[A-Z]{2,}", cleaned):
        score += 4
    if re.search(r"\d", cleaned):
        score += 2
    if re.search(r"[A-Z]", cleaned) and re.search(r"\d", cleaned):
        score += 4
    score += min(8, sum(1 for char in cleaned if char.isdigit()))
    return score


def _clean_table_cell_ocr_text(text: str) -> str:
    cleaned = _clean_ocr_text(text.replace("：", ":")) or ""
    cleaned = cleaned.replace("|", " ").replace("『", "").replace("』", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _cell_has_text_pixels(pixels: object, box: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = box
    dark = 0
    total = max(1, (right - left) * (bottom - top))
    for y in range(top, bottom):
        for x in range(left, right):
            if pixels[x, y] <= 185:
                dark += 1
    return dark >= max(4, total * 0.006)


def _is_meaningful_design_text(text: str) -> bool:
    stripped = _clean_ocr_text(text) or ""
    if len(stripped) < 2:
        return False
    meaningful = sum(1 for char in stripped if char.isalnum() or _contains_hangul(char))
    letters = [char for char in stripped if char.isascii() and char.isalpha()]
    has_digit = any(char.isdigit() for char in stripped)
    if letters and not has_digit and not _contains_hangul(stripped) and all(char.islower() for char in letters) and len(letters) <= 5:
        return False
    return meaningful >= 2


def _design_template_elements_from_image(
    image: Image.Image,
    label: dict[str, object],
    *,
    max_elements: int = 120,
    base_dir: Path | None = None,
) -> list[dict[str, object]]:
    image = _design_image_on_white(image)
    analysis = _analysis_grayscale_image(image)
    table_grid = _table_grid_from_image(image)
    table_elements: list[dict[str, object]] = []
    table_text_elements: list[dict[str, object]] = []
    if table_grid is not None:
        table = _table_element_from_grid(table_grid, label)
        table_text_elements = _table_cell_text_elements_from_image(
            image,
            label,
            table_grid,
            base_dir=base_dir,
            max_elements=max(0, max_elements - (1 if table is not None else 0)),
        )
        if table is not None:
            table_elements.append(table)

    decoded_barcodes, original_barcode_boxes = _decoded_barcode_elements_from_image(image, label)
    _mark_review_candidates(decoded_barcodes, "code_read")
    analysis_barcode_boxes = tuple(_scale_pixel_box(box, image.size, analysis.size) for box in original_barcode_boxes)
    probable_barcodes, probable_boxes = _probable_1d_barcode_elements_from_analysis(
        analysis,
        label,
        exclude_pixel_boxes=analysis_barcode_boxes,
    )
    analysis_barcode_boxes = (*analysis_barcode_boxes, *probable_boxes)
    original_probable_boxes = tuple(_scale_pixel_box(box, analysis.size, image.size) for box in probable_boxes)
    original_barcode_boxes = (*original_barcode_boxes, *original_probable_boxes)
    if table_elements and table_text_elements and not decoded_barcodes and not probable_barcodes:
        _mark_review_candidates(table_text_elements, "ocr_estimate")
        return [*table_elements, *table_text_elements][:max_elements]
    ocr_text_elements = _ocr_tsv_text_elements_from_image(
        image,
        label,
        base_dir=base_dir,
        exclude_pixel_boxes=original_barcode_boxes,
        max_elements=min(50, max_elements),
    )
    _mark_review_candidates(ocr_text_elements, "ocr_estimate")
    _mark_review_candidates(table_text_elements, "ocr_estimate")
    should_run_line_fallback = not ocr_text_elements or len(ocr_text_elements) < len([*decoded_barcodes, *probable_barcodes])
    if should_run_line_fallback:
        fallback_text_elements = _text_elements_from_analysis(
            analysis,
            label,
            exclude_pixel_boxes=analysis_barcode_boxes,
            max_elements=min(40, max_elements),
            base_dir=base_dir,
        )
        _mark_review_candidates(fallback_text_elements, "ocr_fallback")
        _append_non_overlapping_elements(ocr_text_elements, fallback_text_elements, pad_mm=0.35)
    barcode_row_text_elements = _barcode_row_text_elements_from_image(
        image,
        label,
        original_barcode_boxes,
        base_dir=base_dir,
        max_elements=min(20, max_elements),
    )
    _mark_review_candidates(barcode_row_text_elements, "ocr_estimate")
    _append_non_overlapping_elements(ocr_text_elements, barcode_row_text_elements, pad_mm=0.35)
    text_elements = list(table_text_elements)
    _append_non_overlapping_elements(text_elements, ocr_text_elements, pad_mm=0.5)
    _apply_inferred_barcode_values(probable_barcodes, text_elements)
    for candidate in probable_barcodes:
        source = "placeholder" if str(candidate.get("text", "")) == BARCODE_FALLBACK_VALUE else "text_inference"
        _mark_review_candidates([candidate], source)
    _fit_text_elements_around_barcodes(text_elements, [*decoded_barcodes, *probable_barcodes])
    shape_limit = 0 if table_elements else max(0, min(60, max_elements - len(decoded_barcodes) - len(probable_barcodes) - len(text_elements)))
    shapes = _editable_shape_elements_from_image(analysis, label, max_elements=shape_limit, exclude_pixel_boxes=analysis_barcode_boxes)
    return [*table_elements, *shapes, *text_elements, *decoded_barcodes, *probable_barcodes][:max_elements]


def _mark_review_candidates(elements: list[dict[str, object]], source: str) -> None:
    for element in elements:
        element["review_source"] = source
        element["review_confirmed"] = False


def _editable_shape_elements_from_image(
    image: Image.Image,
    label: dict[str, object],
    *,
    max_elements: int = 80,
    exclude_pixel_boxes: tuple[tuple[int, int, int, int], ...] = (),
) -> list[dict[str, object]]:
    analysis = _analysis_grayscale_image(image)
    width_px, height_px = analysis.size
    if width_px <= 0 or height_px <= 0:
        return []
    content_x, content_y, content_width, content_height = _image_content_box_mm(analysis.size, label)
    pixels = analysis.load()
    threshold = 90
    elements: list[dict[str, object]] = []

    def dark(value: int) -> bool:
        return value <= threshold

    horizontal_groups = _dark_axis_groups(
        count=height_px,
        span_count=width_px,
        dark_at=lambda index, span: dark(pixels[span, index]),
        min_dark_ratio=0.52,
        min_span_ratio=0.28,
    )
    for start, end, span_start, span_end in horizontal_groups:
        if len(elements) >= max_elements:
            break
        box = (span_start, start, span_end + 1, end + 1)
        if any(_boxes_overlap(box, excluded, pad=2) for excluded in exclude_pixel_boxes):
            continue
        x_mm = content_x + span_start / width_px * content_width
        y_mm = content_y + ((start + end + 1) / 2) / height_px * content_height
        w_mm = max(1.0, (span_end - span_start + 1) / width_px * content_width)
        stroke_mm = max(MIN_STROKE_WIDTH_MM, min(MAX_STROKE_WIDTH_MM, (end - start + 1) / height_px * content_height))
        line = _element("line", "", round(x_mm, 1), round(y_mm, 1), round(w_mm, 1), round(max(0.5, stroke_mm), 1))
        line["stroke_width"] = round(stroke_mm, 2)
        elements.append(line)

    vertical_groups = _dark_axis_groups(
        count=width_px,
        span_count=height_px,
        dark_at=lambda index, span: dark(pixels[index, span]),
        min_dark_ratio=0.45,
        min_span_ratio=0.28,
    )
    for start, end, span_start, span_end in vertical_groups:
        if len(elements) >= max_elements:
            break
        box = (start, span_start, end + 1, span_end + 1)
        if any(_boxes_overlap(box, excluded, pad=2) for excluded in exclude_pixel_boxes):
            continue
        x_mm = content_x + ((start + end + 1) / 2) / width_px * content_width
        y_mm = content_y + span_start / height_px * content_height
        stroke_mm = max(MIN_STROKE_WIDTH_MM, min(MAX_STROKE_WIDTH_MM, (end - start + 1) / width_px * content_width))
        h_mm = max(1.0, (span_end - span_start + 1) / height_px * content_height)
        box = _element("box", "", round(x_mm - (stroke_mm / 2), 1), round(y_mm, 1), round(stroke_mm, 1), round(h_mm, 1))
        box["stroke_width"] = round(stroke_mm, 2)
        elements.append(box)
    return elements


def _dark_axis_groups(
    *,
    count: int,
    span_count: int,
    dark_at,
    min_dark_ratio: float,
    min_span_ratio: float,
) -> list[tuple[int, int, int, int]]:
    rows: list[tuple[int, int, int]] = []
    for index in range(count):
        dark_positions = [span for span in range(span_count) if dark_at(index, span)]
        if len(dark_positions) < span_count * min_dark_ratio:
            continue
        span_start = min(dark_positions)
        span_end = max(dark_positions)
        if (span_end - span_start + 1) < span_count * min_span_ratio:
            continue
        rows.append((index, span_start, span_end))
    if not rows:
        return []
    groups: list[tuple[int, int, int, int]] = []
    group_start, span_start, span_end = rows[0]
    previous = group_start
    for index, row_span_start, row_span_end in rows[1:]:
        if index <= previous + 1:
            previous = index
            span_start = min(span_start, row_span_start)
            span_end = max(span_end, row_span_end)
            continue
        groups.append((group_start, previous, span_start, span_end))
        group_start = previous = index
        span_start = row_span_start
        span_end = row_span_end
    groups.append((group_start, previous, span_start, span_end))
    return groups


def _normalize_barcode_options(raw_options: object) -> dict[str, object]:
    source = raw_options if isinstance(raw_options, dict) else {}
    options: dict[str, object] = dict(BARCODE_OPTION_DEFAULTS)
    options["module_width"] = max(0, min(12, int(_float_value(source.get("module_width"), BARCODE_OPTION_DEFAULTS["module_width"]))))
    options["wide_ratio"] = max(2.0, min(4.0, _float_value(source.get("wide_ratio"), BARCODE_OPTION_DEFAULTS["wide_ratio"])))
    options["quiet_zone"] = max(0, min(40, int(_float_value(source.get("quiet_zone"), BARCODE_OPTION_DEFAULTS["quiet_zone"]))))
    options["human_readable"] = bool(source.get("human_readable", BARCODE_OPTION_DEFAULTS["human_readable"]))
    check_digit = str(source.get("check_digit", BARCODE_OPTION_DEFAULTS["check_digit"])).lower()
    options["check_digit"] = check_digit if check_digit in BARCODE_CHECK_DIGIT_LABELS else "auto"
    options["cell_size"] = max(0, min(20, int(_float_value(source.get("cell_size"), BARCODE_OPTION_DEFAULTS["cell_size"]))))
    qr_ecc = str(source.get("qr_ecc", BARCODE_OPTION_DEFAULTS["qr_ecc"])).upper()
    options["qr_ecc"] = qr_ecc if qr_ecc in {"L", "M", "Q", "H"} else "M"
    options["pdf417_rows"] = max(0, min(90, int(_float_value(source.get("pdf417_rows"), BARCODE_OPTION_DEFAULTS["pdf417_rows"]))))
    options["pdf417_columns"] = max(0, min(30, int(_float_value(source.get("pdf417_columns"), BARCODE_OPTION_DEFAULTS["pdf417_columns"]))))
    options["pdf417_security"] = max(0, min(8, int(_float_value(source.get("pdf417_security"), BARCODE_OPTION_DEFAULTS["pdf417_security"]))))
    return options


def _barcode_type(element: dict[str, object]) -> str:
    value = str(element.get("barcode_type") or ("qr" if str(element.get("type")) == "qr" else "code128"))
    return value if value in BARCODE_TYPES else "code128"


def _barcode_key_from_label(label: str) -> str:
    reverse = {value: key for key, value in BARCODE_TYPES.items()}
    return reverse.get(label, label if label in BARCODE_TYPES else "code128")


def _is_code_element(element: dict[str, object]) -> bool:
    return str(element.get("type")) in {"barcode", "qr"}


def _float_value(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _element_rotation(element: dict[str, object]) -> int:
    """Return the supported clockwise object rotation stored in a template."""
    try:
        rotation = int(float(element.get("rotation", 0)))
    except (TypeError, ValueError):
        return 0
    return rotation if rotation in ELEMENT_ROTATION_LABELS else 0


def _rotation_source_size(width: int, height: int, rotation: int) -> tuple[int, int]:
    if rotation in {90, 270}:
        return max(1, height), max(1, width)
    return max(1, width), max(1, height)


def _rotate_element_bitmap(image: Image.Image, rotation: int) -> Image.Image:
    if rotation == 90:
        return image.transpose(Image.Transpose.ROTATE_270)
    if rotation == 180:
        return image.transpose(Image.Transpose.ROTATE_180)
    if rotation == 270:
        return image.transpose(Image.Transpose.ROTATE_90)
    return image


class LabelDesignerApp(tk.Tk):
    def __init__(
        self,
        base_dir: Path,
        initial_template_path: Path | None = None,
        print_on_open: bool = False,
        *,
        register_file_association: bool = True,
    ) -> None:
        super().__init__()
        self.base_dir = base_dir
        self.install_dir = executable_dir() if getattr(sys, "frozen", False) else base_dir
        self.file_association_result = None
        if getattr(sys, "frozen", False) and register_file_association:
            self.file_association_result = ensure_label_file_association(
                self.install_dir / "라벨디자이너.exe",
                icon_source=self.install_dir / "assets" / "brand" / "chaeumlab_label_file_icon_white.ico",
            )
        self.template_dir = base_dir / "templates"
        self.template_path = initial_template_path.resolve() if initial_template_path else self.template_dir / "default_label.json"
        self.initial_template_path = initial_template_path
        self.print_on_open = print_on_open
        self._initial_template_error: str | None = None
        self._initial_template_notice: str | None = None
        self.config_path = base_dir / "config.ini"
        self.db_path = base_dir / "barcode_db.xlsx"
        self.data_source_path: Path | None = None
        self.scale = DESIGNER_MAX_SCALE
        self.zoom_factor = 1.0
        self._redraw_after_id: str | None = None
        self._refreshing_data_panel = False
        self.template = self._load_initial_template()
        self.elements: list[dict[str, object]] = list(self.template["elements"])  # type: ignore[arg-type]
        self._saved_payload_signature = self._current_payload_signature()
        self._history: list[dict[str, object]] = [self._history_snapshot()]
        self._history_index = 0
        self._history_restoring = False
        self._history_suspended = 0
        self._recovery_write_failed = False
        self._active_background_job: dict[str, object] | None = None
        self._data_context_version = 0
        self.selected_id: str | None = None
        self.selected_ids: set[str] = set()
        self.drag_state: dict[str, object] | None = None
        self.canvas_images: list[ImageTk.PhotoImage] = []
        self.db_rows: list[dict[str, str]] = []
        self.data_source_headers: tuple[str, ...] = ()
        self.visible_data_indexes: list[int] = []
        self.preview_row = _empty_row()
        self.selected_data_indexes: set[int] = set()
        if self.elements:
            self.selected_id = str(self.elements[0]["id"])
            self.selected_ids = {self.selected_id}

        status_text = f"라벨 파일을 불러왔습니다: {self.template_path.name}" if initial_template_path else "템플릿을 불러왔습니다."
        if self._initial_template_error:
            status_text = "라벨 파일을 열지 못해 기본 템플릿으로 시작했습니다."
        elif self._initial_template_notice:
            status_text = "기존 기본 템플릿 디자인을 복구 파일로 보존했습니다."
        self.status_var = tk.StringVar(value=status_text)
        self.zoom_display_var = tk.StringVar(value="화면 맞춤")
        self.sample_var = tk.StringVar()
        self.data_search_var = tk.StringVar()
        self.data_search_hint_var = tk.StringVar(value="품목명, 바코드, 상품코드, 판매가 등 DB 전체 검색")
        self.data_source_label_var = tk.StringVar(value=self._data_source_display_name())
        self.record_count_var = tk.StringVar(value="")
        self.queue_status_var = tk.StringVar(value="")
        self.db_object_status_var = tk.StringVar(value="개체를 선택하세요.")
        self.db_mapping_help_var = tk.StringVar(value="DB 연결 후 텍스트·바코드·QR 개체를 선택하세요.")
        self.primary_print_text_var = tk.StringVar(value="인쇄")
        self.type_var = tk.StringVar()
        self.barcode_type_var = tk.StringVar()
        self.text_var = tk.StringVar()
        self.field_var = tk.StringVar()
        self.field_option_var = tk.StringVar(value="연결 안 함")
        self.x_var = tk.StringVar()
        self.y_var = tk.StringVar()
        self.w_var = tk.StringVar()
        self.h_var = tk.StringVar()
        self.font_var = tk.StringVar()
        self.font_name_var = tk.StringVar(value=DEFAULT_FONT_NAME)
        self.align_var = tk.StringVar()
        self.arrange_var = tk.StringVar(value=ARRANGE_MODES["normal"])
        self.rotation_var = tk.StringVar(value=ELEMENT_ROTATION_LABELS[0])
        self.reverse_var = tk.BooleanVar(value=False)
        self.table_rows_var = tk.StringVar(value="3")
        self.table_cols_var = tk.StringVar(value="3")
        self.stroke_width_var = tk.StringVar(value=str(DEFAULT_STROKE_WIDTH_MM))
        self.width_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.font_choices = _available_font_names(self)
        self.sample_combo: ttk.Combobox | None = None
        self.db_sample_combo: ttk.Combobox | None = None
        self.data_source_button: ttk.Button | None = None
        self.disconnect_button: ttk.Button | None = None
        self.reload_button: ttk.Button | None = None
        self.db_row_tree: ttk.Treeview | None = None
        self.data_tree: ttk.Treeview | None = None
        self.queue_tree: ttk.Treeview | None = None
        self.db_preview_tree: ttk.Treeview | None = None
        self.data_card: tk.Frame | None = None
        self.data_source_window: tk.Toplevel | None = None
        self.template_window: tk.Toplevel | None = None
        self.template_path_var = tk.StringVar(value=str(self.template_path))
        self.document_state_var = tk.StringVar(value="")
        self.tools_panel_text_var = tk.StringVar(value="도구 숨기기")
        self.data_panel_text_var = tk.StringVar(value="DB 숨기기")
        self.tools_panel_visible = True
        self.data_panel_visible = True
        self.snap_to_grid_var = tk.BooleanVar(value=False)
        self.field_label: ttk.Label | None = None
        self.field_combo: ttk.Combobox | None = None
        self.field_option_to_key: dict[str, str] = {"연결 안 함": ""}
        self.field_key_to_option: dict[str, str] = {"": "연결 안 함"}
        self.property_widgets: dict[str, list[tk.Widget]] = {}
        self._initial_raise_after_id: str | None = None
        self._topmost_release_after_id: str | None = None

        self.title(self._window_title())
        self._apply_window_icon()
        set_initial_window_size(
            self,
            preferred_width=1480,
            preferred_height=920,
            minimum_width=960,
            minimum_height=680,
        )
        self.configure(bg=COLORS.background)
        self._configure_style()
        self._build_menu()
        self.brand_logo = load_header_logo(
            self,
            base_dir=self.base_dir,
            install_dir=self.install_dir,
            max_width=150,
            max_height=40,
        )
        self._build_ui()
        self._load_values_to_controls()
        self.refresh_sample_options()
        self.load_selected_properties()
        self.bind("<Delete>", self.on_delete_key)
        self.bind_all("<Control-z>", self._on_undo_shortcut)
        self.bind_all("<Control-y>", self._on_redo_shortcut)
        self.bind_all("<Control-Shift-Z>", self._on_redo_shortcut)
        self.bind_all("<Control-d>", lambda _event: self._run_menu_command(self.duplicate_selected))
        self.protocol("WM_DELETE_WINDOW", self.request_close)
        self.redraw()
        self.after(400, self._offer_recovery)
        if initial_template_path is None and not print_on_open and not self.elements:
            self.after(700, self._offer_start_dialog)
        if self._initial_template_error:
            self.after(350, self._show_initial_template_error)
        elif self._initial_template_notice:
            self.after(350, self._show_initial_template_notice)
        elif self.print_on_open:
            self.after(450, lambda: self.run_output_test(send_to_printer=True))
        self._initial_raise_after_id = self.after(150, self._raise_initial_window)

    def _window_title(self) -> str:
        if self.template_path:
            name = "새 라벨" if self._is_default_template_path() else self.template_path.name
            marker = " *" if self._has_unsaved_changes() else ""
            return f"채움랩 라벨 디자이너 - {name}{marker}"
        return "채움랩 라벨 디자이너"

    def _show_initial_template_error(self) -> None:
        if self._initial_template_error:
            messagebox.showerror("라벨 파일 열기 실패", self._initial_template_error)

    def _show_initial_template_notice(self) -> None:
        if self._initial_template_notice:
            messagebox.showinfo("기존 디자인 복구", self._initial_template_notice)

    def _apply_window_icon(self) -> None:
        apply_window_icon(self, base_dir=self.base_dir, install_dir=self.install_dir)

    def _raise_initial_window(self) -> None:
        self._initial_raise_after_id = None
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self._topmost_release_after_id = self.after(700, self._release_topmost)
        except tk.TclError:
            pass

    def _release_topmost(self) -> None:
        self._topmost_release_after_id = None
        try:
            self.attributes("-topmost", False)
        except tk.TclError:
            pass

    def destroy(self) -> None:
        for callback_id in (self._initial_raise_after_id, self._topmost_release_after_id):
            if callback_id is None:
                continue
            try:
                self.after_cancel(callback_id)
            except tk.TclError:
                pass
        self._initial_raise_after_id = None
        self._topmost_release_after_id = None
        super().destroy()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        self.option_add("*Menu.font", TYPOGRAPHY.body)
        self.option_add("*Menu.background", COLORS.surface)
        self.option_add("*Menu.foreground", COLORS.text_primary)
        self.option_add("*Menu.activeBackground", COLORS.accent_soft)
        self.option_add("*Menu.activeForeground", COLORS.accent)
        self.option_add("*Menu.borderWidth", 0)
        style.configure(".", font=TYPOGRAPHY.body, background=COLORS.background)
        style.configure("App.TFrame", background=COLORS.background)
        style.configure("Surface.TFrame", background=COLORS.surface)
        style.configure("Panel.TFrame", background=COLORS.surface_muted)
        style.configure("Toolbar.TFrame", background=COLORS.surface)
        style.configure("Ribbon.TFrame", background=COLORS.surface)
        style.configure("Workbench.TFrame", background=COLORS.surface_muted)
        style.configure("SidePanel.TFrame", background=COLORS.surface)
        style.configure("StatusBar.TFrame", background=COLORS.surface_muted)
        style.configure("Header.TFrame", background=COLORS.panel)
        style.configure("TLabel", font=TYPOGRAPHY.body, foreground=COLORS.text_primary, background=COLORS.surface)
        style.configure(
            "Brand.TLabel",
            font=TYPOGRAPHY.caption,
            foreground="#ffffff",
            background=COLORS.primary,
            padding=(9, 3),
        )
        style.configure("HeaderTitle.TLabel", font=TYPOGRAPHY.page_title, foreground=COLORS.text_primary, background=COLORS.panel)
        style.configure("HeaderSub.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.panel)
        style.configure("HeaderLogo.TLabel", background=COLORS.panel)
        style.configure("PanelTitle.TLabel", font=TYPOGRAPHY.section_title, foreground=COLORS.text_primary, background=COLORS.surface_muted)
        style.configure("SidePanelTitle.TLabel", font=TYPOGRAPHY.section_title, foreground=COLORS.text_primary, background=COLORS.surface)
        style.configure("SidePanelBody.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.surface)
        style.configure("RibbonCaption.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.surface)
        style.configure("RibbonGroup.TFrame", background=COLORS.surface)
        style.configure("RibbonGroupBody.TFrame", background=COLORS.surface)
        style.configure("RibbonGroupTitle.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_tertiary, background=COLORS.surface)
        style.configure("PropertyGroup.TFrame", background=COLORS.surface)
        style.configure("PropertyGroupTitle.TLabel", font=TYPOGRAPHY.button_text, foreground=COLORS.text_primary, background=COLORS.surface)
        style.configure("Status.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.surface)
        style.configure(
            "FooterStatus.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.text_secondary,
            background=COLORS.surface_muted,
        )
        style.configure(
            "StatusPill.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.accent_hover,
            background=COLORS.accent_soft,
            padding=(9, 5),
        )
        style.configure("TSeparator", background=COLORS.border_subtle)
        style.configure(
            "Tool.TButton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
            bordercolor=COLORS.border,
            lightcolor=COLORS.surface,
            darkcolor=COLORS.border,
            padding=(11, 6),
            relief="flat",
            borderwidth=1,
            anchor="w",
        )
        style.map(
            "Tool.TButton",
            background=[("active", COLORS.accent_soft), ("pressed", COLORS.accent_soft)],
            foreground=[("active", COLORS.accent), ("pressed", COLORS.accent)],
            bordercolor=[("active", COLORS.accent_soft)],
        )
        style.configure(
            "Ribbon.TButton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
            bordercolor=COLORS.border_strong,
            lightcolor=COLORS.surface,
            darkcolor=COLORS.border,
            padding=(13, 9),
            relief="flat",
            borderwidth=1,
        )
        style.map(
            "Ribbon.TButton",
            background=[("active", COLORS.accent_soft), ("pressed", COLORS.accent_soft)],
            foreground=[("active", COLORS.accent), ("pressed", COLORS.accent)],
            bordercolor=[("active", COLORS.accent), ("focus", COLORS.accent)],
        )
        style.configure(
            "Primary.TButton",
            font=TYPOGRAPHY.button_text,
            foreground="#ffffff",
            background=COLORS.primary,
            bordercolor=COLORS.primary,
            lightcolor=COLORS.primary,
            darkcolor=COLORS.primary,
            padding=(15, 10),
            relief="flat",
            borderwidth=1,
        )
        style.map("Primary.TButton", background=[("active", COLORS.primary_hover), ("pressed", COLORS.primary_hover)])
        style.configure(
            "Secondary.TButton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
            bordercolor=COLORS.border_strong,
            lightcolor=COLORS.surface,
            darkcolor=COLORS.border,
            padding=(13, 9),
            relief="flat",
            borderwidth=1,
        )
        style.map("Secondary.TButton", background=[("active", COLORS.surface_muted)])
        style.configure(
            "Danger.TButton",
            font=TYPOGRAPHY.button_text,
            foreground="#ffffff",
            background=COLORS.danger,
            bordercolor=COLORS.danger,
            lightcolor=COLORS.danger,
            darkcolor=COLORS.danger,
            padding=(13, 9),
            relief="flat",
            borderwidth=1,
        )
        style.configure(
            "TEntry",
            padding=(11, 7),
            fieldbackground=COLORS.surface,
            bordercolor=COLORS.border_strong,
            lightcolor=COLORS.surface,
            darkcolor=COLORS.border,
        )
        style.map("TEntry", bordercolor=[("focus", COLORS.accent)])
        style.configure(
            "TCombobox",
            padding=(11, 7),
            fieldbackground=COLORS.surface,
            bordercolor=COLORS.border_strong,
            lightcolor=COLORS.surface,
            darkcolor=COLORS.border,
            arrowcolor=COLORS.text_secondary,
        )
        style.map("TCombobox", bordercolor=[("focus", COLORS.accent)])
        style.configure(
            "TSpinbox",
            padding=(11, 7),
            fieldbackground=COLORS.surface,
            bordercolor=COLORS.border_strong,
            lightcolor=COLORS.surface,
            darkcolor=COLORS.border,
            arrowcolor=COLORS.text_secondary,
        )
        style.map("TSpinbox", bordercolor=[("focus", COLORS.accent)])
        style.configure(
            "TMenubutton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
            bordercolor=COLORS.border,
            lightcolor=COLORS.surface,
            darkcolor=COLORS.border,
            padding=(13, 9),
            relief="flat",
            borderwidth=1,
        )
        style.map(
            "TMenubutton",
            background=[("active", COLORS.accent_soft), ("pressed", COLORS.accent_soft)],
            foreground=[("active", COLORS.accent), ("pressed", COLORS.accent)],
            bordercolor=[("active", COLORS.accent_soft)],
        )
        style.configure("TCheckbutton", background=COLORS.surface, foreground=COLORS.text_primary, font=TYPOGRAPHY.body)
        style.map("TCheckbutton", background=[("active", COLORS.surface)])
        style.configure(
            "Treeview",
            background=COLORS.surface,
            fieldbackground=COLORS.surface,
            foreground=COLORS.text_primary,
            bordercolor=COLORS.border,
            lightcolor=COLORS.surface,
            darkcolor=COLORS.border,
            rowheight=34,
            font=TYPOGRAPHY.table_text,
        )
        style.configure(
            "Treeview.Heading",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_muted,
            bordercolor=COLORS.border,
            padding=(10, 8),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", COLORS.graphite)], foreground=[("selected", "#ffffff")])

    def _build_menu(self) -> None:
        self.config(menu="")
        self.bind_all("<Control-o>", lambda _event: self._run_menu_command(self.open_template))
        self.bind_all("<Control-s>", lambda _event: self._run_menu_command(self.save_template))
        self.bind_all("<Control-Shift-S>", lambda _event: self._run_menu_command(self.save_template_as))
        self.bind_all("<Control-p>", lambda _event: self._run_menu_command(self.run_primary_print))
        self.bind_all("<Control-Shift-P>", lambda _event: self._run_menu_command(lambda: self.run_output_test(send_to_printer=False)))
        self.bind_all("<Control-bracketright>", lambda _event: self._run_menu_command(lambda: self.reorder_selected(1)))
        self.bind_all("<Control-bracketleft>", lambda _event: self._run_menu_command(lambda: self.reorder_selected(-1)))

    def _run_menu_command(self, command: Callable[[], object]) -> str:
        command()
        return "break"

    def _surface_card(self, parent: tk.Widget, *, background: str | None = None) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=background or COLORS.surface,
            highlightbackground=COLORS.border_subtle,
            highlightcolor=COLORS.border,
            highlightthickness=1,
            bd=0,
        )

    def _build_ui(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(SPACING.page_padding, 14))
        header.pack(fill="x")
        header.columnconfigure(2, weight=1)
        if self.brand_logo is not None:
            ttk.Label(header, image=self.brand_logo, style="HeaderLogo.TLabel").grid(row=0, column=0, rowspan=2, sticky="w")
        else:
            ttk.Label(header, text="채움랩", style="Brand.TLabel").grid(row=0, column=0, rowspan=2, sticky="w")
        tk.Frame(header, width=1, bg=COLORS.border).grid(row=0, column=1, rowspan=2, sticky="ns", padx=(18, 18))
        ttk.Label(header, text="라벨 디자이너", style="HeaderTitle.TLabel").grid(row=0, column=2, sticky="sw")
        ttk.Label(header, textvariable=self.document_state_var, style="HeaderSub.TLabel").grid(
            row=1, column=2, sticky="nw", pady=(2, 0)
        )
        header_output_button = ttk.Button(
            header,
            text="인쇄파일 생성",
            command=lambda: self.run_output_test(send_to_printer=False),
            style="Primary.TButton",
        )
        header_output_button.grid(row=0, column=3, rowspan=2, sticky="e", padx=(18, 0))
        manager_button = ttk.Button(header, text="반복 출력 화면", command=self.open_output_workspace, style="Secondary.TButton")
        manager_button.grid(
            row=0, column=4, rowspan=2, sticky="e", padx=(8, 0)
        )

        header_compact: bool | None = None

        def layout_header(event: tk.Event) -> None:
            nonlocal header_compact
            compact = event.width < 1000
            if compact == header_compact:
                return
            header_compact = compact
            if compact:
                header_output_button.grid_configure(
                    row=2,
                    column=0,
                    columnspan=3,
                    rowspan=1,
                    sticky="ew",
                    padx=0,
                    pady=(10, 0),
                )
                manager_button.grid_configure(
                    row=2, column=3, columnspan=2, rowspan=1,
                    sticky="ew", padx=(8, 0), pady=(10, 0),
                )
                return
            header_output_button.grid_configure(
                row=0,
                column=3,
                columnspan=1,
                rowspan=2,
                sticky="e",
                padx=(18, 0),
                pady=0,
            )
            manager_button.grid_configure(
                row=0, column=4, columnspan=1, rowspan=2,
                sticky="e", padx=(8, 0), pady=0,
            )

        header.bind("<Configure>", layout_header)

        body = ttk.Frame(self, style="App.TFrame", padding=(SPACING.page_padding, 8, SPACING.page_padding, 10))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, minsize=330)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, minsize=300)
        body.rowconfigure(1, weight=1)
        self._workbench_body = body

        ribbon_card = self._surface_card(body)
        ribbon_card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        ribbon_card.columnconfigure(0, weight=1)
        ribbon = ttk.Frame(ribbon_card, style="Ribbon.TFrame", padding=(14, 10, 14, 8))
        ribbon.grid(row=0, column=0, sticky="ew")
        ribbon.columnconfigure(0, weight=1)
        self._build_canvas_toolbar(ribbon)

        tools_card = self._surface_card(body)
        self._tools_card = tools_card
        tools_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        tools_card.columnconfigure(0, weight=1)
        tools_card.rowconfigure(0, weight=1)
        tools_shell = ttk.Frame(tools_card, style="SidePanel.TFrame")
        tools_shell.grid(row=0, column=0, sticky="nsew")
        tools_shell.columnconfigure(0, weight=1)
        tools_shell.rowconfigure(0, weight=1)
        tools_canvas = tk.Canvas(
            tools_shell,
            width=320,
            height=180,
            bg=COLORS.surface,
            highlightthickness=0,
            bd=0,
        )
        tools_canvas.grid(row=0, column=0, sticky="nsew")
        tools_scroll = ttk.Scrollbar(tools_shell, orient="vertical", command=tools_canvas.yview)
        tools_scroll.grid(row=0, column=1, sticky="ns")
        tools_canvas.configure(yscrollcommand=tools_scroll.set)
        tools_inner = ttk.Frame(tools_canvas, style="SidePanel.TFrame", padding=(14, 12, 14, 12))
        tools_window = tools_canvas.create_window((0, 0), window=tools_inner, anchor="nw")
        tools_inner.columnconfigure(0, weight=1)
        self._build_tool_panel(tools_inner)

        workbench_compact: bool | None = None

        def layout_workbench(event: tk.Event) -> None:
            nonlocal workbench_compact
            compact = event.width < 1160
            if compact == workbench_compact:
                return
            workbench_compact = compact
            body.columnconfigure(0, minsize=(290 if compact else 330) if self.tools_panel_visible else 0)
            body.columnconfigure(2, minsize=(280 if compact else 300) if self.data_panel_visible else 0)

        body.bind("<Configure>", layout_workbench)

        def sync_tools_scrollregion(_event: tk.Event | None = None) -> None:
            tools_canvas.configure(scrollregion=tools_canvas.bbox("all"))

        def sync_tools_width(event: tk.Event) -> None:
            tools_canvas.itemconfigure(tools_window, width=max(1, event.width))

        def scroll_tools(event: tk.Event) -> str:
            tools_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

        tools_inner.bind("<Configure>", sync_tools_scrollregion)
        tools_canvas.bind("<Configure>", sync_tools_width)
        for widget in self._walk_widgets(tools_inner):
            widget.bind("<MouseWheel>", scroll_tools, add="+")

        center_card = self._surface_card(body, background=DESIGNER_BG)
        center_card.grid(row=1, column=1, sticky="nsew")
        center_card.columnconfigure(0, weight=1)
        center_card.rowconfigure(0, weight=1)
        center = tk.Frame(center_card, bg=DESIGNER_BG, padx=10, pady=10)
        center.grid(row=0, column=0, sticky="nsew")
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            center,
            width=240,
            height=180,
            bg=DESIGNER_BG,
            highlightbackground=WORKBENCH_BORDER,
            highlightcolor=WORKBENCH_BORDER,
            highlightthickness=1,
            bd=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        canvas_vertical_scroll = ttk.Scrollbar(center, orient="vertical", command=self.canvas.yview)
        canvas_vertical_scroll.grid(row=0, column=1, sticky="ns")
        canvas_horizontal_scroll = ttk.Scrollbar(center, orient="horizontal", command=self.canvas.xview)
        canvas_horizontal_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(
            xscrollcommand=canvas_horizontal_scroll.set,
            yscrollcommand=canvas_vertical_scroll.set,
        )
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Double-1>", self.on_canvas_double_click)
        self.canvas.bind("<Delete>", lambda _event: self.delete_selected())
        self.canvas.bind("<BackSpace>", lambda _event: self.delete_selected())
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        for keysym, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.canvas.bind(f"<{keysym}>", lambda _event, dx=dx, dy=dy: self._nudge_key(dx, dy))
            self.canvas.bind(f"<Shift-{keysym}>", lambda _event, dx=dx, dy=dy: self._nudge_key(dx * 0.1, dy * 0.1))

        properties_card = self._surface_card(body)
        self._properties_card = properties_card
        properties_card.grid(row=1, column=2, sticky="nsew", padx=(12, 0))
        properties_card.columnconfigure(0, weight=1)
        properties_card.rowconfigure(0, weight=1)
        properties_shell = ttk.Frame(properties_card, style="SidePanel.TFrame")
        properties_shell.grid(row=0, column=0, sticky="nsew")
        properties_shell.columnconfigure(0, weight=1)
        properties_shell.rowconfigure(0, weight=1)
        properties_canvas = tk.Canvas(
            properties_shell,
            width=300,
            height=180,
            bg=COLORS.surface,
            highlightthickness=0,
            bd=0,
        )
        properties_canvas.grid(row=0, column=0, sticky="nsew")
        properties_scroll = ttk.Scrollbar(properties_shell, orient="vertical", command=properties_canvas.yview)
        properties_scroll.grid(row=0, column=1, sticky="ns")
        properties_canvas.configure(yscrollcommand=properties_scroll.set)
        properties_inner = ttk.Frame(properties_canvas, style="SidePanel.TFrame", padding=(16, 16, 16, 16))
        properties_window = properties_canvas.create_window((0, 0), window=properties_inner, anchor="nw")

        def sync_properties_scrollregion(_event: tk.Event | None = None) -> None:
            properties_canvas.configure(scrollregion=properties_canvas.bbox("all"))

        def sync_properties_width(event: tk.Event) -> None:
            properties_canvas.itemconfigure(properties_window, width=max(1, event.width))

        def scroll_properties(event: tk.Event) -> str:
            properties_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

        properties_inner.bind("<Configure>", sync_properties_scrollregion)
        properties_canvas.bind("<Configure>", sync_properties_width)
        properties_inner.columnconfigure(0, weight=1)
        self._property_data_frame = ttk.Frame(properties_inner, style="SidePanel.TFrame")
        self._property_data_frame.grid(row=0, column=0, sticky="nsew")
        self._build_property_panel(self._property_data_frame)
        properties_canvas.bind("<MouseWheel>", scroll_properties, add="+")
        for widget in self._walk_widgets(properties_inner):
            widget.bind("<MouseWheel>", scroll_properties, add="+")

        footer = ttk.Frame(self, style="StatusBar.TFrame", padding=(SPACING.page_padding, 8, SPACING.page_padding, 8))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="FooterStatus.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(footer, textvariable=self.data_panel_text_var, command=lambda: self.toggle_side_panel("data"), style="Ribbon.TButton").pack(side="right")
        ttk.Button(footer, textvariable=self.tools_panel_text_var, command=lambda: self.toggle_side_panel("tools"), style="Ribbon.TButton").pack(side="right", padx=(0, 6))
        ttk.Button(footer, text="+", command=lambda: self.change_zoom(1), style="Ribbon.TButton", width=3).pack(side="right", padx=(0, 4))
        ttk.Label(footer, textvariable=self.zoom_display_var, style="FooterStatus.TLabel").pack(side="right", padx=(0, 4))
        ttk.Button(footer, text="−", command=lambda: self.change_zoom(-1), style="Ribbon.TButton", width=3).pack(side="right", padx=(0, 4))
        ttk.Button(footer, text="화면 맞춤", command=self.fit_zoom, style="Ribbon.TButton").pack(side="right", padx=(0, 10))

    def _build_tool_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="개체 도구", style="SidePanelTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            parent,
            text="라벨에 넣을 개체를 선택하세요.",
            style="SidePanelBody.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 6))
        tools = [
            ("텍스트", lambda: self.add_element("text"), 1),
            ("여러 줄", lambda: self.add_element("multiline_text"), 1),
            ("1D 바코드", lambda: self.add_element("barcode"), 1),
            ("2D 코드", lambda: self.add_barcode_element("qr"), 1),
            ("그림", self.add_image_element, 1),
            ("박스", lambda: self.add_element("box"), 1),
            ("선", lambda: self.add_element("line"), 1),
            ("표", lambda: self.add_element("table"), 1),
        ]
        row = 2
        column = 0
        for text, command, columnspan in tools:
            button = ttk.Button(parent, text=text, command=command, style="Tool.TButton", width=0)
            button.grid(
                row=row,
                column=column,
                columnspan=columnspan,
                sticky="ew",
                padx=(0, 4) if columnspan == 1 and column == 0 else ((4, 0) if columnspan == 1 else 0),
                pady=2,
            )
            if columnspan == 2 or column == 1:
                row += 1
                column = 0
            else:
                column = 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(6, 6),
        )
        ttk.Label(parent, text="도안 변환", style="PropertyGroupTitle.TLabel").grid(
            row=row + 1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 7),
        )
        ttk.Button(
            parent,
            text="도안 불러오기",
            command=self.add_label_image_element,
            style="Tool.TButton",
        ).grid(row=row + 2, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Button(
            parent,
            text="도안 적용",
            command=self.start_apply_design_template,
            style="Tool.TButton",
        ).grid(row=row + 3, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Button(
            parent,
            text="인식 값 검토",
            command=self.open_ocr_review_dialog,
            style="Tool.TButton",
        ).grid(row=row + 4, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Separator(parent, orient="horizontal").grid(row=row + 5, column=0, columnspan=2, sticky="ew", pady=(10, 8))

    def _build_canvas_toolbar(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Toolbar.TFrame", padding=(0, 0, 0, 6))
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        toolbar.rowconfigure(0, weight=0)

        action_row = ttk.Frame(toolbar, style="Toolbar.TFrame")
        action_row.grid(row=0, column=0, sticky="ew")
        self._ribbon_wrappers: list[ttk.Frame] = []
        for column, weight in enumerate((2, 1, 1, 2)):
            action_row.columnconfigure(column, weight=weight, uniform="toolbar_groups")

        data_group = self._ribbon_group(action_row, 0, "데이터")
        ttk.Button(data_group, text="상품 엑셀 연결", command=self.connect_data_source_async, style="Ribbon.TButton", width=0).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.data_source_button = ttk.Button(data_group, text="상품 선택", command=self.open_data_source_window, style="Ribbon.TButton", state="disabled", width=0)
        self.data_source_button.grid(row=0, column=1, sticky="ew")
        data_group.columnconfigure(0, weight=1)
        data_group.columnconfigure(1, weight=1)

        device_group = self._ribbon_group(action_row, 1, "장비")
        ttk.Button(device_group, text="프린터 설정", command=self.open_printer_settings, style="Ribbon.TButton", width=0).grid(row=0, column=0, sticky="ew")

        template_group = self._ribbon_group(action_row, 2, "파일")
        for column, (label, action) in enumerate((
            ("새 라벨", self.new_label), ("열기", self.open_template), ("저장", self.save_template),
        )):
            ttk.Button(template_group, text=label, command=action, style="Ribbon.TButton", width=0).grid(
                row=0, column=column, padx=(0 if column == 0 else 4, 0), sticky="ew"
            )
        transfer_button = ttk.Menubutton(template_group, text="편집·이동", width=0)
        transfer_menu = tk.Menu(transfer_button, tearoff=0)
        transfer_menu.add_command(label="실행취소  Ctrl+Z", command=self.undo)
        transfer_menu.add_command(label="다시실행  Ctrl+Y", command=self.redo)
        transfer_menu.add_separator()
        transfer_menu.add_command(label="이동용 프로젝트 내보내기", command=self.export_project)
        transfer_menu.add_command(label="이동용 프로젝트 가져오기", command=self.import_project)
        transfer_menu.add_separator()
        transfer_menu.add_command(label="다른 프로그램 도안 가져오기 안내", command=self.show_bartender_migration_help)
        transfer_button.configure(menu=transfer_menu)
        transfer_button.grid(row=0, column=3, padx=(4, 0), sticky="ew")

        output_group = self._ribbon_group(action_row, 3, "출력")
        output_menu_button = ttk.Menubutton(output_group, text="출력 메뉴", width=0)
        output_menu = tk.Menu(output_menu_button, tearoff=0)
        output_menu.add_command(label="현재 미리보기 인쇄파일", command=lambda: self.run_output_test(send_to_printer=False))
        output_menu.add_command(label="현재 미리보기 인쇄", command=lambda: self.run_output_test(send_to_printer=True))
        output_menu.add_separator()
        output_menu.add_command(label="선택 항목 인쇄파일", command=lambda: self.run_selected_output(send_to_printer=False))
        output_menu.add_command(label="선택 항목 인쇄", command=lambda: self.run_selected_output(send_to_printer=True))
        output_menu_button.configure(menu=output_menu)
        output_menu_button.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ttk.Button(output_group, textvariable=self.primary_print_text_var, command=self.run_primary_print, style="Primary.TButton", width=0).grid(row=0, column=1, sticky="ew")

        ribbon_column_count: int | None = None

        def layout_ribbon_groups(event: tk.Event) -> None:
            nonlocal ribbon_column_count
            column_count = 1 if event.width < 680 else 2 if event.width < 1200 else 4
            if column_count == ribbon_column_count:
                return
            ribbon_column_count = column_count
            wide_weights = (3, 1, 1, 2)
            for column in range(4):
                action_row.columnconfigure(
                    column,
                    weight=(wide_weights[column] if column_count == 4 else 1) if column < column_count else 0,
                    minsize=0,
                    uniform="" if column_count == 4 else ("toolbar_groups" if column < column_count else ""),
                )
            for index, wrapper in enumerate(self._ribbon_wrappers):
                wrapper.grid_configure(
                    row=index // column_count,
                    column=index % column_count,
                    padx=(0 if index % column_count == 0 else 6, 0),
                    pady=(0, 8) if index < len(self._ribbon_wrappers) - column_count else 0,
                )

        action_row.bind("<Configure>", layout_ribbon_groups)

        size_row = ttk.Frame(toolbar, style="Toolbar.TFrame")
        size_row.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        size_row.columnconfigure(5, weight=1)
        ttk.Label(size_row, text="라벨").grid(row=0, column=0, padx=(0, 10), sticky="w")
        ttk.Label(size_row, text="가로(mm)").grid(row=0, column=1, sticky="e")
        ttk.Spinbox(size_row, textvariable=self.width_var, from_=20, to=120, width=8, command=self.update_label_size).grid(row=0, column=2, padx=(5, 12), sticky="w")
        ttk.Label(size_row, text="세로(mm)").grid(row=0, column=3, sticky="e")
        ttk.Spinbox(size_row, textvariable=self.height_var, from_=15, to=120, width=8, command=self.update_label_size).grid(row=0, column=4, padx=(5, 12), sticky="w")
        size_apply_button = ttk.Button(size_row, text="크기 적용", command=self.update_label_size, style="Ribbon.TButton")
        center_button = ttk.Button(size_row, text="좌우 가운데 정렬", command=self.center_selected, style="Ribbon.TButton")
        vertical_center_button = ttk.Button(size_row, text="상하 가운데 정렬", command=self.center_selected_vertically, style="Ribbon.TButton")
        reset_button = ttk.Button(size_row, text="빈 라벨로 초기화", command=self.reset_template, style="Danger.TButton")
        size_apply_button.grid(row=1, column=0, columnspan=2, padx=(0, 6), pady=(8, 0), sticky="ew")
        center_button.grid(row=1, column=2, columnspan=2, padx=(0, 6), pady=(8, 0), sticky="ew")
        vertical_center_button.grid(row=2, column=0, columnspan=2, padx=(0, 6), pady=(6, 0), sticky="ew")
        reset_button.grid(row=2, column=2, columnspan=2, padx=(0, 6), pady=(6, 0), sticky="ew")

        size_row_compact: bool | None = None

        def layout_size_row(event: tk.Event) -> None:
            nonlocal size_row_compact
            compact = event.width < 900
            if compact == size_row_compact:
                return
            size_row_compact = compact
            if compact:
                size_apply_button.grid_configure(row=1, column=0, columnspan=2, padx=(0, 6), pady=(8, 0))
                center_button.grid_configure(row=1, column=2, columnspan=3, padx=0, pady=(8, 0))
                vertical_center_button.grid_configure(row=2, column=0, columnspan=2, padx=(0, 6), pady=(6, 0))
                reset_button.grid_configure(row=2, column=2, columnspan=3, padx=0, pady=(6, 0))
                return
            size_apply_button.grid_configure(row=1, column=0, columnspan=1, padx=(0, 6), pady=(8, 0))
            center_button.grid_configure(row=1, column=1, columnspan=1, padx=(0, 6), pady=(8, 0))
            vertical_center_button.grid_configure(row=1, column=2, columnspan=1, padx=(0, 6), pady=(8, 0))
            reset_button.grid_configure(row=1, column=3, columnspan=2, padx=0, pady=(8, 0))

        size_row.bind("<Configure>", layout_size_row)

    def _ribbon_group(self, parent: ttk.Frame, column: int, title: str) -> ttk.Frame:
        wrapper = ttk.Frame(parent, style="RibbonGroup.TFrame", padding=(0, 0, 10, 0))
        wrapper.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        self._ribbon_wrappers.append(wrapper)
        wrapper.columnconfigure(0, weight=1)
        body = ttk.Frame(wrapper, style="RibbonGroupBody.TFrame")
        body.grid(row=0, column=0, sticky="ew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        ttk.Label(wrapper, text=title, style="RibbonGroupTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 0))
        return body

    def _build_data_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        ttk.Label(parent, text="데이터 소스", style="SidePanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, textvariable=self.data_source_label_var, style="Status.TLabel").grid(row=0, column=0, sticky="e", padx=(0, 8))
        search_row = ttk.Frame(parent, style="SidePanel.TFrame")
        search_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        search_row.columnconfigure(1, weight=1)
        ttk.Label(search_row, text="DB 전체 검색", style="Status.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        search_entry = ttk.Entry(search_row, textvariable=self.data_search_var)
        search_entry.grid(row=0, column=1, sticky="ew")
        search_entry.bind("<Return>", self.search_data_source)
        search_entry.bind("<KeyRelease>", self.filter_data_source_on_key_release)
        ttk.Button(search_row, text="검색", command=self.search_data_source, style="Secondary.TButton").grid(row=0, column=2, sticky="e", padx=(8, 0))
        ttk.Button(search_row, text="초기화", command=self.clear_data_source_search, style="Secondary.TButton").grid(row=0, column=3, sticky="e", padx=(6, 0))
        ttk.Label(search_row, textvariable=self.data_search_hint_var, style="Status.TLabel").grid(row=1, column=1, columnspan=3, sticky="w", pady=(4, 0))
        action_row = ttk.Frame(parent, style="SidePanel.TFrame")
        action_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        action_row.columnconfigure(0, weight=1)
        tools_row = ttk.Frame(action_row, style="SidePanel.TFrame")
        tools_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(tools_row, textvariable=self.record_count_var, style="Status.TLabel").pack(side="left", padx=(0, 8))
        ttk.Button(tools_row, text="전체 선택", command=self.select_all_data_rows, style="Secondary.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(tools_row, text="선택 해제", command=self.clear_selected_data_rows, style="Secondary.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(tools_row, text="새로고침", command=self.reload_db, style="Secondary.TButton").pack(side="left")
        completion_row = ttk.Frame(action_row, style="SidePanel.TFrame")
        completion_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        completion_row.columnconfigure(0, weight=1)
        ttk.Label(completion_row, textvariable=self.queue_status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(completion_row, text="선택 완료", command=self.close_data_source_window, style="Primary.TButton").grid(row=0, column=1, sticky="e")

        columns = list(DB_HEADERS)
        data_table = ttk.Frame(parent, style="Surface.TFrame")
        data_table.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        data_table.rowconfigure(0, weight=1)
        data_table.columnconfigure(0, weight=1)
        self.data_tree = ttk.Treeview(data_table, columns=columns, show="tree headings", height=5, selectmode="browse")
        self.data_tree.heading("#0", text="선택")
        self.data_tree.column("#0", width=54, minwidth=54, stretch=False, anchor="center")
        column_labels = {field: FIELD_LABELS.get(field, field) for field in columns}
        for field in columns:
            self.data_tree.heading(field, text=column_labels[field])
            self.data_tree.column(field, width=118 if field != "item_name" else 210, minwidth=80, stretch=True)
        data_y_scroll = ttk.Scrollbar(data_table, orient="vertical", command=self.data_tree.yview)
        data_x_scroll = ttk.Scrollbar(data_table, orient="horizontal", command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=data_y_scroll.set, xscrollcommand=data_x_scroll.set)
        self.data_tree.grid(row=0, column=0, sticky="nsew")
        data_y_scroll.grid(row=0, column=1, sticky="ns")
        data_x_scroll.grid(row=1, column=0, sticky="ew")
        self.data_tree.bind("<<TreeviewSelect>>", lambda event: self.select_data_tree_row(event.widget))
        self.data_tree.bind("<Button-1>", self.toggle_data_tree_selection)
        self.data_tree.bind("<space>", self.toggle_focused_data_tree_selection)

    def open_data_source_window(self) -> None:
        if self.data_source_path is None:
            messagebox.showwarning("데이터 소스", "DB를 먼저 연결하세요.")
            return
        if self.data_source_window is not None and self.data_source_window.winfo_exists():
            self.data_source_window.deiconify()
            self.data_source_window.lift()
            self.data_source_window.focus_force()
            return
        dialog = tk.Toplevel(self)
        self.data_source_window = dialog
        dialog.title("데이터 소스 선택")
        set_initial_window_size(
            dialog,
            preferred_width=1180,
            preferred_height=720,
            minimum_width=760,
            minimum_height=520,
        )
        dialog.configure(bg=COLORS.background)
        dialog.transient(self)
        apply_window_icon(dialog, base_dir=self.base_dir, install_dir=self.install_dir)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        frame = ttk.Frame(dialog, style="SidePanel.TFrame", padding=(20, 18, 20, 18))
        frame.grid(row=0, column=0, sticky="nsew")
        self._build_data_panel(frame)

        def close_window() -> None:
            self.data_tree = None
            self.queue_tree = None
            self.data_source_window = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", close_window)
        dialog.bind("<Escape>", lambda _event: close_window())
        self.refresh_data_panel()

    def close_data_source_window(self) -> None:
        dialog = self.data_source_window
        if dialog is None or not dialog.winfo_exists():
            self.data_source_window = None
            self.data_tree = None
            return
        self.data_tree = None
        self.queue_tree = None
        self.data_source_window = None
        dialog.destroy()

    def _build_property_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="상품 DB", style="SidePanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text="상품 엑셀 연결 상태와 선택 개체의 열을 확인합니다.",
            style="SidePanelBody.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        connection_group = ttk.Frame(parent, style="PropertyGroup.TFrame")
        connection_group.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        connection_group.columnconfigure(0, weight=1)
        connection_group.columnconfigure(1, weight=1)
        ttk.Label(connection_group, text="상품 엑셀 상태", style="PropertyGroupTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Label(
            connection_group,
            textvariable=self.data_source_label_var,
            bg=COLORS.surface,
            fg=COLORS.text_secondary,
            font=TYPOGRAPHY.caption,
            justify="left",
            anchor="w",
            wraplength=270,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.disconnect_button = ttk.Button(connection_group, text="연결 해제", command=self.disconnect_data_source, style="Secondary.TButton")
        self.disconnect_button.grid(row=2, column=0, sticky="ew", padx=(0, 4))
        self.reload_button = ttk.Button(connection_group, text="엑셀 새로고침", command=self.reload_db, style="Tool.TButton")
        self.reload_button.grid(row=2, column=1, sticky="ew", padx=(4, 0))

        mapping_group = ttk.Frame(parent, style="PropertyGroup.TFrame")
        mapping_group.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        mapping_group.columnconfigure(0, weight=1)
        ttk.Label(mapping_group, text="선택 개체 DB 연결", style="PropertyGroupTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(mapping_group, textvariable=self.db_object_status_var, style="Status.TLabel", wraplength=270).grid(row=1, column=0, sticky="w", pady=(0, 6))
        self.field_label = ttk.Label(mapping_group, text="연결할 DB 열")
        self.field_label.grid(row=2, column=0, sticky="w", pady=(5, 3))
        self.field_combo = ttk.Combobox(mapping_group, textvariable=self.field_option_var, values=["연결 안 함"], state="disabled")
        self.field_combo.grid(row=3, column=0, sticky="ew")
        self.field_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_selected_data_field())
        ttk.Label(mapping_group, textvariable=self.db_mapping_help_var, style="Status.TLabel", wraplength=270).grid(row=4, column=0, sticky="w", pady=(6, 0))

        preview_group = ttk.Frame(parent, style="PropertyGroup.TFrame")
        preview_group.grid(row=4, column=0, sticky="nsew")
        preview_group.columnconfigure(0, weight=1)
        ttk.Label(preview_group, text="현재 행 값", style="PropertyGroupTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        preview_table = ttk.Frame(preview_group, style="Surface.TFrame")
        preview_table.grid(row=1, column=0, sticky="nsew")
        preview_table.columnconfigure(0, weight=1)
        preview_table.rowconfigure(0, weight=1)
        self.db_preview_tree = ttk.Treeview(preview_table, columns=("field", "value"), show="headings", height=7, selectmode="none")
        self.db_preview_tree.heading("field", text="DB 열")
        self.db_preview_tree.heading("value", text="현재 값")
        self.db_preview_tree.column("field", width=92, minwidth=70, stretch=False)
        self.db_preview_tree.column("value", width=148, minwidth=90, stretch=True)
        preview_scroll = ttk.Scrollbar(preview_table, orient="vertical", command=self.db_preview_tree.yview)
        self.db_preview_tree.configure(yscrollcommand=preview_scroll.set)
        self.db_preview_tree.grid(row=0, column=0, sticky="nsew")
        preview_scroll.grid(row=0, column=1, sticky="ns")
        self.property_widgets = {}

    def toggle_side_panel(self, side: str) -> None:
        if side == "tools":
            self.tools_panel_visible = not self.tools_panel_visible
            card = self._tools_card
            column = 0
            visible = self.tools_panel_visible
            self.tools_panel_text_var.set("도구 숨기기" if visible else "도구 보이기")
        else:
            self.data_panel_visible = not self.data_panel_visible
            card = self._properties_card
            column = 2
            visible = self.data_panel_visible
            self.data_panel_text_var.set("DB 숨기기" if visible else "DB 보이기")
        if visible:
            card.grid()
        else:
            card.grid_remove()
        compact = self._workbench_body.winfo_width() < 1160
        minsize = (290 if compact else 330) if side == "tools" else (280 if compact else 300)
        self._workbench_body.columnconfigure(column, minsize=minsize if visible else 0)
        self.update_idletasks()
        self.redraw()

    def _load_initial_template(self) -> dict[str, object]:
        if self.template_path.exists():
            try:
                if self.template_path.name.casefold() == "default_label.json":
                    template, recovery_path = ensure_blank_default_template(self.template_path, self.config_path)
                    if recovery_path is not None:
                        self._initial_template_notice = f"기존 기본 템플릿 디자인을 복구 파일로 보존했습니다.\n\n{recovery_path}"
                    return template
                template = load_template_file(self.template_path)
                if self.initial_template_path is None:
                    template = apply_configured_label_size(template, self.config_path)
                    return template
                return template
            except Exception as exc:
                self._initial_template_error = f"{self.template_path}\n\n{exc}"
        elif self.initial_template_path is not None:
            self._initial_template_error = f"파일을 찾을 수 없습니다.\n\n{self.template_path}"
        template = default_template_from_config(self.config_path)
        if self.initial_template_path is None:
            self._save_initial_default_template(template)
        return template

    def _save_initial_default_template(self, template: dict[str, object]) -> None:
        try:
            _atomic_write_json(self.template_path, template)
        except OSError:
            pass

    def _current_payload_signature(self) -> str:
        return _template_signature(self.template.get("label", {}), self.elements)

    def _history_snapshot(self) -> dict[str, object]:
        return {
            "label": copy.deepcopy(self.template["label"]),
            "elements": copy.deepcopy(self.elements),
            "selected_id": self.selected_id if hasattr(self, "selected_id") else None,
            "selected_ids": sorted(self.__dict__.get("selected_ids", set())),
        }

    def _reset_history(self) -> None:
        self._history = [self._history_snapshot()]
        self._history_index = 0

    def _record_history(self) -> None:
        if not hasattr(self, "_history") or self._history_restoring or self._history_suspended or self.drag_state:
            return
        snapshot = self._history_snapshot()
        current = self._history[self._history_index]
        if _template_signature(snapshot["label"], snapshot["elements"]) == _template_signature(current["label"], current["elements"]):
            return
        del self._history[self._history_index + 1:]
        self._history.append(snapshot)
        if len(self._history) > 51:
            self._history.pop(0)
        self._history_index = len(self._history) - 1
        self._save_recovery()

    def _restore_history(self, index: int) -> None:
        if index < 0 or index >= len(self._history):
            return
        self._history_restoring = True
        try:
            self._history_index = index
            snapshot = self._history[index]
            self.template["label"] = copy.deepcopy(snapshot["label"])
            self.elements = copy.deepcopy(snapshot["elements"])  # type: ignore[assignment]
            self.selected_id = snapshot["selected_id"]  # type: ignore[assignment]
            self.selected_ids = set(snapshot.get("selected_ids", []))  # type: ignore[arg-type]
            self._load_values_to_controls()
            self.load_selected_properties()
            self.redraw()
        finally:
            self._history_restoring = False
        self._save_recovery()

    def undo(self) -> None:
        self._record_history()
        if self._history_index > 0:
            self._restore_history(self._history_index - 1)
            self.status_var.set("실행취소했습니다.")

    def redo(self) -> None:
        if self._history_index + 1 < len(self._history):
            self._restore_history(self._history_index + 1)
            self.status_var.set("다시실행했습니다.")

    def _on_undo_shortcut(self, event: tk.Event) -> str | None:
        if str(event.widget.winfo_class()) in {"Entry", "TEntry", "TSpinbox", "TCombobox", "Spinbox", "Text"}:
            return None
        self.undo()
        return "break"

    def _on_redo_shortcut(self, event: tk.Event) -> str | None:
        if str(event.widget.winfo_class()) in {"Entry", "TEntry", "TSpinbox", "TCombobox", "Spinbox", "Text"}:
            return None
        self.redo()
        return "break"

    def _recovery_path(self, template_path: Path | None = None) -> Path:
        identity = hashlib.sha256(str((template_path or self.template_path).resolve()).encode("utf-8")).hexdigest()[:16]
        return self.base_dir / "out" / f".designer_recovery_{identity}.json"

    def _clear_recovery(self, template_path: Path | None = None) -> None:
        if "base_dir" not in self.__dict__ or "template_path" not in self.__dict__:
            return
        self._recovery_path(template_path).unlink(missing_ok=True)

    def _save_recovery(self) -> None:
        if not self._has_unsaved_changes():
            self._clear_recovery()
            return
        try:
            _atomic_write_json(
                self._recovery_path(),
                {"version": 1, "template_path": str(self.template_path.resolve()), "snapshot": self._history_snapshot()},
            )
        except OSError as exc:
            if not self._recovery_write_failed:
                self._recovery_write_failed = True
                messagebox.showwarning("자동 복구 저장 실패", f"자동 복구 파일을 저장하지 못했습니다. 직접 저장하세요.\n{exc}", parent=self)

    def _offer_recovery(self) -> None:
        if "base_dir" not in self.__dict__ or "template_path" not in self.__dict__:
            return
        path = self._recovery_path()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("template_path") != str(self.template_path.resolve()):
                return
            snapshot = payload["snapshot"]
            recovered = normalize_template({"label": snapshot["label"], "elements": snapshot["elements"]})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showwarning("자동 복구 파일 오류", f"복구 파일을 읽을 수 없습니다. 기존 라벨은 유지됩니다.\n{exc}", parent=self)
            return
        if _template_signature(snapshot["label"], snapshot["elements"]) == self._saved_payload_signature:
            self._clear_recovery()
            return
        if not messagebox.askyesno(
            "저장 전 작업 복구",
            "이 라벨의 저장 전 작업이 남아 있습니다. 화면에 복구할까요?\n기존 저장 파일은 덮어쓰지 않습니다.",
            parent=self,
        ):
            self._clear_recovery()
            return
        self.template = recovered
        self.elements = list(recovered["elements"])  # type: ignore[arg-type]
        selected_id = snapshot.get("selected_id")
        self.selected_id = selected_id if any(str(element.get("id")) == selected_id for element in self.elements) else None
        self._reset_history()
        self._load_values_to_controls()
        self.load_selected_properties()
        self.redraw()
        self.status_var.set("저장 전 작업을 화면에 복구했습니다. 확인 후 직접 저장하세요.")

    def _has_unsaved_changes(self) -> bool:
        saved = self.__dict__.get("_saved_payload_signature")
        return saved is not None and self._current_payload_signature() != saved

    def _confirm_save_changes(self, action: str) -> bool:
        if not self._has_unsaved_changes():
            return True
        answer = messagebox.askyesnocancel(
            "저장하지 않은 변경사항",
            f"{action} 저장하지 않은 변경사항이 있습니다.\n\n저장할까요?",
            parent=self,
        )
        if answer is None:
            return False
        if answer is False:
            return True
        return self.save_template()

    def request_close(self) -> None:
        if self._confirm_save_changes("프로그램을 종료하기 전에"):
            self._clear_recovery()
            self.destroy()

    def _load_db_rows(self) -> list[dict[str, str]]:
        if self.data_source_path is None:
            return []
        return load_db_rows(self.data_source_path)

    def _data_source_display_name(self) -> str:
        if self.data_source_path is None:
            return "상품 엑셀 미연결 · 상단에서 연결하세요"
        try:
            name = str(self.data_source_path.relative_to(self.base_dir))
        except ValueError:
            name = self.data_source_path.name
        total = len(self.__dict__.get("db_rows", []))
        visible = len(self._visible_data_indexes())
        count = f"{visible}/{total}건" if visible != total else f"{total}건"
        return f"DB · {name} · {count}"

    def _visible_data_indexes(self) -> list[int]:
        rows = self.__dict__.get("db_rows", [])
        indexes = self.__dict__.get("visible_data_indexes")
        if indexes is None:
            return list(range(len(rows)))
        return [index for index in indexes if 0 <= index < len(rows)]

    def refresh_sample_options(self) -> None:
        values = []
        row_indexes = self._visible_data_indexes()
        for position, index in enumerate(row_indexes, start=1):
            row = self.db_rows[index]
            row_values = [str(row.get(header, "")).strip() for header in self.data_source_headers]
            preview_values = [value for value in row_values if value][:2]
            values.append(f"{position}. {' / '.join(preview_values)}" if preview_values else f"{position}. 빈 데이터")
        self.sample_combo_values = values
        self.sample_combo_row_indexes = row_indexes
        if self.sample_combo is not None:
            self.sample_combo.configure(values=values)
        db_sample_combo = getattr(self, "db_sample_combo", None)
        if db_sample_combo is not None:
            db_sample_combo.configure(values=values, state="readonly" if values else "disabled")
        if values:
            preview_index = next((index for index in row_indexes if self.db_rows[index] is self.preview_row), row_indexes[0])
            self.sample_var.set(values[row_indexes.index(preview_index)])
            if self.sample_combo is not None:
                self.sample_combo.grid()
        else:
            self.sample_var.set("")
            if self.sample_combo is not None:
                self.sample_combo.grid_remove()
        self._refresh_field_options()
        self.refresh_data_panel()

    def _refresh_field_options(self) -> None:
        headers = tuple(getattr(self, "data_source_headers", ()))
        option_to_key, key_to_option = _data_field_option_maps(headers)
        self.field_option_to_key = option_to_key
        self.field_key_to_option = key_to_option
        combo = getattr(self, "field_combo", None)
        if combo is not None:
            combo.configure(values=list(option_to_key))
        selected = self.selected_element() if hasattr(self, "elements") else None
        field = str(selected.get("field", "")) if selected is not None else ""
        field_option_var = getattr(self, "field_option_var", None)
        if field_option_var is not None:
            field_option_var.set(key_to_option.get(field, "연결 안 함"))
        self._update_field_control_visibility()

    def _update_field_control_visibility(self) -> None:
        label = getattr(self, "field_label", None)
        combo = getattr(self, "field_combo", None)
        if label is None or combo is None:
            return
        element = self.selected_element()
        element_type = str(element.get("type", "")) if element is not None else ""
        connected = self.data_source_path is not None and bool(self.db_rows)
        object_status_var = getattr(self, "db_object_status_var", None)
        mapping_help_var = getattr(self, "db_mapping_help_var", None)
        if connected and element_type in DB_MAPPABLE_ELEMENT_TYPES:
            combo.configure(state="readonly")
            if object_status_var is not None:
                object_status_var.set(f"{ELEMENT_TYPES.get(element_type, '개체')} 개체 선택됨")
            if mapping_help_var is not None:
                mapping_help_var.set("DB 열을 선택하면 이 개체가 해당 열의 문자열 값으로 출력됩니다.")
            return
        combo.configure(state="disabled")
        if object_status_var is not None:
            if element is None:
                object_status_var.set("개체를 선택하세요.")
            else:
                object_status_var.set(f"{ELEMENT_TYPES.get(element_type, '개체')} 개체 선택됨")
        if mapping_help_var is not None:
            if not connected:
                mapping_help_var.set("DB를 연결하면 텍스트·바코드·QR 개체에 열을 지정할 수 있습니다.")
            else:
                mapping_help_var.set("텍스트·여러줄·1D 바코드·QR 개체에서 DB 열을 연결할 수 있습니다.")

    def _apply_selected_data_field(self) -> None:
        element = self.selected_element()
        if element is None or str(element.get("type", "")) not in DB_MAPPABLE_ELEMENT_TYPES:
            return
        element_type = str(element.get("type", ""))
        element_name = ELEMENT_TYPES.get(element_type, "개체")
        option = self.field_option_var.get()
        field = self.field_option_to_key.get(option, "")
        previous_field = str(element.get("field", ""))
        previous_token = "{{" + previous_field + "}}" if previous_field else ""
        element["field"] = field
        if field:
            element["text"] = "{{" + field + "}}"
            status = f"{element_name}을(를) DB 열 '{FIELD_LABELS.get(field, field)}'에 연결했습니다."
        else:
            if previous_token and str(element.get("text", "")) == previous_token:
                fallback = BARCODE_FALLBACK_VALUE if element_type in {"barcode", "qr"} else "새 텍스트"
                element["text"] = str(self.preview_row.get(previous_field, "")) or fallback
            status = f"{element_name}의 DB 연결을 해제했습니다."
        self.field_var.set(field)
        self.text_var.set(str(element.get("text", "")))
        self.redraw()
        self.status_var.set(status)

    def _walk_widgets(self, widget: tk.Widget) -> list[tk.Widget]:
        widgets = [widget]
        for child in widget.winfo_children():
            widgets.extend(self._walk_widgets(child))
        return widgets

    def select_sample_row(self) -> None:
        selected = self.sample_var.get()
        try:
            position = int(selected.split(".", 1)[0]) - 1
        except ValueError:
            position = 0
        row_indexes = self.__dict__.get("sample_combo_row_indexes", self._visible_data_indexes())
        index = row_indexes[position] if 0 <= position < len(row_indexes) else 0
        self._select_data_index(index, update_tree=True)
        self.redraw()

    def search_data_source(self, _event: tk.Event | None = None) -> str:
        query = self.data_search_var.get().strip()
        visible_indexes = _filter_data_source_row_indexes(
            self.db_rows,
            tuple(getattr(self, "data_source_headers", ())),
            query,
        )
        self.visible_data_indexes = visible_indexes
        if visible_indexes and not any(self.preview_row is self.db_rows[index] for index in visible_indexes):
            self.preview_row = self.db_rows[visible_indexes[0]]
        total = len(self.db_rows)
        if query:
            self.data_search_hint_var.set(f"'{query}' 검색 결과 {len(visible_indexes)} / {total}건")
            self.status_var.set(f"DB 전체 검색: {len(visible_indexes)} / {total}건 표시")
        else:
            self.data_search_hint_var.set(f"전체 {total}건 표시")
            self.status_var.set(f"DB 전체 {total}건을 표시합니다.")
        self.refresh_sample_options()
        self.redraw()
        return "break"

    def filter_data_source_on_key_release(self, _event: tk.Event | None = None) -> None:
        self.search_data_source()

    def clear_data_source_search(self) -> None:
        self.data_search_var.set("")
        self.search_data_source()

    def _select_data_index(self, index: int, *, update_tree: bool = False) -> None:
        if 0 <= index < len(self.db_rows):
            self.preview_row = self.db_rows[index]
            if update_tree:
                iid = str(index)
                for tree in (self.__dict__.get("db_row_tree"), self.__dict__.get("data_tree")):
                    if tree is not None and tree.exists(iid):
                        tree.selection_set(iid)
                        tree.see(iid)
        self.refresh_data_panel()

    def connect_data_source(self) -> None:
        source = filedialog.askopenfilename(
            parent=self,
            initialdir=self.base_dir,
            title="상품 엑셀 연결",
            filetypes=[("Excel 통합 문서", "*.xlsx *.xlsm")],
        )
        if not source:
            return
        self.connect_data_source_path(Path(source))

    def _start_background_job(
        self,
        title: str,
        work: Callable[[], object],
        apply_result: Callable[[object], None],
    ) -> None:
        if self.__dict__.get("_active_background_job") is not None:
            messagebox.showinfo("작업 진행 중", "현재 작업이 끝난 뒤 다시 시도하세요.", parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.resizable(False, False)
        ttk.Label(dialog, text=f"{title} 중입니다. 창을 계속 사용할 수 있습니다.", padding=(18, 16, 18, 8)).pack()
        progress = ttk.Progressbar(dialog, mode="indeterminate", length=320)
        progress.pack(padx=18, pady=(0, 10))
        progress.start(12)
        result_queue: Queue[tuple[bool, object]] = Queue(maxsize=1)
        job: dict[str, object] = {"cancelled": False, "title": title}
        self._active_background_job = job

        def cancel() -> None:
            job["cancelled"] = True
            self.status_var.set(f"{title} 취소 요청 · 완료된 결과는 적용하지 않습니다.")
            dialog.destroy()

        ttk.Button(dialog, text="결과 적용 취소", command=cancel, style="Secondary.TButton").pack(pady=(0, 16))
        dialog.protocol("WM_DELETE_WINDOW", cancel)

        def worker() -> None:
            try:
                result_queue.put((True, work()))
            except Exception as exc:
                result_queue.put((False, exc))

        threading.Thread(target=worker, name="designer-background-job", daemon=True).start()

        def poll() -> None:
            try:
                success, result = result_queue.get_nowait()
            except Empty:
                if self.winfo_exists():
                    self.after(80, poll)
                return
            self._active_background_job = None
            if dialog.winfo_exists():
                dialog.destroy()
            if job["cancelled"]:
                self.status_var.set(f"{title} 결과 적용을 취소했습니다.")
                return
            if not success:
                messagebox.showerror(f"{title} 실패", str(result), parent=self)
                self.status_var.set(f"{title} 실패 · 기존 작업은 유지합니다.")
                return
            try:
                apply_result(result)
            except Exception as exc:
                messagebox.showerror(f"{title} 실패", str(exc), parent=self)

        self.after(80, poll)

    def connect_data_source_async(self) -> None:
        source = filedialog.askopenfilename(
            parent=self,
            initialdir=self.base_dir,
            title="상품 엑셀 연결",
            filetypes=[("Excel 통합 문서", "*.xlsx *.xlsm")],
        )
        if not source:
            return
        candidate = Path(source)
        document_path = self.__dict__.get("template_path")
        document_signature = (
            self._current_payload_signature()
            if "template" in self.__dict__ and "elements" in self.__dict__
            else None
        )
        data_source_path = self.__dict__.get("data_source_path")
        data_rows = self.__dict__.get("db_rows")
        selected_indexes = frozenset(self.__dict__.get("selected_data_indexes", set()))
        context_version = self.__dict__.get("_data_context_version", 0)

        def read_excel() -> object:
            if not candidate.is_file():
                raise FileNotFoundError(f"상품 엑셀을 찾을 수 없습니다: {candidate.name}")
            return load_db_source(candidate)

        def apply_rows(result: object) -> None:
            current_signature = (
                self._current_payload_signature()
                if "template" in self.__dict__ and "elements" in self.__dict__
                else None
            )
            if (
                self.__dict__.get("template_path") != document_path
                or current_signature != document_signature
                or self.__dict__.get("data_source_path") != data_source_path
                or self.__dict__.get("db_rows") is not data_rows
                or frozenset(self.__dict__.get("selected_data_indexes", set())) != selected_indexes
                or self.__dict__.get("_data_context_version", 0) != context_version
            ):
                self.status_var.set("상품 엑셀 읽기 완료 · 그 사이 라벨이나 출력 선택이 바뀌어 결과를 적용하지 않았습니다.")
                return
            rows, headers = result  # type: ignore[misc]
            self.data_source_path = candidate
            self._data_context_version = context_version + 1
            width, height = self._apply_loaded_db_rows(rows, headers)
            self.status_var.set(f"상품 엑셀 연결 완료: {candidate.name} · 라벨 {width:g}×{height:g}mm")

        self._start_background_job("상품 엑셀 읽기", read_excel, apply_rows)

    def connect_data_source_path(self, candidate: Path) -> bool:
        try:
            rows, headers = load_db_source(candidate)
        except Exception as exc:
            messagebox.showerror("상품 엑셀 연결 실패", str(exc))
            self.status_var.set("상품 엑셀 연결 실패 · 기존 데이터는 유지합니다.")
            return False
        self.data_source_path = candidate
        self._data_context_version = self.__dict__.get("_data_context_version", 0) + 1
        width, height = self._apply_loaded_db_rows(rows, headers)
        self.status_var.set(
            f"상품 엑셀 연결 완료: {self._data_source_display_name()} · 라벨 {width:g}×{height:g}mm"
        )
        return True

    def disconnect_data_source(self) -> None:
        if getattr(self, "data_source_window", None) is not None:
            self.close_data_source_window()
        self.data_source_path = None
        self._data_context_version = self.__dict__.get("_data_context_version", 0) + 1
        self.db_rows = []
        self.data_source_headers = ()
        self.visible_data_indexes = []
        self.selected_data_indexes = set()
        self.preview_row = _empty_row()
        hint_var = self.__dict__.get("data_search_hint_var")
        if hint_var is not None:
            hint_var.set("품목명, 바코드, 상품코드, 판매가 등 DB 전체 검색")
        self.refresh_sample_options()
        self.redraw()
        self.status_var.set("DB 연결을 해제했습니다.")

    def reload_db(self) -> None:
        if self.data_source_path is None:
            self.status_var.set("DB 연결 후 새로고침할 수 있습니다.")
            return
        source_path = Path(self.data_source_path)
        if not source_path.is_file():
            messagebox.showerror("DB 새로고침 실패", "연결된 DB 파일을 찾을 수 없습니다. 기존 데이터를 유지합니다.")
            self.status_var.set("DB 새로고침 실패 · 기존 데이터와 출력 선택을 유지합니다.")
            return
        previous_rows = self.db_rows
        previous_headers = self.data_source_headers
        previous_visible_indexes = list(self._visible_data_indexes())
        previous_indexes = set(self.selected_data_indexes)
        previous_preview = self.preview_row
        previous_label = dict(self.template.get("label", {})) if isinstance(self.template.get("label"), dict) else None
        try:
            rows, headers = load_db_source(source_path)
            width, height = self._apply_loaded_db_rows(rows, headers)
        except Exception as exc:
            self.db_rows = previous_rows
            self.data_source_headers = previous_headers
            self.visible_data_indexes = previous_visible_indexes
            self.selected_data_indexes = previous_indexes
            self.preview_row = previous_preview
            if previous_label is not None:
                self.template["label"] = previous_label
            messagebox.showerror("DB 새로고침 실패", str(exc))
            self.status_var.set("DB 새로고침 실패 · 기존 데이터와 출력 선택을 유지합니다.")
            self.refresh_sample_options()
            self.redraw()
            return
        self.status_var.set(
            f"DB 데이터 {len(self.db_rows)}건을 다시 불러왔습니다. · 템플릿 {width:g}×{height:g}mm"
        )

    def _apply_loaded_db_rows(
        self,
        rows: list[dict[str, str]],
        headers: tuple[str, ...] | None = None,
    ) -> tuple[int | float, int | float]:
        self.db_rows = rows
        self.data_source_headers = tuple(headers) if headers is not None else _db_headers_from_rows(rows)
        self.visible_data_indexes = list(range(len(self.db_rows)))
        search_var = self.__dict__.get("data_search_var")
        if search_var is not None:
            search_var.set("")
        self.selected_data_indexes = set()
        self.preview_row = self.db_rows[0] if self.db_rows else _empty_row()
        hint_var = self.__dict__.get("data_search_hint_var")
        if hint_var is not None:
            hint_var.set(f"전체 {len(self.db_rows)}건 표시")
        width, height = self._validate_template_size_for_data_source()
        self.refresh_sample_options()
        # Showing the DB panel changes the canvas height. Let Tk settle the layout
        # before recalculating the label scale so the template stays fully visible.
        update_layout = self.__dict__.get("update_idletasks")
        if not callable(update_layout) and self.__dict__.get("tk") is not None:
            update_layout = self.update_idletasks
        if callable(update_layout):
            update_layout()
        self.redraw()
        return width, height

    def _validate_template_size_for_data_source(self) -> tuple[int | float, int | float]:
        fallback_width, fallback_height = configured_label_size(self.config_path)
        label = self.template.get("label") if isinstance(self.template.get("label"), dict) else {}
        width = _normalize_label_mm(label.get("width_mm"), fallback_width)  # type: ignore[union-attr]
        height = _normalize_label_mm(label.get("height_mm"), fallback_height)  # type: ignore[union-attr]
        self.template["label"] = {"width_mm": width, "height_mm": height}
        width_var = self.__dict__.get("width_var")
        if width_var is not None:
            width_var.set(_format_mm_value(width))
        height_var = self.__dict__.get("height_var")
        if height_var is not None:
            height_var.set(_format_mm_value(height))
        return width, height

    def _configure_data_tree_columns(self) -> None:
        if self.data_tree is None:
            return
        headers = tuple(getattr(self, "data_source_headers", ()))
        self.data_tree.configure(columns=headers)
        for field in headers:
            label = FIELD_LABELS.get(field, field)
            width = 210 if field == "item_name" else max(118, min(220, len(label) * 16 + 54))
            self.data_tree.heading(field, text=label)
            self.data_tree.column(field, width=width, minwidth=80, stretch=True)

    def refresh_data_panel(self) -> None:
        self._refreshing_data_panel = True
        connected = self.data_source_path is not None
        data_source_button = self.__dict__.get("data_source_button")
        if data_source_button is not None:
            data_source_button.configure(state="normal" if connected else "disabled")
        for name in ("disconnect_button", "reload_button"):
            button = self.__dict__.get(name)
            if button is not None:
                button.configure(state="normal" if connected else "disabled")
        primary_print_text_var = self.__dict__.get("primary_print_text_var")
        if primary_print_text_var is not None:
            primary_print_text_var.set("선택 인쇄" if connected else "인쇄")
        data_source_label_var = self.__dict__.get("data_source_label_var")
        if data_source_label_var is not None:
            data_source_label_var.set(self._data_source_display_name())
        record_count_var = self.__dict__.get("record_count_var")
        if record_count_var is not None:
            record_count_var.set(f"{len(self._visible_data_indexes())} / {len(self.db_rows)}건")
        try:
            db_preview_tree = self.__dict__.get("db_preview_tree")
            if db_preview_tree is not None:
                db_preview_tree.delete(*db_preview_tree.get_children())
                if connected and self.data_source_headers:
                    for index, field in enumerate(self.data_source_headers):
                        label = FIELD_LABELS.get(field, field)
                        value = str(self.preview_row.get(field, ""))
                        db_preview_tree.insert("", "end", iid=f"db-{index}", values=(label, value))
                else:
                    db_preview_tree.insert("", "end", iid="db-empty", values=("연결 전", "상단에서 상품 엑셀을 연결하세요"))
            db_row_tree = self.__dict__.get("db_row_tree")
            if db_row_tree is not None:
                db_row_tree.delete(*db_row_tree.get_children())
                for index in self._visible_data_indexes():
                    row = self.db_rows[index]
                    row_values = [str(row.get(header, "")) for header in self.data_source_headers]
                    summary_values = [value for value in row_values if value][:2]
                    summary = " / ".join(summary_values) if summary_values else "빈 데이터"
                    checkbox = "☑" if index in self.selected_data_indexes else "☐"
                    db_row_tree.insert("", "end", iid=str(index), text=checkbox, values=(index + 1, summary))
                preview_index = next((index for index, row in enumerate(self.db_rows) if row is self.preview_row), None)
                if preview_index is not None and db_row_tree.exists(str(preview_index)):
                    db_row_tree.selection_set(str(preview_index))
                    db_row_tree.see(str(preview_index))
            if self.data_tree is not None:
                self._configure_data_tree_columns()
                self.data_tree.delete(*self.data_tree.get_children())
                for index in self._visible_data_indexes():
                    row = self.db_rows[index]
                    values = [str(row.get(header, "")) for header in self.data_source_headers]
                    checkbox = "☑" if index in self.selected_data_indexes else "☐"
                    self.data_tree.insert("", "end", iid=str(index), text=checkbox, values=values)
                preview_index = next((index for index, row in enumerate(self.db_rows) if row is self.preview_row), None)
                if preview_index is not None and self.data_tree.exists(str(preview_index)):
                    self.data_tree.selection_set(str(preview_index))
            if self.queue_tree is not None:
                self.queue_tree.delete(*self.queue_tree.get_children())
                selected_rows = self.selected_data_rows(only_selected=True)
                for index, row in enumerate(selected_rows):
                    name = row.get("item_name") or row.get("item_code") or row.get("barcode") or f"작업 {index + 1}"
                    qty = str(row.get("print_qty", "")).strip() or "1"
                    self.queue_tree.insert("", "end", values=(name, qty, "대기"))
            queue_status_var = self.__dict__.get("queue_status_var")
            if queue_status_var is not None:
                queue_status_var.set(f"선택 {len(self.selected_data_rows(only_selected=True))}건 / 전체 {len(self.db_rows)}건")
        finally:
            self._refreshing_data_panel = False

    def select_data_tree_row(self, tree: ttk.Treeview | None = None) -> None:
        if self._refreshing_data_panel:
            return
        tree = tree or self.__dict__.get("db_row_tree") or self.__dict__.get("data_tree")
        if tree is None:
            return
        selected = tree.selection()
        if not selected:
            return
        try:
            preview_index = int(selected[0])
        except ValueError:
            return
        if 0 <= preview_index < len(self.db_rows):
            if self.preview_row is self.db_rows[preview_index]:
                return
            self.preview_row = self.db_rows[preview_index]
            if self.sample_combo_values:
                self.sample_var.set(self.sample_combo_values[preview_index])
        self.refresh_data_panel()
        self.redraw()

    def toggle_data_tree_selection(self, event: tk.Event) -> str | None:
        if self._refreshing_data_panel:
            return None
        tree = getattr(event, "widget", None) or self.__dict__.get("db_row_tree") or self.__dict__.get("data_tree")
        if tree is None:
            return None
        if tree.identify_column(event.x) != "#0":
            return None
        iid = tree.identify_row(event.y)
        if not iid:
            return "break"
        try:
            index = int(iid)
        except ValueError:
            return "break"
        if not 0 <= index < len(self.db_rows):
            return "break"
        self._toggle_data_index(index)
        return "break"

    def toggle_focused_data_tree_selection(self, event: tk.Event) -> str:
        if self._refreshing_data_panel:
            return "break"
        tree = getattr(event, "widget", None) or self.__dict__.get("db_row_tree") or self.__dict__.get("data_tree")
        if tree is None:
            return "break"
        selected = tree.selection()
        if not selected:
            return "break"
        try:
            index = int(selected[0])
        except ValueError:
            return "break"
        if 0 <= index < len(self.db_rows):
            self._toggle_data_index(index)
        return "break"

    def _toggle_data_index(self, index: int) -> None:
        if index in self.selected_data_indexes:
            self.selected_data_indexes.remove(index)
        else:
            self.selected_data_indexes.add(index)
        self.refresh_data_panel()
        self.status_var.set(f"출력 선택 {len(self.selected_data_indexes)}건")

    def select_all_data_rows(self) -> None:
        if self.data_source_path is None:
            self.status_var.set("DB 연결 후 데이터를 선택할 수 있습니다.")
            return
        self.selected_data_indexes.update(self._visible_data_indexes())
        self.refresh_data_panel()
        self.status_var.set(f"현재 표시된 데이터를 선택했습니다. 전체 선택 {len(self.selected_data_indexes)}건")

    def clear_selected_data_rows(self) -> None:
        self.selected_data_indexes = set()
        self.refresh_data_panel()
        self.status_var.set("출력 대상 선택을 해제했습니다.")

    def selected_data_rows(self, *, only_selected: bool = False) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for index in sorted(self.selected_data_indexes):
            if 0 <= index < len(self.db_rows):
                rows.append(self.db_rows[index])
        if rows:
            return rows
        if only_selected:
            return []
        return [self.preview_row] if self.preview_row else [_empty_row()]

    def _load_values_to_controls(self) -> None:
        label = self.template["label"]  # type: ignore[index]
        self.width_var.set(_format_mm_value(label["width_mm"]))  # type: ignore[index]
        self.height_var.set(_format_mm_value(label["height_mm"]))  # type: ignore[index]

    def redraw(self) -> None:
        self._record_history()
        self._update_document_state()
        self.canvas.delete("all")
        self.canvas_images.clear()
        label = self.template["label"]  # type: ignore[index]
        width_mm = float(label["width_mm"])  # type: ignore[index]
        height_mm = float(label["height_mm"])  # type: ignore[index]
        fit_scale, origin_x, origin_y, width, height = _calculate_canvas_label_layout(
            self.canvas.winfo_width(),
            self.canvas.winfo_height(),
            width_mm,
            height_mm,
        )
        zoom_factor = float(self.__dict__.get("zoom_factor", 1.0))
        self.scale = fit_scale * zoom_factor
        if zoom_factor != 1.0:
            width = width_mm * self.scale
            height = height_mm * self.scale
            origin_x = max(RULER_SIZE + 16, (self.canvas.winfo_width() - width) / 2)
            origin_y = max(RULER_SIZE + 16, (self.canvas.winfo_height() - height) / 2)
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.label_width_px = width
        self.label_height_px = height

        self._draw_rulers(origin_x, origin_y, width, height)
        self.canvas.create_rectangle(
            origin_x + LABEL_SHADOW_OFFSET,
            origin_y + LABEL_SHADOW_OFFSET,
            origin_x + width + LABEL_SHADOW_OFFSET,
            origin_y + height + LABEL_SHADOW_OFFSET,
            fill=LABEL_SHADOW_COLOR,
            outline="",
        )
        self._create_round_rect(
            origin_x,
            origin_y,
            origin_x + width,
            origin_y + height,
            radius=LABEL_CORNER_RADIUS,
            fill=LABEL_SURFACE_COLOR,
            outline=LABEL_OUTLINE_COLOR,
            width=1,
        )
        self._draw_grid(origin_x, origin_y, width, height)

        for element in self._drawing_elements():
            self.draw_element(element)
        if callable(getattr(self.canvas, "configure", None)):
            self.canvas.configure(scrollregion=(
                0, 0,
                max(self.canvas.winfo_width(), origin_x + width + LABEL_SHADOW_OFFSET + 20),
                max(self.canvas.winfo_height(), origin_y + height + LABEL_SHADOW_OFFSET + 20),
            ))

    def change_zoom(self, direction: int) -> None:
        levels = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
        current = float(self.__dict__.get("zoom_factor", 1.0))
        index = min(range(len(levels)), key=lambda item: abs(levels[item] - current))
        self.zoom_factor = levels[max(0, min(len(levels) - 1, index + direction))]
        self.zoom_display_var.set(f"{round(self.zoom_factor * 100)}% · 맞춤 기준")
        self.redraw()

    def fit_zoom(self) -> None:
        self.zoom_factor = 1.0
        self.zoom_display_var.set("화면 맞춤")
        self.redraw()

    def _drawing_elements(self) -> list[dict[str, object]]:
        behind = [element for element in self.elements if str(element.get("arrange", "normal")) == "behind"]
        normal = [element for element in self.elements if str(element.get("arrange", "normal")) not in {"behind", "front"}]
        front = [element for element in self.elements if str(element.get("arrange", "normal")) == "front"]
        return behind + normal + front

    def _fit_canvas_scale(self, width_mm: float, height_mm: float) -> float:
        scale, _origin_x, _origin_y, _width, _height = _calculate_canvas_label_layout(
            self.canvas.winfo_width(),
            self.canvas.winfo_height(),
            width_mm,
            height_mm,
        )
        return scale

    def on_canvas_configure(self, _event: tk.Event) -> None:
        if self._redraw_after_id is not None:
            self.after_cancel(self._redraw_after_id)
        self._redraw_after_id = self.after(60, self._redraw_after_resize)

    def _redraw_after_resize(self) -> None:
        self._redraw_after_id = None
        self.redraw()

    def _draw_grid(self, origin_x: float, origin_y: float, width: float, height: float) -> None:
        step = 10 * self.scale
        x = origin_x + step
        while x < origin_x + width:
            self.canvas.create_line(x, origin_y, x, origin_y + height, fill=GRID_COLOR)
            x += step
        y = origin_y + step
        while y < origin_y + height:
            self.canvas.create_line(origin_x, y, origin_x + width, y, fill=GRID_COLOR)
            y += step

    def _draw_rulers(self, origin_x: float, origin_y: float, width: float, height: float) -> None:
        top = origin_y - RULER_SIZE
        left = origin_x - RULER_SIZE
        self.canvas.create_rectangle(origin_x, top, origin_x + width, origin_y - 2, fill=RULER_BG, outline=RULER_OUTLINE)
        self.canvas.create_rectangle(left, origin_y, origin_x - 2, origin_y + height, fill=RULER_BG, outline=RULER_OUTLINE)
        max_x = int(width / self.scale)
        max_y = int(height / self.scale)
        for mm in range(0, max_x + 1):
            x = origin_x + mm * self.scale
            tick = 11 if mm % 10 == 0 else 7 if mm % 5 == 0 else 4
            self.canvas.create_line(x, origin_y - 2, x, origin_y - 2 - tick, fill=RULER_TICK_COLOR)
            if mm % 10 == 0:
                self.canvas.create_text(
                    x + 3,
                    top + 9,
                    text=str(mm),
                    anchor="nw",
                    fill=RULER_LABEL_COLOR,
                    font=("Consolas", 9, "bold"),
                )
        for mm in range(0, max_y + 1):
            y = origin_y + mm * self.scale
            tick = 11 if mm % 10 == 0 else 7 if mm % 5 == 0 else 4
            self.canvas.create_line(origin_x - 2, y, origin_x - 2 - tick, y, fill=RULER_TICK_COLOR)
            if mm % 10 == 0:
                self.canvas.create_text(
                    left + 5,
                    y + 2,
                    text=str(mm),
                    anchor="nw",
                    fill=RULER_LABEL_COLOR,
                    font=("Consolas", 9, "bold"),
                )

    def _create_round_rect(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        radius: float,
        fill: str,
        outline: str,
        width: int = 1,
    ) -> None:
        radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
        self.canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        self.canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline="")
        self.canvas.create_oval(x1, y1, x1 + radius * 2, y1 + radius * 2, fill=fill, outline="")
        self.canvas.create_oval(x2 - radius * 2, y1, x2, y1 + radius * 2, fill=fill, outline="")
        self.canvas.create_oval(x1, y2 - radius * 2, x1 + radius * 2, y2, fill=fill, outline="")
        self.canvas.create_oval(x2 - radius * 2, y2 - radius * 2, x2, y2, fill=fill, outline="")
        self.canvas.create_arc(x1, y1, x1 + radius * 2, y1 + radius * 2, start=90, extent=90, outline=outline, width=width, style="arc")
        self.canvas.create_arc(x2 - radius * 2, y1, x2, y1 + radius * 2, start=0, extent=90, outline=outline, width=width, style="arc")
        self.canvas.create_arc(x1, y2 - radius * 2, x1 + radius * 2, y2, start=180, extent=90, outline=outline, width=width, style="arc")
        self.canvas.create_arc(x2 - radius * 2, y2 - radius * 2, x2, y2, start=270, extent=90, outline=outline, width=width, style="arc")
        self.canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=outline, width=width)
        self.canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=outline, width=width)
        self.canvas.create_line(x1, y1 + radius, x1, y2 - radius, fill=outline, width=width)
        self.canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=outline, width=width)

    def draw_element(self, element: dict[str, object]) -> None:
        x1, y1, x2, y2 = self.element_bbox(element)
        element_id = str(element["id"])
        element_type = str(element["type"])
        selected = element_id in self._selected_ids()
        outline = SELECT_COLOR if selected else ELEMENT_GUIDE_COLOR
        line_width = 2 if selected else 1
        stroke_width = _stroke_width_px(element, self.scale)
        tag = f"element:{element_id}"

        if element_type == "line":
            if _line_is_vertical(element):
                line_x = _line_center_x(x1, x2)
                self.canvas.create_line(line_x, y1, line_x, y2, fill=outline, width=stroke_width, tags=(tag,))
            else:
                line_y = _line_center_y(y1, y2)
                self.canvas.create_line(x1, line_y, x2, line_y, fill=outline, width=stroke_width, tags=(tag,))
        elif _element_rotation(element):
            try:
                rotated_image = self._render_element_bitmap(
                    element,
                    self.preview_row,
                    max(1, round(x2 - x1)),
                    max(1, round(y2 - y1)),
                    transparent=True,
                )
            except ValueError as exc:
                self._draw_barcode_message(x1, y1, x2, y2, str(exc), tag, fill="#b42318")
            else:
                photo = ImageTk.PhotoImage(rotated_image)
                self.canvas_images.append(photo)
                self.canvas.create_image(x1, y1, image=photo, anchor="nw", tags=(tag,))
                if selected:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=line_width, tags=(tag,))
        elif element_type in TEXT_ELEMENT_TYPES:
            text = render_element_text(element, self.preview_row)
            image = _render_text_box_image(text, max(1, round(x2 - x1)), max(1, round(y2 - y1)), element, transparent=True)
            photo = ImageTk.PhotoImage(image)
            self.canvas_images.append(photo)
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline if selected else "", width=1, tags=(tag,))
            self.canvas.create_image(x1, y1, image=photo, anchor="nw", tags=(tag,))
        elif element_type in {"barcode", "qr"}:
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            value = _preview_code_value(
                render_template_text(str(element.get("text", "{{barcode}}")), self.preview_row) or str(self.preview_row.get("barcode", "")),
            )
            if selected:
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=line_width, tags=(tag,))
            if code_type in BARCODE_2D_TYPES:
                self._draw_2d_code_preview(x1, y1, x2, y2, value, code_type, element, tag)
            elif code_type in BARCODE_1D_BITMAP_TYPES:
                self._draw_1d_barcode_preview(x1, y1, x2, y2, value, code_type, element, tag)
            else:
                self._draw_unsupported_barcode_preview(x1 + 5, y1 + 5, x2 - 5, y2 - 5, code_type, tag)
        elif element_type == "box":
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=stroke_width, tags=(tag,))
        elif element_type == "table":
            self._draw_table_on_canvas(x1, y1, x2, y2, outline, tag, element)
        elif element_type == "image":
            self._draw_image_on_canvas(x1, y1, x2, y2, outline, tag, element)

        if selected:
            self.canvas.create_rectangle(x1 - 4, y1 - 4, x2 + 4, y2 + 4, outline=SELECT_COLOR, width=2)
            if element_id == self.selected_id and not element.get("locked"):
                self._draw_resize_handles(x1, y1, x2, y2, tag)

    def _draw_resize_handles(self, x1: float, y1: float, x2: float, y2: float, tag: str) -> None:
        for _handle, hx, hy in self._resize_handle_points(x1, y1, x2, y2):
            half = HANDLE_SIZE / 2
            self.canvas.create_rectangle(
                hx - half,
                hy - half,
                hx + half,
                hy + half,
                fill=SELECT_COLOR,
                outline="#ffffff",
                width=1,
                tags=(tag, "resize-handle"),
            )

    def _draw_table_on_canvas(self, x1: float, y1: float, x2: float, y2: float, outline: str, tag: str, element: dict[str, object]) -> None:
        stroke_width = _stroke_width_px(element, self.scale)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=stroke_width, tags=(tag,))
        selected = str(element.get("id")) == self.selected_id
        for ratio in _table_axis_positions(element, "col"):
            x = x1 + ((x2 - x1) * ratio)
            self.canvas.create_line(x, y1, x, y2, fill=outline, width=stroke_width, tags=(tag,))
            if selected:
                self.canvas.create_oval(x - 4, ((y1 + y2) / 2) - 4, x + 4, ((y1 + y2) / 2) + 4, fill=SELECT_COLOR, outline="#ffffff", tags=(tag, "table-divider"))
        for ratio in _table_axis_positions(element, "row"):
            y = y1 + ((y2 - y1) * ratio)
            self.canvas.create_line(x1, y, x2, y, fill=outline, width=stroke_width, tags=(tag,))
            if selected:
                self.canvas.create_oval(((x1 + x2) / 2) - 4, y - 4, ((x1 + x2) / 2) + 4, y + 4, fill=SELECT_COLOR, outline="#ffffff", tags=(tag, "table-divider"))

    def _draw_image_on_canvas(self, x1: float, y1: float, x2: float, y2: float, outline: str, tag: str, element: dict[str, object]) -> None:
        image = self._load_element_image(element, max(1, round(x2 - x1)), max(1, round(y2 - y1)))
        if image is None:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=1, dash=(4, 3), tags=(tag,))
            self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text="그림 없음", fill=COLORS.text_secondary, font=("Malgun Gothic", 9), tags=(tag,))
            return
        if not bool(element.get("printable", True)):
            image = image.copy()
            alpha = image.getchannel("A").point(lambda value: round(value * 0.38))
            image.putalpha(alpha)
        photo = ImageTk.PhotoImage(image)
        self.canvas_images.append(photo)
        self.canvas.create_image(x1, y1, image=photo, anchor="nw", tags=(tag,))
        if not bool(element.get("printable", True)):
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=COLORS.accent, width=1, dash=(5, 3), tags=(tag,))
            self.canvas.create_text(x1 + 8, y1 + 8, text="참고 도안 - 출력 제외", anchor="nw", fill=COLORS.accent, font=("Malgun Gothic", 9), tags=(tag,))
        else:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline if str(element.get("id")) == self.selected_id else "", width=1, tags=(tag,))

    def _load_element_image(self, element: dict[str, object], width: int, height: int) -> Image.Image | None:
        raw_path = str(element.get("image_path", "")).strip()
        if not raw_path:
            return None
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.base_dir / path
        if not path.exists():
            return None
        try:
            image = _open_design_image(path)
        except Exception:
            return None
        if str(element.get("image_fit", "contain")) == "stretch":
            return image.resize((max(1, width), max(1, height)), Image.Resampling.LANCZOS)
        image.thumbnail((max(1, width), max(1, height)), Image.Resampling.LANCZOS)
        canvas_image = Image.new("RGBA", (max(1, width), max(1, height)), (255, 255, 255, 0))
        offset = ((canvas_image.width - image.width) // 2, (canvas_image.height - image.height) // 2)
        canvas_image.alpha_composite(image, offset)
        return canvas_image

    def _render_element_bitmap(
        self,
        element: dict[str, object],
        row: dict[str, str],
        width: int,
        height: int,
        *,
        transparent: bool,
    ) -> Image.Image:
        """Render one element into its final object bounds, including rotation.

        A rotated element uses a bitmap for every printer language.  This keeps
        text, codes, pictures, lines, boxes, and tables visually identical
        without relying on unverified brand-specific rotation commands.
        """
        rotation = _element_rotation(element)
        source_width, source_height = _rotation_source_size(width, height, rotation)
        element_type = str(element.get("type", "text"))

        if element_type in TEXT_ELEMENT_TYPES:
            image = _render_text_box_image(
                render_element_text(element, row),
                source_width,
                source_height,
                element,
                transparent=transparent,
            )
            return _rotate_element_bitmap(image, rotation)

        if element_type in {"barcode", "qr"}:
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            value = _designer_code_value(element, row)
            if code_type in BARCODE_1D_BITMAP_TYPES:
                image = _render_1d_barcode_image(code_type, value, source_width, source_height, element)
            elif code_type in BARCODE_2D_BITMAP_TYPES:
                image = _render_2d_barcode_image(code_type, value, source_width, source_height, element)
            else:
                raise ValueError(f"{BARCODE_TYPES.get(code_type, code_type)} 타입은 회전 출력에 지원되지 않습니다.")
            if transparent:
                image = _barcode_image_to_transparent_rgba(image)
            return _rotate_element_bitmap(image, rotation)

        if transparent:
            image = Image.new("RGBA", (source_width, source_height), (255, 255, 255, 0))
            stroke_fill: int | tuple[int, int, int, int] = (17, 24, 32, 255)
        else:
            image = Image.new("1", (source_width, source_height), 1)
            stroke_fill = 0
        draw = ImageDraw.Draw(image)
        stroke_width = self._element_bitmap_stroke_width(element, source_width, source_height, rotation)

        if element_type == "box":
            draw.rectangle((0, 0, source_width - 1, source_height - 1), outline=stroke_fill, width=stroke_width)
        elif element_type == "line":
            line_y = _line_bitmap_y(source_height, stroke_width)
            draw.line((0, line_y, source_width - 1, line_y), fill=stroke_fill, width=stroke_width)
        elif element_type == "table":
            draw.rectangle((0, 0, source_width - 1, source_height - 1), outline=stroke_fill, width=stroke_width)
            for ratio in _table_axis_positions(element, "col"):
                x = round((source_width - 1) * ratio)
                draw.line((x, 0, x, source_height - 1), fill=stroke_fill, width=stroke_width)
            for ratio in _table_axis_positions(element, "row"):
                y = round((source_height - 1) * ratio)
                draw.line((0, y, source_width - 1, y), fill=stroke_fill, width=stroke_width)
        elif element_type == "image":
            loaded = self._load_element_image(element, source_width, source_height)
            if loaded is None:
                draw.rectangle((0, 0, source_width - 1, source_height - 1), outline="#8a94a6" if transparent else 0, width=1)
                draw.text((4, 4), "그림 없음", fill="#657085" if transparent else 0, font=_load_font(10))
            elif transparent:
                image = loaded
            else:
                background = Image.new("RGBA", (source_width, source_height), "white")
                background.alpha_composite(loaded.convert("RGBA"))
                image = background.convert("1")

        return _rotate_element_bitmap(image, rotation)

    def _element_bitmap_stroke_width(self, element: dict[str, object], width: int, height: int, rotation: int) -> int:
        logical_width_mm = float(element.get("height" if rotation in {90, 270} else "width", 1))
        logical_height_mm = float(element.get("width" if rotation in {90, 270} else "height", 1))
        pixels_per_mm = min(
            max(1.0, width / max(0.1, logical_width_mm)),
            max(1.0, height / max(0.1, logical_height_mm)),
        )
        return max(1, round(_stroke_width_mm(element) * pixels_per_mm))

    def _animate_selected_element(self) -> None:
        element = self.selected_element()
        if element is None:
            return
        try:
            x1, y1, x2, y2 = self.element_bbox(element)
        except tk.TclError:
            return
        colors = (COLORS.accent, "#57b08b", COLORS.border_strong)

        def frame(step: int) -> None:
            self.canvas.delete("selection-pulse")
            if step >= len(colors):
                return
            pad = 4 + (step * 3)
            self.canvas.create_rectangle(
                x1 - pad,
                y1 - pad,
                x2 + pad,
                y2 + pad,
                outline=colors[step],
                width=max(1, 3 - step),
                tags=("selection-pulse",),
            )
            self.after(90, lambda: frame(step + 1))

        frame(0)

    def _resize_handle_points(self, x1: float, y1: float, x2: float, y2: float) -> list[tuple[str, float, float]]:
        return [
            ("nw", x1, y1),
            ("ne", x2, y1),
            ("sw", x1, y2),
            ("se", x2, y2),
        ]

    def resize_handle_at(self, x: float, y: float, element: dict[str, object] | None) -> str | None:
        if element is None:
            return None
        x1, y1, x2, y2 = self.element_bbox(element)
        hit_size = HANDLE_SIZE + 5
        for handle, hx, hy in self._resize_handle_points(x1, y1, x2, y2):
            if abs(x - hx) <= hit_size and abs(y - hy) <= hit_size:
                return handle
        return None

    def table_divider_at(self, x: float, y: float, element: dict[str, object] | None) -> tuple[str, int] | None:
        if element is None or str(element.get("type")) != "table":
            return None
        x1, y1, x2, y2 = self.element_bbox(element)
        tolerance = max(TABLE_DIVIDER_HIT_PX, self.scale * 0.35)
        if not (x1 - tolerance <= x <= x2 + tolerance and y1 - tolerance <= y <= y2 + tolerance):
            return None
        for index, ratio in enumerate(_table_axis_positions(element, "col")):
            line_x = x1 + ((x2 - x1) * ratio)
            if abs(x - line_x) <= tolerance and y1 <= y <= y2:
                return "col", index
        for index, ratio in enumerate(_table_axis_positions(element, "row")):
            line_y = y1 + ((y2 - y1) * ratio)
            if abs(y - line_y) <= tolerance and x1 <= x <= x2:
                return "row", index
        return None

    def _draw_1d_barcode_preview(self, x1: float, y1: float, x2: float, y2: float, value: str, code_type: str, element: dict[str, object], tag: str) -> None:
        width = max(1, round(x2 - x1))
        height = max(1, round(y2 - y1))
        try:
            image = _render_1d_barcode_image(code_type, value, width, height, element)
        except ValueError as exc:
            self._draw_barcode_message(x1, y1, x2, y2, str(exc), tag, fill="#b42318")
            return
        photo = ImageTk.PhotoImage(_barcode_image_to_transparent_rgba(image))
        self.canvas_images.append(photo)
        self.canvas.create_image(x1, y1, image=photo, anchor="nw", tags=(tag,))

    def _draw_unsupported_barcode_preview(self, x1: float, y1: float, x2: float, y2: float, code_type: str, tag: str) -> None:
        label = BARCODE_TYPES.get(code_type, code_type)
        self._draw_barcode_message(x1, y1, x2, y2, f"{label}\n인쇄 준비 중", tag, fill="#8a4b00")

    def _draw_barcode_message(self, x1: float, y1: float, x2: float, y2: float, message: str, tag: str, *, fill: str) -> None:
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#fff8e8", outline="#f0c36d", tags=(tag,))
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=message, anchor="center", fill=fill, font=("Malgun Gothic", 9, "bold"), tags=(tag,))

    def _draw_barcode_preview(self, x1: float, y1: float, x2: float, y2: float, value: str, tag: str) -> None:
        if y2 <= y1:
            return
        width = max(1, int(x2 - x1))
        seed = sum(ord(char) for char in value) or 1
        cursor = x1
        index = 0
        while cursor < x2:
            bar_width = 1 + ((seed + index) % 4)
            gap = 1 + ((seed // (index + 1)) % 2)
            if index % 2 == 0:
                self.canvas.create_rectangle(cursor, y1, min(cursor + bar_width, x2), y2, fill="#111820", outline="", tags=(tag,))
            cursor += bar_width + gap
            index += 1
            if index > width:
                break

    def _draw_code128_preview(self, x1: float, y1: float, x2: float, y2: float, value: str, tag: str) -> None:
        if x2 <= x1 or y2 <= y1:
            return
        try:
            modules = _code128_module_widths(sanitize_barcode(value))
        except ValueError:
            return
        total_modules = sum(modules) + 20
        scale = max(0.1, (x2 - x1) / max(1, total_modules))
        cursor = x1 + (10 * scale)
        black = True
        for module_width in modules:
            bar_width = module_width * scale
            if black:
                self.canvas.create_rectangle(cursor, y1, cursor + bar_width, y2, fill="#111820", outline="", tags=(tag,))
            cursor += bar_width
            black = not black

    def _draw_2d_code_preview(self, x1: float, y1: float, x2: float, y2: float, value: str, code_type: str, element: dict[str, object], tag: str) -> None:
        width = max(1, round(x2 - x1))
        height = max(1, round(y2 - y1))
        if code_type in BARCODE_2D_BITMAP_TYPES:
            try:
                image = _render_2d_barcode_image(code_type, value, width, height, element)
            except ValueError as exc:
                self._draw_barcode_message(x1, y1, x2, y2, str(exc), tag, fill="#b42318")
                return
            photo = ImageTk.PhotoImage(_barcode_image_to_transparent_rgba(image))
            self.canvas_images.append(photo)
            self.canvas.create_image(x1, y1, image=photo, anchor="nw", tags=(tag,))
            return
        self._draw_barcode_message(
            x1,
            y1,
            x2,
            y2,
            f"{BARCODE_TYPES.get(code_type, code_type)}\n미리보기/인쇄 준비 중",
            tag,
            fill="#8a4b00",
        )

    def _draw_matrix_preview(self, x1: float, y1: float, x2: float, y2: float, value: str, code_type: str, tag: str) -> None:
        size = min(x2 - x1, y2 - y1)
        if size <= 0:
            return
        x1 += ((x2 - x1) - size) / 2
        y1 += ((y2 - y1) - size) / 2
        cells = 10 if code_type == "datamatrix" else 9
        cell = size / cells
        seed = sum(ord(char) for char in value + code_type) or 1
        for row in range(cells):
            for col in range(cells):
                finder = code_type == "qr" and ((row < 3 and col < 3) or (row < 3 and col > cells - 4) or (row > cells - 4 and col < 3))
                data_cell = ((row * 7 + col * 5 + row * col + seed) % 3) == 0
                border_cell = code_type == "datamatrix" and (row == 0 or col == 0 or row == cells - 1 or col == cells - 1)
                if finder or data_cell or border_cell:
                    self.canvas.create_rectangle(x1 + col * cell, y1 + row * cell, x1 + (col + 1) * cell, y1 + (row + 1) * cell, fill="#111820", outline="", tags=(tag,))

    def _draw_pdf417_preview(self, x1: float, y1: float, x2: float, y2: float, value: str, tag: str) -> None:
        if y2 <= y1 or x2 <= x1:
            return
        seed = sum(ord(char) for char in value) or 1
        rows = 5
        row_height = max(2, (y2 - y1) / rows)
        for row in range(rows):
            cursor = x1
            index = 0
            while cursor < x2:
                bar_width = 1 + ((seed + row + index) % 5)
                gap = 1 + ((seed // (index + 1) + row) % 2)
                if (index + row) % 2 == 0:
                    self.canvas.create_rectangle(cursor, y1 + row * row_height, min(cursor + bar_width, x2), y1 + (row + 0.75) * row_height, fill="#111820", outline="", tags=(tag,))
                cursor += bar_width + gap
                index += 1

    def element_bbox(self, element: dict[str, object]) -> tuple[float, float, float, float]:
        x1 = self.origin_x + float(element.get("x", 0)) * self.scale
        y1 = self.origin_y + float(element.get("y", 0)) * self.scale
        x2 = x1 + float(element.get("width", 1)) * self.scale
        y2 = y1 + float(element.get("height", 1)) * self.scale
        return x1, y1, x2, y2

    def add_element(self, element_type: str) -> None:
        text_field = ""
        text_value = "새 텍스트"
        if element_type == "text" and getattr(self, "data_source_path", None) is not None:
            text_field = _preferred_text_db_field(
                getattr(self, "db_rows", []),
                tuple(getattr(self, "data_source_headers", ())),
            )
            if text_field:
                text_value = "{{" + text_field + "}}"
        barcode_text, barcode_field = _new_code_element_values(
            data_source_connected=self.__dict__.get("data_source_path") is not None,
        )
        defaults = {
            "text": _element("text", text_value, 5, 5, 22, 5, field=text_field, font_size=10),
            "multiline_text": _element("multiline_text", "첫째 줄\n둘째 줄", 5, 5, 34, 12, font_size=9),
            "field": _element("field", "텍스트", 5, 5, 30, 5, field="", font_size=10, align="center"),
            "barcode": _element("barcode", barcode_text, 7, 14, 36, 12, field=barcode_field, font_size=10, align="center"),
            "qr": _element("qr", barcode_text, 16, 12, 18, 18, field=barcode_field, align="center"),
            "box": _element("box", "", 5, 5, 20, 10),
            "line": _element("line", "", 5, 5, 20, 0.5),
            "table": _element("table", "", 5, 5, 35, 18),
            "image": _element("image", "그림", 5, 5, 25, 18, align="center"),
        }
        element = defaults[element_type]
        self.elements.append(element)
        self.selected_id = str(element["id"])
        self.load_selected_properties()
        self.redraw()
        self._animate_selected_element()
        if element_type == "text" and text_field:
            field_label = FIELD_LABELS.get(text_field, text_field)
            self.status_var.set(f"텍스트 요소를 DB 열 '{field_label}'에 연결했습니다.")
        else:
            self.status_var.set(f"{ELEMENT_TYPES[element_type]} 요소를 추가했습니다.")

    def add_image_element(self) -> None:
        self._add_image_from_dialog(title="그림 추가", fit_to_label=False)

    def add_label_image_element(self) -> None:
        self._add_image_template_from_dialog()

    def _add_image_from_dialog(self, *, title: str, fit_to_label: bool) -> None:
        source = filedialog.askopenfilename(
            parent=self,
            initialdir=self.base_dir,
            title=title,
            filetypes=IMAGE_FILE_TYPES,
        )
        if not source:
            return
        try:
            element = self._image_element_from_source(Path(source), fit_to_label=fit_to_label)
        except Exception as exc:
            messagebox.showerror(title, f"그림 파일을 불러올 수 없습니다.\n{exc}")
            return
        self.elements.append(element)
        self.selected_id = str(element["id"])
        self.load_selected_properties()
        self.redraw()
        self._animate_selected_element()
        self.status_var.set("이미지를 라벨 크기에 맞춰 적용했습니다." if fit_to_label else "그림을 추가했습니다.")

    def _image_element_from_source(self, source_path: Path, *, fit_to_label: bool) -> dict[str, object]:
        source_path = Path(source_path)
        image_dir = self.base_dir / "assets" / "images"
        target, image_size = _save_design_image_asset(source_path, image_dir)
        label = self.template["label"]  # type: ignore[index]
        return _image_element_for_label(
            str(target.relative_to(self.base_dir)),
            source_path.stem,
            label,
            image_size,
            fit_to_label=fit_to_label,
        )

    def _add_image_template_from_dialog(self) -> None:
        source = filedialog.askopenfilename(
            parent=self,
            initialdir=self.base_dir,
            title="도안 템플릿 생성",
            filetypes=IMAGE_FILE_TYPES,
        )
        if not source:
            return
        try:
            elements = self._editable_template_elements_from_source(Path(source))
        except Exception as exc:
            messagebox.showerror("도안 템플릿 생성", f"도안 파일을 불러올 수 없습니다.\n{exc}")
            return
        self.elements.extend(elements)
        self.selected_id = str(elements[0]["id"]) if elements else None
        self.load_selected_properties()
        self.redraw()
        self._animate_selected_element()
        self.status_var.set("도안을 불러왔습니다. 도안 적용을 누르면 선, 텍스트, 바코드 후보를 생성합니다.")

    def _editable_template_elements_from_source(self, source_path: Path) -> list[dict[str, object]]:
        source_path = Path(source_path)
        image_dir = self.base_dir / "assets" / "images"
        target, image_size = _save_design_image_asset(source_path, image_dir)
        label = self.template["label"]  # type: ignore[index]
        relative_path = str(target.relative_to(self.base_dir))
        guide = _image_element_for_label(
            relative_path,
            f"{source_path.stem} 참고 도안",
            label,
            image_size,
            fit_to_label=True,
            printable=False,
        )
        guide["arrange"] = "behind"
        guide["text"] = f"{source_path.stem} 참고 도안"
        guide["template_role"] = DESIGN_REFERENCE_ROLE
        guide["source_path"] = str(source_path)
        guide["source_image_size"] = list(image_size)
        guide["analysis_applied"] = False
        return [guide]

    def start_apply_design_template(self) -> None:
        reference = self._selected_or_latest_design_reference()
        if reference is None:
            messagebox.showwarning("도안 적용", "먼저 도안 템플릿으로 PSD/사진 파일을 불러오세요.")
            return
        path = self._element_image_path(reference)
        if path is None:
            messagebox.showerror("도안 적용", "참고 도안 이미지 파일을 찾을 수 없습니다.", parent=self)
            return
        label = copy.deepcopy(self.template["label"])
        reference_id = str(reference["id"])
        signature = self._current_payload_signature()

        def analyze() -> object:
            image = _open_design_image(path)
            return _design_template_elements_from_image(image, label, base_dir=self.base_dir)

        def apply_generated(result: object) -> None:
            if self._current_payload_signature() != signature:
                self.status_var.set("도안 분석 중 라벨이 변경되어 결과를 적용하지 않았습니다. 다시 시도하세요.")
                return
            current_reference = next(
                (element for element in self.elements if str(element.get("id")) == reference_id),
                None,
            )
            if current_reference is None:
                self.status_var.set("참고 도안이 삭제되어 분석 결과를 적용하지 않았습니다.")
                return
            self._apply_generated_design_template(current_reference, result)  # type: ignore[arg-type]

        self._start_background_job("도안 분석", analyze, apply_generated)

    def apply_design_template(self) -> None:
        reference = self._selected_or_latest_design_reference()
        if reference is None:
            messagebox.showwarning("도안 적용", "먼저 도안 템플릿으로 PSD/사진 파일을 불러오세요.")
            return
        try:
            generated = self._template_elements_from_reference(reference)
        except Exception as exc:
            messagebox.showerror("도안 적용", f"도안을 분석할 수 없습니다.\n{exc}")
            return
        self._apply_generated_design_template(reference, generated)

    def _apply_generated_design_template(
        self,
        reference: dict[str, object],
        generated: list[dict[str, object]],
    ) -> None:
        if not generated:
            messagebox.showinfo("도안 적용", "생성할 수 있는 선, 텍스트, 바코드 후보를 찾지 못했습니다.")
            return
        review_image_path = str(reference.get("image_path", ""))
        for candidate in generated:
            if candidate.get("review_source"):
                candidate["review_image_path"] = review_image_path
        reference_id = str(reference.get("id", ""))
        self.elements = [element for element in self.elements if str(element.get("id")) != reference_id]
        self.elements.extend(generated)
        reference["analysis_applied"] = True
        review_target = next((element for element in generated if str(element.get("type")) in TEXT_ELEMENT_TYPES or _is_code_element(element)), generated[0])
        self.selected_id = str(review_target["id"])
        self.load_selected_properties()
        self.redraw()
        self._animate_selected_element()
        counts = {
            "table": sum(1 for element in generated if str(element.get("type")) == "table"),
            "line": sum(1 for element in generated if str(element.get("type")) == "line"),
            "box": sum(1 for element in generated if str(element.get("type")) == "box"),
            "text": sum(1 for element in generated if str(element.get("type")) in TEXT_ELEMENT_TYPES),
            "barcode": sum(1 for element in generated if _is_code_element(element)),
        }
        status = f"도안 적용 완료: 표 {counts['table']}개, 선 {counts['line']}개, 박스 {counts['box']}개, 텍스트 {counts['text']}개, 바코드 {counts['barcode']}개"
        if counts["text"] or counts["barcode"]:
            status += " - 텍스트와 바코드 값을 확인하세요."
        if counts["text"] and _resolve_tesseract_executable(self.base_dir) is None:
            status += " (OCR 엔진 없음: 텍스트 후보는 직접 수정)"
        self.status_var.set(status)
        if any(candidate.get("review_source") for candidate in generated):
            self.after(100, self.open_ocr_review_dialog)

    def _recognition_review_candidates(self) -> list[dict[str, object]]:
        return [
            element for element in self.elements
            if element.get("review_source") and str(element.get("type")) in TEXT_ELEMENT_TYPES | {"barcode", "qr"}
        ]

    def confirm_recognized_values(self, values: dict[str, str]) -> int:
        """Validate the entire requested batch before changing any recognition state."""
        by_id = {str(element["id"]): element for element in self._recognition_review_candidates()}
        staged: list[tuple[dict[str, object], str]] = []
        for key, raw_value in values.items():
            if key not in by_id:
                raise ValueError("도안이 변경되었습니다. 인식 값 검토 창을 다시 열어 주세요.")
            element = by_id[key]
            value = raw_value.strip()
            if not value or (element.get("review_source") == "placeholder" and value == BARCODE_FALLBACK_VALUE):
                raise ValueError(f"'{element.get('text', '')}' 항목의 빈 값 또는 임시 값을 원본 값으로 수정하세요.")
            staged.append((element, value))
        for element, value in staged:
            element["text"] = value
            element["review_confirmed"] = True
        if staged:
            self.load_selected_properties()
            self.redraw()
        return len(staged)

    def open_ocr_review_dialog(self) -> None:
        candidates = self._recognition_review_candidates()
        if not candidates:
            messagebox.showinfo("인식 값 검토", "검토할 도안 인식 값이 없습니다.", parent=self)
            return

        dialog = tk.Toplevel(self)
        dialog.title("도안 인식 값 검토")
        dialog.transient(self)
        dialog.grab_set()
        set_initial_window_size(dialog, preferred_width=1020, preferred_height=650, minimum_width=760, minimum_height=500)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(
            dialog,
            text="원본과 값을 대조한 뒤 '전체 값 확인'을 누르세요. 잘못된 값은 먼저 수정하세요.",
            style="Title.TLabel", wraplength=720,
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 10))
        body = ttk.Frame(dialog, padding=(18, 0, 18, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)
        ttk.Label(body, text="원본 도안", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(body, text="추정 결과 · 미확인 표시", style="PanelTitle.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 0), pady=(0, 6))
        image_frame = ttk.Frame(body)
        image_frame.grid(row=1, column=0, sticky="nsew")
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)
        image_label = ttk.Label(image_frame, text="원본 이미지를 찾을 수 없습니다.", anchor="center")
        image_label.grid(row=0, column=0, sticky="nsew")
        raw_image_path = next((str(item.get("review_image_path", "")) for item in candidates if item.get("review_image_path")), "")
        if raw_image_path:
            image_path = Path(raw_image_path)
            if not image_path.is_absolute():
                image_path = self.base_dir / image_path
            if image_path.is_file():
                try:
                    original = _open_design_image(image_path)
                    preview = ImageOps.contain(_design_image_on_white(original), (460, 500), Image.Resampling.LANCZOS)
                    dialog._review_image = ImageTk.PhotoImage(preview)  # type: ignore[attr-defined]
                    image_label.configure(image=dialog._review_image, text="")  # type: ignore[attr-defined]
                except (OSError, ValueError):
                    pass

        result_frame = ttk.Frame(body)
        result_frame.grid(row=1, column=1, sticky="nsew", padx=(14, 0))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(result_frame, columns=("source", "value", "state"), show="headings", selectmode="browse")
        for key, title, width in (("source", "근거", 112), ("value", "인식 값", 220), ("state", "상태", 70)):
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=60, stretch=key == "value")
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        source_labels = {
            "code_read": "코드 판독", "text_inference": "문자에서 추정", "placeholder": "임시 값",
            "ocr_estimate": "문자 인식", "ocr_fallback": "영역 추정",
        }
        by_id = {str(element["id"]): element for element in candidates}
        for element in candidates:
            key = str(element["id"])
            tree.insert("", "end", iid=key, values=(
                source_labels.get(str(element.get("review_source")), "추정"),
                str(element.get("text", "")),
                "확인" if element.get("review_confirmed") else "미확인",
            ))
        value_var = tk.StringVar()
        ttk.Label(result_frame, text="선택한 값 수정").grid(row=1, column=0, sticky="w", pady=(12, 4))
        value_entry = ttk.Entry(result_frame, textvariable=value_var)
        value_entry.grid(row=2, column=0, sticky="ew")

        def select_candidate(_event: tk.Event | None = None) -> None:
            selection = tree.selection()
            if selection:
                value_var.set(str(by_id[selection[0]].get("text", "")))

        tree.bind("<<TreeviewSelect>>", select_candidate)

        def apply_review(*, all_values: bool) -> None:
            selection = tree.selection()
            if not selection and not all_values:
                return
            values = {key: str(element.get("text", "")) for key, element in by_id.items()} if all_values else {}
            if selection:
                values[selection[0]] = value_var.get()
            try:
                self.confirm_recognized_values(values)
            except ValueError as exc:
                messagebox.showwarning("인식 값 검토", str(exc), parent=dialog)
                return
            for key in values:
                tree.set(key, "value", str(by_id[key]["text"]))
                tree.set(key, "state", "확인")
            remaining = [item for item in candidates if not item.get("review_confirmed")]
            if remaining:
                tree.selection_set(str(remaining[0]["id"]))
                tree.see(str(remaining[0]["id"]))
            else:
                self.status_var.set("도안 인식 값을 모두 검토했습니다. 원본과 첫 장 출력을 대조하세요.")

        controls = ttk.Frame(dialog, padding=(18, 0, 18, 16))
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)
        ttk.Button(controls, text="전체 값 확인", command=lambda: apply_review(all_values=True), style="Primary.TButton").grid(row=0, column=1, padx=(0, 8))
        ttk.Button(controls, text="선택 값 수정·확인", command=lambda: apply_review(all_values=False), style="Secondary.TButton").grid(row=0, column=2, padx=(0, 8))
        ttk.Button(controls, text="닫기", command=dialog.destroy, style="Secondary.TButton").grid(row=0, column=3)
        if candidates:
            tree.selection_set(str(candidates[0]["id"]))
            select_candidate()

    def _selected_or_latest_design_reference(self) -> dict[str, object] | None:
        selected = self.selected_element()
        if selected is not None and self._is_design_reference(selected):
            return selected
        for element in reversed(self.elements):
            if self._is_design_reference(element):
                return element
        return None

    def _is_design_reference(self, element: dict[str, object]) -> bool:
        return (
            str(element.get("type")) == "image"
            and str(element.get("template_role")) == DESIGN_REFERENCE_ROLE
            and not bool(element.get("printable", True))
        )

    def _template_elements_from_reference(self, reference: dict[str, object]) -> list[dict[str, object]]:
        path = self._element_image_path(reference)
        if path is None:
            raise FileNotFoundError("참고 도안 이미지 파일을 찾을 수 없습니다.")
        image = _open_design_image(path)
        label = self.template["label"]  # type: ignore[index]
        return _design_template_elements_from_image(image, label, base_dir=self.base_dir)

    def _element_image_path(self, element: dict[str, object]) -> Path | None:
        raw_path = str(element.get("image_path", "")).strip()
        if not raw_path:
            return None
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.base_dir / path
        return path if path.exists() else None

    def add_barcode_element(self, barcode_type: str = "code128") -> None:
        width = 18 if barcode_type in BARCODE_2D_TYPES else 36
        height = 18 if barcode_type in BARCODE_2D_TYPES else 12
        text, field = _new_code_element_values(data_source_connected=self.__dict__.get("data_source_path") is not None)
        element = _element(
            "barcode",
            text,
            7 if width > 20 else 16,
            12,
            width,
            height,
            field=field,
            font_size=10,
            align="center",
            barcode_type=barcode_type,
        )
        self.elements.append(element)
        self.selected_id = str(element["id"])
        self.load_selected_properties()
        self.redraw()
        self._animate_selected_element()
        self.status_var.set(f"{BARCODE_TYPES.get(barcode_type, 'Code 128')} 요소를 추가했습니다.")

    def add_field_element(self, field: str) -> None:
        label = FIELD_LABELS.get(field, field)
        element = _element("field", f"{label}: {{{{{field}}}}}", 5, 5, 30, 5, field=field, font_size=10, align="left")
        self.elements.append(element)
        self.selected_id = str(element["id"])
        self.load_selected_properties()
        self.redraw()
        self.status_var.set(f"{label} 값을 붙였습니다.")

    def on_canvas_press(self, event: tk.Event) -> None:
        self.canvas.focus_set()
        pointer_x, pointer_y = self._canvas_point(event)
        selected = self.selected_element()
        resize_handle = self.resize_handle_at(pointer_x, pointer_y, selected) if selected is not None and not selected.get("locked") else None
        if selected is not None and resize_handle is not None:
            self.drag_state = {
                "mode": "resize",
                "handle": resize_handle,
                "id": str(selected["id"]),
                "start_x": pointer_x,
                "start_y": pointer_y,
                "element_x": float(selected.get("x", 0)),
                "element_y": float(selected.get("y", 0)),
                "element_w": float(selected.get("width", 1)),
                "element_h": float(selected.get("height", 1)),
            }
            return
        table_divider = self.table_divider_at(pointer_x, pointer_y, selected) if selected is not None and not selected.get("locked") else None
        if selected is not None and table_divider is not None:
            axis, index = table_divider
            self.drag_state = {
                "mode": "table-divider",
                "axis": axis,
                "index": float(index),
                "id": str(selected["id"]),
                "start_x": pointer_x,
                "start_y": pointer_y,
            }
            return

        element = self.find_element_at(pointer_x, pointer_y)
        if element is None:
            self.selected_id = None
            self.selected_ids = set()
            self.drag_state = None
            self.clear_property_panel()
            self.redraw()
            return
        element_id = str(element["id"])
        if int(getattr(event, "state", 0)) & 0x0004:
            selected_ids = self._selected_ids()
            if element_id in selected_ids:
                selected_ids.remove(element_id)
            else:
                selected_ids.add(element_id)
            self.selected_ids = selected_ids
            self.selected_id = element_id if element_id in selected_ids else next(iter(selected_ids), None)
            self.drag_state = None
            self.load_selected_properties()
            self.redraw()
            return
        group_id = str(element.get("group_id", ""))
        if group_id:
            self.selected_ids = {str(item["id"]) for item in self.elements if str(item.get("group_id", "")) == group_id}
        elif element_id not in self._selected_ids():
            self.selected_ids = {element_id}
        self.selected_id = element_id
        if element.get("locked"):
            self.drag_state = None
            self.load_selected_properties()
            self.redraw()
            return
        self.drag_state = {
            "mode": "move",
            "id": self.selected_id,
            "start_x": pointer_x,
            "start_y": pointer_y,
            "element_x": float(element.get("x", 0)),
            "element_y": float(element.get("y", 0)),
            "positions": {
                str(item["id"]): (float(item.get("x", 0)), float(item.get("y", 0)))
                for item in self._selected_elements() if not item.get("locked")
            },
        }
        self.load_selected_properties()
        self.redraw()

    def on_canvas_drag(self, event: tk.Event) -> None:
        if not self.drag_state:
            return
        element = self.selected_element()
        if element is None:
            return
        pointer_x, pointer_y = self._canvas_point(event)
        dx = (pointer_x - float(self.drag_state["start_x"])) / self.scale
        dy = (pointer_y - float(self.drag_state["start_y"])) / self.scale
        if self.drag_state.get("mode") == "table-divider":
            x1, y1, x2, y2 = self.element_bbox(element)
            axis = str(self.drag_state.get("axis", "col"))
            index = int(float(self.drag_state.get("index", 0)))
            if axis == "col":
                ratio = (pointer_x - x1) / max(1.0, x2 - x1)
            else:
                ratio = (pointer_y - y1) / max(1.0, y2 - y1)
            _set_table_axis_position(element, axis, index, ratio)
            self.load_selected_properties()
            self.redraw()
            return
        if self.drag_state.get("mode") == "resize":
            handle = str(self.drag_state.get("handle", "se"))
            start_x = float(self.drag_state["element_x"])
            start_y = float(self.drag_state["element_y"])
            start_w = float(self.drag_state["element_w"])
            start_h = float(self.drag_state["element_h"])
            new_x = start_x
            new_y = start_y
            new_w = start_w
            new_h = start_h
            if "e" in handle:
                new_w = max(MIN_ELEMENT_MM, start_w + dx)
            if "s" in handle:
                new_h = max(0.5, start_h + dy)
            if "w" in handle:
                new_x = start_x + dx
                new_w = start_w - dx
                if new_w < MIN_ELEMENT_MM:
                    new_x = start_x + start_w - MIN_ELEMENT_MM
                    new_w = MIN_ELEMENT_MM
            if "n" in handle:
                new_y = start_y + dy
                new_h = start_h - dy
                if new_h < 0.5:
                    new_y = start_y + start_h - 0.5
                    new_h = 0.5
            element["x"] = round(max(0, new_x), 1)
            element["y"] = round(max(0, new_y), 1)
            element["width"] = round(new_w, 1)
            element["height"] = round(new_h, 1)
        else:
            positions = self.drag_state.get("positions")
            if isinstance(positions, dict):
                for item in self._selected_elements():
                    start = positions.get(str(item["id"]))
                    if start is None or item.get("locked"):
                        continue
                    item["x"] = self._drag_coordinate(float(start[0]) + dx)
                    item["y"] = self._drag_coordinate(float(start[1]) + dy)
            else:
                element["x"] = self._drag_coordinate(float(self.drag_state["element_x"]) + dx)
                element["y"] = self._drag_coordinate(float(self.drag_state["element_y"]) + dy)
        self.load_selected_properties()
        self.redraw()

    def on_canvas_release(self, _event: tk.Event) -> None:
        self.drag_state = None
        self._record_history()

    def on_canvas_double_click(self, event: tk.Event) -> None:
        pointer_x, pointer_y = self._canvas_point(event)
        element = self.find_element_at(pointer_x, pointer_y)
        if element is None:
            element = self.selected_element()
        if element is None:
            return
        self.selected_id = str(element["id"])
        self.drag_state = None
        self.load_selected_properties()
        self.redraw()
        self.open_element_editor(element)

    def on_delete_key(self, event: tk.Event) -> str | None:
        widget_class = ""
        try:
            widget_class = str(event.widget.winfo_class())
        except tk.TclError:
            pass
        if widget_class in {"Entry", "TEntry", "TSpinbox", "TCombobox", "Spinbox", "Text"}:
            return None
        self.delete_selected()
        return "break"

    def open_element_editor(self, element: dict[str, object] | None = None) -> None:
        element = element or self.selected_element()
        if element is None:
            messagebox.showwarning("요소 편집", "선택된 요소가 없습니다.")
            return
        if element.get("locked"):
            messagebox.showwarning("요소 편집", "잠긴 개체입니다. 잠금/해제 버튼으로 해제한 뒤 편집하세요.")
            return

        editor = tk.Toplevel(self)
        editor.title("요소 편집")
        set_initial_window_size(
            editor,
            preferred_width=680,
            preferred_height=820,
            minimum_width=540,
            minimum_height=560,
        )
        editor.configure(bg=COLORS.surface)
        editor.transient(self)
        editor.columnconfigure(0, weight=1)
        editor.rowconfigure(0, weight=1)

        editor_body = ttk.Frame(editor, style="Surface.TFrame")
        editor_body.grid(row=0, column=0, sticky="nsew")
        editor_body.columnconfigure(0, weight=1)
        editor_body.rowconfigure(0, weight=1)
        editor_canvas = tk.Canvas(
            editor_body,
            width=420,
            height=360,
            bg=COLORS.surface,
            highlightthickness=0,
            bd=0,
        )
        editor_canvas.grid(row=0, column=0, sticky="nsew")
        editor_scroll = ttk.Scrollbar(editor_body, orient="vertical", command=editor_canvas.yview)
        editor_scroll.grid(row=0, column=1, sticky="ns")
        editor_canvas.configure(yscrollcommand=editor_scroll.set)
        frame = ttk.Frame(editor_canvas, style="Surface.TFrame", padding=(18, 14, 18, 16))
        editor_window = editor_canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.columnconfigure(1, weight=1)

        def sync_editor_scrollregion(_event: tk.Event | None = None) -> None:
            editor_canvas.configure(scrollregion=editor_canvas.bbox("all"))

        def sync_editor_width(event: tk.Event) -> None:
            editor_canvas.itemconfigure(editor_window, width=max(1, event.width))

        def scroll_editor(event: tk.Event) -> str:
            delta = -1 if event.delta > 0 else 1
            editor_canvas.yview_scroll(delta, "units")
            return "break"

        frame.bind("<Configure>", sync_editor_scrollregion)
        editor_canvas.bind("<Configure>", sync_editor_width)
        editor.bind("<MouseWheel>", scroll_editor)

        type_var = tk.StringVar(value=ELEMENT_TYPES.get(str(element.get("type")), "텍스트"))
        code_var = tk.StringVar(value=BARCODE_TYPES.get(_barcode_type(element), "Code 128"))
        text_var = tk.StringVar(value=str(element.get("text", "")))
        field_var = tk.StringVar(value=str(element.get("field", "")))
        editor_headers = tuple(getattr(self, "data_source_headers", ())) if self.data_source_path is not None and self.db_rows else ()
        editor_option_to_key, editor_key_to_option = _data_field_option_maps(editor_headers)
        selected_field = field_var.get()
        if selected_field not in editor_key_to_option:
            selected_field = next(
                (header for header in editor_headers if canonical_db_field(header) == field_var.get()),
                "",
            )
        editor_field_option_var = tk.StringVar(value=editor_key_to_option.get(selected_field, "연결 안 함"))
        align_var = tk.StringVar(value=ALIGNMENTS.get(str(element.get("align", "left")), "왼쪽"))
        arrange_var = tk.StringVar(value=ARRANGE_MODES.get(str(element.get("arrange", "normal")), "일반"))
        rotation_var = tk.StringVar(value=ELEMENT_ROTATION_LABELS[_element_rotation(element)])
        x_var = tk.StringVar(value=str(element.get("x", 0)))
        y_var = tk.StringVar(value=str(element.get("y", 0)))
        w_var = tk.StringVar(value=str(element.get("width", 1)))
        h_var = tk.StringVar(value=str(element.get("height", 1)))
        font_var = tk.StringVar(value=str(element.get("font_size", 10)))
        font_name_var = tk.StringVar(value=str(element.get("font_name") or DEFAULT_FONT_NAME))
        reverse_var = tk.BooleanVar(value=bool(element.get("reverse", False)))
        required_var = tk.BooleanVar(value=bool(element.get("required", False)))
        table_rows_var = tk.StringVar(value=str(_table_shape(element)[0]))
        table_cols_var = tk.StringVar(value=str(_table_shape(element)[1]))
        stroke_width_var = tk.StringVar(value=f"{_stroke_width_mm(element):g}")
        barcode_options = _barcode_options(element) if _is_code_element(element) else dict(BARCODE_OPTION_DEFAULTS)
        module_width_var = tk.StringVar(value=str(barcode_options.get("module_width", 0)))
        wide_ratio_var = tk.StringVar(value=str(barcode_options.get("wide_ratio", 2.5)))
        quiet_zone_var = tk.StringVar(value=str(barcode_options.get("quiet_zone", 10)))
        human_readable_var = tk.BooleanVar(value=bool(barcode_options.get("human_readable", True)))
        check_digit_var = tk.StringVar(value=BARCODE_CHECK_DIGIT_LABELS.get(str(barcode_options.get("check_digit", "auto")), "자동"))
        cell_size_var = tk.StringVar(value=str(barcode_options.get("cell_size", 0)))
        qr_ecc_var = tk.StringVar(value=str(barcode_options.get("qr_ecc", "M")))
        pdf417_rows_var = tk.StringVar(value=str(barcode_options.get("pdf417_rows", 0)))
        pdf417_columns_var = tk.StringVar(value=str(barcode_options.get("pdf417_columns", 0)))
        pdf417_security_var = tk.StringVar(value=str(barcode_options.get("pdf417_security", 2)))
        applying = False

        def add_row(row: int, label: str, widget: tk.Widget) -> None:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)
            widget.grid(row=row, column=1, sticky="ew", pady=6)

        type_combo = ttk.Combobox(frame, textvariable=type_var, values=[ELEMENT_TYPES[key] for key in VISIBLE_ELEMENT_TYPE_KEYS], state="readonly")
        code_combo = ttk.Combobox(frame, textvariable=code_var, values=list(BARCODE_TYPES.values()), state="readonly")
        text_editor = tk.Text(
            frame,
            height=4,
            wrap="word",
            undo=True,
            font=TYPOGRAPHY.body,
            bg=COLORS.surface,
            fg=COLORS.text_primary,
            relief="solid",
            bd=1,
        )
        text_editor.insert("1.0", text_var.get())
        editor_field_combo = ttk.Combobox(
            frame,
            textvariable=editor_field_option_var,
            values=list(editor_option_to_key),
            state="readonly",
        )
        align_combo = ttk.Combobox(frame, textvariable=align_var, values=list(ALIGNMENTS.values()), state="readonly")
        arrange_combo = ttk.Combobox(frame, textvariable=arrange_var, values=list(ARRANGE_MODES.values()), state="readonly")
        rotation_combo = ttk.Combobox(frame, textvariable=rotation_var, values=list(ELEMENT_ROTATION_LABELS.values()), state="readonly")
        font_combo = ttk.Combobox(frame, textvariable=font_name_var, values=self.font_choices, state="readonly")
        add_row(0, "종류", type_combo)
        add_row(1, "코드 종류", code_combo)
        add_row(2, "텍스트/데이터", text_editor)
        editor_field_label = ttk.Label(frame, text="DB 열")
        editor_field_label.grid(row=3, column=0, sticky="w", padx=(0, 10), pady=6)
        editor_field_combo.grid(row=3, column=1, sticky="ew", pady=6)
        add_row(4, "정렬", align_combo)
        add_row(5, "배치", arrange_combo)
        add_row(6, "방향", rotation_combo)
        add_row(7, "글꼴", font_combo)

        numeric = ttk.Frame(frame, style="Surface.TFrame")
        numeric.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for column in range(5):
            numeric.columnconfigure(column, weight=1)
        for column, (label, variable) in enumerate((("왼쪽 위치(mm)", x_var), ("위쪽 위치(mm)", y_var), ("가로(mm)", w_var), ("세로(mm)", h_var), ("글자크기(pt)", font_var))):
            ttk.Label(numeric, text=label).grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else 6, 0))
            ttk.Entry(numeric, textvariable=variable, width=7).grid(row=1, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=(4, 0))
        ttk.Checkbutton(numeric, text="텍스트 반전", variable=reverse_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(numeric, text="연결된 값 필수", variable=required_var).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )
        ttk.Label(numeric, text="행").grid(row=2, column=2, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Entry(numeric, textvariable=table_rows_var, width=7).grid(row=3, column=2, sticky="ew", padx=(6, 0), pady=(4, 0))
        ttk.Label(numeric, text="열").grid(row=2, column=3, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Entry(numeric, textvariable=table_cols_var, width=7).grid(row=3, column=3, sticky="ew", padx=(6, 0), pady=(4, 0))
        stroke_width_label = ttk.Label(numeric, text="선두께(mm)")
        stroke_width_label.grid(row=2, column=4, sticky="w", padx=(6, 0), pady=(8, 0))
        stroke_width_entry = ttk.Entry(numeric, textvariable=stroke_width_var, width=7)
        stroke_width_entry.grid(row=3, column=4, sticky="ew", padx=(6, 0), pady=(4, 0))

        barcode_frame = ttk.Frame(frame, style="Surface.TFrame")
        barcode_frame.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for column in range(4):
            barcode_frame.columnconfigure(column, weight=1)
        ttk.Label(barcode_frame, text="바코드 옵션", style="PanelTitle.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        option_widgets: list[tk.Widget] = []

        def option_entry(row: int, column: int, label: str, variable: tk.StringVar, width: int = 7) -> ttk.Entry:
            ttk.Label(barcode_frame, text=label).grid(row=row, column=column, sticky="w", padx=(0 if column == 0 else 8, 0), pady=(4, 2))
            entry = ttk.Entry(barcode_frame, textvariable=variable, width=width)
            entry.grid(row=row + 1, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
            option_widgets.append(entry)
            return entry

        option_entry(1, 0, "좁은 막대 폭(dot, 0=자동)", module_width_var)
        option_entry(1, 1, "굵은 비율", wide_ratio_var)
        option_entry(1, 2, "바코드 좌우 여백(dot)", quiet_zone_var)
        check_combo = ttk.Combobox(barcode_frame, textvariable=check_digit_var, values=list(BARCODE_CHECK_DIGIT_LABELS.values()), state="readonly", width=8)
        ttk.Label(barcode_frame, text="체크디지트").grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(4, 2))
        check_combo.grid(row=2, column=3, sticky="ew", padx=(8, 0))
        option_widgets.append(check_combo)
        hri_check = ttk.Checkbutton(barcode_frame, text="하단 숫자 표시", variable=human_readable_var)
        hri_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        option_widgets.append(hri_check)
        option_entry(4, 0, "셀 크기(네이티브)", cell_size_var)
        qr_ecc_combo = ttk.Combobox(barcode_frame, textvariable=qr_ecc_var, values=["L", "M", "Q", "H"], state="readonly", width=7)
        ttk.Label(barcode_frame, text="QR 오류 복원 수준").grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(4, 2))
        qr_ecc_combo.grid(row=5, column=1, sticky="ew", padx=(8, 0))
        option_widgets.append(qr_ecc_combo)
        option_entry(4, 2, "PDF 행", pdf417_rows_var)
        option_entry(4, 3, "PDF 열", pdf417_columns_var)
        option_entry(6, 0, "PDF 보안", pdf417_security_var)

        def sync_data_field_state() -> None:
            element_type = _element_type_from_label(type_var.get(), str(element.get("type", "text")))
            visible = bool(editor_headers) and element_type in DB_MAPPABLE_ELEMENT_TYPES
            if visible:
                editor_field_label.grid()
                editor_field_combo.grid()
                editor_field_combo.configure(state="readonly")
                return
            editor_field_label.grid_remove()
            editor_field_combo.grid_remove()

        def apply_editor_data_field(*_args: object) -> None:
            element_type = _element_type_from_label(type_var.get(), str(element.get("type", "text")))
            if element_type not in DB_MAPPABLE_ELEMENT_TYPES:
                return
            field = editor_option_to_key.get(editor_field_option_var.get(), "")
            previous_field = field_var.get()
            previous_token = "{{" + previous_field + "}}" if previous_field else ""
            if field:
                token = "{{" + field + "}}"
                field_var.set(field)
                text_editor.delete("1.0", "end")
                text_editor.insert("1.0", token)
                text_editor.edit_modified(False)
                text_var.set(token)
                return
            if previous_token and text_var.get() == previous_token:
                fallback = BARCODE_FALLBACK_VALUE if element_type in {"barcode", "qr"} else "새 텍스트"
                value = str(self.preview_row.get(previous_field, "")) or fallback
                text_editor.delete("1.0", "end")
                text_editor.insert("1.0", value)
                text_editor.edit_modified(False)
                text_var.set(value)
            field_var.set("")

        def sync_code_state() -> None:
            element_type = _element_type_from_label(type_var.get(), str(element.get("type", "text")))
            if element_type == "qr":
                code_var.set("QR")
                code_combo.configure(state="disabled")
            elif element_type == "barcode":
                code_combo.configure(state="readonly")
            else:
                code_combo.configure(state="disabled")
            option_state = "normal" if element_type in {"barcode", "qr"} else "disabled"
            for widget in option_widgets:
                try:
                    widget.configure(state=option_state)
                except tk.TclError:
                    pass
            if element_type in {"barcode", "qr"}:
                if isinstance(check_combo, ttk.Combobox):
                    check_combo.configure(state="readonly")
                if isinstance(qr_ecc_combo, ttk.Combobox):
                    qr_ecc_combo.configure(state="readonly")

        def sync_stroke_state() -> None:
            element_type = _element_type_from_label(type_var.get(), str(element.get("type", "text")))
            state = "normal" if element_type in STROKE_ELEMENT_TYPES else "disabled"
            stroke_width_label.configure(state=state)
            stroke_width_entry.configure(state=state)
            if state == "normal" and not stroke_width_var.get().strip():
                stroke_width_var.set(f"{DEFAULT_STROKE_WIDTH_MM:g}")

        def apply_live(*_args: object) -> None:
            nonlocal applying
            if applying:
                return
            applying = True
            reverse_align = {label: key for key, label in ALIGNMENTS.items()}
            reverse_arrange = {label: key for key, label in ARRANGE_MODES.items()}
            element_type = _element_type_from_label(type_var.get(), str(element.get("type", "text")))
            element["type"] = element_type
            element["text"] = text_var.get()
            element["field"] = field_var.get()
            element["align"] = reverse_align.get(align_var.get(), str(element.get("align", "left")))
            element["arrange"] = reverse_arrange.get(arrange_var.get(), str(element.get("arrange", "normal")))
            element["rotation"] = ELEMENT_ROTATION_VALUES.get(rotation_var.get(), 0)
            if element_type in {"barcode", "qr"}:
                element["barcode_type"] = "qr" if element_type == "qr" else _barcode_key_from_label(code_var.get())
                element["barcode_options"] = _normalize_barcode_options(
                    {
                        "module_width": module_width_var.get(),
                        "wide_ratio": wide_ratio_var.get(),
                        "quiet_zone": quiet_zone_var.get(),
                        "human_readable": human_readable_var.get(),
                        "check_digit": BARCODE_CHECK_DIGIT_VALUES.get(check_digit_var.get(), "auto"),
                        "cell_size": cell_size_var.get(),
                        "qr_ecc": qr_ecc_var.get(),
                        "pdf417_rows": pdf417_rows_var.get(),
                        "pdf417_columns": pdf417_columns_var.get(),
                        "pdf417_security": pdf417_security_var.get(),
                    }
                )
            else:
                element.pop("barcode_type", None)
                element.pop("barcode_options", None)
            element["x"] = _float_value(x_var.get(), float(element.get("x", 0)))
            element["y"] = _float_value(y_var.get(), float(element.get("y", 0)))
            element["width"] = max(1.0, _float_value(w_var.get(), float(element.get("width", 1))))
            element["height"] = max(0.5, _float_value(h_var.get(), float(element.get("height", 1))))
            element["font_size"] = max(6, min(48, int(_float_value(font_var.get(), float(element.get("font_size", 10))))))
            element["font_name"] = font_name_var.get() or DEFAULT_FONT_NAME
            element["reverse"] = bool(reverse_var.get())
            if element_type in TEXT_ELEMENT_TYPES:
                element["required"] = bool(required_var.get())
            else:
                element.pop("required", None)
            if element_type == "table":
                _apply_table_shape(
                    element,
                    max(1, min(20, int(_float_value(table_rows_var.get(), 3)))),
                    max(1, min(20, int(_float_value(table_cols_var.get(), 3)))),
                )
            else:
                element.pop("table_rows", None)
                element.pop("table_cols", None)
                element.pop("table_row_positions", None)
                element.pop("table_col_positions", None)
            if element_type in STROKE_ELEMENT_TYPES:
                element["stroke_width"] = _normalize_stroke_width(stroke_width_var.get())
            else:
                element.pop("stroke_width", None)
            self.selected_id = str(element["id"])
            self.redraw()
            self._save_recovery()
            self.status_var.set("편집 내용을 미리보기에 반영했습니다.")
            applying = False

        def on_type_change(*_args: object) -> None:
            sync_code_state()
            sync_data_field_state()
            sync_stroke_state()
            apply_live()

        for variable in (
            text_var,
            field_var,
            align_var,
            arrange_var,
            rotation_var,
            code_var,
            x_var,
            y_var,
            w_var,
            h_var,
            font_var,
            font_name_var,
            reverse_var,
            table_rows_var,
            table_cols_var,
            stroke_width_var,
            module_width_var,
            wide_ratio_var,
            quiet_zone_var,
            human_readable_var,
            check_digit_var,
            cell_size_var,
            qr_ecc_var,
            pdf417_rows_var,
            pdf417_columns_var,
            pdf417_security_var,
        ):
            variable.trace_add("write", apply_live)
        type_var.trace_add("write", on_type_change)

        def on_text_modified(_event: tk.Event) -> None:
            if not text_editor.edit_modified():
                return
            text_editor.edit_modified(False)
            value = text_editor.get("1.0", "end-1c")
            if text_var.get() != value:
                text_var.set(value)

        text_editor.bind("<<Modified>>", on_text_modified)
        editor_field_combo.bind("<<ComboboxSelected>>", apply_editor_data_field)
        sync_code_state()
        sync_data_field_state()
        sync_stroke_state()
        self._history_suspended += 1

        def record_editor_close(event: tk.Event) -> None:
            if event.widget is editor:
                self._history_suspended -= 1
                self._record_history()

        editor.bind("<Destroy>", record_editor_close, add="+")

        buttons = ttk.Frame(editor, style="Surface.TFrame", padding=(18, 10, 18, 14))
        buttons.grid(row=1, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        close_button = ttk.Button(buttons, text="닫기", command=editor.destroy, style="Primary.TButton")
        close_button.grid(row=0, column=1, sticky="e")

        def on_close() -> None:
            self.load_selected_properties()
            editor.destroy()

        close_button.configure(command=on_close)
        editor.protocol("WM_DELETE_WINDOW", on_close)
        text_editor.focus_set()

    def find_element_at(self, x: float, y: float) -> dict[str, object] | None:
        hits: list[dict[str, object]] = []
        for element in reversed(self._drawing_elements()):
            x1, y1, x2, y2 = self.element_bbox(element)
            if x1 <= x <= x2 and y1 <= y <= y2:
                hits.append(element)
        if not hits:
            return None
        for mode_group in ({"normal", "front"}, {"through"}, {"behind"}):
            for element in hits:
                if str(element.get("arrange", "normal")) in mode_group:
                    return element
        return hits[0]

    def selected_element(self) -> dict[str, object] | None:
        if self.selected_id is None:
            return None
        for element in self.elements:
            if str(element.get("id")) == self.selected_id:
                return element
        return None

    def _selected_ids(self) -> set[str]:
        selected_id = self.__dict__.get("selected_id")
        if selected_id is None:
            return set()
        ids = set(self.__dict__.get("selected_ids", set()))
        return ids if selected_id in ids else {str(selected_id)}

    def _selected_elements(self) -> list[dict[str, object]]:
        ids = self._selected_ids()
        return [element for element in self.elements if str(element.get("id")) in ids]

    def _canvas_point(self, event: tk.Event) -> tuple[float, float]:
        canvas = self.__dict__.get("canvas")
        if canvas is not None and callable(getattr(canvas, "canvasx", None)):
            return float(canvas.canvasx(event.x)), float(canvas.canvasy(event.y))
        return float(event.x), float(event.y)

    def _drag_coordinate(self, value: float) -> float:
        snap_var = self.__dict__.get("snap_to_grid_var")
        snap = bool(snap_var.get()) if snap_var is not None else False
        return round(max(0.0, value), 0 if snap else 1)

    def load_selected_properties(self) -> None:
        element = self.selected_element()
        if element is None:
            self.clear_property_panel()
            return
        self.type_var.set(ELEMENT_TYPES.get(str(element.get("type")), "텍스트"))
        self.barcode_type_var.set(BARCODE_TYPES.get(_barcode_type(element), "Code 128") if _is_code_element(element) else "")
        self.text_var.set(str(element.get("text", "")))
        self.field_var.set(str(element.get("field", "")))
        self.align_var.set(ALIGNMENTS.get(str(element.get("align", "left")), "왼쪽"))
        self.arrange_var.set(ARRANGE_MODES.get(str(element.get("arrange", "normal")), "일반"))
        self.rotation_var.set(ELEMENT_ROTATION_LABELS[_element_rotation(element)])
        self.x_var.set(str(element.get("x", 0)))
        self.y_var.set(str(element.get("y", 0)))
        self.w_var.set(str(element.get("width", 1)))
        self.h_var.set(str(element.get("height", 1)))
        self.font_var.set(str(element.get("font_size", 10)))
        self.font_name_var.set(str(element.get("font_name") or DEFAULT_FONT_NAME))
        self.reverse_var.set(bool(element.get("reverse", False)))
        rows, cols = _table_shape(element)
        self.table_rows_var.set(str(rows))
        self.table_cols_var.set(str(cols))
        if str(element.get("type")) in STROKE_ELEMENT_TYPES:
            self.stroke_width_var.set(f"{_stroke_width_mm(element):g}")
        else:
            self.stroke_width_var.set("")
        self._refresh_field_options()
        self._sync_property_widget_states()

    def clear_property_panel(self) -> None:
        for variable in (
            self.type_var,
            self.barcode_type_var,
            self.text_var,
            self.field_var,
            self.x_var,
            self.y_var,
            self.w_var,
            self.h_var,
            self.font_var,
            self.font_name_var,
            self.align_var,
            self.arrange_var,
            self.rotation_var,
            self.table_rows_var,
            self.table_cols_var,
            self.stroke_width_var,
        ):
            variable.set("")
        self.field_option_var.set("연결 안 함")
        self.reverse_var.set(False)
        self._sync_property_widget_states()

    def _sync_property_widget_states(self) -> None:
        element = self.selected_element()
        element_type = str(element.get("type", "")) if element is not None else ""
        has_selection = element is not None
        state_map = {
            "always": has_selection,
            "barcode": has_selection and element_type in {"barcode", "qr"},
            "text": has_selection and (element_type in TEXT_ELEMENT_TYPES or element_type in {"barcode", "qr"}),
            "table": has_selection and element_type == "table",
            "stroke": has_selection and element_type in STROKE_ELEMENT_TYPES,
        }
        for group, widgets in self.property_widgets.items():
            enabled = state_map.get(group, has_selection)
            for widget in widgets:
                self._set_property_widget_enabled(widget, enabled)
        self._update_field_control_visibility()

    def _set_property_widget_enabled(self, widget: tk.Widget, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        try:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly" if enabled else "disabled")
            else:
                widget.configure(state=state)
        except tk.TclError:
            pass

    def apply_properties(self) -> None:
        element = self.selected_element()
        if element is None:
            messagebox.showwarning("속성 적용", "선택된 요소가 없습니다.")
            return
        if element.get("locked"):
            messagebox.showwarning("속성 적용", "잠긴 개체입니다. 잠금을 해제한 뒤 편집하세요.")
            return
        reverse_align = {label: key for key, label in ALIGNMENTS.items()}
        reverse_arrange = {label: key for key, label in ARRANGE_MODES.items()}
        element_type = _element_type_from_label(self.type_var.get(), str(element.get("type", "text")))
        element["type"] = element_type
        element["text"] = self.text_var.get()
        element["field"] = self.field_option_to_key.get(self.field_option_var.get(), self.field_var.get())
        self.field_var.set(str(element["field"]))
        element["align"] = reverse_align.get(self.align_var.get(), str(element.get("align", "left")))
        element["arrange"] = reverse_arrange.get(self.arrange_var.get(), str(element.get("arrange", "normal")))
        element["rotation"] = ELEMENT_ROTATION_VALUES.get(self.rotation_var.get(), _element_rotation(element))
        if element_type in {"barcode", "qr"}:
            element["barcode_type"] = "qr" if element_type == "qr" else _barcode_key_from_label(self.barcode_type_var.get())
        else:
            element.pop("barcode_type", None)
        element["x"] = _float_value(self.x_var.get(), float(element.get("x", 0)))
        element["y"] = _float_value(self.y_var.get(), float(element.get("y", 0)))
        element["width"] = max(1.0, _float_value(self.w_var.get(), float(element.get("width", 1))))
        element["height"] = max(0.5, _float_value(self.h_var.get(), float(element.get("height", 1))))
        element["font_size"] = max(6, min(48, int(_float_value(self.font_var.get(), float(element.get("font_size", 10))))))
        element["font_name"] = self.font_name_var.get() or DEFAULT_FONT_NAME
        element["reverse"] = bool(self.reverse_var.get())
        if element_type == "table":
            _apply_table_shape(
                element,
                max(1, min(20, int(_float_value(self.table_rows_var.get(), 3)))),
                max(1, min(20, int(_float_value(self.table_cols_var.get(), 3)))),
            )
        else:
            element.pop("table_rows", None)
            element.pop("table_cols", None)
            element.pop("table_row_positions", None)
            element.pop("table_col_positions", None)
        if element_type in STROKE_ELEMENT_TYPES:
            element["stroke_width"] = _normalize_stroke_width(
                self.stroke_width_var.get(),
                _stroke_width_mm(element),
            )
        else:
            element.pop("stroke_width", None)
        self.redraw()
        self.status_var.set("속성을 적용했습니다.")

    def delete_selected(self) -> None:
        selected = self._selected_ids()
        if not selected:
            return
        unlocked = {str(element["id"]) for element in self._selected_elements() if not element.get("locked")}
        if not unlocked:
            self.status_var.set("잠긴 개체는 삭제할 수 없습니다. 잠금을 먼저 해제하세요.")
            return
        self.elements = [element for element in self.elements if str(element.get("id")) not in unlocked]
        self.selected_id = None
        self.selected_ids = set()
        self.clear_property_panel()
        self.redraw()

    def duplicate_selected(self) -> None:
        selected = self._selected_elements()
        if not selected:
            return
        label = self.template["label"]
        label_width = float(label["width_mm"])  # type: ignore[index]
        label_height = float(label["height_mm"])  # type: ignore[index]
        source_group_ids = {str(element.get("group_id", "")) for element in selected}
        new_group_id = uuid4().hex if len(source_group_ids) == 1 and "" not in source_group_ids else ""
        copies: list[dict[str, object]] = []
        for element in selected:
            duplicate = copy.deepcopy(element)
            duplicate["id"] = uuid4().hex
            duplicate["locked"] = False
            duplicate["x"] = round(min(label_width - float(duplicate.get("width", 1)), float(element.get("x", 0)) + 2), 1)
            duplicate["y"] = round(min(label_height - float(duplicate.get("height", 1)), float(element.get("y", 0)) + 2), 1)
            if new_group_id:
                duplicate["group_id"] = new_group_id
            else:
                duplicate.pop("group_id", None)
            copies.append(duplicate)
        self.elements.extend(copies)
        self.selected_ids = {str(element["id"]) for element in copies}
        self.selected_id = str(copies[-1]["id"])
        self.load_selected_properties()
        self.redraw()
        self.status_var.set(f"개체 {len(copies)}개를 복제했습니다.")

    def group_selected(self) -> None:
        selected = self._selected_elements()
        if len(selected) < 2:
            self.status_var.set("그룹으로 묶을 개체를 Ctrl+클릭으로 2개 이상 선택하세요.")
            return
        group_id = uuid4().hex
        for element in selected:
            element["group_id"] = group_id
        self.redraw()
        self.status_var.set(f"개체 {len(selected)}개를 그룹으로 묶었습니다.")

    def ungroup_selected(self) -> None:
        selected = self._selected_elements()
        for element in selected:
            element.pop("group_id", None)
        if selected:
            self.redraw()
            self.status_var.set("선택한 개체의 그룹을 해제했습니다.")

    def toggle_lock_selected(self) -> None:
        selected = self._selected_elements()
        if not selected:
            return
        lock = any(not element.get("locked") for element in selected)
        for element in selected:
            element["locked"] = lock
        self.redraw()
        self.status_var.set(f"개체 {len(selected)}개를 {'잠갔습니다' if lock else '잠금 해제했습니다'}.")

    def _nudge_key(self, dx: float, dy: float) -> str:
        self.nudge_selected(dx, dy)
        return "break"

    def nudge_selected(self, dx: float, dy: float) -> None:
        label = self.template["label"]
        label_width = float(label["width_mm"])  # type: ignore[index]
        label_height = float(label["height_mm"])  # type: ignore[index]
        moved = 0
        for element in self._selected_elements():
            if element.get("locked"):
                continue
            max_x = max(0.0, label_width - float(element.get("width", 1)))
            max_y = max(0.0, label_height - float(element.get("height", 1)))
            element["x"] = round(max(0.0, min(max_x, float(element.get("x", 0)) + dx)), 1)
            element["y"] = round(max(0.0, min(max_y, float(element.get("y", 0)) + dy)), 1)
            moved += 1
        if moved:
            self.load_selected_properties()
            self.redraw()

    def align_selected_left(self) -> None:
        selected = [element for element in self._selected_elements() if not element.get("locked")]
        if len(selected) < 2:
            return
        left = min(float(element.get("x", 0)) for element in selected)
        for element in selected:
            element["x"] = left
        self.load_selected_properties()
        self.redraw()

    def distribute_selected_horizontally(self) -> None:
        selected = sorted(
            (element for element in self._selected_elements() if not element.get("locked")),
            key=lambda element: float(element.get("x", 0)),
        )
        if len(selected) < 3:
            self.status_var.set("가로 간격 맞춤은 개체 3개 이상을 선택하세요.")
            return
        left_edge = float(selected[0].get("x", 0)) + float(selected[0].get("width", 1))
        right_edge = float(selected[-1].get("x", 0))
        interior_width = sum(float(element.get("width", 1)) for element in selected[1:-1])
        gap = (right_edge - left_edge - interior_width) / (len(selected) - 1)
        if gap < 0:
            self.status_var.set("개체가 겹쳐 간격을 맞출 수 없습니다. 먼저 라벨 안에 개체를 배치하세요.")
            return
        cursor = left_edge + gap
        for element in selected[1:-1]:
            element["x"] = round(cursor, 1)
            cursor += float(element.get("width", 1)) + gap
        self.load_selected_properties()
        self.redraw()

    def reorder_selected(self, direction: int) -> None:
        element = self.selected_element()
        if element is None:
            return
        index = self.elements.index(element)
        new_index = max(0, min(len(self.elements) - 1, index + direction))
        self.elements.pop(index)
        self.elements.insert(new_index, element)
        self.redraw()

    def center_selected(self) -> None:
        self._center_selected_axis("x")

    def center_selected_vertically(self) -> None:
        self._center_selected_axis("y")

    def _center_selected_axis(self, axis: str) -> None:
        selected = [element for element in self._selected_elements() if not element.get("locked")]
        if not selected:
            self.status_var.set("정렬할 개체를 선택하세요. 잠긴 개체는 이동하지 않습니다.")
            return
        label = self.template["label"]  # type: ignore[index]
        dimension = "width" if axis == "x" else "height"
        label_size = float(label[dimension + "_mm"])  # type: ignore[index]
        start = min(float(element.get(axis, 0)) for element in selected)
        end = max(float(element.get(axis, 0)) + float(element.get(dimension, 1)) for element in selected)
        if end - start > label_size:
            self.status_var.set("선택한 개체가 라벨보다 큽니다. 크기를 줄인 뒤 정렬하세요.")
            return
        delta = (label_size - (end - start)) / 2 - start
        for element in selected:
            element[axis] = round(float(element.get(axis, 0)) + delta, 1)
        self.load_selected_properties()
        self.redraw()
        self.status_var.set(f"선택한 개체 {len(selected)}개를 {'좌우' if axis == 'x' else '상하'} 가운데로 정렬했습니다.")

    def update_label_size(self) -> None:
        try:
            width = _normalize_label_mm(self.width_var.get(), DEFAULT_LABEL_WIDTH_MM)
            height = _normalize_label_mm(self.height_var.get(), DEFAULT_LABEL_HEIGHT_MM)
        except ValueError:
            messagebox.showerror("라벨 크기", "가로/세로를 숫자로 입력하세요.")
            return
        self.template["label"] = {"width_mm": width, "height_mm": height}
        self.redraw()
        self.status_var.set(f"라벨 크기를 {width:g}x{height:g}mm로 적용했습니다.")

    def reset_template(self) -> None:
        if not messagebox.askyesno("기본 템플릿", "현재 편집 내용을 기본 템플릿으로 초기화할까요?"):
            return
        self.template = default_template_from_config(self.config_path)
        self.elements = list(self.template["elements"])  # type: ignore[arg-type]
        self.selected_id = None
        self.selected_ids = set()
        self._load_values_to_controls()
        self.redraw()

    def new_label(self) -> None:
        if not self._confirm_save_changes("새 라벨을 만들기 전에"):
            return
        previous_path = self.template_path
        was_dirty = self._has_unsaved_changes()
        self.template_path = self.template_dir / "default_label.json"
        self.template = default_template_from_config(self.config_path)
        self.elements = []
        self.selected_id = None
        self.selected_ids = set()
        self.selected_data_indexes = set()
        self._data_context_version = self.__dict__.get("_data_context_version", 0) + 1
        self._saved_payload_signature = self._current_payload_signature()
        self._reset_history()
        self._load_values_to_controls()
        self.load_selected_properties()
        if "db_rows" in self.__dict__ and "data_tree" in self.__dict__:
            self.refresh_data_panel()
        self.redraw()
        if was_dirty:
            self._clear_recovery(previous_path)
        self.title(self._window_title())
        self.template_path_var.set(str(self.template_path))
        self.status_var.set(
            "새 빈 라벨입니다. 출력할 상품을 다시 선택하세요."
            if self.__dict__.get("data_source_path") is not None
            else "새 빈 라벨입니다. 상품 엑셀을 연결하거나 개체를 추가하세요."
        )
        self._update_document_state()

    def start_with_example(self) -> None:
        template_path = self.base_dir / "templates" / "sample_excel_product.gblabel"
        db_path = self.base_dir / "barcode_db.xlsx"
        try:
            template = load_template_file(template_path)
            rows, headers = load_db_source(db_path)
        except Exception as exc:
            messagebox.showerror("예제 시작 실패", f"예제 라벨이나 상품 엑셀을 읽지 못했습니다.\n{exc}", parent=self)
            return
        if not self._confirm_save_changes("예제를 열기 전에"):
            return
        previous_path = self.template_path
        was_dirty = self._has_unsaved_changes()
        self.template_path = self.template_dir / "default_label.json"
        self.template = template
        self.elements = list(template["elements"])  # type: ignore[arg-type]
        self.selected_id = None
        self.selected_ids = set()
        self._data_context_version = self.__dict__.get("_data_context_version", 0) + 1
        self._reset_history()
        self._load_values_to_controls()
        self.data_source_path = db_path
        self._apply_loaded_db_rows(rows, headers)
        self.title(self._window_title())
        self.template_path_var.set("예제 라벨 · 저장 전")
        if was_dirty:
            self._clear_recovery(previous_path)
        self._save_recovery()
        self.status_var.set("예제 라벨과 상품 엑셀을 연결했습니다. 출력할 상품을 선택한 뒤 인쇄파일로 먼저 확인하세요.")
        self._update_document_state()
        self.open_data_source_window()

    def _offer_start_dialog(self) -> None:
        if self.elements or self._has_unsaved_changes() or self._initial_template_error:
            return
        dialog = tk.Toplevel(self)
        dialog.title("라벨 작업 시작")
        dialog.transient(self)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=(24, 22, 24, 22))
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="어떤 작업을 시작할까요?", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="상품 엑셀 연결 → 라벨 배치 → 상품 선택 → 인쇄파일 확인 순서로 진행합니다.",
            style="Hint.TLabel", wraplength=450,
        ).grid(row=1, column=0, sticky="w", pady=(8, 18))

        def choose(action: Callable[[], None]) -> None:
            dialog.destroy()
            action()

        ttk.Button(frame, text="예제로 시작 · 상품 엑셀 포함", command=lambda: choose(self.start_with_example), style="Primary.TButton").grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(frame, text="최근 라벨 열기", command=lambda: choose(self.open_recent_template), style="Secondary.TButton").grid(row=3, column=0, sticky="ew", pady=4)
        ttk.Button(frame, text="새 빈 라벨", command=lambda: choose(self.new_label), style="Secondary.TButton").grid(row=4, column=0, sticky="ew", pady=4)
        ttk.Button(frame, text="반복 출력 화면", command=lambda: choose(self.open_output_workspace), style="Secondary.TButton").grid(row=5, column=0, sticky="ew", pady=(12, 4))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.grab_set()

    def open_recent_template(self) -> None:
        recent = self._recent_template_paths()
        if not recent:
            messagebox.showinfo("최근 라벨", "최근 작업한 라벨이 없습니다. 파일을 선택하세요.", parent=self)
            self.open_template()
            return
        dialog = tk.Toplevel(self)
        dialog.title("최근 라벨")
        dialog.transient(self)
        set_initial_window_size(dialog, preferred_width=600, preferred_height=360, minimum_width=440, minimum_height=280)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(dialog, text="최근 라벨", style="Title.TLabel").grid(row=0, column=0, sticky="w", padx=18, pady=(16, 8))
        listbox = tk.Listbox(dialog, font=TYPOGRAPHY.body, activestyle="dotbox")
        listbox.grid(row=1, column=0, sticky="nsew", padx=18)
        for path in recent:
            listbox.insert("end", f"{path.name}  ·  {path.parent}")
        listbox.selection_set(0)

        def open_selected(_event: tk.Event | None = None) -> None:
            selection = listbox.curselection()
            if not selection or not self._confirm_save_changes("최근 라벨을 열기 전에"):
                return
            try:
                self.open_template_path(recent[selection[0]])
            except Exception as exc:
                messagebox.showerror("최근 라벨 열기 실패", str(exc), parent=dialog)
                return
            dialog.destroy()

        actions = ttk.Frame(dialog, padding=(18, 10, 18, 16))
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="다른 파일 열기", command=lambda: (dialog.destroy(), self.open_template()), style="Secondary.TButton").grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="열기", command=open_selected, style="Primary.TButton").grid(row=0, column=1, sticky="e")
        listbox.bind("<Double-Button-1>", open_selected)
        listbox.bind("<Return>", open_selected)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())

    def open_output_workspace(self) -> None:
        manager_exe = self.install_dir / "라벨출력관리.exe"
        if manager_exe.is_file():
            command = [str(manager_exe), "--base-dir", str(self.base_dir)]
        elif not getattr(sys, "frozen", False):
            command = [sys.executable, "-m", "barcode_label_automation.label_manager_app", "--base-dir", str(self.base_dir)]
        else:
            messagebox.showerror("반복 출력 화면", "라벨출력관리.exe를 찾을 수 없습니다. 고객 배포 폴더 전체를 확인하세요.", parent=self)
            return
        try:
            subprocess.Popen(command, cwd=str(self.base_dir))
        except OSError as exc:
            messagebox.showerror("반복 출력 화면", f"출력 화면을 열지 못했습니다.\n{exc}", parent=self)
            return
        self.status_var.set("반복 출력 화면을 열었습니다. 상품을 선택해 매수를 확인한 뒤 출력하세요.")

    def _recent_template_paths(self) -> list[Path]:
        path = self.base_dir / "out" / "designer_recent_files.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(payload, dict) or not isinstance(payload.get("paths"), list):
            return []
        return [candidate for raw in payload["paths"] if isinstance(raw, str)
                and (candidate := Path(raw)).is_file() and candidate.suffix.lower() == LABEL_FILE_EXTENSION][:8]

    def _remember_template(self) -> None:
        if "base_dir" not in self.__dict__ or "template_path" not in self.__dict__:
            return
        if self._is_default_template_path() or self.template_path.name.startswith("sample_"):
            return
        path = self.template_path.resolve()
        recent = [other for other in self._recent_template_paths() if other.resolve() != path]
        try:
            _atomic_write_json(self.base_dir / "out" / "designer_recent_files.json", {
                "paths": [str(item) for item in [path, *recent][:8]],
            })
        except OSError:
            self.status_var.set("라벨은 저장했지만 최근 파일 목록을 갱신하지 못했습니다.")

    def _update_document_state(self) -> None:
        state_var = self.__dict__.get("document_state_var")
        if state_var is None:
            return
        name = "새 라벨" if self._is_default_template_path() else self.template_path.name
        state = "미저장 변경 있음" if self._has_unsaved_changes() else "저장됨"
        state_var.set(f"{name} · {state}")
        self.title(self._window_title())

    def open_template_window(self) -> None:
        if self.template_window is not None and self.template_window.winfo_exists():
            self.template_path_var.set(str(self.template_path))
            self.template_window.deiconify()
            self.template_window.lift()
            self.template_window.focus_force()
            return
        dialog = tk.Toplevel(self)
        self.template_window = dialog
        dialog.title("파일")
        set_initial_window_size(
            dialog,
            preferred_width=600,
            preferred_height=560,
            minimum_width=460,
            minimum_height=420,
        )
        dialog.configure(bg=COLORS.surface)
        dialog.transient(self)
        apply_window_icon(dialog, base_dir=self.base_dir, install_dir=self.install_dir)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        frame = ttk.Frame(dialog, style="Surface.TFrame", padding=(24, 22, 24, 20))
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="파일", style="SidePanelTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        tk.Label(
            frame,
            textvariable=self.template_path_var,
            bg=COLORS.surface,
            fg=COLORS.text_secondary,
            font=TYPOGRAPHY.caption,
            justify="left",
            anchor="w",
            wraplength=480,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        def run_action(action: Callable[[], object]) -> None:
            action()
            self.template_path_var.set(str(self.template_path))

        actions = (
            ("저장", self.save_template, "Primary.TButton"),
            ("다른 이름으로 저장", self.save_template_as, "Secondary.TButton"),
            ("기존 파일 불러오기", self.open_template, "Secondary.TButton"),
            ("최근 라벨", self.open_recent_template, "Secondary.TButton"),
        )
        for index, (text, action, style) in enumerate(actions):
            ttk.Button(frame, text=text, command=lambda action=action: run_action(action), style=style).grid(
                row=2 + (index // 2),
                column=index % 2,
                sticky="ew",
                padx=(0 if index % 2 == 0 else 5, 0),
                pady=5,
            )
        ttk.Button(frame, text="닫기", command=self.close_template_window, style="Tool.TButton").grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(16, 0),
        )

        def close_window() -> None:
            self.template_window = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", close_window)
        dialog.bind("<Escape>", lambda _event: close_window())

    def close_template_window(self) -> None:
        dialog = self.template_window
        if dialog is None or not dialog.winfo_exists():
            self.template_window = None
            return
        self.template_window = None
        dialog.destroy()

    def template_payload(self) -> dict[str, object]:
        self.update_label_size()
        return {"version": 1, "label": self.template["label"], "elements": self.elements}

    def export_project(self) -> None:
        target = filedialog.asksaveasfilename(
            parent=self,
            initialdir=self.template_dir,
            defaultextension=PROJECT_EXTENSION,
            filetypes=[("채움랩 이동용 프로젝트", f"*{PROJECT_EXTENSION}")],
        )
        if not target:
            return
        try:
            export_portable_project(
                self.template_payload(),
                self.base_dir,
                Path(target),
                data_source_path=self.data_source_path,
                data_source_headers=self.data_source_headers,
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("프로젝트 내보내기 실패", str(exc), parent=self)
            return
        self.status_var.set(f"이동용 프로젝트 저장 완료: {Path(target).name}")
        messagebox.showinfo(
            "PC 이동 준비 완료",
            "라벨과 이미지를 한 파일로 저장했습니다. 상품 엑셀 원본과 프린터 설정은 포함하지 않습니다. "
            "새 PC에서 엑셀·프린터를 다시 연결하고 첫 장을 확인하세요.",
            parent=self,
        )

    def import_project(self) -> None:
        source = filedialog.askopenfilename(
            parent=self,
            initialdir=self.template_dir,
            filetypes=[("채움랩 이동용 프로젝트", f"*{PROJECT_EXTENSION}")],
        )
        if not source or not self._confirm_save_changes("프로젝트를 가져오기 전에"):
            return
        try:
            label_path, profile = import_portable_project(Path(source), self.base_dir)
            self.open_template_path(label_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("프로젝트 가져오기 실패", str(exc), parent=self)
            return
        source_name = str(profile.get("file_name", "")).strip()
        fonts = ", ".join(str(name) for name in profile.get("fonts", []))
        notice = "라벨과 이미지를 가져왔습니다. 상품 엑셀과 프린터를 다시 연결한 뒤 첫 장을 확인하세요."
        if source_name:
            notice += f"\n\n이전에 연결한 엑셀: {source_name}"
        if fonts:
            notice += f"\n사용한 글꼴: {fonts}"
        self.status_var.set("프로젝트 가져오기 완료 · 상품 엑셀 재연결 필요")
        messagebox.showinfo("프로젝트 가져오기", notice, parent=self)

    def show_bartender_migration_help(self) -> None:
        messagebox.showinfo(
            "다른 프로그램 도안 가져오기",
            ".btw/.nlbl/.lbl 같은 원본 파일의 이름만 .png로 바꿔서는 가져올 수 없습니다.\n\n"
            "원본 프로그램에서 실제 이미지로 내보내거나 인쇄 미리보기를 저장하세요. "
            "라벨 1장만 여백 없이 저장하고 용지 크기를 동일하게 맞춘 뒤 도안 불러오기 → 도안 적용 → 인식 값 검토를 사용합니다.\n\n"
            "글꼴·수식·DB 연결은 이미지에 남지 않아 다시 연결해야 합니다. "
            "원본 파일을 직접 읽는 연동 방식은 프로그램별 SDK와 버전 검증이 필요하며 현재 지원하지 않습니다.",
            parent=self,
        )

    def _is_default_template_path(self) -> bool:
        return self.template_path.resolve() == (self.template_dir / "default_label.json").resolve()

    def save_template(self) -> bool:
        if self._is_default_template_path():
            return self.save_template_as()
        try:
            payload = self.template_payload()
            self.template_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(self.template_path, payload)
        except Exception as exc:
            messagebox.showerror("템플릿 저장 실패", str(exc))
            return False
        self._saved_payload_signature = _template_signature(payload.get("label", {}), payload.get("elements", []))
        self._clear_recovery()
        self._remember_template()
        self._update_document_state()
        self.status_var.set(f"템플릿 저장 완료: {self.template_path}")
        if hasattr(self, "template_path_var"):
            self.template_path_var.set(str(self.template_path))
        return True

    def save_template_as(self) -> bool:
        self.template_dir.mkdir(parents=True, exist_ok=True)
        target = filedialog.asksaveasfilename(
            parent=self,
            initialdir=self.template_dir,
            defaultextension=LABEL_FILE_EXTENSION,
            filetypes=LABEL_FILE_TYPES,
        )
        if not target:
            return False
        target_path = Path(target)
        if not target_path.suffix:
            target_path = target_path.with_suffix(LABEL_FILE_EXTENSION)
        default_path = (self.template_dir / "default_label.json").resolve()
        if target_path.resolve() == default_path:
            messagebox.showerror(
                "기본 템플릿 저장 불가",
                "기본 템플릿은 빈 라벨로 유지됩니다. 다른 파일 이름으로 저장하세요.",
                parent=self,
            )
            return False

        previous_path = self.template_path
        self.template_path = target_path
        self.title(self._window_title())
        if hasattr(self, "template_path_var"):
            self.template_path_var.set(str(self.template_path))
        if self.save_template():
            self._clear_recovery(previous_path)
            return True

        self.template_path = previous_path
        self.title(self._window_title())
        if hasattr(self, "template_path_var"):
            self.template_path_var.set(str(self.template_path))
        return False

    def open_template(self) -> None:
        self.template_dir.mkdir(parents=True, exist_ok=True)
        source = filedialog.askopenfilename(parent=self, initialdir=self.template_dir, filetypes=LABEL_FILE_TYPES)
        if not source:
            return
        if not self._confirm_save_changes("다른 라벨 파일을 열기 전에"):
            return
        try:
            self.open_template_path(Path(source))
        except Exception as exc:
            messagebox.showerror("템플릿 불러오기 실패", str(exc))
            return

    def open_template_path(self, source: Path) -> None:
        source_path = source.resolve()
        if source_path.suffix.lower() == ".btw":
            raise ValueError(".btw 파일은 직접 열 수 없습니다. BarTender에서 PNG로 내보낸 뒤 도안 불러오기에서 다시 작성하세요.")
        default_path = (self.template_dir / "default_label.json").resolve()
        if source_path == default_path:
            template, recovery_path = ensure_blank_default_template(source_path, self.config_path)
        else:
            template = load_template_file(source_path)
            recovery_path = None
        elements = list(template["elements"])  # type: ignore[arg-type]
        previous_path = self.__dict__.get("template_path")
        was_dirty = self._has_unsaved_changes()
        self.template_path = source_path
        self.template = template
        self.elements = elements
        self._saved_payload_signature = self._current_payload_signature()
        self.selected_id = None
        self.selected_ids = set()
        self.selected_data_indexes = set()
        self._data_context_version = self.__dict__.get("_data_context_version", 0) + 1
        if (source_path.parent / "project_profile.json").is_file():
            self.disconnect_data_source()
        self._reset_history()
        self._remember_template()
        self.title(self._window_title())
        if hasattr(self, "template_path_var"):
            self.template_path_var.set(str(self.template_path))
        self._load_values_to_controls()
        self.load_selected_properties()
        if "db_rows" in self.__dict__ and "data_tree" in self.__dict__:
            self.refresh_data_panel()
        self.redraw()
        if was_dirty:
            self._clear_recovery(previous_path)
        self._offer_recovery()
        self.status_var.set(
            f"라벨 파일을 불러왔습니다: {self.template_path} · 출력할 상품을 다시 선택하세요."
            if self.__dict__.get("data_source_path") is not None
            else f"라벨 파일을 불러왔습니다: {self.template_path}"
        )
        self._update_document_state()
        if recovery_path is not None:
            messagebox.showinfo(
                "기본 템플릿 복구",
                f"기존 기본 템플릿 디자인을 복구 파일로 보존했습니다.\n\n{recovery_path}",
                parent=self,
            )

    def export_preview_png(self) -> None:
        out_dir = self.base_dir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "designer_preview.png"
        image = self.render_preview_image()
        image.save(path)
        self.status_var.set(f"미리보기 저장 완료: {path}")

    def run_selected_output(self, send_to_printer: bool) -> None:
        if self.data_source_path is None:
            messagebox.showwarning("선택 인쇄", "DB를 연결한 뒤 데이터 소스에서 출력할 행을 선택하세요.")
            return
        if not self.selected_data_rows(only_selected=True):
            messagebox.showwarning("선택 인쇄", "데이터 소스 왼쪽의 선택 칸에서 출력할 행을 하나 이상 선택하세요.")
            return
        self.run_output_test(send_to_printer=send_to_printer, selected_only=True)

    def run_primary_print(self) -> None:
        if self.data_source_path is None:
            self.run_output_test(send_to_printer=True)
            return
        self.run_selected_output(send_to_printer=True)

    def _validate_output_row(self, row: dict[str, str], *, row_number: int) -> None:
        printable_elements = [element for element in self._drawing_elements() if bool(element.get("printable", True))]
        if not printable_elements:
            raise ValueError("출력 가능한 개체가 없습니다. 텍스트, 바코드, 도형 또는 그림을 먼저 추가하세요.")

        label = self.template["label"]
        label_width = float(label["width_mm"])  # type: ignore[index]
        label_height = float(label["height_mm"])  # type: ignore[index]
        has_renderable_content = False
        for element_index, element in enumerate(printable_elements, start=1):
            element_type = str(element.get("type", "text"))
            if element.get("review_source") and not element.get("review_confirmed"):
                raise ValueError(f"{element_index}번 도안 인식 값이 미확인입니다. '인식 값 검토'에서 원본과 비교해 확인하세요.")
            x_mm = float(element.get("x", 0))
            y_mm = float(element.get("y", 0))
            width_mm = float(element.get("width", 1))
            height_mm = float(element.get("height", 1))
            if (x_mm < -0.01 or y_mm < -0.01 or width_mm <= 0 or height_mm <= 0
                    or x_mm + width_mm > label_width + 0.01
                    or y_mm + height_mm > label_height + 0.01):
                raise ValueError(
                    f"{element_index}번 개체가 라벨 {label_width:g}×{label_height:g}mm 경계를 벗어납니다. "
                    "위치와 크기를 조정한 뒤 출력하세요."
                )
            if element_type in TEXT_ELEMENT_TYPES:
                field = str(element.get("field", "")).strip()
                referenced_fields = {match.group(1).strip() for match in TEMPLATE_FIELD_RE.finditer(str(element.get("text", "")))}
                if field:
                    referenced_fields.add(field)
                required_fields = referenced_fields if bool(element.get("required", False)) else referenced_fields & {"item_name"}
                for required_field in sorted(required_fields):
                    if not str(row.get(required_field, "")).strip():
                        display_name = FIELD_LABELS.get(required_field, required_field)
                        raise ValueError(
                            f"{row_number}번째 출력 대상의 필수 값 '{display_name}'이 비어 있습니다. "
                            f"{element_index}번 개체의 DB 연결과 원본 행을 확인하세요."
                        )
                text = render_element_text(element, row)
                if text.strip():
                    _load_font(10, str(element.get("font_name") or DEFAULT_FONT_NAME))
                    has_renderable_content = True
                continue
            if element_type in {"barcode", "qr"}:
                _designer_code_value(element, row)
                if element_type == "barcode" and _barcode_type(element) in BARCODE_1D_BITMAP_TYPES:
                    _load_font(10, str(element.get("font_name") or DEFAULT_FONT_NAME))
                has_renderable_content = True
                continue
            if element_type in STROKE_ELEMENT_TYPES:
                has_renderable_content = True
                continue
            if element_type == "image":
                if self._load_element_image(element, 8, 8) is None:
                    raise ValueError(f"{row_number}번째 출력 대상의 그림 파일을 찾거나 읽을 수 없습니다.")
                has_renderable_content = True

        if not has_renderable_content:
            raise ValueError(f"{row_number}번째 출력 대상에 실제로 인쇄할 내용이 없습니다.")

    def _output_preflight_warnings(self, rows: list[dict[str, str]], dpi: int) -> list[str]:
        warnings: list[str] = []
        for row_number, row in enumerate(rows, start=1):
            for element_index, element in enumerate(self._drawing_elements(), start=1):
                if not bool(element.get("printable", True)):
                    continue
                element_type = str(element.get("type", "text"))
                width = max(1, mm_to_dots(float(element.get("width", 1)), dpi))
                height = max(1, mm_to_dots(float(element.get("height", 1)), dpi))
                source_width, source_height = _rotation_source_size(width, height, _element_rotation(element))
                if element_type in TEXT_ELEMENT_TYPES:
                    text = render_element_text(element, row)
                    if not text.strip():
                        continue
                    requested = _text_requested_font_size(element, source_height)
                    font = _fit_font_to_box(
                        text, source_width - 4, source_height - 4, requested,
                        str(element.get("font_name") or DEFAULT_FONT_NAME),
                    )
                    if getattr(font, "size", requested) < max(8, int(requested * 0.7)):
                        warnings.append(f"{row_number}행 · {element_index}번 텍스트: 글자가 크게 축소됩니다.")
                elif element_type == "qr" or (element_type == "barcode" and _barcode_type(element) == "qr"):
                    value = sanitize_barcode(_designer_code_value(element, row))
                    options = _barcode_options(element)
                    qr = qrcode.QRCode(
                        version=None,
                        error_correction=QR_ERROR_CORRECTION.get(str(options.get("qr_ecc", "M")).upper(), ERROR_CORRECT_M),
                        box_size=1,
                        border=4,
                    )
                    qr.add_data(value)
                    qr.make(fit=True)
                    module_count = len(qr.get_matrix())
                    if min(source_width, source_height) // module_count < 2:
                        warnings.append(f"{row_number}행 · {element_index}번 QR: 한 칸이 2도트 미만입니다. 크기를 늘리고 실물 스캔을 확인하세요.")
        return warnings

    def run_output_test(
        self,
        send_to_printer: bool,
        *,
        selected_only: bool = False,
        print_quantity: int | None = None,
    ) -> None:
        active_job = self.__dict__.get("_active_background_job")
        if active_job is not None:
            title = str(active_job.get("title", "백그라운드 작업"))
            messagebox.showwarning("작업 진행 중", f"{title} 완료 후 출력 대상을 다시 확인하세요.", parent=self)
            return
        source_rows = self.selected_data_rows(only_selected=selected_only)
        if selected_only and not source_rows:
            messagebox.showwarning("선택 인쇄", "데이터 소스에서 선택한 출력 대상이 없습니다.")
            return
        try:
            for row_number, source_row in enumerate(source_rows, start=1):
                self._validate_output_row(source_row, row_number=row_number)
        except ValueError as exc:
            messagebox.showwarning("인쇄할 내용 확인", str(exc))
            return
        if send_to_printer and print_quantity is None:
            print_quantity = self.ask_print_quantity()
            if print_quantity is None:
                self.status_var.set("인쇄 매수 선택을 취소했습니다.")
                return
        try:
            out_dir = self.base_dir / "out"
            out_dir.mkdir(parents=True, exist_ok=True)
            config_path = out_dir / "designer_test_config.ini"
            barcode_type = self._selected_output_barcode_type()
            if barcode_type is not None and barcode_type not in DESIGNER_PRINT_SUPPORTED_BARCODE_TYPES:
                messagebox.showwarning(
                    "인쇄",
                    f"{BARCODE_TYPES.get(barcode_type, barcode_type)} 타입은 현재 프린터 명령 출력에서 아직 지원하지 않습니다.\n"
                    "실제 인쇄는 Code 128, GS1-128, Code 39, EAN, UPC-A, ITF, Codabar, Pharmacode, QR 계열로 진행해 주세요.",
                )
                return
            self._write_output_test_config(config_path, out_dir, barcode_type)
            config = load_config(config_path)
            dpi = int(getattr(getattr(config, "label", None), "dpi", 203))
            warnings = self._output_preflight_warnings(source_rows, dpi)
            if warnings:
                displayed = warnings[:8]
                remaining = len(warnings) - len(displayed)
                warning_text = "\n".join(f"• {warning}" for warning in displayed)
                if remaining:
                    warning_text += f"\n• 그 외 {remaining}건"
                if not messagebox.askyesno(
                    "출력 전 확인",
                    f"다음 항목을 확인하세요.\n\n{warning_text}\n\n계속하시겠습니까?",
                    parent=self,
                ):
                    self.status_var.set("출력 전 경고를 확인하고 작업을 취소했습니다. 프린터로 전송하지 않았습니다.")
                    return
            prepared_jobs: list[bytes] = []
            prepared_label_counts: list[int] = []
            for source_row in source_rows:
                row_print_qty = print_quantity
                if row_print_qty is None:
                    row_print_qty = max(1, min(100, int(_float_value(str(source_row.get("print_qty", "1")), 1))))
                row = self._output_test_row(row_print_qty, source_row=source_row)
                prepared_jobs.append(self.render_designer_print_command(config, row, row_print_qty))
                prepared_label_counts.append(row_print_qty)
            output_files: list[Path] = []
            for index, command_payload in enumerate(prepared_jobs, start=1):
                output_file = self._write_designer_command_file(config, out_dir, command_payload, index=index)
                output_files.append(output_file)

            progress: PrintProgress | None = None
            if send_to_printer:
                progress_path = out_dir / DESIGNER_PROGRESS_FILE_NAME
                command_encoding = str(getattr(getattr(config, "printer", None), "command_encoding", "utf-8"))
                try:
                    progress = PrintProgress.open_for_job(
                        progress_path,
                        prepared_jobs,
                        command_encoding,
                        _designer_print_job_context(config),
                    )
                except NewPrintJobRequired:
                    progress = PrintProgress.open_for_job(
                        progress_path,
                        prepared_jobs,
                        command_encoding,
                        _designer_print_job_context(config),
                        reset=True,
                    )

                had_unknown_items = bool(progress.unknown_indexes)
                if had_unknown_items and not _resolve_unknown_items_for_explicit_print(progress, self):
                    self.status_var.set("미확인 출력 상태 확인을 취소했습니다. 프린터로 전송하지 않았습니다.")
                    return

                # A completed job must not suppress a later, explicit print request.
                if not had_unknown_items and progress.sent_indexes and not progress.pending_indexes:
                    progress = PrintProgress.open_for_job(
                        progress_path,
                        prepared_jobs,
                        command_encoding,
                        _designer_print_job_context(config),
                        reset=True,
                    )

            sent_count = 0
            sent_label_count = 0
            send_error: Exception | None = None
            if send_to_printer:
                assert progress is not None
                for item_index in list(progress.pending_indexes):
                    command_payload = prepared_jobs[item_index - 1]
                    progress.mark_sending(item_index)
                    try:
                        self._send_designer_print(config, command_payload)
                    except Exception as exc:
                        # A handled transport exception is not a completed send.
                        # Return the item to pending so an explicit second Print
                        # action can retry it. A process crash between
                        # mark_sending() and this handler still remains unknown.
                        progress.resolve_unknown(item_index, was_printed=False)
                        send_error = exc
                        break
                    progress.mark_sent(item_index)
                    sent_count += 1
                    sent_label_count += prepared_label_counts[item_index - 1]
            returncode = 0
            stdout = "designer command written to " + ", ".join(str(path) for path in output_files)
            if send_to_printer:
                stdout += f"\nprint jobs sent: {sent_count}"
            stderr = ""
        except Exception as exc:
            messagebox.showerror("인쇄 오류", str(exc))
            return

        if send_error is not None:
            assert progress is not None
            remaining_count = len(progress.pending_indexes) + len(progress.unknown_indexes)
            stderr = f"printer transport failed after {sent_count} completed job(s): {send_error}"
            log_path = self._write_print_result_log(
                command="designer-direct-print",
                returncode=1,
                stdout=stdout,
                stderr=stderr,
                config_path=config_path,
                out_dir=out_dir,
                send_to_printer=True,
            )
            self.status_var.set(f"프린터 전송 실패 · 전송 {sent_count}건 / 재시도 가능 {remaining_count}건 · 실제 출력 확인 필요")
            messagebox.showerror(
                "인쇄 오류",
                (
                    f"전송 {sent_count}건 / 재시도 가능 {remaining_count}건입니다. 실제 라벨 출력 여부를 확인하세요.\n"
                    "프린터와 연결 상태를 확인한 뒤 인쇄 버튼을 다시 누르세요.\n\n"
                    f"오류: {send_error}\n로그: {log_path}"
                ),
            )
            return

        log_path = self._write_print_result_log(
            command="designer-direct-print",
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            config_path=config_path,
            out_dir=out_dir,
            send_to_printer=send_to_printer,
        )
        config_summary = self._print_config_summary(config_path)
        if returncode != 0:
            messagebox.showerror(
                "인쇄 오류",
                f"{(stderr or stdout or '알 수 없는 오류').strip()}\n\n"
                f"현재 설정: {config_summary}\n"
                f"로그: {log_path}",
            )
            return
        mode_text = "프린터 전송 완료 · 실제 출력 확인 필요" if send_to_printer else "인쇄 파일 생성 완료"
        completed_count = sent_count if send_to_printer else len(output_files)
        if send_to_printer and completed_count == 0:
            mode_text = "이미 전송한 작업 · 이번에는 추가 전송하지 않았습니다"
        self.status_var.set(f"{mode_text} {completed_count}건 / 출력 폴더: {out_dir}")
        if send_to_printer:
            messagebox.showinfo(
                "프린터 전송 완료 · 출력 확인 필요",
                f"{sent_label_count}장의 인쇄 명령을 프린터로 전송했습니다.\n실제 라벨 출력 여부는 프린터에서 확인하세요.",
            )
        else:
            messagebox.showinfo("인쇄 파일 생성", f"인쇄 파일 생성 완료: {len(output_files)}건")

    def ask_print_quantity(self) -> int | None:
        initial = int(_float_value(str(self.preview_row.get("print_qty", "1")), 1))
        initial = max(1, min(100, initial))
        result: dict[str, int | None] = {"value": None}
        dialog = tk.Toplevel(self)
        dialog.title("인쇄 매수 선택")
        set_initial_window_size(
            dialog,
            preferred_width=520,
            preferred_height=460,
            minimum_width=440,
            minimum_height=420,
        )
        dialog.resizable(True, True)
        dialog.configure(bg=COLORS.surface)
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        frame = ttk.Frame(dialog, style="Surface.TFrame", padding=22)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="몇 장씩 인쇄할까요?", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="선택한 각 항목에 같은 수량이 적용됩니다. 1장부터 100장까지 선택할 수 있습니다.",
            style="Hint.TLabel",
            wraplength=470,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 16))

        quantity_card = tk.Frame(
            frame,
            bg=COLORS.surface_subtle,
            highlightbackground=COLORS.border_subtle,
            highlightcolor=COLORS.border,
            highlightthickness=1,
            bd=0,
        )
        quantity_card.grid(row=2, column=0, sticky="ew")
        quantity_card.columnconfigure(1, weight=1)
        tk.Label(
            quantity_card,
            text="인쇄 매수",
            bg=COLORS.surface_subtle,
            fg=COLORS.text_secondary,
            font=TYPOGRAPHY.caption,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 4))

        qty_var = tk.StringVar(value=str(initial))
        qty_entry = ttk.Spinbox(
            quantity_card,
            from_=1,
            to=100,
            textvariable=qty_var,
            justify="center",
            font=(APP_FONT_FAMILY, 24, "bold"),
            width=7,
        )
        qty_entry.grid(row=1, column=1, sticky="ew", ipady=6, pady=(0, 14))

        def adjust(delta: int) -> None:
            value = int(_float_value(qty_var.get(), initial))
            qty_var.set(max(1, min(100, value + delta)))

        ttk.Button(
            quantity_card,
            text="−",
            command=lambda: adjust(-1),
            style="Secondary.TButton",
            width=3,
        ).grid(row=1, column=0, sticky="e", padx=(16, 10), pady=(0, 14))
        ttk.Button(
            quantity_card,
            text="+",
            command=lambda: adjust(1),
            style="Secondary.TButton",
            width=3,
        ).grid(row=1, column=2, sticky="w", padx=(10, 16), pady=(0, 14))

        presets = ttk.Frame(frame, style="Surface.TFrame")
        presets.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(presets, text="빠른 선택", style="Hint.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        for column, value in enumerate((1, 3, 5, 10), start=1):
            ttk.Button(
                presets,
                text=f"{value}장",
                command=lambda selected=value: qty_var.set(str(selected)),
                style="Secondary.TButton",
                width=5,
            ).grid(row=0, column=column, padx=(0, 6), sticky="ew")

        summary_var = tk.StringVar()

        def refresh_summary(*_args: object) -> None:
            value = int(_float_value(qty_var.get(), initial))
            value = max(1, min(100, value))
            summary_var.set(f"각 항목을 {value}장씩 프린터로 전송합니다.")

        qty_var.trace_add("write", refresh_summary)
        refresh_summary()
        ttk.Label(frame, textvariable=summary_var, style="Hint.TLabel").grid(row=4, column=0, sticky="w", pady=(12, 0))

        buttons = ttk.Frame(frame, style="Surface.TFrame")
        buttons.grid(row=5, column=0, sticky="ew", pady=(18, 0))
        buttons.columnconfigure(0, weight=1)

        def confirm() -> None:
            try:
                value = int(qty_var.get())
            except (TypeError, ValueError):
                messagebox.showwarning("인쇄 매수", "인쇄 매수는 1부터 100 사이의 숫자로 입력해 주세요.", parent=dialog)
                return
            if value < 1 or value > 100:
                messagebox.showwarning("인쇄 매수", "인쇄 매수는 1부터 100 사이로 선택해 주세요.", parent=dialog)
                return
            result["value"] = value
            dialog.destroy()

        def cancel() -> None:
            result["value"] = None
            dialog.destroy()

        ttk.Button(buttons, text="취소", command=cancel, style="Secondary.TButton").grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="인쇄 시작", command=confirm, style="Primary.TButton").grid(row=0, column=2)
        dialog.bind("<Return>", lambda _event: confirm())
        dialog.bind("<Escape>", lambda _event: cancel())
        qty_entry.focus_set()
        qty_entry.select_range(0, "end")
        self.wait_window(dialog)
        return result["value"]

    def _output_test_row(self, print_qty: int = 1, *, source_row: dict[str, str] | None = None) -> dict[str, str]:
        source = self.preview_row if source_row is None else source_row
        row = {header: str(source.get(header, "")).strip() for header in LABEL_HEADERS}
        for header, value in source.items():
            row.setdefault(header, str(value).strip())
        row["print_qty"] = str(print_qty)
        return row

    def _selected_output_barcode_type(self) -> str | None:
        selected = self.selected_element()
        if selected is not None and _is_code_element(selected):
            return _barcode_type(selected)
        for element in self.elements:
            if _is_code_element(element):
                return _barcode_type(element)
        return None

    def _write_output_test_config(self, config_path: Path, out_dir: Path, barcode_type: str | None) -> None:
        parser = ConfigParser()
        parser.read_dict(DEFAULTS)
        if self.config_path.exists():
            parser.read(self.config_path, encoding="utf-8-sig")
        for section in ("data", "label", "barcode"):
            if not parser.has_section(section):
                parser.add_section(section)
        label = self.template["label"]  # type: ignore[index]
        parser.set("data", "excel_file", str(out_dir / "designer_direct_queue.xlsx"))
        parser.set("data", "output_dir", str(out_dir))
        parser.set("label", "width_mm", str(label["width_mm"]))  # type: ignore[index]
        parser.set("label", "height_mm", str(label["height_mm"]))  # type: ignore[index]
        if barcode_type is not None and barcode_type in PRINT_SUPPORTED_BARCODE_TYPES:
            parser.set("barcode", "type", barcode_type)
        with config_path.open("w", encoding="utf-8") as config_file:
            parser.write(config_file)

    def render_designer_print_command(self, config: object, row: dict[str, str], print_qty: int) -> bytes:
        language = str(config.printer.language)  # type: ignore[attr-defined]
        if language == "tspl":
            return self._render_tspl_designer_command(config, row, print_qty)
        if language == "slcs":
            return self._render_slcs_designer_command(config, row, print_qty)
        if language == "zpl":
            return self._render_zpl_designer_command(config, row, print_qty)
        raise ValueError("printer.language must be slcs, tspl, or zpl.")

    def _render_slcs_designer_command(self, config: object, row: dict[str, str], print_qty: int) -> bytes:
        label = self.template["label"]  # type: ignore[index]
        width_mm = float(label["width_mm"])  # type: ignore[index]
        height_mm = float(label["height_mm"])  # type: ignore[index]
        dpi = int(config.label.dpi)  # type: ignore[attr-defined]
        width_dot = mm_to_dots(width_mm, dpi)
        height_dot = mm_to_dots(height_mm, dpi)
        gap_dot = mm_to_dots(float(config.label.gap_mm), dpi)  # type: ignore[attr-defined]
        parts: list[bytes] = [
            b"CB\r\n",
            f"SS{config.printer.print_speed}\r\n".encode("ascii"),  # type: ignore[attr-defined]
            f"SD{config.printer.print_density}\r\n".encode("ascii"),  # type: ignore[attr-defined]
            b"CS13,0\r\n",
            self._slcs_print_method_command(config.printer.print_method).replace("\n", "\r\n").encode("ascii"),  # type: ignore[attr-defined]
            self._slcs_media_handling_command(str(getattr(config.printer, "media_handling", "tear_off"))).replace("\n", "\r\n").encode("ascii"),  # type: ignore[attr-defined]
            f"SW{width_dot}\r\n".encode("ascii"),
            self._slcs_media_type_command(
                height_dot,
                gap_dot,
                str(getattr(config.label, "media_type", "gap")),  # type: ignore[attr-defined]
            ).replace("\n", "\r\n").encode("ascii"),
            print_orientation_command(
                "slcs",
                str(getattr(config.printer, "print_orientation", "normal")),  # type: ignore[attr-defined]
            ).replace("\n", "\r\n").encode("ascii"),
        ]
        for element in self._drawing_elements():
            parts.append(self._render_slcs_element(element, row, dpi, width_dot, height_dot, config))
        parts.append(f"P{print_qty}\r\n".encode("ascii"))
        return b"".join(parts)

    def _render_zpl_designer_command(self, config: object, row: dict[str, str], print_qty: int) -> bytes:
        label = self.template["label"]  # type: ignore[index]
        width_mm = float(label["width_mm"])  # type: ignore[index]
        height_mm = float(label["height_mm"])  # type: ignore[index]
        dpi = int(config.label.dpi)  # type: ignore[attr-defined]
        width_dot = mm_to_dots(width_mm, dpi)
        height_dot = mm_to_dots(height_mm, dpi)
        parts = [
            "^XA\n",
            "^CI28\n",
            print_orientation_command(
                "zpl",
                str(getattr(config.printer, "print_orientation", "normal")),  # type: ignore[attr-defined]
            ),
            self._zpl_print_method_command(config.printer.print_method),  # type: ignore[attr-defined]
            self._zpl_media_handling_command(str(getattr(config.printer, "media_handling", "tear_off"))),  # type: ignore[attr-defined]
            self._zpl_media_type_command(str(getattr(config.label, "media_type", "gap"))),  # type: ignore[attr-defined]
            f"^PR{config.printer.print_speed}\n",  # type: ignore[attr-defined]
            f"^MD{config.printer.print_density}\n",  # type: ignore[attr-defined]
            f"^PW{width_dot}\n",
            f"^LL{height_dot}\n",
        ]
        for element in self._drawing_elements():
            parts.append(self._render_zpl_element(element, row, dpi, width_dot, height_dot, config))
        parts.append(f"^PQ{print_qty}\n^XZ\n")
        return "".join(parts).encode(str(config.printer.command_encoding), errors="replace")  # type: ignore[attr-defined]

    def _render_tspl_designer_command(self, config: object, row: dict[str, str], print_qty: int) -> bytes:
        label = self.template["label"]  # type: ignore[index]
        width_mm = float(label["width_mm"])  # type: ignore[index]
        height_mm = float(label["height_mm"])  # type: ignore[index]
        dpi = int(config.label.dpi)  # type: ignore[attr-defined]
        width_dot = mm_to_dots(width_mm, dpi)
        height_dot = mm_to_dots(height_mm, dpi)
        header = (
            f"SIZE {width_mm:g} mm,{height_mm:g} mm\n"
            f"{self._tspl_media_type_command(float(config.label.gap_mm), str(getattr(config.label, 'media_type', 'gap')))}"  # type: ignore[attr-defined]
            f"{self._tspl_codepage_command(config.printer.command_encoding)}"  # type: ignore[attr-defined]
            f"DENSITY {config.printer.print_density}\n"  # type: ignore[attr-defined]
            f"SPEED {config.printer.print_speed}\n"  # type: ignore[attr-defined]
            f"{self._tspl_print_method_command(config.printer.print_method)}"  # type: ignore[attr-defined]
            f"{print_orientation_command('tspl', str(getattr(config.printer, 'print_orientation', 'normal')))}"  # type: ignore[attr-defined]
            "REFERENCE 0,0\n"
            "CLS\n"
        ).encode("ascii")
        commands: list[bytes] = [header]
        for element in self._drawing_elements():
            commands.append(self._render_tspl_element(element, row, dpi, width_dot, height_dot, config))
        commands.append(self._tspl_media_handling_command(str(getattr(config.printer, "media_handling", "tear_off"))).encode("ascii"))  # type: ignore[attr-defined]
        commands.append(f"PRINT 1,{print_qty}\n".encode("ascii"))
        return b"".join(command for command in commands if command)

    def _render_tspl_element(self, element: dict[str, object], row: dict[str, str], dpi: int, width_dot: int, height_dot: int, config: object) -> bytes:
        if not bool(element.get("printable", True)):
            return b""
        x, y, w, h = self._element_dot_box(element, dpi, width_dot, height_dot)
        element_type = str(element.get("type", "text"))
        if element_type == "line":
            thickness = _stroke_width_dots(element, dpi)
            if _line_is_vertical(element):
                line_x = _line_dot_x(x, w, thickness)
                return f"BAR {line_x},{y},{thickness},{max(1, h)}\n".encode("ascii")
            line_y = _line_dot_y(y, h, thickness)
            return f"BAR {x},{line_y},{max(1, w)},{thickness}\n".encode("ascii")
        if _element_rotation(element):
            return self._tspl_bitmap_command(x, y, self._render_element_bitmap(element, row, w, h, transparent=False))
        if element_type in TEXT_ELEMENT_TYPES:
            text = render_element_text(element, row)
            return self._tspl_text_bitmap_command(x, y, w, h, text, element)
        if element_type in {"barcode", "qr"}:
            value = _designer_code_value(element, row)
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            return self._tspl_barcode_command(x, y, w, h, value, code_type, config, element)
        if element_type == "box":
            return f"BOX {x},{y},{x + w},{y + h},{_stroke_width_dots(element, dpi)}\n".encode("ascii")
        if element_type == "table":
            return self._tspl_table_command(x, y, w, h, element, dpi)
        if element_type == "image":
            image = self._load_element_image(element, w, h)
            return self._tspl_bitmap_command(x, y, image) if image is not None else b""
        return b""

    def _render_slcs_element(self, element: dict[str, object], row: dict[str, str], dpi: int, width_dot: int, height_dot: int, config: object) -> bytes:
        if not bool(element.get("printable", True)):
            return b""
        x, y, w, h = self._element_dot_box(element, dpi, width_dot, height_dot)
        element_type = str(element.get("type", "text"))
        if element_type == "line":
            thickness = _stroke_width_dots(element, dpi)
            if _line_is_vertical(element):
                return self._slcs_line_command(_line_dot_x(x, w, thickness), y, w, h, thickness, vertical=True)
            return self._slcs_line_command(x, _line_dot_y(y, h, thickness), w, h, thickness)
        if _element_rotation(element):
            return self._slcs_bitmap_command(x, y, self._render_element_bitmap(element, row, w, h, transparent=False))
        if element_type in TEXT_ELEMENT_TYPES:
            text = render_element_text(element, row)
            if not text:
                return b""
            return self._slcs_text_bitmap_command(x, y, w, h, text, element)
        if element_type in {"barcode", "qr"}:
            value = _designer_code_value(element, row)
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            return self._slcs_barcode_command(x, y, w, h, value, code_type, config, element)
        if element_type == "box":
            return self._slcs_box_command(x, y, w, h, _stroke_width_dots(element, dpi))
        if element_type == "table":
            return self._slcs_table_command(x, y, w, h, element, dpi)
        if element_type == "image":
            image = self._load_element_image(element, w, h)
            return self._slcs_bitmap_command(x, y, image) if image is not None else b""
        return b""

    def _render_zpl_element(self, element: dict[str, object], row: dict[str, str], dpi: int, width_dot: int, height_dot: int, config: object) -> str:
        if not bool(element.get("printable", True)):
            return ""
        x, y, w, h = self._element_dot_box(element, dpi, width_dot, height_dot)
        element_type = str(element.get("type", "text"))
        if element_type == "line":
            thickness = _stroke_width_dots(element, dpi)
            if _line_is_vertical(element):
                return f"^FO{_line_dot_x(x, w, thickness)},{y}^GB{thickness},{max(1, h)},{thickness}^FS\n"
            return f"^FO{x},{_line_dot_y(y, h, thickness)}^GB{max(1, w)},{thickness},{thickness}^FS\n"
        if _element_rotation(element):
            return self._zpl_bitmap_command(x, y, self._render_element_bitmap(element, row, w, h, transparent=False))
        if element_type in TEXT_ELEMENT_TYPES:
            raw_text = render_element_text(element, row)
            if not raw_text:
                return ""
            image = _render_text_box_image(raw_text, max(1, w), max(1, h), element, transparent=False)
            return self._zpl_bitmap_command(x, y, image)
        if element_type in {"barcode", "qr"}:
            value = _designer_code_value(element, row)
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            return self._zpl_barcode_command(x, y, w, h, value, code_type, config, element)
        if element_type == "box":
            return f"^FO{x},{y}^GB{w},{h},{_stroke_width_dots(element, dpi)}^FS\n"
        if element_type == "table":
            return self._zpl_table_command(x, y, w, h, element, dpi)
        if element_type == "image":
            image = self._load_element_image(element, w, h)
            return self._zpl_bitmap_command(x, y, image) if image is not None else ""
        return ""

    def _element_dot_box(self, element: dict[str, object], dpi: int, width_dot: int, height_dot: int) -> tuple[int, int, int, int]:
        x = mm_to_dots(float(element.get("x", 0)), dpi)
        y = mm_to_dots(float(element.get("y", 0)), dpi)
        w = max(1, mm_to_dots(float(element.get("width", 1)), dpi))
        h = max(1, mm_to_dots(float(element.get("height", 1)), dpi))
        x = max(0, min(width_dot - 1, x))
        y = max(0, min(height_dot - 1, y))
        w = max(1, min(width_dot - x, w))
        h = max(1, min(height_dot - y, h))
        return x, y, w, h

    def _tspl_text_bitmap_command(self, x: int, y: int, width: int, height: int, text: str, element: dict[str, object]) -> bytes:
        if not text:
            return b""
        image = _render_text_box_image(text, max(1, width), max(1, height), element, transparent=False)
        return self._tspl_bitmap_command(x, y, image)

    def _tspl_barcode_command(self, x: int, y: int, width: int, height: int, value: str, code_type: str, config: object, element: dict[str, object] | None = None) -> bytes:
        if element is not None and code_type in BARCODE_1D_BITMAP_TYPES:
            image = _render_1d_barcode_image(code_type, value, width, height, element)
            return self._tspl_bitmap_command(x, y, image)
        if element is not None and code_type in BARCODE_2D_BITMAP_TYPES:
            image = _render_2d_barcode_image(code_type, value, width, height, element)
            return self._tspl_bitmap_command(x, y, image)
        clean_value = sanitize_barcode(value)
        rotation = 0
        if code_type in {"code128", "code39", "ean13", "ean8", "upca", "itf"}:
            symbology = {
                "code128": "128",
                "code39": "39",
                "ean13": "EAN13",
                "ean8": "EAN8",
                "upca": "UPCA",
                "itf": "ITF",
            }[code_type]
            hri = 1 if height >= 36 else 0
            bar_height = max(12, height - (18 if hri else 2))
            modules = self._barcode_module_count(code_type, clean_value)
            narrow = max(1, min(4, width // max(1, modules)))
            wide = max(narrow + 1, narrow * 2)
            return f'BARCODE {x},{y},"{symbology}",{bar_height},{hri},{rotation},{narrow},{wide},"{clean_value}"\n'.encode("ascii")
        if code_type == "qr":
            cell = _barcode_option_int(element, "cell_size", int(config.barcode.qr_cell_size), 1, 20)  # type: ignore[attr-defined]
            cell = min(cell, max(1, min(width, height) // 21))
            size = cell * 29
            qx = x + max(0, (width - size) // 2)
            ecc = str((_barcode_options(element or {}).get("qr_ecc") if element is not None else config.barcode.qr_ecc) or config.barcode.qr_ecc).upper()  # type: ignore[attr-defined]
            if ecc not in {"L", "M", "Q", "H"}:
                ecc = str(config.barcode.qr_ecc)  # type: ignore[attr-defined]
            return f'QRCODE {qx},{y},{ecc},{cell},A,{rotation},M{config.barcode.qr_model},S7,"{clean_value}"\n'.encode("ascii")  # type: ignore[attr-defined]
        if code_type == "datamatrix":
            cell = _barcode_option_int(element, "cell_size", int(config.barcode.datamatrix_cell_size), 1, 20)  # type: ignore[attr-defined]
            cell = min(cell, max(1, min(width, height) // 16))
            size = max(24, cell * 24)
            qx = x + max(0, (width - size) // 2)
            return f'DMATRIX {qx},{y},{size},{size},{cell},{cell},"{clean_value}"\n'.encode("ascii")
        if code_type == "pdf417":
            columns = _barcode_option_int(element, "pdf417_columns", int(config.barcode.pdf417_columns), 2, 30)  # type: ignore[attr-defined]
            rows = _barcode_option_int(element, "pdf417_rows", int(config.barcode.pdf417_rows), 3, 90)  # type: ignore[attr-defined]
            security = _barcode_option_int(element, "pdf417_security", int(config.barcode.pdf417_security_level), 0, 8)  # type: ignore[attr-defined]
            module_width = max(1, min(6, width // max(1, columns * 17)))
            module_height = max(2, min(20, height // max(1, rows)))
            return (
                f"PDF417 {x},{y},{module_width},{module_height},{columns},{rows},"
                f'{security},{rotation},"{clean_value}"\n'
            ).encode("ascii")
        raise ValueError(f"{BARCODE_TYPES.get(code_type, code_type)} 타입은 현재 인쇄 명령에서 지원하지 않습니다.")

    def _slcs_barcode_command(self, x: int, y: int, width: int, height: int, value: str, code_type: str, config: object, element: dict[str, object] | None = None) -> bytes:
        if element is not None and code_type in BARCODE_1D_BITMAP_TYPES:
            image = _render_1d_barcode_image(code_type, value, width, height, element)
            return self._slcs_bitmap_command(x, y, image)
        if element is not None and code_type in BARCODE_2D_BITMAP_TYPES:
            image = _render_2d_barcode_image(code_type, value, width, height, element)
            return self._slcs_bitmap_command(x, y, image)
        clean_value = sanitize_barcode(value)
        if code_type in {"code128", "code39", "ean13", "ean8", "upca", "itf"}:
            symbology = {
                "code39": 0,
                "code128": 1,
                "itf": 2,
                "ean13": 3,
                "ean8": 4,
                "upca": 5,
            }[code_type]
            hri = 1 if height >= 36 else 0
            bar_height = max(12, height - (18 if hri else 2))
            modules = self._barcode_module_count(code_type, clean_value)
            narrow = max(1, min(6, round(width / max(1, modules))))
            while modules * narrow > width and narrow > 1:
                narrow -= 1
            wide = max(narrow + 1, narrow * 2)
            estimated_width = modules * narrow
            bx = x + max(0, (width - estimated_width) // 2)
            return f"B1{bx},{y},{symbology},{narrow},{wide},{bar_height},0,{hri},'{clean_value}'\r\n".encode("ascii")
        if code_type == "qr":
            cell = _barcode_option_int(element, "cell_size", int(config.barcode.qr_cell_size), 1, 20)  # type: ignore[attr-defined]
            cell = min(cell, max(1, min(width, height) // 21))
            size = cell * 29
            qx = x + max(0, (width - size) // 2)
            ecc = str((_barcode_options(element or {}).get("qr_ecc") if element is not None else config.barcode.qr_ecc) or config.barcode.qr_ecc).upper()  # type: ignore[attr-defined]
            if ecc not in {"L", "M", "Q", "H"}:
                ecc = str(config.barcode.qr_ecc)  # type: ignore[attr-defined]
            return f"B2{qx},{y},Q,{config.barcode.qr_model},{ecc},{cell},0,'{clean_value}'\r\n".encode("ascii")  # type: ignore[attr-defined]
        if code_type == "datamatrix":
            cell = _barcode_option_int(element, "cell_size", int(config.barcode.datamatrix_cell_size), 1, 20)  # type: ignore[attr-defined]
            cell = min(cell, max(1, min(width, height) // 16))
            size = max(24, cell * 24)
            qx = x + max(0, (width - size) // 2)
            return f"B2{qx},{y},D,{cell},N,0,'{clean_value}'\r\n".encode("ascii")
        if code_type == "pdf417":
            columns = _barcode_option_int(element, "pdf417_columns", int(config.barcode.pdf417_columns), 2, 30)  # type: ignore[attr-defined]
            rows = _barcode_option_int(element, "pdf417_rows", int(config.barcode.pdf417_rows), 3, 90)  # type: ignore[attr-defined]
            security = _barcode_option_int(element, "pdf417_security", int(config.barcode.pdf417_security_level), 0, 8)  # type: ignore[attr-defined]
            module_width = max(1, min(6, width // max(1, columns * 17)))
            module_height = max(2, min(20, height // max(1, rows)))
            hri = 1 if height >= 36 else 0
            return (
                f"B2{x},{y},P,{rows},{columns},{security},"
                f"0,{hri},1,{module_width},{module_height},0,'{clean_value}'\r\n"
            ).encode("ascii")
        raise ValueError(f"{BARCODE_TYPES.get(code_type, code_type)} 타입은 현재 인쇄 명령에서 지원하지 않습니다.")

    def _zpl_barcode_command(self, x: int, y: int, width: int, height: int, value: str, code_type: str, config: object, element: dict[str, object] | None = None) -> str:
        if element is not None and code_type in BARCODE_1D_BITMAP_TYPES:
            image = _render_1d_barcode_image(code_type, value, width, height, element)
            return self._zpl_bitmap_command(x, y, image)
        if element is not None and code_type in BARCODE_2D_BITMAP_TYPES:
            image = _render_2d_barcode_image(code_type, value, width, height, element)
            return self._zpl_bitmap_command(x, y, image)
        clean_value = self._zpl_escape(sanitize_barcode(value))
        if code_type == "code128":
            return f"^FO{x},{y}^BY{self._zpl_narrow(width, clean_value)},2,{height}^BCN,{height},Y,N,N^FD{clean_value}^FS\n"
        if code_type == "code39":
            return f"^FO{x},{y}^BY{self._zpl_narrow(width, clean_value)},2,{height}^B3N,N,{height},Y,N^FD{clean_value}^FS\n"
        if code_type == "ean13":
            return f"^FO{x},{y}^BEN,{height},Y,N^FD{clean_value}^FS\n"
        if code_type == "ean8":
            return f"^FO{x},{y}^B8N,{height},Y,N^FD{clean_value}^FS\n"
        if code_type == "upca":
            return f"^FO{x},{y}^BUN,{height},Y,N^FD{clean_value}^FS\n"
        if code_type == "itf":
            return f"^FO{x},{y}^BY{self._zpl_narrow(width, clean_value)},2,{height}^B2N,{height},Y,N,N^FD{clean_value}^FS\n"
        if code_type == "qr":
            cell = _barcode_option_int(element, "cell_size", int(config.barcode.qr_cell_size), 1, 20)  # type: ignore[attr-defined]
            cell = min(cell, max(1, min(width, height) // 21))
            return f"^FO{x},{y}^BQN,2,{cell}^FDLA,{clean_value}^FS\n"
        if code_type == "datamatrix":
            cell = _barcode_option_int(element, "cell_size", int(config.barcode.datamatrix_cell_size), 1, 20)  # type: ignore[attr-defined]
            cell = min(cell, max(1, min(width, height) // 16))
            return f"^FO{x},{y}^BXN,{cell},200^FD{clean_value}^FS\n"
        if code_type == "pdf417":
            columns = _barcode_option_int(element, "pdf417_columns", int(config.barcode.pdf417_columns), 2, 30)  # type: ignore[attr-defined]
            rows = _barcode_option_int(element, "pdf417_rows", int(config.barcode.pdf417_rows), 3, 90)  # type: ignore[attr-defined]
            security = _barcode_option_int(element, "pdf417_security", int(config.barcode.pdf417_security_level), 0, 8)  # type: ignore[attr-defined]
            module_height = max(2, min(20, height // max(1, rows)))
            return (
                f"^FO{x},{y}^B7N,{module_height},{security},"
                f"{columns},{rows},N^FD{clean_value}^FS\n"
            )
        raise ValueError(f"{BARCODE_TYPES.get(code_type, code_type)} 타입은 현재 인쇄 명령에서 지원하지 않습니다.")

    def _barcode_module_count(self, barcode_type: str, barcode: str) -> int:
        length = max(1, len(barcode))
        if barcode_type == "code128":
            return max(68, ((length + 3) * 11) + 13)
        if barcode_type == "code39":
            return max(70, (length * 13) + 35)
        if barcode_type in {"ean13", "upca"}:
            return 113
        if barcode_type == "ean8":
            return 81
        if barcode_type == "itf":
            return max(70, (length * 9) + 45)
        return max(70, length * 11)

    def _tspl_bitmap_command(self, x: int, y: int, image: Image.Image) -> bytes:
        image = image.convert("1")
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

    def _slcs_text_bitmap_command(self, x: int, y: int, width: int, height: int, text: str, element: dict[str, object]) -> bytes:
        if not text:
            return b""
        image = _render_text_box_image(text, max(1, width), max(1, height), element, transparent=False)
        return self._slcs_bitmap_command(x, y, image)

    def _slcs_code128_bitmap_command(self, x: int, y: int, width: int, height: int, barcode: str, element: dict[str, object]) -> bytes:
        if not barcode:
            return b""
        image = Image.new("1", (max(1, width), max(1, height)), 1)
        draw = ImageDraw.Draw(image)
        padding = max(2, min(8, round(min(width, height) * 0.04)))
        hri_height = 0
        hri_font = _load_font(max(8, min(22, round(height * 0.16))), str(element.get("font_name") or "Consolas"))
        if height >= 36:
            bbox = draw.textbbox((0, 0), barcode, font=hri_font)
            hri_height = min(max(14, bbox[3] - bbox[1] + 6), max(14, height // 3))
        bar_width = max(1, width - (padding * 2))
        bar_height = max(8, height - (padding * 2) - hri_height)
        barcode_image = _render_code128_image(barcode, bar_width, bar_height)
        image.paste(barcode_image, (padding, padding))
        if hri_height:
            bbox = draw.textbbox((0, 0), barcode, font=hri_font)
            text_w = bbox[2] - bbox[0]
            text_x = max(0, (width - text_w) // 2)
            text_y = max(padding + bar_height + 2, height - hri_height + 1)
            draw.text((text_x - bbox[0], text_y - bbox[1]), barcode, fill=0, font=hri_font)
        return self._slcs_bitmap_command(x, y, image)

    def _slcs_bitmap_command(self, x: int, y: int, image: Image.Image) -> bytes:
        output = io.BytesIO()
        image.convert("1").save(output, format="BMP")
        return f"BMP{x},{y}\r\n".encode("ascii") + output.getvalue() + b"\r\n"

    def _zpl_bitmap_command(self, x: int, y: int, image: Image.Image) -> str:
        mono = image.convert("1")
        width, height = mono.size
        width_bytes = (width + 7) // 8
        pixels = mono.load()
        payload = bytearray()
        for row in range(height):
            for byte_index in range(width_bytes):
                value = 0
                for bit in range(8):
                    col = (byte_index * 8) + bit
                    if col < width and pixels[col, row] == 0:
                        value |= 0x80 >> bit
                payload.append(value)
        total = len(payload)
        return f"^FO{x},{y}^GFA,{total},{total},{width_bytes},{payload.hex().upper()}^FS\n"

    def _tspl_codepage_command(self, command_encoding: str) -> str:
        normalized = command_encoding.strip().replace("_", "-").lower()
        if normalized in {"cp949", "ms949", "949", "ks-c-5601", "ks-c-5601-1987", "euc-kr"}:
            return "CODEPAGE 949\n"
        return "CODEPAGE UTF-8\n"

    def _tspl_print_method_command(self, print_method: str) -> str:
        if print_method == "thermal_transfer":
            return "SET RIBBON ON\n"
        return "SET RIBBON OFF\n"

    def _tspl_media_handling_command(self, media_handling: str) -> str:
        _ensure_media_handling_supported("tspl", media_handling)
        if media_handling == "cutter":
            return "SET PEEL OFF\nSET CUTTER 1\n"
        if media_handling == "peeler":
            return "SET CUTTER OFF\nSET PEEL ON\n"
        return "SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n"

    def _tspl_media_type_command(self, gap_mm: float, media_type: str) -> str:
        if media_type == "gap":
            return f"GAP {gap_mm:g} mm,0 mm\n"
        if media_type == "black_mark":
            return f"BLINE {gap_mm:g} mm,0 mm\n"
        if media_type == "continuous":
            return "GAP 0,0\n"
        raise ValueError("media_type must be 'gap', 'black_mark', or 'continuous'.")

    def _slcs_print_method_command(self, print_method: str) -> str:
        if print_method == "thermal_transfer":
            return "STt\n"
        return "STd\n"

    def _slcs_media_handling_command(self, media_handling: str) -> str:
        _ensure_media_handling_supported("slcs", media_handling)
        if media_handling == "cutter":
            return "CUTy\n"
        return "CUTn\n"

    def _slcs_media_type_command(self, height_dot: int, gap_dot: int, media_type: str) -> str:
        if media_type == "gap":
            return f"SL{height_dot},{gap_dot},G\n"
        if media_type == "black_mark":
            return f"SL{height_dot},{gap_dot},B\n"
        if media_type == "continuous":
            return f"SL{height_dot},0,C\n"
        raise ValueError("media_type must be 'gap', 'black_mark', or 'continuous'.")

    def _zpl_print_method_command(self, print_method: str) -> str:
        if print_method == "thermal_transfer":
            return "^MTT\n"
        return "^MTD\n"

    def _zpl_media_handling_command(self, media_handling: str) -> str:
        _ensure_media_handling_supported("zpl", media_handling)
        if media_handling == "cutter":
            return "^MMC\n"
        if media_handling == "peeler":
            return "^MMP\n"
        return "^MMT\n"

    def _zpl_media_type_command(self, media_type: str) -> str:
        if media_type == "gap":
            return "^MNY\n"
        if media_type == "black_mark":
            return "^MNM,0\n"
        if media_type == "continuous":
            return "^MNN\n"
        raise ValueError("media_type must be 'gap', 'black_mark', or 'continuous'.")

    def _slcs_font_for_height(self, height: int) -> str:
        if height >= 64:
            return "6"
        if height >= 50:
            return "5"
        if height >= 38:
            return "4"
        if height >= 30:
            return "3"
        if height >= 25:
            return "2"
        if height >= 20:
            return "1"
        return "0"

    def _slcs_box_command(self, x: int, y: int, width: int, height: int, thickness: int = 2) -> bytes:
        thickness = max(1, int(thickness))
        return f"BD{x},{y},{x + width},{y + height},B,{thickness}\r\n".encode("ascii")

    def _slcs_line_command(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        thickness: int = 2,
        *,
        vertical: bool = False,
    ) -> bytes:
        thickness = max(1, int(thickness))
        if vertical:
            return f"BD{x},{y},{x + thickness - 1},{y + max(1, height) - 1},O\r\n".encode("ascii")
        return f"BD{x},{y},{x + max(1, width) - 1},{y + thickness - 1},O\r\n".encode("ascii")

    def _tspl_table_command(self, x: int, y: int, width: int, height: int, element: dict[str, object], dpi: int) -> bytes:
        thickness = _stroke_width_dots(element, dpi)
        parts = [f"BOX {x},{y},{x + width},{y + height},{thickness}\n"]
        for ratio in _table_axis_positions(element, "col"):
            line_x = x + round(width * ratio)
            parts.append(f"BAR {line_x},{y},{thickness},{height}\n")
        for ratio in _table_axis_positions(element, "row"):
            line_y = y + round(height * ratio)
            parts.append(f"BAR {x},{line_y},{width},{thickness}\n")
        return "".join(parts).encode("ascii")

    def _slcs_table_command(self, x: int, y: int, width: int, height: int, element: dict[str, object], dpi: int) -> bytes:
        thickness = _stroke_width_dots(element, dpi)
        parts = [self._slcs_box_command(x, y, width, height, thickness)]
        for ratio in _table_axis_positions(element, "col"):
            line_x = x + round(width * ratio)
            parts.append(self._slcs_line_command(line_x, y, thickness, height, thickness, vertical=True))
        for ratio in _table_axis_positions(element, "row"):
            line_y = y + round(height * ratio)
            parts.append(self._slcs_line_command(x, line_y, width, thickness, thickness))
        return b"".join(parts)

    def _zpl_table_command(self, x: int, y: int, width: int, height: int, element: dict[str, object], dpi: int) -> str:
        thickness = _stroke_width_dots(element, dpi)
        parts = [f"^FO{x},{y}^GB{width},{height},{thickness}^FS\n"]
        for ratio in _table_axis_positions(element, "col"):
            line_x = x + round(width * ratio)
            parts.append(f"^FO{line_x},{y}^GB{thickness},{height},{thickness}^FS\n")
        for ratio in _table_axis_positions(element, "row"):
            line_y = y + round(height * ratio)
            parts.append(f"^FO{x},{line_y}^GB{width},{thickness},{thickness}^FS\n")
        return "".join(parts)

    def _zpl_narrow(self, width: int, barcode: str) -> int:
        modules = max(68, ((max(1, len(barcode)) + 3) * 11) + 13)
        return max(1, min(4, width // modules))

    def _zpl_escape(self, text: str) -> str:
        return text.replace("^", " ").replace("~", " ")

    def _write_designer_command_file(self, config: object, out_dir: Path, command_payload: bytes, *, index: int = 1) -> Path:
        extension = str(config.printer.language)  # type: ignore[attr-defined]
        output_file = out_dir / f"designer_label_{index:03d}.{extension}"
        output_file.write_bytes(command_payload)
        return output_file

    def _send_designer_print(self, config: object, command_payload: bytes) -> None:
        if config.printer.mode == "network":  # type: ignore[attr-defined]
            send_network_raw(config.printer.ip, config.printer.port, command_payload, config.printer.command_encoding)  # type: ignore[attr-defined]
            return
        if config.printer.mode == "windows_raw":  # type: ignore[attr-defined]
            send_windows_raw(config.printer.windows_printer_name, command_payload, config.printer.command_encoding)  # type: ignore[attr-defined]
            return
        raise ValueError("printer.mode must be 'network' or 'windows_raw'")

    def _print_config_summary(self, config_path: Path) -> str:
        try:
            config = load_config(config_path)
        except Exception as exc:
            return f"설정 읽기 실패: {exc}"
        if config.printer.mode == "network":
            target = f"{config.printer.ip}:{config.printer.port}"
        else:
            target = config.printer.windows_printer_name
        return f"{config.printer.brand.upper()} / {config.printer.language.upper()} / {config.printer.mode} / {target}"

    def _write_print_result_log(
        self,
        command: str,
        returncode: int,
        stdout: str,
        stderr: str,
        config_path: Path,
        out_dir: Path,
        send_to_printer: bool,
    ) -> Path:
        log_path = out_dir / "designer_print_last.log"
        lines = [
            f"mode={'print' if send_to_printer else 'dry-run'}",
            f"config={config_path}",
            f"command={command}",
            f"returncode={returncode}",
            "stdout:",
            stdout.strip(),
            "stderr:",
            stderr.strip(),
        ]
        log_path.write_text("\n".join(lines), encoding="utf-8")
        return log_path

    def render_preview_image(self) -> Image.Image:
        label = self.template["label"]  # type: ignore[index]
        width = int(float(label["width_mm"]) * 8)  # type: ignore[index]
        height = int(float(label["height_mm"]) * 8)  # type: ignore[index]
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        for element in self._drawing_elements():
            self._draw_element_to_image(image, draw, element, 8)
        return image

    def _draw_element_to_image(self, image: Image.Image, draw: ImageDraw.ImageDraw, element: dict[str, object], scale: float) -> None:
        if not bool(element.get("printable", True)):
            return
        x1 = float(element.get("x", 0)) * scale
        y1 = float(element.get("y", 0)) * scale
        x2 = x1 + float(element.get("width", 1)) * scale
        y2 = y1 + float(element.get("height", 1)) * scale
        element_type = str(element.get("type", "text"))
        if element_type == "line":
            stroke_width = _stroke_width_px(element, scale)
            if _line_is_vertical(element):
                line_x = _line_center_x(x1, x2)
                draw.line((line_x, y1, line_x, y2), fill="#111820", width=stroke_width)
            else:
                line_y = _line_center_y(y1, y2)
                draw.line((x1, line_y, x2, line_y), fill="#111820", width=stroke_width)
        elif _element_rotation(element):
            try:
                rotated_image = self._render_element_bitmap(
                    element,
                    self.preview_row,
                    max(1, round(x2 - x1)),
                    max(1, round(y2 - y1)),
                    transparent=False,
                )
            except ValueError as exc:
                draw.text((x1 + 4, y1 + 4), str(exc), fill="#b42318", font=_load_font(10))
                return
            image.paste(rotated_image.convert("RGB"), (round(x1), round(y1)))
            return
        if element_type in TEXT_ELEMENT_TYPES:
            text = render_element_text(element, self.preview_row)
            text_image = _render_text_box_image(text, max(1, round(x2 - x1)), max(1, round(y2 - y1)), element, transparent=False).convert("L")
            text_mask = ImageChops.invert(text_image).convert("1")
            draw.bitmap((x1, y1), text_mask, fill="#111820")
        elif element_type in {"barcode", "qr"}:
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            value = _preview_code_value(render_template_text(str(element.get("text", "{{barcode}}")), self.preview_row))
            if code_type in BARCODE_2D_TYPES:
                if code_type in BARCODE_2D_BITMAP_TYPES:
                    try:
                        barcode_image = _render_2d_barcode_image(code_type, value, max(1, round(x2 - x1)), max(1, round(y2 - y1)), element)
                        barcode_rgba = _barcode_image_to_transparent_rgba(barcode_image)
                        image.paste(barcode_rgba.convert("RGB"), (round(x1), round(y1)), barcode_rgba.getchannel("A"))
                    except ValueError as exc:
                        draw.text((x1 + 4, y1 + 4), str(exc), fill="#b42318", font=_load_font(10))
                else:
                    draw.text((x1 + 4, y1 + 4), f"{BARCODE_TYPES.get(code_type, code_type)} 준비 중", fill="#8a4b00", font=_load_font(10))
            elif code_type in BARCODE_1D_BITMAP_TYPES:
                try:
                    barcode_image = _render_1d_barcode_image(code_type, value, max(1, round(x2 - x1)), max(1, round(y2 - y1)), element)
                    barcode_rgba = _barcode_image_to_transparent_rgba(barcode_image)
                    image.paste(barcode_rgba.convert("RGB"), (round(x1), round(y1)), barcode_rgba.getchannel("A"))
                except ValueError as exc:
                    draw.text((x1 + 4, y1 + 4), str(exc), fill="#b42318", font=_load_font(10))
            else:
                draw.text((x1 + 4, y1 + 4), f"{BARCODE_TYPES.get(code_type, code_type)} 준비 중", fill="#8a4b00", font=_load_font(10))
        elif element_type == "box":
            draw.rectangle((x1, y1, x2, y2), outline="#111820", width=_stroke_width_px(element, scale))
        elif element_type == "table":
            stroke_width = _stroke_width_px(element, scale)
            draw.rectangle((x1, y1, x2, y2), outline="#111820", width=stroke_width)
            for ratio in _table_axis_positions(element, "col"):
                x = x1 + ((x2 - x1) * ratio)
                draw.line((x, y1, x, y2), fill="#111820", width=stroke_width)
            for ratio in _table_axis_positions(element, "row"):
                y = y1 + ((y2 - y1) * ratio)
                draw.line((x1, y, x2, y), fill="#111820", width=stroke_width)
        elif element_type == "image":
            loaded = self._load_element_image(element, max(1, round(x2 - x1)), max(1, round(y2 - y1)))
            if loaded is not None:
                image.paste(loaded.convert("RGB"), (round(x1), round(y1)), loaded.getchannel("A"))
            else:
                draw.rectangle((x1, y1, x2, y2), outline="#8a94a6", width=1)
                draw.text((x1 + 4, y1 + 4), "그림 없음", fill="#657085", font=_load_font(10))

    def _draw_2d_code_to_image(self, draw: ImageDraw.ImageDraw, x1: float, y1: float, x2: float, y2: float, value: str, code_type: str) -> None:
        if x2 <= x1 or y2 <= y1:
            return
        if code_type in {"pdf417", "micropdf417"}:
            seed = sum(ord(char) for char in value) or 1
            rows = 5
            row_height = max(2, (y2 - y1) / rows)
            for row in range(rows):
                cursor = x1
                index = 0
                while cursor < x2:
                    bar_width = 1 + ((seed + row + index) % 5)
                    gap = 1 + ((seed // (index + 1) + row) % 2)
                    if (index + row) % 2 == 0:
                        draw.rectangle((cursor, y1 + row * row_height, min(cursor + bar_width, x2), y1 + (row + 0.75) * row_height), fill="#111820")
                    cursor += bar_width + gap
                    index += 1
            return
        size = min(x2 - x1, y2 - y1)
        x1 += ((x2 - x1) - size) / 2
        y1 += ((y2 - y1) - size) / 2
        cells = 10 if code_type == "datamatrix" else 9
        cell = size / cells
        seed = sum(ord(char) for char in value + code_type) or 1
        for row in range(cells):
            for column in range(cells):
                finder = code_type == "qr" and ((row < 3 and column < 3) or (row < 3 and column > cells - 4) or (row > cells - 4 and column < 3))
                data_cell = ((row * 7 + column * 5 + row * column + seed) % 3) == 0
                border_cell = code_type == "datamatrix" and (row == 0 or column == 0 or row == cells - 1 or column == cells - 1)
                if finder or data_cell or border_cell:
                    draw.rectangle((x1 + column * cell, y1 + row * cell, x1 + (column + 1) * cell, y1 + (row + 1) * cell), fill="#111820")

    def _draw_code128_to_image(self, draw: ImageDraw.ImageDraw, x1: float, y1: float, x2: float, y2: float, value: str) -> None:
        if x2 <= x1 or y2 <= y1:
            return
        try:
            modules = _code128_module_widths(sanitize_barcode(value))
        except ValueError:
            return
        total_modules = sum(modules) + 20
        scale = max(0.1, (x2 - x1) / max(1, total_modules))
        cursor = x1 + (10 * scale)
        black = True
        for module_width in modules:
            bar_width = module_width * scale
            if black:
                draw.rectangle((cursor, y1, cursor + bar_width, y2), fill="#111820")
            cursor += bar_width
            black = not black

    def open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(path)])

    def open_printer_settings(self) -> None:
        try:
            command = _printer_settings_command(self.base_dir, self.install_dir)
            popen_kwargs: dict[str, object] = {"cwd": str(self.install_dir)}
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(command, **popen_kwargs)
        except Exception as exc:
            messagebox.showerror("프린터 설정", f"프린터 설정을 열지 못했습니다.\n{exc}")
            self.status_var.set("프린터 설정 실행 실패")
            return
        self.status_var.set("프린터 설정을 열었습니다.")


def _empty_row() -> dict[str, str]:
    return {field: "" for field in DB_HEADERS}


def _table_shape(element: dict[str, object]) -> tuple[int, int]:
    rows = max(1, min(20, int(_float_value(element.get("table_rows"), 3))))
    cols = max(1, min(20, int(_float_value(element.get("table_cols"), 3))))
    return rows, cols


def _even_table_positions(segments: int) -> list[float]:
    segments = max(1, int(segments))
    return [round(index / segments, 4) for index in range(1, segments)]


def _normalize_table_axis_positions(value: object, segments: int) -> list[float]:
    expected = max(0, int(segments) - 1)
    if expected <= 0:
        return []
    if not isinstance(value, (list, tuple)):
        return _even_table_positions(segments)
    positions: list[float] = []
    for item in value:
        try:
            position = float(item)
        except (TypeError, ValueError):
            continue
        if 0.0 < position < 1.0:
            positions.append(position)
    positions = sorted(positions)
    if len(positions) != expected:
        return _even_table_positions(segments)
    minimum_gap = min(0.45, max(0.01, 1.0 / max(segments * 20, 1)))
    normalized: list[float] = []
    for index, position in enumerate(positions):
        lower = minimum_gap if index == 0 else normalized[index - 1] + minimum_gap
        upper = 1.0 - minimum_gap * (expected - index)
        if lower > upper:
            return _even_table_positions(segments)
        normalized.append(round(max(lower, min(upper, position)), 4))
    return normalized


def _table_axis_positions(element: dict[str, object], axis: str) -> list[float]:
    rows, cols = _table_shape(element)
    if axis == "row":
        return _normalize_table_axis_positions(element.get("table_row_positions"), rows)
    return _normalize_table_axis_positions(element.get("table_col_positions"), cols)


def _apply_table_shape(element: dict[str, object], rows: int, cols: int) -> None:
    old_rows, old_cols = _table_shape(element)
    rows = max(1, min(20, int(rows)))
    cols = max(1, min(20, int(cols)))
    element["table_rows"] = rows
    element["table_cols"] = cols
    if old_rows != rows or len(_table_axis_positions(element, "row")) != max(0, rows - 1):
        element["table_row_positions"] = _even_table_positions(rows)
    else:
        element["table_row_positions"] = _table_axis_positions(element, "row")
    if old_cols != cols or len(_table_axis_positions(element, "col")) != max(0, cols - 1):
        element["table_col_positions"] = _even_table_positions(cols)
    else:
        element["table_col_positions"] = _table_axis_positions(element, "col")


def _set_table_axis_position(element: dict[str, object], axis: str, index: int, ratio: float) -> None:
    rows, cols = _table_shape(element)
    segments = rows if axis == "row" else cols
    positions = _table_axis_positions(element, axis)
    if index < 0 or index >= len(positions):
        return
    size_mm = float(element.get("height" if axis == "row" else "width", 1))
    minimum_gap = min(0.45, max(0.02, TABLE_MIN_CELL_MM / max(size_mm, 1.0)))
    lower = minimum_gap if index == 0 else positions[index - 1] + minimum_gap
    upper = 1.0 - minimum_gap if index == len(positions) - 1 else positions[index + 1] - minimum_gap
    if lower > upper:
        return
    positions[index] = round(max(lower, min(upper, ratio)), 4)
    key = "table_row_positions" if axis == "row" else "table_col_positions"
    element[key] = positions


def _normalize_stroke_width(value: object, fallback: float = DEFAULT_STROKE_WIDTH_MM) -> float:
    width = _float_value(value, fallback)
    return round(max(MIN_STROKE_WIDTH_MM, min(MAX_STROKE_WIDTH_MM, width)), 2)


def _stroke_width_mm(element: dict[str, object]) -> float:
    return _normalize_stroke_width(element.get("stroke_width"))


def _stroke_width_px(element: dict[str, object], scale: float) -> int:
    return max(1, round(_stroke_width_mm(element) * scale))


def _stroke_width_dots(element: dict[str, object], dpi: int) -> int:
    return max(1, mm_to_dots(_stroke_width_mm(element), dpi))


def _line_center_y(top: float, bottom: float) -> float:
    """Return the visual center of a line object's thickness bounds."""
    return top + max(0.0, bottom - top) / 2


def _line_center_x(left: float, right: float) -> float:
    """Return the visual center of a vertical line object's thickness bounds."""
    return left + max(0.0, right - left) / 2


def _line_bitmap_y(height: int, stroke_width: int) -> int:
    """Keep a horizontal raster line centered and fully inside its object box."""
    return max(0, min(max(1, height) - 1, (max(1, height) - max(1, stroke_width)) // 2))


def _line_dot_y(top: int, height: int, stroke_width: int) -> int:
    """Match printer line commands to the designer's centered line geometry."""
    return top + max(0, (max(1, height) - max(1, stroke_width)) // 2)


def _line_dot_x(left: int, width: int, stroke_width: int) -> int:
    """Match vertical printer line commands to the designer's centered geometry."""
    return left + max(0, (max(1, width) - max(1, stroke_width)) // 2)


def _line_is_vertical(element: dict[str, object]) -> bool:
    """A plain line has two useful orientations; 180-degree reversal is identical."""
    return _element_rotation(element) in {90, 270}


def _ensure_media_handling_supported(language: str, media_handling: str) -> None:
    supported = SUPPORTED_MEDIA_HANDLING_BY_LANGUAGE.get(language, {"tear_off"})
    if media_handling in supported:
        return
    if language == "slcs" and media_handling == "peeler":
        raise ValueError("BIXOLON/SLCS peeler command is not supported yet. Use tear_off or cutter.")
    raise ValueError(f"media_handling '{media_handling}' is not supported for {language}.")


def _split_text_lines(text: str) -> list[str]:
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    return normalized.split("\n") if normalized else [""]


def _text_line_spacing(font: ImageFont.ImageFont) -> int:
    return max(1, round(float(getattr(font, "size", 10)) * 0.22))


def _multiline_text_metrics(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
) -> tuple[list[tuple[str, tuple[int, int, int, int], int, int]], int, int, int]:
    metrics: list[tuple[str, tuple[int, int, int, int], int, int]] = []
    max_width = 0
    total_height = 0
    spacing = _text_line_spacing(font)
    for line in lines:
        probe = line if line else " "
        bbox = draw.textbbox((0, 0), probe, font=font)
        line_width = max(0, bbox[2] - bbox[0])
        line_height = max(1, bbox[3] - bbox[1])
        metrics.append((line, bbox, line_width, line_height))
        max_width = max(max_width, line_width)
        total_height += line_height
    if len(lines) > 1:
        total_height += spacing * (len(lines) - 1)
    return metrics, max_width, total_height, spacing


def _render_text_box_image(text: str, width: int, height: int, element: dict[str, object], *, transparent: bool) -> Image.Image:
    image: Image.Image
    reverse = bool(element.get("reverse", False))
    if transparent:
        background = (17, 24, 32, 255) if reverse else (255, 255, 255, 0)
        image = Image.new("RGBA", (max(1, width), max(1, height)), background)
        fill = (255, 255, 255, 255) if reverse else (17, 24, 32, 255)
    else:
        image = Image.new("1", (max(1, width), max(1, height)), 0 if reverse else 1)
        fill = 1 if reverse else 0
    draw = ImageDraw.Draw(image)
    requested = _text_requested_font_size(element, height)
    font = _fit_font_to_box(text, width - 4, height - 4, requested, str(element.get("font_name") or DEFAULT_FONT_NAME))
    lines = _split_text_lines(text)
    metrics, _max_text_w, total_text_h, spacing = _multiline_text_metrics(draw, lines, font)
    align = str(element.get("align", "left"))
    cursor_y = max(0, (height - total_text_h) // 2)
    for line, bbox, text_w, text_h in metrics:
        if align == "center":
            text_x = max(2, (width - text_w) // 2)
        elif align == "right":
            text_x = max(2, width - text_w - 2)
        else:
            text_x = 2
        if line:
            draw.text((text_x - bbox[0], cursor_y - bbox[1]), line, fill=fill, font=font)
        cursor_y += text_h + spacing
    return image


def _text_requested_font_size(element: dict[str, object], box_height_px: int) -> int:
    base_size = max(8, int(float(element.get("font_size", 10)) * 1.5))
    if bool(element.get("fit_text_to_box", True)):
        return max(base_size, int(box_height_px * 0.72))
    return base_size


def _fit_font_to_box(text: str, max_width: int, max_height: int, requested_size: int, font_name: str = DEFAULT_FONT_NAME) -> ImageFont.ImageFont:
    size = max(8, requested_size)
    lines = _split_text_lines(text)
    while size >= 8:
        font = _load_font(size, font_name)
        probe = Image.new("L", (1, 1), 255)
        draw = ImageDraw.Draw(probe)
        _metrics, text_width, text_height, _spacing = _multiline_text_metrics(draw, lines, font)
        if text_width <= max(1, max_width) and text_height <= max(1, max_height):
            return font
        size -= 2
    return _load_font(8, font_name)


def _load_font(size: int, font_name: str = DEFAULT_FONT_NAME) -> ImageFont.ImageFont:
    registry = _font_registry()
    resolved_name = _font_key(font_name)
    face = registry.get(resolved_name)
    if face is None:
        raise ValueError(f"설치된 Windows 글꼴에서 '{font_name}'을(를) 찾을 수 없습니다.")
    try:
        font = ImageFont.truetype(str(face.path), size=size, index=face.index)
        if face.variation is not None:
            font.set_variation_by_name(face.variation)
        return font
    except (OSError, ValueError) as exc:
        raise ValueError(f"Windows 글꼴 '{resolved_name}'을(를) 불러올 수 없습니다.") from exc


def _available_font_names(root: tk.Misc | None = None) -> list[str]:
    del root
    registry = _font_registry()
    names = {name for name in registry if name}
    sorted_names = sorted(names, key=lambda name: (name.casefold(), name))
    preferred = [name for name in (DEFAULT_FONT_NAME, "Segoe UI", "Arial", "Consolas") if name in names]
    others = [name for name in sorted_names if name not in preferred]
    return preferred + others


def _font_registry() -> dict[str, FontFace]:
    global _FONT_REGISTRY_CACHE
    if _FONT_REGISTRY_CACHE is not None:
        return _FONT_REGISTRY_CACHE

    font_directories = _windows_font_directories()
    font_paths: set[Path] = set()
    packaged_font = bundled_font_path()
    if packaged_font is not None:
        font_paths.add(packaged_font)
    bundled_path = bundled_font_path()
    if bundled_path is not None and bundled_path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
        font_paths.add(bundled_path)
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        except OSError:
            continue
        with key:
            index = 0
            while True:
                try:
                    _value_name, file_name, _value_type = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                search_directories = font_directories if hive == winreg.HKEY_CURRENT_USER else tuple(reversed(font_directories))
                font_path = _resolve_windows_font_path(file_name, search_directories)
                if font_path is not None:
                    font_paths.add(font_path)

    for directory in font_directories:
        try:
            entries = directory.iterdir()
        except OSError:
            continue
        for path in entries:
            if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                font_paths.add(path)

    registry: dict[str, FontFace] = {}
    for font_path in sorted(font_paths, key=lambda path: str(path).casefold()):
        for display_name, face in _loadable_font_faces(font_path):
            unique_name = display_name
            if unique_name in registry and registry[unique_name] != face:
                unique_name = f"{display_name} [{font_path.stem} #{face.index + 1}]"
                suffix = 2
                while unique_name in registry and registry[unique_name] != face:
                    unique_name = f"{display_name} [{font_path.stem} #{face.index + 1}-{suffix}]"
                    suffix += 1
            registry.setdefault(unique_name, face)
    if packaged_font is not None:
        packaged_faces = _loadable_font_faces(packaged_font)
        if packaged_faces:
            registry.setdefault(APP_FONT_FAMILY, packaged_faces[0][1])
    _FONT_REGISTRY_CACHE = registry
    return registry


def _windows_font_directories() -> tuple[Path, ...]:
    directories: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        directories.append(Path(local_app_data) / "Microsoft" / "Windows" / "Fonts")
    directories.append(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts")
    unique: list[Path] = []
    for directory in directories:
        if directory not in unique:
            unique.append(directory)
    return tuple(unique)


def _resolve_windows_font_path(file_name: object, directories: tuple[Path, ...]) -> Path | None:
    raw_name = os.path.expandvars(str(file_name).strip().strip('"'))
    if not raw_name:
        return None
    path = Path(raw_name)
    candidates = (path,) if path.is_absolute() else tuple(directory / path for directory in directories)
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() in {".ttf", ".otf", ".ttc"}:
            return candidate
    return None


def _loadable_font_faces(font_path: Path) -> list[tuple[str, FontFace]]:
    faces: list[tuple[str, FontFace]] = []
    for face_index in range(64):
        try:
            font = ImageFont.truetype(str(font_path), size=16, index=face_index)
        except (OSError, ValueError):
            break
        try:
            family, style = (str(part).strip() for part in font.getname())
        except (OSError, ValueError):
            continue
        display_name = _font_display_name(family, style)
        if display_name:
            faces.append((display_name, FontFace(path=font_path, index=face_index)))
        try:
            variation_names = font.get_variation_names()
        except (AttributeError, OSError, ValueError):
            variation_names = []
        for variation in variation_names:
            variation_label = variation.decode("utf-8", errors="replace").strip()
            variation_display = _font_display_name(family, variation_label)
            if variation_display and variation_display != display_name:
                try:
                    variation_font = ImageFont.truetype(str(font_path), size=16, index=face_index)
                    variation_font.set_variation_by_name(variation)
                except (OSError, ValueError):
                    continue
                faces.append(
                    (
                        variation_display,
                        FontFace(path=font_path, index=face_index, variation=variation),
                    )
                )
        if font_path.suffix.lower() != ".ttc":
            break
    return faces


def _font_display_name(family: str, style: str) -> str:
    family = family.strip()
    style = style.strip()
    if not family or family.startswith("@"):
        return ""
    if not style or style.casefold() in {"regular", "normal", "roman", "보통"}:
        return family
    return f"{family} {style}"


def _font_key(font_name: str) -> str:
    registry = _font_registry()
    if font_name in registry:
        return font_name
    normalized = font_name.strip().casefold().replace(" ", "")
    for name in registry:
        if name.strip().casefold().replace(" ", "") == normalized:
            return name
    return font_name


_CODE39_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%"
_CODE39_PATTERNS = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn", "4": "nnnwwnnnw",
    "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw", "8": "wnnwnnwnn", "9": "nnwwnnwnn",
    "A": "wnnnnwnnw", "B": "nnwnnwnnw", "C": "wnwnnwnnn", "D": "nnnnwwnnw", "E": "wnnnwwnnn",
    "F": "nnwnwwnnn", "G": "nnnnnwwnw", "H": "wnnnnwwnn", "I": "nnwnnwwnn", "J": "nnnnwwwnn",
    "K": "wnnnnnnww", "L": "nnwnnnnww", "M": "wnwnnnnwn", "N": "nnnnwnnww", "O": "wnnnwnnwn",
    "P": "nnwnwnnwn", "Q": "nnnnnnwww", "R": "wnnnnnwwn", "S": "nnwnnnwwn", "T": "nnnnwnwwn",
    "U": "wwnnnnnnw", "V": "nwwnnnnnw", "W": "wwwnnnnnn", "X": "nwnnwnnnw", "Y": "wwnnwnnnn",
    "Z": "nwwnwnnnn", "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "$": "nwnwnwnnn",
    "/": "nwnwnnnwn", "+": "nwnnnwnwn", "%": "nnnwnwnwn", "*": "nwnnwnwnn",
}
_ITF_PATTERNS = {
    "0": "nnwwn", "1": "wnnnw", "2": "nwnnw", "3": "wwnnn", "4": "nnwnw",
    "5": "wnwnn", "6": "nwwnn", "7": "nnnww", "8": "wnnwn", "9": "nwnwn",
}
_CODABAR_PATTERNS = {
    "0": "nnnnnww", "1": "nnnnwwn", "2": "nnnwnnw", "3": "wwnnnnn", "4": "nnwnnwn",
    "5": "wnnnnwn", "6": "nwnnnnw", "7": "nwnnwnn", "8": "nwwnnnn", "9": "wnnwnnn",
    "-": "nnnwwnn", "$": "nnwwnnn", ":": "wnnnwnw", "/": "wnwnnnw", ".": "wnwnwnn",
    "+": "nnwnwnw", "A": "nnwwnwn", "B": "nwnwnnw", "C": "nnnwnww", "D": "nnnwwwn",
}
_EAN_L = {
    "0": "0001101", "1": "0011001", "2": "0010011", "3": "0111101", "4": "0100011",
    "5": "0110001", "6": "0101111", "7": "0111011", "8": "0110111", "9": "0001011",
}
_EAN_G = {
    "0": "0100111", "1": "0110011", "2": "0011011", "3": "0100001", "4": "0011101",
    "5": "0111001", "6": "0000101", "7": "0010001", "8": "0001001", "9": "0010111",
}
_EAN_R = {
    "0": "1110010", "1": "1100110", "2": "1101100", "3": "1000010", "4": "1011100",
    "5": "1001110", "6": "1010000", "7": "1000100", "8": "1001000", "9": "1110100",
}
_EAN13_PARITY = {
    "0": "LLLLLL", "1": "LLGLGG", "2": "LLGGLG", "3": "LLGGGL", "4": "LGLLGG",
    "5": "LGGLLG", "6": "LGGGLL", "7": "LGLGLG", "8": "LGLGGL", "9": "LGGLGL",
}


def _barcode_options(element: dict[str, object]) -> dict[str, object]:
    options = _normalize_barcode_options(element.get("barcode_options"))
    element["barcode_options"] = options
    return options


def _barcode_option_int(element: dict[str, object] | None, key: str, fallback: int, minimum: int, maximum: int) -> int:
    if element is None:
        return fallback
    options = _barcode_options(element)
    return max(minimum, min(maximum, int(_float_value(options.get(key), fallback))))


def _barcode_option_float(element: dict[str, object], key: str, fallback: float, minimum: float, maximum: float) -> float:
    options = _barcode_options(element)
    return max(minimum, min(maximum, _float_value(options.get(key), fallback)))


def _barcode_option_bool(element: dict[str, object], key: str, fallback: bool) -> bool:
    options = _barcode_options(element)
    return bool(options.get(key, fallback))


def _barcode_check_mode(element: dict[str, object]) -> str:
    options = _barcode_options(element)
    value = str(options.get("check_digit", "auto")).lower()
    return value if value in BARCODE_CHECK_DIGIT_LABELS else "auto"


def _render_qr_code_image(value: str, width: int, height: int, element: dict[str, object]) -> Image.Image:
    clean_value = sanitize_barcode(value)
    options = _barcode_options(element)
    ecc = str(options.get("qr_ecc", "M")).upper()
    error_correction = QR_ERROR_CORRECTION.get(ecc, ERROR_CORRECT_M)
    qr = qrcode.QRCode(version=None, error_correction=error_correction, box_size=1, border=4)
    qr.add_data(clean_value)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    module_count = max(1, len(matrix))

    image_width = max(1, width)
    image_height = max(1, height)
    image = Image.new("1", (image_width, image_height), 1)
    max_symbol_size = max(1, min(image_width, image_height))
    cell_size = max(1, max_symbol_size // module_count)
    symbol_size = module_count * cell_size

    source = Image.new("1", (module_count, module_count), 1)
    draw = ImageDraw.Draw(source)
    for row_index, row in enumerate(matrix):
        for col_index, enabled in enumerate(row):
            if enabled:
                source.putpixel((col_index, row_index), 0)
    source = source.resize((symbol_size, symbol_size), Image.Resampling.NEAREST)
    paste_x = max(0, (image_width - symbol_size) // 2)
    paste_y = max(0, (image_height - symbol_size) // 2)
    image.paste(source, (paste_x, paste_y))
    return image


def _render_2d_barcode_image(code_type: str, value: str, width: int, height: int, element: dict[str, object]) -> Image.Image:
    if code_type == "qr":
        return _render_qr_code_image(value, width, height, element)
    if code_type in ZXING_2D_FORMATS:
        return _render_zxing_2d_barcode_image(code_type, value, width, height)
    raise ValueError(f"{BARCODE_TYPES.get(code_type, code_type)} does not have a verified bitmap renderer.")


def _render_zxing_2d_barcode_image(code_type: str, value: str, width: int, height: int) -> Image.Image:
    clean_value = sanitize_barcode(value)
    barcode = zxingcpp.create_barcode(clean_value, ZXING_2D_FORMATS[code_type])
    source = _zxing_image_to_pil(zxingcpp.write_barcode_to_image(barcode, scale=4, add_quiet_zones=True))
    return _fit_barcode_source_to_box(source, width, height)


def _zxing_image_to_pil(source: zxingcpp.Image) -> Image.Image:
    shape = source.shape
    data = bytes(memoryview(source))
    if len(shape) == 2:
        height, width = shape
        image = Image.frombuffer("L", (width, height), data, "raw", "L", 0, 1)
    elif len(shape) == 3 and shape[2] == 3:
        height, width, _channels = shape
        image = Image.frombuffer("RGB", (width, height), data, "raw", "RGB", 0, 1).convert("L")
    else:
        raise ValueError("Unsupported zxing image format.")
    return image.point(lambda pixel: 0 if pixel < 128 else 255).convert("1")


def _fit_barcode_source_to_box(source: Image.Image, width: int, height: int) -> Image.Image:
    image_width = max(1, width)
    image_height = max(1, height)
    image = Image.new("1", (image_width, image_height), 1)
    source_width, source_height = source.size
    scale = min(image_width / max(1, source_width), image_height / max(1, source_height))
    target_width = max(1, min(image_width, round(source_width * scale)))
    target_height = max(1, min(image_height, round(source_height * scale)))
    resized = source.resize((target_width, target_height), Image.Resampling.NEAREST)
    paste_x = max(0, (image_width - target_width) // 2)
    paste_y = max(0, (image_height - target_height) // 2)
    image.paste(resized, (paste_x, paste_y))
    return image


def _barcode_image_to_transparent_rgba(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    alpha = gray.point(lambda pixel: 0 if pixel >= 250 else 255)
    rgba = Image.new("RGBA", image.size, (17, 24, 32, 255))
    rgba.putalpha(alpha)
    return rgba


def _render_1d_barcode_image(code_type: str, value: str, width: int, height: int, element: dict[str, object]) -> Image.Image:
    if code_type in {"ean13", "ean8", "upca"}:
        return _render_ean_upc_image(code_type, value, width, height, element)
    modules, display_value = _one_d_barcode_modules(code_type, value, element)
    image = Image.new("1", (max(1, width), max(1, height)), 1)
    draw = ImageDraw.Draw(image)
    padding = max(1, min(6, round(min(width, height) * 0.035)))
    hri_enabled = _barcode_option_bool(element, "human_readable", True)
    hri_height = 0
    hri_font = _load_font(max(8, min(22, round(height * 0.16))), str(element.get("font_name") or "Consolas"))
    if hri_enabled and height >= 22:
        bbox = draw.textbbox((0, 0), display_value, font=hri_font)
        hri_height = min(max(12, bbox[3] - bbox[1] + 5), max(12, height // 3))
    bar_height = max(6, height - (padding * 2) - hri_height)
    quiet_zone = _barcode_option_int(element, "quiet_zone", 10, 0, 40)
    source_width = max(1, sum(modules) + (quiet_zone * 2))
    source = Image.new("1", (source_width, bar_height), 1)
    source_draw = ImageDraw.Draw(source)
    cursor = quiet_zone
    black = True
    for module_width in modules:
        if black:
            source_draw.rectangle((cursor, 0, cursor + module_width - 1, bar_height), fill=0)
        cursor += module_width
        black = not black
    available_width = max(1, width - (padding * 2))
    configured_module = _barcode_option_int(element, "module_width", 0, 0, 12)
    target_width = min(available_width, source_width * configured_module) if configured_module else available_width
    target_width = max(1, target_width)
    barcode = source.resize((target_width, bar_height), Image.Resampling.NEAREST)
    image.paste(barcode, (padding + max(0, (available_width - target_width) // 2), padding))
    if hri_height:
        bbox = draw.textbbox((0, 0), display_value, font=hri_font)
        text_w = bbox[2] - bbox[0]
        text_x = max(0, (width - text_w) // 2)
        text_y = max(padding + bar_height + 2, height - hri_height + 1)
        draw.text((text_x - bbox[0], text_y - bbox[1]), display_value, fill=0, font=hri_font)
    return image


def _render_ean_upc_image(code_type: str, value: str, width: int, height: int, element: dict[str, object]) -> Image.Image:
    if code_type == "ean13":
        display_value = _normalize_numeric_with_checksum(value, 12, 13, "EAN-13")
        bits = _ean13_bits(display_value)
        guard_ranges = ((0, 3), (45, 50), (92, 95))
    elif code_type == "ean8":
        display_value = _normalize_numeric_with_checksum(value, 7, 8, "EAN-8")
        bits = _ean8_bits(display_value)
        guard_ranges = ((0, 3), (31, 36), (64, 67))
    else:
        display_value = _normalize_numeric_with_checksum(value, 11, 12, "UPC-A")
        bits = _upca_bits(display_value)
        guard_ranges = ((0, 3), (45, 50), (92, 95))

    image = Image.new("1", (max(1, width), max(1, height)), 1)
    draw = ImageDraw.Draw(image)
    padding = max(1, min(6, round(min(width, height) * 0.035)))
    quiet_zone = _barcode_option_int(element, "quiet_zone", 10, 0, 40)
    hri_enabled = _barcode_option_bool(element, "human_readable", True)
    font = _load_font(max(8, min(22, round(height * 0.17))), str(element.get("font_name") or "Consolas"))
    text_height = 0
    if hri_enabled and height >= 24:
        bbox = draw.textbbox((0, 0), display_value, font=font)
        text_height = min(max(12, bbox[3] - bbox[1] + 6), max(12, height // 3))

    bar_height = max(8, height - (padding * 2) - text_height)
    guard_extension = min(max(4, text_height // 2), max(4, height - padding - bar_height)) if text_height else 0
    guard_height = min(height - padding, bar_height + guard_extension)
    module_count = len(bits)
    available_width = max(1, width - (padding * 2))
    configured_module = _barcode_option_int(element, "module_width", 0, 0, 12)
    target_width = min(available_width, (module_count + (quiet_zone * 2)) * configured_module) if configured_module else available_width
    target_width = max(1, target_width)
    scale = target_width / max(1, module_count + (quiet_zone * 2))
    bar_left = padding + max(0, (available_width - target_width) / 2) + (quiet_zone * scale)
    top = padding

    for index, bit in enumerate(bits):
        if bit != "1":
            continue
        x1 = bar_left + (index * scale)
        x2 = bar_left + ((index + 1) * scale)
        is_guard = any(start <= index < end for start, end in guard_ranges)
        y2 = top + (guard_height if is_guard else bar_height)
        draw.rectangle((round(x1), top, max(round(x1), round(x2) - 1), y2), fill=0)

    if hri_enabled and text_height:
        text_y = min(height - text_height + 1, top + bar_height + 2)
        if code_type == "ean13":
            _draw_centered_hri(draw, display_value[0], bar_left - (7 * scale), text_y, font)
            _draw_centered_hri(draw, display_value[1:7], bar_left + (24 * scale), text_y, font)
            _draw_centered_hri(draw, display_value[7:], bar_left + (72 * scale), text_y, font)
        elif code_type == "ean8":
            _draw_centered_hri(draw, display_value[:4], bar_left + (17 * scale), text_y, font)
            _draw_centered_hri(draw, display_value[4:], bar_left + (50 * scale), text_y, font)
        else:
            _draw_centered_hri(draw, display_value[0], bar_left - (6 * scale), text_y, font)
            _draw_centered_hri(draw, display_value[1:6], bar_left + (24 * scale), text_y, font)
            _draw_centered_hri(draw, display_value[6:11], bar_left + (72 * scale), text_y, font)
            _draw_centered_hri(draw, display_value[11], bar_left + (101 * scale), text_y, font)
    return image


def _draw_centered_hri(draw: ImageDraw.ImageDraw, text: str, center_x: float, y: float, font: ImageFont.ImageFont) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    draw.text((round(center_x - (width / 2) - bbox[0]), round(y - bbox[1])), text, fill=0, font=font)


def _one_d_barcode_modules(code_type: str, value: str, element: dict[str, object]) -> tuple[list[int], str]:
    if code_type in {"code128", "gs1_128"}:
        clean = _clean_code128_value(value, gs1=code_type == "gs1_128")
        return _code128_module_widths(clean, gs1=code_type == "gs1_128"), clean
    if code_type == "code39":
        clean = _clean_code39_value(value)
        if _barcode_check_mode(element) == "on":
            clean += _code39_check_digit(clean)
        return _code39_module_widths(clean, _barcode_option_float(element, "wide_ratio", 2.5, 2.0, 4.0)), clean
    if code_type == "ean13":
        clean = _normalize_numeric_with_checksum(value, 12, 13, "EAN-13")
        return _runs_from_bits(_ean13_bits(clean)), clean
    if code_type == "ean8":
        clean = _normalize_numeric_with_checksum(value, 7, 8, "EAN-8")
        return _runs_from_bits(_ean8_bits(clean)), clean
    if code_type == "upca":
        clean = _normalize_numeric_with_checksum(value, 11, 12, "UPC-A")
        return _runs_from_bits(_ean13_bits("0" + clean)), clean
    if code_type == "itf":
        clean = _numeric_only(value)
        if _barcode_check_mode(element) == "on":
            clean += _ean_checksum(clean)
        if len(clean) % 2:
            raise ValueError("ITF는 짝수 자리 숫자가 필요합니다.")
        return _itf_module_widths(clean, _barcode_option_float(element, "wide_ratio", 2.5, 2.0, 4.0)), clean
    if code_type == "codabar":
        clean = _clean_codabar_value(value)
        return _codabar_module_widths(clean, _barcode_option_float(element, "wide_ratio", 2.5, 2.0, 4.0)), clean
    if code_type == "pharmacode":
        number = int(_numeric_only(value))
        if number < 3 or number > 131070:
            raise ValueError("Pharmacode는 3부터 131070까지 가능합니다.")
        return _pharmacode_module_widths(number), str(number)
    raise ValueError(f"{BARCODE_TYPES.get(code_type, code_type)}는 현재 실제 인코딩을 지원하지 않습니다.")


def _clean_code128_value(value: str, *, gs1: bool = False) -> str:
    text = str(value).strip()
    if gs1:
        text = text.replace("(", "").replace(")", "")
    return sanitize_barcode(text)


def _clean_code39_value(value: str) -> str:
    clean = "".join(char for char in str(value).upper().strip() if char in _CODE39_CHARS)
    if not clean:
        raise ValueError("Code 39에 사용할 수 있는 데이터가 없습니다.")
    return clean


def _clean_codabar_value(value: str) -> str:
    clean = "".join(char for char in str(value).upper().strip() if char in _CODABAR_PATTERNS)
    if not clean:
        raise ValueError("Codabar에 사용할 수 있는 데이터가 없습니다.")
    starts = {"A", "B", "C", "D"}
    if clean[0] not in starts:
        clean = "A" + clean
    if clean[-1] not in starts:
        clean = clean + "A"
    return clean


def _numeric_only(value: str) -> str:
    digits = "".join(char for char in str(value) if char.isdigit())
    if not digits:
        raise ValueError("숫자 바코드에 사용할 숫자가 없습니다.")
    return digits


def _normalize_numeric_with_checksum(value: str, body_length: int, total_length: int, label: str) -> str:
    digits = _numeric_only(value)
    if len(digits) == body_length:
        return digits + _ean_checksum(digits)
    if len(digits) == total_length:
        expected = _ean_checksum(digits[:-1])
        if digits[-1] != expected:
            raise ValueError(f"{label} 체크디지트가 맞지 않습니다. 예상값: {expected}")
        return digits
    raise ValueError(f"{label}는 {body_length}자리 또는 {total_length}자리 숫자가 필요합니다.")


def _ean_checksum(body: str) -> str:
    total = 0
    for index, digit in enumerate(reversed(body)):
        total += int(digit) * (3 if index % 2 == 0 else 1)
    return str((10 - (total % 10)) % 10)


def _code39_check_digit(value: str) -> str:
    total = sum(_CODE39_CHARS.index(char) for char in value)
    return _CODE39_CHARS[total % 43]


def _code39_module_widths(value: str, wide_ratio: float) -> list[int]:
    modules: list[int] = []
    wide = max(2, round(wide_ratio))
    encoded = "*" + value + "*"
    for char_index, char in enumerate(encoded):
        pattern = _CODE39_PATTERNS[char]
        modules.extend(wide if part == "w" else 1 for part in pattern)
        if char_index < len(encoded) - 1:
            modules.append(1)
    return modules


def _itf_module_widths(value: str, wide_ratio: float) -> list[int]:
    wide = max(2, round(wide_ratio))
    modules: list[int] = [1, 1, 1, 1]
    for index in range(0, len(value), 2):
        bars = _ITF_PATTERNS[value[index]]
        spaces = _ITF_PATTERNS[value[index + 1]]
        for bar, space in zip(bars, spaces):
            modules.append(wide if bar == "w" else 1)
            modules.append(wide if space == "w" else 1)
    modules.extend([wide, 1, 1])
    return modules


def _codabar_module_widths(value: str, wide_ratio: float) -> list[int]:
    wide = max(2, round(wide_ratio))
    modules: list[int] = []
    for char_index, char in enumerate(value):
        modules.extend(wide if part == "w" else 1 for part in _CODABAR_PATTERNS[char])
        if char_index < len(value) - 1:
            modules.append(1)
    return modules


def _pharmacode_module_widths(value: int) -> list[int]:
    bars: list[int] = []
    number = value
    while number > 0:
        if number % 2:
            bars.append(1)
            number = (number - 1) // 2
        else:
            bars.append(3)
            number = (number - 2) // 2
    modules: list[int] = []
    for index, bar in enumerate(reversed(bars)):
        modules.append(bar)
        if index < len(bars) - 1:
            modules.append(1)
    return modules


def _ean13_bits(value: str) -> str:
    parity = _EAN13_PARITY[value[0]]
    left = "".join((_EAN_L if mode == "L" else _EAN_G)[digit] for mode, digit in zip(parity, value[1:7]))
    right = "".join(_EAN_R[digit] for digit in value[7:])
    return "101" + left + "01010" + right + "101"


def _ean8_bits(value: str) -> str:
    left = "".join(_EAN_L[digit] for digit in value[:4])
    right = "".join(_EAN_R[digit] for digit in value[4:])
    return "101" + left + "01010" + right + "101"


def _upca_bits(value: str) -> str:
    left = "".join(_EAN_L[digit] for digit in value[:6])
    right = "".join(_EAN_R[digit] for digit in value[6:])
    return "101" + left + "01010" + right + "101"


def _runs_from_bits(bits: str) -> list[int]:
    runs: list[int] = []
    current = bits[0]
    count = 0
    for bit in bits:
        if bit == current:
            count += 1
        else:
            runs.append(count)
            current = bit
            count = 1
    runs.append(count)
    return runs


def _render_code128_image(value: str, width: int, height: int) -> Image.Image:
    modules = _code128_module_widths(value)
    quiet_zone = 10
    source_width = max(1, sum(modules) + (quiet_zone * 2))
    source = Image.new("1", (source_width, max(1, height)), 1)
    draw = ImageDraw.Draw(source)
    cursor = quiet_zone
    black = True
    for module_width in modules:
        if black:
            draw.rectangle((cursor, 0, cursor + module_width - 1, height), fill=0)
        cursor += module_width
        black = not black
    return source.resize((max(1, width), max(1, height)), Image.Resampling.NEAREST)


def _code128_module_widths(value: str, *, gs1: bool = False) -> list[int]:
    codes = [104]
    if gs1:
        codes.append(102)
    for char in value:
        code = ord(char) - 32
        if code < 0 or code > 95:
            code = ord("?") - 32
        codes.append(code)
    checksum = 104
    for index, code in enumerate(codes[1:], start=1):
        checksum += code * index
    codes.append(checksum % 103)
    codes.append(106)
    modules: list[int] = []
    for code in codes:
        modules.extend(int(width) for width in _CODE128_PATTERNS[code])
    return modules


def _design_analysis_counts(elements: list[dict[str, object]]) -> dict[str, int]:
    return {
        "table": sum(1 for element in elements if str(element.get("type")) == "table"),
        "line": sum(1 for element in elements if str(element.get("type")) == "line"),
        "box": sum(1 for element in elements if str(element.get("type")) == "box"),
        "text": sum(1 for element in elements if str(element.get("type")) in TEXT_ELEMENT_TYPES),
        "barcode": sum(1 for element in elements if _is_code_element(element)),
    }


def _render_elements_preview(label: dict[str, object], elements: list[dict[str, object]], base_dir: Path) -> Image.Image:
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = base_dir
    app.template = {"version": 1, "label": label, "elements": elements}
    app.elements = elements
    app.preview_row = _empty_row()
    return LabelDesignerApp.render_preview_image(app)


def _run_design_analysis_cli(args: argparse.Namespace, base_dir: Path) -> int:
    source = Path(args.analyze_design).resolve()
    if not source.exists():
        raise FileNotFoundError(f"도안 파일을 찾을 수 없습니다: {source}")
    config_template = default_template_from_config(base_dir / "config.ini")
    label = dict(config_template["label"])  # type: ignore[index]
    if args.label_width_mm is not None:
        label["width_mm"] = _normalize_label_mm(args.label_width_mm, DEFAULT_LABEL_WIDTH_MM)
    if args.label_height_mm is not None:
        label["height_mm"] = _normalize_label_mm(args.label_height_mm, DEFAULT_LABEL_HEIGHT_MM)
    image = _open_design_image(source)
    elements = _design_template_elements_from_image(image, label, base_dir=base_dir)
    payload = {
        "source": str(source),
        "base_dir": str(base_dir),
        "label": label,
        "ocr_engine": str(_resolve_tesseract_executable(base_dir) or ""),
        "counts": _design_analysis_counts(elements),
        "elements": elements,
    }
    if args.analysis_json:
        target = Path(args.analysis_json).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.analysis_preview:
        preview_path = Path(args.analysis_preview).resolve()
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        _render_elements_preview(label, elements, base_dir).save(preview_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visual label template designer.")
    parser.add_argument("label_file", nargs="?", help="Saved .gblabel or .json label file to open")
    parser.add_argument("--base-dir", default=None, help="Folder containing config.ini and barcode_db.xlsx")
    parser.add_argument("--print", dest="print_on_open", action="store_true", help="Open the label file and show the print flow")
    parser.add_argument("--smoke-test", action="store_true", help="Load template and data source without showing the UI")
    parser.add_argument("--ui-smoke-test", action="store_true", help="Create the Tk UI once and exit without printing")
    parser.add_argument("--analyze-design", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--label-width-mm", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--label-height-mm", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--analysis-json", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--analysis-preview", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.smoke_test and not args.base_dir:
        base_dir = executable_dir()
    else:
        base_dir = Path(args.base_dir).resolve() if args.base_dir else app_base_dir()
    label_file = Path(args.label_file).resolve() if args.label_file else None
    if args.analyze_design:
        return _run_design_analysis_cli(args, base_dir)
    if args.print_on_open and label_file is None:
        parser.error("--print requires a label_file")
    if args.smoke_test:
        if label_file is not None:
            load_template_file(label_file)
        else:
            template_dir = base_dir / "templates"
            template_dir.mkdir(parents=True, exist_ok=True)
            template_path = template_dir / "default_label.json"
            ensure_blank_default_template(template_path, base_dir / "config.ini")
            load_template_file(template_path)
        try:
            load_db_rows(base_dir / "barcode_db.xlsx")
        except Exception:
            pass
        return 0
    if args.ui_smoke_test:
        # UI smoke tests must only construct the window. File association is
        # an operating-system registration step and can wait on Explorer.
        app = LabelDesignerApp(
            base_dir,
            initial_template_path=label_file,
            print_on_open=False,
            register_file_association=False,
        )
        app.update_idletasks()
        app.destroy()
        return 0
    app = LabelDesignerApp(base_dir, initial_template_path=label_file, print_on_open=args.print_on_open)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
