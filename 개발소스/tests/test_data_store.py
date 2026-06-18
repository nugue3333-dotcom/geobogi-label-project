from __future__ import annotations

from barcode_label_automation.data_store import (
    DB_HEADERS,
    LABEL_HEADERS,
    load_db_rows,
    load_label_rows,
    lookup_barcode,
    save_db_rows,
    save_label_rows,
)
from barcode_label_automation.excel_reader import read_labels


def test_label_rows_round_trip_and_match_print_engine(tmp_path):
    path = tmp_path / "print_queue.xlsx"
    rows = [
        {
            "item_code": "A1001",
            "item_name": "SENSOR BRACKET",
            "barcode": "88023502",
            "lot_no": "LOT250531",
            "qty": "100",
            "print_qty": "1",
        }
    ]

    save_label_rows(path, rows)

    assert load_label_rows(path) == rows
    label_rows = read_labels(path)
    assert label_rows[0].barcode == "88023502"
    assert label_rows[0].print_qty == 1


def test_barcode_db_lookup_fills_label_fields(tmp_path):
    path = tmp_path / "barcode_db.xlsx"
    rows = [
        {
            "barcode": "KOR-TEST-001",
            "item_code": "K1001",
            "item_name": "한글품목테스트",
            "lot_no": "LOT-HANGUL",
            "qty": "10",
            "print_qty": "1",
        }
    ]

    save_db_rows(path, rows)
    loaded = load_db_rows(path)
    result = lookup_barcode(loaded, "KOR-TEST-001")

    assert result is not None
    assert result.item_name == "한글품목테스트"
    assert result.qty == "10"


def test_missing_files_are_created_with_required_headers(tmp_path):
    queue_path = tmp_path / "print_queue.xlsx"
    db_path = tmp_path / "barcode_db.xlsx"

    assert load_label_rows(queue_path) == []
    assert set(load_db_rows(db_path)[0]) == set(DB_HEADERS)
    assert set(load_label_rows(queue_path) or [{header: "" for header in LABEL_HEADERS}][0]) == set(LABEL_HEADERS)
