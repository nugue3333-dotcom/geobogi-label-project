"""Atomic value snapshots and serial reservations independent of printer transport."""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from .value_rules import (
    SERIAL_ALPHABETS, GeneratedLabel, _format_serial, _serial_index,
    compile_generated_labels, job_date_value, validate_value_rules,
)
from .print_quantity import parse_print_quantity


@dataclass(frozen=True)
class ValueJob:
    snapshot_id: str
    labels: list[GeneratedLabel]
    job_date: str
    template_key: str
    context: dict[str, object] = field(default_factory=dict)

    @property
    def request_key(self) -> str:
        return str(self.context.get("request_key", ""))


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sequence_key(template_key: str, name: str) -> str:
    return _digest([template_key, name])


def _legacy_rule_digest(rule: Mapping[str, object]) -> str:
    """Match ledgers written before direction/alphabet/partial-target defaults existed."""
    legacy = {key: value for key, value in rule.items() if key not in {"alphabet", "direction", "preserve_width", "target_field", "target_start", "target_length"}}
    return _digest(legacy)


def effective_job_rules(rules: Sequence[Mapping[str, object]], copies_per_serial: int | None = None) -> list[dict[str, object]]:
    """Apply a print-job copy count without changing saved serialization rules."""
    effective = [dict(rule) for rule in rules]
    if copies_per_serial is None:
        return effective
    copies = parse_print_quantity(copies_per_serial)
    serials = [rule for rule in effective if rule.get("kind") == "serial"]
    if not serials:
        raise ValueError("번호당 매수는 일련화가 설정된 도안에서만 사용할 수 있습니다.")
    if len({parse_print_quantity(rule.get("copies_per_value", 1)) for rule in serials}) > 1:
        raise ValueError("이 도안의 일련번호마다 반복 간격이 다릅니다. 기존 설정을 확인한 뒤 출력하세요.")
    for rule in serials:
        rule["copies_per_value"] = copies
    return effective


