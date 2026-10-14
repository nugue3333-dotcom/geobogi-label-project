"""Deterministic label value generation; never reserves numbers or sends output."""
from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

FIELD_RE = re.compile(r"\{\{([^{}]+)\}\}")
DATE_FORMATS = {"YYYYMMDD": "%Y%m%d", "YYMMDD": "%y%m%d", "YYYY-MM-DD": "%Y-%m-%d"}
RULE_KINDS = ("serial", "date", "text", "slice")


class ValueGenerationCancelled(ValueError):
    """Cancelled before reservation or transport."""


@dataclass(frozen=True)
class GeneratedLabel:
    row: dict[str, str]
    copies: int


def _integer(value: object, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise ValueError(f"{label}: {minimum} 이상의 정수를 입력하세요.")
    result = int(str(value))
    if result < minimum:
        raise ValueError(f"{label}: {minimum} 이상의 정수를 입력하세요.")
    return result


def job_date_value(value: date | str | None = None) -> date:
    if value is None:
        return datetime.now(timezone(timedelta(hours=9), "Asia/Seoul")).date()
    if isinstance(value, datetime):
        raise ValueError("작업 기준일은 시간 없는 날짜로 지정하세요.")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("작업 기준일은 YYYY-MM-DD 날짜로 지정하세요.") from exc


def validate_value_rules(rules: Sequence[Mapping[str, object]], headers: Sequence[str] = ()) -> list[dict[str, object]]:
    """Normalize explicit rule settings and reject ambiguous bindings."""
    if not isinstance(rules, (list, tuple)):
        raise ValueError("값 생성 규칙은 목록이어야 합니다.")
    names = [str(rule.get("name", "")).strip() for rule in rules if isinstance(rule, Mapping)]
    if len(names) != len(rules):
        raise ValueError("값 생성 규칙 형식이 올바르지 않습니다.")
    if any(not name or len(name) > 80 or "{" in name or "}" in name or name.startswith("__cl_") for name in names):
        raise ValueError("생성 필드 이름은 1~80자이며 중괄호와 __cl_ 접두사를 사용할 수 없습니다.")
    if len(set(names)) != len(names):
        raise ValueError("생성 필드 이름이 중복됩니다.")
    collisions = set(names).intersection(str(header) for header in headers)
    if collisions:
        raise ValueError("DB 열과 생성 필드 이름이 같습니다: " + ", ".join(sorted(collisions)))
    result: list[dict[str, object]] = []
    for index, rule in enumerate(rules):
        name, kind = names[index], str(rule.get("kind", ""))
        if kind not in RULE_KINDS:
            raise ValueError(f"{name}: 지원하는 값 생성 방식을 선택하세요.")
        item: dict[str, object] = {"name": name, "kind": kind}
        references: list[str] = []
        if kind == "serial":
            for key, default, minimum, label in (
                ("start", 1, 0, "시작 번호"), ("step", 1, 1, "증가량"),
                ("digits", 6, 1, "자리수"), ("copies_per_value", 1, 1, "번호당 복사 수"),
            ):
                item[key] = _integer(rule.get(key, default), f"{name} · {label}", minimum)
            if int(item["digits"]) > 30:
                raise ValueError(f"{name}: 자리수는 1~30자리로 지정하세요.")
            if len(str(item["start"])) > int(item["digits"]):
                raise ValueError(f"{name}: 시작 번호가 지정한 자리수를 넘습니다.")
            item["reset"] = str(rule.get("reset", "job"))
            if item["reset"] not in ("job", "continue"):
                raise ValueError(f"{name}: 작업마다 시작 또는 계속 발급을 선택하세요.")
            item["prefix"], item["suffix"] = str(rule.get("prefix", "")), str(rule.get("suffix", ""))
        elif kind == "date":
            item["base"] = str(rule.get("base", "job"))
            if item["base"] not in ("job", "field"):
                raise ValueError(f"{name}: 작업 날짜 또는 DB 날짜를 선택하세요.")
            item["field"] = str(rule.get("field", "")).strip()
            if item["base"] == "field":
                if not item["field"]:
                    raise ValueError(f"{name}: 기준 날짜 열을 선택하세요.")
                references.append(str(item["field"]))
            raw_offset = rule.get("offset_days", 0)
            if isinstance(raw_offset, bool) or not re.fullmatch(r"-?[0-9]+", str(raw_offset)):
                raise ValueError(f"{name}: 더할 일수를 정수로 입력하세요.")
            item["offset_days"] = int(str(raw_offset))
            if abs(int(item["offset_days"])) > 365000:
                raise ValueError(f"{name}: 날짜 계산 범위가 너무 큽니다.")
            item["format"] = str(rule.get("format", "YYYYMMDD"))
            if item["format"] not in DATE_FORMATS:
                raise ValueError(f"{name}: 날짜 표시 형식을 선택하세요.")
        elif kind == "text":
            item["template"] = str(rule.get("template", ""))
            references.extend(match.group(1).strip() for match in FIELD_RE.finditer(str(item["template"])))
        else:
            item["field"] = str(rule.get("field", "")).strip()
            if not item["field"]:
                raise ValueError(f"{name}: 추출할 원본 열을 선택하세요.")
            item["start"] = _integer(rule.get("start", 1), f"{name} · 시작 위치", 1)
            item["length"] = _integer(rule.get("length", 1), f"{name} · 추출 글자 수", 1)
            references.append(str(item["field"]))
        for reference in references:
            if reference in names[index:]:
                raise ValueError(f"{name}: '{reference}'은 앞에 정의한 생성 필드만 참조할 수 있습니다.")
            if headers and reference not in headers and reference not in names[:index]:
                raise ValueError(f"{name}: 원본 열 '{reference}'이 없습니다. DB를 다시 연결하세요.")
        result.append(item)
    return result


def _field_value(row: Mapping[str, str], field: str, name: str) -> str:
    if field not in row:
        raise ValueError(f"{name}: 원본 열 '{field}'이 없습니다. DB를 다시 연결하세요.")
    return str(row[field])


def _date_field(raw: str, name: str) -> date:
    try:
        if re.fullmatch(r"[0-9]{8}", raw):
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{name}: 원본 날짜는 YYYYMMDD 또는 YYYY-MM-DD여야 합니다.") from exc


def iter_generated_labels(
    rows: Sequence[Mapping[str, object]], quantities: Sequence[int],
    rules: Sequence[Mapping[str, object]], job_date: date | str | None = None,
    start_overrides: Mapping[str, int] | None = None,
    *, cancel_check: Callable[[], bool] | None = None,
) -> Iterator[GeneratedLabel]:
    """Expand variable values, compress only identical adjacent copies; no state writes."""
    if len(rows) != len(quantities):
        raise ValueError("출력 행과 인쇄 매수의 개수가 다릅니다.")
    headers = tuple(dict.fromkeys(str(key) for row in rows for key in row))
    normalized = validate_value_rules(rules, headers)
    fixed_date = job_date_value(job_date)
    overrides = dict(start_overrides or {})
    serials = [rule for rule in normalized if rule["kind"] == "serial"]
    normalized_quantities = [_integer(value, "인쇄 매수", 1) for value in quantities]
    total = sum(normalized_quantities)
    for rule in serials:
        start = _integer(overrides.get(str(rule["name"]), rule["start"]), f"{rule['name']} · 시작 번호")
        last = start + ((total - 1) // int(rule["copies_per_value"])) * int(rule["step"]) if total else start
        if len(str(last)) > int(rule["digits"]):
            raise ValueError(f"{rule['name']}: 마지막 번호 {last}가 {rule['digits']}자리 범위를 넘습니다. 출력 전 자리수를 늘리세요.")
    pending: GeneratedLabel | None = None
    position = 0
    for source, qty in zip(rows, normalized_quantities):
        remaining = qty
        while remaining:
            if cancel_check is not None and cancel_check():
                raise ValueGenerationCancelled("값 생성 작업을 취소했습니다. 번호를 예약하거나 프린터로 전송하지 않았습니다.")
            copies = min([remaining] + [int(rule["copies_per_value"]) - position % int(rule["copies_per_value"]) for rule in serials])
            generated = {str(key): str(value) for key, value in source.items()}
            for rule in normalized:
                name, kind = str(rule["name"]), rule["kind"]
                if kind == "serial":
                    start = _integer(overrides.get(name, rule["start"]), f"{name} · 시작 번호")
                    number = start + (position // int(rule["copies_per_value"])) * int(rule["step"])
                    if len(str(number)) > int(rule["digits"]):
                        raise ValueError(f"{name}: {number}번이 {rule['digits']}자리 범위를 넘습니다. 출력 전 자리수를 늘리세요.")
                    value = str(rule["prefix"]) + str(number).zfill(int(rule["digits"])) + str(rule["suffix"])
                elif kind == "date":
                    base = fixed_date if rule["base"] == "job" else _date_field(_field_value(generated, str(rule["field"]), name), name)
                    try:
                        calculated = base + timedelta(days=int(rule["offset_days"]))
                    except (OverflowError, ValueError) as exc:
                        raise ValueError(f"{name}: 계산한 날짜가 유효 범위를 넘습니다.") from exc
                    value = calculated.strftime(DATE_FORMATS[str(rule["format"])])
                elif kind == "text":
                    value = FIELD_RE.sub(lambda match: _field_value(generated, match.group(1).strip(), name), str(rule["template"]))
                else:
                    original = _field_value(generated, str(rule["field"]), name)
                    start = int(rule["start"]) - 1
                    if start >= len(original):
                        raise ValueError(f"{name}: 추출 시작 위치가 원본 {len(original)}글자를 넘습니다.")
                    value = original[start:start + int(rule["length"])]
                generated[name] = value
            if pending is not None and pending.row == generated:
                pending = GeneratedLabel(generated, pending.copies + copies)
            else:
                if pending is not None:
                    yield pending
                pending = GeneratedLabel(generated, copies)
            position += copies
            remaining -= copies
    if pending is not None:
        yield pending


def compile_generated_labels(
    rows: Sequence[Mapping[str, object]], quantities: Sequence[int],
    rules: Sequence[Mapping[str, object]], job_date: date | str | None = None,
    start_overrides: Mapping[str, int] | None = None,
    *, cancel_check: Callable[[], bool] | None = None,
) -> list[GeneratedLabel]:
    return list(iter_generated_labels(rows, quantities, rules, job_date, start_overrides, cancel_check=cancel_check))
