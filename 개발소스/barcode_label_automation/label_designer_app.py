from __future__ import annotations

import argparse
import io
import shutil
import struct
from configparser import ConfigParser
import json
import subprocess
import sys
import tkinter as tk
import winreg
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from uuid import uuid4

import qrcode
import zxingcpp
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageTk

from .config import DEFAULTS
from .config import SUPPORTED_BARCODE_TYPES as PRINT_SUPPORTED_BARCODE_TYPES
from .config import load_config
from .data_store import DB_HEADERS, LABEL_HEADERS, load_db_rows
from .printers.network import send_raw as send_network_raw
from .printers.windows_raw import send_raw as send_windows_raw
from .sanitizer import sanitize_barcode, sanitize_slcs_text, sanitize_zpl_text
from .templates import mm_to_dots
from .ui_tokens import COLORS, SPACING, TYPOGRAPHY


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
    "barcode": "1D 바코드",
    "qr": "QR",
    "box": "박스",
    "line": "선",
    "table": "표",
    "image": "그림",
}
ALIGNMENTS = {"left": "왼쪽", "center": "가운데", "right": "오른쪽"}
ARRANGE_MODES = {"normal": "일반", "front": "글 앞으로", "behind": "글 뒤로", "through": "어울림"}
VISIBLE_ELEMENT_TYPE_KEYS = ("text", "barcode", "qr", "image", "box", "line", "table")
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
DESIGNER_MIN_SCALE = 1.2
DESIGNER_CANVAS_MARGIN = 80
DESIGNER_BG = COLORS.surface_muted
RULER_BG = COLORS.surface
RULER_OUTLINE = COLORS.border_strong
SELECT_COLOR = COLORS.accent
DEFAULT_FONT_NAME = "Malgun Gothic"
LABEL_FILE_EXTENSION = ".gblabel"
LABEL_FILE_TYPES = [
    ("거복이 라벨 파일", f"*{LABEL_FILE_EXTENSION}"),
    ("라벨 템플릿 JSON", "*.json"),
    ("모든 파일", "*.*"),
]
_FONT_REGISTRY_CACHE: dict[str, Path] | None = None
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
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_template(width_mm: int = 50, height_mm: int = 40) -> dict[str, object]:
    return {
        "version": 1,
        "label": {"width_mm": width_mm, "height_mm": height_mm},
        "elements": [],
    }


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
    }
    if element_type in {"barcode", "qr"}:
        element["barcode_type"] = barcode_type or ("qr" if element_type == "qr" else "code128")
        element["barcode_options"] = dict(BARCODE_OPTION_DEFAULTS)
    if element_type == "table":
        element["table_rows"] = 3
        element["table_cols"] = 3
    return element


def render_template_text(template_text: str, row: dict[str, str]) -> str:
    text = template_text
    for field in FIELDS:
        text = text.replace("{{" + field + "}}", str(row.get(field, "")))
    return text


def _element_type_from_label(label: str, fallback: str = "text") -> str:
    for key in VISIBLE_ELEMENT_TYPE_KEYS:
        if ELEMENT_TYPES[key] == label:
            return key
    return fallback


def normalize_template(template: dict[str, object]) -> dict[str, object]:
    label = template.get("label") if isinstance(template.get("label"), dict) else {}
    width_mm = int(float(label.get("width_mm", 50)))  # type: ignore[union-attr]
    height_mm = int(float(label.get("height_mm", 40)))  # type: ignore[union-attr]
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
    }
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
    if element_type == "image":
        normalized["image_path"] = str(element.get("image_path", ""))
    return normalized


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


