from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from .config import load_config
from .errors import BarcodeLabelAutomationError
from .excel_reader import LabelRow, read_labels
from .logger import append_print_log
from .printers.network import check_connection as check_network_connection
from .printers.network import send_raw as send_network_raw
from .printers.windows_raw import send_raw as send_windows_raw
from .sanitizer import sanitize_barcode
from .templates import CommandPayload, render_label

MAX_PRINT_QTY = 100


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except BarcodeLabelAutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render and optionally print barcode labels.")
    parser.add_argument("--config", default="config.ini", help="Path to config.ini")
    parser.add_argument("--excel", default=None, help="Override the Excel workbook path from config.ini")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="Render commands to output files only")
    action.add_argument("--print", dest="do_print", action="store_true", help="Send commands to the configured printer")
    action.add_argument("--check-printer", action="store_true", help="Check printer connectivity without printing")
    parser.add_argument("--yes", action="store_true", help="Confirm non-interactive print execution")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.excel:
        config = replace(config, data=replace(config.data, excel_file=_resolve_cli_path(args.excel)))

    if args.check_printer:
        _check_printer(config.printer.mode, config.printer)
        return 0

    dry_run = not args.do_print
    if args.do_print:
        print("Print mode enabled. Commands will be sent to the configured printer.")
        print("Dry-run is the default; use --dry-run when you only want files in the output folder.")

    labels = read_labels(config.data.excel_file)
    config.data.output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = config.data.output_dir.parent

    log_entries: list[dict[str, object]] = []
    rendered_count = 0
    skipped_count = 0
    for row_index, row in enumerate(labels, start=1):
        validation_error = _validate_row_for_output(row)
        if validation_error:
            skipped_count += 1
            print(f"Warning: row {row_index} skipped. {validation_error}")
            log_entries.append(
                {
                    "label": row,
                    "language": config.printer.language,
                    "mode": "dry-run" if dry_run else config.printer.mode,
                    "status": "skipped",
                    "output_file": "",
                    "error_message": validation_error,
                }
            )
            continue

        command = render_label(
            config.printer.language,
            row,
            config.label.width_mm,
            config.label.height_mm,
            config.label.dpi,
            config.label.gap_mm,
            config.printer.print_method,
            config.barcode,
            config.printer.command_encoding,
            config.printer.print_speed,
            config.printer.print_density,
            config.printer.media_handling,
        )
        output_file = _write_command_file(
            config.data.output_dir,
            config.printer.language,
            config.printer.command_encoding,
            row,
            row_index,
            command,
        )
        if not dry_run:
            try:
                _send_to_printer(config.printer.mode, config.printer, command, config.printer.command_encoding)
            except BarcodeLabelAutomationError as exc:
                log_entries.append(
                    {
                        "label": row,
                        "language": config.printer.language,
                        "mode": config.printer.mode,
                        "status": "error",
                        "output_file": output_file,
                        "error_message": str(exc),
                    }
                )
                append_print_log(log_dir, log_entries)
                raise
        rendered_count += 1
        log_entries.append(
            {
                "label": row,
                "language": config.printer.language,
                "mode": "dry-run" if dry_run else config.printer.mode,
                "status": "rendered" if dry_run else "sent",
                "output_file": output_file,
                "error_message": "",
            }
        )

    log_path = append_print_log(log_dir, log_entries)
    print(f"{rendered_count} label command file(s) written to {_display_path(config.data.output_dir, log_dir)}")
    if skipped_count:
        print(f"{skipped_count} row(s) skipped before rendering or printing.")
    print(f"Print log written to {_display_path(log_path, log_dir)}")
    if dry_run:
        print("Dry-run complete. No data was sent to a printer.")
    return 0


def _check_printer(mode: str, printer_config: object) -> None:
    if mode == "network":
        check_network_connection(printer_config.ip, printer_config.port)  # type: ignore[attr-defined]
        print(f"Printer connection check succeeded: {printer_config.ip}:{printer_config.port}")  # type: ignore[attr-defined]
        print("No label data was sent.")
        return
    if mode == "windows_raw":
        print("windows_raw mode does not support a no-output connectivity check yet.")
        print("No label data was sent.")
        return
    raise ValueError("printer.mode must be 'network' or 'windows_raw'")


def _validate_row_for_output(row: LabelRow) -> str | None:
    if not row.barcode.strip():
        return "barcode is empty"
    try:
        sanitize_barcode(row.barcode)
    except ValueError:
        return "barcode is empty or contains no printable barcode characters"
    if row.print_qty <= 0:
        return "print_qty must be greater than 0"
    if row.print_qty > MAX_PRINT_QTY:
        return f"print_qty exceeds the safety limit of {MAX_PRINT_QTY}"
    return None


def _write_command_file(
    output_dir: Path,
    language: str,
    command_encoding: str,
    row: LabelRow,
    row_index: int,
    command: CommandPayload,
) -> Path:
    path = output_dir / f"label_{row_index:03d}.{language}"
    payload = command if isinstance(command, bytes) else command.encode(command_encoding, errors="replace")
    path.write_bytes(payload)
    return path


def _send_to_printer(mode: str, printer_config: object, command: CommandPayload, command_encoding: str) -> None:
    if mode == "network":
        send_network_raw(printer_config.ip, printer_config.port, command, command_encoding)  # type: ignore[attr-defined]
        return
    if mode == "windows_raw":
        send_windows_raw(printer_config.windows_printer_name, command, command_encoding)  # type: ignore[attr-defined]
        return
    raise ValueError("printer.mode must be 'network' or 'windows_raw'")


def _display_path(path: Path, base_dir: Path) -> str:
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


def _resolve_cli_path(value: str) -> Path:
    path = Path(value.strip())
    return path if path.is_absolute() else Path.cwd() / path
