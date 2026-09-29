from __future__ import annotations

import socket

import pytest

from barcode_label_automation.errors import (
    PrinterConnectionRefusedError,
    PrinterHostResolutionError,
    PrinterInvalidIPError,
    PrinterMissingConfigError,
    PrinterTimeoutError,
)
from barcode_label_automation.printers import network


def test_check_connection_rejects_missing_config():
    with pytest.raises(PrinterMissingConfigError, match="Missing network printer config"):
        network.check_connection("", 9100)


def test_check_connection_rejects_invalid_endpoint():
    with pytest.raises(PrinterInvalidIPError, match="IP address or host name"):
        network.check_connection("bad host", 9100)


@pytest.mark.parametrize("host", ["printer.local", "label-printer.example.com", "127.0.0.1", "::1"])
def test_check_connection_accepts_ip_or_hostname(monkeypatch, host):
    calls = []

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(network.socket, "create_connection", lambda endpoint, timeout: calls.append((endpoint, timeout)) or FakeSocket())

    network.check_connection(host, 9100, timeout=2.5)

    assert calls == [((host, 9100), 2.5)]


def test_check_connection_converts_unicode_hostname_to_idna(monkeypatch):
    calls = []

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(network.socket, "create_connection", lambda endpoint, timeout: calls.append(endpoint) or FakeSocket())

    network.check_connection("프린터.local", 9100)

    assert calls == [("프린터.local".encode("idna").decode("ascii"), 9100)]


def test_send_raw_reports_timeout(monkeypatch):
    def fake_create_connection(*args, **kwargs):
        raise socket.timeout()

    monkeypatch.setattr(network.socket, "create_connection", fake_create_connection)

    with pytest.raises(PrinterTimeoutError, match="Timed out"):
        network.send_raw("127.0.0.1", 9100, "CB\nP1\n")


def test_send_raw_reports_connection_refused(monkeypatch):
    def fake_create_connection(*args, **kwargs):
        raise ConnectionRefusedError()

    monkeypatch.setattr(network.socket, "create_connection", fake_create_connection)

    with pytest.raises(PrinterConnectionRefusedError, match="refused"):
        network.send_raw("127.0.0.1", 9100, "CB\nP1\n")


def test_check_connection_reports_host_resolution_failure(monkeypatch):
    def fake_create_connection(*args, **kwargs):
        raise socket.gaierror(11003, "getaddrinfo failed")

    monkeypatch.setattr(network.socket, "create_connection", fake_create_connection)

    with pytest.raises(PrinterHostResolutionError, match="프린터 주소를 찾을 수 없습니다"):
        network.check_connection("printer-name", 9100)


def test_send_raw_reports_host_resolution_failure(monkeypatch):
    def fake_create_connection(*args, **kwargs):
        raise socket.gaierror(11003, "getaddrinfo failed")

    monkeypatch.setattr(network.socket, "create_connection", fake_create_connection)

    with pytest.raises(PrinterHostResolutionError, match="프린터 주소를 찾을 수 없어 전송하지 못했습니다"):
        network.send_raw("printer-name", 9100, "CB\nP1\n")


def test_send_raw_uses_configured_encoding(monkeypatch):
    sent_payloads: list[bytes] = []

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def sendall(self, payload: bytes):
            sent_payloads.append(payload)

    monkeypatch.setattr(network.socket, "create_connection", lambda *_args, **_kwargs: FakeSocket())

    network.send_raw("127.0.0.1", 9100, "ITEM: 한글", "cp949")

    assert sent_payloads == ["ITEM: 한글".encode("cp949")]


def test_send_raw_preserves_binary_payload(monkeypatch):
    sent_payloads: list[bytes] = []

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def sendall(self, payload: bytes):
            sent_payloads.append(payload)

    monkeypatch.setattr(network.socket, "create_connection", lambda *_args, **_kwargs: FakeSocket())

    network.send_raw("127.0.0.1", 9100, b"BITMAP 0,0,1,1,0,\x80\n", "cp949")

    assert sent_payloads == [b"BITMAP 0,0,1,1,0,\x80\n"]
