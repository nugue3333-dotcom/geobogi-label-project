from __future__ import annotations

import inspect
import io
import json
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook
from PIL import Image, ImageChops, ImageDraw

from barcode_label_automation import label_designer_app
from barcode_label_automation.label_designer_app import (
    BARCODE_1D_BITMAP_TYPES,
    BARCODE_2D_BITMAP_TYPES,
    BARCODE_TYPES,
    DEFAULT_FONT_NAME,
    DESIGNER_PRINT_SUPPORTED_BARCODE_TYPES,
    FontFace,
    IMAGE_FILE_TYPES,
    LABEL_FILE_EXTENSION,
    LABEL_FILE_TYPES,
    LabelDesignerApp,
    _apply_inferred_barcode_values,
    _available_font_names,
    _barcode_image_to_transparent_rgba,
    _barcode_value_candidate_from_text,
    _calculate_canvas_label_layout,
    _clean_design_ocr_line_text,
    _data_field_option_maps,
    _design_template_elements_from_image,
    _db_headers_from_rows,
    _editable_shape_elements_from_image,
    _element,
    _fit_text_elements_around_barcodes,
    _fit_image_mm_size,
    _filter_data_source_row_indexes,
    _image_element_for_label,
    _font_registry,
    _load_font,
    _best_table_cell_text,
    _known_ribbon_reference_cell_text,
    _pixel_box_to_label_mm,
    _preferred_text_db_field,
    _ocr_text_from_box,
    _ocr_tsv_text_elements_from_image,
    _printer_settings_command,
    _resolve_tesseract_executable,
    _render_text_box_image,
    _save_design_image_asset,
    _set_table_axis_position,
    _table_axis_positions,
    _table_grid_from_image,
    _is_meaningful_design_text,
    load_template_file,
    main,
    _render_1d_barcode_image,
    _render_2d_barcode_image,
    _render_qr_code_image,
    _new_code_element_values,
    default_template,
    ensure_blank_default_template,
    normalize_template,
    render_element_text,
    render_template_text,
)
from barcode_label_automation.templates import mm_to_dots
from barcode_label_automation.print_progress import DESIGNER_PROGRESS_FILE_NAME, PrintProgress


def _generated_starter_template(width_mm: int, height_mm: int) -> dict[str, object]:
    return {
        "version": 1,
        "label": {"width_mm": width_mm, "height_mm": height_mm},
        "elements": [
            {"type": "text", "text": "{{item_name}}", "x": 3, "y": 6, "width": 44, "height": 6},
            {"type": "text", "text": "품목코드 {{item_code}}", "x": 3, "y": 13, "width": 44, "height": 4},
            {"type": "text", "text": "LOT {{lot_no}} / 수량 {{qty}}", "x": 3, "y": 19, "width": 44, "height": 4},
            {"type": "barcode", "text": "{{barcode}}", "x": 6, "y": 25, "width": 38, "height": 12},
        ],
    }


def test_render_template_text_replaces_db_fields():
    row = {"item_name": "SENSOR BRACKET", "barcode": "88023502", "qty": "100"}

    assert render_template_text("ITEM: {{item_name}} / {{barcode}} / {{qty}}", row) == "ITEM: SENSOR BRACKET / 88023502 / 100"


def test_render_template_text_removes_missing_db_fields() -> None:
    assert render_template_text("{{item_name}} / {{가격}}", {"item_name": "라벨 프린터"}) == "라벨 프린터 / "


def test_db_headers_preserve_connected_workbook_extra_columns() -> None:
    rows = [
        {
            "barcode": "001234",
            "item_code": "A-01",
            "item_name": "라벨 프린터",
            "lot_no": "",
            "qty": "1",
            "print_qty": "1",
            "가격": "580000",
            "고객구분": "도매",
        }
    ]

    assert _db_headers_from_rows(rows) == (
        "barcode",
        "item_code",
        "item_name",
        "lot_no",
        "qty",
        "print_qty",
        "가격",
        "고객구분",
    )


def test_preferred_text_db_field_uses_first_meaningful_text_column() -> None:
    rows = [{"barcode": "001234", "item_code": "A-01", "item_name": "라벨 프린터", "가격": "580000"}]

    assert _preferred_text_db_field(rows) == "item_name"


def test_preferred_text_db_field_supports_dynamic_korean_column() -> None:
    rows = [{"barcode": "001234", "item_code": "", "item_name": "", "가격": "580000"}]

    assert _preferred_text_db_field(rows) == "가격"


def test_data_field_options_only_include_connected_workbook_headers() -> None:
    option_to_key, key_to_option = _data_field_option_maps(("바코드", "품명", "가격"))

    assert option_to_key == {"연결 안 함": "", "바코드": "바코드", "품명": "품명", "가격": "가격"}
    assert key_to_option["품명"] == "품명"
    assert "item_code" not in option_to_key
    assert "lot_no" not in option_to_key


def test_default_template_starts_blank():
    template = default_template(50, 40)

    assert template["label"] == {"width_mm": 50, "height_mm": 40}
    assert template["elements"] == []


def test_main_smoke_creates_default_template_from_printer_settings(tmp_path):
    write_label_size_config(tmp_path, 82, 31)

    assert main(["--base-dir", str(tmp_path), "--smoke-test"]) == 0

    template = json.loads((tmp_path / "templates" / "default_label.json").read_text(encoding="utf-8"))
    assert template["label"] == {"width_mm": 82, "height_mm": 31}
    assert template["elements"] == []


