from __future__ import annotations

import contextlib
import io
import re
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest
from openpyxl import Workbook

from barcode_label_automation import cli as print_cli
from barcode_label_automation.data_store import (
    DB_HEADERS,
    DEFAULT_DB_HEADERS,
    LABEL_HEADERS,
    load_label_rows,
    save_db_rows,
    save_label_rows,
)
from barcode_label_automation.excel_reader import read_labels
from barcode_label_automation.label_manager_app import (
    LabelManagerApp,
    _build_preflight_check_args,
    _build_print_args,
    _build_support_package_args,
    _ask_unknown_resolution,
    _default_print_quantity,
    _delete_label_rows,
    _duplicate_selection_result,
    _dynamic_label_rows_from_db_rows,
    _ensure_label_row_index,
    _initial_duplicate_selection_positions,
    _label_rows_from_db_rows,
    _load_active_db_state,
    _load_dynamic_db_rows,
    _printable_rows_from_label_rows,
    _print_readiness_errors,
    _read_preflight_summary,
    _rows_with_print_quantity,
    _row_field_value,
    _save_dynamic_db_rows,
    _selected_print_queue_path,
    _support_package_paths,
    main as manager_main,
)
from barcode_label_automation.print_progress import (
    PROGRESS_FILE_NAME,
    TRANSPORT_UNCERTAIN_CODE,
    NEW_JOB_REQUIRED_CODE,
    PrintProgress,
)


def _write_ready_config(path: Path, *, gap_mm: str = "3", media_type: str = "gap") -> None:
    path.write_text(
        f"""
[printer]
brand = tsc
mode = network
print_method = direct_thermal
media_handling = tear_off
ip = 127.0.0.1
port = 9100
windows_printer_name = auto

[label]
width_mm = 50
height_mm = 40
dpi = 203
gap_mm = {gap_mm}
media_type = {media_type}

[data]
excel_file = print_queue.xlsx
output_dir = out
""".strip(),
        encoding="utf-8",
    )


def test_label_rows_are_loaded_from_db_rows():
    rows = [
        {
            "barcode": "KOR-TEST-001",
            "item_code": "K1001",
            "item_name": "한글품목테스트",
            "lot_no": "LOT-HANGUL",
            "qty": "10",
            "print_qty": "",
        }
    ]

    assert _label_rows_from_db_rows(rows) == [
        {
            "item_code": "K1001",
            "item_name": "한글품목테스트",
            "barcode": "KOR-TEST-001",
            "lot_no": "LOT-HANGUL",
            "qty": "10",
            "print_qty": "1",
        }
    ]


def test_empty_db_rows_are_not_added_to_output_list():
    assert _label_rows_from_db_rows([{"barcode": "", "item_code": "", "item_name": ""}]) == []


def test_dynamic_db_headers_are_preserved_for_output_rows():
    headers = ("바코드", "가격", "날짜")
    rows = [{"바코드": "8801234", "가격": "12000", "날짜": "2026-06-24"}]

    assert _dynamic_label_rows_from_db_rows(rows, headers) == rows


def test_dynamic_db_rows_convert_to_printable_fixed_queue_rows():
    rows = [{"바코드": "8801234", "가격": "12000", "날짜": "2026-06-24"}]

    printable = _printable_rows_from_label_rows(rows, ("바코드", "가격", "날짜"))

    assert printable == [
        {
            "item_code": "",
            "item_name": "",
            "barcode": "8801234",
            "lot_no": "",
            "qty": "1",
            "print_qty": "1",
            "바코드": "8801234",
            "가격": "12000",
            "날짜": "2026-06-24",
        }
    ]


def test_missing_default_db_uses_sales_headers_and_printable_queue_defaults(tmp_path):
    headers, rows = _load_dynamic_db_rows(tmp_path / "barcode_db.xlsx")

    assert headers == DEFAULT_DB_HEADERS
    assert len(rows) == 100
    assert all(not {"lot_no", "qty", "print_qty"}.intersection(row) for row in rows)

    printable = _printable_rows_from_label_rows(rows[:1], headers)
    assert printable[0]["qty"] == "1"
    assert printable[0]["print_qty"] == "1"


def test_printable_conversion_does_not_emit_empty_rows():
    assert _printable_rows_from_label_rows([{"바코드": "", "가격": "", "날짜": ""}], ("바코드", "가격", "날짜")) == []


def test_item_code_alias_does_not_mask_barcode_column():
    row = {"바코드": "8801234", "상품코드": "ITEM-9"}

    printable = _printable_rows_from_label_rows([row], ("바코드", "상품코드"))

    assert printable[0]["barcode"] == "8801234"
    assert printable[0]["item_code"] == "ITEM-9"
    assert printable[0]["qty"] == "1"


def test_product_name_alias_maps_to_item_name_without_qty_column():
    row = {"바코드": "123456789", "가격": "10000", "품명": "가나"}

    printable = _printable_rows_from_label_rows([row], ("바코드", "가격", "품명"))

    assert printable[0]["barcode"] == "123456789"
    assert printable[0]["item_code"] == ""
    assert printable[0]["item_name"] == "가나"
    assert printable[0]["qty"] == "1"
    assert printable[0]["print_qty"] == "1"


def test_dynamic_db_excel_roundtrip_preserves_custom_headers(tmp_path):
    db_path = tmp_path / "custom_db.xlsx"
    headers = ("바코드", "가격", "날짜")
    rows = [{"바코드": "8801234", "가격": "12000", "날짜": "2026-06-24"}]

    _save_dynamic_db_rows(db_path, headers, rows)

    loaded_headers, loaded_rows = _load_dynamic_db_rows(db_path)
    assert loaded_headers == headers
    assert loaded_rows == rows
    assert _row_field_value(loaded_rows[0], "barcode") == "8801234"


