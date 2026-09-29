from __future__ import annotations

import codecs
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError
from .runtime_paths import runtime_base_dir


@dataclass(frozen=True)
class PrinterConfig:
    brand: str
    model: str
    mode: str
    print_method: str
    print_orientation: str
    media_handling: str
    print_speed: int
    print_density: int
    language: str
    command_encoding: str
    ip: str
    port: int
    windows_printer_name: str


@dataclass(frozen=True)
class LabelConfig:
    width_mm: int
    height_mm: int
    dpi: int
    gap_mm: float
    media_type: str


@dataclass(frozen=True)
class BarcodeConfig:
    barcode_type: str
    auto_layout: bool
    x: int
    y: int
    rotation: int
    one_d_height: int
    one_d_narrow: int
    one_d_wide: int
    one_d_human_readable: bool
    qr_model: int
    qr_ecc: str
    qr_cell_size: int
    datamatrix_cell_size: int
    pdf417_rows: int
    pdf417_columns: int
    pdf417_security_level: int
    pdf417_module_width: int
    pdf417_module_height: int


@dataclass(frozen=True)
class DataConfig:
    excel_file: Path
    output_dir: Path


@dataclass(frozen=True)
class AppConfig:
    printer: PrinterConfig
    label: LabelConfig
    barcode: BarcodeConfig
    data: DataConfig


DEFAULTS = {
    "printer": {
        "brand": "bixolon",
        "model": "",
        "mode": "network",
        "print_method": "direct_thermal",
        "print_orientation": "normal",
        "media_handling": "tear_off",
        "speed": "auto",
        "density": "auto",
        "language": "auto",
        "command_encoding": "auto",
        "ip": "192.168.0.50",
        "port": "9100",
        "windows_printer_name": "auto",
    },
    "brand.bixolon": {
        "language": "slcs",
        "command_encoding": "cp949",
        "windows_printer_name": "BIXOLON Label Printer",
    },
    "brand.tsc": {
        "language": "tspl",
        "command_encoding": "utf-8",
        "windows_printer_name": "TSC Label Printer",
    },
    "brand.zebra": {
        "language": "zpl",
        "command_encoding": "utf-8",
        "windows_printer_name": "ZDesigner Label Printer",
    },
    "brand.sewoo": {
        "language": "zpl",
        "command_encoding": "utf-8",
        "windows_printer_name": "SEWOO Label Printer",
    },
    "label": {
        "width_mm": "60",
        "height_mm": "40",
        "dpi": "203",
        "gap_mm": "3",
        "media_type": "gap",
    },
    "barcode": {
        "type": "code128",
        "auto_layout": "yes",
        "x": "130",
        "y": "115",
        "rotation": "0",
    },
    "barcode.1d": {
        "height": "80",
        "narrow": "2",
        "wide": "auto",
        "human_readable": "yes",
    },
    "barcode.qr": {
        "model": "2",
        "ecc": "M",
        "cell_size": "4",
    },
    "barcode.datamatrix": {
        "cell_size": "4",
    },
    "barcode.pdf417": {
        "rows": "30",
        "columns": "5",
        "security_level": "2",
        "module_width": "3",
        "module_height": "10",
    },
    "data": {
        "excel_file": "labels.xlsx",
        "output_dir": "out",
    },
}

DEFAULT_LANGUAGE_BY_BRAND = {
    "bixolon": "slcs",
    "tsc": "tspl",
    "zebra": "zpl",
    "sewoo": "zpl",
}

DEFAULT_ENCODING_BY_BRAND = {
    "bixolon": "cp949",
    "tsc": "utf-8",
    "zebra": "utf-8",
    "sewoo": "utf-8",
}

DEFAULT_SPEED_BY_LANGUAGE = {
    "slcs": 3,
    "tspl": 4,
    "zpl": 4,
}

DEFAULT_DENSITY_BY_LANGUAGE = {
    "slcs": 20,
    "tspl": 8,
    "zpl": 10,
}