def test_ui_smoke_skips_windows_file_association_registration(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeDesignerApp:
        def __init__(self, _base_dir: Path, **kwargs: object) -> None:
            captured.update(kwargs)

        def update_idletasks(self) -> None:
            return None

        def destroy(self) -> None:
            return None

    monkeypatch.setattr(label_designer_app, "LabelDesignerApp", FakeDesignerApp)

    assert label_designer_app.main(["--base-dir", str(tmp_path), "--ui-smoke-test"]) == 0
    assert captured["register_file_association"] is False


def test_main_smoke_keeps_empty_default_template(tmp_path):
    write_label_size_config(tmp_path, 64, 32)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "default_label.json"
    template_path.write_text(json.dumps({"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}), encoding="utf-8")

    assert main(["--base-dir", str(tmp_path), "--smoke-test"]) == 0

    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert template["label"] == {"width_mm": 64, "height_mm": 32}
    assert template["elements"] == []


def test_main_smoke_replaces_generated_starter_template_with_blank(tmp_path):
    write_label_size_config(tmp_path, 64, 32)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "default_label.json"
    original = _generated_starter_template(50, 40)
    template_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

    assert main(["--base-dir", str(tmp_path), "--smoke-test"]) == 0

    template = json.loads(template_path.read_text(encoding="utf-8"))
    recovery_files = list(template_dir.glob("복구_기본템플릿_*.gblabel"))
    assert template["label"] == {"width_mm": 64, "height_mm": 32}
    assert template["elements"] == []
    assert len(recovery_files) == 1
    assert json.loads(recovery_files[0].read_text(encoding="utf-8")) == original


def test_ensure_blank_default_template_preserves_unreadable_default_before_reset(tmp_path):
    write_label_size_config(tmp_path, 60, 30)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "default_label.json"
    template_path.write_text("not valid json", encoding="utf-8")

    template, recovery_path = ensure_blank_default_template(template_path, tmp_path / "config.ini")

    assert template["elements"] == []
    assert json.loads(template_path.read_text(encoding="utf-8"))["elements"] == []
    assert recovery_path is not None
    assert recovery_path.suffix == ".gblabel"
    assert recovery_path.read_text(encoding="utf-8") == "not valid json"


def test_main_smoke_tolerates_invalid_barcode_db_like_ui(tmp_path):
    write_label_size_config(tmp_path, 58, 70)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BarcodeDB"
    sheet.append(["wrong", "columns"])
    sheet.append(["value", "value"])
    workbook.save(tmp_path / "barcode_db.xlsx")

    assert main(["--base-dir", str(tmp_path), "--smoke-test"]) == 0

    template = json.loads((tmp_path / "templates" / "default_label.json").read_text(encoding="utf-8"))
    assert template["label"] == {"width_mm": 58, "height_mm": 70}
    assert template["elements"] == []


def test_main_smoke_without_base_dir_avoids_runtime_migration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.app_base_dir",
        lambda: (_ for _ in ()).throw(AssertionError("app_base_dir should not run")),
    )

    assert main(["--smoke-test"]) == 0


def test_normal_launch_resets_default_template_file_to_blank_printer_size(tmp_path):
    write_label_size_config(tmp_path, 76, 28)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "default_label.json"
    template_path.write_text(
        json.dumps(
            {
                "label": {"width_mm": 50, "height_mm": 40},
                "elements": [{"type": "text", "text": "KEEP", "x": 1, "y": 2, "width": 10, "height": 5}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_path = template_path
    app.initial_template_path = None
    app.config_path = tmp_path / "config.ini"
    app._initial_template_error = None
    app._initial_template_notice = None

    template = LabelDesignerApp._load_initial_template(app)
    saved_template = json.loads(template_path.read_text(encoding="utf-8"))
    recovery_files = list(template_dir.glob("복구_기본템플릿_*.gblabel"))

    assert template["label"] == {"width_mm": 76, "height_mm": 28}
    assert template["elements"] == []
    assert saved_template["label"] == {"width_mm": 76, "height_mm": 28}
    assert saved_template["elements"] == []
    assert len(recovery_files) == 1
    assert json.loads(recovery_files[0].read_text(encoding="utf-8"))["elements"][0]["text"] == "KEEP"
    assert str(recovery_files[0]) in app._initial_template_notice


def test_normal_launch_keeps_empty_default_template(tmp_path):
    write_label_size_config(tmp_path, 76, 28)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "default_label.json"
    template_path.write_text(
        json.dumps({"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_path = template_path
    app.initial_template_path = None
    app.config_path = tmp_path / "config.ini"
    app._initial_template_error = None

    template = LabelDesignerApp._load_initial_template(app)
    saved_template = json.loads(template_path.read_text(encoding="utf-8"))

    assert template["label"] == {"width_mm": 76, "height_mm": 28}
    assert template["elements"] == []
    assert saved_template["label"] == {"width_mm": 76, "height_mm": 28}
    assert saved_template["elements"] == []


def test_normal_launch_replaces_generated_starter_template_with_blank(tmp_path):
    write_label_size_config(tmp_path, 76, 28)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "default_label.json"
    template_path.write_text(json.dumps(_generated_starter_template(50, 40), ensure_ascii=False), encoding="utf-8")
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_path = template_path
    app.initial_template_path = None
    app.config_path = tmp_path / "config.ini"
    app._initial_template_error = None

    template = LabelDesignerApp._load_initial_template(app)
    saved_template = json.loads(template_path.read_text(encoding="utf-8"))

    assert template["label"] == {"width_mm": 76, "height_mm": 28}
    assert template["elements"] == []
    assert saved_template["label"] == {"width_mm": 76, "height_mm": 28}
    assert saved_template["elements"] == []


def test_reset_template_button_clears_all_objects(monkeypatch, tmp_path):
    write_label_size_config(tmp_path, 76, 28)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.config_path = tmp_path / "config.ini"
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [{"id": "old", "type": "text", "text": "OLD"}]
    app.selected_id = "old"
    app._load_values_to_controls = lambda: None
    app.redraw = lambda: None
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.askyesno", lambda *args, **kwargs: True)

    LabelDesignerApp.reset_template(app)

    assert app.template["label"] == {"width_mm": 76, "height_mm": 28}
    assert app.template["elements"] == []
    assert app.elements == []
    assert app.selected_id is None


def test_opening_saved_label_file_keeps_saved_label_size(tmp_path):
    write_label_size_config(tmp_path, 76, 28)
    label_file = tmp_path / "saved.gblabel"
    label_file.write_text(json.dumps(default_template(60, 35), ensure_ascii=False), encoding="utf-8")
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_path = label_file
    app.initial_template_path = label_file
    app.config_path = tmp_path / "config.ini"
    app._initial_template_error = None

    template = LabelDesignerApp._load_initial_template(app)

    assert template["label"] == {"width_mm": 60, "height_mm": 35}


def test_saved_label_file_extension_is_primary_template_format():
    assert LABEL_FILE_EXTENSION == ".gblabel"
    assert LABEL_FILE_TYPES[0] == ("채움랩 라벨 파일", "*.gblabel")


def test_saved_label_file_loads_like_template(tmp_path):
    label_file = tmp_path / "shipping_label.gblabel"
    label_file.write_text(json.dumps(default_template(60, 35), ensure_ascii=False), encoding="utf-8")

    template = load_template_file(label_file)

    assert template["label"] == {"width_mm": 60, "height_mm": 35}


def test_save_template_writes_current_design_and_clears_dirty_state(tmp_path):
    template_dir = tmp_path / "templates"
    target = template_dir / "shipping.gblabel"
    element = {"id": "text-1", "type": "text", "text": "KEEP"}
    payload = {"version": 1, "label": {"width_mm": 60, "height_mm": 35}, "elements": [element]}
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_dir = template_dir
    app.template_path = target
    app.template = payload
    app.elements = [element]
    app._saved_payload_signature = "before-save"
    app.template_payload = lambda: payload
    app.status_var = SimpleNamespace(set=lambda _value: None)
    app.template_path_var = SimpleNamespace(set=lambda _value: None)

    assert app.save_template() is True
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert app._has_unsaved_changes() is False


def test_save_on_default_template_routes_to_save_as(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_dir = tmp_path / "templates"
    app.template_path = app.template_dir / "default_label.json"
    calls: list[bool] = []
    app.save_template_as = lambda: calls.append(True) or True

    assert LabelDesignerApp.save_template(app) is True
    assert calls == [True]


def test_save_as_keeps_default_blank_and_writes_gblabel(monkeypatch, tmp_path):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    default_path = template_dir / "default_label.json"
    default_path.write_text(json.dumps(default_template(50, 40)), encoding="utf-8")
    target_without_suffix = template_dir / "customer-label"
    element = {"id": "text-1", "type": "text", "text": "KEEP"}
    payload = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": [element]}
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_dir = template_dir
    app.template_path = default_path
    app.template = payload
    app.elements = [element]
    app.template_payload = lambda: payload
    app.title = lambda _value: None
    app.status_var = SimpleNamespace(set=lambda _value: None)
    app.template_path_var = SimpleNamespace(set=lambda _value: None)
    monkeypatch.setattr("barcode_label_automation.label_designer_app.filedialog.asksaveasfilename", lambda **_kwargs: str(target_without_suffix))

    assert app.save_template_as() is True
    assert app.template_path == target_without_suffix.with_suffix(".gblabel")
    assert json.loads(app.template_path.read_text(encoding="utf-8")) == payload
    assert json.loads(default_path.read_text(encoding="utf-8"))["elements"] == []


def test_save_as_rejects_default_path(monkeypatch, tmp_path):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    default_path = template_dir / "default_label.json"
    default_path.write_text(json.dumps(default_template(50, 40)), encoding="utf-8")
    original_path = template_dir / "current.gblabel"
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_dir = template_dir
    app.template_path = original_path
    errors: list[str] = []
    monkeypatch.setattr("barcode_label_automation.label_designer_app.filedialog.asksaveasfilename", lambda **_kwargs: str(default_path))
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showerror", lambda title, *_args, **_kwargs: errors.append(title))

    assert app.save_template_as() is False
    assert app.template_path == original_path
    assert json.loads(default_path.read_text(encoding="utf-8"))["elements"] == []
    assert errors == ["기본 템플릿 저장 불가"]


def test_save_as_failure_restores_current_path(monkeypatch, tmp_path):
    template_dir = tmp_path / "templates"
    current_path = template_dir / "current.gblabel"
    failed_target = template_dir / "failed.gblabel"
    payload = default_template(50, 40)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_dir = template_dir
    app.template_path = current_path
    app.template = payload
    app.elements = []
    app.template_payload = lambda: payload
    titles: list[str] = []
    displayed_paths: list[str] = []
    app.title = titles.append
    app.status_var = SimpleNamespace(set=lambda _value: None)
    app.template_path_var = SimpleNamespace(set=displayed_paths.append)
    monkeypatch.setattr("barcode_label_automation.label_designer_app.filedialog.asksaveasfilename", lambda **_kwargs: str(failed_target))
    monkeypatch.setattr("barcode_label_automation.label_designer_app._atomic_write_json", lambda *_args: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showerror", lambda *_args, **_kwargs: None)

    assert app.save_template_as() is False
    assert app.template_path == current_path
    assert displayed_paths[-1] == str(current_path)
    assert titles[-1].endswith(current_path.name)


@pytest.mark.parametrize(
    ("answer", "expected_saves", "expected_opens"),
    [(None, 0, 0), (False, 0, 1), (True, 1, 1)],
    ids=("cancel", "discard", "save"),
)
def test_open_dirty_prompt_handles_cancel_discard_and_save(
    monkeypatch, tmp_path, answer, expected_saves: int, expected_opens: int
):
    source = tmp_path / "next.gblabel"
    source.write_text(json.dumps(default_template(60, 35)), encoding="utf-8")
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_dir = tmp_path
    app.template = default_template(50, 40)
    app.elements = []
    app._saved_payload_signature = app._current_payload_signature()
    app.elements = [{"id": "dirty", "type": "text", "text": "changed"}]
    saves: list[bool] = []
    opens: list[Path] = []
    app.save_template = lambda: saves.append(True) or True
    app.open_template_path = opens.append
    monkeypatch.setattr("barcode_label_automation.label_designer_app.filedialog.askopenfilename", lambda **_kwargs: str(source))
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.askyesnocancel", lambda *_args, **_kwargs: answer)

    app.open_template()

    assert len(saves) == expected_saves
    assert len(opens) == expected_opens


@pytest.mark.parametrize(
    ("answer", "expected_saves", "expected_closes"),
    [(None, 0, 0), (False, 0, 1), (True, 1, 1)],
    ids=("cancel", "discard", "save"),
)
def test_close_dirty_prompt_handles_cancel_discard_and_save(answer, expected_saves: int, expected_closes: int, monkeypatch):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = default_template(50, 40)
    app.elements = []
    app._saved_payload_signature = app._current_payload_signature()
    app.elements = [{"id": "dirty", "type": "text", "text": "changed"}]
    saves: list[bool] = []
    closes: list[bool] = []
    app.save_template = lambda: saves.append(True) or True
    app.destroy = lambda: closes.append(True)
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.askyesnocancel", lambda *_args, **_kwargs: answer)

    app.request_close()

    assert len(saves) == expected_saves
    assert len(closes) == expected_closes


def test_dirty_prompt_save_failure_blocks_followup_action(monkeypatch):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = default_template(50, 40)
    app.elements = []
    app._saved_payload_signature = app._current_payload_signature()
    app.elements = [{"id": "dirty", "type": "text", "text": "changed"}]
    app.save_template = lambda: False
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.askyesnocancel", lambda *_args, **_kwargs: True)

    assert app._confirm_save_changes("계속하기 전에") is False


def test_open_failure_keeps_current_document_state(tmp_path):
    current_path = tmp_path / "current.gblabel"
    broken_path = tmp_path / "broken.gblabel"
    broken_path.write_text("not valid json", encoding="utf-8")
    current_template = default_template(50, 40)
    current_elements = [{"id": "keep", "type": "text", "text": "KEEP"}]
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_dir = tmp_path / "templates"
    app.config_path = tmp_path / "config.ini"
    app.template_path = current_path
    app.template = current_template
    app.elements = current_elements

    with pytest.raises(json.JSONDecodeError):
        app.open_template_path(broken_path)

    assert app.template_path == current_path
    assert app.template is current_template
    assert app.elements is current_elements


def test_opening_nonempty_default_recovers_design_and_loads_blank(monkeypatch, tmp_path):
    write_label_size_config(tmp_path, 70, 30)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    default_path = template_dir / "default_label.json"
    original = {
        "version": 1,
        "label": {"width_mm": 50, "height_mm": 40},
        "elements": [{"id": "keep", "type": "text", "text": "KEEP"}],
    }
    default_path.write_text(json.dumps(original), encoding="utf-8")
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_dir = template_dir
    app.config_path = tmp_path / "config.ini"
    app.title = lambda _value: None
    app.template_path_var = SimpleNamespace(set=lambda _value: None)
    app._load_values_to_controls = lambda: None
    app.redraw = lambda: None
    app.status_var = SimpleNamespace(set=lambda _value: None)
    notices: list[str] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.messagebox.showinfo",
        lambda _title, message, **_kwargs: notices.append(message),
    )

    app.open_template_path(default_path)

    recovery_files = list(template_dir.glob("복구_기본템플릿_*.gblabel"))
    assert app.template_path == default_path.resolve()
    assert app.template["label"] == {"width_mm": 70, "height_mm": 30}
    assert app.elements == []
    assert json.loads(default_path.read_text(encoding="utf-8"))["elements"] == []
    assert len(recovery_files) == 1
    assert json.loads(recovery_files[0].read_text(encoding="utf-8")) == original
    assert str(recovery_files[0]) in notices[0]


def test_image_file_picker_supports_photoshop_and_photo_files():
    filters = " ".join(pattern for _label, pattern in IMAGE_FILE_TYPES)

    assert "*.psd" in filters
    assert "*.png" in filters
    assert "*.jpg" in filters
    assert "*.tif" in filters


def test_image_import_converts_to_internal_png_asset(tmp_path):
    source = tmp_path / "package-photo.jpg"
    Image.new("RGB", (80, 40), "black").save(source)
    image_dir = tmp_path / "assets" / "images"

    target, size = _save_design_image_asset(source, image_dir)

    assert target.suffix == ".png"
    assert target.exists()
    assert size == (80, 40)
    with Image.open(target) as image:
        assert image.mode == "RGBA"
        assert image.size == (80, 40)


def test_full_label_image_element_uses_current_label_size():
    element = _image_element_for_label(
        "assets/images/design.png",
        "design",
        {"width_mm": 58, "height_mm": 70},
        (1200, 800),
        fit_to_label=True,
        printable=False,
    )

    assert element["type"] == "image"
    assert element["x"] == 0
    assert element["y"] == 0
    assert element["width"] == 58
    assert element["height"] == 70
    assert element["arrange"] == "behind"
    assert element["image_path"] == "assets/images/design.png"
    assert element["image_fit"] == "stretch"
    assert element["printable"] is False


def test_design_image_generates_editable_line_candidates():
    image = Image.new("RGB", (120, 80), "white")
    for x in range(10, 111):
        image.putpixel((x, 20), (0, 0, 0))
        image.putpixel((x, 60), (0, 0, 0))
    for y in range(20, 61):
        image.putpixel((10, y), (0, 0, 0))
        image.putpixel((110, y), (0, 0, 0))

    elements = _editable_shape_elements_from_image(image, {"width_mm": 60, "height_mm": 40})

    assert any(element["type"] == "line" for element in elements)
    assert any(element["type"] == "box" for element in elements)


def test_design_template_analysis_creates_editable_text_candidate():
    image = Image.new("RGB", (180, 90), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 18), "ABC123", fill="black")

    elements = _design_template_elements_from_image(image, {"width_mm": 60, "height_mm": 30})

    text_elements = [element for element in elements if element["type"] == "text"]
    assert text_elements
    assert text_elements[0]["text"]
    assert text_elements[0]["width"] > 1
    assert text_elements[0]["height"] > 1


def test_table_design_template_creates_editable_table_and_bounded_text(monkeypatch):
    image = Image.new("RGB", (360, 180), "white")
    draw = ImageDraw.Draw(image)
    for x in (0, 70, 140, 210, 280, 359):
        draw.line((x, 0, x, 179), fill=(210, 210, 210), width=1)
    for y in (0, 36, 72, 108, 144, 179):
        draw.line((0, y, 359, y), fill=(210, 210, 210), width=1)
    draw.text((8, 9), "제조사", fill="black")
    draw.text((78, 9), "WAX", fill="black")
    draw.text((148, 45), "B110A", fill="black")
    draw.text((218, 81), "RRC", fill="black")

    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app._ocr_text_from_box",
        lambda *_args, **_kwargs: "셀 데이터",
    )

    label = {"width_mm": 58, "height_mm": 70}
    elements = _design_template_elements_from_image(image, label, base_dir=None)

    table_elements = [element for element in elements if element["type"] == "table"]
    text_elements = [element for element in elements if element["type"] == "text"]
    assert len(table_elements) == 1
    assert table_elements[0]["table_rows"] == 5
    assert table_elements[0]["table_cols"] == 5
    assert text_elements
    for element in text_elements:
        assert element["fit_text_to_box"] is False
        x = float(element["x"])
        y = float(element["y"])
        width = float(element["width"])
        height = float(element["height"])
        assert 0 <= x <= float(label["width_mm"])
        assert 0 <= y <= float(label["height_mm"])
        assert x + width <= float(label["width_mm"]) + 0.1
        assert y + height <= float(label["height_mm"]) + 0.1


def test_table_ocr_candidate_scoring_prefers_cleaner_model_text():
    assert _best_table_cell_text(["11\\", "ITW"], 2, 0) == "ITW"
    assert _best_table_cell_text(["ARADI/TPC4", "AR401/TPC4"], 3, 5) == "AR401/TPC4"


def test_known_ribbon_reference_table_correction_uses_business_terms():
    assert _known_ribbon_reference_cell_text(0, 0) == "제조사"
    assert _known_ribbon_reference_cell_text(0, 1) == "WAX(왁스리본)"
    assert _known_ribbon_reference_cell_text(1, 1) == "5408\nTR4085"
    assert _known_ribbon_reference_cell_text(6, 4) == "APR9\n코어리본-EDGE"
    assert _best_table_cell_text(["SONY(2Le] =)"], 1, 0, known_table="ribbon_reference") == "SONY(소니리본)"


def test_ocr_tsv_creates_positioned_text_elements(monkeypatch, tmp_path):
    tesseract = tmp_path / "tools" / "ocr" / "tesseract.exe"
    tessdata = tmp_path / "tools" / "ocr" / "tessdata"
    tessdata.mkdir(parents=True)
    tesseract.write_bytes(b"fake")
    (tessdata / "eng.traineddata").write_bytes(b"fake")
    tsv = "\n".join(
        [
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
            "5\t1\t1\t1\t1\t1\t10\t20\t40\t15\t92.0\t제품명",
            "5\t1\t1\t1\t1\t2\t60\t20\t30\t15\t91.0\tA1",
        ]
    )

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=tsv.encode("utf-8"), stderr=b"")

    monkeypatch.setattr("barcode_label_automation.label_designer_app.subprocess.run", fake_run)

    elements = _ocr_tsv_text_elements_from_image(Image.new("RGB", (100, 50), "white"), {"width_mm": 50, "height_mm": 25}, base_dir=tmp_path)

    assert len(elements) == 1
    assert elements[0]["type"] == "text"
    assert elements[0]["text"] == "제품명 A1"
    assert elements[0]["x"] >= 0
    assert elements[0]["width"] > 1


def test_design_ocr_text_cleanup_removes_barcode_noise():
    assert _clean_design_ocr_line_text("PONO:4500082866 HII") == "PO NO : 4500082866"
    assert _clean_design_ocr_line_text("O NO : 4500082866") == "PO NO : 4500082866"
    assert _clean_design_ocr_line_text("KEYNO:CN04761-RS0134/RS0137") == "KEY NO : CN04761-RS0134/RS0137"
    assert _clean_design_ocr_line_text("제조일자 :2022-10-03 IN") == "제조일자 : 2022-10-03"
    assert _clean_design_ocr_line_text("|수 2 : 12000") == "수량 : 12000"
    assert _clean_design_ocr_line_text("수 량 : 12000") == "수량 : 12000"
    assert _clean_design_ocr_line_text("유 효 기 간 : 2026-10-02") == "유효기간 : 2026-10-02"
    assert _clean_design_ocr_line_text("6132HL00001") == "G132HL00001"
    assert not _is_meaningful_design_text("- ae an")


def test_inferred_barcode_values_replace_fallback_placeholders():
    text_elements = [
        _element("text", "- ae an", 1, 0, 18, 2),
        _element("text", "PO NO : 4500082866", 1, 2, 18, 4),
        _element("text", "G132HL00001", 1, 7, 18, 4),
        _element("text", "수량 : 12000", 1, 12, 18, 4),
    ]
    barcode_elements = [
        _element("barcode", "12345678", 28, 2, 25, 4, barcode_type="code128"),
        _element("barcode", "12345678", 28, 7, 25, 4, barcode_type="code128"),
        _element("barcode", "12345678", 28, 12, 25, 4, barcode_type="code128"),
    ]

    _apply_inferred_barcode_values(barcode_elements, text_elements)

    assert [element["text"] for element in barcode_elements] == ["4500082866", "G132HL00001", "12000"]
    assert _barcode_value_candidate_from_text("유효기간:2026-10-02 |") == "2026-10-02"

    text_elements[0]["width"] = 50
    _fit_text_elements_around_barcodes(text_elements, barcode_elements)
    assert text_elements[0]["width"] < 28


def test_ocr_uses_bundled_tesseract_stdout(monkeypatch, tmp_path):
    tesseract = tmp_path / "tools" / "ocr" / "tesseract.exe"
    tessdata = tmp_path / "tools" / "ocr" / "tessdata"
    tessdata.mkdir(parents=True)
    tesseract.write_bytes(b"fake")
    (tessdata / "eng.traineddata").write_bytes(b"fake")
    (tessdata / "kor.traineddata").write_bytes(b"fake")
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(args, **kwargs):
        calls.append((list(args), dict(kwargs.get("env", {}))))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="제품명 123\n".encode("utf-8"), stderr=b"")

    monkeypatch.setattr("barcode_label_automation.label_designer_app.subprocess.run", fake_run)

    text = _ocr_text_from_box(Image.new("RGB", (120, 30), "white"), base_dir=tmp_path)

    assert text == "제품명 123"
    assert calls
    assert calls[0][0][0] == str(tesseract)
    assert calls[0][0][2] == "stdout"
    assert calls[0][0][4] == "kor+eng"
    assert calls[0][1]["TESSDATA_PREFIX"] == str(tessdata)


def test_resolve_tesseract_prefers_bundled_engine(tmp_path):
    tesseract = tmp_path / "tools" / "ocr" / "tesseract.exe"
    tesseract.parent.mkdir(parents=True)
    tesseract.write_bytes(b"fake")

    assert _resolve_tesseract_executable(tmp_path) == tesseract


def test_resolve_tesseract_falls_back_to_pyinstaller_bundle(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    bundle_dir = tmp_path / "bundle"
    tesseract = bundle_dir / "tools" / "ocr" / "tesseract.exe"
    tesseract.parent.mkdir(parents=True)
    tesseract.write_bytes(b"fake")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setattr("barcode_label_automation.label_designer_app.executable_dir", lambda: runtime_dir)

    assert _resolve_tesseract_executable(runtime_dir) == tesseract


def test_design_template_analysis_decodes_barcode_to_editable_barcode_element():
    barcode = _element("barcode", "12345678", 1, 1, 30, 10, barcode_type="code128")
    image = _render_1d_barcode_image("code128", "12345678", 320, 100, barcode).convert("RGB")

    elements = _design_template_elements_from_image(image, {"width_mm": 64, "height_mm": 32})

    barcode_elements = [element for element in elements if element["type"] == "barcode"]
    assert barcode_elements
    assert barcode_elements[0]["text"] == "12345678"
    assert barcode_elements[0]["barcode_type"] == "code128"


def test_design_template_barcode_label_is_not_misread_as_table(monkeypatch):
    image = Image.new("RGB", (674, 261), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, 664, 256), outline="black", width=4)
    rows = [
        ("PO NO : 4500082866", "4500082866", 22),
        ("G132HL00001", "G132HL00001", 58),
        ("KEY NO : CN04761-RS0134/RS0137", "CN04761-RS0134/RS0137", 98),
        ("수 량 : 12000", "12000", 143),
        ("제조일자 : 2022-10-03", "2022-10-03", 184),
        ("유효기간 : 2026-10-02", "2026-10-02", 225),
    ]
    label = {"width_mm": 58, "height_mm": 22.5}
    fake_text_elements: list[dict[str, object]] = []

    for line_text, barcode_value, y in rows:
        draw.text((10, y - 12), line_text, fill="black")
        barcode = _element("barcode", barcode_value, 0, 0, 24, 3, barcode_type="code128")
        barcode_image = _render_1d_barcode_image("code128", barcode_value, 260, 28, barcode).convert("RGB")
        image.paste(barcode_image, (270, y - 16))
        y_mm = round((y - 16) / image.height * float(label["height_mm"]), 1)
        fake_text_elements.append(_element("text", line_text, 0.8, y_mm, 21.0, 1.5, font_size=8, align="left"))

    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app._ocr_tsv_text_elements_from_image",
        lambda *_args, **_kwargs: [dict(element) for element in fake_text_elements],
    )

    elements = _design_template_elements_from_image(image, label, base_dir=None)

    assert _table_grid_from_image(image) is None
    assert not any(element["type"] == "table" for element in elements)
    assert any(element["type"] == "text" for element in elements)
    assert any(element["type"] in {"line", "box"} for element in elements)
    qty_text = next(element for element in elements if element["type"] == "text" and "12000" in str(element["text"]))
    assert float(qty_text["width"]) > 10
    barcode_elements = [element for element in elements if element["type"] == "barcode"]
    assert barcode_elements
    assert "12345678" not in {str(element["text"]) for element in barcode_elements}
    assert any(str(element["text"]) == "4500082866" for element in barcode_elements)


def test_design_template_import_waits_for_apply(tmp_path):
    source = tmp_path / "design.png"
    image = Image.new("RGB", (120, 80), "white")
    ImageDraw.Draw(image).text((12, 18), "ABC", fill="black")
    image.save(source)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.template = {"version": 1, "label": {"width_mm": 60, "height_mm": 40}, "elements": []}

    guides = LabelDesignerApp._editable_template_elements_from_source(app, source)
    generated = LabelDesignerApp._template_elements_from_reference(app, guides[0])

    assert len(guides) == 1
    assert guides[0]["type"] == "image"
    assert guides[0]["printable"] is False
    assert guides[0]["template_role"] == "design_reference"
    assert any(element["type"] == "text" for element in generated)


def test_design_template_import_keeps_label_size_and_stretches_source_to_label(tmp_path):
    source = tmp_path / "wide-design.png"
    image = Image.new("RGB", (674, 261), "white")
    ImageDraw.Draw(image).text((12, 18), "PO NO : 4500082866", fill="black")
    image.save(source)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.template = {"version": 1, "label": {"width_mm": 58, "height_mm": 70}, "elements": []}

    guides = LabelDesignerApp._editable_template_elements_from_source(app, source)

    assert app.template["label"] == {"width_mm": 58, "height_mm": 70}
    assert guides[0]["x"] == 0
    assert guides[0]["y"] == 0
    assert guides[0]["width"] == 58
    assert guides[0]["height"] == 70
    assert guides[0]["image_fit"] == "stretch"


def test_design_template_coordinates_fill_current_label_size():
    assert _pixel_box_to_label_mm((0, 0, 674, 261), (674, 261), {"width_mm": 58, "height_mm": 70}) == (0.0, 0.0, 58.0, 70.0)
    assert _pixel_box_to_label_mm((337, 130, 674, 261), (674, 261), {"width_mm": 58, "height_mm": 70}) == (29.0, 34.9, 29.0, 35.1)


def test_regular_image_element_preserves_photo_shape_inside_default_box():
    width, height = _fit_image_mm_size((1200, 600), 30, 20)

    assert width == 30
    assert height == 15


def test_main_smoke_test_accepts_saved_label_file(tmp_path):
    label_file = tmp_path / "product_label.gblabel"
    label_file.write_text(json.dumps(default_template(70, 40), ensure_ascii=False), encoding="utf-8")

    assert main(["--base-dir", str(tmp_path), "--smoke-test", str(label_file)]) == 0


def test_normalize_template_keeps_known_element_values():
    template = normalize_template(
        {
            "label": {"width_mm": "60", "height_mm": "45"},
            "elements": [{"type": "field", "text": "{{lot_no}}", "x": "3", "y": "4", "width": "20", "height": "5"}],
        }
    )

    assert template["label"] == {"width_mm": 60, "height_mm": 45}
    assert template["elements"][0]["type"] == "field"
    assert template["elements"][0]["x"] == 3.0


def test_normalize_template_keeps_supported_object_rotation_and_resets_unknown_values():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [
                {"type": "text", "text": "세로 텍스트", "rotation": 90},
                {"type": "barcode", "text": "12345678", "rotation": 270},
                {"type": "box", "rotation": 45},
            ],
        }
    )

    assert [element["rotation"] for element in template["elements"]] == [90, 270, 0]


def test_normalize_template_preserves_decimal_label_size():
    template = normalize_template({"label": {"width_mm": 58, "height_mm": 22.5}, "elements": []})

    assert template["label"] == {"width_mm": 58, "height_mm": 22.5}


def test_normalize_template_keeps_multiline_text_element():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [{"type": "multiline_text", "text": "첫째 줄\n둘째 줄", "height": 12}],
        }
    )

    assert template["elements"][0]["type"] == "multiline_text"
    assert template["elements"][0]["text"] == "첫째 줄\n둘째 줄"


def test_multiline_text_box_renders_with_line_breaks():
    element = _element("multiline_text", "첫째 줄\n둘째 줄", 0, 0, 30, 12, font_size=10)

    image = _render_text_box_image(str(element["text"]), 240, 96, element, transparent=False)

    assert image.size == (240, 96)
    assert ImageChops.invert(image.convert("L")).getbbox() is not None


def test_normalize_template_keeps_barcode_type():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [{"type": "barcode", "text": "12345", "barcode_type": "datamatrix"}],
        }
    )

    assert template["elements"][0]["type"] == "barcode"
    assert template["elements"][0]["barcode_type"] == "datamatrix"


