import json

import pytest

from barcode_label_automation.value_jobs import ValueJobStore, read_ledger, validate_ledger_bytes
from barcode_label_automation.value_jobs import _digest, _sequence_key
from barcode_label_automation.value_rules import ValueGenerationCancelled
from barcode_label_automation.print_progress import PrintProgress


def serial(**kwargs):
    rule = dict(name="번호", kind="serial", start=1, digits=5, step=1, copies_per_value=1, reset="continue")
    rule.update(kwargs)
    return rule


def test_preview_read_does_not_create_or_consume(tmp_path):
    store = ValueJobStore(tmp_path)
    assert store.peek_start_overrides("도안A", [serial()]) == {"번호": 1}
    assert not store.directory.exists()


def test_snapshot_continue_resume_reprint_and_context(tmp_path):
    store = ValueJobStore(tmp_path)
    first = store.prepare_job([{"품번": "001"}], [3], [serial()], template_key="도안A", job_date="2026-10-08", context={"request_key": "abc"})
    assert first.request_key == "abc"
    assert store.peek_start_overrides("도안A", [serial()]) == {"번호": 4}
    saved = store.load_job(first.snapshot_id)
    assert saved == first
    assert saved.labels[0].row["번호"] == "00001"
    assert store.latest_job("도안A").snapshot_id == first.snapshot_id
    second = store.prepare_job([{}], [1], [serial()], template_key="도안A", job_date="2026-10-09")
    assert second.labels[0].row["번호"] == "00004"
    assert store.load_job(first.snapshot_id).labels == first.labels
    assert store.latest_job("missing") is None
    assert not store.lock_path.exists()
    assert not list(store.directory.glob("*.tmp"))


def test_partial_copy_reservation_and_template_isolation(tmp_path):
    store = ValueJobStore(tmp_path)
    rules = [serial(copies_per_value=2)]
    first = store.prepare_job([{}], [3], rules, template_key="A")
    assert [label.copies for label in first.labels] == [2, 1]
    assert store.peek_start_overrides("A", rules) == {"번호": 3}
    assert store.peek_start_overrides("B", rules) == {"번호": 1}


def test_decrement_sequence_continues_and_blocks_underflow(tmp_path):
    store = ValueJobStore(tmp_path)
    rule = serial(start=3, digits=2, direction="down")
    job = store.prepare_job([{}], [2], [rule], template_key="down")
    assert [label.row["번호"] for label in job.labels] == ["03", "02"]
    assert ValueJobStore(tmp_path).peek_start_overrides("down", [rule]) == {"번호": 1}
    store.prepare_job([{}], [1], [rule], template_key="down")
    assert store.peek_start_overrides("down", [rule]) == {"번호": 0}
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="시작 범위보다 작아졌습니다"):
        store.prepare_job([{}], [2], [rule], template_key="down")
    assert store.path.read_bytes() == before


def test_alphabetic_continue_stores_counter_and_returns_formatted_value(tmp_path):
    store = ValueJobStore(tmp_path)
    rule = serial(start="Z", digits=2, alphabet="uppercase")
    job = store.prepare_job([{}], [2], [rule], template_key="alpha")
    assert [label.row["번호"] for label in job.labels] == ["Z", "AA"]
    assert store.peek_start_overrides("alpha", [rule]) == {"번호": "AB"}


@pytest.mark.parametrize(('alphabet', 'start', 'expected', 'next_value'), [
    ('numeric', 9, ['9', '10'], 11),
    ('uppercase', 'Z', ['Z', 'AA'], 'AB'),
])
def test_continue_automatic_width_across_digit_rollover(tmp_path, alphabet, start, expected, next_value):
    store = ValueJobStore(tmp_path)
    rule = serial(start=start, digits=1, alphabet=alphabet, preserve_width=False)
    first = store.prepare_job([{}], [2], [rule], template_key='automatic')
    assert [label.row['번호'] for label in first.labels] == expected
    assert store.peek_start_overrides('automatic', [rule]) == {'번호': next_value}
    second = store.prepare_job([{}], [1], [rule], template_key='automatic')
    assert second.labels[0].row['번호'] == str(next_value)
    assert store.load_job(first.snapshot_id).labels == first.labels


def test_continue_sequence_accepts_pre_direction_ledger_digest(tmp_path):
    store = ValueJobStore(tmp_path)
    rule = serial()
    store.prepare_job([{}], [1], [rule], template_key="legacy")
    ledger = store._load()
    key = _sequence_key("legacy", "번호")
    ledger["sequences"][key]["rule_digest"] = _digest({
        "name": "번호", "kind": "serial", "start": 1, "step": 1,
        "digits": 5, "copies_per_value": 1, "reset": "continue", "prefix": "", "suffix": "",
    })
    store._save(ledger)
    assert store.peek_start_overrides("legacy", [rule]) == {"번호": 2}


def test_job_reset_mode_never_reserves_continue_counter(tmp_path):
    store = ValueJobStore(tmp_path)
    rules = [serial(reset="job")]
    first = store.prepare_job([{}], [2], rules, template_key="A")
    second = store.prepare_job([{}], [2], rules, template_key="A")
    assert first.labels == second.labels
    assert store.peek_start_overrides("A", rules) == {}