SUPPORTED_LANGUAGES = {"slcs", "tspl", "zpl"}
SUPPORTED_PRINT_METHODS = {"direct_thermal", "thermal_transfer"}
SUPPORTED_PRINT_ORIENTATIONS = {"normal", "rotate_180"}
SUPPORTED_MEDIA_HANDLING = {"tear_off", "cutter", "peeler"}
SUPPORTED_MEDIA_TYPES = {"gap", "black_mark", "continuous"}
SUPPORTED_MEDIA_HANDLING_BY_LANGUAGE = {
    "slcs": {"tear_off", "cutter"},
    "tspl": {"tear_off", "cutter", "peeler"},
    "zpl": {"tear_off", "cutter", "peeler"},
}
SUPPORTED_MEDIA_HANDLING_BY_BRAND = {
    "sewoo": {"tear_off"},
}
# Keep this in sync with the approved-model table in docs/PRODUCT_PACKAGES.md.
# No SEWOO model is release-approved until model-specific manufacturer ZPL
# evidence and a physical output check have both been recorded.
APPROVED_SEWOO_ZPL_MODELS: frozenset[str] = frozenset()
SUPPORTED_BARCODE_TYPES = {"code128", "code39", "ean13", "ean8", "upca", "itf", "qr", "datamatrix", "pdf417"}


def load_config(path: str | Path = "config.ini") -> AppConfig:
    config_path = Path(path)
    parser = ConfigParser()
    parser.read_dict(DEFAULTS)
    if config_path.exists():
        parser.read(config_path, encoding="utf-8-sig")

    mode = parser.get("printer", "mode").strip().lower()
    brand = parser.get("printer", "brand", fallback="bixolon").strip().lower()
    if mode not in {"network", "windows_raw"}:
        raise ConfigError("printer.mode must be 'network' or 'windows_raw'.")
    if brand not in DEFAULT_LANGUAGE_BY_BRAND:
        raise ConfigError("printer.brand must be 'bixolon', 'tsc', 'zebra', or 'sewoo'.")
    model = parser.get("printer", "model", fallback="").strip()
    print_method = parser.get("printer", "print_method", fallback="direct_thermal").strip().lower()
    if print_method not in SUPPORTED_PRINT_METHODS:
        raise ConfigError("printer.print_method must be 'direct_thermal' or 'thermal_transfer'.")
    print_orientation = parser.get("printer", "print_orientation", fallback="normal").strip().lower()
    if print_orientation not in SUPPORTED_PRINT_ORIENTATIONS:
        raise ConfigError("printer.print_orientation must be 'normal' or 'rotate_180'.")
    media_handling = parser.get("printer", "media_handling", fallback="tear_off").strip().lower()
    if media_handling not in SUPPORTED_MEDIA_HANDLING:
        raise ConfigError("printer.media_handling must be 'tear_off', 'cutter', or 'peeler'.")
    media_type = parser.get("label", "media_type", fallback="gap").strip().lower()
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise ConfigError("label.media_type must be 'gap', 'black_mark', or 'continuous'.")
    language = _read_language(parser, brand)
    _validate_media_handling(brand, language, media_handling)
    _validate_model_approval(brand, model)
    command_encoding = _read_command_encoding(parser, brand)
    windows_printer_name = _read_windows_printer_name(parser, brand)
    print_speed = _read_print_tuning(parser, "speed", language, DEFAULT_SPEED_BY_LANGUAGE, 1, 20)
    print_density = _read_print_tuning(parser, "density", language, DEFAULT_DENSITY_BY_LANGUAGE, 0, 30)

    base_dir = config_path.parent if config_path.exists() else Path.cwd()
    data_base_dir = runtime_base_dir(base_dir)
    excel_file = _resolve_path(data_base_dir, parser.get("data", "excel_file"))
    output_dir = _resolve_path(data_base_dir, parser.get("data", "output_dir"))
    port = _read_optional_port(parser)

    return AppConfig(
        printer=PrinterConfig(
            brand=brand,
            model=model,
            mode=mode,
            print_method=print_method,
            print_orientation=print_orientation,
            media_handling=media_handling,
            print_speed=print_speed,
            print_density=print_density,
            language=language,
            command_encoding=command_encoding,
            ip=parser.get("printer", "ip").strip(),
            port=port,
            windows_printer_name=windows_printer_name,
        ),
        label=LabelConfig(
            width_mm=parser.getint("label", "width_mm"),
            height_mm=parser.getint("label", "height_mm"),
            dpi=parser.getint("label", "dpi"),
            gap_mm=parser.getfloat("label", "gap_mm"),
            media_type=media_type,
        ),
        barcode=_read_barcode_config(parser, language),
        data=DataConfig(excel_file=excel_file, output_dir=output_dir),
    )


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value.strip())
    return path if path.is_absolute() else base_dir / path


