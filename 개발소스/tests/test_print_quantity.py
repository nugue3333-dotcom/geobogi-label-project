import pytest
from barcode_label_automation.print_quantity import parse_print_quantity

@pytest.mark.parametrize("value", [1, 101, 1001, 1000000, "1000000", " 00012 "])
def test_positive_count_has_no_application_cap(value):
    assert parse_print_quantity(value) == int(value)

@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, 1.1, float("nan"), float("inf"), "1.0", "1e3", "-1", "+1", "", None])
def test_invalid_counts_are_rejected(value):
    with pytest.raises(ValueError):
        parse_print_quantity(value)

def test_excel_integral_float_is_supported():
    assert parse_print_quantity(1001.0, allow_integral_float=True) == 1001

@pytest.mark.parametrize("value", [True, 1.5, float("nan"), float("inf")])
def test_excel_invalid_float_never_truncates(value):
    with pytest.raises(ValueError):
        parse_print_quantity(value, allow_integral_float=True)
