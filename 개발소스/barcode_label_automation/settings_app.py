from __future__ import annotations

import argparse
import socket
import sys
import tkinter as tk
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from .config import DEFAULTS, SUPPORTED_BARCODE_TYPES, SUPPORTED_MEDIA_HANDLING, SUPPORTED_PRINT_METHODS
from .ui_tokens import COLORS, SPACING, TYPOGRAPHY


BRAND_LABELS = {
    "bixolon": "BIXOLON / \ube45\uc194\ub860",
    "tsc": "TSC",
    "zebra": "Zebra / \uc81c\ube0c\ub77c",
}
MODE_LABELS = {
    "network": "LAN / \ub124\ud2b8\uc6cc\ud06c",
    "windows_raw": "USB / Windows \ud504\ub9b0\ud130",
}
PRINT_METHOD_LABELS = {
    "direct_thermal": "\uac10\uc5f4 / \ub9ac\ubcf8 \uc5c6\uc74c",
    "thermal_transfer": "\uc5f4\uc804\uc0ac / \ub9ac\ubcf8 \uc0ac\uc6a9",
}
MEDIA_HANDLING_LABELS = {
    "tear_off": "뜯어내기",
    "cutter": "커터",
    "peeler": "필러",
}
BARCODE_TYPE_LABELS = {
    "code128": "1D - Code128",
    "code39": "1D - Code39",
    "ean13": "1D - EAN13",
    "ean8": "1D - EAN8",
    "upca": "1D - UPC-A",
    "itf": "1D - ITF",
    "qr": "2D - QR Code",
    "datamatrix": "2D - DataMatrix",
    "pdf417": "2D - PDF417",
}
BRAND_VALUES = {label: value for value, label in BRAND_LABELS.items()}
MODE_VALUES = {label: value for value, label in MODE_LABELS.items()}
PRINT_METHOD_VALUES = {label: value for value, label in PRINT_METHOD_LABELS.items()}
MEDIA_HANDLING_VALUES = {label: value for value, label in MEDIA_HANDLING_LABELS.items()}
BARCODE_TYPE_VALUES = {label: value for value, label in BARCODE_TYPE_LABELS.items()}


@dataclass(frozen=True)
class PrinterSettings:
    brand: str
    mode: str
    print_method: str
    ip: str
    port: int
    windows_printer_name: str
    width_mm: int
    height_mm: int
    dpi: int
    gap_mm: float
    media_handling: str = "tear_off"
    print_speed: int = 4
    print_density: int = 8
    barcode_type: str = "code128"
    barcode_auto_layout: bool = True
    barcode_x: int = 130
    barcode_y: int = 115
    barcode_rotation: int = 0
    one_d_height: int = 80
    one_d_narrow: int = 2
    one_d_wide: int = 2
    one_d_human_readable: bool = True
    qr_model: int = 2
    qr_ecc: str = "M"
    qr_cell_size: int = 4
    datamatrix_cell_size: int = 4
    pdf417_rows: int = 30
    pdf417_columns: int = 5
    pdf417_security_level: int = 2
    pdf417_module_width: int = 3
    pdf417_module_height: int = 10


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def config_path_for_app() -> Path:
    return app_base_dir() / "config.ini"