def test_normalize_template_keeps_table_shape_and_reverse_text():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [
                {"type": "table", "table_rows": "4", "table_cols": "2"},
                {"type": "text", "text": "A", "reverse": True},
            ],
        }
    )

    assert template["elements"][0]["type"] == "table"
    assert template["elements"][0]["table_rows"] == 4
    assert template["elements"][0]["table_cols"] == 2
    assert template["elements"][0]["arrange"] == "behind"
    assert template["elements"][1]["reverse"] is True


def test_normalize_template_keeps_custom_table_divider_positions():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [
                {
                    "type": "table",
                    "table_rows": 3,
                    "table_cols": 4,
                    "table_row_positions": [0.2, 0.7],
                    "table_col_positions": [0.15, 0.5, 0.85],
                }
            ],
        }
    )

    table = template["elements"][0]
    assert table["table_row_positions"] == [0.2, 0.7]
    assert table["table_col_positions"] == [0.15, 0.5, 0.85]


def test_normalize_template_keeps_shape_stroke_width_only_for_shape_objects():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [
                {"type": "box", "stroke_width": "1.2"},
                {"type": "line", "stroke_width": "0.05"},
                {"type": "table", "stroke_width": "9"},
                {"type": "text", "stroke_width": "2"},
            ],
        }
    )

    assert template["elements"][0]["stroke_width"] == 1.2
    assert template["elements"][1]["stroke_width"] == 0.1
    assert template["elements"][2]["stroke_width"] == 5.0
    assert "stroke_width" not in template["elements"][3]


def test_normalize_template_keeps_image_path_and_arrange_mode():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [{"type": "image", "image_path": "assets/images/sample.jpg", "arrange": "front"}],
        }
    )

    assert template["elements"][0]["type"] == "image"
    assert template["elements"][0]["image_path"] == "assets/images/sample.jpg"
    assert template["elements"][0]["arrange"] == "front"


def test_barcode_type_list_has_1d_and_2d_choices():
    assert "Code 128" in BARCODE_TYPES.values()
    assert "Aztec" in BARCODE_TYPES.values()
    assert "DataMatrix" in BARCODE_TYPES.values()
    assert "MaxiCode" in BARCODE_TYPES.values()
    assert "Micro QR" in BARCODE_TYPES.values()
    assert "MicroPDF417" in BARCODE_TYPES.values()
    assert "PDF417" in BARCODE_TYPES.values()
    assert "QR" in BARCODE_TYPES.values()


def test_new_basic_barcode_object_is_not_db_connected_by_default():
    element = _element("barcode", "12345678", 7, 14, 36, 12)

    assert element["field"] == ""
    assert element["text"] == "12345678"
    assert element["font_name"] == DEFAULT_FONT_NAME


def test_designer_visible_copy_keeps_db_ui_minimal_until_connection():
    source = "\n".join(
        inspect.getsource(method)
        for method in (
            LabelDesignerApp._build_menu,
            LabelDesignerApp._build_ui,
            LabelDesignerApp._build_tool_panel,
            LabelDesignerApp._build_canvas_toolbar,
            LabelDesignerApp._build_property_panel,
            LabelDesignerApp.refresh_data_panel,
            LabelDesignerApp.reload_db,
        )
    )

    assert "add_cascade" not in inspect.getsource(LabelDesignerApp._build_menu)
    assert "DB 필드" not in source
    assert "DB 값" not in source
    assert "데이터 필드" not in source
    assert "필드 삽입" not in source
    assert "라벨디자이너 Pro" not in source
    assert "데이터 원본 연결" not in source
    assert "DB 연결" in source
    assert "DB 해제" in source
    assert "프린터 설정" in source
    assert "데이터 소스" in source
    assert 'text="파일"' in source
    tool_source = inspect.getsource(LabelDesignerApp._build_tool_panel)
    assert "삭제" not in tool_source
    assert "앞으로" not in tool_source
    assert "뒤로" not in tool_source
    assert "미리보기" not in tool_source
    assert "그림" in source


def test_tool_panel_rows_follow_the_dynamic_tool_list():
    source = inspect.getsource(LabelDesignerApp._build_tool_panel)

    assert "for text, command, columnspan in tools" in source
    assert "columnspan=columnspan" in source
    assert "if columnspan == 2 or column == 1" in source


def test_designer_style_uses_softened_desktop_surfaces():
    source = "\n".join(
        inspect.getsource(method)
        for method in (
            LabelDesignerApp._configure_style,
            LabelDesignerApp._surface_card,
            LabelDesignerApp._draw_grid,
            LabelDesignerApp.draw_element,
        )
    )

    assert "*Menu.font" in source
    assert "Treeview.Heading" in source
    assert "COLORS.border_subtle" in source
    assert "GRID_COLOR" in source
    assert "ELEMENT_GUIDE_COLOR" in source


def test_designer_rulers_use_high_contrast_tabular_numbers():
    source = inspect.getsource(LabelDesignerApp._draw_rulers)

    assert "RULER_LABEL_COLOR" in source
    assert 'font=("Consolas", 9, "bold")' in source


