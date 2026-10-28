from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace
import copy
import json
import tkinter as tk

import pytest

from barcode_label_automation.config import DEFAULTS
from barcode_label_automation.label_media import write_config_atomic
from barcode_label_automation.label_designer_app import normalize_template
from barcode_label_automation.label_manager_app import LabelManagerApp, LABEL_HEADERS
from barcode_label_automation.job_profile import file_fingerprint
from barcode_label_automation.print_quantity import (
    SerialPrintQuantity, ask_serial_print_quantity, serial_rule_copies, rules_for_serial_job,
)


def serial_rule(name='번호', copies=1):
    return {'name': name, 'kind': 'serial', 'start': 1, 'step': 1, 'digits': 6,
            'copies_per_value': copies, 'reset': 'continue', 'direction': 'up',
            'alphabet': 'numeric', 'prefix': '', 'suffix': ''}


def make_manager(tmp_path):
    parser = ConfigParser(interpolation=None)
    parser.read_dict(DEFAULTS)
    parser.set('printer', 'mode', 'network'); parser.set('printer', 'ip', '127.0.0.1')
    parser.set('label', 'width_mm', '50'); parser.set('label', 'height_mm', '30')
    write_config_atomic(tmp_path / 'config.ini', parser)
    template = normalize_template({'label': {'width_mm': 50, 'height_mm': 30},
        'elements': [{'id': 'text1', 'type': 'text', 'text': '', 'field': '번호',
                      'x': 2, 'y': 2, 'width': 30, 'height': 6, 'font_size': 8}],
        'value_rules': [serial_rule()], 'value_profile_id': '1234567890abcdef1234567890abcdef'})
    path = tmp_path / 'test.cllabel'; path.write_text(json.dumps(template, ensure_ascii=False), 'utf-8')
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path; app.config_path = tmp_path / 'config.ini'
    app.queue_path = tmp_path / 'print_queue.xlsx'; app.db_path = tmp_path / 'barcode_db.xlsx'
    app.print_exe = tmp_path / 'engine.exe'; app.print_exe.write_bytes(b'stub')
    app.label_headers = LABEL_HEADERS; app.label_rows = []; app.selected_label_indexes = set()
    app.output_template = template; app.output_template_path = path
    app.output_template_fingerprint = file_fingerprint(path)
    app.template_only_var = SimpleNamespace(get=lambda: True)
    app.status_var = SimpleNamespace(set=lambda value: None)
    app.data_profile = {}
    return app


def test_serial_quantity_per_target_no_double_multiplication():
    choice = SerialPrintQuantity(3, 2)
    assert (choice.serial_numbers, choice.copies_per_serial, choice.total_per_target) == (3, 2, 6)
    with pytest.raises(ValueError): SerialPrintQuantity(0, 2)
    with pytest.raises(ValueError): SerialPrintQuantity(3, -1)


def test_job_rules_do_not_mutate_saved_rules_and_detect_conflict():
    original = [serial_rule(copies=1)]
    snapshot = copy.deepcopy(original)
    assert serial_rule_copies(original) == 1
    effective = rules_for_serial_job(original, 2)
    assert effective[0]['copies_per_value'] == 2
    assert original == snapshot
    with pytest.raises(ValueError, match='반복 간격'):
        serial_rule_copies(original + [serial_rule('다른 번호', 3)])
    with pytest.raises(ValueError, match='일련화'):
        rules_for_serial_job([], 2)


def test_print_dialog_passes_3_numbers_times_2_copies_for_empty_data(monkeypatch, tmp_path):
    app = make_manager(tmp_path)
    prompts, calls = [], []
    monkeypatch.setattr('barcode_label_automation.label_manager_app.ask_serial_print_quantity',
                        lambda _parent, **kw: prompts.append(kw) or SerialPrintQuantity(3, 2))
    app.run_print_job = lambda action, **kw: calls.append((action, kw))
    app.print_with_quantity()
    assert prompts == [{'target_count': 1, 'default_serial_numbers': 1, 'default_copies': 1}]
    assert calls == [('--print', {'selected_only': False, 'print_quantity': 6, 'copies_per_serial': 2})]
    assert not app.queue_path.exists() and not app.db_path.exists()


def test_no_data_saved_template_generates_valid_cli_args_without_excel(monkeypatch, tmp_path):
    app = make_manager(tmp_path)
    calls, warnings = [], []
    app._invoke_print_engine = lambda args: calls.append(args) or SimpleNamespace(returncode=0, stdout='ok', stderr='')
    monkeypatch.setattr('barcode_label_automation.label_manager_app.messagebox.showwarning', lambda *a, **k: warnings.append(a))
    app.run_print_job('--dry-run', print_quantity=6, copies_per_serial=2)
    assert not warnings
    args = calls[0]
    assert '--no-data' in args and '--excel' not in args
    assert args[args.index('--force-print-qty') + 1] == '6'
    assert args[args.index('--copies-per-serial') + 1] == '2'
    assert not app.queue_path.exists() and not app.db_path.exists()
    assert not (tmp_path / 'out' / 'selected_print_queue.xlsx').exists()