def load_settings(path: str | Path) -> PrinterSettings:
    config_path = Path(path)
    parser = _read_parser(config_path)
    brand = parser.get("printer", "brand", fallback="bixolon").strip().lower()
    mode = parser.get("printer", "mode", fallback="network").strip().lower()
    print_method = parser.get("printer", "print_method", fallback="direct_thermal").strip().lower()
    media_handling = parser.get("printer", "media_handling", fallback="tear_off").strip().lower()
    print_speed = _read_setting_print_tuning(parser, "speed", brand, {"bixolon": 3, "tsc": 4, "zebra": 4}, 1, 20)
    print_density = _read_setting_print_tuning(parser, "density", brand, {"bixolon": 20, "tsc": 8, "zebra": 10}, 0, 30)
    barcode_type = parser.get("barcode", "type", fallback="code128").strip().lower()
    if barcode_type == "qrcode":
        barcode_type = "qr"
    if barcode_type in {"data_matrix", "dmatrix", "dm"}:
        barcode_type = "datamatrix"
    return PrinterSettings(
        brand=brand if brand in BRAND_LABELS else "bixolon",
        mode=mode if mode in MODE_LABELS else "network",
        print_method=print_method if print_method in SUPPORTED_PRINT_METHODS else "direct_thermal",
        media_handling=media_handling if media_handling in SUPPORTED_MEDIA_HANDLING else "tear_off",
        ip=parser.get("printer", "ip", fallback="192.168.0.50").strip(),
        port=parser.getint("printer", "port", fallback=9100),
        windows_printer_name=parser.get("printer", "windows_printer_name", fallback="auto").strip(),
        width_mm=parser.getint("label", "width_mm", fallback=50),
        height_mm=parser.getint("label", "height_mm", fallback=30),
        dpi=parser.getint("label", "dpi", fallback=203),
        gap_mm=parser.getfloat("label", "gap_mm", fallback=3),
        print_speed=print_speed,
        print_density=print_density,
        barcode_type=barcode_type if barcode_type in SUPPORTED_BARCODE_TYPES else "code128",
        barcode_auto_layout=parser.getboolean("barcode", "auto_layout", fallback=True),
        barcode_x=parser.getint("barcode", "x", fallback=130),
        barcode_y=parser.getint("barcode", "y", fallback=115),
        barcode_rotation=parser.getint("barcode", "rotation", fallback=0),
        one_d_height=parser.getint("barcode.1d", "height", fallback=80),
        one_d_narrow=parser.getint("barcode.1d", "narrow", fallback=2),
        one_d_wide=_read_setting_one_d_wide(parser, brand),
        one_d_human_readable=parser.getboolean("barcode.1d", "human_readable", fallback=True),
        qr_model=parser.getint("barcode.qr", "model", fallback=2),
        qr_ecc=parser.get("barcode.qr", "ecc", fallback="M").strip().upper(),
        qr_cell_size=parser.getint("barcode.qr", "cell_size", fallback=4),
        datamatrix_cell_size=parser.getint("barcode.datamatrix", "cell_size", fallback=4),
        pdf417_rows=parser.getint("barcode.pdf417", "rows", fallback=30),
        pdf417_columns=parser.getint("barcode.pdf417", "columns", fallback=5),
        pdf417_security_level=parser.getint("barcode.pdf417", "security_level", fallback=2),
        pdf417_module_width=parser.getint("barcode.pdf417", "module_width", fallback=3),
        pdf417_module_height=parser.getint("barcode.pdf417", "module_height", fallback=10),
    )


def save_settings(path: str | Path, settings: PrinterSettings) -> None:
    _validate_settings(settings)
    config_path = Path(path)
    parser = _read_parser(config_path)
    _ensure_sections(parser)

    parser.set("printer", "brand", settings.brand)
    parser.set("printer", "mode", settings.mode)
    parser.set("printer", "print_method", settings.print_method)
    parser.set("printer", "media_handling", settings.media_handling)
    parser.set("printer", "speed", str(settings.print_speed))
    parser.set("printer", "density", str(settings.print_density))
    parser.set("printer", "language", "auto")
    parser.set("printer", "command_encoding", "auto")
    parser.set("printer", "ip", settings.ip)
    parser.set("printer", "port", str(settings.port))
    parser.set("printer", "windows_printer_name", settings.windows_printer_name or "auto")

    parser.set("label", "width_mm", str(settings.width_mm))
    parser.set("label", "height_mm", str(settings.height_mm))
    parser.set("label", "dpi", str(settings.dpi))
    parser.set("label", "gap_mm", _format_float(settings.gap_mm))
    if not parser.has_option("label", "media_type"):
        parser.set("label", "media_type", "gap")

    parser.set("barcode", "type", settings.barcode_type)
    parser.set("barcode", "auto_layout", "yes" if settings.barcode_auto_layout else "no")
    parser.set("barcode", "x", str(settings.barcode_x))
    parser.set("barcode", "y", str(settings.barcode_y))
    parser.set("barcode", "rotation", str(settings.barcode_rotation))
    parser.set("barcode.1d", "height", str(settings.one_d_height))
    parser.set("barcode.1d", "narrow", str(settings.one_d_narrow))
    parser.set("barcode.1d", "wide", str(settings.one_d_wide))
    parser.set("barcode.1d", "human_readable", "yes" if settings.one_d_human_readable else "no")
    parser.set("barcode.qr", "model", str(settings.qr_model))
    parser.set("barcode.qr", "ecc", settings.qr_ecc)
    parser.set("barcode.qr", "cell_size", str(settings.qr_cell_size))
    parser.set("barcode.datamatrix", "cell_size", str(settings.datamatrix_cell_size))
    parser.set("barcode.pdf417", "rows", str(settings.pdf417_rows))
    parser.set("barcode.pdf417", "columns", str(settings.pdf417_columns))
    parser.set("barcode.pdf417", "security_level", str(settings.pdf417_security_level))
    parser.set("barcode.pdf417", "module_width", str(settings.pdf417_module_width))
    parser.set("barcode.pdf417", "module_height", str(settings.pdf417_module_height))

    if not parser.has_section("data"):
        parser.add_section("data")
    if not parser.has_option("data", "excel_file"):
        parser.set("data", "excel_file", DEFAULTS["data"]["excel_file"])
    if not parser.has_option("data", "output_dir"):
        parser.set("data", "output_dir", DEFAULTS["data"]["output_dir"])

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8-sig") as file:
        parser.write(file)


def installed_printers() -> list[str]:
    try:
        import win32print
    except ImportError:
        return []
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    names = [printer[2] for printer in win32print.EnumPrinters(flags)]
    return sorted({name for name in names if name})


