from datetime import date, datetime

import pytest

from barcode_label_automation.value_rules import (
    ValueGenerationCancelled, compile_generated_labels, iter_generated_labels,
    job_date_value, validate_value_rules,
)


def serial(**kwargs):
    rule = dict(name="번호", kind="serial", start=1, step=1, digits=4, copies_per_value=1, reset="job")
    rule.update(kwargs)
    return rule


def expanded(labels, field="번호"):
    return [label.row[field] for label in labels for _ in range(label.copies)]


def test_serial_increment_preserves_zero_and_input():
    rows = [{"품번": "00123"}]
    labels = compile_generated_labels(rows, [3], [serial()], "2026-10-08")
    assert expanded(labels) == ["0001", "0002", "0003"]
    assert rows == [{"품번": "00123"}]
    assert labels[0].row["품번"] == "00123"


def test_serial_step_prefix_suffix():
    rule = serial()
    rule.update(start=7, step=3, prefix="LOT-", suffix="-A")
    assert expanded(compile_generated_labels([{}], [3], [rule])) == ["LOT-0007-A", "LOT-0010-A", "LOT-0013-A"]


def test_serial_decrement_preserves_width_and_stops_before_underflow():
    rule = serial(start=3, digits=2, direction="down")
    assert expanded(compile_generated_labels([{}], [3], [rule])) == ["03", "02", "01"]
    with pytest.raises(ValueError, match="시작 범위보다 작아졌습니다"):
        compile_generated_labels([{}], [5], [rule])


@pytest.mark.parametrize(("alphabet", "start", "digits", "expected"), [
    ("uppercase", "AZ", 2, ["AZ", "BA", "BB"]),
    ("lowercase", "y", 2, ["y", "z", "aa"]),
    ("alphanumeric", "0Z", 2, ["0Z", "10", "11"]),
])
def test_alpha_serial_rollover(alphabet, start, digits, expected):
    rule = serial(name="순번", start=start, alphabet=alphabet, digits=digits,
                  preserve_width=(alphabet == "alphanumeric"))
    assert expanded(compile_generated_labels([{}], [len(expected)], [rule]), "순번") == expected


@pytest.mark.parametrize(('alphabet', 'start', 'expected'), [
    ('numeric', 8, ['8', '9', '10', '11', '12']),
    ('uppercase', 'Y', ['Y', 'Z', 'AA', 'AB', 'AC']),
    ('lowercase', 'y', ['y', 'z', 'aa', 'ab', 'ac']),
    ('alphanumeric', 'Y', ['Y', 'Z', '10', '11', '12']),
])
def test_automatic_width_rolls_over_without_truncation(alphabet, start, expected):
    rule = serial(start=start, digits=1, alphabet=alphabet, preserve_width=False)
    assert expanded(compile_generated_labels([{}], [5], [rule])) == expected


def test_automatic_width_accepts_start_larger_than_display_digits():
    rule = serial(start=10, digits=1, preserve_width=False)
    assert expanded(compile_generated_labels([{}], [2], [rule])) == ['10', '11']


def test_automatic_width_has_safe_absolute_limit_and_fixed_width_still_blocks():
    with pytest.raises(ValueError, match='최대 30자리'):
        compile_generated_labels([{}], [2], [serial(start=int('9' * 30), digits=1, preserve_width=False)])
    with pytest.raises(ValueError, match='마지막 번호'):
        compile_generated_labels([{}], [2], [serial(start=9, digits=1, preserve_width=True)])


def test_partial_db_replacement_requires_width_preservation():
    rule = serial(start=9, digits=1, preserve_width=False,
                  target_field='원본', target_start=2, target_length=1)
    with pytest.raises(ValueError, match='문자 수 유지'):
        compile_generated_labels([{'원본': 'A0B'}], [2], [rule])


def test_serial_replaces_selected_db_substring_without_changing_source():
    source = {"원본": "LOT-ABCD-X"}
    rule = serial(name="가공값", digits=4, target_field="원본", target_start=5, target_length=4)
    labels = compile_generated_labels([source], [2], [rule])
    assert expanded(labels, "가공값") == ["LOT-0001-X", "LOT-0002-X"]
    assert source == {"원본": "LOT-ABCD-X"}


def test_copy_groups_continue_across_db_rows():
    rule = serial()
    rule["copies_per_value"] = 2
    labels = compile_generated_labels([{"품번": "A"}, {"품번": "B"}], [3, 2], [rule])
    assert expanded(labels) == ["0001", "0001", "0002", "0002", "0003"]
    assert [(label.row["품번"], label.copies) for label in labels] == [("A", 2), ("A", 1), ("B", 1), ("B", 1)]


def test_multiple_serial_copy_boundaries():
    a = serial()
    a["copies_per_value"] = 2
    b = serial()
    b.update(name="둘째", copies_per_value=3)
    labels = compile_generated_labels([{}], [7], [a, b])
    assert expanded(labels) == ["0001", "0001", "0002", "0002", "0003", "0003", "0004"]
    assert expanded(labels, "둘째") == ["0001", "0001", "0001", "0002", "0002", "0002", "0003"]


