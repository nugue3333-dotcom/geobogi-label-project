from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

from .errors import BarcodeLabelAutomationError


PROGRESS_FILE_NAME = "print_progress.json"
DESIGNER_PROGRESS_FILE_NAME = "designer_print_progress.json"
PENDING = "pending"
SENT = "sent"
UNKNOWN = "unknown"
VALID_STATUSES = {PENDING, SENT, UNKNOWN}
NEW_JOB_REQUIRED_CODE = "PRINT_PROGRESS_NEW_JOB_REQUIRED"
UNKNOWN_ITEMS_CODE = "PRINT_PROGRESS_UNKNOWN"
TRANSPORT_UNCERTAIN_CODE = "PRINT_PROGRESS_TRANSPORT_UNCERTAIN"


class PrintProgressError(BarcodeLabelAutomationError):
    """Raised when persisted print progress cannot be trusted."""


class NewPrintJobRequired(PrintProgressError):
    def __init__(self) -> None:
        super().__init__(
            f"{NEW_JOB_REQUIRED_CODE}: a different print job is already recorded. "
            "Start a new job only after explicit confirmation."
        )


class UnknownPrintItemsError(PrintProgressError):
    def __init__(self, item_indexes: Iterable[int]) -> None:
        indexes = ", ".join(str(index) for index in item_indexes)
        super().__init__(
            f"{UNKNOWN_ITEMS_CODE}: item(s) {indexes} may already have been output. "
            "Resolve each item as printed or not printed before continuing."
        )


class PrintTransportUncertainError(PrintProgressError):
    def __init__(self, item_index: int, cause: Exception) -> None:
        super().__init__(
            f"{TRANSPORT_UNCERTAIN_CODE}: item {item_index} transport failed and its output state is unknown: {cause}"
        )


def command_bytes(command: str | bytes, encoding: str) -> bytes:
    return command if isinstance(command, bytes) else command.encode(encoding, errors="replace")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _job_definition(commands: Iterable[str | bytes], encoding: str, context: Mapping[str, object]) -> dict[str, Any]:
    command_hashes = [_sha256(command_bytes(command, encoding)) for command in commands]
    item_fingerprints = [
        _sha256(f"{index}:{command_hash}".encode("ascii"))
        for index, command_hash in enumerate(command_hashes, start=1)
    ]
    fingerprint = _sha256(_canonical_json({"context": dict(context), "commands": command_hashes}))
    now = _utc_now()
    return {
        "version": 1,
        "job_fingerprint": fingerprint,
        "created_at": now,
        "updated_at": now,
        "items": [
            {"index": index, "fingerprint": item_fingerprint, "status": PENDING}
            for index, item_fingerprint in enumerate(item_fingerprints, start=1)
        ],
    }


class PrintProgress:
    def __init__(self, path: Path, data: dict[str, Any]) -> None:
        self.path = Path(path)
        self._data = data
        self._validate()

    @classmethod
    def open_for_job(
        cls,
        path: Path,
        commands: Iterable[str | bytes],
        encoding: str,
        context: Mapping[str, object],
        *,
        reset: bool = False,
    ) -> "PrintProgress":
        expected = _job_definition(commands, encoding, context)
        path = Path(path)
        if path.exists() and not reset:
            current = cls.load(path)
            if current.job_fingerprint != expected["job_fingerprint"]:
                raise NewPrintJobRequired()
            expected_items = [item["fingerprint"] for item in expected["items"]]
            if current.item_fingerprints != expected_items:
                raise PrintProgressError("Print progress item fingerprints do not match the recorded job.")
            # A fully completed job represents a previous explicit print action.
            # Start a fresh progress record so pressing Print again sends the
            # same label set instead of silently skipping every item.
            if current.sent_indexes and not current.pending_indexes and not current.unknown_indexes:
                progress = cls(path, expected)
                progress.save()
                return progress
            return current

        progress = cls(path, expected)
        progress.save()
        return progress

    @classmethod
    def load(cls, path: Path) -> "PrintProgress":
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PrintProgressError(f"Could not safely read print progress: {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise PrintProgressError(f"Print progress must contain a JSON object: {path}")
        return cls(path, data)

    @property
    def job_fingerprint(self) -> str:
        return str(self._data["job_fingerprint"])

    @property
    def item_fingerprints(self) -> list[str]:
        return [str(item["fingerprint"]) for item in self._data["items"]]

    def item_indexes(self, status: str) -> list[int]:
        return [int(item["index"]) for item in self._data["items"] if item["status"] == status]

    @property
    def pending_indexes(self) -> list[int]:
        return self.item_indexes(PENDING)

    @property
    def sent_indexes(self) -> list[int]:
        return self.item_indexes(SENT)

    @property
    def unknown_indexes(self) -> list[int]:
        return self.item_indexes(UNKNOWN)

    def status(self, item_index: int) -> str:
        return str(self._item(item_index)["status"])

    def mark_sending(self, item_index: int) -> None:
        if self.status(item_index) != PENDING:
            raise PrintProgressError(f"Only pending item {item_index} can start transport.")
        self._set_status(item_index, UNKNOWN)

    def mark_sent(self, item_index: int) -> None:
        if self.status(item_index) != UNKNOWN:
            raise PrintProgressError(f"Only unknown item {item_index} can be marked sent.")
        self._set_status(item_index, SENT)

    def resolve_unknown(self, item_index: int, *, was_printed: bool) -> None:
        if self.status(item_index) != UNKNOWN:
            raise PrintProgressError(f"Item {item_index} is not awaiting output confirmation.")
        self._set_status(item_index, SENT if was_printed else PENDING)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data["updated_at"] = _utc_now()
        temp_path = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(self._data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
        except OSError as exc:
            raise PrintProgressError(f"Could not atomically save print progress: {self.path}: {exc}") from exc
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _set_status(self, item_index: int, status: str) -> None:
        self._item(item_index)["status"] = status
        self.save()

    def _item(self, item_index: int) -> dict[str, Any]:
        for item in self._data["items"]:
            if item["index"] == item_index:
                return item
        raise PrintProgressError(f"Print progress item {item_index} does not exist.")

    def _validate(self) -> None:
        if self._data.get("version") != 1:
            raise PrintProgressError("Unsupported print progress version.")
        fingerprint = self._data.get("job_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise PrintProgressError("Print progress has an invalid job fingerprint.")
        items = self._data.get("items")
        if not isinstance(items, list):
            raise PrintProgressError("Print progress items are missing.")
        expected_indexes = list(range(1, len(items) + 1))
        indexes: list[int] = []
        for item in items:
            if not isinstance(item, dict):
                raise PrintProgressError("Print progress contains an invalid item.")
            index = item.get("index")
            item_fingerprint = item.get("fingerprint")
            status = item.get("status")
            if not isinstance(index, int):
                raise PrintProgressError("Print progress item index is invalid.")
            if not isinstance(item_fingerprint, str) or len(item_fingerprint) != 64:
                raise PrintProgressError(f"Print progress item {index} fingerprint is invalid.")
            if status not in VALID_STATUSES:
                raise PrintProgressError(f"Print progress item {index} status is invalid.")
            indexes.append(index)
        if indexes != expected_indexes:
            raise PrintProgressError("Print progress item indexes are not contiguous.")