def check_network(ip: str, port: int, timeout: float = 2.0) -> None:
    with socket.create_connection((ip, port), timeout=timeout):
        return


def _read_parser(path: Path) -> ConfigParser:
    parser = ConfigParser()
    parser.read_dict(DEFAULTS)
    if path.exists():
        parser.read(path, encoding="utf-8-sig")
    return parser


def _ensure_sections(parser: ConfigParser) -> None:
    for section, values in DEFAULTS.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for option, value in values.items():
            if not parser.has_option(section, option):
                parser.set(section, option, value)


def _read_setting_one_d_wide(parser: ConfigParser, brand: str) -> int:
    raw_wide = parser.get("barcode.1d", "wide", fallback="auto").strip().lower()
    if raw_wide in {"", "auto"}:
        return 6 if brand == "bixolon" else 2
    return int(raw_wide)


def _read_setting_print_tuning(
    parser: ConfigParser,
    option: str,
    brand: str,
    defaults: dict[str, int],
    minimum: int,
    maximum: int,
) -> int:
    raw_value = parser.get("printer", option, fallback="auto").strip().lower()
    if raw_value in {"", "auto"}:
        return defaults.get(brand, defaults["bixolon"])
    value = int(raw_value)
    return max(minimum, min(maximum, value))


def _validate_settings(settings: PrinterSettings) -> None:
    if settings.brand not in BRAND_LABELS:
        raise ValueError("\ud504\ub9b0\ud130 \ube0c\ub79c\ub4dc\ub97c \uc120\ud0dd\ud558\uc138\uc694.")
    if settings.mode not in MODE_LABELS:
        raise ValueError("\uc5f0\uacb0 \ubc29\uc2dd\uc744 \uc120\ud0dd\ud558\uc138\uc694.")
    if settings.print_method not in SUPPORTED_PRINT_METHODS:
        raise ValueError("\uc778\uc1c4 \ubc29\uc2dd\uc744 \uc120\ud0dd\ud558\uc138\uc694.")
    if settings.media_handling not in SUPPORTED_MEDIA_HANDLING:
        raise ValueError("배출 옵션을 선택하세요.")
    if settings.barcode_type not in SUPPORTED_BARCODE_TYPES:
        raise ValueError("\ubc14\ucf54\ub4dc \uc885\ub958\ub97c \uc120\ud0dd\ud558\uc138\uc694.")
    if settings.width_mm <= 0 or settings.height_mm <= 0:
        raise ValueError("\uc6a9\uc9c0 \uac00\ub85c, \uc138\ub85c\ub294 1mm \uc774\uc0c1\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4.")
    if settings.dpi not in {203, 300, 600}:
        raise ValueError("DPI\ub294 203, 300, 600 \uc911 \ud558\ub098\ub85c \uc785\ub825\ud558\uc138\uc694.")
    if settings.gap_mm < 0:
        raise ValueError("\ub77c\ubca8 \uac04\uaca9\uc740 0 \uc774\uc0c1\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4.")
    if settings.print_speed < 1 or settings.print_speed > 20:
        raise ValueError("\uc778\uc1c4\uc18d\ub3c4\ub294 1\ubd80\ud130 20 \uc0ac\uc774\ub85c \uc785\ub825\ud558\uc138\uc694.")
    if settings.print_density < 0 or settings.print_density > 30:
        raise ValueError("\ub18d\ub3c4\ub294 0\ubd80\ud130 30 \uc0ac\uc774\ub85c \uc785\ub825\ud558\uc138\uc694.")
    if settings.barcode_rotation not in {0, 90, 180, 270}:
        raise ValueError("\ubc14\ucf54\ub4dc \ud68c\uc804\uc740 0, 90, 180, 270 \uc911 \ud558\ub098\uc785\ub2c8\ub2e4.")
    if min(settings.barcode_x, settings.barcode_y) < 0:
        raise ValueError("\ubc14\ucf54\ub4dc X/Y \uc88c\ud45c\ub294 0 \uc774\uc0c1\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4.")
    if min(settings.one_d_height, settings.one_d_narrow, settings.one_d_wide) <= 0:
        raise ValueError("1D \ubc14\ucf54\ub4dc \ub192\uc774/\ub108\ube44 \uc124\uc815\uc740 1 \uc774\uc0c1\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4.")
    if settings.qr_ecc not in {"L", "M", "Q", "H"}:
        raise ValueError("QR ECC\ub294 L, M, Q, H \uc911 \ud558\ub098\uc785\ub2c8\ub2e4.")
    if settings.mode == "network":
        if not settings.ip.strip():
            raise ValueError("LAN \uc5f0\uacb0\uc740 \ud504\ub9b0\ud130 IP\uac00 \ud544\uc694\ud569\ub2c8\ub2e4.")
        if settings.port <= 0 or settings.port > 65535:
            raise ValueError("\ud3ec\ud2b8\ub294 1\ubd80\ud130 65535 \uc0ac\uc774\ub85c \uc785\ub825\ud558\uc138\uc694.")
    if settings.mode == "windows_raw" and not _usable_printer_name(settings.windows_printer_name):
        raise ValueError("USB \uc5f0\uacb0\uc740 Windows \ud504\ub9b0\ud130 \uc774\ub984\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.")