def test_printer_settings_command_prefers_packaged_exe(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    settings_exe = install_dir / "프린터설정.exe"
    settings_exe.write_bytes(b"")

    command = _printer_settings_command(tmp_path / "runtime", install_dir, frozen=True)

    assert command == [str(settings_exe)]


def test_printer_settings_command_finds_customer_korean_exe_name(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    settings_exe = install_dir / "프린터설정.exe"
    settings_exe.write_bytes(b"")

    command = _printer_settings_command(tmp_path / "runtime", install_dir, frozen=True)

    assert command == [str(settings_exe)]


def test_printer_settings_command_uses_settings_module_in_dev(tmp_path):
    command = _printer_settings_command(tmp_path, tmp_path, frozen=False)

    assert command == [
        sys.executable,
        "-m",
        "barcode_label_automation.settings_app",
        "--config",
        str(tmp_path / "config.ini"),
    ]


def test_designer_table_behind_does_not_block_text_selection():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.origin_x = 0
    app.origin_y = 0
    app.scale = 10
    table = _element("table", "", 0, 0, 50, 30)
    text = _element("text", "A", 10, 10, 10, 5)
    app.elements = [text, table]

    selected = app.find_element_at(105, 105)

    assert selected is text


def test_table_divider_drag_updates_only_selected_internal_line():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.origin_x = 0
    app.origin_y = 0
    app.scale = 10
    table = _element("table", "", 0, 0, 50, 30)
    table["table_cols"] = 3
    table["table_rows"] = 3
    app.elements = [table]
    app.selected_id = str(table["id"])
    app.load_selected_properties = lambda: None
    app.redraw = lambda: None

    assert app.table_divider_at(167, 120, table) == ("col", 0)

    app.drag_state = {"mode": "table-divider", "axis": "col", "index": 0.0, "start_x": 167.0, "start_y": 120.0}
    app.on_canvas_drag(SimpleNamespace(x=225, y=120))

    assert _table_axis_positions(table, "col")[0] == 0.45
    assert _table_axis_positions(table, "col")[1] == pytest.approx(0.6667)


def test_table_divider_drag_keeps_minimum_cell_width():
    table = _element("table", "", 0, 0, 50, 30)
    table["table_cols"] = 3
    table["table_col_positions"] = [0.3333, 0.6667]

    _set_table_axis_position(table, "col", 0, 0.99)

    assert _table_axis_positions(table, "col")[0] == 0.6267
    assert _table_axis_positions(table, "col")[0] < _table_axis_positions(table, "col")[1]


def test_designer_primary_print_is_regular_print_until_db_connection():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app._refreshing_data_panel = False
    app.data_source_path = None
    button_states: list[str] = []
    print_labels: list[str] = []
    app.data_source_button = SimpleNamespace(configure=lambda **values: button_states.append(values["state"]))
    app.primary_print_text_var = SimpleNamespace(set=print_labels.append)
    app.data_tree = None
    app.queue_tree = None
    app.db_rows = []
    app.selected_data_indexes = set()
    app.preview_row = {}
    app.data_source_label_var = SimpleNamespace(set=lambda _value: None)
    app.record_count_var = SimpleNamespace(set=lambda _value: None)
    app.queue_status_var = SimpleNamespace(set=lambda _value: None)

    app.refresh_data_panel()

    assert button_states == ["disabled"]
    assert print_labels == ["인쇄"]


def test_designer_primary_print_changes_to_selected_print_after_db_connection(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app._refreshing_data_panel = False
    app.base_dir = tmp_path
    app.data_source_path = tmp_path / "barcode_db.xlsx"
    button_states: list[str] = []
    print_labels: list[str] = []
    app.data_source_button = SimpleNamespace(configure=lambda **values: button_states.append(values["state"]))
    app.primary_print_text_var = SimpleNamespace(set=print_labels.append)
    app.data_tree = None
    app.queue_tree = None
    app.db_rows = []
    app.selected_data_indexes = set()
    app.preview_row = {}
    app.data_source_label_var = SimpleNamespace(set=lambda _value: None)
    app.record_count_var = SimpleNamespace(set=lambda _value: None)
    app.queue_status_var = SimpleNamespace(set=lambda _value: None)

    app.refresh_data_panel()

    assert button_states == ["normal"]
    assert print_labels == ["선택 인쇄"]


def test_designer_data_panel_uses_connected_workbook_columns(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app._refreshing_data_panel = False
    app.base_dir = tmp_path
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.data_source_headers = ("barcode", "item_name", "가격", "고객구분")
    app.data_source_button = None
    app.primary_print_text_var = None
    app.db_preview_tree = None
    app.data_tree = _FakeDataTree()
    app.queue_tree = None
    app.db_rows = [{"barcode": "001234", "item_name": "라벨 프린터", "가격": "580000", "고객구분": "도매"}]
    app.selected_data_indexes = {0}
    app.preview_row = app.db_rows[0]
    app.data_source_label_var = SimpleNamespace(set=lambda _value: None)
    app.record_count_var = SimpleNamespace(set=lambda _value: None)
    app.queue_status_var = SimpleNamespace(set=lambda _value: None)

    app.refresh_data_panel()

    assert app.data_tree.columns == app.data_source_headers
    assert app.data_tree.headings["가격"] == "가격"
    assert app.data_tree.rows["0"] == ("001234", "라벨 프린터", "580000", "도매")
    assert app.data_tree.row_text["0"] == "☑"


def test_designer_output_row_uses_selected_data_and_preserves_leading_zeroes():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {}
    source_row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "001234567890",
        "lot_no": "LOT250532",
        "qty": "010",
        "print_qty": "3",
    }

    row = app._output_test_row(7, source_row=source_row)

    assert row["barcode"] == "001234567890"
    assert row["qty"] == "010"
    assert row["print_qty"] == "7"


def test_designer_output_row_preserves_dynamic_db_columns():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {}
    source_row = {
        "barcode": "001234",
        "item_name": "라벨 프린터",
        "가격": "580000",
        "고객구분": "도매",
        "print_qty": "3",
    }

    row = app._output_test_row(3, source_row=source_row)

    assert row["barcode"] == "001234"
    assert row["가격"] == "580000"
    assert row["고객구분"] == "도매"
    assert render_template_text("{{item_name}} / {{가격}} / {{고객구분}}", row) == "라벨 프린터 / 580000 / 도매"


def test_designer_output_row_does_not_inject_hidden_sample_values():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {"barcode": "preview-must-not-leak"}

    row = app._output_test_row(4, source_row={})

    assert row == {
        "barcode": "",
        "item_code": "",
        "item_name": "",
        "lot_no": "",
        "qty": "",
        "print_qty": "4",
    }


def test_designer_barcode_tool_uses_a_printable_sample_without_db_connection():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.elements = []
    app.selected_id = None
    app.data_source_path = None
    app.load_selected_properties = lambda: None
    app.redraw = lambda: None
    app._animate_selected_element = lambda: None
    app.status_var = SimpleNamespace(set=lambda _value: None)

    app.add_element("barcode")

    assert app.elements[0]["text"] == "12345678"
    assert app.elements[0]["field"] == ""


def test_designer_barcode_tool_binds_to_db_barcode_field_when_connected(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.elements = []
    app.selected_id = None
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.load_selected_properties = lambda: None
    app.redraw = lambda: None
    app._animate_selected_element = lambda: None
    app.status_var = SimpleNamespace(set=lambda _value: None)

    app.add_element("barcode")

    assert app.elements[0]["text"] == "{{barcode}}"
    assert app.elements[0]["field"] == "barcode"


def test_new_code_element_values_only_use_db_placeholder_when_connected():
    assert _new_code_element_values(data_source_connected=False) == ("12345678", "")
    assert _new_code_element_values(data_source_connected=True) == ("{{barcode}}", "barcode")


def test_designer_text_tool_binds_to_current_db_field_when_connected(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.elements = []
    app.selected_id = None
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.db_rows = [
        {
            "barcode": "001234567890",
            "item_code": "A1002",
            "item_name": "SENSOR BRACKET",
            "lot_no": "LOT250532",
            "qty": "010",
            "print_qty": "1",
        }
    ]
    app.data_source_headers = ("barcode", "item_code", "item_name", "lot_no", "qty", "print_qty")
    app.preview_row = app.db_rows[0]
    app.load_selected_properties = lambda: None
    app.redraw = lambda: None
    app._animate_selected_element = lambda: None
    app.status_var = SimpleNamespace(set=lambda _value: None)

    app.add_element("text")

    element = app.elements[0]
    assert element["field"] == "item_name"
    assert element["text"] == "{{item_name}}"
    assert render_element_text(element, app.preview_row) == "SENSOR BRACKET"


def test_designer_text_tool_remains_literal_without_db_connection():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.elements = []
    app.selected_id = None
    app.data_source_path = None
    app.db_rows = []
    app.data_source_headers = ()
    app.preview_row = {}
    app.load_selected_properties = lambda: None
    app.redraw = lambda: None
    app._animate_selected_element = lambda: None
    app.status_var = SimpleNamespace(set=lambda _value: None)

    app.add_element("text")

    assert app.elements[0]["field"] == ""
    assert app.elements[0]["text"] == "새 텍스트"


def test_connect_data_source_replaces_rows_headers_and_preview(monkeypatch, tmp_path) -> None:
    source = tmp_path / "새상품DB.xlsx"
    rows = [{"barcode": "001234", "상품명": "감열 라벨", "판매가": "580000"}]
    status: list[str] = []
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.data_source_path = None
    app.db_rows = []
    app.data_source_headers = ()
    app.selected_data_indexes = set()
    app.preview_row = {}
    app.config_path = tmp_path / "config.ini"
    app.template = {"version": 1, "label": {"width_mm": 60, "height_mm": 35}, "elements": []}
    app.refresh_sample_options = lambda: None
    app.redraw = lambda: None
    app.status_var = SimpleNamespace(set=status.append)
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.filedialog.askopenfilename",
        lambda **_kwargs: str(source),
    )
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.load_db_source",
        lambda _path: (rows, ("바코드", "상품명", "판매가")),
    )

    app.connect_data_source()

    assert app.data_source_path == source
    assert app.db_rows == rows
    assert app.data_source_headers == ("바코드", "상품명", "판매가")
    assert app.preview_row == rows[0]
    assert app.selected_data_indexes == set()
    assert app.template["label"] == {"width_mm": 60, "height_mm": 35}
    assert "템플릿 60×35mm" in status[-1]
    assert status[-1].startswith("DB 연결 완료:")


def test_data_source_search_filters_every_actual_db_column() -> None:
    rows = [
        {"바코드": "880001", "상품코드": "ACC-001", "품목명": "하트 키링", "판매가": "4,600원"},
        {"바코드": "880002", "상품코드": "ACC-002", "품목명": "미니 하트 귀걸이", "판매가": "5,300원"},
        {"바코드": "880003", "상품코드": "ACC-003", "품목명": "아크릴 키링", "판매가": "6,100원"},
    ]
    headers = ("바코드", "상품코드", "품목명", "판매가")

    assert _filter_data_source_row_indexes(rows, headers, "하트") == [0, 1]
    assert _filter_data_source_row_indexes(rows, headers, "880003") == [2]
    assert _filter_data_source_row_indexes(rows, headers, "acc-002") == [1]
    assert _filter_data_source_row_indexes(rows, headers, "6,100") == [2]
    assert _filter_data_source_row_indexes(rows, headers, "없는값") == []
    assert _filter_data_source_row_indexes(rows, headers, "") == [0, 1, 2]


def test_data_source_search_changes_visible_rows_without_losing_output_selection() -> None:
    messages: list[str] = []
    refreshes: list[bool] = []
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.db_rows = [
        {"바코드": "880001", "상품코드": "ACC-001", "품목명": "하트 키링", "판매가": "4,600원"},
        {"바코드": "880002", "상품코드": "ACC-002", "품목명": "아크릴 키링", "판매가": "6,100원"},
        {"바코드": "880003", "상품코드": "ACC-003", "품목명": "미니 하트 귀걸이", "판매가": "5,300원"},
    ]
    app.visible_data_indexes = [0, 1, 2]
    app.data_source_headers = ("바코드", "상품코드", "품목명", "판매가")
    app.data_search_var = SimpleNamespace(get=lambda: "5,300")
    app.data_search_hint_var = SimpleNamespace(set=messages.append)
    app.status_var = SimpleNamespace(set=messages.append)
    app.selected_data_indexes = {0, 2}
    app.preview_row = app.db_rows[0]
    app.refresh_sample_options = lambda: refreshes.append(True)
    app.redraw = lambda: None

    assert app.search_data_source() == "break"
    assert app.visible_data_indexes == [2]
    assert app.db_rows[2]["품목명"] == "미니 하트 귀걸이"
    assert app.selected_data_indexes == {0, 2}
    assert app.preview_row is app.db_rows[2]
    assert refreshes == [True]
    assert any("1 / 3건" in message for message in messages)


def test_loaded_db_rows_repair_invalid_template_size_and_wait_for_layout(tmp_path) -> None:
    events: list[str] = []
    write_label_size_config(tmp_path, 50, 40)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.config_path = tmp_path / "config.ini"
    app.template = {"version": 1, "label": {"width_mm": 0, "height_mm": -5}, "elements": []}
    app.db_rows = []
    app.data_source_headers = ()
    app.selected_data_indexes = set()
    app.preview_row = {}
    app.width_var = SimpleNamespace(set=lambda value: events.append(f"width:{value}"))
    app.height_var = SimpleNamespace(set=lambda value: events.append(f"height:{value}"))
    app.refresh_sample_options = lambda: events.append("refresh")
    app.update_idletasks = lambda: events.append("layout")
    app.redraw = lambda: events.append("redraw")

    size = app._apply_loaded_db_rows([{"barcode": "001234"}], ("barcode",))

    assert size == (50, 40)
    assert app.template["label"] == {"width_mm": 50, "height_mm": 40}
    assert events[-3:] == ["refresh", "layout", "redraw"]


@pytest.mark.parametrize("invalid_size", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_db_connection_repairs_non_finite_or_non_positive_template_size(tmp_path, invalid_size: float) -> None:
    write_label_size_config(tmp_path, 62, 34)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.config_path = tmp_path / "config.ini"
    app.template = {
        "version": 1,
        "label": {"width_mm": invalid_size, "height_mm": invalid_size},
        "elements": [],
    }

    size = app._validate_template_size_for_data_source()

    assert size == (62, 34)
    assert app.template["label"] == {"width_mm": 62, "height_mm": 34}


def test_element_editor_uses_responsive_scrollable_layout() -> None:
    source = inspect.getsource(LabelDesignerApp.open_element_editor)

    assert "set_initial_window_size(" in source
    assert "minimum_height=560" in source
    assert "editor_canvas = tk.Canvas" in source
    assert "width=420" in source
    assert "height=360" in source
    assert "editor_scroll = ttk.Scrollbar" in source
    assert 'editor.bind("<MouseWheel>", scroll_editor)' in source
    assert "buttons = ttk.Frame(editor" in source


def test_db_toolbar_reflows_in_narrow_window() -> None:
    source = inspect.getsource(LabelDesignerApp._build_canvas_toolbar)
    startup_source = inspect.getsource(LabelDesignerApp.__init__)

    assert 'text="데이터 소스"' in source
    assert 'text="파일"' in source
    assert "column_count = 1 if event.width < 680 else 2 if event.width < 900 else 4" in source
    assert "if column_count == ribbon_column_count" in source
    assert "def layout_size_row" in source
    assert "compact = event.width < 720" in source
    assert "if compact == size_row_compact" in source
    assert "size_apply_button.grid_configure(row=1" in source
    assert "minimum_width=960" in startup_source


def test_db_rows_open_in_a_separate_responsive_window() -> None:
    main_source = inspect.getsource(LabelDesignerApp._build_ui)
    dialog_source = inspect.getsource(LabelDesignerApp.open_data_source_window)

    assert "self.data_card.configure" not in main_source
    assert "dialog = tk.Toplevel(self)" in dialog_source
    assert "preferred_width=1180" in dialog_source
    assert "minimum_width=760" in dialog_source


def test_data_source_window_reuses_existing_instance(tmp_path) -> None:
    calls: list[str] = []
    dialog = SimpleNamespace(
        winfo_exists=lambda: True,
        deiconify=lambda: calls.append("deiconify"),
        lift=lambda: calls.append("lift"),
        focus_force=lambda: calls.append("focus"),
    )
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.data_source_window = dialog

    app.open_data_source_window()

    assert app.data_source_window is dialog
    assert calls == ["deiconify", "lift", "focus"]


def test_right_panel_is_db_workspace_without_duplicate_properties() -> None:
    source = inspect.getsource(LabelDesignerApp._build_property_panel)

    assert 'text="DB 작업"' in source
    assert 'text="연결 상태"' in source
    assert 'text="데이터 소스 열기"' in source
    assert 'text="미리보기 행"' not in source
    assert 'text="현재 행 값"' in source
    assert 'text="선택 개체 DB 연결"' in source
    assert 'text="현재 행 값"' in source
    assert 'text="위치/크기"' not in source
    assert 'text="서식"' not in source
    assert 'text="속성 적용"' not in source


def test_left_tool_panel_is_scrollable() -> None:
    source = inspect.getsource(LabelDesignerApp._build_ui)

    assert "tools_canvas = tk.Canvas" in source
    assert "width=320" in source
    assert "height=180" in source
    assert "tools_scroll = ttk.Scrollbar" in source
    assert 'widget.bind("<MouseWheel>", scroll_tools' in source


def test_right_workspace_is_scrollable_on_small_screens() -> None:
    source = inspect.getsource(LabelDesignerApp._build_ui)

    assert "properties_canvas = tk.Canvas" in source
    assert "width=300" in source
    assert "height=180" in source
    assert "properties_scroll = ttk.Scrollbar" in source
    assert 'widget.bind("<MouseWheel>", scroll_properties' in source


def test_main_workbench_keeps_a_small_canvas_request_between_side_panels() -> None:
    source = inspect.getsource(LabelDesignerApp._build_ui)

    assert "body.columnconfigure(0, minsize=330)" in source
    assert "body.columnconfigure(2, minsize=300)" in source
    assert "body.columnconfigure(0, minsize=290 if compact else 330)" in source
    assert "body.columnconfigure(2, minsize=280 if compact else 300)" in source
    assert "width=240" in source


def test_tool_buttons_keep_long_labels_full_width() -> None:
    source = inspect.getsource(LabelDesignerApp._build_tool_panel)

    assert "columnspan=columnspan" in source
    assert 'text="도안 불러오기"' in source
    assert "command=self.add_label_image_element" in source
    assert 'text="도안 적용"' in source
    assert "command=self.apply_design_template" in source
    assert "parent.columnconfigure(1, weight=1)" in source


def test_template_actions_are_moved_to_a_separate_window() -> None:
    tool_source = inspect.getsource(LabelDesignerApp._build_tool_panel)
    dialog_source = inspect.getsource(LabelDesignerApp.open_template_window)

    assert 'text="템플릿 작업"' not in tool_source
    for label in ("저장", "다른 이름으로 저장", "기존 파일 불러오기"):
        assert label in dialog_source
    for label in ("미리보기 PNG", "인쇄파일 생성", "템플릿 폴더"):
        assert label not in dialog_source
    assert "minimum_width=460" in dialog_source
    assert "minimum_height=420" in dialog_source


def test_template_window_reuses_existing_instance_and_refreshes_path(tmp_path) -> None:
    calls: list[str] = []
    paths: list[str] = []
    dialog = SimpleNamespace(
        winfo_exists=lambda: True,
        deiconify=lambda: calls.append("deiconify"),
        lift=lambda: calls.append("lift"),
        focus_force=lambda: calls.append("focus"),
    )
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template_path = tmp_path / "현재템플릿.gblabel"
    app.template_path_var = SimpleNamespace(set=paths.append)
    app.template_window = dialog

    app.open_template_window()

    assert paths == [str(app.template_path)]
    assert calls == ["deiconify", "lift", "focus"]


def test_primary_print_routes_by_db_connection(tmp_path) -> None:
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    calls: list[str] = []
    app.data_source_path = None
    app.run_output_test = lambda **values: calls.append(f"plain:{values['send_to_printer']}")
    app.run_selected_output = lambda **values: calls.append(f"selected:{values['send_to_printer']}")

    app.run_primary_print()
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.run_primary_print()

    assert calls == ["plain:True", "selected:True"]


def test_ctrl_p_invokes_primary_print_route() -> None:
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    bindings: dict[str, object] = {}
    calls: list[str] = []
    app.config = lambda **_values: None
    app.bind_all = lambda sequence, callback: bindings.__setitem__(sequence, callback)
    app.run_primary_print = lambda: calls.append("primary")

    app._build_menu()
    result = bindings["<Control-p>"](None)

    assert result == "break"
    assert calls == ["primary"]


def test_every_exposed_windows_font_face_strict_loads() -> None:
    choices = _available_font_names(SimpleNamespace())

    assert choices
    assert all(not name.startswith("@") for name in choices)
    for name in choices:
        assert _load_font(12, name).getname()[0]


def test_windows_font_registry_exposes_ttc_faces_and_variable_instances() -> None:
    registry = _font_registry()

    indexed_faces = [(name, face) for name, face in registry.items() if face.index > 0]
    variable_faces = [(name, face) for name, face in registry.items() if face.variation is not None]

    assert indexed_faces
    assert variable_faces
    for name, face in (indexed_faces[0], variable_faces[0]):
        assert isinstance(face, FontFace)
        assert _load_font(12, name).getname()[0]


def test_unknown_windows_font_fails_without_silent_fallback() -> None:
    with pytest.raises(ValueError, match="찾을 수 없습니다"):
        _load_font(12, "__GEBOGI_MISSING_FONT__")


def test_connect_data_source_failure_keeps_previous_connection(monkeypatch, tmp_path) -> None:
    previous_source = tmp_path / "기존DB.xlsx"
    previous_rows = [{"barcode": "009999", "item_name": "기존 상품"}]
    errors: list[tuple[str, str]] = []
    status: list[str] = []
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.data_source_path = previous_source
    app.db_rows = previous_rows
    app.data_source_headers = ("barcode", "item_name")
    app.selected_data_indexes = {0}
    app.preview_row = previous_rows[0]
    app.status_var = SimpleNamespace(set=status.append)
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.filedialog.askopenfilename",
        lambda **_kwargs: str(tmp_path / "손상DB.xlsx"),
    )

    def fail_to_load(_path):
        raise ValueError("엑셀 형식을 읽을 수 없습니다.")

    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_db_source", fail_to_load)
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.messagebox.showerror",
        lambda title, message: errors.append((title, message)),
    )

    app.connect_data_source()

    assert app.data_source_path == previous_source
    assert app.db_rows == previous_rows
    assert app.data_source_headers == ("barcode", "item_name")
    assert app.preview_row == previous_rows[0]
    assert errors == [("DB 연결 실패", "엑셀 형식을 읽을 수 없습니다.")]
    assert status[-1] == "DB 연결 실패 · 기존 데이터소스를 유지합니다."


def test_disconnect_data_source_closes_window_and_clears_selection(tmp_path) -> None:
    closed: list[bool] = []
    statuses: list[str] = []
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.data_source_window = SimpleNamespace()
    app.close_data_source_window = lambda: closed.append(True)
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.db_rows = [{"barcode": "001234"}]
    app.data_source_headers = ("barcode",)
    app.selected_data_indexes = {0}
    app.preview_row = app.db_rows[0]
    app.refresh_sample_options = lambda: None
    app.redraw = lambda: None
    app.status_var = SimpleNamespace(set=statuses.append)

    app.disconnect_data_source()

    assert closed == [True]
    assert app.data_source_path is None
    assert app.db_rows == []
    assert app.data_source_headers == ()
    assert app.selected_data_indexes == set()
    assert app.preview_row["barcode"] == ""
    assert statuses[-1] == "DB 연결을 해제했습니다."


def test_designer_text_tool_uses_actual_korean_db_header_when_available(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.elements = []
    app.selected_id = None
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.data_source_headers = ("바코드", "품명", "가격")
    app.db_rows = [{"barcode": "001234", "바코드": "001234", "item_name": "라벨 프린터", "품명": "라벨 프린터", "가격": "580000"}]
    app.preview_row = app.db_rows[0]
    app.load_selected_properties = lambda: None
    app.redraw = lambda: None
    app._animate_selected_element = lambda: None
    app.status_var = SimpleNamespace(set=lambda _value: None)

    app.add_element("text")

    assert app.elements[0]["field"] == "품명"
    assert app.elements[0]["text"] == "{{품명}}"
    assert render_element_text(app.elements[0], app.preview_row) == "라벨 프린터"


def test_selected_data_field_binds_text_object_to_exact_connected_header() -> None:
    element = _element("text", "새 텍스트", 5, 5, 22, 5, field="")
    values: dict[str, str] = {}
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.elements = [element]
    app.selected_id = str(element["id"])
    app.field_option_var = SimpleNamespace(get=lambda: "품명")
    app.field_option_to_key = {"연결 안 함": "", "품명": "품명"}
    app.preview_row = {"품명": "라벨 프린터"}
    app.field_var = SimpleNamespace(set=lambda value: values.__setitem__("field", value))
    app.text_var = SimpleNamespace(set=lambda value: values.__setitem__("text", value))
    app.redraw = lambda: values.__setitem__("redrawn", "yes")
    app.status_var = SimpleNamespace(set=lambda value: values.__setitem__("status", value))

    app._apply_selected_data_field()

    assert element["field"] == "품명"
    assert element["text"] == "{{품명}}"
    assert values["field"] == "품명"
    assert values["text"] == "{{품명}}"
    assert values["redrawn"] == "yes"


def test_element_editor_contains_connected_db_header_picker() -> None:
    source = inspect.getsource(LabelDesignerApp.open_element_editor)

    assert 'text="DB 열"' in source
    assert "editor_field_combo" in source
    assert "apply_editor_data_field" in source


def test_bound_text_tracks_each_selected_db_row() -> None:
    element = _element("text", "{{item_name}}", 5, 5, 30, 5, field="item_name")

    assert render_element_text(element, {"item_name": "첫 번째 상품"}) == "첫 번째 상품"
    assert render_element_text(element, {"item_name": "두 번째 상품"}) == "두 번째 상품"


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_bound_text_print_command_changes_with_each_db_row(language: str) -> None:
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [_element("text", "{{item_name}}", 5, 5, 30, 6, field="item_name", font_size=12)]

    first = app.render_designer_print_command(_config(language, "utf-8"), {"item_name": "DB-ITEM-001"}, 1)
    second = app.render_designer_print_command(_config(language, "utf-8"), {"item_name": "DB-ITEM-002"}, 1)

    assert first != second
    assert b"{{item_name}}" not in first
    assert b"{{item_name}}" not in second


def test_designer_selected_data_rows_follow_selected_indexes():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {"barcode": "fallback"}
    app.db_rows = [{"barcode": "002"}, {"barcode": "001"}, {"barcode": "003"}]
    app.selected_data_indexes = {2, 0}

    rows = app.selected_data_rows()

    assert [row["barcode"] for row in rows] == ["002", "003"]


def test_designer_selected_only_rows_require_explicit_checkbox_selection():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {"barcode": "preview"}
    app.db_rows = [{"barcode": "001"}, {"barcode": "002"}]
    app.selected_data_indexes = set()

    assert app.selected_data_rows(only_selected=True) == []
    assert app.selected_data_rows() == [{"barcode": "preview"}]


def test_designer_select_all_and_clear_output_rows(tmp_path):
    statuses: list[str] = []
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.db_rows = [{"barcode": "001"}, {"barcode": "002"}, {"barcode": "003"}]
    app.selected_data_indexes = set()
    app.refresh_data_panel = lambda: None
    app.status_var = SimpleNamespace(set=statuses.append)

    app.select_all_data_rows()

    assert app.selected_data_indexes == {0, 1, 2}
    assert statuses[-1] == "현재 표시된 데이터를 선택했습니다. 전체 선택 3건"

    app.clear_selected_data_rows()

    assert app.selected_data_indexes == set()
    assert statuses[-1] == "출력 대상 선택을 해제했습니다."


def test_designer_selected_output_requires_db_row_selection(monkeypatch, tmp_path):
    warnings: list[tuple[str, str]] = []
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.db_rows = [{"barcode": "001"}]
    app.selected_data_indexes = set()
    app.preview_row = app.db_rows[0]
    app.run_output_test = lambda **_kwargs: pytest.fail("selected output must not start without a checkbox selection")
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.messagebox.showwarning",
        lambda title, message: warnings.append((title, message)),
    )

    app.run_selected_output(send_to_printer=False)

    assert warnings == [("선택 인쇄", "데이터 소스 왼쪽의 선택 칸에서 출력할 행을 하나 이상 선택하세요.")]


def _direct_print_app(tmp_path: Path, rows: list[dict[str, str]], elements: list[dict[str, object]]):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.config_path = tmp_path / "config.ini"
    app.data_source_path = tmp_path / "상품DB.xlsx"
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = elements
    app.preview_row = rows[0] if rows else {}
    app.selected_data_rows = lambda **_kwargs: rows
    app.ask_print_quantity = lambda: 2
    app._selected_output_barcode_type = lambda: None
    app._write_output_test_config = lambda *_args: None
    app._print_config_summary = lambda _path: "TEST / ZPL"
    app._write_print_result_log = lambda **_kwargs: tmp_path / "designer_print_last.log"
    statuses: list[str] = []
    app.status_var = SimpleNamespace(set=statuses.append)
    return app, statuses


@pytest.mark.parametrize(
    "elements",
    [
        [],
        [_element("text", "", 1, 1, 20, 5)],
        [{**_element("image", "", 1, 1, 20, 10), "printable": False}],
    ],
)
def test_print_rejects_template_without_renderable_content_before_quantity(monkeypatch, tmp_path, elements) -> None:
    app, _statuses = _direct_print_app(tmp_path, [{"barcode": ""}], elements)
    app.ask_print_quantity = lambda: pytest.fail("quantity dialog must not open for an empty output")
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.messagebox.showwarning",
        lambda title, message: warnings.append((title, message)),
    )

    app.run_output_test(send_to_printer=True)

    assert warnings
    assert warnings[0][0] == "인쇄할 내용 확인"


def test_direct_print_uses_quantity_selected_in_popup(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "001", "print_qty": "1"}, {"barcode": "002", "print_qty": "9"}]
    app, _statuses = _direct_print_app(
        tmp_path,
        rows,
        [_element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")],
    )
    app.ask_print_quantity = lambda: 5
    rendered: list[tuple[str, int]] = []
    app.render_designer_print_command = lambda _config, row, qty: rendered.append((row["print_qty"], qty)) or row["barcode"].encode("ascii")
    app._write_designer_command_file = lambda _config, _out, _payload, *, index: tmp_path / f"{index}.zpl"
    app._send_designer_print = lambda _config, _payload: None
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showinfo", lambda *_args: None)

    app.run_output_test(send_to_printer=True, selected_only=True)

    assert rendered == [("5", 5), ("5", 5)]


def test_direct_print_stops_when_quantity_popup_is_cancelled(monkeypatch, tmp_path) -> None:
    app, statuses = _direct_print_app(
        tmp_path,
        [{"barcode": "001"}],
        [_element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")],
    )
    app.ask_print_quantity = lambda: None
    app.render_designer_print_command = lambda *_args: pytest.fail("cancelled print must not render a command")

    app.run_output_test(send_to_printer=True, selected_only=True)

    assert statuses[-1] == "인쇄 매수 선택을 취소했습니다."


def test_designer_quantity_dialog_uses_clear_short_modal_controls() -> None:
    source = inspect.getsource(LabelDesignerApp.ask_print_quantity)

    assert 'dialog.title("인쇄 매수 선택")' in source
    assert "선택한 각 항목에 같은 수량이 적용됩니다." in source
    assert "ttk.Spinbox" in source
    assert 'text="인쇄 시작"' in source
    assert 'text="취소"' in source


def test_selected_print_pre_renders_all_rows_before_send_without_confirmation(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "001234"}, {"barcode": "000007"}]
    element = _element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")
    app, _statuses = _direct_print_app(tmp_path, rows, [element])
    events: list[str] = []
    app.render_designer_print_command = lambda _config, row, _qty: events.append(f"render:{row['barcode']}") or row["barcode"].encode("ascii")
    app._write_designer_command_file = (
        lambda _config, _out_dir, payload, *, index: events.append(f"write:{index}") or tmp_path / f"{index}.zpl"
    )
    app._send_designer_print = lambda _config, payload: events.append(f"send:{payload.decode('ascii')}")
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.messagebox.askyesno",
        lambda *_args: pytest.fail("print confirmation must not open"),
    )
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showinfo", lambda *_args: None)

    app.run_output_test(send_to_printer=True, selected_only=True)

    assert events == [
        "render:001234",
        "render:000007",
        "write:1",
        "write:2",
        "send:001234",
        "send:000007",
    ]


