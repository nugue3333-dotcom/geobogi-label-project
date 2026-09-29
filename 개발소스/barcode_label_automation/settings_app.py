from __future__ import annotations

import argparse
import sys
import tkinter as tk
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from .brand_assets import apply_window_icon, load_header_logo
from .config import (
    DEFAULTS,
    SUPPORTED_BARCODE_TYPES,
    SUPPORTED_MEDIA_HANDLING,
    SUPPORTED_MEDIA_TYPES,
    SUPPORTED_PRINT_METHODS,
    SUPPORTED_PRINT_ORIENTATIONS,
    is_printer_model_approved,
    supported_media_handling_for_brand,
)
from .errors import PrinterError
from .printers.network import check_connection as check_network_connection
from .runtime_paths import executable_dir, runtime_base_dir
from .ui_tokens import COLORS, SPACING, TYPOGRAPHY
from .ui_window import set_initial_window_size


BRAND_LABELS = {
    "bixolon": "BIXOLON / \ube45\uc194\ub860",
    "tsc": "TSC",
    "zebra": "Zebra / \uc81c\ube0c\ub77c",
    "sewoo": "SEWOO / \uc138\uc6b0\ud14c\ud06c",
}
MODE_LABELS = {
    "network": "LAN / \ub124\ud2b8\uc6cc\ud06c",
    "windows_raw": "USB / Windows",
}
PRINT_METHOD_LABELS = {
    "direct_thermal": "\uac10\uc5f4 / \ub9ac\ubcf8 \uc5c6\uc74c",
    "thermal_transfer": "\uc5f4\uc804\uc0ac / \ub9ac\ubcf8",
}
PRINT_ORIENTATION_LABELS = {
    "normal": "정방향 (기존 출력)",
    "rotate_180": "180도 회전",
}
MEDIA_HANDLING_LABELS = {
    "tear_off": "뜯어내기",
    "cutter": "커터",
    "peeler": "필러",
}
MEDIA_TYPE_LABELS = {
    "gap": "갭 용지",
    "black_mark": "블랙마크 용지",
    "continuous": "연속 용지",
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
PRINT_ORIENTATION_VALUES = {label: value for value, label in PRINT_ORIENTATION_LABELS.items()}
MEDIA_HANDLING_VALUES = {label: value for value, label in MEDIA_HANDLING_LABELS.items()}
MEDIA_TYPE_VALUES = {label: value for value, label in MEDIA_TYPE_LABELS.items()}
BARCODE_TYPE_VALUES = {label: value for value, label in BARCODE_TYPE_LABELS.items()}


@dataclass(frozen=True)
class SettingsValidationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


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
    model: str = ""
    media_type: str = "gap"
    media_handling: str = "tear_off"
    print_orientation: str = "normal"
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
    return runtime_base_dir(executable_dir())


def config_path_for_app() -> Path:
    return app_base_dir() / "config.ini"


def load_settings(path: str | Path) -> PrinterSettings:
    config_path = Path(path)
    parser = _read_parser(config_path)
    brand = parser.get("printer", "brand", fallback="bixolon").strip().lower()
    model = parser.get("printer", "model", fallback="").strip()
    mode = parser.get("printer", "mode", fallback="network").strip().lower()
    print_method = parser.get("printer", "print_method", fallback="direct_thermal").strip().lower()
    print_orientation = parser.get("printer", "print_orientation", fallback="normal").strip().lower()
    media_handling = parser.get("printer", "media_handling", fallback="tear_off").strip().lower()
    media_type = parser.get("label", "media_type", fallback="gap").strip().lower()
    print_speed = _read_setting_print_tuning(parser, "speed", brand, {"bixolon": 3, "tsc": 4, "zebra": 4, "sewoo": 4}, 1, 20)
    print_density = _read_setting_print_tuning(parser, "density", brand, {"bixolon": 20, "tsc": 8, "zebra": 10, "sewoo": 10}, 0, 30)
    barcode_type = parser.get("barcode", "type", fallback="code128").strip().lower()
    if barcode_type == "qrcode":
        barcode_type = "qr"
    if barcode_type in {"data_matrix", "dmatrix", "dm"}:
        barcode_type = "datamatrix"
    return PrinterSettings(
        brand=brand if brand in BRAND_LABELS else "bixolon",
        model=model,
        mode=mode if mode in MODE_LABELS else "network",
        print_method=print_method if print_method in SUPPORTED_PRINT_METHODS else "direct_thermal",
        print_orientation=print_orientation if print_orientation in SUPPORTED_PRINT_ORIENTATIONS else "normal",
        media_handling=media_handling if media_handling in SUPPORTED_MEDIA_HANDLING else "tear_off",
        ip=parser.get("printer", "ip", fallback="192.168.0.50").strip(),
        port=parser.getint("printer", "port", fallback=9100),
        windows_printer_name=parser.get("printer", "windows_printer_name", fallback="auto").strip(),
        width_mm=parser.getint("label", "width_mm", fallback=50),
        height_mm=parser.getint("label", "height_mm", fallback=30),
        dpi=parser.getint("label", "dpi", fallback=203),
        gap_mm=parser.getfloat("label", "gap_mm", fallback=3),
        media_type=media_type if media_type in SUPPORTED_MEDIA_TYPES else "gap",
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
    if settings.model.strip():
        parser.set("printer", "model", settings.model.strip())
    else:
        parser.remove_option("printer", "model")
    parser.set("printer", "mode", settings.mode)
    parser.set("printer", "print_method", settings.print_method)
    parser.set("printer", "print_orientation", settings.print_orientation)
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
    parser.set("label", "media_type", settings.media_type)

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
    check_network_connection(ip, port, timeout=timeout)


def validate_settings(settings: PrinterSettings) -> SettingsValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if settings.brand not in BRAND_LABELS:
        errors.append("프린터 브랜드를 선택하세요.")
    elif not is_printer_model_approved(settings.brand, settings.model):
        errors.append(
            "SEWOO는 제조사 ZPL 근거와 실제 출력 확인 후 docs/PRODUCT_PACKAGES.md에 승인된 모델만 저장할 수 있습니다."
        )
    if settings.mode not in MODE_LABELS:
        errors.append("연결 방식을 선택하세요.")
    if settings.print_method not in SUPPORTED_PRINT_METHODS:
        errors.append("인쇄 방식을 선택하세요.")
    if settings.print_orientation not in SUPPORTED_PRINT_ORIENTATIONS:
        errors.append("인쇄 방향은 정방향 또는 180도 회전 중 하나를 선택하세요.")
    if settings.media_handling not in SUPPORTED_MEDIA_HANDLING:
        errors.append("인쇄후작업을 선택하세요.")
    if settings.media_handling in SUPPORTED_MEDIA_HANDLING:
        if settings.media_handling not in supported_media_handling_for_brand(settings.brand):
            if settings.brand == "sewoo":
                errors.append("SEWOO는 공식 모델별 근거가 승인될 때까지 인쇄후작업을 뜯어내기만 사용할 수 있습니다.")
            elif settings.brand == "bixolon" and settings.media_handling == "peeler":
                errors.append("BIXOLON/SLCS 필러 명령은 아직 지원하지 않습니다. 인쇄후작업을 뜯어내기 또는 커터로 선택하세요.")
            else:
                errors.append("선택한 브랜드에서 지원하지 않는 인쇄후작업입니다.")
    if settings.barcode_type not in SUPPORTED_BARCODE_TYPES:
        errors.append("바코드 종류를 선택하세요.")
    if settings.width_mm <= 0 or settings.height_mm <= 0:
        errors.append("용지 가로, 세로는 1mm 이상이어야 합니다.")
    if settings.width_mm > 300 or settings.height_mm > 300:
        warnings.append("300mm가 넘는 라벨은 프린터 모델별 최대 출력 폭/길이를 먼저 확인하세요.")
    if settings.dpi not in {203, 300, 600}:
        errors.append("DPI는 203, 300, 600 중 하나로 입력하세요.")
    if settings.gap_mm < 0:
        errors.append("라벨 간격은 0 이상이어야 합니다.")
    if settings.media_type not in SUPPORTED_MEDIA_TYPES:
        errors.append("용지 유형을 선택하세요.")
    if settings.media_type in {"gap", "black_mark"} and settings.gap_mm <= 0:
        errors.append("갭 용지와 블랙마크 용지는 간격(mm)을 0보다 크게 입력하세요.")
    if settings.media_type == "continuous" and settings.gap_mm > 0:
        warnings.append("연속 용지는 간격(mm)을 0으로 두는 것을 권장합니다.")
    if settings.print_speed < 1 or settings.print_speed > 20:
        errors.append("인쇄속도는 1부터 20 사이로 입력하세요.")
    if settings.print_density < 0 or settings.print_density > 30:
        errors.append("농도는 0부터 30 사이로 입력하세요.")
    if settings.barcode_rotation not in {0, 90, 180, 270}:
        errors.append("바코드 회전은 0, 90, 180, 270 중 하나입니다.")
    if min(settings.barcode_x, settings.barcode_y) < 0:
        errors.append("바코드 X/Y 좌표는 0 이상이어야 합니다.")
    if min(settings.one_d_height, settings.one_d_narrow, settings.one_d_wide) <= 0:
        errors.append("1D 바코드 높이/너비 설정은 1 이상이어야 합니다.")
    if settings.qr_ecc not in {"L", "M", "Q", "H"}:
        errors.append("QR ECC는 L, M, Q, H 중 하나입니다.")
    if settings.mode == "network":
        if not settings.ip.strip():
            errors.append("LAN 연결은 프린터 IP가 필요합니다.")
        elif any(char.isspace() for char in settings.ip.strip()):
            errors.append("프린터 IP 또는 호스트명에는 공백을 넣을 수 없습니다.")
        if settings.port <= 0 or settings.port > 65535:
            errors.append("포트는 1부터 65535 사이로 입력하세요.")
        elif settings.port != 9100:
            warnings.append("RAW LAN 프린터는 보통 9100 포트를 사용합니다. 장비 설정이 다를 때만 변경하세요.")
    if settings.mode == "windows_raw" and not _usable_printer_name(settings.windows_printer_name):
        errors.append("USB 연결은 Windows 프린터 이름이 필요합니다.")

    return SettingsValidationReport(tuple(errors), tuple(warnings))


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
    report = validate_settings(settings)
    if report.errors:
        raise ValueError("\n".join(report.errors))


def _parse_int_field(text: str, label: str, *, default: int | None = None) -> int:
    value = text.strip()
    if not value:
        if default is not None:
            return default
        raise ValueError(f"{label}을 입력하세요.")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{label}은 숫자로 입력하세요.") from exc


def _parse_float_field(text: str, label: str, *, default: float | None = None) -> float:
    value = text.strip()
    if not value:
        if default is not None:
            return default
        raise ValueError(f"{label}을 입력하세요.")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{label}은 숫자로 입력하세요.") from exc


def _usable_printer_name(name: str) -> bool:
    return bool(name.strip()) and name.strip().lower() != "auto"


def _format_float(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


class SettingsApp(tk.Tk):
    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self._display_scale = self._resolve_display_scale()
        self._base_title = "채움랩 프린터 설정"
        self._settings_dirty = False
        self._suspend_dirty_tracking = False
        self.config_path = config_path
        self.base_dir = config_path.parent
        self.install_dir = executable_dir() if getattr(sys, "frozen", False) else self.base_dir
        self.printer_names = installed_printers()
        self.title(self._base_title)
        apply_window_icon(self, base_dir=self.base_dir, install_dir=self.install_dir)
        set_initial_window_size(
            self,
            preferred_width=1280,
            preferred_height=860,
            minimum_width=900,
            minimum_height=680,
        )
        self.configure(bg=COLORS.background)

        self.brand_var = tk.StringVar()
        self._saved_model = ""
        self.mode_var = tk.StringVar()
        self.print_method_var = tk.StringVar()
        self.print_orientation_var = tk.StringVar()
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
        self.media_type_var = tk.StringVar()
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
        self.validation_var = tk.StringVar()
        self.brand_logo = load_header_logo(
            self,
            base_dir=self.base_dir,
            install_dir=self.install_dir,
            max_width=220,
            max_height=54,
        )

        self._configure_style()
        self._build_ui()
        self.load_from_file(confirm_discard=False)
        self._install_dirty_tracking()
        self.bind("<Control-s>", self._save_shortcut)
        self.protocol("WM_DELETE_WINDOW", self._confirm_close)

    def _resolve_display_scale(self) -> float:
        try:
            scale = float(self.winfo_fpixels("1i")) / 96.0
        except (tk.TclError, TypeError, ValueError):
            return 1.0
        return max(1.0, min(2.0, scale))

    def _scaled(self, value: int) -> int:
        return max(1, round(value * self._display_scale))

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=TYPOGRAPHY.body, background=COLORS.background)
        style.configure("TLabel", font=TYPOGRAPHY.body, foreground=COLORS.text_primary, background=COLORS.surface)
        style.configure("Body.TFrame", background=COLORS.background)
        style.configure("Surface.TFrame", background=COLORS.surface)
        style.configure("Header.TFrame", background=COLORS.panel)
        style.configure("Ribbon.TFrame", background=COLORS.surface)
        style.configure("Overview.TFrame", background=COLORS.surface_subtle)
        style.configure(
            "Brand.TLabel",
            font=TYPOGRAPHY.caption,
            foreground="#ffffff",
            background=COLORS.primary,
            padding=(9, 4),
        )
        style.configure(
            "Title.TLabel",
            font=(TYPOGRAPHY.page_title[0], 18, "bold"),
            foreground=COLORS.text_primary,
            background=COLORS.panel,
        )
        style.configure(
            "Subtitle.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.text_secondary,
            background=COLORS.panel,
        )
        style.configure("HeaderLogo.TLabel", background=COLORS.panel)
        style.configure(
            "SectionTitle.TLabel",
            font=TYPOGRAPHY.section_title,
            foreground=COLORS.text_primary,
            background=COLORS.surface,
        )
        style.configure(
            "OverviewTitle.TLabel",
            font=TYPOGRAPHY.section_title,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
        )
        style.configure(
            "OverviewBody.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.text_secondary,
            background=COLORS.surface_subtle,
        )
        style.configure(
            "Primary.TButton",
            font=TYPOGRAPHY.button_text,
            foreground="#ffffff",
            background=COLORS.primary,
            bordercolor=COLORS.primary,
            padding=(12, 5),
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
            padding=(12, 5),
            relief="flat",
            borderwidth=1,
        )
        style.map("Secondary.TButton", background=[("active", COLORS.surface_muted)])
        style.configure("Status.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.surface)
        style.configure(
            "StatusPill.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.accent,
            background=COLORS.accent_soft,
            padding=(8, 4),
        )
        style.configure(
            "Validation.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.text_primary,
            background=COLORS.surface_subtle,
        )
        style.configure(
            "ValidationMuted.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.text_secondary,
            background=COLORS.surface_subtle,
        )
        style.configure("TEntry", padding=(8, 5), fieldbackground=COLORS.surface, bordercolor=COLORS.border_strong)
        style.configure(
            "TSpinbox",
            padding=(8, 5),
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
            padding=(8, 5),
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
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        canvas = tk.Canvas(container, bg=COLORS.background, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        main = ttk.Frame(canvas, padding=(12, 10), style="Body.TFrame")
        main_window = canvas.create_window((0, 0), window=main, anchor="nw")
        self._settings_canvas = canvas
        self._settings_scrollbar = scrollbar
        self._settings_main = main
        self._settings_main_window = main_window
        main.bind("<Configure>", self._on_settings_content_configure)
        canvas.bind("<Configure>", self._on_settings_canvas_configure)
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        main.columnconfigure(0, weight=1)

        header = ttk.Frame(main, style="Header.TFrame", padding=(16, 8))
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(1, weight=1)
        if self.brand_logo is not None:
            ttk.Label(header, image=self.brand_logo, style="HeaderLogo.TLabel").grid(
                row=0, column=0, sticky="w", padx=(0, 18)
            )
        else:
            ttk.Label(header, text="채움랩", style="Brand.TLabel").grid(
                row=0, column=0, sticky="w", padx=(0, 18)
            )
        ttk.Label(header, text="\ud504\ub9b0\ud130 \uc124\uc815", style="Title.TLabel").grid(row=0, column=1, sticky="w")
        self._settings_status_label = ttk.Label(
            header,
            textvariable=self.status_var,
            style="StatusPill.TLabel",
            wraplength=240,
        )
        self._settings_status_label.grid(row=0, column=2, sticky="e", padx=(14, 0))
        self._settings_path_label = ttk.Label(
            header,
            text=f"설정 파일  {self.config_path.name}",
            style="Subtitle.TLabel",
        )
        self._settings_path_label.grid(row=0, column=3, sticky="e", padx=(14, 0))

        ribbon_card = tk.Frame(main, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        ribbon_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ribbon_card.columnconfigure(0, weight=1)
        ribbon = ttk.Frame(ribbon_card, style="Ribbon.TFrame", padding=(8, 5))
        ribbon.grid(row=0, column=0, sticky="ew")
        self._settings_ribbon = ribbon
        self._build_buttons(ribbon, 0, save_text="설정 저장")

        overview_card = tk.Frame(
            main,
            bg=COLORS.surface_subtle,
            highlightbackground=COLORS.border,
            highlightthickness=1,
            bd=0,
        )
        overview_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        overview_card.columnconfigure(0, weight=1)
        overview = ttk.Frame(overview_card, style="Overview.TFrame")
        overview.grid(row=0, column=0, sticky="ew")
        self._settings_overview = overview

        flow_inner = ttk.Frame(overview, style="Overview.TFrame", padding=(12, 6))
        flow_inner.columnconfigure(0, weight=1)
        self._settings_flow_panel = flow_inner
        self._build_settings_flow(flow_inner)

        validation_inner = ttk.Frame(overview, style="Overview.TFrame", padding=(12, 6))
        validation_inner.columnconfigure(0, weight=1)
        self._settings_validation_panel = validation_inner
        self._build_validation_section(validation_inner, 0)
        self._layout_settings_overview(compact=False)

        self._settings_workbench = ttk.Frame(main, style="Body.TFrame")
        self._settings_workbench.grid(row=3, column=0, sticky="nsew")

        self._settings_primary_column = ttk.Frame(self._settings_workbench, style="Body.TFrame")
        self._settings_primary_column.columnconfigure(0, weight=1)
        self._build_printer_section(self._settings_primary_column, 0)
        self._build_connection_section(self._settings_primary_column, 1)

        self._settings_secondary_column = ttk.Frame(self._settings_workbench, style="Body.TFrame")
        self._settings_secondary_column.columnconfigure(0, weight=1)
        self._build_label_section(self._settings_secondary_column, 0)
        self._build_barcode_section(self._settings_secondary_column, 1)

        self._layout_settings_workbench(compact=False)

    def _on_settings_content_configure(self, _event: tk.Event | None = None) -> None:
        bounds = self._settings_canvas.bbox("all")
        self._settings_canvas.configure(scrollregion=bounds)
        if bounds is not None and bounds[3] - bounds[1] > self._settings_canvas.winfo_height():
            self._settings_scrollbar.grid()
            return
        self._settings_scrollbar.grid_remove()
        self._settings_canvas.yview_moveto(0)

    def _on_settings_canvas_configure(self, event: tk.Event) -> None:
        viewport_width = max(1, int(event.width))
        self._settings_canvas.itemconfigure(self._settings_main_window, width=viewport_width)
        compact = viewport_width < 900
        self._layout_settings_ribbon(compact=viewport_width < 720)
        self._layout_settings_overview(compact=compact)
        self._layout_settings_workbench(compact=compact)
        self.after_idle(self._on_settings_content_configure)

    def _layout_settings_ribbon(self, *, compact: bool) -> None:
        ribbon = self._settings_ribbon
        for column in range(4):
            ribbon.columnconfigure(column, weight=0, minsize=0, uniform="")
        if compact:
            for column in range(2):
                ribbon.columnconfigure(column, weight=1, uniform="settings_ribbon_compact")
            for index, button in enumerate(self._settings_ribbon_buttons):
                row, column = divmod(index, 2)
                button.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=(0, 6 if row == 0 else 0))
            return
        for column in range(4):
            ribbon.columnconfigure(column, weight=1, uniform="settings_ribbon")
        for index, button in enumerate(self._settings_ribbon_buttons):
            button.grid(row=0, column=index, sticky="ew", padx=(0, 8) if index < 3 else 0, pady=0)

    def _layout_settings_overview(self, *, compact: bool) -> None:
        overview = self._settings_overview
        for column in range(2):
            overview.columnconfigure(column, weight=0, minsize=0)
        if compact:
            overview.columnconfigure(0, weight=1)
            self._settings_flow_panel.grid(row=0, column=0, sticky="ew")
            self._settings_validation_panel.grid(row=1, column=0, sticky="ew")
            self._settings_validation_summary.configure(wraplength=380)
            return
        overview.columnconfigure(0, weight=1, uniform="settings_overview")
        overview.columnconfigure(1, weight=1, uniform="settings_overview")
        self._settings_flow_panel.grid(row=0, column=0, sticky="nsew")
        self._settings_validation_panel.grid(row=0, column=1, sticky="nsew")
        self._settings_validation_summary.configure(wraplength=340)

    def _layout_settings_workbench(self, *, compact: bool) -> None:
        workbench = self._settings_workbench
        workbench.columnconfigure(0, weight=1, minsize=0, uniform="settings_columns")
        workbench.columnconfigure(1, weight=1, minsize=0, uniform="settings_columns")
        workbench.rowconfigure(0, weight=1)
        workbench.rowconfigure(1, weight=0)
        if compact:
            self._settings_primary_column.grid(row=0, column=0, columnspan=2, sticky="nsew")
            self._settings_secondary_column.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
            return
        self._settings_primary_column.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self._settings_secondary_column.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    def _build_settings_flow(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="1 장비  2 연결  3 용지  4 바코드  5 저장",
            style="OverviewTitle.TLabel",
            wraplength=430,
        ).grid(row=0, column=0, sticky="w")

    def _build_printer_section(self, parent: ttk.Frame, row: int) -> None:
        frame = self._section_card(parent, row, "1. 장비와 출력")
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="제조사").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=3)
        self.brand_box = ttk.Combobox(
            frame, textvariable=self.brand_var, values=list(BRAND_VALUES), state="readonly", width=18
        )
        self.brand_box.grid(row=0, column=1, sticky="ew", pady=3)
        self.brand_box.bind("<<ComboboxSelected>>", self._sync_media_handling_state)
        ttk.Label(frame, text="\uc778\uc1c4 \ubc29\uc2dd").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=3)
        method_frame = ttk.Frame(frame, style="Surface.TFrame")
        method_frame.grid(row=1, column=1, sticky="w", pady=3)
        for label in PRINT_METHOD_VALUES:
            ttk.Radiobutton(method_frame, text=label, value=label, variable=self.print_method_var).pack(side="left", padx=(0, 12))
        ttk.Label(frame, text="인쇄후작업").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=3)
        handling_frame = ttk.Frame(frame, style="Surface.TFrame")
        handling_frame.grid(row=2, column=1, sticky="w", pady=3)
        self.media_handling_buttons: dict[str, ttk.Radiobutton] = {}
        for label, value in MEDIA_HANDLING_VALUES.items():
            button = ttk.Radiobutton(handling_frame, text=label, value=label, variable=self.media_handling_var)
            button.pack(side="left", padx=(0, 12))
            self.media_handling_buttons[value] = button
        ttk.Label(frame, text="\uc778\uc1c4 \ubc29\ud5a5").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=3)
        orientation_frame = ttk.Frame(frame, style="Surface.TFrame")
        orientation_frame.grid(row=3, column=1, sticky="w", pady=3)
        for label in PRINT_ORIENTATION_VALUES:
            ttk.Radiobutton(orientation_frame, text=label, value=label, variable=self.print_orientation_var).pack(side="left", padx=(0, 12))
        ttk.Label(frame, text="\ucd9c\ub825 \uac15\ub3c4").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=3)
        tuning_frame = ttk.Frame(frame, style="Surface.TFrame")
        tuning_frame.grid(row=4, column=1, sticky="ew", pady=3)
        for col in range(2):
            tuning_frame.columnconfigure(col, weight=1)
        for column, (label, variable, minimum, maximum) in enumerate(
            (
                ("속도", self.print_speed_var, 1, 20),
                ("농도", self.print_density_var, 0, 30),
            )
        ):
            control = ttk.Frame(tuning_frame, style="Surface.TFrame")
            control.grid(row=0, column=column, sticky="ew", padx=(0, 8) if column == 0 else 0)
            control.columnconfigure(1, weight=1)
            ttk.Label(control, text=label).grid(row=0, column=0, sticky="w", padx=(0, 5))
            self._number_stepper(control, variable, minimum, maximum).grid(row=0, column=1, sticky="ew")

    def _build_connection_section(self, parent: ttk.Frame, row: int) -> None:
        frame = self._section_card(parent, row, "2. 연결")
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="\ubc29\uc2dd").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=3)
        mode_frame = ttk.Frame(frame, style="Surface.TFrame")
        mode_frame.grid(row=0, column=1, sticky="w", pady=3)
        for label in MODE_VALUES:
            ttk.Radiobutton(mode_frame, text=label, value=label, variable=self.mode_var, command=self._sync_connection_state).pack(
                side="left", padx=(0, 12)
            )

        network_row = ttk.Frame(frame, style="Surface.TFrame")
        network_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        network_row.columnconfigure(0, weight=3)
        network_row.columnconfigure(1, weight=1)
        self.ip_label = ttk.Label(network_row, text="\ud504\ub9b0\ud130 IP")
        self.ip_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.ip_entry = ttk.Entry(network_row, textvariable=self.ip_var, width=15)
        self.ip_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.port_label = ttk.Label(network_row, text="\ud3ec\ud2b8")
        self.port_label.grid(row=0, column=1, sticky="w", pady=(0, 2))
        self.port_entry = ttk.Entry(network_row, textvariable=self.port_var, width=6)
        self.port_entry.grid(row=1, column=1, sticky="ew")

        printer_group = ttk.Frame(frame, style="Surface.TFrame")
        printer_group.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        printer_group.columnconfigure(0, weight=1)
        self.printer_label = ttk.Label(printer_group, text="Windows \ud504\ub9b0\ud130 \uc774\ub984")
        self.printer_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        printer_row = ttk.Frame(printer_group, style="Surface.TFrame")
        printer_row.grid(row=1, column=0, sticky="ew")
        printer_row.columnconfigure(0, weight=1)
        self.printer_box = ttk.Combobox(
            printer_row, textvariable=self.printer_name_var, values=self.printer_names, width=14
        )
        self.printer_box.grid(row=0, column=0, sticky="ew")
        ttk.Button(printer_row, text="\ubaa9\ub85d \uc0c8\ub85c\uace0\uce68", command=self.refresh_printers, style="Secondary.TButton").grid(row=0, column=1, padx=(8, 0))

    def _build_label_section(self, parent: ttk.Frame, row: int) -> None:
        frame = self._section_card(parent, row, "3. 용지")
        for col in range(4):
            frame.columnconfigure(col, weight=1)
        entries = [
            ("\uac00\ub85c(mm)", self.width_var),
            ("\uc138\ub85c(mm)", self.height_var),
            ("\uac04\uaca9(mm)", self.gap_var),
            ("DPI", self.dpi_var),
        ]
        for idx, (label, var) in enumerate(entries):
            ttk.Label(frame, text=label).grid(row=0, column=idx, sticky="w", padx=(0 if idx == 0 else 8, 2), pady=(0, 2))
            widget = (
                ttk.Combobox(frame, textvariable=var, values=["203", "300", "600"], width=6)
                if label == "DPI"
                else ttk.Entry(frame, textvariable=var, width=6)
            )
            widget.grid(row=1, column=idx, sticky="ew", padx=(0 if idx == 0 else 8, 2))
        ttk.Label(frame, text="용지 유형").grid(row=2, column=0, sticky="w", pady=(8, 2))
        ttk.Combobox(
            frame,
            textvariable=self.media_type_var,
            values=list(MEDIA_TYPE_VALUES),
            state="readonly",
            width=16,
        ).grid(
            row=3, column=0, columnspan=4, sticky="ew"
        )

    def _build_barcode_section(self, parent: ttk.Frame, row: int) -> None:
        frame = self._section_card(parent, row, "4. 바코드")
        for col in range(3):
            frame.columnconfigure(col, weight=1)

        self._labeled_widget(
            frame,
            0,
            0,
            "\uc885\ub958",
            ttk.Combobox(
                frame,
                textvariable=self.barcode_type_var,
                values=list(BARCODE_TYPE_VALUES),
                state="readonly",
                width=14,
            ),
        )
        ttk.Checkbutton(
            frame,
            text="자동 가운데 배치",
            variable=self.barcode_auto_layout_var,
            command=self._sync_barcode_layout_state,
        ).grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 2), pady=(0, 4))
        ttk.Label(
            frame,
            text="자동 배치가 켜져 있으면 X/Y는 라벨 크기에 맞춰 자동 계산됩니다.",
            style="Status.TLabel",
            wraplength=300,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 2))
        self.barcode_x_entry = ttk.Entry(frame, textvariable=self.barcode_x_var, width=7)
        self.barcode_y_entry = ttk.Entry(frame, textvariable=self.barcode_y_var, width=7)
        self._labeled_widget(frame, 3, 1, "X", self.barcode_x_entry)
        self._labeled_widget(frame, 3, 2, "Y", self.barcode_y_entry)

    def _build_validation_section(self, parent: ttk.Frame, row: int) -> None:
        frame = ttk.Frame(parent, style="Overview.TFrame")
        frame.grid(row=row, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)
        heading = ttk.Frame(frame, style="Overview.TFrame")
        heading.grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(heading, text="저장 전 점검", style="OverviewTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(heading, text="설정 점검 결과", style="OverviewBody.TLabel").grid(row=1, column=0, sticky="w")
        self._settings_validation_summary = ttk.Label(
            frame,
            textvariable=self.validation_var,
            style="Validation.TLabel",
            wraplength=340,
        )
        self._settings_validation_summary.grid(row=0, column=1, sticky="ew")

    def _labeled_widget(self, parent: ttk.Frame, row: int, column: int, text: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky="w", padx=(0 if column == 0 else 8, 2), pady=(0, 2))
        widget.grid(row=row + 1, column=column, sticky="ew", padx=(0 if column == 0 else 8, 2), pady=(0, 4))

    def _number_stepper(self, parent: ttk.Frame, variable: tk.StringVar, minimum: int, maximum: int) -> tk.Widget:
        if hasattr(ttk, "Spinbox"):
            return ttk.Spinbox(
                parent,
                from_=minimum,
                to=maximum,
                increment=1,
                textvariable=variable,
                width=5,
            )
        return tk.Spinbox(
            parent,
            from_=minimum,
            to=maximum,
            increment=1,
            textvariable=variable,
            width=5,
            bg=COLORS.surface,
            fg=COLORS.text_primary,
            relief="solid",
            bd=1,
        )

    def _section_card(self, parent: ttk.Frame, row: int, title: str) -> ttk.Frame:
        card = tk.Frame(parent, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        card.columnconfigure(0, weight=1)
        title_bar = tk.Frame(card, bg=COLORS.surface_muted, height=30)
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.columnconfigure(0, weight=1)
        tk.Label(
            title_bar,
            text=title,
            bg=COLORS.surface_muted,
            fg=COLORS.text_primary,
            font=TYPOGRAPHY.section_title,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=4)
        inner = ttk.Frame(card, style="Surface.TFrame", padding=(12, 6, 12, 7))
        inner.grid(row=1, column=0, sticky="ew")
        inner.columnconfigure(0, weight=0)
        return inner

    def _build_buttons(self, parent: ttk.Frame, row: int, *, save_text: str) -> None:
        buttons = ttk.Frame(parent, style="Ribbon.TFrame")
        buttons.grid(row=row, column=0, sticky="ew")
        self._settings_ribbon_buttons = (
            ttk.Button(buttons, text="다시 불러오기", command=self.load_from_file, style="Secondary.TButton"),
            ttk.Button(buttons, text="연결 확인", command=self.check_connection, style="Secondary.TButton"),
            ttk.Button(buttons, text="설정 점검", command=self.validate_current_settings, style="Secondary.TButton"),
            ttk.Button(buttons, text=save_text, command=self.save_to_file, style="Primary.TButton"),
        )
        self._settings_ribbon = buttons
        self._layout_settings_ribbon(compact=False)

    def load_from_file(self, *, confirm_discard: bool = True) -> None:
        if confirm_discard and self._settings_dirty:
            should_reload = messagebox.askyesno(
                "현재 설정 다시 불러오기",
                "저장하지 않은 변경사항이 있습니다. 현재 파일의 설정으로 되돌릴까요?",
                parent=self,
            )
            if not should_reload:
                return
        try:
            settings = load_settings(self.config_path)
        except Exception as exc:
            messagebox.showerror("\uc124\uc815 \uc77d\uae30 \uc2e4\ud328", str(exc))
            return
        self._suspend_dirty_tracking = True
        self.brand_var.set(BRAND_LABELS[settings.brand])
        self._saved_model = settings.model
        self.mode_var.set(MODE_LABELS[settings.mode])
        self.print_method_var.set(PRINT_METHOD_LABELS[settings.print_method])
        self.print_orientation_var.set(PRINT_ORIENTATION_LABELS[settings.print_orientation])
        self.media_handling_var.set(MEDIA_HANDLING_LABELS[settings.media_handling])
        self.ip_var.set(settings.ip)
        self.port_var.set(str(settings.port))
        self.printer_name_var.set("" if settings.windows_printer_name == "auto" else settings.windows_printer_name)
        self.width_var.set(str(settings.width_mm))
        self.height_var.set(str(settings.height_mm))
        self.dpi_var.set(str(settings.dpi))
        self.gap_var.set(_format_float(settings.gap_mm))
        self.media_type_var.set(MEDIA_TYPE_LABELS[settings.media_type])
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
        self._sync_media_handling_state()
        self._sync_connection_state()
        self._sync_barcode_layout_state()
        self._suspend_dirty_tracking = False
        self._set_settings_dirty(False)
        self.status_var.set("\ud604\uc7ac \uc124\uc815\uc744 \ubd88\ub7ec\uc654\uc2b5\ub2c8\ub2e4.")
        self._update_validation_summary()

    def _save_shortcut(self, _event: tk.Event | None = None) -> str:
        self.save_to_file()
        return "break"

    def save_to_file(self) -> None:
        try:
            settings = self._collect_settings()
            save_settings(self.config_path, settings)
        except Exception as exc:
            self.validation_var.set(f"저장 전 점검 필요: {exc}")
            messagebox.showwarning("설정 확인", str(exc))
            return
        self._update_validation_summary(settings)
        self._set_settings_dirty(False)
        self.status_var.set("설정을 저장했습니다. 다음 출력부터 적용됩니다.")

    def _install_dirty_tracking(self) -> None:
        for variable in self._settings_variables():
            variable.trace_add("write", self._mark_settings_dirty)

    def _settings_variables(self) -> tuple[tk.Variable, ...]:
        return (
            self.brand_var,
            self.mode_var,
            self.print_method_var,
            self.print_orientation_var,
            self.media_handling_var,
            self.print_speed_var,
            self.print_density_var,
            self.ip_var,
            self.port_var,
            self.printer_name_var,
            self.width_var,
            self.height_var,
            self.dpi_var,
            self.gap_var,
            self.media_type_var,
            self.barcode_type_var,
            self.barcode_auto_layout_var,
            self.barcode_x_var,
            self.barcode_y_var,
        )

    def _mark_settings_dirty(self, *_args: object) -> None:
        if self._suspend_dirty_tracking:
            return
        self._set_settings_dirty(True)
        self.status_var.set("변경사항 있음 · 저장 필요")

    def _set_settings_dirty(self, dirty: bool) -> None:
        self._settings_dirty = dirty
        self.title(f"{self._base_title}{' *' if dirty else ''}")

    def _confirm_close(self) -> None:
        if self._settings_dirty and not messagebox.askyesno(
            "저장하지 않은 변경사항",
            "저장하지 않은 변경사항이 있습니다. 저장하지 않고 닫을까요?",
            parent=self,
        ):
            return
        self.destroy()

    def refresh_printers(self) -> None:
        self.printer_names = installed_printers()
        self.printer_box.configure(values=self.printer_names)
        self.status_var.set(f"프린터 목록 새로고침 · {len(self.printer_names)}개 발견")

    def check_connection(self) -> None:
        try:
            settings = self._collect_settings()
        except Exception as exc:
            self.validation_var.set(f"연결 확인 전 설정 수정 필요: {exc}")
            messagebox.showwarning("설정 확인", str(exc))
            return
        if settings.mode == "network":
            try:
                check_network(settings.ip, settings.port)
            except PrinterError as exc:
                messagebox.showerror("\uc5f0\uacb0 \uc2e4\ud328", f"{settings.ip}:{settings.port} \uc5f0\uacb0\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.\n{exc}")
                return
            self.status_var.set(f"LAN 연결 성공 · {settings.ip}:{settings.port}")
            return
        printers = installed_printers()
        if settings.windows_printer_name in printers:
            self.status_var.set(f"Windows 프린터 확인 · {settings.windows_printer_name}")
        else:
            messagebox.showwarning("\ud504\ub9b0\ud130 \ud655\uc778 \ud544\uc694", "\uc785\ub825\ud55c \ud504\ub9b0\ud130 \uc774\ub984\uc774 Windows \ud504\ub9b0\ud130 \ubaa9\ub85d\uc5d0\uc11c \ubcf4\uc774\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.")

    def validate_current_settings(self) -> None:
        try:
            settings = self._collect_settings()
        except Exception as exc:
            self.validation_var.set(f"수정 필요: {exc}")
            messagebox.showwarning("설정 확인", str(exc))
            return
        self._update_validation_summary(settings)
        self.status_var.set("설정 점검을 완료했습니다.")

    def _update_validation_summary(self, settings: PrinterSettings | None = None) -> None:
        if settings is None:
            try:
                settings = self._collect_settings()
            except Exception as exc:
                self.validation_var.set(f"수정 필요: {exc}")
                return
        report = validate_settings(settings)
        if report.errors:
            self.validation_var.set("수정 필요: " + " / ".join(report.errors))
            return
        if report.warnings:
            self.validation_var.set("저장 가능, 확인 필요: " + " / ".join(report.warnings))
            return
        self.validation_var.set("저장 가능: 필수 설정이 정상입니다.")

    def _collect_settings(self) -> PrinterSettings:
        settings = PrinterSettings(
            brand=BRAND_VALUES.get(self.brand_var.get(), ""),
            model=self._saved_model,
            mode=MODE_VALUES.get(self.mode_var.get(), ""),
            print_method=PRINT_METHOD_VALUES.get(self.print_method_var.get(), ""),
            print_orientation=PRINT_ORIENTATION_VALUES.get(self.print_orientation_var.get(), ""),
            media_handling=MEDIA_HANDLING_VALUES.get(self.media_handling_var.get(), ""),
            ip=self.ip_var.get().strip(),
            port=_parse_int_field(self.port_var.get(), "포트", default=9100),
            windows_printer_name=self.printer_name_var.get().strip(),
            width_mm=_parse_int_field(self.width_var.get(), "용지 가로(mm)"),
            height_mm=_parse_int_field(self.height_var.get(), "용지 세로(mm)"),
            dpi=_parse_int_field(self.dpi_var.get(), "DPI"),
            gap_mm=_parse_float_field(self.gap_var.get(), "간격(mm)", default=0),
            media_type=MEDIA_TYPE_VALUES.get(self.media_type_var.get(), ""),
            print_speed=_parse_int_field(self.print_speed_var.get(), "인쇄속도"),
            print_density=_parse_int_field(self.print_density_var.get(), "농도"),
            barcode_type=BARCODE_TYPE_VALUES.get(self.barcode_type_var.get(), ""),
            barcode_auto_layout=bool(self.barcode_auto_layout_var.get()),
            barcode_x=_parse_int_field(self.barcode_x_var.get(), "바코드 X", default=0),
            barcode_y=_parse_int_field(self.barcode_y_var.get(), "바코드 Y", default=0),
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
        for label in (self.ip_label, self.port_label):
            label.configure(state=network_state)
        self.printer_label.configure(state=usb_state)

    def _sync_media_handling_state(self, _event: object | None = None) -> None:
        brand = BRAND_VALUES.get(self.brand_var.get(), "")
        supported = supported_media_handling_for_brand(brand)
        current = MEDIA_HANDLING_VALUES.get(self.media_handling_var.get(), "")
        if current not in supported:
            self.media_handling_var.set(MEDIA_HANDLING_LABELS["tear_off"])
        for value, button in self.media_handling_buttons.items():
            button.configure(state="normal" if value in supported else "disabled")

    def _sync_barcode_layout_state(self) -> None:
        state = "disabled" if self.barcode_auto_layout_var.get() else "normal"
        for widget in (self.barcode_x_entry, self.barcode_y_entry):
            widget.configure(state=state)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Edit label printer settings.")
    parser.add_argument("--config", default=None, help="Path to config.ini")
    parser.add_argument("--base-dir", default=None, help="Folder containing config.ini")
    parser.add_argument("--show-config-path", action="store_true", help="Print the config path and exit")
    parser.add_argument("--smoke-test", action="store_true", help="Load settings and exit without showing the UI")
    parser.add_argument("--ui-smoke-test", action="store_true", help="Create the Tk UI once and exit")
    args = parser.parse_args(argv)

    if args.config:
        config_path = Path(args.config)
    elif args.base_dir:
        config_path = Path(args.base_dir).resolve() / "config.ini"
    else:
        config_path = config_path_for_app()
    if args.show_config_path:
        print(config_path)
        return 0
    if args.smoke_test:
        load_settings(config_path)
        return 0
    if args.ui_smoke_test:
        app = SettingsApp(config_path)
        app.update_idletasks()
        app.destroy()
        return 0

    app = SettingsApp(config_path)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