def _usable_printer_name(name: str) -> bool:
    return bool(name.strip()) and name.strip().lower() != "auto"


def _format_float(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


class SettingsApp(tk.Tk):
    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.config_path = config_path
        self.printer_names = installed_printers()
        self.title("\ud504\ub9b0\ud130 \uc124\uc815")
        self.geometry("900x700")
        self.minsize(800, 640)
        self.configure(bg=COLORS.background)

        self.brand_var = tk.StringVar()
        self.mode_var = tk.StringVar()
        self.print_method_var = tk.StringVar()
        self.media_handling_var = tk.StringVar()
        self.print_speed_var = tk.StringVar()
        self.print_density_var = tk.StringVar()
        self.ip_var = tk.StringVar()
        self.port_var = tk.StringVar()
        self.printer_name_var = tk.StringVar()
        self.width_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.dpi_var = tk.StringVar()
        self.gap_var = tk.StringVar()
        self.barcode_type_var = tk.StringVar()
        self.barcode_auto_layout_var = tk.BooleanVar()
        self.barcode_x_var = tk.StringVar()
        self.barcode_y_var = tk.StringVar()
        self.barcode_rotation_var = tk.StringVar()
        self.one_d_height_var = tk.StringVar()
        self.one_d_narrow_var = tk.StringVar()
        self.one_d_wide_var = tk.StringVar()
        self.one_d_human_readable_var = tk.BooleanVar()
        self.qr_model_var = tk.StringVar()
        self.qr_ecc_var = tk.StringVar()
        self.qr_cell_size_var = tk.StringVar()
        self.datamatrix_cell_size_var = tk.StringVar()
        self.pdf417_rows_var = tk.StringVar()
        self.pdf417_columns_var = tk.StringVar()
        self.pdf417_security_var = tk.StringVar()
        self.pdf417_module_width_var = tk.StringVar()
        self.pdf417_module_height_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self._configure_style()
        self._build_ui()
        self.load_from_file()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=TYPOGRAPHY.body, background=COLORS.background)
        style.configure("TLabel", font=TYPOGRAPHY.body, foreground=COLORS.text_primary, background=COLORS.surface)
        style.configure("Body.TFrame", background=COLORS.background)
        style.configure("Surface.TFrame", background=COLORS.surface)
        style.configure("Header.TFrame", background=COLORS.panel)
        style.configure(
            "Brand.TLabel",
            font=TYPOGRAPHY.caption,
            foreground="#ffffff",
            background=COLORS.primary,
            padding=(9, 3),
        )
        style.configure(
            "Title.TLabel",
            font=TYPOGRAPHY.page_title,
            foreground=COLORS.text_primary,
            background=COLORS.panel,
        )
        style.configure(
            "Subtitle.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.text_secondary,
            background=COLORS.panel,
        )
        style.configure("BodySubtitle.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.background)
        style.configure(
            "Card.TLabelframe",
            background=COLORS.surface,
            bordercolor=COLORS.border,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Card.TLabelframe.Label",
            font=TYPOGRAPHY.section_title,
            foreground=COLORS.text_primary,
            background=COLORS.surface,
        )
        style.configure(
            "SectionTitle.TLabel",
            font=TYPOGRAPHY.section_title,
            foreground=COLORS.text_primary,
            background=COLORS.surface,
        )
        style.configure(
            "Primary.TButton",
            font=TYPOGRAPHY.button_text,
            foreground="#ffffff",
            background=COLORS.primary,
            bordercolor=COLORS.primary,
            padding=(14, 7),
            relief="flat",
            borderwidth=1,
        )
        style.map("Primary.TButton", background=[("active", COLORS.primary_hover), ("pressed", COLORS.primary_hover)])
        style.configure(
            "Secondary.TButton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface,
            bordercolor=COLORS.border_strong,
            padding=(14, 7),
            relief="flat",
            borderwidth=1,
        )
        style.map("Secondary.TButton", background=[("active", COLORS.surface_muted)])
        style.configure("Status.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.background)
        style.configure(
            "StatusPill.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.accent,
            background=COLORS.accent_soft,
            padding=(12, 5),
        )
        style.configure("TEntry", padding=(10, 6), fieldbackground=COLORS.surface, bordercolor=COLORS.border_strong)
        style.configure(
            "TSpinbox",
            padding=(10, 6),
            background=COLORS.surface,
            fieldbackground=COLORS.surface,
            foreground=COLORS.text_primary,
            bordercolor=COLORS.border_strong,
            arrowcolor=COLORS.text_secondary,
        )
        style.map(
            "TSpinbox",
            fieldbackground=[("disabled", COLORS.surface_muted)],
            background=[("active", COLORS.surface_muted)],
            foreground=[("disabled", COLORS.text_tertiary)],
        )
        style.configure(
            "TCombobox",
            padding=(10, 6),
            background=COLORS.surface,
            fieldbackground=COLORS.surface,
            foreground=COLORS.text_primary,
            bordercolor=COLORS.border_strong,
            arrowcolor=COLORS.text_secondary,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS.surface), ("disabled", COLORS.surface_muted)],
            background=[("readonly", COLORS.surface), ("active", COLORS.surface_muted)],
            foreground=[("disabled", COLORS.text_tertiary)],
        )
        style.configure("TRadiobutton", background=COLORS.surface, foreground=COLORS.text_primary, font=TYPOGRAPHY.body)
        style.map("TRadiobutton", background=[("active", COLORS.surface)])
        style.configure("TCheckbutton", background=COLORS.surface, foreground=COLORS.text_primary, font=TYPOGRAPHY.body)
        style.map("TCheckbutton", background=[("active", COLORS.surface)])

    def _build_ui(self) -> None:
        container = tk.Frame(self, bg=COLORS.background)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, bg=COLORS.background, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main = ttk.Frame(canvas, padding=SPACING.page_padding, style="Body.TFrame")
        main_window = canvas.create_window((0, 0), window=main, anchor="nw")
        main.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(main_window, width=event.width))
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        main.columnconfigure(0, weight=1)

        header = ttk.Frame(main, style="Header.TFrame", padding=(SPACING.page_padding, 14))
        header.grid(row=0, column=0, sticky="ew", pady=(0, SPACING.section_gap))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="거복이의꿈", style="Brand.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(header, text="\ud504\ub9b0\ud130 \uc124\uc815", style="Title.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(
            header,
            text=f"\uc800\uc7a5 \uc704\uce58: {self.config_path}",
            style="Subtitle.TLabel",
            wraplength=760,
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

        self._build_printer_section(main, 1)
        self._build_connection_section(main, 2)
        self._build_label_section(main, 3)
        self._build_barcode_section(main, 4)
        self._build_buttons(main, 5)

    def _build_printer_section(self, parent: ttk.Frame, row: int) -> None:
        frame = self._section_card(parent, row, "\ud504\ub9b0\ud130 \uae30\ubcf8 \uc124\uc815")
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="\ube0c\ub79c\ub4dc").grid(row=0, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Combobox(frame, textvariable=self.brand_var, values=list(BRAND_VALUES), state="readonly").grid(
            row=0, column=1, sticky="ew", pady=5
        )
        ttk.Label(frame, text="\uc778\uc1c4 \ubc29\uc2dd").grid(row=1, column=0, sticky="w", padx=(0, 14), pady=5)
        method_frame = ttk.Frame(frame, style="Surface.TFrame")
        method_frame.grid(row=1, column=1, sticky="w", pady=5)
        for label in PRINT_METHOD_VALUES:
            ttk.Radiobutton(method_frame, text=label, value=label, variable=self.print_method_var).pack(side="left", padx=(0, 20))
        ttk.Label(frame, text="배출 옵션").grid(row=2, column=0, sticky="w", padx=(0, 14), pady=5)
        handling_frame = ttk.Frame(frame, style="Surface.TFrame")
        handling_frame.grid(row=2, column=1, sticky="w", pady=5)
        for label in MEDIA_HANDLING_VALUES:
            ttk.Radiobutton(handling_frame, text=label, value=label, variable=self.media_handling_var).pack(side="left", padx=(0, 20))
        ttk.Label(frame, text="\ucd9c\ub825 \uac15\ub3c4").grid(row=3, column=0, sticky="w", padx=(0, 14), pady=5)
        tuning_frame = ttk.Frame(frame, style="Surface.TFrame")
        tuning_frame.grid(row=3, column=1, sticky="ew", pady=5)
        for col in range(2):
            tuning_frame.columnconfigure(col, weight=1)
        self._labeled_widget(
            tuning_frame,
            0,
            0,
            "\uc778\uc1c4\uc18d\ub3c4",
            self._number_stepper(tuning_frame, self.print_speed_var, 1, 20),
        )
        self._labeled_widget(
            tuning_frame,
            0,
            1,
            "\ub18d\ub3c4",
            self._number_stepper(tuning_frame, self.print_density_var, 0, 30),
        )

    def _build_connection_section(self, parent: ttk.Frame, row: int) -> None:
        frame = self._section_card(parent, row, "\uc5f0\uacb0 \ubc29\uc2dd")
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="\ubc29\uc2dd").grid(row=0, column=0, sticky="w", padx=(0, 14), pady=5)
        mode_frame = ttk.Frame(frame, style="Surface.TFrame")
        mode_frame.grid(row=0, column=1, sticky="w", pady=5)
        for label in MODE_VALUES:
            ttk.Radiobutton(mode_frame, text=label, value=label, variable=self.mode_var, command=self._sync_connection_state).pack(
                side="left", padx=(0, 20)
            )
        self.ip_label = ttk.Label(frame, text="\ud504\ub9b0\ud130 IP")
        self.ip_label.grid(row=1, column=0, sticky="w", padx=(0, 14), pady=5)
        self.ip_entry = ttk.Entry(frame, textvariable=self.ip_var)
        self.ip_entry.grid(row=1, column=1, sticky="ew", pady=5)
        self.port_label = ttk.Label(frame, text="\ud3ec\ud2b8")
        self.port_label.grid(row=2, column=0, sticky="w", padx=(0, 14), pady=5)
        self.port_entry = ttk.Entry(frame, textvariable=self.port_var)
        self.port_entry.grid(row=2, column=1, sticky="ew", pady=5)
        self.printer_label = ttk.Label(frame, text="Windows \ud504\ub9b0\ud130 \uc774\ub984")
        self.printer_label.grid(row=3, column=0, sticky="w", padx=(0, 14), pady=5)
        printer_row = ttk.Frame(frame, style="Surface.TFrame")
        printer_row.grid(row=3, column=1, sticky="ew", pady=5)
        printer_row.columnconfigure(0, weight=1)
        self.printer_box = ttk.Combobox(printer_row, textvariable=self.printer_name_var, values=self.printer_names)
        self.printer_box.grid(row=0, column=0, sticky="ew")
        ttk.Button(printer_row, text="\ubaa9\ub85d \uc0c8\ub85c\uace0\uce68", command=self.refresh_printers, style="Secondary.TButton").grid(row=0, column=1, padx=(8, 0))

    def _build_label_section(self, parent: ttk.Frame, row: int) -> None:
        frame = self._section_card(parent, row, "\uc6a9\uc9c0 \ud06c\uae30")
        for col in range(4):
            frame.columnconfigure(col, weight=1)
        entries = [
            ("\uac00\ub85c(mm)", self.width_var),
            ("\uc138\ub85c(mm)", self.height_var),
            ("\uac04\uaca9(mm)", self.gap_var),
            ("DPI", self.dpi_var),
        ]
        for idx, (label, var) in enumerate(entries):
            ttk.Label(frame, text=label).grid(row=0, column=idx, sticky="w", padx=(0 if idx == 0 else 10, 4), pady=(0, 4))
            widget = ttk.Combobox(frame, textvariable=var, values=["203", "300", "600"]) if label == "DPI" else ttk.Entry(frame, textvariable=var)
            widget.grid(row=1, column=idx, sticky="ew", padx=(0 if idx == 0 else 10, 4))

    def _build_barcode_section(self, parent: ttk.Frame, row: int) -> None:
        frame = self._section_card(parent, row, "\ubc14\ucf54\ub4dc \uc124\uc815")
        for col in range(3):
            frame.columnconfigure(col, weight=1)

        self._labeled_widget(frame, 0, 0, "\uc885\ub958", ttk.Combobox(frame, textvariable=self.barcode_type_var, values=list(BARCODE_TYPE_VALUES), state="readonly"))
        ttk.Checkbutton(
            frame,
            text="\uc6a9\uc9c0 \ud06c\uae30\uc5d0 \ub9de\ucdb0 \uc790\ub3d9 \uac00\uc6b4\ub370 \ubc30\uce58",
            variable=self.barcode_auto_layout_var,
            command=self._sync_barcode_layout_state,
        ).grid(row=0, column=1, columnspan=2, sticky="w", padx=(10, 4), pady=(18, 6))
        self.barcode_x_entry = ttk.Entry(frame, textvariable=self.barcode_x_var)
        self.barcode_y_entry = ttk.Entry(frame, textvariable=self.barcode_y_var)
        self._labeled_widget(frame, 2, 1, "X", self.barcode_x_entry)
        self._labeled_widget(frame, 2, 2, "Y", self.barcode_y_entry)

    def _labeled_widget(self, parent: ttk.Frame, row: int, column: int, text: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky="w", padx=(0 if column == 0 else 10, 4), pady=(0, 4))
        widget.grid(row=row + 1, column=column, sticky="ew", padx=(0 if column == 0 else 10, 4), pady=(0, 6))

    def _number_stepper(self, parent: ttk.Frame, variable: tk.StringVar, minimum: int, maximum: int) -> tk.Widget:
        if hasattr(ttk, "Spinbox"):
            return ttk.Spinbox(
                parent,
                from_=minimum,
                to=maximum,
                increment=1,
                textvariable=variable,
                width=8,
            )
        return tk.Spinbox(
            parent,
            from_=minimum,
            to=maximum,
            increment=1,
            textvariable=variable,
            width=8,
            bg=COLORS.surface,
            fg=COLORS.text_primary,
            relief="solid",
            bd=1,
        )

    def _section_card(self, parent: ttk.Frame, row: int, title: str) -> ttk.Frame:
        card = tk.Frame(parent, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        card.grid(row=row, column=0, sticky="ew", pady=(0, SPACING.section_gap))
        card.columnconfigure(0, weight=1)
        title_bar = tk.Frame(card, bg=COLORS.surface_muted, height=42)
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.columnconfigure(1, weight=1)
        tk.Frame(title_bar, bg=COLORS.accent, width=3).grid(row=0, column=0, sticky="ns", padx=(SPACING.card_padding, 10), pady=11)
        tk.Label(
            title_bar,
            text=title,
            bg=COLORS.surface_muted,
            fg=COLORS.text_primary,
            font=TYPOGRAPHY.section_title,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(0, SPACING.card_padding), pady=(11, 10))
        inner = ttk.Frame(card, style="Surface.TFrame", padding=(SPACING.card_padding, 13, SPACING.card_padding, SPACING.card_padding))
        inner.grid(row=1, column=0, sticky="ew")
        inner.columnconfigure(0, weight=0)
        return inner

    def _build_buttons(self, parent: ttk.Frame, row: int) -> None:
        buttons = ttk.Frame(parent, style="Body.TFrame")
        buttons.grid(row=row, column=0, sticky="ew", pady=(4, 0))
        buttons.columnconfigure(0, weight=1)
        ttk.Label(buttons, textvariable=self.status_var, style="StatusPill.TLabel", wraplength=460).grid(row=0, column=0, sticky="w")
        ttk.Button(buttons, text="\ud604\uc7ac \uc124\uc815 \ub2e4\uc2dc \ubd88\ub7ec\uc624\uae30", command=self.load_from_file, style="Secondary.TButton").grid(row=0, column=1, padx=(8, 0))
        ttk.Button(buttons, text="\uc5f0\uacb0 \ud655\uc778", command=self.check_connection, style="Secondary.TButton").grid(row=0, column=2, padx=(8, 0))
        ttk.Button(buttons, text="\uc124\uc815 \uc800\uc7a5", command=self.save_to_file, style="Primary.TButton").grid(row=0, column=3, padx=(8, 0))

    def load_from_file(self) -> None:
        try:
            settings = load_settings(self.config_path)
        except Exception as exc:
            messagebox.showerror("\uc124\uc815 \uc77d\uae30 \uc2e4\ud328", str(exc))
            return
        self.brand_var.set(BRAND_LABELS[settings.brand])
        self.mode_var.set(MODE_LABELS[settings.mode])
        self.print_method_var.set(PRINT_METHOD_LABELS[settings.print_method])
        self.media_handling_var.set(MEDIA_HANDLING_LABELS[settings.media_handling])
        self.ip_var.set(settings.ip)
        self.port_var.set(str(settings.port))
        self.printer_name_var.set("" if settings.windows_printer_name == "auto" else settings.windows_printer_name)
        self.width_var.set(str(settings.width_mm))
        self.height_var.set(str(settings.height_mm))
        self.dpi_var.set(str(settings.dpi))
        self.gap_var.set(_format_float(settings.gap_mm))
        self.print_speed_var.set(str(settings.print_speed))
        self.print_density_var.set(str(settings.print_density))
        self.barcode_type_var.set(BARCODE_TYPE_LABELS[settings.barcode_type])
        self.barcode_auto_layout_var.set(settings.barcode_auto_layout)
        self.barcode_x_var.set(str(settings.barcode_x))
        self.barcode_y_var.set(str(settings.barcode_y))
        self.barcode_rotation_var.set(str(settings.barcode_rotation))
        self.one_d_height_var.set(str(settings.one_d_height))
        self.one_d_narrow_var.set(str(settings.one_d_narrow))
        self.one_d_wide_var.set(str(settings.one_d_wide))
        self.one_d_human_readable_var.set(settings.one_d_human_readable)
        self.qr_model_var.set(str(settings.qr_model))
        self.qr_ecc_var.set(settings.qr_ecc)
        self.qr_cell_size_var.set(str(settings.qr_cell_size))
        self.datamatrix_cell_size_var.set(str(settings.datamatrix_cell_size))
        self.pdf417_rows_var.set(str(settings.pdf417_rows))
        self.pdf417_columns_var.set(str(settings.pdf417_columns))
        self.pdf417_security_var.set(str(settings.pdf417_security_level))
        self.pdf417_module_width_var.set(str(settings.pdf417_module_width))
        self.pdf417_module_height_var.set(str(settings.pdf417_module_height))
        self._sync_connection_state()
        self._sync_barcode_layout_state()
        self.status_var.set("\ud604\uc7ac \uc124\uc815\uc744 \ubd88\ub7ec\uc654\uc2b5\ub2c8\ub2e4.")

    def save_to_file(self) -> None:
        try:
            settings = self._collect_settings()
            save_settings(self.config_path, settings)
        except Exception as exc:
            messagebox.showerror("\uc124\uc815 \uc800\uc7a5 \uc2e4\ud328", str(exc))
            return
        self.status_var.set("\uc124\uc815\uc774 \uc800\uc7a5\ub418\uc5c8\uc2b5\ub2c8\ub2e4. Excel\uc5d0\uc11c \ub77c\ubca8 \ucd9c\ub825 \ubc84\ud2bc\uc744 \ub204\ub974\uba74 \uc801\uc6a9\ub429\ub2c8\ub2e4.")

    def refresh_printers(self) -> None:
        self.printer_names = installed_printers()
        self.printer_box.configure(values=self.printer_names)
        self.status_var.set(f"\ud504\ub9b0\ud130 \ubaa9\ub85d\uc744 \uc0c8\ub85c\uace0\uce68\ud588\uc2b5\ub2c8\ub2e4. \ubc1c\uacac: {len(self.printer_names)}\uac1c")

    def check_connection(self) -> None:
        try:
            settings = self._collect_settings()
        except Exception as exc:
            messagebox.showerror("\uc5f0\uacb0 \ud655\uc778 \uc2e4\ud328", str(exc))
            return
        if settings.mode == "network":
            try:
                check_network(settings.ip, settings.port)
            except OSError as exc:
                messagebox.showerror("\uc5f0\uacb0 \uc2e4\ud328", f"{settings.ip}:{settings.port} \uc5f0\uacb0\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.\n{exc}")
                return
            self.status_var.set(f"LAN \uc5f0\uacb0 \ud655\uc778 \uc131\uacf5: {settings.ip}:{settings.port}")
            return
        printers = installed_printers()
        if settings.windows_printer_name in printers:
            self.status_var.set(f"Windows \ud504\ub9b0\ud130 \ud655\uc778 \uc131\uacf5: {settings.windows_printer_name}")
        else:
            messagebox.showwarning("\ud504\ub9b0\ud130 \ud655\uc778 \ud544\uc694", "\uc785\ub825\ud55c \ud504\ub9b0\ud130 \uc774\ub984\uc774 Windows \ud504\ub9b0\ud130 \ubaa9\ub85d\uc5d0\uc11c \ubcf4\uc774\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.")

    def _collect_settings(self) -> PrinterSettings:
        port_text = self.port_var.get().strip()
        settings = PrinterSettings(
            brand=BRAND_VALUES.get(self.brand_var.get(), ""),
            mode=MODE_VALUES.get(self.mode_var.get(), ""),
            print_method=PRINT_METHOD_VALUES.get(self.print_method_var.get(), ""),
            media_handling=MEDIA_HANDLING_VALUES.get(self.media_handling_var.get(), ""),
            ip=self.ip_var.get().strip(),
            port=int(port_text) if port_text else 9100,
            windows_printer_name=self.printer_name_var.get().strip(),
            width_mm=int(self.width_var.get().strip()),
            height_mm=int(self.height_var.get().strip()),
            dpi=int(self.dpi_var.get().strip()),
            gap_mm=float(self.gap_var.get().strip()),
            print_speed=int(self.print_speed_var.get().strip()),
            print_density=int(self.print_density_var.get().strip()),
            barcode_type=BARCODE_TYPE_VALUES.get(self.barcode_type_var.get(), ""),
            barcode_auto_layout=bool(self.barcode_auto_layout_var.get()),
            barcode_x=int(self.barcode_x_var.get().strip()),
            barcode_y=int(self.barcode_y_var.get().strip()),
            barcode_rotation=0,
            one_d_height=80,
            one_d_narrow=2,
            one_d_wide=6 if BRAND_VALUES.get(self.brand_var.get(), "") == "bixolon" else 2,
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
        _validate_settings(settings)
        return settings

    def _sync_connection_state(self) -> None:
        mode = MODE_VALUES.get(self.mode_var.get(), "network")
        network_state = "normal" if mode == "network" else "disabled"
        usb_state = "normal" if mode == "windows_raw" else "disabled"
        for widget in (self.ip_entry, self.port_entry):
            widget.configure(state=network_state)
        self.printer_box.configure(state=usb_state)

    def _sync_barcode_layout_state(self) -> None:
        state = "disabled" if self.barcode_auto_layout_var.get() else "normal"
        for widget in (self.barcode_x_entry, self.barcode_y_entry):
            widget.configure(state=state)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Edit label printer settings.")
    parser.add_argument("--config", default=None, help="Path to config.ini")
    parser.add_argument("--show-config-path", action="store_true", help="Print the config path and exit")
    parser.add_argument("--smoke-test", action="store_true", help="Load settings and exit without showing the UI")
    args = parser.parse_args(argv)

    config_path = Path(args.config) if args.config else config_path_for_app()
    if args.show_config_path:
        print(config_path)
        return 0
    if args.smoke_test:
        load_settings(config_path)
        return 0

    app = SettingsApp(config_path)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
