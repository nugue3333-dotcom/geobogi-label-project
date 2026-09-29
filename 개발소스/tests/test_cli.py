from __future__ import annotations

import pytest

from barcode_label_automation import cli
from barcode_label_automation.errors import BarcodeLabelAutomationError
from barcode_label_automation.cli import _validate_row_for_output, _write_command_file
from barcode_label_automation.data_store import save_label_rows
from barcode_label_automation.excel_reader import LabelRow
from barcode_label_automation.print_progress import PROGRESS_FILE_NAME, PrintProgress


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


def test_print_requires_explicit_yes_confirmation(monkeypatch, tmp_path):
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

    with pytest.raises(BarcodeLabelAutomationError, match="--print requires --yes"):
        cli._main(["--config", str(config_path), "--print"])

    assert sent == []
    assert not (tmp_path / "out" / "label_001.slcs").exists()


def test_limit_and_force_print_qty_make_single_physical_test_job(monkeypatch, tmp_path):
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
    monkeypatch.setattr(cli, "read_labels", lambda _path: [make_row("FIRST", print_qty=5), make_row("SECOND")])
    monkeypatch.setattr(cli, "_send_to_printer", lambda _mode, _printer, command, _encoding: sent.append(command))

    result = cli._main(["--config", str(config_path), "--print", "--yes", "--limit", "1", "--force-print-qty", "1"])

    assert result == 0
    assert len(sent) == 1
    assert "FIRST" in sent[0]
    assert "SECOND" not in sent[0]
    assert sent[0].endswith("P1\n")
    assert (tmp_path / "out" / "label_001.slcs").exists()
    assert not (tmp_path / "out" / "label_002.slcs").exists()


def test_partial_failure_blocks_unknown_retry_and_resumes_only_pending(monkeypatch, tmp_path):
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
    barcodes = ("JOB-A-001", "JOB-B-002", "JOB-C-003")
    monkeypatch.setattr(cli, "read_labels", lambda _path: [make_row(value) for value in barcodes])
    sent: list[str] = []

    def fail_on_b(_mode, _printer, command, _encoding):
        payload = command.decode("cp949") if isinstance(command, bytes) else command
        barcode = next(value for value in barcodes if value in payload)
        sent.append(barcode)
        if barcode == "JOB-B-002":
            raise OSError("transport failed")

    monkeypatch.setattr(cli, "_send_to_printer", fail_on_b)
    assert cli.main(["--config", str(config_path), "--print", "--yes"]) == 1
    assert sent == ["JOB-A-001", "JOB-B-002"]

    progress_path = tmp_path / "out" / PROGRESS_FILE_NAME
    progress = PrintProgress.load(progress_path)
    assert [progress.status(index) for index in (1, 2, 3)] == ["sent", "unknown", "pending"]

    sent.clear()
    monkeypatch.setattr(cli, "_send_to_printer", lambda *_args: sent.append("unexpected"))
    assert cli.main(["--config", str(config_path), "--print", "--yes"]) == 1
    assert sent == []

    progress = PrintProgress.load(progress_path)
    progress.resolve_unknown(2, was_printed=True)
    resumed: list[str] = []

    def record_resume(_mode, _printer, command, _encoding):
        payload = command.decode("cp949") if isinstance(command, bytes) else command
        resumed.append(next(value for value in barcodes if value in payload))

    monkeypatch.setattr(cli, "_send_to_printer", record_resume)
    assert cli.main(["--config", str(config_path), "--print", "--yes"]) == 0
    assert resumed == ["JOB-C-003"]
    assert PrintProgress.load(progress_path).sent_indexes == [1, 2, 3]


def test_later_render_error_calls_no_transport(monkeypatch, tmp_path):
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
    monkeypatch.setattr(cli, "read_labels", lambda _path: [make_row("A"), make_row("B")])
    original_render = cli.render_label

    def render(*args, **kwargs):
        if args[1].barcode == "B":
            raise ValueError("later row invalid")
        return original_render(*args, **kwargs)

    sends: list[object] = []
    monkeypatch.setattr(cli, "render_label", render)
    monkeypatch.setattr(cli, "_send_to_printer", lambda *args: sends.append(args))

    with pytest.raises(ValueError, match="later row invalid"):
        cli._main(["--config", str(config_path), "--print", "--yes"])
    assert sends == []


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


def test_sewoo_auto_brand_renders_zpl_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr("barcode_label_automation.config.APPROVED_SEWOO_ZPL_MODELS", frozenset({"TEST-ZPL"}))
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[printer]
brand = sewoo
model = TEST-ZPL
mode = network
language = auto
command_encoding = auto
ip = 127.0.0.1
port = 9100

[brand.sewoo]
language = zpl
command_encoding = utf-8
windows_printer_name = SEWOO Label Printer

[label]
width_mm = 50
height_mm = 30
dpi = 203
gap_mm = 3

[data]
excel_file = print_queue.xlsx
output_dir = out
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "read_labels", lambda _path: [make_row("SEWOO-001")])

    result = cli._main(["--config", str(config_path), "--dry-run"])

    assert result == 0
    payload = (tmp_path / "out" / "label_001.zpl").read_text(encoding="utf-8")
    assert payload.startswith("^XA\n")
    assert "^FDSEWOO-001^FS" in payload
