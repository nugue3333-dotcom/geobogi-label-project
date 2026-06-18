from __future__ import annotations

from types import SimpleNamespace

from barcode_label_automation.data_store import load_label_rows, save_db_rows, save_label_rows
from barcode_label_automation.label_manager_app import (
    LabelManagerApp,
    _build_print_args,
    _delete_label_rows,
    _ensure_label_row_index,
    _label_rows_from_db_rows,
    _selected_print_queue_path,
    main as manager_main,
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


def test_selected_print_uses_temporary_excel_without_replacing_full_queue(monkeypatch, tmp_path):
    app = LabelManagerApp.__new__(LabelManagerApp)
    app.base_dir = tmp_path
    app.queue_path = tmp_path / "print_queue.xlsx"
    app.db_path = tmp_path / "barcode_db.xlsx"
    app.config_path = tmp_path / "config.ini"
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


def test_build_print_args_passes_excel_override_and_yes_for_print(tmp_path):
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