def test_changed_continue_rule_requires_confirmed_reset(tmp_path):
    store = ValueJobStore(tmp_path)
    store.prepare_job([{}], [2], [serial()], template_key="A")
    with pytest.raises(ValueError, match="規則|規|규칙"):
        store.peek_start_overrides("A", [serial(step=2)])
    with pytest.raises(ValueError, match="명시적 확인"):
        store.reset_sequence("A", "번호")
    store.reset_sequence("A", "번호", confirmed=True)
    assert store.peek_start_overrides("A", [serial(step=2)]) == {"번호": 1}
    assert store.latest_job("A") is not None


def test_corrupt_ledger_blocks_without_reinitializing(tmp_path):
    store = ValueJobStore(tmp_path)
    store.prepare_job([{}], [2], [serial()], template_key="A")
    original = store.path.read_bytes()
    damaged = json.loads(original)
    damaged["sequences"][next(iter(damaged["sequences"]))]["next"] = 1
    store.path.write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(ValueError, match="자동 초기화하지"):
        store.peek_start_overrides("A", [serial()])


def test_write_failure_does_not_commit_number_or_snapshot(tmp_path, monkeypatch):
    store = ValueJobStore(tmp_path)
    original = store.prepare_job([{}], [2], [serial()], template_key="A")
    before = store.path.read_bytes()
    monkeypatch.setattr("barcode_label_automation.value_jobs.os.replace", lambda *_args: (_ for _ in ()).throw(OSError("blocked")))
    with pytest.raises(ValueError, match="저장하지 못"):
        store.prepare_job([{}], [2], [serial()], template_key="A")
    assert store.path.read_bytes() == before
    assert store.latest_job("A").snapshot_id == original.snapshot_id
    assert not store.lock_path.exists()


def test_generation_cancel_does_not_reserve(tmp_path):
    store = ValueJobStore(tmp_path)
    with pytest.raises(ValueGenerationCancelled):
        store.prepare_job([{}], [100], [serial()], template_key="A", cancel_check=lambda: True)
    assert not store.path.exists()
    assert store.peek_start_overrides("A", [serial()]) == {"번호": 1}
    assert not store.lock_path.exists()


def test_lock_blocks_concurrent_allocation(tmp_path):
    store = ValueJobStore(tmp_path)
    store.directory.mkdir(parents=True)
    store.lock_path.write_text("busy", encoding="utf-8")
    with pytest.raises(ValueError, match="발급 중"):
        store.prepare_job([{}], [1], [serial()], template_key="A")
    assert not store.path.exists()
    assert store.lock_path.exists()


def test_serial_overflow_does_not_reserve(tmp_path):
    store = ValueJobStore(tmp_path)
    with pytest.raises(ValueError, match="자리 범위"):
        store.prepare_job([{}], [100001], [serial()], template_key="A")
    assert not store.path.exists()


def test_date_snapshot_survives_new_jobs_and_reload(tmp_path):
    store = ValueJobStore(tmp_path)
    rules = [{"name": "기한", "kind": "date", "offset_days": 30}]
    first = store.prepare_job([{}], [1], rules, template_key="A", job_date="2026-10-08")
    store.prepare_job([{}], [1], rules, template_key="A", job_date="2026-10-09")
    assert store.load_job(first.snapshot_id).labels[0].row["기한"] == "20261107"


def test_public_backup_validation_and_guard(tmp_path):
    store = ValueJobStore(tmp_path)
    job = store.prepare_job([{}], [1], [serial()], template_key="A")
    with store.exclusive_access():
        assert store.lock_path.exists()
        restored = validate_ledger_bytes(store.path.read_bytes())
        assert job.snapshot_id in restored["jobs"]
        assert read_ledger(store.path) == restored
    assert not store.lock_path.exists()


@pytest.mark.parametrize("content", [b"bad", b"\xff", b"[]", b'{"version":1}'])
def test_invalid_backup_payload_blocks(content):
    with pytest.raises(ValueError, match="안전하게 읽을"):
        validate_ledger_bytes(content)


def test_unfinished_print_resumes_same_snapshot_values_without_reallocation(tmp_path):
    store = ValueJobStore(tmp_path)
    job = store.prepare_job([{}], [3], [serial()], template_key="A", context={"request_key": "same"})
    commands = [label.row["번호"].encode("ascii") for label in job.labels]
    path = tmp_path / "out" / "print_progress.json"
    progress = PrintProgress.open_for_job(path, commands, "ascii", {"value_job": job.snapshot_id})
    progress.mark_sending(1)
    progress.mark_sent(1)
    progress.mark_sending(2)
    reloaded_job = ValueJobStore(tmp_path).load_job(job.snapshot_id)
    same_commands = [label.row["번호"].encode("ascii") for label in reloaded_job.labels]
    resumed = PrintProgress.open_for_job(path, same_commands, "ascii", {"value_job": reloaded_job.snapshot_id})
    assert resumed.sent_indexes == [1]
    assert resumed.unknown_indexes == [2]
    assert resumed.pending_indexes == [3]
    assert same_commands == [b"00001", b"00002", b"00003"]
    assert store.peek_start_overrides("A", [serial()]) == {"번호": 4}
