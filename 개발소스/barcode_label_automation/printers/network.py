from __future__ import annotations

import ipaddress
import socket

from ..errors import (
    PrinterConnectionError,
    PrinterConnectionRefusedError,
    PrinterInvalidIPError,
    PrinterMissingConfigError,
    PrinterTimeoutError,
)


def check_connection(ip: str, port: int, timeout: float = 5.0) -> None:
    validated_ip, validated_port = _validate_endpoint(ip, port)
    try:
        with socket.create_connection((validated_ip, validated_port), timeout=timeout):
            return
    except TimeoutError as exc:
        raise PrinterTimeoutError(f"Timed out while connecting to printer at {validated_ip}:{validated_port}.") from exc
    except ConnectionRefusedError as exc:
        raise PrinterConnectionRefusedError(
            f"Printer at {validated_ip}:{validated_port} refused the connection."
        ) from exc
    except OSError as exc:
        raise PrinterConnectionError(f"Could not connect to printer at {validated_ip}:{validated_port}: {exc}") from exc


def send_raw(ip: str, port: int, command: str | bytes, encoding: str = "utf-8", timeout: float = 10.0) -> None:
    validated_ip, validated_port = _validate_endpoint(ip, port)
    payload = command if isinstance(command, bytes) else command.encode(encoding, errors="replace")
    try:
        with socket.create_connection((validated_ip, validated_port), timeout=timeout) as sock:
            sock.sendall(payload)
    except TimeoutError as exc:
        raise PrinterTimeoutError(f"Timed out while sending data to printer at {validated_ip}:{validated_port}.") from exc
    except ConnectionRefusedError as exc:
        raise PrinterConnectionRefusedError(
            f"Printer at {validated_ip}:{validated_port} refused the connection."
        ) from exc
    except OSError as exc:
        raise PrinterConnectionError(f"Could not send data to printer at {validated_ip}:{validated_port}: {exc}") from exc


def _validate_endpoint(ip: str, port: int) -> tuple[str, int]:
    clean_ip = str(ip or "").strip()
    if not clean_ip or not port:
        raise PrinterMissingConfigError("Missing network printer config. Set printer.ip and printer.port in config.ini.")
    try:
        ipaddress.ip_address(clean_ip)
    except ValueError as exc:
        raise PrinterInvalidIPError(f"Invalid printer IP address: {clean_ip}") from exc
    if port < 1 or port > 65535:
        raise PrinterMissingConfigError("Missing network printer config. printer.port must be between 1 and 65535.")
    return clean_ip, port