def test_date_expiry_join_and_extract_chained():
    rules = [
        {"name": "제조", "kind": "date", "base": "field", "field": "원본날짜", "format": "YYYY-MM-DD"},
        {"name": "기한", "kind": "date", "base": "field", "field": "제조", "offset_days": 2, "format": "YYMMDD"},
        {"name": "부분", "kind": "slice", "field": "품번", "start": 4, "length": 3},
        {"name": "결합", "kind": "text", "template": "LOT-{{부분}}-{{기한}}"},
        {"name": "작업일", "kind": "date", "offset_days": -1, "format": "YYYYMMDD"},
    ]
    label = compile_generated_labels([{"원본날짜": "20240228", "품번": "ABC001"}], [2], rules, date(2026, 10, 8))[0]
    assert label.copies == 2
    assert label.row["기한"] == "240301"
    assert label.row["결합"] == "LOT-001-240301"
    assert label.row["작업일"] == "20261007"


@pytest.mark.parametrize("rule,match", [
    ({"name": "", "kind": "serial"}, "필드 이름"),
    ({"name": "__cl_id", "kind": "serial"}, "필드 이름"),
    ({"name": "품번", "kind": "serial"}, "DB 열"),
    ({"name": "번호", "kind": "serial", "step": 0}, "변화량"),
    ({"name": "번호", "kind": "serial", "start": -1}, "시작 번호"),
    ({"name": "번호", "kind": "serial", "digits": 31}, "자리수"),
    ({"name": "번호", "kind": "serial", "digits": 1, "start": 10}, "자리수"),
    ({"name": "번호", "kind": "serial", "copies_per_value": False}, "복사 수"),
    ({"name": "번호", "kind": "serial", "reset": "auto"}, "계속 발급"),
    ({"name": "날짜", "kind": "date", "offset_days": "1.5"}, "일수"),
    ({"name": "날짜", "kind": "date", "format": "%s"}, "표시 형식"),
    ({"name": "부분", "kind": "slice", "field": "품번", "start": 0}, "시작 위치"),
    ({"name": "부분", "kind": "slice", "field": "missing"}, "원본 열"),
    ({"name": "번호", "kind": "serial", "digits": 4, "target_field": "품번", "target_length": 3}, "같게 설정"),
    ({"name": "결합", "kind": "text", "template": "{{결합}}"}, "앞에 정의"),
])
def test_invalid_rules_block(rule, match):
    with pytest.raises(ValueError, match=match):
        validate_value_rules([rule], ("품번",))


def test_future_reference_and_duplicates_block():
    with pytest.raises(ValueError, match="앞에 정의"):
        validate_value_rules([{"name": "결합", "kind": "text", "template": "{{번호}}"}, serial()])
    with pytest.raises(ValueError, match="중복"):
        validate_value_rules([serial(), serial()])


@pytest.mark.parametrize("raw", ["20260230", "261008", "garbage", ""])
def test_invalid_date_does_not_generate(raw):
    with pytest.raises(ValueError, match="원본 날짜"):
        compile_generated_labels([{"일자": raw}], [1], [{"name": "날짜", "kind": "date", "base": "field", "field": "일자"}])


def test_missing_bindings_and_out_of_bounds_extract_block():
    with pytest.raises(ValueError, match="원본 열"):
        compile_generated_labels([{}], [1], [{"name": "결합", "kind": "text", "template": "{{누락}}"}])
    with pytest.raises(ValueError, match="시작 위치"):
        compile_generated_labels([{"값": "AB"}], [1], [{"name": "부분", "kind": "slice", "field": "값", "start": 3, "length": 1}])


def test_serial_override_and_full_range_preflight():
    assert expanded(compile_generated_labels([{}], [2], [serial()], start_overrides={"번호": 31})) == ["0031", "0032"]
    with pytest.raises(ValueError, match="마지막 번호"):
        compile_generated_labels([{}], [10**12], [serial()])


def test_unlimited_fixed_quantity_does_not_expand_memory():
    labels = compile_generated_labels([{"품번": "A"}], [10**12], [])
    assert len(labels) == 1 and labels[0].copies == 10**12


def test_iterator_streams_huge_sequence_and_cancellation():
    rule = serial()
    rule["digits"] = 15
    stream = iter_generated_labels([{}], [10**12], [rule])
    assert next(stream).row["번호"] == "000000000000001"
    assert next(stream).row["번호"] == "000000000000002"
    with pytest.raises(ValueGenerationCancelled):
        compile_generated_labels([{}], [3], [serial()], cancel_check=lambda: True)


@pytest.mark.parametrize("qty", [0, -1, True, 1.5, "x"])
def test_invalid_quantities(qty):
    with pytest.raises(ValueError, match="인쇄 매수"):
        compile_generated_labels([{}], [qty], [])


def test_job_date_explicit_timezone_and_validation():
    assert isinstance(job_date_value(), date)
    assert job_date_value("2026-10-08") == date(2026, 10, 8)
    with pytest.raises(ValueError):
        job_date_value(datetime(2026, 10, 8))
