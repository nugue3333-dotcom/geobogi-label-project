"""Use the designer's existing renderer for saved-label batch output."""
from __future__ import annotations

import hashlib
import json
import copy
from dataclasses import dataclass
from pathlib import Path


def template_digest(template: dict) -> str:
    """Use the same normalized document identity across designer and print engine."""
    from .label_designer_app import normalize_template
    normalized = normalize_template(template)
    normalized.pop("data_source", None)  # Reprints use their immutable recorded rows.
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DataIssue:
    row: int
    element: int
    name: str
    message: str


def renderer(template: dict, base_dir: Path, row: dict | None = None):
    from .label_designer_app import LabelDesignerApp
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = Path(base_dir)
    app.template = copy.deepcopy(template)
    app.elements = list(app.template.get("elements", []))
    app.preview_row = dict(row or {})
    return app


def validate_rows(template: dict, rows: list[dict], base_dir: Path, *, dpi: int = 203) -> list[DataIssue]:
    from .label_designer_app import TEMPLATE_FIELD_RE
    app = renderer(template, base_dir)
    app.template.setdefault("label", {})["dpi"] = dpi
    issues = []
    elements = list(app.elements)
    if not any(bool(e.get("printable", True)) for e in elements):
        return [DataIssue(0, 0, "도안", "출력할 개체가 없습니다. 개체를 추가하세요.")]
    for row_number, row in enumerate(rows, 1):
        for element_number, element in enumerate(elements, 1):
            if not bool(element.get("printable", True)):
                continue
            name = str(element.get("name") or element.get("type", "개체"))
            refs = {m.group(1).strip() for m in TEMPLATE_FIELD_RE.finditer(str(element.get("text", "")))}
            if str(element.get("field", "")).strip():
                refs.add(str(element["field"]).strip())
            for item in element.get("gs1_elements", []):
                if isinstance(item, dict) and item.get("source") == "db":
                    refs.add(str(item.get("field", "")))
            missing = sorted(ref for ref in refs if ref and ref not in row)
            if missing:
                issues.append(DataIssue(row_number, element_number, name, "DB 열이 없습니다: " + ", ".join(missing) + " · 열 연결을 수정하세요."))
                continue
            app.elements = [element]
            try:
                app._validate_output_row(row, row_number=row_number)
            except (ValueError, OSError, TypeError) as exc:
                issues.append(DataIssue(row_number, element_number, name, str(exc)))
    return issues


def render_command(template: dict, row: dict, config, base_dir: Path, copies: int) -> bytes:
    from .print_quantity import parse_print_quantity
    copies = parse_print_quantity(copies)
    app = renderer(template, base_dir, row)
    app.template.setdefault("label", {})["dpi"] = config.label.dpi
    app._validate_output_row(row, row_number=1)
    return app.render_designer_print_command(config, row, copies)


def render_preview(template: dict, row: dict, base_dir: Path):
    from .config import load_config
    app = renderer(template, base_dir, row)
    config_path = Path(base_dir) / "config.ini"
    if config_path.is_file():
        app.template.setdefault("label", {})["dpi"] = load_config(config_path).label.dpi
    return app.render_preview_image()
