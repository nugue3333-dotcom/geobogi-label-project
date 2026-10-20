from __future__ import annotations

import copy
import json
from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from barcode_label_automation import cli
from barcode_label_automation.config import DEFAULTS, load_config
from barcode_label_automation.data_store import load_db_source, save_label_rows, save_table
from barcode_label_automation.job_profile import data_profile, file_fingerprint, profile_problem
from barcode_label_automation.label_designer_app import LabelDesignerApp, _element, load_template_file, normalize_template
from barcode_label_automation.label_manager_app import LabelManagerApp
from barcode_label_automation.print_progress import DESIGNER_PROGRESS_FILE_NAME, PrintProgress
from barcode_label_automation.saved_output import prepare_saved_output
from barcode_label_automation.template_output import render_command, render_preview, validate_rows
from barcode_label_automation.value_jobs import ValueJobStore


def setup_job(tmp_path, *, rules=None, elements=None, rows=None):
    parser = ConfigParser(interpolation=None)
    parser.read_dict(DEFAULTS)
    parser.set("printer", "brand", "tsc")
    parser.set("printer", "language", "tspl")
    parser.set("printer", "mode", "network")
    parser.set("printer", "ip", "127.0.0.1")
    parser.set("label", "width_mm", "50")
    parser.set("label", "height_mm", "40")
    parser.set("data", "excel_file", str(tmp_path / "print_queue.xlsx"))
    parser.set("data", "output_dir", str(tmp_path / "out"))
    config_path = tmp_path / "config.ini"
    with config_path.open("w", encoding="utf-8") as stream:
        parser.write(stream)
    payload = {"version": 1, "label": {"width_mm": 50, "height_mm": 40},
               "elements": elements or [_element("text", "CUSTOM {{상품명}}", 1, 1, 40, 6)]}
    if rules:
        payload["value_rules"] = rules
        payload["value_profile_id"] = "a" * 32
    path = tmp_path / "custom.cllabel"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    rows = rows or [{"상품명": "테스트 상품", "barcode": "0000123", "print_qty": "2"}]
    save_label_rows(tmp_path / "print_queue.xlsx", rows)
    return config_path, path, load_template_file(path), rows


def arguments(config, path, **kwargs):
    return SimpleNamespace(config=str(config), template=str(path), template_hash=None,
                           value_job=None, limit=None, force_print_qty=None, **kwargs)


def serial_rules():
    return [{"name": "일련번호", "kind": "serial", "start": 1, "step": 1, "digits": 4,
             "copies_per_value": 1, "reset": "continue", "prefix": "", "suffix": ""}]


def test_saved_design_cli_dry_run_uses_the_exact_designer_renderer(tmp_path):
    config, path, payload, _rows = setup_job(tmp_path)
    assert cli.main(["--config", str(config), "--template", str(path), "--dry-run"]) == 0
    raw_rows, _headers = load_db_source(tmp_path / "print_queue.xlsx")
    expected = render_command(payload, raw_rows[0], load_config(config), tmp_path, 2)
    assert (tmp_path / "out" / "label_001.tspl").read_bytes() == expected
    assert not (tmp_path / "out" / "value_jobs").exists()


def test_custom_text_design_does_not_require_a_barcode_column_value(tmp_path):
    config, path, _template, _rows = setup_job(tmp_path, rows=[{"상품명": "문자만", "barcode": "", "print_qty": "1"}])
    assert cli.main(["--config", str(config), "--template", str(path), "--dry-run"]) == 0


def test_all_row_and_object_errors_are_collected_before_send(monkeypatch, tmp_path):
    elements = [_element("barcode", "{{barcode}}", 1, 1, 38, 12, barcode_type="ean13"),
                _element("text", "{{없는열}}", 1, 20, 30, 5)]
    rows = [{"barcode": "ABC", "print_qty": "1"}, {"barcode": "XYZ", "print_qty": "1"}]
    config, path, template, _rows = setup_job(tmp_path, elements=elements, rows=rows)
    issues = validate_rows(template, rows, tmp_path)
    assert len(issues) == 4
    assert {(issue.row, issue.element) for issue in issues} == {(1, 1), (1, 2), (2, 1), (2, 2)}
    sent = []
    monkeypatch.setattr(cli, "_send_to_printer", lambda *args: sent.append(args))
    assert cli.main(["--config", str(config), "--template", str(path), "--print", "--yes"]) == 1
    assert not sent