def _read_optional_port(parser: ConfigParser) -> int:
    raw_port = parser.get("printer", "port", fallback="").strip()
    if raw_port == "":
        return 0
    try:
        return int(raw_port)
    except ValueError as exc:
        raise ConfigError("printer.port must be an integer.") from exc


def _read_language(parser: ConfigParser, brand: str) -> str:
    raw_language = parser.get("printer", "language", fallback="auto").strip().lower()
    if raw_language in {"", "auto"}:
        language = parser.get(
            f"brand.{brand}",
            "language",
            fallback=DEFAULT_LANGUAGE_BY_BRAND.get(brand, ""),
        ).strip().lower()
    else:
        language = raw_language

    if language not in SUPPORTED_LANGUAGES:
        raise ConfigError("printer.language must be 'auto', 'slcs', 'tspl', or 'zpl'.")

    expected = DEFAULT_LANGUAGE_BY_BRAND.get(brand)
    if expected is not None and language != expected:
        raise ConfigError(f"printer.language for brand '{brand}' must be '{expected}' or 'auto'.")

    return language


def _read_windows_printer_name(parser: ConfigParser, brand: str) -> str:
    raw_name = parser.get("printer", "windows_printer_name", fallback="auto").strip()
    if raw_name and raw_name.lower() != "auto":
        return raw_name
    return parser.get(
        f"brand.{brand}",
        "windows_printer_name",
        fallback=DEFAULTS.get(f"brand.{brand}", {}).get("windows_printer_name", ""),
    ).strip()


def _read_command_encoding(parser: ConfigParser, brand: str) -> str:
    raw_encoding = parser.get("printer", "command_encoding", fallback="auto").strip()
    if raw_encoding == "" or raw_encoding.lower() == "auto":
        raw_encoding = parser.get(
            f"brand.{brand}",
            "command_encoding",
            fallback=DEFAULT_ENCODING_BY_BRAND.get(brand, "utf-8"),
        ).strip()

    try:
        codecs.lookup(raw_encoding)
    except LookupError as exc:
        raise ConfigError(f"printer.command_encoding is not supported: {raw_encoding}") from exc

    return raw_encoding


def _read_print_tuning(
    parser: ConfigParser,
    option: str,
    language: str,
    defaults: dict[str, int],
    minimum: int,
    maximum: int,
) -> int:
    raw_value = parser.get("printer", option, fallback="auto").strip().lower()
    if raw_value in {"", "auto"}:
        return defaults[language]
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"printer.{option} must be an integer or 'auto'.") from exc
    if value < minimum or value > maximum:
        raise ConfigError(f"printer.{option} must be between {minimum} and {maximum}.")
    return value


def supported_media_handling_for_brand(brand: str) -> set[str]:
    brand_supported = SUPPORTED_MEDIA_HANDLING_BY_BRAND.get(brand)
    if brand_supported is not None:
        return set(brand_supported)
    language = DEFAULT_LANGUAGE_BY_BRAND.get(brand, "")
    return set(SUPPORTED_MEDIA_HANDLING_BY_LANGUAGE.get(language, SUPPORTED_MEDIA_HANDLING))