def test_manager_db_preserves_excel_zero_padded_numeric_barcode_in_print_rows(tmp_path):
    db_path = tmp_path / "numeric_barcode.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BarcodeDB"
    sheet.append(["바코드", "상품코드", "품명", "판매가"])
    sheet.append([123, 7, "테스트 상품", 1200])
    sheet["A2"].number_format = "00000000"
    sheet["B2"].number_format = "0000"
    sheet["D2"].number_format = "#,##0"
    sheet.append(["00000999", "0008", "문자 바코드", 900])
    workbook.save(db_path)

    headers, rows = _load_dynamic_db_rows(db_path)
    assert headers == ("바코드", "상품코드", "품명", "판매가")
    assert rows[0] == {"바코드": "00000123", "상품코드": "0007", "품명": "테스트 상품", "판매가": "1200"}
    assert rows[1]["바코드"] == "00000999"

    _db_headers, _db_rows, label_headers, label_rows = _load_active_db_state(db_path)
    printable = _printable_rows_from_label_rows(label_rows, label_headers)
    assert [row["barcode"] for row in printable] == ["00000123", "00000999"]


def test_manager_db_rejects_numeric_barcode_format_that_cannot_be_reproduced(tmp_path):
    db_path = tmp_path / "formatted_barcode.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BarcodeDB"
    sheet.append(["바코드", "품명"])
    sheet.append([12345, "테스트 상품"])
    sheet["A2"].number_format = "000-00"
    workbook.save(db_path)

    with pytest.raises(ValueError, match="2행.*바코드.*텍스트"):
        _load_dynamic_db_rows(db_path)


def test_switching_active_db_replaces_all_rows_headers_and_print_values(tmp_path):
    first_path = tmp_path / "first.xlsx"
    second_path = tmp_path / "second.xlsx"
    _save_dynamic_db_rows(
        first_path,
        ("바코드", "상품명", "판매가"),
        [{"바코드": "111", "상품명": "이전 상품", "판매가": "1,000원"}],
    )
    _save_dynamic_db_rows(
        second_path,
        ("제품바코드", "품명", "규격", "원산지"),
        [{"제품바코드": "222", "품명": "새 상품", "규격": "대", "원산지": "국내산"}],
    )

    _, first_rows, _, _ = _load_active_db_state(first_path)
    db_headers, db_rows, label_headers, label_rows = _load_active_db_state(second_path)
    printable = _printable_rows_from_label_rows(label_rows, label_headers)

    assert first_rows[0]["상품명"] == "이전 상품"
    assert db_headers == ("제품바코드", "품명", "규격", "원산지")
    assert db_rows == label_rows == [{"제품바코드": "222", "품명": "새 상품", "규격": "대", "원산지": "국내산"}]
    assert all("이전 상품" not in row.values() for row in printable)
    assert printable[0]["barcode"] == "222"
    assert printable[0]["item_name"] == "새 상품"
    assert printable[0]["규격"] == "대"
    assert printable[0]["원산지"] == "국내산"


def test_scan_target_uses_selected_output_row_without_appending():
    rows = [{"item_code": "OLD"}]

    index, appended = _ensure_label_row_index(rows, 0)

    assert index == 0
    assert appended is False
    assert rows == [{"item_code": "OLD"}]


def test_scan_target_appends_when_no_output_row_is_selected():
    rows = [{"item_code": "OLD"}]

    index, appended = _ensure_label_row_index(rows, None)

    assert index == 1
    assert appended is True
    assert rows[index] == {
        "item_code": "",
        "item_name": "",
        "barcode": "",
        "lot_no": "",
        "qty": "",
        "print_qty": "",
    }


def test_delete_label_rows_removes_checked_rows_and_clears_selection():
    rows = [
        {"barcode": "A"},
        {"barcode": "B"},
        {"barcode": "C"},
        {"barcode": "D"},
    ]
    selected_indexes = {1, 3}

    deleted_count = _delete_label_rows(rows, selected_indexes, focused_index=0)

    assert deleted_count == 2
    assert [row["barcode"] for row in rows] == ["A", "C"]
    assert selected_indexes == set()


def test_delete_label_rows_falls_back_to_focused_row_when_no_checked_rows():
    rows = [
        {"barcode": "A"},
        {"barcode": "B"},
        {"barcode": "C"},
    ]
    selected_indexes: set[int] = set()

    deleted_count = _delete_label_rows(rows, selected_indexes, focused_index=1)

    assert deleted_count == 1
    assert [row["barcode"] for row in rows] == ["A", "C"]


def test_manager_smoke_test_does_not_rewrite_print_queue(tmp_path):
    db_path = tmp_path / "barcode_db.xlsx"
    queue_path = tmp_path / "print_queue.xlsx"
    save_db_rows(
        db_path,
        [
            {
                "barcode": "DB-001",
                "item_code": "DBITEM",
                "item_name": "From DB",
                "lot_no": "LOT-DB",
                "qty": "10",
                "print_qty": "1",
            }
        ],
    )
    save_label_rows(
        queue_path,
        [
            {
                "item_code": "QUEUEITEM",
                "item_name": "Keep Queue",
                "barcode": "QUEUE-001",
                "lot_no": "LOT-Q",
                "qty": "3",
                "print_qty": "2",
            }
        ],
    )
    before = queue_path.read_bytes()

    assert manager_main(["--base-dir", str(tmp_path), "--smoke-test"]) == 0

    assert queue_path.read_bytes() == before
    assert load_label_rows(queue_path)[0]["barcode"] == "QUEUE-001"


def test_manager_smoke_test_accepts_dynamic_db_headers(tmp_path):
    db_path = tmp_path / "barcode_db.xlsx"
    queue_path = tmp_path / "print_queue.xlsx"
    _save_dynamic_db_rows(
        db_path,
        ("바코드", "가격", "날짜"),
        [{"바코드": "8801234", "가격": "12000", "날짜": "2026-06-24"}],
    )
    save_label_rows(
        queue_path,
        [
            {
                "item_code": "12000",
                "item_name": "2026-06-24",
                "barcode": "8801234",
                "lot_no": "",
                "qty": "",
                "print_qty": "1",
            }
        ],
    )

    assert manager_main(["--base-dir", str(tmp_path), "--smoke-test"]) == 0