class LabelDesignerApp(tk.Tk):
    def __init__(self, base_dir: Path, initial_template_path: Path | None = None, print_on_open: bool = False) -> None:
        super().__init__()
        self.base_dir = base_dir
        self.template_dir = base_dir / "templates"
        self.template_path = initial_template_path.resolve() if initial_template_path else self.template_dir / "default_label.json"
        self.initial_template_path = initial_template_path
        self.print_on_open = print_on_open
        self._initial_template_error: str | None = None
        self.config_path = base_dir / "config.ini"
        self.db_path = base_dir / "barcode_db.xlsx"
        self.data_source_path: Path | None = None
        self.scale = DESIGNER_MAX_SCALE
        self._redraw_after_id: str | None = None
        self._refreshing_data_panel = False
        self.template = self._load_initial_template()
        self.elements: list[dict[str, object]] = list(self.template["elements"])  # type: ignore[arg-type]
        self.selected_id: str | None = None
        self.drag_state: dict[str, float | str] | None = None
        self.canvas_images: list[ImageTk.PhotoImage] = []
        self.db_rows: list[dict[str, str]] = []
        self.preview_row = _empty_row()
        self.selected_data_indexes: set[int] = set()
        if self.elements:
            self.selected_id = str(self.elements[0]["id"])

        status_text = f"라벨 파일을 불러왔습니다: {self.template_path.name}" if initial_template_path else "템플릿을 불러왔습니다."
        if self._initial_template_error:
            status_text = "라벨 파일을 열지 못해 기본 템플릿으로 시작했습니다."
        self.status_var = tk.StringVar(value=status_text)
        self.sample_var = tk.StringVar()
        self.data_source_label_var = tk.StringVar(value=self._data_source_display_name())
        self.record_count_var = tk.StringVar(value="")
        self.queue_status_var = tk.StringVar(value="")
        self.type_var = tk.StringVar()
        self.barcode_type_var = tk.StringVar()
        self.text_var = tk.StringVar()
        self.field_var = tk.StringVar()
        self.x_var = tk.StringVar()
        self.y_var = tk.StringVar()
        self.w_var = tk.StringVar()
        self.h_var = tk.StringVar()
        self.font_var = tk.StringVar()
        self.font_name_var = tk.StringVar(value=DEFAULT_FONT_NAME)
        self.align_var = tk.StringVar()
        self.arrange_var = tk.StringVar(value=ARRANGE_MODES["normal"])
        self.reverse_var = tk.BooleanVar(value=False)
        self.table_rows_var = tk.StringVar(value="3")
        self.table_cols_var = tk.StringVar(value="3")
        self.width_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.font_choices = _available_font_names()
        self.sample_combo: ttk.Combobox | None = None
        self.data_tree: ttk.Treeview | None = None
        self.queue_tree: ttk.Treeview | None = None
        self.data_card: tk.Frame | None = None

        self.title(self._window_title())
        self._apply_window_icon()
        screen_width = max(1024, self.winfo_screenwidth())
        screen_height = max(720, self.winfo_screenheight())
        window_width = min(1600, max(1120, screen_width - 80))
        window_height = min(980, max(760, screen_height - 90))
        self.geometry(f"{window_width}x{window_height}+20+20")
        self.minsize(1040, 640)
        self.configure(bg=COLORS.background)
        self._configure_style()
        self._build_menu()
        self._build_ui()
        self._load_values_to_controls()
        self.refresh_sample_options()
        self.load_selected_properties()
        self.bind("<Delete>", self.on_delete_key)
        self.redraw()
        if self._initial_template_error:
            self.after(350, self._show_initial_template_error)
        elif self.print_on_open:
            self.after(450, lambda: self.run_output_test(send_to_printer=True))
        self.after(150, self._raise_initial_window)

    def _window_title(self) -> str:
        if self.template_path:
            return f"라벨 디자이너 - {self.template_path.name}"
        return "라벨 디자이너"

    def _show_initial_template_error(self) -> None:
        if self._initial_template_error:
            messagebox.showerror("라벨 파일 열기 실패", self._initial_template_error)

    def _apply_window_icon(self) -> None:
        candidates = [
            self.base_dir / "assets" / "label_designer.ico",
            Path(getattr(sys, "_MEIPASS", "")) / "assets" / "label_designer.ico",
            Path(__file__).resolve().parents[1] / "assets" / "label_designer.ico",
        ]
        for icon_path in candidates:
            if not icon_path.exists():
                continue
            try:
                self.iconbitmap(default=str(icon_path))
                return
            except tk.TclError:
                continue

    def _raise_initial_window(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(700, lambda: self.attributes("-topmost", False))
        except tk.TclError:
            pass

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
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
        style.configure("PanelTitle.TLabel", font=TYPOGRAPHY.section_title, foreground=COLORS.text_primary, background=COLORS.surface_muted)
        style.configure("SidePanelTitle.TLabel", font=TYPOGRAPHY.section_title, foreground=COLORS.text_primary, background=COLORS.surface)
        style.configure("RibbonCaption.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.surface)
        style.configure("Status.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.background)
        style.configure(
            "Tool.TButton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
            bordercolor=COLORS.border_strong,
            padding=(12, 12),
            relief="flat",
            borderwidth=1,
            anchor="w",
        )
        style.map("Tool.TButton", background=[("active", COLORS.accent_soft)], foreground=[("active", COLORS.accent)])
        style.configure(
            "Ribbon.TButton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
            bordercolor=COLORS.border_strong,
            padding=(16, 10),
            relief="flat",
            borderwidth=1,
        )
        style.map("Ribbon.TButton", background=[("active", COLORS.accent_soft)], foreground=[("active", COLORS.accent)])
        style.configure(
            "Primary.TButton",
            font=TYPOGRAPHY.button_text,
            foreground="#ffffff",
            background=COLORS.primary,
            bordercolor=COLORS.primary,
            padding=(18, 10),
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
            padding=(16, 9),
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
            padding=(16, 9),
            relief="flat",
            borderwidth=1,
        )
        style.configure("TEntry", padding=(10, 6), fieldbackground=COLORS.surface, bordercolor=COLORS.border_strong)
        style.configure("TCombobox", padding=(10, 6), fieldbackground=COLORS.surface, bordercolor=COLORS.border_strong)
        style.configure("TSpinbox", padding=(10, 6), fieldbackground=COLORS.surface, bordercolor=COLORS.border_strong)
        style.configure(
            "TMenubutton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
            bordercolor=COLORS.border_strong,
            padding=(16, 10),
            relief="flat",
            borderwidth=1,
        )

    def _build_menu(self) -> None:
        self.config(menu="")

    def _build_ui(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(SPACING.page_padding, 12))
        header.pack(fill="x")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="거복이의꿈", style="Brand.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(header, text="라벨 발행 프로그램", style="HeaderTitle.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(header, text="라벨 디자인과 출력 파일을 한 화면에서 정리합니다.", style="HeaderSub.TLabel").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="인쇄", command=lambda: self.run_output_test(send_to_printer=True), style="Primary.TButton").grid(row=0, column=3, rowspan=3, sticky="e", padx=(8, 0))

        body = ttk.Frame(self, style="App.TFrame", padding=(SPACING.page_padding, 14, SPACING.page_padding, 12))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, minsize=220)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, minsize=300)
        body.rowconfigure(1, weight=1)
        body.rowconfigure(2, weight=0)

        ribbon_card = tk.Frame(body, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        ribbon_card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        ribbon_card.columnconfigure(0, weight=1)
        ribbon = ttk.Frame(ribbon_card, style="Ribbon.TFrame", padding=(12, 10, 12, 8))
        ribbon.grid(row=0, column=0, sticky="ew")
        ribbon.columnconfigure(0, weight=1)
        self._build_canvas_toolbar(ribbon)

        tools_card = tk.Frame(body, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        tools_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        tools_card.columnconfigure(0, weight=1)
        tools_card.rowconfigure(0, weight=1)
        tools_inner = ttk.Frame(tools_card, style="SidePanel.TFrame", padding=(16, 16, 16, 14))
        tools_inner.grid(row=0, column=0, sticky="nsew")
        tools_inner.columnconfigure(0, weight=1)
        self._build_tool_panel(tools_inner)

        center_card = tk.Frame(body, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        center_card.grid(row=1, column=1, sticky="nsew")
        center_card.columnconfigure(0, weight=1)
        center_card.rowconfigure(0, weight=1)
        center = ttk.Frame(center_card, style="Workbench.TFrame", padding=10)
        center.grid(row=0, column=0, sticky="nsew")
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(center, bg=DESIGNER_BG, highlightthickness=1, highlightbackground=COLORS.border)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Double-1>", self.on_canvas_double_click)
        self.canvas.bind("<Delete>", lambda _event: self.delete_selected())
        self.canvas.bind("<BackSpace>", lambda _event: self.delete_selected())
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        properties_card = tk.Frame(body, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        properties_card.grid(row=1, column=2, sticky="nsew", padx=(12, 0))
        properties_card.columnconfigure(0, weight=1)
        properties_card.rowconfigure(0, weight=1)
        properties_inner = ttk.Frame(properties_card, style="SidePanel.TFrame", padding=(16, 16, 16, 14))
        properties_inner.grid(row=0, column=0, sticky="nsew")
        properties_inner.columnconfigure(0, weight=1)
        self._build_property_panel(properties_inner)

        self.data_card = tk.Frame(body, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        self.data_card.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        self.data_card.columnconfigure(0, weight=1)
        self.data_card.rowconfigure(0, weight=1)
        data_inner = ttk.Frame(self.data_card, style="SidePanel.TFrame", padding=(10, 8))
        data_inner.grid(row=0, column=0, sticky="nsew")
        self._build_data_panel(data_inner)
        self.data_card.grid_remove()

        footer = ttk.Frame(self, style="StatusBar.TFrame", padding=(SPACING.page_padding, 7, SPACING.page_padding, 7))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").pack(side="left")

    def _build_tool_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="개체 도구", style="SidePanelTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        tools = [
            ("T  텍스트", lambda: self.add_element("text")),
            ("|||  1D 바코드", lambda: self.add_element("barcode")),
            ("▦  2D 코드", lambda: self.add_barcode_element("qr")),
            ("▧  그림", self.add_image_element),
            ("□  박스", lambda: self.add_element("box")),
            ("/  선", lambda: self.add_element("line")),
            ("▤  표", lambda: self.add_element("table")),
        ]
        row = 1
        for index, (text, command) in enumerate(tools):
            ttk.Button(parent, text=text, command=command, style="Tool.TButton").grid(
                row=row + (index // 2),
                column=index % 2,
                sticky="ew",
                padx=(0 if index % 2 == 0 else 4, 0),
                pady=3,
            )

        tool_rows = (len(tools) + 1) // 2
        row += tool_rows
        ttk.Separator(parent).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(14, 10))
        row += 1
        ttk.Label(parent, text="템플릿 작업", style="SidePanelTitle.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1
        ttk.Button(parent, text="저장", command=self.save_template, style="Primary.TButton").grid(row=row, column=0, sticky="ew", pady=3)
        ttk.Button(parent, text="다른 저장", command=self.save_template_as, style="Tool.TButton").grid(row=row, column=1, sticky="ew", padx=(4, 0), pady=3)
        row += 1
        ttk.Button(parent, text="불러오기", command=self.open_template, style="Tool.TButton").grid(row=row, column=0, sticky="ew", pady=3)
        ttk.Button(parent, text="인쇄파일", command=lambda: self.run_output_test(send_to_printer=False), style="Tool.TButton").grid(row=row, column=1, sticky="ew", padx=(4, 0), pady=3)
        row += 1
        ttk.Button(parent, text="템플릿 폴더", command=lambda: self.open_path(self.template_dir), style="Tool.TButton").grid(row=row, column=0, columnspan=2, sticky="ew", pady=(3, 0))

    def _build_canvas_toolbar(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Toolbar.TFrame", padding=(0, 0, 0, 6))
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        toolbar.rowconfigure(0, weight=0)

        action_row = ttk.Frame(toolbar, style="Toolbar.TFrame")
        action_row.grid(row=0, column=0, sticky="ew")
        for column in range(6):
            action_row.columnconfigure(column, weight=1, uniform="toolbar_actions")

        ttk.Button(action_row, text="DB 연결", command=self.connect_data_source, style="Ribbon.TButton").grid(row=0, column=0, padx=(0, 8), pady=(0, 7), sticky="ew")
        ttk.Button(action_row, text="DB 해제", command=self.disconnect_data_source, style="Ribbon.TButton").grid(row=0, column=1, padx=(0, 8), pady=(0, 7), sticky="ew")

        object_menu_button = ttk.Menubutton(action_row, text="개체 추가")
        object_menu = tk.Menu(object_menu_button, tearoff=0)
        for label, command in (
            ("텍스트", lambda: self.add_element("text")),
            ("1D 바코드", lambda: self.add_element("barcode")),
            ("2D 코드", lambda: self.add_barcode_element("qr")),
            ("그림", self.add_image_element),
            ("박스", lambda: self.add_element("box")),
            ("선", lambda: self.add_element("line")),
            ("표", lambda: self.add_element("table")),
        ):
            object_menu.add_command(label=label, command=command)
        object_menu_button.configure(menu=object_menu)
        object_menu_button.grid(row=0, column=2, padx=(0, 8), pady=(0, 7), sticky="ew")

        template_menu_button = ttk.Menubutton(action_row, text="템플릿")
        template_menu = tk.Menu(template_menu_button, tearoff=0)
        template_menu.add_command(label="저장", command=self.save_template)
        template_menu.add_command(label="다른 이름 저장", command=self.save_template_as)
        template_menu.add_command(label="불러오기", command=self.open_template)
        template_menu.add_separator()
        template_menu.add_command(label="미리보기 PNG", command=self.export_preview_png)
        template_menu.add_command(label="템플릿 폴더 열기", command=lambda: self.open_path(self.template_dir))
        template_menu_button.configure(menu=template_menu)
        template_menu_button.grid(row=0, column=3, padx=(0, 8), pady=(0, 7), sticky="ew")

        ttk.Button(action_row, text="인쇄파일 생성", command=lambda: self.run_output_test(send_to_printer=False), style="Ribbon.TButton").grid(row=0, column=4, padx=(0, 8), pady=(0, 7), sticky="ew")
        ttk.Button(action_row, text="인쇄", command=lambda: self.run_output_test(send_to_printer=True), style="Primary.TButton").grid(row=0, column=5, pady=(0, 7), sticky="ew")

        size_row = ttk.Frame(toolbar, style="Toolbar.TFrame")
        size_row.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        size_row.columnconfigure(8, weight=1)
        ttk.Label(size_row, text="라벨").grid(row=0, column=0, padx=(0, 10), sticky="w")
        ttk.Label(size_row, text="가로").grid(row=0, column=1, sticky="e")
        ttk.Spinbox(size_row, textvariable=self.width_var, from_=20, to=120, width=8, command=self.update_label_size).grid(row=0, column=2, padx=(5, 12), sticky="w")
        ttk.Label(size_row, text="세로").grid(row=0, column=3, sticky="e")
        ttk.Spinbox(size_row, textvariable=self.height_var, from_=15, to=120, width=8, command=self.update_label_size).grid(row=0, column=4, padx=(5, 12), sticky="w")
        ttk.Button(size_row, text="크기 적용", command=self.update_label_size, style="Ribbon.TButton").grid(row=0, column=5, padx=(0, 6), sticky="ew")
        ttk.Button(size_row, text="가운데 정렬", command=self.center_selected, style="Ribbon.TButton").grid(row=0, column=6, padx=(0, 6), sticky="ew")
        ttk.Button(size_row, text="기본 템플릿", command=self.reset_template, style="Ribbon.TButton").grid(row=0, column=7, padx=(0, 0), sticky="ew")

    def _build_data_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, minsize=300)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="데이터 소스", style="SidePanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, textvariable=self.data_source_label_var, style="Status.TLabel").grid(row=0, column=0, sticky="e", padx=(0, 8))
        action_row = ttk.Frame(parent, style="SidePanel.TFrame")
        action_row.grid(row=0, column=1, sticky="e")
        ttk.Label(action_row, textvariable=self.record_count_var, style="Status.TLabel").pack(side="left", padx=(0, 8))
        ttk.Button(action_row, text="연결", command=self.connect_data_source, style="Secondary.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(action_row, text="새로고침", command=self.reload_db, style="Secondary.TButton").pack(side="left")

        columns = list(DB_HEADERS)
        self.data_tree = ttk.Treeview(parent, columns=columns, show="headings", height=5, selectmode="extended")
        column_labels = {field: FIELD_LABELS.get(field, field) for field in columns}
        for field in columns:
            self.data_tree.heading(field, text=column_labels[field])
            self.data_tree.column(field, width=118 if field != "item_name" else 210, minwidth=80, stretch=True)
        self.data_tree.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(6, 0))
        self.data_tree.bind("<<TreeviewSelect>>", lambda _event: self.select_data_tree_row())

        queue_panel = ttk.Frame(parent, style="Panel.TFrame")
        queue_panel.grid(row=1, column=1, sticky="nsew", pady=(6, 0))
        queue_panel.columnconfigure(0, weight=1)
        ttk.Label(queue_panel, text="인쇄 대기열", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.queue_tree = ttk.Treeview(queue_panel, columns=("name", "qty", "status"), show="headings", height=4, selectmode="none")
        for field, label, width in (("name", "작업명", 150), ("qty", "수량", 58), ("status", "상태", 70)):
            self.queue_tree.heading(field, text=label)
            self.queue_tree.column(field, width=width, anchor="center" if field != "name" else "w")
        self.queue_tree.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        ttk.Label(queue_panel, textvariable=self.queue_status_var, style="Status.TLabel").grid(row=2, column=0, sticky="w", pady=(6, 0))

    def _build_property_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="속성 패널", style="SidePanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        row = 1
        self._property_combo(parent, row, "종류", self.type_var, [ELEMENT_TYPES[key] for key in VISIBLE_ELEMENT_TYPE_KEYS], state="readonly")
        row += 1
        self._property_combo(parent, row, "코드 종류", self.barcode_type_var, list(BARCODE_TYPES.values()), state="readonly")
        row += 1
        self._property_entry(parent, row, "텍스트", self.text_var)
        row += 1
        self._property_combo(parent, row, "정렬", self.align_var, list(ALIGNMENTS.values()), state="readonly")
        row += 1
        self._property_combo(parent, row, "배치", self.arrange_var, list(ARRANGE_MODES.values()), state="readonly")
        row += 1
        grid = ttk.Frame(parent, style="Panel.TFrame")
        grid.grid(row=row, column=0, sticky="ew", pady=(6, 0))
        for col in range(2):
            grid.columnconfigure(col, weight=1)
        self._small_property(grid, 0, 0, "X(mm)", self.x_var)
        self._small_property(grid, 0, 1, "Y(mm)", self.y_var)
        self._small_property(grid, 2, 0, "W(mm)", self.w_var)
        self._small_property(grid, 2, 1, "H(mm)", self.h_var)
        self._small_property(grid, 4, 0, "글자", self.font_var)
        self._small_property(grid, 4, 1, "행", self.table_rows_var)
        self._small_property(grid, 6, 0, "열", self.table_cols_var)
        ttk.Label(parent, text="글꼴").grid(row=row + 1, column=0, sticky="w", pady=(8, 3))
        ttk.Combobox(parent, textvariable=self.font_name_var, values=self.font_choices, state="readonly").grid(row=row + 2, column=0, sticky="ew")
        ttk.Checkbutton(parent, text="텍스트 반전", variable=self.reverse_var).grid(row=row + 3, column=0, sticky="w", pady=(8, 0))
        ttk.Button(parent, text="속성 적용", command=self.apply_properties, style="Primary.TButton").grid(row=row + 4, column=0, sticky="ew", pady=(10, 4))

    def _property_entry(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row * 2, column=0, sticky="w", pady=(5, 3))
        ttk.Entry(parent, textvariable=variable).grid(row=row * 2 + 1, column=0, sticky="ew")

    def _property_combo(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, values: list[str], state: str = "normal") -> None:
        ttk.Label(parent, text=label).grid(row=row * 2, column=0, sticky="w", pady=(5, 3))
        ttk.Combobox(parent, textvariable=variable, values=values, state=state).grid(row=row * 2 + 1, column=0, sticky="ew")

    def _small_property(self, parent: ttk.Frame, row: int, column: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=(0 if column == 0 else 8, 0), pady=(5, 3))
        ttk.Entry(parent, textvariable=variable, width=10).grid(row=row + 1, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))

    def _load_initial_template(self) -> dict[str, object]:
        if self.template_path.exists():
            try:
                return load_template_file(self.template_path)
            except Exception as exc:
                self._initial_template_error = f"{self.template_path}\n\n{exc}"
        elif self.initial_template_path is not None:
            self._initial_template_error = f"파일을 찾을 수 없습니다.\n\n{self.template_path}"
        try:
            config = load_config(self.config_path)
            return default_template(config.label.width_mm, config.label.height_mm)
        except Exception:
            return default_template()

    def _load_db_rows(self) -> list[dict[str, str]]:
        if self.data_source_path is None:
            return []
        try:
            return load_db_rows(self.data_source_path)
        except Exception:
            return []

    def _data_source_display_name(self) -> str:
        if self.data_source_path is None:
            return "DB 연결 전"
        try:
            return str(self.data_source_path.relative_to(self.base_dir))
        except ValueError:
            return self.data_source_path.name

    def refresh_sample_options(self) -> None:
        values = []
        for index, row in enumerate(self.db_rows, start=1):
            barcode = row.get("barcode", "")
            item = row.get("item_name", "")
            values.append(f"{index}. {barcode} / {item}")
        self.sample_combo_values = values
        if self.sample_combo is not None:
            self.sample_combo.configure(values=values)
        if values:
            selected_index = min(next(iter(self.selected_data_indexes), 0), len(values) - 1)
            self.sample_var.set(values[selected_index])
        else:
            self.sample_var.set("")
        self.refresh_data_panel()

    def _walk_widgets(self, widget: tk.Widget) -> list[tk.Widget]:
        widgets = [widget]
        for child in widget.winfo_children():
            widgets.extend(self._walk_widgets(child))
        return widgets

    def select_sample_row(self) -> None:
        selected = self.sample_var.get()
        try:
            index = int(selected.split(".", 1)[0]) - 1
        except ValueError:
            index = 0
        self._select_data_index(index, update_tree=True)
        self.redraw()

    def _select_data_index(self, index: int, *, update_tree: bool = False) -> None:
        if 0 <= index < len(self.db_rows):
            self.selected_data_indexes = {index}
            self.preview_row = self.db_rows[index]
            if update_tree and self.data_tree is not None:
                iid = str(index)
                if self.data_tree.exists(iid):
                    self.data_tree.selection_set(iid)
                    self.data_tree.see(iid)
        self.refresh_data_panel()

    def connect_data_source(self) -> None:
        source = filedialog.askopenfilename(
            parent=self,
            initialdir=self.base_dir,
            title="DB 연결",
            filetypes=[("Excel workbook", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if not source:
            return
        self.data_source_path = Path(source)
        self.reload_db()
        self.status_var.set(f"DB 연결 완료: {self._data_source_display_name()}")

    def disconnect_data_source(self) -> None:
        self.data_source_path = None
        self.db_rows = []
        self.selected_data_indexes = set()
        self.preview_row = _empty_row()
        self.refresh_sample_options()
        self.redraw()
        self.status_var.set("DB 연결을 해제했습니다.")

    def reload_db(self) -> None:
        if self.data_source_path is None:
            self.disconnect_data_source()
            return
        self.db_rows = self._load_db_rows()
        self.selected_data_indexes = {0} if self.db_rows else set()
        self.preview_row = self.db_rows[0] if self.db_rows else _empty_row()
        self.refresh_sample_options()
        self.redraw()
        self.status_var.set(f"DB 데이터 {len(self.db_rows)}건을 다시 불러왔습니다.")

    def refresh_data_panel(self) -> None:
        self._refreshing_data_panel = True
        connected = self.data_source_path is not None
        if self.data_card is not None:
            if connected:
                self.data_card.grid()
            else:
                self.data_card.grid_remove()
        if hasattr(self, "data_source_label_var"):
            self.data_source_label_var.set(self._data_source_display_name())
        if hasattr(self, "record_count_var"):
            self.record_count_var.set(f"{len(self.db_rows)}건")
        try:
            if self.data_tree is not None:
                previous_selection = {str(index) for index in self.selected_data_indexes}
                self.data_tree.delete(*self.data_tree.get_children())
                for index, row in enumerate(self.db_rows):
                    values = [str(row.get(header, "")) for header in DB_HEADERS]
                    self.data_tree.insert("", "end", iid=str(index), values=values)
                existing = [iid for iid in previous_selection if self.data_tree.exists(iid)]
                if existing:
                    self.data_tree.selection_set(existing)
                elif self.db_rows:
                    self.data_tree.selection_set("0")
            if self.queue_tree is not None:
                self.queue_tree.delete(*self.queue_tree.get_children())
                for index, row in enumerate(self.selected_data_rows()):
                    name = row.get("item_name") or row.get("item_code") or row.get("barcode") or f"작업 {index + 1}"
                    qty = str(row.get("print_qty", "")).strip() or "1"
                    self.queue_tree.insert("", "end", values=(name, qty, "대기"))
            if hasattr(self, "queue_status_var"):
                self.queue_status_var.set(f"선택 {len(self.selected_data_rows())}건 / 전체 {len(self.db_rows)}건")
        finally:
            self._refreshing_data_panel = False

    def select_data_tree_row(self) -> None:
        if self._refreshing_data_panel:
            return
        if self.data_tree is None:
            return
        indexes: set[int] = set()
        for iid in self.data_tree.selection():
            try:
                indexes.add(int(iid))
            except ValueError:
                continue
        if not indexes and self.db_rows:
            indexes = {0}
        if indexes == self.selected_data_indexes:
            return
        self.selected_data_indexes = indexes
        first_index = min(indexes) if indexes else 0
        if 0 <= first_index < len(self.db_rows):
            self.preview_row = self.db_rows[first_index]
            if self.sample_combo_values:
                self.sample_var.set(self.sample_combo_values[first_index])
        self.refresh_data_panel()
        self.redraw()

    def selected_data_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for index in sorted(self.selected_data_indexes):
            if 0 <= index < len(self.db_rows):
                rows.append(self.db_rows[index])
        if rows:
            return rows
        return [self.preview_row] if self.preview_row else [_empty_row()]

    def _load_values_to_controls(self) -> None:
        label = self.template["label"]  # type: ignore[index]
        self.width_var.set(str(label["width_mm"]))  # type: ignore[index]
        self.height_var.set(str(label["height_mm"]))  # type: ignore[index]

    def redraw(self) -> None:
        self.canvas.delete("all")
        self.canvas_images.clear()
        label = self.template["label"]  # type: ignore[index]
        width_mm = float(label["width_mm"])  # type: ignore[index]
        height_mm = float(label["height_mm"])  # type: ignore[index]
        self.scale = self._fit_canvas_scale(width_mm, height_mm)
        width = width_mm * self.scale
        height = height_mm * self.scale
        canvas_width = max(self.canvas.winfo_width(), int(width + DESIGNER_CANVAS_MARGIN))
        canvas_height = max(self.canvas.winfo_height(), int(height + DESIGNER_CANVAS_MARGIN))
        origin_x = max(50, (canvas_width - width) / 2)
        origin_y = max(40, (canvas_height - height) / 2)
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.label_width_px = width
        self.label_height_px = height

        self._draw_rulers(origin_x, origin_y, width, height)
        self.canvas.create_rectangle(
            origin_x + 8,
            origin_y + 8,
            origin_x + width + 8,
            origin_y + height + 8,
            fill=COLORS.border_strong,
            outline="",
        )
        radius = max(8, min(38, min(width, height) * 0.08))
        self._create_round_rect(
            origin_x,
            origin_y,
            origin_x + width,
            origin_y + height,
            radius=radius,
            fill=COLORS.surface_subtle,
            outline=COLORS.border_strong,
            width=1,
        )
        self._draw_grid(origin_x, origin_y, width, height)

        for element in self._drawing_elements():
            self.draw_element(element)

    def _drawing_elements(self) -> list[dict[str, object]]:
        behind = [element for element in self.elements if str(element.get("arrange", "normal")) == "behind"]
        normal = [element for element in self.elements if str(element.get("arrange", "normal")) not in {"behind", "front"}]
        front = [element for element in self.elements if str(element.get("arrange", "normal")) == "front"]
        return behind + normal + front

    def _fit_canvas_scale(self, width_mm: float, height_mm: float) -> float:
        if width_mm <= 0 or height_mm <= 0:
            return DESIGNER_MAX_SCALE
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width = max(800, self.winfo_width() - 320)
            canvas_height = max(520, self.winfo_height() - 180)
        available_width = max(1, canvas_width - DESIGNER_CANVAS_MARGIN)
        available_height = max(1, canvas_height - DESIGNER_CANVAS_MARGIN)
        fit_scale = min(DESIGNER_MAX_SCALE, available_width / width_mm, available_height / height_mm)
        return max(DESIGNER_MIN_SCALE, fit_scale)

    def on_canvas_configure(self, _event: tk.Event) -> None:
        if self._redraw_after_id is not None:
            self.after_cancel(self._redraw_after_id)
        self._redraw_after_id = self.after(60, self._redraw_after_resize)

    def _redraw_after_resize(self) -> None:
        self._redraw_after_id = None
        self.redraw()

    def _draw_grid(self, origin_x: float, origin_y: float, width: float, height: float) -> None:
        step = 5 * self.scale
        x = origin_x + step
        while x < origin_x + width:
            self.canvas.create_line(x, origin_y, x, origin_y + height, fill=COLORS.border)
            x += step
        y = origin_y + step
        while y < origin_y + height:
            self.canvas.create_line(origin_x, y, origin_x + width, y, fill=COLORS.border)
            y += step

    def _draw_rulers(self, origin_x: float, origin_y: float, width: float, height: float) -> None:
        top = origin_y - 28
        left = origin_x - 28
        self.canvas.create_rectangle(origin_x, top, origin_x + width, origin_y - 2, fill=RULER_BG, outline=RULER_OUTLINE)
        self.canvas.create_rectangle(left, origin_y, origin_x - 2, origin_y + height, fill=RULER_BG, outline=RULER_OUTLINE)
        max_x = int(width / self.scale)
        max_y = int(height / self.scale)
        for mm in range(0, max_x + 1):
            x = origin_x + mm * self.scale
            tick = 11 if mm % 10 == 0 else 7 if mm % 5 == 0 else 4
            self.canvas.create_line(x, origin_y - 2, x, origin_y - 2 - tick, fill=COLORS.text_secondary)
            if mm % 10 == 0:
                self.canvas.create_text(x + 2, top + 8, text=str(mm), anchor="nw", fill=COLORS.text_secondary, font=("Malgun Gothic", 7))
        for mm in range(0, max_y + 1):
            y = origin_y + mm * self.scale
            tick = 11 if mm % 10 == 0 else 7 if mm % 5 == 0 else 4
            self.canvas.create_line(origin_x - 2, y, origin_x - 2 - tick, y, fill=COLORS.text_secondary)
            if mm % 10 == 0:
                self.canvas.create_text(left + 4, y + 2, text=str(mm), anchor="nw", fill=COLORS.text_secondary, font=("Malgun Gothic", 7))

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
        selected = element_id == self.selected_id
        outline = SELECT_COLOR if selected else COLORS.border_strong
        tag = f"element:{element_id}"

        if element_type in {"text", "field"}:
            text = render_template_text(str(element.get("text", "")), self.preview_row)
            image = _render_text_box_image(text, max(1, round(x2 - x1)), max(1, round(y2 - y1)), element, transparent=True)
            photo = ImageTk.PhotoImage(image)
            self.canvas_images.append(photo)
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline if selected else "", width=1, tags=(tag,))
            self.canvas.create_image(x1, y1, image=photo, anchor="nw", tags=(tag,))
        elif element_type in {"barcode", "qr"}:
            value = render_template_text(str(element.get("text", "{{barcode}}")), self.preview_row) or self.preview_row.get("barcode", "")
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=1, tags=(tag,))
            if code_type in BARCODE_2D_TYPES:
                self._draw_2d_code_preview(x1, y1, x2, y2, value, code_type, element, tag)
            elif code_type in BARCODE_1D_BITMAP_TYPES:
                self._draw_1d_barcode_preview(x1, y1, x2, y2, value, code_type, element, tag)
            else:
                self._draw_unsupported_barcode_preview(x1 + 5, y1 + 5, x2 - 5, y2 - 5, code_type, tag)
        elif element_type == "box":
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=2, tags=(tag,))
        elif element_type == "line":
            self.canvas.create_line(x1, y1, x2, y2, fill=outline, width=2, tags=(tag,))
        elif element_type == "table":
            self._draw_table_on_canvas(x1, y1, x2, y2, outline, tag, element)
        elif element_type == "image":
            self._draw_image_on_canvas(x1, y1, x2, y2, outline, tag, element)

        if selected:
            self.canvas.create_rectangle(x1 - 3, y1 - 3, x2 + 3, y2 + 3, outline=SELECT_COLOR, width=2)
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
        rows, cols = _table_shape(element)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=2, tags=(tag,))
        for col in range(1, cols):
            x = x1 + ((x2 - x1) * col / cols)
            self.canvas.create_line(x, y1, x, y2, fill=outline, width=1, tags=(tag,))
        for row in range(1, rows):
            y = y1 + ((y2 - y1) * row / rows)
            self.canvas.create_line(x1, y, x2, y, fill=outline, width=1, tags=(tag,))

    def _draw_image_on_canvas(self, x1: float, y1: float, x2: float, y2: float, outline: str, tag: str, element: dict[str, object]) -> None:
        image = self._load_element_image(element, max(1, round(x2 - x1)), max(1, round(y2 - y1)))
        if image is None:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=1, dash=(4, 3), tags=(tag,))
            self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text="그림 없음", fill=COLORS.text_secondary, font=("Malgun Gothic", 9), tags=(tag,))
            return
        photo = ImageTk.PhotoImage(image)
        self.canvas_images.append(photo)
        self.canvas.create_image(x1, y1, image=photo, anchor="nw", tags=(tag,))
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
            image = Image.open(path).convert("RGBA")
        except Exception:
            return None
        image.thumbnail((max(1, width), max(1, height)), Image.Resampling.LANCZOS)
        canvas_image = Image.new("RGBA", (max(1, width), max(1, height)), (255, 255, 255, 0))
        offset = ((canvas_image.width - image.width) // 2, (canvas_image.height - image.height) // 2)
        canvas_image.alpha_composite(image, offset)
        return canvas_image

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

    def _draw_1d_barcode_preview(self, x1: float, y1: float, x2: float, y2: float, value: str, code_type: str, element: dict[str, object], tag: str) -> None:
        width = max(1, round(x2 - x1))
        height = max(1, round(y2 - y1))
        try:
            image = _render_1d_barcode_image(code_type, value, width, height, element)
        except ValueError as exc:
            self._draw_barcode_message(x1, y1, x2, y2, str(exc), tag, fill="#b42318")
            return
        photo = ImageTk.PhotoImage(image.convert("RGBA"))
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
            photo = ImageTk.PhotoImage(image.convert("RGBA"))
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
        defaults = {
            "text": _element("text", "새 텍스트", 5, 5, 22, 5, font_size=10),
            "field": _element("field", "텍스트", 5, 5, 30, 5, field="", font_size=10, align="center"),
            "barcode": _element("barcode", "12345678", 7, 14, 36, 12, field="", font_size=10, align="center"),
            "qr": _element("qr", "12345678", 16, 12, 18, 18, field="", align="center"),
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
        self.status_var.set(f"{ELEMENT_TYPES[element_type]} 요소를 추가했습니다.")

    def add_image_element(self) -> None:
        source = filedialog.askopenfilename(
            parent=self,
            initialdir=self.base_dir,
            title="그림 추가",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"),
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("All files", "*.*"),
            ],
        )
        if not source:
            return
        source_path = Path(source)
        image_dir = self.base_dir / "assets" / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid4().hex[:8]}_{source_path.name}"
        target = image_dir / safe_name
        try:
            shutil.copy2(source_path, target)
            with Image.open(target) as image:
                width, height = image.size
        except Exception as exc:
            messagebox.showerror("그림 추가", f"그림 파일을 불러올 수 없습니다.\n{exc}")
            return
        label = self.template["label"]  # type: ignore[index]
        max_w = max(8.0, float(label["width_mm"]) * 0.55)  # type: ignore[index]
        max_h = max(8.0, float(label["height_mm"]) * 0.45)  # type: ignore[index]
        ratio = width / height if height else 1
        box_w = min(max_w, max(12.0, max_h * ratio))
        box_h = min(max_h, max(8.0, box_w / ratio))
        element = _element("image", source_path.stem, 5, 5, round(box_w, 1), round(box_h, 1), align="center")
        element["image_path"] = str(target.relative_to(self.base_dir))
        self.elements.append(element)
        self.selected_id = str(element["id"])
        self.load_selected_properties()
        self.redraw()
        self._animate_selected_element()
        self.status_var.set("그림을 추가했습니다.")

    def add_barcode_element(self, barcode_type: str = "code128") -> None:
        width = 18 if barcode_type in BARCODE_2D_TYPES else 36
        height = 18 if barcode_type in BARCODE_2D_TYPES else 12
        element = _element(
            "barcode",
            "12345678",
            7 if width > 20 else 16,
            12,
            width,
            height,
            field="",
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
        selected = self.selected_element()
        resize_handle = self.resize_handle_at(event.x, event.y, selected)
        if selected is not None and resize_handle is not None:
            self.drag_state = {
                "mode": "resize",
                "handle": resize_handle,
                "id": str(selected["id"]),
                "start_x": float(event.x),
                "start_y": float(event.y),
                "element_x": float(selected.get("x", 0)),
                "element_y": float(selected.get("y", 0)),
                "element_w": float(selected.get("width", 1)),
                "element_h": float(selected.get("height", 1)),
            }
            return

        element = self.find_element_at(event.x, event.y)
        if element is None:
            self.selected_id = None
            self.clear_property_panel()
            self.redraw()
            return
        self.selected_id = str(element["id"])
        self.drag_state = {
            "mode": "move",
            "id": self.selected_id,
            "start_x": float(event.x),
            "start_y": float(event.y),
            "element_x": float(element.get("x", 0)),
            "element_y": float(element.get("y", 0)),
        }
        self.load_selected_properties()
        self.redraw()

    def on_canvas_drag(self, event: tk.Event) -> None:
        if not self.drag_state:
            return
        element = self.selected_element()
        if element is None:
            return
        dx = (float(event.x) - float(self.drag_state["start_x"])) / self.scale
        dy = (float(event.y) - float(self.drag_state["start_y"])) / self.scale
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
            element["x"] = round(max(0, float(self.drag_state["element_x"]) + dx), 1)
            element["y"] = round(max(0, float(self.drag_state["element_y"]) + dy), 1)
        self.load_selected_properties()
        self.redraw()

    def on_canvas_release(self, _event: tk.Event) -> None:
        self.drag_state = None

    def on_canvas_double_click(self, event: tk.Event) -> None:
        element = self.find_element_at(event.x, event.y)
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
        if widget_class in {"Entry", "TEntry", "TSpinbox", "TCombobox", "Spinbox"}:
            return None
        self.delete_selected()
        return "break"

    def open_element_editor(self, element: dict[str, object] | None = None) -> None:
        element = element or self.selected_element()
        if element is None:
            messagebox.showwarning("요소 편집", "선택된 요소가 없습니다.")
            return

        editor = tk.Toplevel(self)
        editor.title("요소 편집")
        editor.geometry("620x760")
        editor.minsize(560, 640)
        editor.configure(bg=COLORS.surface)
        editor.transient(self)

        frame = ttk.Frame(editor, style="Surface.TFrame", padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        type_var = tk.StringVar(value=ELEMENT_TYPES.get(str(element.get("type")), "텍스트"))
        code_var = tk.StringVar(value=BARCODE_TYPES.get(_barcode_type(element), "Code 128"))
        text_var = tk.StringVar(value=str(element.get("text", "")))
        field_var = tk.StringVar(value=str(element.get("field", "")))
        align_var = tk.StringVar(value=ALIGNMENTS.get(str(element.get("align", "left")), "왼쪽"))
        arrange_var = tk.StringVar(value=ARRANGE_MODES.get(str(element.get("arrange", "normal")), "일반"))
        x_var = tk.StringVar(value=str(element.get("x", 0)))
        y_var = tk.StringVar(value=str(element.get("y", 0)))
        w_var = tk.StringVar(value=str(element.get("width", 1)))
        h_var = tk.StringVar(value=str(element.get("height", 1)))
        font_var = tk.StringVar(value=str(element.get("font_size", 10)))
        font_name_var = tk.StringVar(value=str(element.get("font_name") or DEFAULT_FONT_NAME))
        reverse_var = tk.BooleanVar(value=bool(element.get("reverse", False)))
        table_rows_var = tk.StringVar(value=str(_table_shape(element)[0]))
        table_cols_var = tk.StringVar(value=str(_table_shape(element)[1]))
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
        text_entry = ttk.Entry(frame, textvariable=text_var)
        align_combo = ttk.Combobox(frame, textvariable=align_var, values=list(ALIGNMENTS.values()), state="readonly")
        arrange_combo = ttk.Combobox(frame, textvariable=arrange_var, values=list(ARRANGE_MODES.values()), state="readonly")
        font_combo = ttk.Combobox(frame, textvariable=font_name_var, values=self.font_choices, state="readonly")
        add_row(0, "종류", type_combo)
        add_row(1, "코드 종류", code_combo)
        add_row(2, "텍스트/데이터", text_entry)
        add_row(3, "정렬", align_combo)
        add_row(4, "배치", arrange_combo)
        add_row(5, "글꼴", font_combo)

        numeric = ttk.Frame(frame, style="Surface.TFrame")
        numeric.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for column in range(5):
            numeric.columnconfigure(column, weight=1)
        for column, (label, variable) in enumerate((("X", x_var), ("Y", y_var), ("W", w_var), ("H", h_var), ("글자", font_var))):
            ttk.Label(numeric, text=f"{label}(mm)" if label != "글자" else label).grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else 6, 0))
            ttk.Entry(numeric, textvariable=variable, width=7).grid(row=1, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=(4, 0))
        ttk.Checkbutton(numeric, text="텍스트 반전", variable=reverse_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(numeric, text="행").grid(row=2, column=2, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Entry(numeric, textvariable=table_rows_var, width=7).grid(row=3, column=2, sticky="ew", padx=(6, 0), pady=(4, 0))
        ttk.Label(numeric, text="열").grid(row=2, column=3, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Entry(numeric, textvariable=table_cols_var, width=7).grid(row=3, column=3, sticky="ew", padx=(6, 0), pady=(4, 0))

        barcode_frame = ttk.Frame(frame, style="Surface.TFrame")
        barcode_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(12, 0))
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

        option_entry(1, 0, "X 모듈(0=자동)", module_width_var)
        option_entry(1, 1, "굵은 비율", wide_ratio_var)
        option_entry(1, 2, "Quiet", quiet_zone_var)
        check_combo = ttk.Combobox(barcode_frame, textvariable=check_digit_var, values=list(BARCODE_CHECK_DIGIT_LABELS.values()), state="readonly", width=8)
        ttk.Label(barcode_frame, text="체크디지트").grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(4, 2))
        check_combo.grid(row=2, column=3, sticky="ew", padx=(8, 0))
        option_widgets.append(check_combo)
        hri_check = ttk.Checkbutton(barcode_frame, text="하단 숫자 표시", variable=human_readable_var)
        hri_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        option_widgets.append(hri_check)
        option_entry(4, 0, "셀 크기(네이티브)", cell_size_var)
        qr_ecc_combo = ttk.Combobox(barcode_frame, textvariable=qr_ecc_var, values=["L", "M", "Q", "H"], state="readonly", width=7)
        ttk.Label(barcode_frame, text="QR ECC").grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(4, 2))
        qr_ecc_combo.grid(row=5, column=1, sticky="ew", padx=(8, 0))
        option_widgets.append(qr_ecc_combo)
        option_entry(4, 2, "PDF 행", pdf417_rows_var)
        option_entry(4, 3, "PDF 열", pdf417_columns_var)
        option_entry(6, 0, "PDF 보안", pdf417_security_var)

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
            if element_type == "table":
                element["table_rows"] = max(1, min(20, int(_float_value(table_rows_var.get(), 3))))
                element["table_cols"] = max(1, min(20, int(_float_value(table_cols_var.get(), 3))))
            else:
                element.pop("table_rows", None)
                element.pop("table_cols", None)
            self.selected_id = str(element["id"])
            self.redraw()
            self.status_var.set("편집 내용을 미리보기에 반영했습니다.")
            applying = False

        def on_type_change(*_args: object) -> None:
            sync_code_state()
            apply_live()

        for variable in (
            text_var,
            field_var,
            align_var,
            arrange_var,
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
        sync_code_state()

        buttons = ttk.Frame(frame, style="Surface.TFrame")
        buttons.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        buttons.columnconfigure(0, weight=1)
        close_button = ttk.Button(buttons, text="닫기", command=editor.destroy, style="Primary.TButton")
        close_button.grid(row=0, column=1, sticky="e")

        def on_close() -> None:
            self.load_selected_properties()
            editor.destroy()

        close_button.configure(command=on_close)
        editor.protocol("WM_DELETE_WINDOW", on_close)
        text_entry.focus_set()

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
            self.table_rows_var,
            self.table_cols_var,
        ):
            variable.set("")
        self.reverse_var.set(False)

    def apply_properties(self) -> None:
        element = self.selected_element()
        if element is None:
            messagebox.showwarning("속성 적용", "선택된 요소가 없습니다.")
            return
        reverse_align = {label: key for key, label in ALIGNMENTS.items()}
        reverse_arrange = {label: key for key, label in ARRANGE_MODES.items()}
        element_type = _element_type_from_label(self.type_var.get(), str(element.get("type", "text")))
        element["type"] = element_type
        element["text"] = self.text_var.get()
        element["field"] = self.field_var.get()
        element["align"] = reverse_align.get(self.align_var.get(), str(element.get("align", "left")))
        element["arrange"] = reverse_arrange.get(self.arrange_var.get(), str(element.get("arrange", "normal")))
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
            element["table_rows"] = max(1, min(20, int(_float_value(self.table_rows_var.get(), 3))))
            element["table_cols"] = max(1, min(20, int(_float_value(self.table_cols_var.get(), 3))))
        else:
            element.pop("table_rows", None)
            element.pop("table_cols", None)
        self.redraw()
        self.status_var.set("속성을 적용했습니다.")

    def delete_selected(self) -> None:
        if self.selected_id is None:
            return
        self.elements = [element for element in self.elements if str(element.get("id")) != self.selected_id]
        self.selected_id = None
        self.clear_property_panel()
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
        element = self.selected_element()
        if element is None:
            return
        label = self.template["label"]  # type: ignore[index]
        element["x"] = round((float(label["width_mm"]) - float(element.get("width", 1))) / 2, 1)  # type: ignore[index]
        self.load_selected_properties()
        self.redraw()

    def update_label_size(self) -> None:
        try:
            width = int(float(self.width_var.get()))
            height = int(float(self.height_var.get()))
        except ValueError:
            messagebox.showerror("라벨 크기", "가로/세로를 숫자로 입력하세요.")
            return
        self.template["label"] = {"width_mm": width, "height_mm": height}
        self.redraw()
        self.status_var.set(f"라벨 크기를 {width}x{height}mm로 적용했습니다.")

    def reset_template(self) -> None:
        if not messagebox.askyesno("기본 템플릿", "현재 편집 내용을 기본 템플릿으로 초기화할까요?"):
            return
        width = int(float(self.width_var.get() or 50))
        height = int(float(self.height_var.get() or 40))
        self.template = default_template(width, height)
        self.elements = list(self.template["elements"])  # type: ignore[arg-type]
        self.selected_id = None
        self.redraw()

    def template_payload(self) -> dict[str, object]:
        self.update_label_size()
        return {"version": 1, "label": self.template["label"], "elements": self.elements}

    def save_template(self) -> None:
        try:
            payload = self.template_payload()
            self.template_dir.mkdir(parents=True, exist_ok=True)
            self.template_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("템플릿 저장 실패", str(exc))
            return
        self.status_var.set(f"템플릿 저장 완료: {self.template_path}")

    def save_template_as(self) -> None:
        self.template_dir.mkdir(parents=True, exist_ok=True)
        target = filedialog.asksaveasfilename(
            parent=self,
            initialdir=self.template_dir,
            defaultextension=LABEL_FILE_EXTENSION,
            filetypes=LABEL_FILE_TYPES,
        )
        if not target:
            return
        self.template_path = Path(target)
        if not self.template_path.suffix:
            self.template_path = self.template_path.with_suffix(LABEL_FILE_EXTENSION)
        self.title(self._window_title())
        self.save_template()

    def open_template(self) -> None:
        self.template_dir.mkdir(parents=True, exist_ok=True)
        source = filedialog.askopenfilename(parent=self, initialdir=self.template_dir, filetypes=LABEL_FILE_TYPES)
        if not source:
            return
        try:
            self.open_template_path(Path(source))
        except Exception as exc:
            messagebox.showerror("템플릿 불러오기 실패", str(exc))
            return

    def open_template_path(self, source: Path) -> None:
        self.template_path = source.resolve()
        self.template = load_template_file(self.template_path)
        self.elements = list(self.template["elements"])  # type: ignore[arg-type]
        self.selected_id = None
        self.title(self._window_title())
        self._load_values_to_controls()
        self.redraw()
        self.status_var.set(f"라벨 파일을 불러왔습니다: {self.template_path}")

    def export_preview_png(self) -> None:
        out_dir = self.base_dir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "designer_preview.png"
        image = self.render_preview_image()
        image.save(path)
        self.status_var.set(f"미리보기 저장 완료: {path}")

    def run_output_test(self, send_to_printer: bool) -> None:
        print_qty = self.ask_print_quantity() if send_to_printer else 1
        if print_qty is None:
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
            output_files: list[Path] = []
            sent_count = 0
            source_rows = self.selected_data_rows()
            if send_to_printer and len(source_rows) > 1:
                if not messagebox.askyesno("인쇄 확인", f"선택된 데이터 {len(source_rows)}건을 프린터로 보낼까요?"):
                    return
            for index, source_row in enumerate(source_rows, start=1):
                row_print_qty = print_qty if send_to_printer else max(1, min(100, int(_float_value(str(source_row.get("print_qty", "1")), 1))))
                row = self._output_test_row(row_print_qty, source_row=source_row)
                command_payload = self.render_designer_print_command(config, row, row_print_qty)
                output_file = self._write_designer_command_file(config, out_dir, command_payload, index=index)
                output_files.append(output_file)
                if send_to_printer:
                    self._send_designer_print(config, command_payload)
                    sent_count += 1
            returncode = 0
            stdout = "designer command written to " + ", ".join(str(path) for path in output_files)
            if send_to_printer:
                stdout += f"\nprint jobs sent: {sent_count}"
            stderr = ""
        except Exception as exc:
            messagebox.showerror("인쇄 실패", str(exc))
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
                "인쇄 실패",
                f"{(stderr or stdout or '알 수 없는 오류').strip()}\n\n"
                f"현재 설정: {config_summary}\n"
                f"로그: {log_path}",
            )
            return
        mode_text = "인쇄 명령을 프린터로 보냈습니다." if send_to_printer else "인쇄 파일을 생성했습니다."
        self.status_var.set(f"{mode_text} {len(output_files)}건 / 출력 폴더: {out_dir}")
        if send_to_printer:
            messagebox.showinfo("인쇄 완료", "인쇄 완료")
        else:
            messagebox.showinfo("인쇄 파일 생성", f"인쇄 파일 생성 완료: {len(output_files)}건")

    def ask_print_quantity(self) -> int | None:
        initial = int(_float_value(str(self.preview_row.get("print_qty", "1")), 1))
        initial = max(1, min(100, initial))
        result: dict[str, int | None] = {"value": None}
        dialog = tk.Toplevel(self)
        dialog.title("인쇄 수량")
        dialog.geometry("390x240")
        dialog.minsize(390, 240)
        dialog.resizable(False, False)
        dialog.configure(bg=COLORS.surface)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, style="Surface.TFrame", padding=22)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="인쇄 수량", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        qty_var = tk.IntVar(value=initial)
        quantity_row = ttk.Frame(frame, style="Surface.TFrame")
        quantity_row.grid(row=1, column=0, sticky="ew", pady=(14, 12))
        quantity_row.columnconfigure(0, weight=1)
        qty_entry = ttk.Entry(quantity_row, textvariable=qty_var, justify="right", font=("Segoe UI", 22, "bold"))
        qty_entry.grid(row=0, column=0, rowspan=2, sticky="nsew", ipady=12, padx=(0, 10))

        def adjust(delta: int) -> None:
            value = int(_float_value(qty_var.get(), initial))
            qty_var.set(max(1, min(100, value + delta)))

        arrow_font = ("Segoe UI", 18, "bold")
        tk.Button(
            quantity_row,
            text="▲",
            command=lambda: adjust(1),
            font=arrow_font,
            width=5,
            height=1,
            bg=COLORS.surface_muted,
            fg=COLORS.text_primary,
            relief="solid",
            bd=1,
        ).grid(row=0, column=1, sticky="nsew")
        tk.Button(
            quantity_row,
            text="▼",
            command=lambda: adjust(-1),
            font=arrow_font,
            width=5,
            height=1,
            bg=COLORS.surface_muted,
            fg=COLORS.text_primary,
            relief="solid",
            bd=1,
        ).grid(row=1, column=1, sticky="nsew", pady=(6, 0))

        buttons = ttk.Frame(frame, style="Surface.TFrame")
        buttons.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        buttons.columnconfigure(0, weight=1)

        def confirm() -> None:
            value = max(1, min(100, int(_float_value(qty_var.get(), initial))))
            result["value"] = value
            dialog.destroy()

        def cancel() -> None:
            result["value"] = None
            dialog.destroy()

        ttk.Button(buttons, text="취소", command=cancel, style="Secondary.TButton").grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="인쇄", command=confirm, style="Primary.TButton").grid(row=0, column=2)
        dialog.bind("<Return>", lambda _event: confirm())
        dialog.bind("<Escape>", lambda _event: cancel())
        qty_entry.focus_set()
        qty_entry.select_range(0, "end")
        self.wait_window(dialog)
        return result["value"]

    def _output_test_row(self, print_qty: int = 1, *, source_row: dict[str, str] | None = None) -> dict[str, str]:
        source = source_row or self.preview_row
        row = {header: str(source.get(header, "")).strip() for header in LABEL_HEADERS}
        row["barcode"] = row.get("barcode") or "1234567890"
        row["item_code"] = row.get("item_code") or "TEST-ITEM"
        row["item_name"] = row.get("item_name") or "TEST LABEL"
        row["lot_no"] = row.get("lot_no") or "LOT-TEST"
        row["qty"] = row.get("qty") or "1"
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
            f"SL{height_dot},{gap_dot},G\r\n".encode("ascii"),
            b"SOT\r\n",
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
            self._zpl_print_method_command(config.printer.print_method),  # type: ignore[attr-defined]
            self._zpl_media_handling_command(str(getattr(config.printer, "media_handling", "tear_off"))),  # type: ignore[attr-defined]
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
            f"GAP {float(config.label.gap_mm):g} mm,0 mm\n"  # type: ignore[attr-defined]
            f"{self._tspl_codepage_command(config.printer.command_encoding)}"  # type: ignore[attr-defined]
            f"DENSITY {config.printer.print_density}\n"  # type: ignore[attr-defined]
            f"SPEED {config.printer.print_speed}\n"  # type: ignore[attr-defined]
            f"{self._tspl_print_method_command(config.printer.print_method)}"  # type: ignore[attr-defined]
            f"{self._tspl_media_handling_command(str(getattr(config.printer, 'media_handling', 'tear_off')))}"  # type: ignore[attr-defined]
            "DIRECTION 1\n"
            "REFERENCE 0,0\n"
            "CLS\n"
        ).encode("ascii")
        commands: list[bytes] = [header]
        for element in self._drawing_elements():
            commands.append(self._render_tspl_element(element, row, dpi, width_dot, height_dot, config))
        commands.append(f"PRINT 1,{print_qty}\n".encode("ascii"))
        return b"".join(command for command in commands if command)

    def _render_tspl_element(self, element: dict[str, object], row: dict[str, str], dpi: int, width_dot: int, height_dot: int, config: object) -> bytes:
        x, y, w, h = self._element_dot_box(element, dpi, width_dot, height_dot)
        element_type = str(element.get("type", "text"))
        if element_type in {"text", "field"}:
            text = render_template_text(str(element.get("text", "")), row)
            return self._tspl_text_bitmap_command(x, y, w, h, text, element)
        if element_type in {"barcode", "qr"}:
            value = render_template_text(str(element.get("text", "12345678")), row) or row.get("barcode", "12345678")
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            return self._tspl_barcode_command(x, y, w, h, value, code_type, config, element)
        if element_type == "box":
            return f"BOX {x},{y},{x + w},{y + h},2\n".encode("ascii")
        if element_type == "line":
            thickness = max(1, min(8, h if h > 1 else 2))
            return f"BAR {x},{y},{max(1, w)},{thickness}\n".encode("ascii")
        if element_type == "table":
            return self._tspl_table_command(x, y, w, h, element)
        if element_type == "image":
            image = self._load_element_image(element, w, h)
            return self._tspl_bitmap_command(x, y, image) if image is not None else b""
        return b""

    def _render_slcs_element(self, element: dict[str, object], row: dict[str, str], dpi: int, width_dot: int, height_dot: int, config: object) -> bytes:
        x, y, w, h = self._element_dot_box(element, dpi, width_dot, height_dot)
        element_type = str(element.get("type", "text"))
        if element_type in {"text", "field"}:
            text = render_template_text(str(element.get("text", "")), row)
            if not text:
                return b""
            return self._slcs_text_bitmap_command(x, y, w, h, text, element)
        if element_type in {"barcode", "qr"}:
            value = render_template_text(str(element.get("text", "12345678")), row) or row.get("barcode", "12345678")
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            return self._slcs_barcode_command(x, y, w, h, value, code_type, config, element)
        if element_type == "box":
            return self._slcs_box_command(x, y, w, h)
        if element_type == "line":
            return self._slcs_line_command(x, y, w, h)
        if element_type == "table":
            return self._slcs_table_command(x, y, w, h, element)
        if element_type == "image":
            image = self._load_element_image(element, w, h)
            return self._slcs_bitmap_command(x, y, image) if image is not None else b""
        return b""

    def _render_zpl_element(self, element: dict[str, object], row: dict[str, str], dpi: int, width_dot: int, height_dot: int, config: object) -> str:
        x, y, w, h = self._element_dot_box(element, dpi, width_dot, height_dot)
        element_type = str(element.get("type", "text"))
        if element_type in {"text", "field"}:
            text = self._zpl_escape(sanitize_zpl_text(render_template_text(str(element.get("text", "")), row)))
            if not text:
                return ""
            if bool(element.get("reverse", False)):
                image = _render_text_box_image(text, max(1, w), max(1, h), element, transparent=False)
                return self._zpl_bitmap_command(x, y, image)
            font_size = max(10, min(180, h))
            align = self._zpl_align(str(element.get("align", "left")))
            return f"^FO{x},{y}^FB{w},1,0,{align},0^A0N,{font_size},{font_size}^FD{text}^FS\n"
        if element_type in {"barcode", "qr"}:
            value = render_template_text(str(element.get("text", "12345678")), row) or row.get("barcode", "12345678")
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            return self._zpl_barcode_command(x, y, w, h, value, code_type, config, element)
        if element_type == "box":
            return f"^FO{x},{y}^GB{w},{h},2^FS\n"
        if element_type == "line":
            thickness = max(1, min(8, h if h > 1 else 2))
            return f"^FO{x},{y}^GB{max(1, w)},{thickness},{thickness}^FS\n"
        if element_type == "table":
            return self._zpl_table_command(x, y, w, h, element)
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
        reverse = bool(element.get("reverse", False))
        image = Image.new("1", (max(1, width), max(1, height)), 0 if reverse else 1)
        draw = ImageDraw.Draw(image)
        requested = max(int(float(element.get("font_size", 10)) * 1.5), int(height * 0.72))
        font = _fit_font_to_box(text, width - 4, height - 4, requested, str(element.get("font_name") or DEFAULT_FONT_NAME))
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        align = str(element.get("align", "left"))
        if align == "center":
            text_x = max(2, (width - text_w) // 2)
        elif align == "right":
            text_x = max(2, width - text_w - 2)
        else:
            text_x = 2
        text_y = max(0, (height - text_h) // 2 - bbox[1])
        draw.text((text_x - bbox[0], text_y), text, fill=1 if reverse else 0, font=font)
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
        if media_handling == "cutter":
            return "SET CUTTER 1\nSET PEEL OFF\nSET TEAR OFF\n"
        if media_handling == "peeler":
            return "SET CUTTER OFF\nSET PEEL ON\nSET TEAR OFF\n"
        return "SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n"

    def _slcs_print_method_command(self, print_method: str) -> str:
        if print_method == "thermal_transfer":
            return "STt\n"
        return "STd\n"

    def _slcs_media_handling_command(self, media_handling: str) -> str:
        if media_handling == "cutter":
            return "CUTy\n"
        return "CUTn\n"

    def _zpl_print_method_command(self, print_method: str) -> str:
        if print_method == "thermal_transfer":
            return "^MTT\n"
        return "^MTD\n"

    def _zpl_media_handling_command(self, media_handling: str) -> str:
        if media_handling == "cutter":
            return "^MMC\n"
        if media_handling == "peeler":
            return "^MMP\n"
        return "^MMT\n"

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

    def _slcs_box_command(self, x: int, y: int, width: int, height: int) -> bytes:
        thickness = 2
        return f"BD{x},{y},{x + width},{y + height},B,{thickness}\r\n".encode("ascii")

    def _slcs_line_command(self, x: int, y: int, width: int, height: int) -> bytes:
        thickness = max(1, min(8, height if height > 1 else 2))
        return f"BD{x},{y},{x + max(1, width)},{y},S,{thickness}\r\n".encode("ascii")

    def _tspl_table_command(self, x: int, y: int, width: int, height: int, element: dict[str, object]) -> bytes:
        rows, cols = _table_shape(element)
        parts = [f"BOX {x},{y},{x + width},{y + height},2\n"]
        for col in range(1, cols):
            line_x = x + round(width * col / cols)
            parts.append(f"BAR {line_x},{y},2,{height}\n")
        for row in range(1, rows):
            line_y = y + round(height * row / rows)
            parts.append(f"BAR {x},{line_y},{width},2\n")
        return "".join(parts).encode("ascii")

    def _slcs_table_command(self, x: int, y: int, width: int, height: int, element: dict[str, object]) -> bytes:
        rows, cols = _table_shape(element)
        parts = [self._slcs_box_command(x, y, width, height)]
        for col in range(1, cols):
            line_x = x + round(width * col / cols)
            parts.append(f"BD{line_x},{y},{line_x},{y + height},S,2\r\n".encode("ascii"))
        for row in range(1, rows):
            line_y = y + round(height * row / rows)
            parts.append(f"BD{x},{line_y},{x + width},{line_y},S,2\r\n".encode("ascii"))
        return b"".join(parts)

    def _zpl_table_command(self, x: int, y: int, width: int, height: int, element: dict[str, object]) -> str:
        rows, cols = _table_shape(element)
        parts = [f"^FO{x},{y}^GB{width},{height},2^FS\n"]
        for col in range(1, cols):
            line_x = x + round(width * col / cols)
            parts.append(f"^FO{line_x},{y}^GB2,{height},2^FS\n")
        for row in range(1, rows):
            line_y = y + round(height * row / rows)
            parts.append(f"^FO{x},{line_y}^GB{width},2,2^FS\n")
        return "".join(parts)

    def _zpl_align(self, align: str) -> str:
        return {"left": "L", "center": "C", "right": "R"}.get(align, "L")

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
        x1 = float(element.get("x", 0)) * scale
        y1 = float(element.get("y", 0)) * scale
        x2 = x1 + float(element.get("width", 1)) * scale
        y2 = y1 + float(element.get("height", 1)) * scale
        element_type = str(element.get("type", "text"))
        if element_type in {"text", "field"}:
            text = render_template_text(str(element.get("text", "")), self.preview_row)
            text_image = _render_text_box_image(text, max(1, round(x2 - x1)), max(1, round(y2 - y1)), element, transparent=False).convert("L")
            text_mask = ImageChops.invert(text_image).convert("1")
            draw.bitmap((x1, y1), text_mask, fill="#111820")
        elif element_type in {"barcode", "qr"}:
            draw.rectangle((x1, y1, x2, y2), outline="#111820", width=1)
            value = render_template_text(str(element.get("text", "{{barcode}}")), self.preview_row)
            code_type = "qr" if element_type == "qr" else _barcode_type(element)
            if code_type in BARCODE_2D_TYPES:
                if code_type in BARCODE_2D_BITMAP_TYPES:
                    try:
                        barcode_image = _render_2d_barcode_image(code_type, value, max(1, round(x2 - x1)), max(1, round(y2 - y1)), element)
                        image.paste(barcode_image.convert("RGB"), (round(x1), round(y1)))
                    except ValueError as exc:
                        draw.text((x1 + 4, y1 + 4), str(exc), fill="#b42318", font=_load_font(10))
                else:
                    draw.text((x1 + 4, y1 + 4), f"{BARCODE_TYPES.get(code_type, code_type)} 준비 중", fill="#8a4b00", font=_load_font(10))
            elif code_type in BARCODE_1D_BITMAP_TYPES:
                try:
                    barcode_image = _render_1d_barcode_image(code_type, value, max(1, round(x2 - x1)), max(1, round(y2 - y1)), element)
                    image.paste(barcode_image.convert("RGB"), (round(x1), round(y1)))
                except ValueError as exc:
                    draw.text((x1 + 4, y1 + 4), str(exc), fill="#b42318", font=_load_font(10))
            else:
                draw.text((x1 + 4, y1 + 4), f"{BARCODE_TYPES.get(code_type, code_type)} 준비 중", fill="#8a4b00", font=_load_font(10))
        elif element_type == "box":
            draw.rectangle((x1, y1, x2, y2), outline="#111820", width=2)
        elif element_type == "line":
            draw.line((x1, y1, x2, y2), fill="#111820", width=2)
        elif element_type == "table":
            rows, cols = _table_shape(element)
            draw.rectangle((x1, y1, x2, y2), outline="#111820", width=2)
            for col in range(1, cols):
                x = x1 + ((x2 - x1) * col / cols)
                draw.line((x, y1, x, y2), fill="#111820", width=1)
            for row in range(1, rows):
                y = y1 + ((y2 - y1) * row / rows)
                draw.line((x1, y, x2, y), fill="#111820", width=1)
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


def _empty_row() -> dict[str, str]:
    return {field: "" for field in DB_HEADERS}


def _table_shape(element: dict[str, object]) -> tuple[int, int]:
    rows = max(1, min(20, int(_float_value(element.get("table_rows"), 3))))
    cols = max(1, min(20, int(_float_value(element.get("table_cols"), 3))))
    return rows, cols


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
    requested = max(int(float(element.get("font_size", 10)) * 1.5), int(height * 0.72))
    font = _fit_font_to_box(text, width - 4, height - 4, requested, str(element.get("font_name") or DEFAULT_FONT_NAME))
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    align = str(element.get("align", "left"))
    if align == "center":
        text_x = max(2, (width - text_w) // 2)
    elif align == "right":
        text_x = max(2, width - text_w - 2)
    else:
        text_x = 2
    text_y = max(0, (height - text_h) // 2 - bbox[1])
    draw.text((text_x - bbox[0], text_y), text, fill=fill, font=font)
    return image


def _fit_font_to_box(text: str, max_width: int, max_height: int, requested_size: int, font_name: str = DEFAULT_FONT_NAME) -> ImageFont.ImageFont:
    size = max(8, requested_size)
    while size >= 8:
        font = _load_font(size, font_name)
        probe = Image.new("L", (1, 1), 255)
        bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max(1, max_width) and bbox[3] - bbox[1] <= max(1, max_height):
            return font
        size -= 2
    return _load_font(8, font_name)


def _load_font(size: int, font_name: str = DEFAULT_FONT_NAME) -> ImageFont.ImageFont:
    registry = _font_registry()
    candidates = [
        registry.get(_font_key(font_name)),
        registry.get(_font_key(DEFAULT_FONT_NAME)),
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for font_path in candidates:
        if font_path is not None and font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except (OSError, ValueError):
                continue
    return ImageFont.load_default()


def _available_font_names() -> list[str]:
    registry = _font_registry()
    names = sorted({name for name in registry if name})
    preferred = [name for name in (DEFAULT_FONT_NAME, "Arial", "Consolas") if name in names]
    others = [name for name in names if name not in preferred]
    return preferred + others


def _font_registry() -> dict[str, Path]:
    global _FONT_REGISTRY_CACHE
    if _FONT_REGISTRY_CACHE is not None:
        return _FONT_REGISTRY_CACHE
    fonts_dir = Path("C:/Windows/Fonts")
    registry: dict[str, Path] = {}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
            index = 0
            while True:
                try:
                    value_name, file_name, _value_type = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                font_path = Path(str(file_name))
                if not font_path.is_absolute():
                    font_path = fonts_dir / font_path
                if not font_path.exists():
                    continue
                display = value_name.split("(", 1)[0].strip()
                for suffix in ("Regular", "보통", "Normal"):
                    if display.endswith(" " + suffix):
                        display = display[: -len(suffix) - 1]
                if not _is_usable_font_choice(display, font_path):
                    continue
                registry.setdefault(display, font_path)
    except OSError:
        pass
    for fallback_name, fallback_path in {
        DEFAULT_FONT_NAME: fonts_dir / "malgun.ttf",
        "Arial": fonts_dir / "arial.ttf",
        "Consolas": fonts_dir / "consola.ttf",
    }.items():
        if fallback_path.exists():
            registry.setdefault(fallback_name, fallback_path)
    _FONT_REGISTRY_CACHE = registry
    return registry


def _font_key(font_name: str) -> str:
    registry = _font_registry()
    if font_name in registry:
        return font_name
    normalized = font_name.strip().lower().replace(" ", "")
    for name in registry:
        if name.strip().lower().replace(" ", "") == normalized:
            return name
    return font_name


def _is_usable_font_choice(display_name: str, font_path: Path) -> bool:
    if font_path.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
        return False
    lowered = display_name.lower()
    blocked = ("symbol", "wingdings", "webdings", "marlett", "emoji", "icons", "assets", "eudc")
    if any(word in lowered for word in blocked):
        return False
    if not _font_has_hangul(font_path):
        return False
    try:
        font = ImageFont.truetype(str(font_path), size=16)
        probe = Image.new("L", (260, 48), 255)
        draw = ImageDraw.Draw(probe)
        draw.text((2, 2), "한글 ABC 123", fill=0, font=font)
        return ImageChops.invert(probe).getbbox() is not None
    except (OSError, ValueError):
        return False


def _font_has_hangul(font_path: Path) -> bool:
    try:
        data = font_path.read_bytes()
    except OSError:
        return False
    for codepoint in (0xAC00, 0xB098, 0xD55C):
        if _font_data_contains_codepoint(data, codepoint):
            return True
    return False


def _font_data_contains_codepoint(data: bytes, codepoint: int) -> bool:
    if data[:4] == b"ttcf":
        if len(data) < 12:
            return False
        count = struct.unpack_from(">L", data, 8)[0]
        for index in range(count):
            offset_pos = 12 + (index * 4)
            if offset_pos + 4 <= len(data):
                font_offset = struct.unpack_from(">L", data, offset_pos)[0]
                if _sfnt_contains_codepoint(data, font_offset, codepoint):
                    return True
        return False
    return _sfnt_contains_codepoint(data, 0, codepoint)


def _sfnt_contains_codepoint(data: bytes, sfnt_offset: int, codepoint: int) -> bool:
    if sfnt_offset + 12 > len(data):
        return False
    table_count = struct.unpack_from(">H", data, sfnt_offset + 4)[0]
    cmap_offset = None
    cmap_length = None
    table_base = sfnt_offset + 12
    for index in range(table_count):
        record = table_base + (index * 16)
        if record + 16 > len(data):
            return False
        tag = data[record : record + 4]
        if tag == b"cmap":
            cmap_offset = struct.unpack_from(">L", data, record + 8)[0]
            cmap_length = struct.unpack_from(">L", data, record + 12)[0]
            break
    if cmap_offset is None or cmap_length is None or cmap_offset + cmap_length > len(data):
        return False
    if cmap_offset + 4 > len(data):
        return False
    subtable_count = struct.unpack_from(">H", data, cmap_offset + 2)[0]
    for index in range(subtable_count):
        record = cmap_offset + 4 + (index * 8)
        if record + 8 > len(data):
            continue
        subtable_offset = cmap_offset + struct.unpack_from(">L", data, record + 4)[0]
        if _cmap_subtable_contains_codepoint(data, subtable_offset, codepoint):
            return True
    return False


def _cmap_subtable_contains_codepoint(data: bytes, offset: int, codepoint: int) -> bool:
    if offset + 2 > len(data):
        return False
    fmt = struct.unpack_from(">H", data, offset)[0]
    if fmt == 4 and codepoint <= 0xFFFF:
        return _cmap_format4_contains_codepoint(data, offset, codepoint)
    if fmt in {12, 13}:
        return _cmap_format12_contains_codepoint(data, offset, codepoint)
    return False


def _cmap_format4_contains_codepoint(data: bytes, offset: int, codepoint: int) -> bool:
    if offset + 16 > len(data):
        return False
    length = struct.unpack_from(">H", data, offset + 2)[0]
    if offset + length > len(data):
        return False
    seg_count = struct.unpack_from(">H", data, offset + 6)[0] // 2
    end_codes = offset + 14
    start_codes = end_codes + (seg_count * 2) + 2
    id_deltas = start_codes + (seg_count * 2)
    id_range_offsets = id_deltas + (seg_count * 2)
    for index in range(seg_count):
        end_code = struct.unpack_from(">H", data, end_codes + (index * 2))[0]
        start_code = struct.unpack_from(">H", data, start_codes + (index * 2))[0]
        if start_code <= codepoint <= end_code:
            range_offset = struct.unpack_from(">H", data, id_range_offsets + (index * 2))[0]
            if range_offset == 0:
                delta = struct.unpack_from(">h", data, id_deltas + (index * 2))[0]
                return ((codepoint + delta) & 0xFFFF) != 0
            glyph_pos = id_range_offsets + (index * 2) + range_offset + ((codepoint - start_code) * 2)
            if glyph_pos + 2 > offset + length:
                return False
            return struct.unpack_from(">H", data, glyph_pos)[0] != 0
    return False


def _cmap_format12_contains_codepoint(data: bytes, offset: int, codepoint: int) -> bool:
    if offset + 16 > len(data):
        return False
    length = struct.unpack_from(">L", data, offset + 4)[0]
    if offset + length > len(data):
        return False
    group_count = struct.unpack_from(">L", data, offset + 12)[0]
    groups_offset = offset + 16
    for index in range(group_count):
        group = groups_offset + (index * 12)
        if group + 12 > offset + length:
            return False
        start_char, end_char, start_glyph = struct.unpack_from(">LLL", data, group)
        if start_char <= codepoint <= end_char:
            return start_glyph + (codepoint - start_char) != 0
    return False


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visual label template designer.")
    parser.add_argument("label_file", nargs="?", help="Saved .gblabel or .json label file to open")
    parser.add_argument("--base-dir", default=None, help="Folder containing config.ini and barcode_db.xlsx")
    parser.add_argument("--print", dest="print_on_open", action="store_true", help="Open the label file and show the print flow")
    parser.add_argument("--smoke-test", action="store_true", help="Load template and data source without showing the UI")
    args = parser.parse_args(argv)
    base_dir = Path(args.base_dir).resolve() if args.base_dir else app_base_dir()
    label_file = Path(args.label_file).resolve() if args.label_file else None
    if args.print_on_open and label_file is None:
        parser.error("--print requires a label_file")
    if args.smoke_test:
        if label_file is not None:
            load_template_file(label_file)
        else:
            template_dir = base_dir / "templates"
            template_dir.mkdir(parents=True, exist_ok=True)
            template_path = template_dir / "default_label.json"
            if not template_path.exists():
                template_path.write_text(json.dumps(default_template(), ensure_ascii=False, indent=2), encoding="utf-8")
            load_template_file(template_path)
        load_db_rows(base_dir / "barcode_db.xlsx")
        return 0
    app = LabelDesignerApp(base_dir, initial_template_path=label_file, print_on_open=args.print_on_open)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
