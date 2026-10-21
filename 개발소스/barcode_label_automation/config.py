from __future__ import annotations

import codecs
import json
import math
from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path

from .barcode_catalog import SUPPORTED_BARCODE_TYPES
from .errors import ConfigError
from .runtime_paths import runtime_base_dir
from .printer_offsets import validate_offsets


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
    width_mm: float
    height_mm: float
    dpi: int
    gap_mm: float
    media_type: str
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    gap_offset_mm: float | None = None
    feed_offset_mm: float | None = None
    bixolon_extended_stop: bool = False


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
    encoder_options: dict[str, object] = field(default_factory=dict)


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
SUPPORTED_PRINT_ORIENTATIONS = {"normal", "landscape", "rotate_180", "landscape_180"}
SUPPORTED_MEDIA_HANDLING = {"tear_off", "cutter", "peeler", "printer_default"}
SUPPORTED_MEDIA_TYPES = {"gap", "black_mark", "continuous"}
SUPPORTED_MEDIA_HANDLING_BY_LANGUAGE = {
    "slcs": {"tear_off", "cutter", "printer_default"},
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


def load_config(path: str | Path = "config.ini") -> AppConfig:
    config_path = Path(path)
    parser = ConfigParser(interpolation=None)
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
        raise ConfigError("인쇄 방향은 세로, 가로, 세로 180도, 가로 180도 중 하나여야 합니다.")
    media_handling = parser.get("printer", "media_handling", fallback="tear_off").strip().lower()
    if media_handling not in SUPPORTED_MEDIA_HANDLING:
        raise ConfigError("printer.media_handling must be 'tear_off', 'cutter', 'peeler', or 'printer_default'.")
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

    offsets = {key: read_media_number(parser, key, default=("0" if key in {"offset_x_mm", "offset_y_mm"} or (key == "gap_offset_mm" and language == "tspl") else "auto"))
               for key in ("offset_x_mm", "offset_y_mm", "gap_offset_mm", "feed_offset_mm")}
    offsets["gap_offset_mm"] = read_gap_offset(parser, brand, language)
    if read_media_number(parser, "gap_mm", default="0") < 0:
        raise ConfigError("라벨 간격은 0 이상의 유한한 숫자여야 합니다.")
    if any(abs(offsets[key]) > 300 for key in ("offset_x_mm", "offset_y_mm")):
        raise ConfigError("좌우·상하 보정은 -300~300mm 사이여야 합니다.")
    gap_offset, feed_offset = offsets["gap_offset_mm"], offsets["feed_offset_mm"]
    try:
        extended_stop = parser.getboolean("label", "bixolon_extended_stop", fallback=False)
    except ValueError as exc:
        raise ConfigError("label.bixolon_extended_stop: yes 또는 no로 지정하세요.") from exc
    if media_handling == "printer_default" and (gap_offset is not None or feed_offset is not None):
        raise ConfigError("본체 커터·센서 설정 유지에서는 두 오프셋을 현재 프린터 설정 사용(auto)으로 선택하세요.")
    try:
        validate_offsets(language, media_type, read_label_dimension(parser, "height_mm"),
                         parser.getint("label", "dpi"), gap_offset, feed_offset,
                         brand=brand, model=model, extended_stop=extended_stop)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
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
            width_mm=read_label_dimension(parser, "width_mm"),
            height_mm=read_label_dimension(parser, "height_mm"),
            dpi=parser.getint("label", "dpi"),
            gap_mm=parser.getfloat("label", "gap_mm"),
            media_type=media_type,
            offset_x_mm=read_media_number(parser, "offset_x_mm", default="0"),
            offset_y_mm=read_media_number(parser, "offset_y_mm", default="0"),
            gap_offset_mm=gap_offset,
            feed_offset_mm=feed_offset,
            bixolon_extended_stop=extended_stop,
        ),
        barcode=_read_barcode_config(parser, language),
        data=DataConfig(excel_file=excel_file, output_dir=output_dir),
    )


def read_media_number(parser: ConfigParser, key: str, *, default: str = "auto") -> float | None:
    raw = parser.get("label", key, fallback=default).strip().lower()
    if raw == "auto" and key in {"gap_offset_mm", "feed_offset_mm"}:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"label.{key}: 유한한 숫자를 입력하세요.") from exc
    if not math.isfinite(value):
        raise ConfigError(f"label.{key}: 유한한 숫자를 입력하세요.")
    return value


def read_gap_offset(parser: ConfigParser, brand: str, language: str | None = None) -> float | None:
    language = language or DEFAULT_LANGUAGE_BY_BRAND.get(brand)
    value = read_media_number(parser, "gap_offset_mm", default="0" if language == "tspl" else "auto")
    # Before manufacturer offsets existed, the disabled BIXOLON control saved
    # zero even though no SL p4 was sent. Preserve that device state on upgrade.
    # New settings saves mark intentional zero so a user can explicitly reset it.
    if brand == "bixolon" and language == "slcs" and value == 0 and parser.get(
        "label", "offsets_profile", fallback=""
    ).strip().lower() != "bixolon":
        return None
    return value


def read_label_dimension(parser: ConfigParser, key: str) -> float:
    value = read_media_number(parser, key, default="0")
    dpi = parser.getint("label", "dpi", fallback=203)
    if value is None or not 0 < value <= 300 or round(value / 25.4 * dpi) < 1:
        raise ConfigError("용지 가로·세로는 0보다 크고 300mm 이하이며 최소 1도트여야 합니다.")
    return value


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
            "barcode.type must be one of: " + ", ".join(sorted(SUPPORTED_BARCODE_TYPES))
        )

    encoder_options = read_encoder_options(parser, barcode_type)

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
        encoder_options=encoder_options,
    )


def _read_one_d_wide(parser: ConfigParser, language: str) -> int:
    raw_wide = parser.get("barcode.1d", "wide", fallback="auto").strip().lower()
    if raw_wide in {"", "auto"}:
        return 6 if language == "slcs" else 2
    try:
        return int(raw_wide)
    except ValueError as exc:
        raise ConfigError("barcode.1d.wide must be an integer or 'auto'.") from exc


def read_encoder_options(parser: ConfigParser, barcode_type: str) -> dict[str, object]:
    """Read explicit advanced settings without interpolation or silent loss."""
    from .barcode_catalog import option_definitions
    raw = parser.get("barcode", "options_json", fallback="{}", raw=True)
    try:
        options = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ConfigError("barcode.options_json must be a JSON object.") from exc
    if not isinstance(options, dict):
        raise ConfigError("barcode.options_json must be a JSON object.")
    definitions = option_definitions(barcode_type)
    for key, value in options.items():
        if key not in definitions:
            raise ConfigError(f"Unsupported {barcode_type} option: {key}")
        spec = definitions[key]
        if spec.get("type") == "bool":
            valid = isinstance(value, bool)
        elif spec.get("type") == "text":
            valid = isinstance(value, str) and len(value) <= 10000
        elif "choices" in spec:
            valid = value in spec["choices"]
        elif spec.get("type") == "float":
            valid = isinstance(value, (int, float)) and not isinstance(value, bool) and spec["min"] <= value <= spec["max"] and math.isfinite(value)
        else:
            valid = isinstance(value, int) and not isinstance(value, bool) and spec["min"] <= value <= spec["max"]
        if not valid:
            raise ConfigError(f"Invalid barcode option {key}: {value!r}")
    return options