def test_manager_load_files_does_not_persist_db_rows_until_save_or_print(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.db_path = tmp_path / "barcode_db.xlsx"
    app.queue_path = tmp_path / "print_queue.xlsx"
    app.db_rows = []
    app.label_rows = []
    app.db_headers = tuple(DB_HEADERS)
    app.label_headers = tuple(LABEL_HEADERS)
    app.selected_label_indexes = set()
    app.status_var = type("Status", (), {"set": lambda self, value: None})()
    app.refresh_tables = lambda: None
    app._sync_labels_from_db = lambda preserve_selection=False: setattr(
        app,
        "label_rows",
        [{"barcode": "DB-001", "item_name": "DB item", "print_qty": "1"}],
    )
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app._load_active_db_state",
        lambda _path: (
            tuple(DB_HEADERS),
            [{"barcode": "DB-001"}],
            tuple(LABEL_HEADERS),
            [{"barcode": "DB-001", "item_name": "DB item", "print_qty": "1"}],
        ),
    )
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.save_label_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("startup must not save the queue")),
    )

    app.load_files()

    assert app.label_rows[0]["barcode"] == "DB-001"


def test_manager_ui_smoke_instantiates_app(monkeypatch, tmp_path):
    created: list[Path] = []

    class FakeApp:
        def __init__(self, base_dir: Path) -> None:
            created.append(base_dir)

        def update_idletasks(self) -> None:
            pass

        def destroy(self) -> None:
            pass

    monkeypatch.setattr("barcode_label_automation.label_manager_app.LabelManagerApp", FakeApp)

    assert manager_main(["--base-dir", str(tmp_path), "--ui-smoke-test"]) == 0
    assert created == [tmp_path.resolve()]


def test_selected_print_uses_temporary_excel_without_replacing_full_queue(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.queue_path = tmp_path / "print_queue.xlsx"
    app.db_path = tmp_path / "barcode_db.xlsx"
    app.config_path = tmp_path / "config.ini"
    _write_ready_config(app.config_path)
    app.print_exe = tmp_path / "print_labels.exe"
    app.print_exe.write_text("stub", encoding="utf-8")
    app.db_rows = []
    app.label_rows = [
        {
            "item_code": "KEEP-001",
            "item_name": "Keep 1",
            "barcode": "KEEP-001",
            "lot_no": "LOT-1",
            "qty": "1",
            "print_qty": "1",
        },
        {
            "item_code": "SEL-002",
            "item_name": "Selected 2",
            "barcode": "SEL-002",
            "lot_no": "LOT-2",
            "qty": "2",
            "print_qty": "1",
        },
    ]
    app.selected_label_indexes = {1}
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.subprocess.run",
        lambda args, **_kwargs: calls.append(args) or SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )

    app.run_print_job("--dry-run", selected_only=True)

    selected_path = _selected_print_queue_path(tmp_path)
    assert [row["barcode"] for row in load_label_rows(app.queue_path)] == ["KEEP-001", "SEL-002"]
    assert [row["barcode"] for row in load_label_rows(selected_path)] == ["SEL-002"]
    assert calls
    assert "--excel" in calls[0]
    assert str(selected_path) in calls[0]


def test_selected_print_with_dynamic_headers_fills_required_qty(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.queue_path = tmp_path / "print_queue.xlsx"
    app.db_path = tmp_path / "barcode_db.xlsx"
    app.config_path = tmp_path / "config.ini"
    _write_ready_config(app.config_path)
    app.print_exe = tmp_path / "print_labels.exe"
    app.print_exe.write_text("stub", encoding="utf-8")
    app.db_rows = []
    app.db_headers = ("바코드", "가격", "품명")
    app.label_headers = ("바코드", "가격", "품명")
    app.label_rows = [
        {"바코드": "123456789", "가격": "10000", "품명": "가나"},
        {"바코드": "123456790", "가격": "10001", "품명": "가나"},
    ]
    app.selected_label_indexes = {0, 1}
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.subprocess.run",
        lambda args, **_kwargs: calls.append(args) or SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )

    app.run_print_job("--dry-run", selected_only=True)

    rows = load_label_rows(_selected_print_queue_path(tmp_path))
    assert [row["barcode"] for row in rows] == ["123456789", "123456790"]
    assert [row["qty"] for row in rows] == ["1", "1"]
    assert [row["item_name"] for row in rows] == ["가나", "가나"]
    engine_rows = read_labels(_selected_print_queue_path(tmp_path))
    assert engine_rows[0].source_fields == (("가격", "10,000원"), ("품명", "가나"))
    assert calls