def validate_ledger_bytes(content: bytes) -> dict[str, object]:
    """Validate backup bytes without creating files or changing issued numbers."""
    try:
        stored = json.loads(content.decode("utf-8"))
        if not isinstance(stored, dict):
            raise ValueError("기록 형식 오류")
        checksum = stored.pop("checksum", None)
        if checksum != _digest(stored):
            raise ValueError("무결성 검사 오류")
        if stored.get("version") != 1 or not isinstance(stored.get("sequences"), dict) or not isinstance(stored.get("jobs"), dict):
            raise ValueError("기록 버전/형식 오류")
        for key, item in stored["sequences"].items():
            if not isinstance(key, str) or len(key) != 64:
                raise ValueError("발급 키 오류")
            if not isinstance(item, dict) or isinstance(item.get("next"), bool) or not isinstance(item.get("next"), int):
                raise ValueError("발급 번호 오류")
            if not isinstance(item.get("rule_digest"), str) or len(item["rule_digest"]) != 64:
                raise ValueError("발급 규칙 오류")
        for snapshot_id, record in stored["jobs"].items():
            job = ValueJobStore._job(record)
            if job.snapshot_id != snapshot_id or len(snapshot_id) != 32:
                raise ValueError("작업 식별값 오류")
        return stored
    except (UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("값 발급 기록을 안전하게 읽을 수 없습니다. 자동 초기화하지 않습니다. 백업 복원 또는 지원 점검이 필요합니다.") from exc


def read_ledger(path: Path) -> dict[str, object]:
    """Read and validate an existing ledger, including all immutable snapshots."""
    try:
        return validate_ledger_bytes(Path(path).read_bytes())
    except OSError as exc:
        raise ValueError("값 발급 기록 파일을 읽지 못했습니다. 자동 초기화하지 않습니다.") from exc


class ValueJobStore:
    """One ledger transaction stores both issued ranges and immutable job values.

    Reserved numbers are never returned automatically after a failed/cancelled
    print. Resuming/reprinting loads the original snapshot; transport acknowledgement
    remains the responsibility of PrintProgress, not this ledger.
    """

    def __init__(self, base_dir: Path):
        self.directory = Path(base_dir) / "out" / "value_jobs"
        self.path = self.directory / "ledger.json"
        self.lock_path = self.directory / "ledger.lock"

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"version": 1, "sequences": {}, "jobs": {}}
        return read_ledger(self.path)

    @contextmanager
    def exclusive_access(self):
        """Guard backup/restore with the same lock used by live allocation."""
        with self._locked():
            yield

    @contextmanager
    def _locked(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ValueError("다른 화면에서 번호를 발급 중입니다. 작업을 완료한 후 다시 시도하세요. 비정상 종료 후 남은 잠금은 지원 점검으로 해제하세요.") from exc
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(str(os.getpid()))
                stream.flush()
                os.fsync(stream.fileno())
            yield
        finally:
            self.lock_path.unlink(missing_ok=True)

    def _save(self, ledger: dict[str, object]) -> None:
        payload = dict(ledger)
        payload["checksum"] = _digest(ledger)
        temporary = self.directory / f".ledger.{uuid4().hex}.tmp"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            raise ValueError("번호와 출력 값을 저장하지 못했습니다. 저장되지 않은 작업을 프린터로 전송하지 마세요.") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _overrides(self, ledger: Mapping[str, object], template_key: str, rules: Sequence[Mapping[str, object]]) -> dict[str, int | str]:
        output: dict[str, int | str] = {}
        for rule in rules:
            if rule["kind"] != "serial" or rule["reset"] != "continue":
                continue
            name = str(rule["name"])
            recorded = ledger["sequences"].get(_sequence_key(template_key, name))
            if recorded is None:
                output[name] = rule["start"]  # type: ignore[assignment]
            else:
                if recorded["rule_digest"] not in (_digest(rule), _legacy_rule_digest(rule)):
                    raise ValueError(f"{name}: 계속 발급 규칙이 이전 기록과 다릅니다. 규칙을 되돌리거나 번호 초기화를 명시적으로 확인하세요.")
                alphabet = SERIAL_ALPHABETS[str(rule["alphabet"])]
                output[name] = (
                    int(recorded["next"]) if str(rule["alphabet"]) == "numeric"
                    else _format_serial(int(recorded["next"]), alphabet, int(rule["digits"]), name, bool(rule["preserve_width"]))
                )
        return output

    def peek_start_overrides(self, template_key: str, rules: Sequence[Mapping[str, object]]) -> dict[str, int | str]:
        """Read only: neither creates storage nor consumes a serial."""
        return self._overrides(self._load(), str(template_key), validate_value_rules(rules))

    def prepare_job(
        self, rows: Sequence[Mapping[str, object]], quantities: Sequence[int], rules: Sequence[Mapping[str, object]],
        *, template_key: str, job_date: date | str | None = None, context: Mapping[str, object] | None = None,
        cancel_check: Callable[[], bool] | None = None, copies_per_serial: int | None = None,
    ) -> ValueJob:
        """Call only after explicit print confirmation; reserve and persist atomically."""
        if not str(template_key).strip():
            raise ValueError("번호 발급을 위해 도안 식별값이 필요합니다.")
        normalized = validate_value_rules(rules, tuple(dict.fromkeys(str(key) for row in rows for key in row)))
        effective = effective_job_rules(normalized, copies_per_serial)
        fixed_date = job_date_value(job_date)
        with self._locked():
            ledger = self._load()
            overrides = self._overrides(ledger, str(template_key), normalized)
            labels = compile_generated_labels(rows, quantities, effective, fixed_date, overrides, cancel_check=cancel_check)
            if not labels:
                raise ValueError("번호를 발급할 출력 대상이 없습니다.")
            total = sum(label.copies for label in labels)
            for rule in normalized:
                if rule["kind"] == "serial" and rule["reset"] == "continue":
                    name = str(rule["name"])
                    alphabet = SERIAL_ALPHABETS[str(rule["alphabet"])]
                    start_value = overrides.get(name, rule["start"])
                    start_index = _serial_index(start_value, alphabet, name)
                    copies = int(copies_per_serial) if copies_per_serial is not None else int(rule["copies_per_value"])
                    # A partially used copy group is still issued; unused copies
                    # are never reused by a later job without explicit reprinting.
                    direction = 1 if rule["direction"] == "up" else -1
                    next_value = start_index + direction * ((total + copies - 1) // copies) * int(rule["step"])
                    ledger["sequences"][_sequence_key(str(template_key), name)] = {
                        "next": next_value, "rule_digest": _digest(rule),
                    }
            snapshot_id = uuid4().hex
            record = {
                "snapshot_id": snapshot_id, "template_key": str(template_key), "job_date": fixed_date.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(), "rules": normalized,
                "context": dict(context or {}), "start_overrides": overrides,
                "labels": [{"row": label.row, "copies": label.copies} for label in labels],
            }
            if copies_per_serial is not None:
                record["copies_per_serial"] = parse_print_quantity(copies_per_serial)
            record["digest"] = _digest(record)
            ledger["jobs"][snapshot_id] = record
            self._save(ledger)
        return ValueJob(snapshot_id, labels, fixed_date.isoformat(), str(template_key), dict(context or {}))

    @staticmethod
    def _job(record: object) -> ValueJob:
        if not isinstance(record, dict):
            raise ValueError("저장한 값 생성 작업을 찾을 수 없습니다.")
        payload = dict(record)
        checksum = payload.pop("digest", None)
        if checksum != _digest(payload):
            raise ValueError("저장한 출력 값의 무결성을 확인할 수 없습니다. 자동 재생성하지 않습니다.")
        raw_labels = record.get("labels")
        if not isinstance(raw_labels, list) or not raw_labels:
            raise ValueError("저장한 출력 값이 비어 있습니다.")
        labels = []
        for label in raw_labels:
            if not isinstance(label, dict) or not isinstance(label.get("row"), dict) or isinstance(label.get("copies"), bool) or not isinstance(label.get("copies"), int) or label["copies"] < 1:
                raise ValueError("저장한 출력 값의 형식이 올바르지 않습니다.")
            if any(not isinstance(key, str) or not isinstance(value, str) for key, value in label["row"].items()):
                raise ValueError("저장한 출력 데이터의 형식이 올바르지 않습니다.")
            labels.append(GeneratedLabel(dict(label["row"]), label["copies"]))
        job_date_value(str(record["job_date"]))
        if not isinstance(record.get("context"), dict):
            raise ValueError("저장한 작업 맥락의 형식이 올바르지 않습니다.")
        return ValueJob(str(record["snapshot_id"]), labels, str(record["job_date"]), str(record["template_key"]), dict(record["context"]))

    def load_job(self, snapshot_id: str) -> ValueJob:
        return self._job(self._load()["jobs"].get(str(snapshot_id)))

    def latest_job(self, template_key: str) -> ValueJob | None:
        for record in reversed(list(self._load()["jobs"].values())):
            if isinstance(record, dict) and record.get("template_key") == str(template_key):
                return self._job(record)
        return None

    def reset_sequence(self, template_key: str, field_name: str, *, confirmed: bool = False) -> None:
        if not confirmed:
            raise ValueError("번호 초기화는 이미 발급한 번호와 중복될 수 있습니다. 명시적 확인이 필요합니다.")
        with self._locked():
            ledger = self._load()
            ledger["sequences"].pop(_sequence_key(str(template_key), str(field_name)), None)
            # Job snapshots remain available for explicit reprint/audit.
            self._save(ledger)