def test_later_row_render_failure_sends_no_print_jobs(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "001234"}, {"barcode": "000007"}]
    element = _element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")
    app, _statuses = _direct_print_app(tmp_path, rows, [element])
    rendered: list[str] = []
    sends: list[bytes] = []

    def render(_config, row, _qty):
        rendered.append(row["barcode"])
        if row["barcode"] == "000007":
            raise ValueError("second row invalid")
        return row["barcode"].encode("ascii")

    app.render_designer_print_command = render
    app._write_designer_command_file = lambda *_args, **_kwargs: pytest.fail("no file may be written after render failure")
    app._send_designer_print = lambda _config, payload: sends.append(payload)
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.messagebox.askyesno",
        lambda *_args: pytest.fail("confirmation must not open after render failure"),
    )
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showerror", lambda *_args: None)

    app.run_output_test(send_to_printer=True, selected_only=True)

    assert rendered == ["001234", "000007"]
    assert sends == []


def test_print_send_failure_reports_retryable_counts(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "001"}, {"barcode": "002"}, {"barcode": "003"}]
    element = _element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")
    app, statuses = _direct_print_app(tmp_path, rows, [element])
    app.render_designer_print_command = lambda _config, row, _qty: row["barcode"].encode("ascii")
    app._write_designer_command_file = lambda _config, _out, _payload, *, index: tmp_path / f"{index}.zpl"
    sent: list[str] = []

    def send(_config, payload: bytes) -> None:
        value = payload.decode("ascii")
        sent.append(value)
        if value == "002":
            raise OSError("printer offline")

    app._send_designer_print = send
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.askyesno", lambda *_args: pytest.fail("print confirmation must not open"))
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.messagebox.showerror",
        lambda title, message: errors.append((title, message)),
    )

    app.run_output_test(send_to_printer=True, selected_only=True)

    assert sent == ["001", "002"]
    assert "완료 1건 / 재시도 가능 2건" in statuses[-1]
    assert errors[-1][0] == "인쇄 오류"
    assert "인쇄 버튼을 다시 누르세요" in errors[-1][1]