def test_template_hash_change_and_media_mismatch_block_output(tmp_path):
    config, path, payload, _rows = setup_job(tmp_path)
    old_hash = file_fingerprint(path)
    path.write_text(json.dumps(dict(payload, label={"width_mm": 80, "height_mm": 40})), encoding="utf-8")
    assert cli.main(["--config", str(config), "--template", str(path), "--template-hash", old_hash, "--dry-run"]) == 1
    assert cli.main(["--config", str(config), "--template", str(path), "--dry-run"]) == 1
    assert not list((tmp_path / "out").glob("*.tspl"))


def test_workbook_profile_tracks_sheet_headers_missing_and_changed_file(tmp_path):
    path = tmp_path / "products.xlsx"
    book = Workbook()
    book.active.title = "설명"
    book.active.append(["안내"])
    sheet = book.create_sheet("판매상품")
    sheet.append(["barcode", "상품명"])
    sheet.append(["0000123", "테스트"])
    book.save(path)
    rows, headers = load_db_source(path, sheet_name="판매상품")
    profile = data_profile(path, sheet="판매상품", headers=headers)
    assert rows[0]["barcode"] == "0000123"
    assert profile_problem(profile) is None
    assert normalize_template({"label": {}, "elements": [], "data_source": profile})["data_source"] == profile
    sheet.append(["0000124", "추가"])
    book.save(path)
    assert "변경" in profile_problem(profile)
    path.unlink()
    assert "재연결" in profile_problem(profile)


