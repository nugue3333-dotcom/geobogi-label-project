from __future__ import annotations

import os

from ..errors import PrinterConnectionError


def send_raw(printer_name: str, command: str | bytes, encoding: str = "utf-8") -> None:
    if os.name != "nt":
        raise PrinterConnectionError("windows_raw mode is only supported on Windows.")

    try:
        import win32print  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PrinterConnectionError("windows_raw mode requires pywin32. Install it with: pip install pywin32") from exc

    handle = win32print.OpenPrinter(printer_name)
    try:
        job = win32print.StartDocPrinter(handle, 1, ("barcode-label", None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            payload = command if isinstance(command, bytes) else command.encode(encoding, errors="replace")
            win32print.WritePrinter(handle, payload)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)