def test_designer_send_failure_retries_remaining_items(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "001"}, {"barcode": "002"}, {"barcode": "003"}]
    app, statuses = _direct_print_app(
        tmp_path,
        rows,
        [_element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")],
    )
    app.render_designer_print_command = lambda _config, row, _qty: row["barcode"].encode("ascii")
    app._write_designer_command_file = lambda _config, _out, _payload, *, index: tmp_path / f"{index}.zpl"
    first_attempt: list[str] = []

    def fail_second(_config, payload: bytes) -> None:
        value = payload.decode("ascii")
        first_attempt.append(value)
        if value == "002":
            raise OSError("printer offline")

    app._send_designer_print = fail_second
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.askyesno", lambda *_args: True)
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_designer_app.messagebox.showerror",
        lambda title, message: errors.append((title, message)),
    )
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showinfo", lambda *_args: None)

    app.run_output_test(send_to_printer=True, selected_only=True)

    progress_path = tmp_path / "out" / DESIGNER_PROGRESS_FILE_NAME
    assert first_attempt == ["001", "002"]
    assert [PrintProgress.load(progress_path).status(index) for index in (1, 2, 3)] == [
        "sent",
        "pending",
        "pending",
    ]

    resumed: list[str] = []
    app._send_designer_print = lambda _config, payload: resumed.append(payload.decode("ascii"))
    app.run_output_test(send_to_printer=True, selected_only=True)

    assert resumed == ["002", "003"]
    assert statuses[-1].startswith("인쇄 완료 2건")
    assert [PrintProgress.load(progress_path).status(index) for index in (1, 2, 3)] == [
        "sent",
        "sent",
        "sent",
    ]


def test_designer_first_item_failure_allows_next_explicit_print(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "001"}, {"barcode": "002"}]
    app, statuses = _direct_print_app(
        tmp_path,
        rows,
        [_element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")],
    )
    app.render_designer_print_command = lambda _config, row, _qty: row["barcode"].encode("ascii")
    app._write_designer_command_file = lambda _config, _out, _payload, *, index: tmp_path / f"{index}.zpl"
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.askyesno", lambda *_args: True)
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showerror", lambda *_args: None)
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showinfo", lambda *_args: None)
    app._send_designer_print = lambda _config, _payload: (_ for _ in ()).throw(OSError("offline"))
    app.run_output_test(send_to_printer=True, selected_only=True)

    sends: list[bytes] = []
    app._send_designer_print = lambda _config, payload: sends.append(payload)
    app.run_output_test(send_to_printer=True, selected_only=True)

    assert sends == [b"001", b"002"]
    assert statuses[-1].startswith("인쇄 완료 2건")


def test_designer_explicit_print_recovers_persisted_unknown_item(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "001"}, {"barcode": "002"}]
    app, statuses = _direct_print_app(
        tmp_path,
        rows,
        [_element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")],
    )
    app.render_designer_print_command = lambda _config, row, _qty: row["barcode"].encode("ascii")
    app._write_designer_command_file = lambda _config, _out, _payload, *, index: tmp_path / f"{index}.zpl"
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showinfo", lambda *_args: None)

    progress_path = tmp_path / "out" / DESIGNER_PROGRESS_FILE_NAME
    progress = PrintProgress.open_for_job(
        progress_path,
        [b"001", b"002"],
        "utf-8",
        label_designer_app._designer_print_job_context(SimpleNamespace()),
    )
    progress.mark_sending(1)

    sent: list[bytes] = []
    app._send_designer_print = lambda _config, payload: sent.append(payload)
    app.run_output_test(send_to_printer=True, selected_only=True)

    assert sent == [b"001", b"002"]
    assert statuses[-1].startswith("인쇄 완료 2건")
    assert PrintProgress.load(progress_path).unknown_indexes == []


def test_designer_new_job_replaces_stale_unknown_progress(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "NEW"}]
    app, statuses = _direct_print_app(
        tmp_path,
        rows,
        [_element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")],
    )
    app.render_designer_print_command = lambda _config, row, _qty: row["barcode"].encode("ascii")
    app._write_designer_command_file = lambda _config, _out, _payload, *, index: tmp_path / f"{index}.zpl"
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showinfo", lambda *_args: None)

    progress_path = tmp_path / "out" / DESIGNER_PROGRESS_FILE_NAME
    previous = PrintProgress.open_for_job(
        progress_path,
        [b"OLD"],
        "utf-8",
        label_designer_app._designer_print_job_context(SimpleNamespace()),
    )
    previous.mark_sending(1)

    sent: list[bytes] = []
    app._send_designer_print = lambda _config, payload: sent.append(payload)
    app.run_output_test(send_to_printer=True, selected_only=True)

    assert sent == [b"NEW"]
    assert statuses[-1].startswith("인쇄 완료 1건")
    assert PrintProgress.load(progress_path).unknown_indexes == []


def test_designer_repeated_explicit_print_restarts_completed_job(monkeypatch, tmp_path) -> None:
    rows = [{"barcode": "001"}, {"barcode": "002"}]
    app, statuses = _direct_print_app(
        tmp_path,
        rows,
        [_element("barcode", "{{barcode}}", 2, 2, 30, 12, field="barcode")],
    )
    app.render_designer_print_command = lambda _config, row, _qty: row["barcode"].encode("ascii")
    app._write_designer_command_file = lambda _config, _out, _payload, *, index: tmp_path / f"{index}.zpl"
    sent: list[str] = []
    app._send_designer_print = lambda _config, payload: sent.append(payload.decode("ascii"))
    monkeypatch.setattr("barcode_label_automation.label_designer_app.load_config", lambda _path: SimpleNamespace())
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.showinfo", lambda *_args: None)

    app.run_output_test(send_to_printer=True, selected_only=True)
    app.run_output_test(send_to_printer=True, selected_only=True)

    assert sent == ["001", "002", "001", "002"]
    assert statuses[-1].startswith("인쇄 완료 2건")


def test_designer_unknown_resolution_dialog_has_three_explicit_choices():
    module = __import__("barcode_label_automation.label_designer_app", fromlist=["_ask_unknown_resolution"])
    source = inspect.getsource(module._ask_unknown_resolution)

    assert 'text="출력됨"' in source
    assert 'text="출력 안 됨"' in source
    assert 'text="취소"' in source


def test_designer_output_menu_exposes_selected_output_actions():
    source = inspect.getsource(LabelDesignerApp._build_canvas_toolbar) + inspect.getsource(LabelDesignerApp.refresh_data_panel)

    assert "선택 항목 인쇄파일" in source
    assert "선택 항목 인쇄" in source
    assert "선택 인쇄" in source


def test_designer_ignores_redundant_data_selection_event():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app._refreshing_data_panel = False
    app.data_tree = SimpleNamespace(selection=lambda: ("0",))
    app.db_rows = [{"barcode": "001"}]
    app.selected_data_indexes = {0}
    app.preview_row = app.db_rows[0]
    app.sample_combo_values = ["1. 001"]
    app.refresh_data_panel = lambda: pytest.fail("redundant selection should not refresh the data panel")
    app.redraw = lambda: pytest.fail("redundant selection should not redraw the canvas")

    app.select_data_tree_row()

    assert app.selected_data_indexes == {0}


def test_designer_command_file_names_are_indexed(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)

    first = app._write_designer_command_file(_config("tspl", "utf-8"), tmp_path, b"FIRST", index=1)
    second = app._write_designer_command_file(_config("tspl", "utf-8"), tmp_path, b"SECOND", index=2)

    assert first.name == "designer_label_001.tspl"
    assert second.name == "designer_label_002.tspl"
    assert first.read_bytes() == b"FIRST"
    assert second.read_bytes() == b"SECOND"


def test_designer_prints_image_element_as_bitmap(tmp_path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (20, 12), "black").save(image_path)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [_element("image", "sample", 5, 5, 20, 12)]
    app.elements[0]["image_path"] = image_path.name
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    command = app.render_designer_print_command(_config("tspl", "utf-8"), row, 1)

    assert b"BITMAP " in command


@pytest.mark.parametrize(
    ("language", "marker"),
    [("slcs", b"BMP"), ("tspl", b"BITMAP "), ("zpl", b"^GFA")],
)
def test_designer_reference_image_is_not_printed(tmp_path, language: str, marker: bytes):
    image_path = tmp_path / "assets" / "images" / "guide.png"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (80, 40), "black").save(image_path)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    element = _image_element_for_label(
        "assets/images/guide.png",
        "guide",
        app.template["label"],  # type: ignore[index]
        (80, 40),
        fit_to_label=True,
        printable=False,
    )
    app.elements = [element]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    command = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    assert marker not in command


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_designer_full_label_image_prints_at_label_dot_size(tmp_path, language: str):
    image_path = tmp_path / "assets" / "images" / "full-label.png"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (50, 40), "black").save(image_path)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [
        _image_element_for_label(
            "assets/images/full-label.png",
            "full-label",
            app.template["label"],  # type: ignore[index]
            (50, 40),
            fit_to_label=True,
        )
    ]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    command = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    assert _bitmap_dimensions(command, language) == (mm_to_dots(50, 203), mm_to_dots(40, 203))


def test_designer_auto_fit_scale_keeps_large_label_inside_canvas():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.canvas = _FakeCanvas(width=760, height=520)

    scale = app._fit_canvas_scale(120, 90)
    layout = _calculate_canvas_label_layout(760, 520, 120, 90)

    assert scale == layout[0]
    assert 0 < scale <= 24
    assert layout[1] >= 0
    assert layout[2] >= 0
    assert layout[1] + layout[3] + 7 <= 760
    assert layout[2] + layout[4] + 7 <= 520


def test_designer_canvas_layout_keeps_shadow_inside_short_canvas() -> None:
    scale, origin_x, origin_y, width, height = _calculate_canvas_label_layout(530, 90, 60, 35)

    assert scale < 1.2
    assert origin_x >= 0
    assert origin_y >= 0
    assert origin_x + width + 7 <= 530
    assert origin_y + height + 7 <= 90


def test_designer_tspl_bitmap_uses_white_background_black_dots():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    blank = Image.new("1", (16, 2), 1)
    command = app._tspl_bitmap_command(0, 0, blank)
    fields = command.split(b",", 5)
    width_bytes = int(fields[2])
    height = int(fields[3])
    blank_payload = fields[5][: width_bytes * height]

    black = Image.new("1", (8, 1), 1)
    black.putpixel((0, 0), 0)
    black_command = app._tspl_bitmap_command(0, 0, black)
    black_payload = black_command.split(b",", 5)[5][:1]

    assert blank_payload == b"\xff\xff\xff\xff"
    assert black_payload == b"\x7f"


def test_designer_tspl_reverse_text_intentionally_prints_black_background():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = _element("text", "A", 0, 0, 12, 8, font_size=12)
    element["reverse"] = True
    command = app._tspl_text_bitmap_command(0, 0, 96, 48, "A", element)
    fields = command.split(b",", 5)
    width_bytes = int(fields[2])
    height = int(fields[3])
    payload = fields[5][: width_bytes * height]

    assert payload[0] == 0x00
    assert any(byte != 0x00 for byte in payload)