def test_missing_db_field_in_no_data_mode_is_not_silently_replaced(monkeypatch, tmp_path):
    app = make_manager(tmp_path)
    app.output_template['elements'][0]['field'] = '실제DB열'
    issues = app._template_data_issues([{}], 6, 2)
    assert issues and '실제DB열' in issues[0].message


def test_conflicting_saved_intervals_are_rejected_before_showing_quantity(monkeypatch, tmp_path):
    app = make_manager(tmp_path)
    app.output_template['value_rules'].append(serial_rule('다른번호', 2))
    warnings = []
    monkeypatch.setattr('barcode_label_automation.label_manager_app.messagebox.showwarning', lambda *a, **k: warnings.append(a))
    monkeypatch.setattr('barcode_label_automation.label_manager_app.ask_serial_print_quantity',
                        lambda *a, **k: pytest.fail('충돌 설정에서 수량창을 열면 안 됩니다'))
    app.print_with_quantity()
    assert warnings and '반복 간격' in warnings[0][1]


def test_reprint_does_not_replace_unresolved_progress(monkeypatch, tmp_path):
    from barcode_label_automation.print_progress import PrintProgress, DESIGNER_PROGRESS_FILE_NAME
    app = make_manager(tmp_path)
    path = tmp_path / 'out' / DESIGNER_PROGRESS_FILE_NAME
    progress = PrintProgress.open_for_job(path, [b'A'], 'utf-8', {'source': 'previous'})
    progress.mark_sending(1)
    before = path.read_bytes()
    warnings = []
    monkeypatch.setattr('barcode_label_automation.label_manager_app.messagebox.showerror',
                        lambda title, text: warnings.append((title, text)))
    monkeypatch.setattr('barcode_label_automation.label_manager_app.messagebox.askyesno',
                        lambda *a, **kw: pytest.fail('미확인 기록을 먼저 처리해야 합니다'))
    app.reprint_last_value_job()
    assert path.read_bytes() == before
    assert warnings and '덮어쓰지 않고' in warnings[0][1]



def test_no_data_saved_output_emits_three_sequences_twice(monkeypatch, tmp_path):
    from barcode_label_automation.config import load_config
    from barcode_label_automation import saved_output
    app = make_manager(tmp_path)
    captured = []
    original = saved_output.render_command
    def record_render(template, row, config, base_dir, copies):
        captured.append((row['번호'], copies))
        return original(template, row, config, base_dir, copies)
    monkeypatch.setattr(saved_output, 'render_command', record_render)
    args = SimpleNamespace(template=str(app.output_template_path), template_hash=app.output_template_fingerprint,
                           config=str(app.config_path), value_job=None, no_data=True,
                           copies_per_serial=2, limit=None, force_print_qty=6, new_job=False)
    labels, commands, context = saved_output.prepare_saved_output(args, load_config(app.config_path), dry_run=True)
    assert captured == [('000001', 2), ('000002', 2), ('000003', 2)]
    assert [label.print_qty for label in labels] == [2, 2, 2]
    assert len(commands) == 3 and all(commands)
    assert not (tmp_path / 'out' / 'value_jobs' / 'ledger.json').exists()
    assert not app.queue_path.exists()

def test_serial_quantity_dialog_confirms_three_by_two():
    root = tk.Tk(); root.withdraw(); found = []
    def interact():
        dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
        dialog._serial_numbers_var.set('3'); dialog._serial_copies_var.set('2')
        found.append(dialog._serial_summary_var.get())
        dialog._serial_confirm()
    try:
        root.after(200, interact)
        result = ask_serial_print_quantity(root, target_count=1)
        assert result == SerialPrintQuantity(3, 2)
        assert '총 6장' in found[0]
    finally:
        root.destroy()


def test_manager_gui_selects_saved_template_without_product_data(monkeypatch, tmp_path):
    fixture = make_manager(tmp_path)
    monkeypatch.setattr('barcode_label_automation.label_manager_app.load_header_logo', lambda *a, **k: None)
    monkeypatch.setattr('barcode_label_automation.label_manager_app.apply_window_icon', lambda *a, **k: None)
    app = LabelManagerApp(tmp_path)
    try:
        app.update()
        assert app.open_output_template(fixture.output_template_path)
        app.update()
        assert app._template_only_button.winfo_ismapped()
        app._template_only_button.invoke()
        app.update()
        assert app._is_template_only()
        assert app._print_target_rows(False) == [{}]
        assert app.print_scope_var.get() == '상품 데이터 없이 도안만 인쇄'
        assert 'disabled' not in app.print_button.state()
        assert not app.queue_path.exists()
        assert app.db_tree.bind('<Button-3>')
        assert app.labels_tree.bind('<Button-3>')
    finally:
        app.destroy()
