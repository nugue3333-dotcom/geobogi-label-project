"""Shared validation for print counts without an arbitrary application cap."""
from __future__ import annotations

import math
import re


def parse_print_quantity(value: object, *, allow_integral_float: bool = False) -> int:
    message = "인쇄 매수는 1 이상의 정수로 입력해 주세요."
    if isinstance(value, bool):
        raise ValueError(message)
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and allow_integral_float:
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError(message)
        number = int(value)
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        number = int(value.strip())
    else:
        raise ValueError(message)
    if number < 1:
        raise ValueError(message)
    return number