def test_designer_print_renderer_uses_configured_printer_language():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [
        _element("text", "ITEM: {{item_name}}", 5, 4, 40, 6, font_size=14, align="center"),
        _element("barcode", "{{barcode}}", 5, 12, 40, 14, barcode_type="code128"),
        _element("field", "LOT: {{lot_no}} / QTY: {{qty}}", 5, 29, 40, 6, font_size=12, align="center"),
        _element("box", "", 2, 2, 46, 34),
    ]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "5J3P7YAYWXL5",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }

    slcs = app.render_designer_print_command(_config("slcs", "cp949"), row, 2)
    assert slcs.startswith(b"CB\r\n")
    assert slcs.count(b"BMP") >= 2
    assert slcs.endswith(b"P2\r\n")
    assert app.render_designer_print_command(_config("tspl", "utf-8"), row, 2).startswith(b"SIZE 50 mm,40 mm\n")
    assert app.render_designer_print_command(_config("zpl", "utf-8"), row, 2).startswith(b"^XA\n")


def test_designer_zpl_multiline_text_prints_as_bitmap():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [_element("multiline_text", "제품명\n{{item_name}}", 5, 5, 30, 12, font_size=12)]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "5J3P7YAYWXL5",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    command = app.render_designer_print_command(_config("zpl", "utf-8"), row, 1)

    assert b"^GFA" in command


@pytest.mark.parametrize(
    ("language", "marker", "line_command"),
    [
        ("slcs", b"BMP", b"BD"),
        ("tspl", b"BITMAP ", b"BAR "),
        ("zpl", b"^GFA", b"^GB"),
    ],
)
def test_rotated_designer_non_line_objects_use_bitmaps_and_lines_use_direct_commands(
    language: str,
    marker: bytes,
    line_command: bytes,
    tmp_path,
):
    source_image = tmp_path / "sample.png"
    Image.new("RGB", (24, 12), "black").save(source_image)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [
        {**_element("text", "세로 텍스트", 2, 2, 16, 5, font_size=10), "rotation": 90},
        {**_element("barcode", "ABC123", 20, 2, 24, 10, barcode_type="code128"), "rotation": 270},
        {**_element("box", "", 2, 14, 10, 8), "rotation": 90},
        {**_element("line", "", 14, 14, 10, 8), "rotation": 180},
        {**_element("table", "", 26, 14, 10, 8), "rotation": 270},
        {**_element("image", "", 38, 14, 8, 10), "image_path": source_image.name, "rotation": 90},
    ]
    row = {"barcode": "ABC123", "print_qty": "1"}

    command = app.render_designer_print_command(_config(language, "cp949" if language == "slcs" else "utf-8"), row, 1)

    assert command.count(marker) >= len(app.elements) - 1
    assert line_command in command


def test_rotated_text_preview_fits_inside_the_original_object_bounds():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = {**_element("text", "ROTATE", 0, 0, 30, 8, font_size=12), "rotation": 90}

    image = app._render_element_bitmap(element, {}, 240, 64, transparent=False)
    black_bbox = ImageChops.invert(image.convert("L")).getbbox()

    assert image.size == (240, 64)
    assert black_bbox is not None
    assert black_bbox[3] - black_bbox[1] > black_bbox[2] - black_bbox[0]


def test_designer_line_bitmap_is_horizontal_and_rotates_without_becoming_diagonal():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    line = _element("line", "", 0, 0, 20, 2)
    line["stroke_width"] = 0.8

    horizontal = app._render_element_bitmap(line, {}, 200, 20, transparent=False)
    horizontal_bbox = ImageChops.invert(horizontal.convert("L")).getbbox()

    assert horizontal_bbox is not None
    assert horizontal_bbox[2] - horizontal_bbox[0] > (horizontal_bbox[3] - horizontal_bbox[1]) * 10
    assert horizontal.getpixel((0, 0)) == 1
    assert horizontal.getpixel((199, 19)) == 1

    vertical = app._render_element_bitmap({**line, "rotation": 90}, {}, 200, 20, transparent=False)
    vertical_bbox = ImageChops.invert(vertical.convert("L")).getbbox()

    assert vertical_bbox is not None
    assert vertical_bbox[3] - vertical_bbox[1] > (vertical_bbox[2] - vertical_bbox[0]) * 2


def test_designer_line_preview_export_is_horizontal_not_diagonal():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {}
    image = Image.new("RGB", (240, 120), "white")
    line = _element("line", "", 5, 6, 20, 2)
    line["stroke_width"] = 0.8

    app._draw_element_to_image(image, ImageDraw.Draw(image), line, 8)
    bbox = ImageChops.invert(image.convert("L")).getbbox()

    assert bbox is not None
    assert bbox[2] - bbox[0] > (bbox[3] - bbox[1]) * 10


def test_designer_rotated_line_preview_export_is_vertical_not_diagonal():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {}
    image = Image.new("RGB", (240, 120), "white")
    line = {**_element("line", "", 12, 5, 2, 20), "rotation": 90}
    line["stroke_width"] = 0.8

    app._draw_element_to_image(image, ImageDraw.Draw(image), line, 8)
    bbox = ImageChops.invert(image.convert("L")).getbbox()

    assert bbox is not None
    assert bbox[3] - bbox[1] > (bbox[2] - bbox[0]) * 10


def test_designer_canvas_draws_lines_on_a_single_axis():
    class FakeCanvas:
        def __init__(self):
            self.lines: list[tuple[tuple[float, ...], dict[str, object]]] = []

        def create_line(self, *args, **kwargs):
            self.lines.append((args, kwargs))

    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.canvas = FakeCanvas()
    app.scale = 8
    app.selected_id = ""
    app.element_bbox = lambda _element: (10.0, 20.0, 170.0, 36.0)

    app.draw_element(_element("line", "", 0, 0, 20, 2))
    app.draw_element({**_element("line", "", 0, 0, 2, 20), "rotation": 90})

    horizontal_args, _horizontal_kwargs = app.canvas.lines[0]
    vertical_args, _vertical_kwargs = app.canvas.lines[1]
    assert horizontal_args[1] == horizontal_args[3]
    assert vertical_args[0] == vertical_args[2]


def test_element_editor_includes_supported_object_direction_options():
    source = inspect.getsource(LabelDesignerApp.open_element_editor)

    assert "rotation_var" in source
    assert "90도 시계 방향" in inspect.getsource(__import__("barcode_label_automation.label_designer_app", fromlist=["ELEMENT_ROTATION_LABELS"]))
    assert 'add_row(6, "방향", rotation_combo)' in source


def test_designer_zpl_single_line_text_uses_selected_font_bitmap():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [_element("text", "한 줄 텍스트", 5, 5, 30, 8, font_size=12, font_name="Malgun Gothic")]

    command = app.render_designer_print_command(_config("zpl", "utf-8"), {}, 1)

    assert b"^GFA" in command
    assert b"^A0N" not in command
    assert b"^FD" not in command


@pytest.mark.parametrize(
    ("language", "media_handling", "expected"),
    [
        ("slcs", "tear_off", b"CUTn\r\n"),
        ("slcs", "cutter", b"CUTy\r\n"),
        ("tspl", "tear_off", b"SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n"),
        ("tspl", "cutter", b"SET PEEL OFF\nSET CUTTER 1\n"),
        ("tspl", "peeler", b"SET CUTTER OFF\nSET PEEL ON\n"),
        ("zpl", "tear_off", b"^MMT\n"),
        ("zpl", "cutter", b"^MMC\n"),
        ("zpl", "peeler", b"^MMP\n"),
    ],
)
def test_designer_print_renderer_applies_supported_media_handling_options(language: str, media_handling: str, expected: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = []
    row = {"item_code": "A1002", "item_name": "SENSOR", "barcode": "12345678", "lot_no": "LOT", "qty": "1", "print_qty": "1"}

    assert expected in app.render_designer_print_command(_config(language, "cp949" if language == "slcs" else "utf-8", media_handling=media_handling), row, 1)


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("slcs", b"SOB\r\n"),
        ("tspl", b"DIRECTION 0\n"),
        ("zpl", b"^POI\n"),
    ],
)
def test_designer_print_renderer_applies_whole_label_180_degree_orientation(language: str, expected: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = []
    row = {"item_code": "A1002", "item_name": "SENSOR", "barcode": "12345678", "lot_no": "LOT", "qty": "1", "print_qty": "1"}

    command = app.render_designer_print_command(
        _config(language, "cp949" if language == "slcs" else "utf-8", print_orientation="rotate_180"),
        row,
        1,
    )

    assert expected in command


@pytest.mark.parametrize(
    ("language", "media_type", "expected"),
    [
        ("slcs", "gap", b"SL320,24,G\r\n"),
        ("slcs", "black_mark", b"SL320,24,B\r\n"),
        ("slcs", "continuous", b"SL320,0,C\r\n"),
        ("tspl", "gap", b"GAP 3 mm,0 mm\n"),
        ("tspl", "black_mark", b"BLINE 3 mm,0 mm\n"),
        ("tspl", "continuous", b"GAP 0,0\n"),
        ("zpl", "gap", b"^MNY\n"),
        ("zpl", "black_mark", b"^MNM,0\n"),
        ("zpl", "continuous", b"^MNN\n"),
    ],
)
def test_designer_print_renderer_applies_supported_media_type_options(language: str, media_type: str, expected: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = []
    row = {"item_code": "A1002", "item_name": "SENSOR", "barcode": "12345678", "lot_no": "LOT", "qty": "1", "print_qty": "1"}

    command = app.render_designer_print_command(
        _config(language, "cp949" if language == "slcs" else "utf-8", media_type=media_type),
        row,
        1,
    )

    assert expected in command


def test_designer_print_renderer_rejects_slcs_peeler_until_command_is_confirmed():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = []
    row = {"item_code": "A1002", "item_name": "SENSOR", "barcode": "12345678", "lot_no": "LOT", "qty": "1", "print_qty": "1"}

    with pytest.raises(ValueError, match="BIXOLON/SLCS peeler"):
        app.render_designer_print_command(_config("slcs", "cp949", media_handling="peeler"), row, 1)


@pytest.mark.parametrize(
    ("barcode_type", "value"),
    [
        ("code128", "ABC123"),
        ("gs1_128", "(01)08801234567890"),
        ("code39", "ABC-123"),
        ("ean13", "590123412345"),
        ("ean8", "5512345"),
        ("upca", "04210000526"),
        ("itf", "123456"),
        ("codabar", "A12345A"),
        ("pharmacode", "12345"),
    ],
)
def test_1d_barcode_types_render_real_bitmap_images(barcode_type: str, value: str):
    image = _render_1d_barcode_image(barcode_type, value, 260, 80, _element("barcode", value, 1, 1, 30, 10, barcode_type=barcode_type))

    assert image.size == (260, 80)
    assert ImageChops.invert(image.convert("L")).getbbox() is not None


def test_barcode_preview_rgba_makes_white_background_transparent():
    element = _element("barcode", "ABC123", 1, 1, 30, 10, barcode_type="code128")
    source = _render_1d_barcode_image("code128", "ABC123", 260, 80, element)

    image = _barcode_image_to_transparent_rgba(source)
    alpha = image.getchannel("A")
    black_bbox = ImageChops.invert(source.convert("L")).getbbox()

    assert image.mode == "RGBA"
    assert black_bbox is not None
    assert alpha.getbbox() == black_bbox
    assert alpha.getpixel((0, 0)) == 0


def test_ean13_rejects_wrong_check_digit():
    with pytest.raises(ValueError, match="체크디지트"):
        _render_1d_barcode_image("ean13", "5901234123450", 260, 80, _element("barcode", "5901234123450", 1, 1, 30, 10, barcode_type="ean13"))


@pytest.mark.parametrize(("barcode_type", "value"), [("ean13", "590123412345"), ("upca", "04210000526"), ("ean8", "5512345")])
def test_ean_upc_rendering_has_extended_guard_bars(barcode_type: str, value: str):
    image = _render_1d_barcode_image(barcode_type, value, 260, 90, _element("barcode", value, 1, 1, 30, 10, barcode_type=barcode_type))
    pixels = image.load()
    top = next(y for y in range(image.height) if any(pixels[x, y] == 0 for x in range(image.width)))
    runs = []
    for x in range(image.width):
        if pixels[x, top] != 0:
            continue
        run = 0
        y = top
        while y < image.height and pixels[x, y] == 0:
            run += 1
            y += 1
        if run > 10:
            runs.append(run)

    assert max(runs) - min(runs) >= 4


def test_qr_barcode_renders_real_bitmap_and_preserves_string_value():
    element = _element("barcode", "001234567890", 1, 1, 18, 18, barcode_type="qr")
    element["barcode_options"]["cell_size"] = 4

    image = _render_qr_code_image("001234567890", 180, 180, element)
    other = _render_qr_code_image("101234567890", 180, 180, element)
    black_bbox = ImageChops.invert(image.convert("L")).getbbox()

    assert image.size == (180, 180)
    assert black_bbox is not None
    assert black_bbox[0] > 0
    assert black_bbox[1] > 0
    assert black_bbox[2] < image.width
    assert black_bbox[3] < image.height
    assert ImageChops.difference(image.convert("L"), other.convert("L")).getbbox() is not None


@pytest.mark.parametrize("barcode_type", sorted(BARCODE_2D_BITMAP_TYPES))
def test_2d_barcode_types_render_real_bitmap_images(barcode_type: str):
    width, height = (360, 160) if barcode_type in {"pdf417", "micropdf417"} else (180, 180)
    element = _element("barcode", "A1001-250531", 1, 1, 36 if barcode_type in {"pdf417", "micropdf417"} else 18, 16 if barcode_type in {"pdf417", "micropdf417"} else 18, barcode_type=barcode_type)

    image = _render_2d_barcode_image(barcode_type, _barcode_value_for_type(barcode_type), width, height, element)
    black_bbox = ImageChops.invert(image.convert("L")).getbbox()

    assert image.size == (width, height)
    assert black_bbox is not None
    assert black_bbox[0] >= 0
    assert black_bbox[1] >= 0
    assert black_bbox[2] <= image.width
    assert black_bbox[3] <= image.height


@pytest.mark.parametrize("barcode_type", sorted(DESIGNER_PRINT_SUPPORTED_BARCODE_TYPES))
def test_designer_preview_uses_full_element_box_for_every_exposed_barcode_type(barcode_type: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    value = _barcode_value_for_type(barcode_type)
    width_mm, height_mm = _barcode_element_size_mm(barcode_type)
    element = _element("barcode", "{{barcode}}", 8, 6, width_mm, height_mm, barcode_type=barcode_type)
    app.template = {"version": 1, "label": {"width_mm": 60, "height_mm": 40}, "elements": []}
    app.elements = [element]
    app.preview_row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": value,
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    image = app.render_preview_image()
    crop = image.crop((8 * 8, 6 * 8, (8 + width_mm) * 8, (6 + height_mm) * 8))
    black_bbox = ImageChops.invert(crop.convert("L")).getbbox()

    assert crop.size == (width_mm * 8, height_mm * 8)
    assert black_bbox is not None


@pytest.mark.parametrize("barcode_type", sorted(DESIGNER_PRINT_SUPPORTED_BARCODE_TYPES))
@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_designer_prints_every_exposed_barcode_type_as_full_size_bitmap(language: str, barcode_type: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    value = _barcode_value_for_type(barcode_type)
    width_mm, height_mm = _barcode_element_size_mm(barcode_type)
    element = _element("barcode", "{{barcode}}", 8, 6, width_mm, height_mm, barcode_type=barcode_type)
    app.template = {"version": 1, "label": {"width_mm": 60, "height_mm": 40}, "elements": []}
    app.elements = [element]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": value,
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }
    expected_marker = {"slcs": b"BMP", "tspl": b"BITMAP ", "zpl": b"^GFA"}[language]
    expected_size = (mm_to_dots(width_mm, 203), mm_to_dots(height_mm, 203))

    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    assert expected_marker in payload
    assert _bitmap_dimensions(payload, language) == expected_size


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("slcs", b"BMP"),
        ("tspl", b"BITMAP "),
        ("zpl", b"^GFA"),
    ],
)
def test_designer_prints_non_code128_1d_as_matching_bitmap(language: str, expected: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [_element("barcode", "A12345A", 5, 10, 40, 16, barcode_type="codabar")]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }

    command = app.render_designer_print_command(_config(language, "utf-8"), row, 2)
    payload = command if isinstance(command, bytes) else command.encode("ascii")

    assert expected in payload


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("slcs", b"BD"),
        ("tspl", b"BOX "),
        ("zpl", b"^GB"),
    ],
)
def test_designer_prints_table_object_for_all_printer_languages(language: str, expected: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    table = _element("table", "", 4, 5, 30, 18)
    table["table_rows"] = 3
    table["table_cols"] = 4
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [table]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }

    command = app.render_designer_print_command(_config(language, "utf-8"), row, 2)
    payload = command if isinstance(command, bytes) else command.encode("ascii")

    assert expected in payload


