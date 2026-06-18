from __future__ import annotations

from barcode_label_automation import cli
from barcode_label_automation.cli import _validate_row_for_output, _write_command_file
from barcode_label_automation.data_store import save_label_rows
from barcode_label_automation.excel_reader import LabelRow


def make_row(barcode: str = "123456", print_qty: int = 1) -> LabelRow:
    return LabelRow(
        item_code="ITEM-001",
        item_name="Sample",
        barcode=barcode,
        lot_no="LOT-A",
        qty=1,
        print_qty=print_qty,
    )


def test_validate_row_skips_empty_barcode():
    assert _validate_row_for_output(make_row(barcode="")) == "barcode is empty"


def test_validate_row_skips_non_positive_print_qty():
    assert _validate_row_for_output(make_row(print_qty=0)) == "print_qty must be greater than 0"


def test_validate_row_skips_print_qty_over_safety_limit():
    assert _validate_row_for_output(make_row(print_qty=101)) == "print_qty exceeds the safety limit of 100"


def test_print_yes_runs_without_prompt_and_writes_root_log(monkeypatch, tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[printer]
mode = network
language = slcs
ip = 127.0.0.1
port = 9100

[label]
width_mm = 60
height_mm = 40
dpi = 203

[data]
excel_file = print_queue.xlsx
output_dir = out
""".strip(),
        encoding="utf-8",
    )

    sent: list[str] = []
    monkeypatch.setattr(cli, "read_labels", lambda _path: [make_row()])
    monkeypatch.setattr(cli, "_send_to_printer", lambda _mode, _printer, command, _encoding: sent.append(command))

    result = cli._main(["--config", str(config_path), "--print", "--yes"])

    assert result == 0
    assert sent
    assert (tmp_path / "out" / "label_001.slcs").exists()
    assert (tmp_path / "print_log.xlsx").exists()


def test_excel_override_takes_precedence_over_config_excel_file(tmp_path, monkeypatch):
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[printer]
mode = network
language = slcs
ip = 127.0.0.1
port = 9100

[label]
width_mm = 60
height_mm = 40
dpi = 203

[data]
excel_file = missing.xlsx
output_dir = out
""".strip(),
        encoding="utf-8",
    )
    override_path = tmp_path / "override_queue.xlsx"
    save_label_rows(
        override_path,
        [
            {
                "item_code": "ITEM-EXCEL",
                "item_name": "Override",
                "barcode": "OVERRIDE-001",
                "lot_no": "LOT-EXCEL",
                "qty": "1",
                "print_qty": "1",
            }
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = cli._main(["--config", str(config_path), "--excel", "override_queue.xlsx", "--dry-run"])

    assert result == 0
    assert (tmp_path / "out" / "label_001.slcs").exists()


def test_write_command_file_uses_configured_encoding(tmp_path):
    path = _write_command_file(tmp_path, "slcs", "cp949", make_row(), 1, "ITEM: 한글\n")

    assert path.read_bytes() == "ITEM: 한글\n".encode("cp949")


def test_write_command_file_preserves_binary_payload(tmp_path):
    payload = b"BITMAP 0,0,1,2,0,\x80\x00\nPRINT 1,1\n"

    path = _write_command_file(tmp_path, "tspl", "utf-8", make_row(), 1, payload)

    assert path.read_bytes() == payload