def _validate_media_handling(brand: str, language: str, media_handling: str) -> None:
    supported = supported_media_handling_for_brand(brand)
    if media_handling in supported:
        return
    if brand == "sewoo":
        raise ConfigError(
            "SEWOO media handling is restricted to 'tear_off' until official model-specific evidence is approved."
        )
    if language == "slcs" and media_handling == "peeler":
        raise ConfigError("BIXOLON/SLCS peeler command is not supported yet. Use tear_off or cutter.")
    raise ConfigError(f"printer.media_handling '{media_handling}' is not supported for language '{language}'.")


def _validate_model_approval(brand: str, model: str) -> None:
    if is_printer_model_approved(brand, model):
        return
    raise ConfigError(
        "printer.model is not an approved SEWOO ZPL model. "
        "Record model-specific manufacturer evidence and approval in docs/PRODUCT_PACKAGES.md before use."
    )


def is_printer_model_approved(brand: str, model: str) -> bool:
    if brand != "sewoo":
        return True
    normalized_model = model.strip().casefold()
    return bool(normalized_model) and normalized_model in {
        approved.casefold() for approved in APPROVED_SEWOO_ZPL_MODELS
    }


def _read_barcode_config(parser: ConfigParser, language: str) -> BarcodeConfig:
    barcode_type = parser.get("barcode", "type", fallback="code128").strip().lower()
    if barcode_type in {"qrcode", "qr_code"}:
        barcode_type = "qr"
    if barcode_type in {"data_matrix", "dmatrix", "dm"}:
        barcode_type = "datamatrix"
    if barcode_type not in SUPPORTED_BARCODE_TYPES:
        raise ConfigError(
            "barcode.type must be one of: code128, code39, ean13, ean8, upca, itf, qr, datamatrix, pdf417."
        )

    qr_ecc = parser.get("barcode.qr", "ecc", fallback="M").strip().upper()
    if qr_ecc not in {"L", "M", "Q", "H"}:
        raise ConfigError("barcode.qr.ecc must be L, M, Q, or H.")

    return BarcodeConfig(
        barcode_type=barcode_type,
        auto_layout=parser.getboolean("barcode", "auto_layout", fallback=True),
        x=parser.getint("barcode", "x", fallback=130),
        y=parser.getint("barcode", "y", fallback=115),
        rotation=parser.getint("barcode", "rotation", fallback=0),
        one_d_height=parser.getint("barcode.1d", "height", fallback=80),
        one_d_narrow=parser.getint("barcode.1d", "narrow", fallback=2),
        one_d_wide=_read_one_d_wide(parser, language),
        one_d_human_readable=parser.getboolean("barcode.1d", "human_readable", fallback=True),
        qr_model=parser.getint("barcode.qr", "model", fallback=2),
        qr_ecc=qr_ecc,
        qr_cell_size=parser.getint("barcode.qr", "cell_size", fallback=4),
        datamatrix_cell_size=parser.getint("barcode.datamatrix", "cell_size", fallback=4),
        pdf417_rows=parser.getint("barcode.pdf417", "rows", fallback=30),
        pdf417_columns=parser.getint("barcode.pdf417", "columns", fallback=5),
        pdf417_security_level=parser.getint("barcode.pdf417", "security_level", fallback=2),
        pdf417_module_width=parser.getint("barcode.pdf417", "module_width", fallback=3),
        pdf417_module_height=parser.getint("barcode.pdf417", "module_height", fallback=10),
    )


def _read_one_d_wide(parser: ConfigParser, language: str) -> int:
    raw_wide = parser.get("barcode.1d", "wide", fallback="auto").strip().lower()
    if raw_wide in {"", "auto"}:
        return 6 if language == "slcs" else 2
    try:
        return int(raw_wide)
    except ValueError as exc:
        raise ConfigError("barcode.1d.wide must be an integer or 'auto'.") from exc