def test_db_selected_print_renders_config_size_peeler_and_alignment(monkeypatch, tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[printer]
brand = tsc
mode = network
print_method = direct_thermal
media_handling = peeler
speed = 5
density = 7
language = auto
command_encoding = auto
ip = 127.0.0.1
port = 9100
windows_printer_name = TSC TDP-247

[label]
width_mm = 50
height_mm = 40
dpi = 203
gap_mm = 3

[barcode]
type = code128
auto_layout = yes
x = 110
y = 86
rotation = 0

[barcode.1d]
height = 80
narrow = 2
wide = 2
human_readable = yes

[data]
excel_file = print_queue.xlsx
output_dir = out
""".strip(),
        encoding="utf-8",
    )
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.queue_path = tmp_path / "print_queue.xlsx"
    app.db_path = tmp_path / "barcode_db.xlsx"
    app.config_path = config_path
    app.print_exe = tmp_path / "print_labels.exe"
    app.print_exe.write_text("stub", encoding="utf-8")
    app.db_rows = [{"바코드": "123456789012", "가격": "10000", "품명": "가나"}]
    app.db_headers = ("바코드", "가격", "품명")
    app.label_headers = ("바코드", "가격", "품명")
    app.label_rows = list(app.db_rows)
    app.selected_label_indexes = {0}
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))

    def run_cli(args, **_kwargs):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            returncode = print_cli.main(args[1:])
        return SimpleNamespace(returncode=returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue())

    monkeypatch.setattr("barcode_label_automation.label_manager_app.subprocess.run", run_cli)

    app.run_print_job("--dry-run", selected_only=True)

    command = (tmp_path / "out" / "label_001.tspl").read_bytes()
    assert command.startswith(b"SIZE 50 mm,40 mm\n")
    assert b"SET CUTTER OFF\nSET PEEL ON\n" in command
    assert b"SET TEAR OFF\n" not in command
    assert b"BITMAP 20," in command
    match = re.search(rb'BARCODE (\d+),(\d+),"128",(\d+),1,0,(\d+),(\d+),"123456789012"', command)
    assert match is not None
    x = int(match.group(1))
    y = int(match.group(2))
    height = int(match.group(3))
    narrow = int(match.group(4))
    barcode_width = (((len("123456789012") + 3) * 11) + 13) * narrow
    label_width = round(50 / 25.4 * 203)
    label_height = round(40 / 25.4 * 203)
    assert height >= round(label_height * 0.35)
    assert abs((x + (barcode_width / 2)) - (label_width / 2)) <= 2
    assert y + height <= label_height


def test_scan_lookup_selects_matching_print_data_row():
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.label_headers = ("바코드", "가격", "품명")
    app.label_rows = [
        {"바코드": "123456789", "가격": "10000", "품명": "가나"},
        {"바코드": "123456790", "가격": "10001", "품명": "다라"},
    ]
    app.selected_label_indexes = {0}
    app.labels_tree = object()
    status = SimpleNamespace(value="")
    status.set = lambda value: setattr(status, "value", value)
    app.status_var = status
    app.refresh_tables = lambda: setattr(app, "refreshed", True)
    app.tabs = SimpleNamespace(
        tabs=lambda: ["labels", "db"],
        select=lambda tab: setattr(app, "selected_tab", tab),
    )
    app._select_index = lambda tree, index: setattr(app, "selected_index", index)

    assert app.select_label_row_by_barcode("123456790")

    assert app.selected_label_indexes == {0, 1}
    assert app.refreshed is True
    assert app.selected_tab == "labels"
    assert app.selected_index == 1
    assert app.status_var.value == "인쇄 데이터 선택: 123456790 / 다라"


def test_scan_lookup_searches_all_db_values_and_checks_print_data_row():
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.db_headers = ("바코드", "가격", "품명")
    app.label_headers = ("바코드", "가격", "품명")
    app.db_rows = [
        {"바코드": "123456790", "가격": "10001", "품명": "다라"},
    ]
    app.label_rows = [
        {"바코드": "123456789", "가격": "10000", "품명": "가나"},
        {"바코드": "123456790", "가격": "10001", "품명": "다라"},
    ]
    app.selected_label_indexes = {0}
    app.db_tree = "db-tree"
    app.labels_tree = "labels-tree"
    scan = SimpleNamespace(value="다라")
    scan.get = lambda: scan.value
    scan.set = lambda value: setattr(scan, "value", value)
    app.scan_var = scan
    status = SimpleNamespace(value="")
    status.set = lambda value: setattr(status, "value", value)
    app.status_var = status
    app.refresh_tables = lambda: setattr(app, "refreshed", True)
    app.tabs = SimpleNamespace(
        tabs=lambda: ["labels", "db"],
        select=lambda tab: setattr(app, "selected_tab", tab),
    )
    selected_indexes: list[tuple[str, int]] = []
    app._select_index = lambda tree, index: selected_indexes.append((tree, index))

    app.scan_barcode()

    assert app.selected_label_indexes == {0, 1}
    assert selected_indexes == [("db-tree", 0), ("labels-tree", 1)]
    assert app.refreshed is True
    assert app.selected_tab == "labels"
    assert app.status_var.value == "인쇄 데이터 선택: 123456790 / 다라"
    assert app.scan_var.value == ""


def test_duplicate_db_picker_starts_with_no_checked_rows():
    assert _initial_duplicate_selection_positions(3) == set()


def test_duplicate_db_picker_applies_only_confirmed_checked_rows():
    matches = [
        (0, {"바코드": "123456790", "품명": "다라"}),
        (1, {"바코드": "223456790", "품명": "다라"}),
        (2, {"바코드": "323456790", "품명": "다라"}),
    ]

    assert _duplicate_selection_result(matches, {2, 0}) == [matches[0], matches[2]]
    assert _duplicate_selection_result(matches, set()) == []


def test_duplicate_db_picker_uses_confirm_dialog_copy():
    import inspect

    source = inspect.getsource(LabelManagerApp._choose_db_matches)

    assert "체크 후 확인을 누르면 인쇄 데이터에 적용됩니다." in source
    assert 'text="확인"' in source
    assert 'text="선택 적용"' not in source
    assert "확인할 항목을 먼저 체크하세요." in source
    assert "_duplicate_selection_result" in source


def test_scan_lookup_with_duplicate_db_matches_uses_picker_selection():
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.db_headers = ("바코드", "가격", "품명")
    app.label_headers = ("바코드", "가격", "품명")
    app.db_rows = [
        {"바코드": "123456790", "가격": "10001", "품명": "다라"},
        {"바코드": "223456790", "가격": "10002", "품명": "다라"},
    ]
    app.label_rows = [
        {"바코드": "123456790", "가격": "10001", "품명": "다라"},
        {"바코드": "223456790", "가격": "10002", "품명": "다라"},
    ]
    app.selected_label_indexes = set()
    app.db_tree = "db-tree"
    app.labels_tree = "labels-tree"
    scan = SimpleNamespace(value="다라")
    scan.get = lambda: scan.value
    scan.set = lambda value: setattr(scan, "value", value)
    app.scan_var = scan
    status = SimpleNamespace(value="")
    status.set = lambda value: setattr(status, "value", value)
    app.status_var = status
    app.refresh_tables = lambda: setattr(app, "refreshed", True)
    app.tabs = SimpleNamespace(
        tabs=lambda: ["labels", "db"],
        select=lambda tab: setattr(app, "selected_tab", tab),
    )
    selected_indexes: list[tuple[str, int]] = []
    app._select_index = lambda tree, index: selected_indexes.append((tree, index))
    captured: dict[str, object] = {}

    def choose_matches(query, matches):
        captured["query"] = query
        captured["match_count"] = len(matches)
        return [matches[1]]

    app._choose_db_matches = choose_matches

    app.scan_barcode()

    assert captured == {"query": "다라", "match_count": 2}
    assert app.selected_label_indexes == {1}
    assert selected_indexes == [("db-tree", 1), ("labels-tree", 1)]
    assert app.refreshed is True
    assert app.selected_tab == "labels"
    assert app.status_var.value == "인쇄 데이터 적용 완료: 1건 · 선택 항목 인쇄를 누르세요."
    assert app.scan_var.value == ""


def test_duplicate_db_selection_can_check_all_matching_print_rows():
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.label_headers = ("바코드", "가격", "품명")
    app.label_rows = [
        {"바코드": "123456790", "가격": "10001", "품명": "다라"},
        {"바코드": "223456790", "가격": "10002", "품명": "다라"},
    ]
    app.selected_label_indexes = set()
    app.labels_tree = "labels-tree"
    app.refresh_tables = lambda: setattr(app, "refreshed", True)
    app.tabs = SimpleNamespace(
        tabs=lambda: ["labels", "db"],
        select=lambda tab: setattr(app, "selected_tab", tab),
    )
    app._select_index = lambda tree, index: setattr(app, "selected_index", (tree, index))
    status = SimpleNamespace(value="")
    status.set = lambda value: setattr(status, "value", value)
    app.status_var = status
    matches = [
        (0, {"바코드": "123456790", "가격": "10001", "품명": "다라"}),
        (1, {"바코드": "223456790", "가격": "10002", "품명": "다라"}),
    ]

    assert app._select_label_rows_for_db_matches("다라", matches) == 2

    assert app.selected_label_indexes == {0, 1}
    assert app.refreshed is True
    assert app.selected_tab == "labels"
    assert app.selected_index == ("labels-tree", 0)
    assert app.status_var.value == "인쇄 데이터 적용 완료: 2건 · 선택 항목 인쇄를 누르세요."


def test_duplicate_db_confirmation_replaces_existing_print_selection():
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.label_headers = ("바코드", "가격", "품명")
    app.label_rows = [
        {"바코드": "111", "가격": "1000", "품명": "기존 선택"},
        {"바코드": "222", "가격": "2000", "품명": "확인 선택"},
    ]
    app.selected_label_indexes = {0}
    app.labels_tree = "labels-tree"
    app.refresh_tables = lambda: None
    app.tabs = SimpleNamespace(tabs=lambda: ["labels", "db"], select=lambda _tab: None)
    app._select_index = lambda _tree, _index: None
    app.status_var = SimpleNamespace(set=lambda _value: None)

    count = app._select_label_rows_for_db_matches(
        "확인 선택",
        [(1, {"바코드": "222", "가격": "2000", "품명": "확인 선택"})],
    )

    assert count == 1
    assert app.selected_label_indexes == {1}
    assert [row["바코드"] for row in app._selected_print_rows()] == ["222"]


def test_confirming_one_duplicate_barcode_row_does_not_select_every_same_barcode():
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.label_headers = ("바코드", "가격", "품명")
    app.label_rows = [
        {"바코드": "999", "가격": "1000", "품명": "첫 번째"},
        {"바코드": "999", "가격": "2000", "품명": "두 번째"},
    ]

    indexes = app._label_indexes_for_db_match(
        99,
        {"바코드": "999", "가격": "2000", "품명": "두 번째"},
        "두 번째",
    )

    assert indexes == [0]


def test_db_lookup_searches_all_db_values():
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.db_headers = ("바코드", "가격", "품명")
    app.db_rows = [
        {"바코드": "123456790", "가격": "10001", "품명": "다라"},
    ]
    app.db_tree = "db-tree"
    status = SimpleNamespace(value="")
    status.set = lambda value: setattr(status, "value", value)
    app.status_var = status
    app.tabs = SimpleNamespace(
        tabs=lambda: ["labels", "db"],
        select=lambda tab: setattr(app, "selected_tab", tab),
    )
    app._select_index = lambda tree, index: setattr(app, "selected_index", (tree, index))

    assert app.select_db_row_by_barcode("10001")

    assert app.selected_tab == "db"
    assert app.selected_index == ("db-tree", 0)
    assert app.status_var.value == "DB 조회 완료: 10001 -> 123456790 / 다라"


def test_scan_lookup_warns_when_print_data_has_no_matching_barcode(monkeypatch):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.label_rows = [{"바코드": "123456789", "품명": "가나"}]
    app.selected_label_indexes = set()
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showwarning",
        lambda title, message: warnings.append((title, message)),
    )

    assert not app.select_label_row_by_barcode("000000000")
    assert app.selected_label_indexes == set()
    assert warnings == [("인쇄 데이터", "인쇄 데이터에서 해당 바코드를 찾을 수 없습니다.")]


def test_print_quantity_override_uses_temporary_excel_without_replacing_full_queue(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.queue_path = tmp_path / "print_queue.xlsx"
    app.db_path = tmp_path / "barcode_db.xlsx"
    app.config_path = tmp_path / "config.ini"
    _write_ready_config(app.config_path)
    app.print_exe = tmp_path / "print_labels.exe"
    app.print_exe.write_text("stub", encoding="utf-8")
    app.db_rows = []
    app.label_rows = [
        {
            "item_code": "ALL-001",
            "item_name": "All 1",
            "barcode": "ALL-001",
            "lot_no": "LOT-1",
            "qty": "1",
            "print_qty": "1",
        }
    ]
    app.selected_label_indexes = set()
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.subprocess.run",
        lambda args, **_kwargs: calls.append(args) or SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    popups: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showinfo",
        lambda title, message: popups.append((title, message)),
    )
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.askyesno",
        lambda *_args, **_kwargs: pytest.fail("인쇄 확인 창이 열리면 안 됩니다."),
    )

    app.run_print_job("--print", print_quantity=7)

    selected_path = _selected_print_queue_path(tmp_path)
    assert load_label_rows(app.queue_path)[0]["print_qty"] == "1"
    assert load_label_rows(selected_path)[0]["print_qty"] == "7"
    assert calls
    assert "--yes" in calls[0]
    assert popups == [
        (
            "프린터 전송 완료 · 출력 확인 필요",
            "1건의 인쇄 명령을 프린터로 전송했습니다.\n실제 라벨 출력 여부는 프린터에서 확인하세요.",
        )
    ]


def test_print_with_quantity_prompts_for_selected_rows_and_passes_override(monkeypatch):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.label_rows = [
        {"barcode": "A", "print_qty": "1"},
        {"barcode": "B", "print_qty": "3"},
    ]
    app.selected_label_indexes = {1}
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    monkeypatch.setattr(app, "_selected_print_rows", lambda: [app.label_rows[1]])
    prompts: list[tuple[int, bool]] = []
    monkeypatch.setattr(
        app,
        "ask_print_quantity",
        lambda default_quantity, *, selected_only: prompts.append((default_quantity, selected_only)) or 7,
    )
    print_calls: list[tuple[str, bool, int | None]] = []
    monkeypatch.setattr(
        app,
        "run_print_job",
        lambda action, selected_only=False, print_quantity=None: print_calls.append(
            (action, selected_only, print_quantity)
        ),
    )

    app.print_with_quantity()

    assert prompts == [(3, True)]
    assert print_calls == [("--print", True, 7)]


def test_print_with_quantity_cancel_does_not_start_print(monkeypatch):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.label_rows = [{"barcode": "A", "print_qty": "2"}]
    app.selected_label_indexes = {0}
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    monkeypatch.setattr(app, "ask_print_quantity", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        app,
        "run_print_job",
        lambda *_args, **_kwargs: pytest.fail("취소 후 인쇄가 시작되면 안 됩니다."),
    )

    app.print_with_quantity()

    assert app.status_var.value == "인쇄 매수 선택을 취소했습니다."


def test_print_with_quantity_requires_explicit_output_selection(monkeypatch):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.label_rows = [{"barcode": "A", "print_qty": "2"}]
    app.selected_label_indexes = set()
    warnings: list[str] = []
    monkeypatch.setattr("barcode_label_automation.label_manager_app.messagebox.showwarning", lambda _title, message: warnings.append(message))
    app.ask_print_quantity = lambda *_args, **_kwargs: pytest.fail("no quantity popup before selection")
    app.run_print_job = lambda *_args, **_kwargs: pytest.fail("no print without selection")

    app.print_with_quantity()

    assert "먼저 선택하세요" in warnings[0]


def test_print_job_sends_without_confirmation(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.queue_path = tmp_path / "print_queue.xlsx"
    app.db_path = tmp_path / "barcode_db.xlsx"
    app.config_path = tmp_path / "config.ini"
    _write_ready_config(app.config_path)
    app.print_exe = tmp_path / "print_labels.exe"
    app.print_exe.write_text("stub", encoding="utf-8")
    app.db_rows = []
    app.label_rows = [
        {
            "item_code": "A100",
            "item_name": "Ready",
            "barcode": "A100",
            "lot_no": "",
            "qty": "1",
            "print_qty": "1",
        }
    ]
    app.selected_label_indexes = set()
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.askyesno",
        lambda *_args, **_kwargs: pytest.fail("인쇄 확인 창이 열리면 안 됩니다."),
    )
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.subprocess.run",
        lambda args, **_kwargs: calls.append(args) or SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    popups: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showinfo",
        lambda title, message: popups.append((title, message)),
    )

    app.run_print_job("--print")

    assert calls
    assert "--yes" in calls[0]
    assert popups and popups[-1][0] == "프린터 전송 완료 · 출력 확인 필요"


def test_manager_unknown_state_reports_error_and_blocks_retry_without_dialog(monkeypatch, tmp_path):
    config_path = tmp_path / "config.ini"
    _write_ready_config(config_path)
    progress_path = tmp_path / "out" / PROGRESS_FILE_NAME
    progress = PrintProgress.open_for_job(progress_path, [b"A", b"B", b"C"], "utf-8", {"source": "test"})
    progress.mark_sending(1)
    progress.mark_sent(1)
    progress.mark_sending(2)

    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.config_path = config_path
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    calls: list[list[str]] = []
    app._invoke_print_engine = lambda args: calls.append(args) or subprocess.CompletedProcess(args, 0, "resumed", "")
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showerror",
        lambda title, message: errors.append((title, message)),
    )
    args = ["print_labels.exe", "--print", "--yes"]
    failed = subprocess.CompletedProcess(args, 1, "", f"{TRANSPORT_UNCERTAIN_CODE}: item 2")

    recovered = app._recover_print_progress(args, failed)

    assert recovered is None
    assert calls == []
    assert app.status_var.value == "인쇄 오류 · 이전 인쇄 작업의 전송 상태를 확인해야 합니다."
    assert errors and errors[-1][0] == "인쇄 오류"
    assert "자동 재전송하지 않았습니다" in errors[-1][1]


def test_manager_new_job_starts_without_confirmation(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.config_path = tmp_path / "config.ini"
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    calls: list[list[str]] = []
    app._invoke_print_engine = lambda args: calls.append(args) or subprocess.CompletedProcess(args, 0, "new", "")
    args = ["print_labels.exe", "--print", "--yes"]
    blocked = subprocess.CompletedProcess(args, 1, "", f"{NEW_JOB_REQUIRED_CODE}: different job")

    recovered = app._recover_print_progress(args, blocked)

    assert recovered is not None and recovered.returncode == 0
    assert calls == [[*args, "--new-job"]]


def test_manager_unknown_resolution_dialog_has_three_explicit_choices():
    import inspect

    source = inspect.getsource(_ask_unknown_resolution)
    assert 'text="출력됨"' in source
    assert 'text="출력 안 됨"' in source
    assert 'text="취소"' in source


def test_print_readiness_errors_require_barcode_and_numeric_quantity(tmp_path):
    config_path = tmp_path / "config.ini"
    _write_ready_config(config_path)
    rows = [
        {"item_code": "A100", "item_name": "No Barcode", "barcode": "", "print_qty": "1"},
        {"item_code": "B100", "item_name": "Bad Qty", "barcode": "B100", "print_qty": "abc"},
    ]

    errors = _print_readiness_errors(rows, config_path=config_path)

    assert "1행 바코드가 비어 있습니다." in errors
    assert "2행 출력 매수는 숫자로 입력하세요." in errors


def test_print_readiness_errors_report_invalid_printer_settings(tmp_path):
    config_path = tmp_path / "config.ini"
    _write_ready_config(config_path, gap_mm="0", media_type="gap")
    rows = [{"item_code": "A100", "item_name": "Ready", "barcode": "A100", "print_qty": "1"}]

    errors = _print_readiness_errors(rows, config_path=config_path)

    assert any("프린터 설정:" in error and "갭 용지" in error for error in errors)


def test_run_print_job_blocks_before_subprocess_when_readiness_fails(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.queue_path = tmp_path / "print_queue.xlsx"
    app.db_path = tmp_path / "barcode_db.xlsx"
    app.config_path = tmp_path / "config.ini"
    _write_ready_config(app.config_path)
    app.print_exe = tmp_path / "print_labels.exe"
    app.print_exe.write_text("stub", encoding="utf-8")
    app.db_rows = []
    app.label_rows = [{"item_code": "A100", "item_name": "No Barcode", "barcode": "", "print_qty": "1"}]
    app.selected_label_indexes = set()
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    calls: list[list[str]] = []
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr("barcode_label_automation.label_manager_app.subprocess.run", lambda args, **_kwargs: calls.append(args))
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showwarning",
        lambda title, message: warnings.append((title, message)),
    )

    app.run_print_job("--dry-run")

    assert calls == []
    assert warnings
    assert warnings[0][0] == "인쇄 전 점검"
    assert "바코드가 비어 있습니다" in warnings[0][1]


def test_build_support_package_args_uses_customer_base_dir(tmp_path):
    preflight_exe = tmp_path / "고객환경점검.exe"

    assert _build_support_package_args(preflight_exe, tmp_path) == [
        str(preflight_exe),
        "--base-dir",
        str(tmp_path),
    ]


def test_build_preflight_check_args_skips_support_zip(tmp_path):
    preflight_exe = tmp_path / "고객환경점검.exe"

    assert _build_preflight_check_args(preflight_exe, tmp_path) == [
        str(preflight_exe),
        "--base-dir",
        str(tmp_path),
        "--no-support-package",
    ]


def test_read_preflight_summary_reads_report_result_line(tmp_path):
    report_path = tmp_path / "customer_preflight_report.txt"
    report_path.write_text("제목\n점검 결과: 정상 29개 / 오류 0개\n끝", encoding="utf-8-sig")

    assert _read_preflight_summary(report_path) == "점검 결과: 정상 29개 / 오류 0개"


def test_run_preflight_check_reports_success_without_support_zip(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.preflight_exe = tmp_path / "고객환경점검.exe"
    app.preflight_exe.write_text("stub", encoding="utf-8")
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    app.update_idletasks = lambda: None
    report_path, package_path = _support_package_paths(tmp_path)
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("점검 결과: 정상 29개 / 오류 0개\n", encoding="utf-8")
        assert kwargs["cwd"] == tmp_path
        assert kwargs["timeout"] == 180
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("barcode_label_automation.label_manager_app.subprocess.run", fake_run)
    popups: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showinfo",
        lambda title, message: popups.append((title, message)),
    )

    app.run_preflight_check()

    assert calls == [[str(app.preflight_exe), "--base-dir", str(tmp_path), "--no-support-package"]]
    assert "실행 전 점검 완료" in app.status_var.value
    assert popups
    assert "정상 29개 / 오류 0개" in popups[0][1]
    assert not package_path.exists()


def test_run_preflight_check_reports_failure_and_support_guidance(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.preflight_exe = tmp_path / "고객환경점검.exe"
    app.preflight_exe.write_text("stub", encoding="utf-8")
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    app.update_idletasks = lambda: None
    report_path, _package_path = _support_package_paths(tmp_path)

    def fake_run(args, **_kwargs):
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("점검 결과: 정상 28개 / 오류 1개\n", encoding="utf-8")
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr("barcode_label_automation.label_manager_app.subprocess.run", fake_run)
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showerror",
        lambda title, message: errors.append((title, message)),
    )

    app.run_preflight_check()

    assert "오류가 발견" in app.status_var.value
    assert errors
    assert "정상 28개 / 오류 1개" in errors[0][1]
    assert "지원 패키지 생성" in errors[0][1]


def test_create_support_package_runs_preflight_and_reports_zip(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.preflight_exe = tmp_path / "고객환경점검.exe"
    app.preflight_exe.write_text("stub", encoding="utf-8")
    app.status_var = SimpleNamespace(value="", set=lambda value: setattr(app.status_var, "value", value))
    app.update_idletasks = lambda: None
    report_path, package_path = _support_package_paths(tmp_path)
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("ok", encoding="utf-8")
        package_path.write_bytes(b"PK")
        assert kwargs["cwd"] == tmp_path
        assert kwargs["timeout"] == 180
        return SimpleNamespace(returncode=0, stdout="지원 패키지 저장", stderr="")

    monkeypatch.setattr("barcode_label_automation.label_manager_app.subprocess.run", fake_run)
    popups: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showinfo",
        lambda title, message: popups.append((title, message)),
    )

    app.create_support_package()

    assert calls == [[str(app.preflight_exe), "--base-dir", str(tmp_path)]]
    assert "지원 패키지 생성 완료" in app.status_var.value
    assert popups
    assert str(package_path) in popups[0][1]


def test_create_support_package_warns_when_preflight_missing(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.preflight_exe = tmp_path / "고객환경점검.exe"
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showwarning",
        lambda title, message: warnings.append((title, message)),
    )

    app.create_support_package()

    assert warnings == [("지원 패키지", "고객환경점검.exe를 찾을 수 없습니다.")]


def test_open_quick_guide_opens_existing_file(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    guide_path = tmp_path / "사용안내.txt"
    guide_path.write_text("guide", encoding="utf-8")
    app.quick_guide_path = guide_path
    opened: list[Path] = []
    monkeypatch.setattr("barcode_label_automation.label_manager_app._open_file", lambda path: opened.append(path))

    app.open_quick_guide()

    assert opened == [guide_path]


def test_open_manual_warns_when_file_is_missing(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.manual_path = tmp_path / "missing.txt"
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "barcode_label_automation.label_manager_app.messagebox.showwarning",
        lambda title, message: warnings.append((title, message)),
    )

    app.open_manual()

    assert warnings == [("상세 매뉴얼", "상세 매뉴얼 파일을 찾을 수 없습니다.")]


def test_label_manager_prefers_docx_manual_over_text_manual():
    import inspect

    source = inspect.getsource(LabelManagerApp.__init__)

    docx_index = source.index('base_dir / "라벨출력패키지_고객용_매뉴얼.docx"')
    text_index = source.index('base_dir / "설치_및_사용_메뉴얼.txt"')
    assert docx_index < text_index


def test_rows_with_print_quantity_returns_copies_and_clamps_quantity():
    rows = [{"barcode": "A", "print_qty": "2"}]

    copied = _rows_with_print_quantity(rows, 120)

    assert copied == [{"barcode": "A", "print_qty": "100"}]
    assert rows == [{"barcode": "A", "print_qty": "2"}]


def test_default_print_quantity_uses_first_valid_positive_value():
    assert _default_print_quantity([{"print_qty": ""}, {"print_qty": "3"}]) == 3
    assert _default_print_quantity([{"print_qty": "bad"}]) == 1


def test_top_action_surface_is_three_menus():
    import inspect

    source = inspect.getsource(LabelManagerApp._build_ui)

    assert 'text="DB 파일"' in source
    assert 'text="설정"' in source
    assert 'text="출력"' in source
    assert "DB 연결" in source
    assert "DB 해제" in source
    assert "프린터 설정" in source
    assert "실행 전 점검" in source
    assert "빠른 사용안내 열기" in source
    assert "상세 매뉴얼 열기" in source
    assert "지원 패키지 생성" in source
    assert 'label="인쇄"' in source
    assert 'label="전체 선택"' in source
    assert 'label="선택 해제"' in source
    assert "출력 파일 확인" not in source
    assert "출력 폴더 열기" not in source
    assert "인쇄 데이터" in source
    assert "원본 DB" in source
    assert "self._build_start_checklist(workflow_inner)" in source
    assert "self._build_job_panel(job_inner)" in source


def test_start_checklist_exposes_first_run_workflow():
    import inspect

    source = inspect.getsource(LabelManagerApp._build_start_checklist)

    assert "시작 체크리스트" in source
    assert "처음 설치, PC 교체, 프린터 변경" in source
    assert "1. 프린터 설정" in source
    assert "2. DB 연결" in source
    assert "3. 실행 전 점검" in source
    assert "4. 테스트 인쇄" in source
    assert "self.open_settings" in source
    assert "self.connect_db_file" in source
    assert "self.run_preflight_check" in source
    assert "self.print_with_quantity" in source


def test_label_manager_uses_chaeumlab_icon_in_spec():
    spec_path = Path(__file__).resolve().parents[1] / "label_manager.spec"

    assert "icon='assets/brand/chaeumlab_app_icon.ico'" in spec_path.read_text(encoding="utf-8")


def test_build_print_args_passes_excel_override_with_yes_for_explicit_print(tmp_path):
    args = _build_print_args(tmp_path / "print_labels.exe", tmp_path / "config.ini", "--print", tmp_path / "queue.xlsx")

    assert args == [
        str(tmp_path / "print_labels.exe"),
        "--config",
        str(tmp_path / "config.ini"),
        "--excel",
        str(tmp_path / "queue.xlsx"),
        "--print",
        "--yes",
    ]


def test_build_print_args_dry_run_does_not_add_yes(tmp_path):
    args = _build_print_args(tmp_path / "print_labels.exe", tmp_path / "config.ini", "--dry-run", tmp_path / "queue.xlsx")

    assert "--yes" not in args


def test_job_panel_keeps_support_package_generation_in_settings_menu():
    source = Path(__file__).resolve().parents[1].joinpath("barcode_label_automation", "label_manager_app.py").read_text(encoding="utf-8")
    panel_start = source.index("    def _build_job_panel")
    panel_end = source.index("    def _create_table", panel_start)
    panel_source = source[panel_start:panel_end]

    assert "지원 패키지는 설정 메뉴에서 생성합니다." in panel_source
    assert 'text="지원 패키지 생성"' not in panel_source