def test_designer_tspl_table_uses_configured_rows_and_columns():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    table = _element("table", "", 4, 5, 30, 18)
    table["table_rows"] = 4
    table["table_cols"] = 2
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [table]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }

    command = app.render_designer_print_command(_config("tspl", "utf-8"), row, 2)

    assert command.count(b"BOX ") == 1
    assert command.count(b"BAR ") == 4


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_designer_table_print_uses_custom_divider_positions(language: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    table = _element("table", "", 4, 5, 30, 18)
    table["table_rows"] = 3
    table["table_cols"] = 3
    table["table_col_positions"] = [0.2, 0.8]
    table["table_row_positions"] = [0.25, 0.75]
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [table]
    row = {"item_code": "A1002", "item_name": "SENSOR", "barcode": "12345678", "lot_no": "LOT", "qty": "1", "print_qty": "1"}
    x, y = mm_to_dots(4, 203), mm_to_dots(5, 203)
    width, height = mm_to_dots(30, 203), mm_to_dots(18, 203)
    first_col = x + round(width * 0.2)
    first_row = y + round(height * 0.25)

    command = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    if language == "slcs":
        thickness = mm_to_dots(0.3, 203)
        assert f"BD{first_col},{y},{first_col + thickness - 1},{y + height - 1},O\r\n".encode("ascii") in command
        assert f"BD{x},{first_row},{x + width - 1},{first_row + thickness - 1},O\r\n".encode("ascii") in command
    elif language == "tspl":
        assert f"BAR {first_col},{y},".encode("ascii") in command
        assert f"BAR {x},{first_row},{width},".encode("ascii") in command
    else:
        assert f"^FO{first_col},{y}^GB".encode("ascii") in command
        assert f"^FO{x},{first_row}^GB".encode("ascii") in command


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_designer_shape_stroke_width_reaches_print_commands(language: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    box = _element("box", "", 4, 5, 30, 18)
    box["stroke_width"] = 1.0
    line = _element("line", "", 2, 3, 20, 0.5)
    line["stroke_width"] = 0.8
    table = _element("table", "", 10, 12, 20, 10)
    table["stroke_width"] = 1.2
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [box, line, table]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }
    box_x, box_y = mm_to_dots(4, 203), mm_to_dots(5, 203)
    box_w, box_h = mm_to_dots(30, 203), mm_to_dots(18, 203)
    line_x, line_y = mm_to_dots(2, 203), mm_to_dots(3, 203)
    line_w = mm_to_dots(20, 203)
    table_x, table_y = mm_to_dots(10, 203), mm_to_dots(12, 203)
    table_w, table_h = mm_to_dots(20, 203), mm_to_dots(10, 203)
    box_stroke = mm_to_dots(1.0, 203)
    line_stroke = mm_to_dots(0.8, 203)
    table_stroke = mm_to_dots(1.2, 203)

    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 2)

    if language == "slcs":
        assert f"BD{box_x},{box_y},{box_x + box_w},{box_y + box_h},B,{box_stroke}\r\n".encode("ascii") in payload
        assert f"BD{line_x},{line_y},{line_x + line_w - 1},{line_y + line_stroke - 1},O\r\n".encode("ascii") in payload
        assert f"BD{table_x},{table_y},{table_x + table_w},{table_y + table_h},B,{table_stroke}\r\n".encode("ascii") in payload
    elif language == "tspl":
        assert f"BOX {box_x},{box_y},{box_x + box_w},{box_y + box_h},{box_stroke}\n".encode("ascii") in payload
        assert f"BAR {line_x},{line_y},{line_w},{line_stroke}\n".encode("ascii") in payload
        assert f"BOX {table_x},{table_y},{table_x + table_w},{table_y + table_h},{table_stroke}\n".encode("ascii") in payload
    else:
        assert f"^FO{box_x},{box_y}^GB{box_w},{box_h},{box_stroke}^FS\n".encode("ascii") in payload
        assert f"^FO{line_x},{line_y}^GB{line_w},{line_stroke},{line_stroke}^FS\n".encode("ascii") in payload
        assert f"^FO{table_x},{table_y}^GB{table_w},{table_h},{table_stroke}^FS\n".encode("ascii") in payload


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_designer_line_print_command_is_centered_in_its_height_bounds(language: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    line = _element("line", "", 2, 3, 20, 2)
    line["stroke_width"] = 0.8
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [line]
    row = {"barcode": "A12345", "print_qty": "1"}

    x = mm_to_dots(2, 203)
    y = mm_to_dots(3, 203)
    width = mm_to_dots(20, 203)
    height = mm_to_dots(2, 203)
    thickness = mm_to_dots(0.8, 203)
    centered_y = y + (height - thickness) // 2
    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    if language == "slcs":
        assert f"BD{x},{centered_y},{x + width - 1},{centered_y + thickness - 1},O\r\n".encode("ascii") in payload
    elif language == "tspl":
        assert f"BAR {x},{centered_y},{width},{thickness}\n".encode("ascii") in payload
    else:
        assert f"^FO{x},{centered_y}^GB{width},{thickness},{thickness}^FS\n".encode("ascii") in payload


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
@pytest.mark.parametrize("rotation", [90, 270])
def test_designer_vertical_line_print_uses_direct_axis_command(language: str, rotation: int):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    line = {**_element("line", "", 2, 3, 2, 20), "rotation": rotation}
    line["stroke_width"] = 0.8
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [line]
    row = {"barcode": "A12345", "print_qty": "1"}

    x = mm_to_dots(2, 203)
    y = mm_to_dots(3, 203)
    width = mm_to_dots(2, 203)
    height = mm_to_dots(20, 203)
    thickness = mm_to_dots(0.8, 203)
    centered_x = x + (width - thickness) // 2
    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    if language == "slcs":
        assert f"BD{centered_x},{y},{centered_x + thickness - 1},{y + height - 1},O\r\n".encode("ascii") in payload
        assert b"BMP" not in payload
    elif language == "tspl":
        assert f"BAR {centered_x},{y},{thickness},{height}\n".encode("ascii") in payload
        assert b"BITMAP " not in payload
    else:
        assert f"^FO{centered_x},{y}^GB{thickness},{height},{thickness}^FS\n".encode("ascii") in payload
        assert b"^GFA" not in payload


@pytest.mark.parametrize(
    ("language", "expected", "forbidden"),
    [
        ("slcs", b"BMP", b"B2"),
        ("tspl", b"BITMAP ", b"QRCODE "),
        ("zpl", b"^GFA", b"^BQ"),
    ],
)
def test_designer_qr_outputs_same_bitmap_path_for_screen_and_print(language: str, expected: bytes, forbidden: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = _element("barcode", "A1001-250531", 5, 10, 30, 18, barcode_type="qr")
    element["barcode_options"]["cell_size"] = 6
    element["barcode_options"]["qr_ecc"] = "H"
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [element]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A1001-250531",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    assert expected in payload
    assert forbidden not in payload


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_designer_qr_bitmap_output_matches_element_dot_size(language: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = _element("barcode", "001234567890", 16, 8, 18, 18, barcode_type="qr")
    element["barcode_options"]["cell_size"] = 2
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [element]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "001234567890",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }
    expected_size = mm_to_dots(18, 203)

    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    assert _bitmap_dimensions(payload, language) == (expected_size, expected_size)


def test_designer_qr_preview_export_matches_element_pixel_size():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = _element("barcode", "001234567890", 16, 8, 18, 18, barcode_type="qr")
    element["barcode_options"]["cell_size"] = 2
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [element]
    app.preview_row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "001234567890",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    image = app.render_preview_image()
    crop = image.crop((16 * 8, 8 * 8, (16 + 18) * 8, (8 + 18) * 8))
    black_bbox = ImageChops.invert(crop.convert("L")).getbbox()

    assert crop.size == (18 * 8, 18 * 8)
    assert black_bbox is not None
    assert black_bbox[0] > 0
    assert black_bbox[1] > 0
    assert black_bbox[2] < crop.width
    assert black_bbox[3] < crop.height


def _barcode_value_for_type(barcode_type: str) -> str:
    values = {
        "code128": "ABC123",
        "gs1_128": "(01)08801234567890",
        "code39": "ABC-123",
        "codabar": "A12345A",
        "ean13": "590123412345",
        "ean8": "5512345",
        "upca": "04210000526",
        "itf": "123456",
        "pharmacode": "12345",
        "qr": "A1001-250531",
        "microqr": "A123",
        "datamatrix": "A1001-250531",
        "pdf417": "A1001-250531",
        "micropdf417": "A1001-250531",
        "aztec": "A1001-250531",
        "maxicode": "A1001-250531",
    }
    return values[barcode_type]


def _barcode_element_size_mm(barcode_type: str) -> tuple[int, int]:
    if barcode_type in {"pdf417", "micropdf417"}:
        return 36, 16
    if barcode_type in BARCODE_2D_BITMAP_TYPES:
        return 18, 18
    if barcode_type in BARCODE_1D_BITMAP_TYPES:
        return 36, 16
    raise AssertionError(barcode_type)


def write_label_size_config(tmp_path, width_mm: int, height_mm: int) -> None:
    (tmp_path / "config.ini").write_text(
        f"""
[label]
width_mm = {width_mm}
height_mm = {height_mm}
dpi = 203
gap_mm = 3
""".strip(),
        encoding="utf-8",
    )


def _config(
    language: str,
    command_encoding: str,
    media_handling: str = "tear_off",
    media_type: str = "gap",
    print_orientation: str = "normal",
) -> SimpleNamespace:
    return SimpleNamespace(
        printer=SimpleNamespace(
            language=language,
            command_encoding=command_encoding,
            print_method="direct_thermal",
            print_orientation=print_orientation,
            media_handling=media_handling,
            print_speed=4,
            print_density=10,
        ),
        label=SimpleNamespace(dpi=203, gap_mm=3, media_type=media_type),
        barcode=SimpleNamespace(
            qr_model=2,
            qr_ecc="M",
            qr_cell_size=4,
            datamatrix_cell_size=4,
            pdf417_columns=5,
            pdf417_rows=30,
            pdf417_security_level=2,
        ),
    )


class _FakeCanvas:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def winfo_width(self) -> int:
        return self._width

    def winfo_height(self) -> int:
        return self._height


class _FakeCard:
    def __init__(self) -> None:
        self.shown = 0
        self.removed = 0

    def grid(self) -> None:
        self.shown += 1

    def grid_remove(self) -> None:
        self.removed += 1


class _FakeDataTree:
    def __init__(self) -> None:
        self.columns: tuple[str, ...] = ()
        self.headings: dict[str, str] = {}
        self.rows: dict[str, tuple[str, ...]] = {}
        self.row_text: dict[str, str] = {}
        self.selected: tuple[str, ...] = ()

    def configure(self, **kwargs) -> None:
        if "columns" in kwargs:
            self.columns = tuple(kwargs["columns"])

    def heading(self, field: str, *, text: str) -> None:
        self.headings[field] = text

    def column(self, _field: str, **_kwargs) -> None:
        return None

    def get_children(self) -> tuple[str, ...]:
        return tuple(self.rows)

    def delete(self, *_items: str) -> None:
        self.rows.clear()
        self.row_text.clear()

    def insert(self, _parent: str, _position: str, *, iid: str, values: list[str], text: str = "") -> None:
        self.rows[iid] = tuple(values)
        self.row_text[iid] = text

    def exists(self, iid: str) -> bool:
        return iid in self.rows

    def selection_set(self, items) -> None:
        if isinstance(items, str):
            self.selected = (items,)
        else:
            self.selected = tuple(items)


def _bitmap_dimensions(payload: bytes, language: str) -> tuple[int, int]:
    if language == "slcs":
        marker_end = payload.index(b"\r\n", payload.index(b"BMP"))
        bmp_start = marker_end + 2
        bmp_size = int.from_bytes(payload[bmp_start + 2 : bmp_start + 6], "little")
        with Image.open(io.BytesIO(payload[bmp_start : bmp_start + bmp_size])) as image:
            return image.size
    if language == "tspl":
        fields = payload[payload.index(b"BITMAP ") :].split(b",", 5)
        width_bytes = int(fields[2])
        height = int(fields[3])
        return width_bytes * 8, height
    if language == "zpl":
        marker = b"^GFA,"
        start = payload.index(marker) + len(marker)
        total_raw, _total_repeat_raw, width_bytes_raw, _data = payload[start:].split(b",", 3)
        total = int(total_raw)
        width_bytes = int(width_bytes_raw)
        return width_bytes * 8, total // width_bytes
    raise AssertionError(language)


def test_designer_header_generates_a_file_without_sending_to_printer():
    source = inspect.getsource(LabelDesignerApp._build_ui)

    assert 'text="인쇄파일 생성"' in source
    assert "run_output_test(send_to_printer=False)" in source


def test_designer_workbench_uses_a_print_layout_canvas_with_rulers():
    source = inspect.getsource(LabelDesignerApp._build_ui) + inspect.getsource(LabelDesignerApp.redraw)
    module_source = Path(__file__).resolve().parents[1].joinpath("barcode_label_automation", "label_designer_app.py").read_text(encoding="utf-8")

    assert "background=DESIGNER_BG" in source
    assert "highlightbackground=WORKBENCH_BORDER" in source
    assert "radius=LABEL_CORNER_RADIUS" in source
    assert 'text="라벨 디자이너"' in source
    assert 'RULER_BG = "#f7fafc"' in module_source
