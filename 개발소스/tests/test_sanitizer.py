from __future__ import annotations

import pytest

from barcode_label_automation.sanitizer import sanitize_barcode, sanitize_slcs_text, sanitize_tspl_text, sanitize_zpl_text


def test_sanitize_slcs_text_removes_single_quotes():
    assert sanitize_slcs_text("sensor ' bracket") == "sensor   bracket"


def test_sanitize_barcode_rejects_empty_values():
    with pytest.raises(ValueError, match="barcode is empty"):
        sanitize_barcode(" !!! ")


def test_sanitize_tspl_text_removes_double_quotes():
    assert sanitize_tspl_text('sensor " bracket') == "sensor   bracket"


def test_sanitize_zpl_text_removes_command_prefixes():
    assert sanitize_zpl_text("sensor ^ bracket ~") == "sensor   bracket  "