def test_template_rules_and_profile_are_in_dirty_signature_and_recovery(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = []
    app.selected_id = None
    app._saved_payload_signature = app._current_payload_signature()
    app.template["value_rules"] = serial_rules()
    assert app._has_unsaved_changes()
    assert app._history_snapshot()["value_rules"] == serial_rules()
    assert app.template_payload()["value_rules"] == serial_rules()


def test_designer_handoff_always_passes_saved_current_template(monkeypatch, tmp_path):
    config, path, template, _rows = setup_job(tmp_path)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = app.install_dir = tmp_path
    app.template_dir = tmp_path / "templates"
    app.template_path = path
    app.template = template
    app.elements = template["elements"]
    app._saved_payload_signature = app._current_payload_signature()
    app.status_var = SimpleNamespace(set=lambda _text: None)
    captured = []
    monkeypatch.setattr("barcode_label_automation.label_designer_app.subprocess.Popen", lambda args, **kwargs: captured.append(args))
    app.open_output_workspace()
    assert captured[0][-2:] == ["--template", str(path.resolve())]


def test_unsaved_handoff_cancel_does_not_save_or_launch(monkeypatch, tmp_path):
    config, path, template, _rows = setup_job(tmp_path)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = app.install_dir = tmp_path
    app.template_dir = tmp_path / "templates"
    app.template_path = path
    app.template = template
    app.elements = template["elements"]
    app._saved_payload_signature = app._current_payload_signature()
    app.elements[0]["text"] = "변경"
    app.save_template = lambda: pytest.fail("cancel must not save")
    monkeypatch.setattr("barcode_label_automation.label_designer_app.messagebox.askyesno", lambda *args, **kwargs: False)
    monkeypatch.setattr("barcode_label_automation.label_designer_app.subprocess.Popen", lambda *args, **kwargs: pytest.fail("cancel must not launch"))
    app.open_output_workspace()


def test_manager_opens_the_same_template_in_designer(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.designer_exe = tmp_path / "라벨디자이너.exe"
    app.output_template_path = tmp_path / "actual.cllabel"
    captured = []
    monkeypatch.setattr("barcode_label_automation.label_manager_app.subprocess.Popen", lambda args, **kwargs: captured.append(args))
    app.open_designer()
    assert captured[0][-1] == str(app.output_template_path)
    assert "--base-dir" in captured[0]


def test_serial_dry_run_does_not_consume_numbers_and_real_job_increments_per_label(tmp_path):
    config, path, payload, _rows = setup_job(tmp_path, rules=serial_rules(), elements=[_element("text", "{{일련번호}}", 1, 1, 30, 6)])
    args = arguments(config, path)
    labels, commands, context = prepare_saved_output(args, load_config(config), dry_run=True)
    assert len(labels) == 2
    assert not (tmp_path / "out" / "value_jobs").exists()
    labels, commands, context = prepare_saved_output(args, load_config(config), dry_run=False)
    job = ValueJobStore(tmp_path).load_job(context["snapshot_id"])
    assert [item.row["일련번호"] for item in job.labels] == ["0001", "0002"]
    assert ValueJobStore(tmp_path).peek_start_overrides("a" * 32, serial_rules()) == {"일련번호": 3}


def test_serial_partial_job_resume_uses_same_values_and_snapshot(tmp_path):
    config, path, _payload, _rows = setup_job(tmp_path, rules=serial_rules(), elements=[_element("text", "{{일련번호}}", 1, 1, 30, 6)])
    args = arguments(config, path)
    loaded = load_config(config)
    labels, commands, context = prepare_saved_output(args, loaded, dry_run=False)
    progress = PrintProgress.open_for_job(tmp_path / "out" / DESIGNER_PROGRESS_FILE_NAME, commands, loaded.printer.command_encoding, context)
    progress.mark_sending(1)
    progress.mark_sent(1)
    again = prepare_saved_output(args, loaded, dry_run=False)
    assert again[1] == commands
    assert again[2]["snapshot_id"] == context["snapshot_id"]
    assert ValueJobStore(tmp_path).peek_start_overrides("a" * 32, serial_rules())["일련번호"] == 3


def test_explicit_serial_reprint_preserves_snapshot_and_does_not_allocate(tmp_path):
    config, path, _payload, _rows = setup_job(tmp_path, rules=serial_rules(), elements=[_element("text", "{{일련번호}}", 1, 1, 30, 6)])
    args = arguments(config, path)
    first = prepare_saved_output(args, load_config(config), dry_run=False)
    args.value_job = first[2]["snapshot_id"]
    (tmp_path / "print_queue.xlsx").unlink()
    replay = prepare_saved_output(args, load_config(config), dry_run=False)
    assert replay[1] == first[1]
    assert ValueJobStore(tmp_path).peek_start_overrides("a" * 32, serial_rules())["일련번호"] == 3
    template = json.loads(path.read_text(encoding="utf-8"))
    template["elements"][0]["text"] = "CHANGED {{일련번호}}"
    path.write_text(json.dumps(template), encoding="utf-8")
    with pytest.raises(ValueError, match="변경"):
        prepare_saved_output(args, load_config(config), dry_run=False)


def test_serial_sequence_identity_survives_label_file_relocation(tmp_path):
    config, path, _payload, _rows = setup_job(tmp_path, rules=serial_rules(), elements=[_element("text", "{{일련번호}}", 1, 1, 30, 6)])
    first = prepare_saved_output(arguments(config, path), load_config(config), dry_run=False)
    new_path = tmp_path / "new-name.cllabel"
    new_path.write_bytes(path.read_bytes())
    store = ValueJobStore(tmp_path)
    assert store.peek_start_overrides(load_template_file(new_path)["value_profile_id"], serial_rules())["일련번호"] == 3


def test_preview_renderer_uses_custom_objects_and_current_data(tmp_path):
    config, path, payload, _rows = setup_job(tmp_path)
    image = render_preview(payload, {"상품명": "테스트"}, tmp_path)
    assert image.size == (400, 320)
    assert image.convert("L").getextrema()[0] < 255
