from __future__ import annotations

import json

import pytest

from barcode_label_automation.print_progress import (
    PENDING,
    SENT,
    UNKNOWN,
    NewPrintJobRequired,
    PrintProgress,
    PrintProgressError,
)


def test_progress_persists_sent_unknown_and_pending_atomically(tmp_path):
    path = tmp_path / "out" / "print_progress.json"
    progress = PrintProgress.open_for_job(path, [b"A", b"B", b"C"], "utf-8", {"source": "test"})

    progress.mark_sending(1)
    progress.mark_sent(1)
    progress.mark_sending(2)

    reloaded = PrintProgress.load(path)
    assert [reloaded.status(index) for index in (1, 2, 3)] == [SENT, UNKNOWN, PENDING]
    assert list(path.parent.glob(".*.tmp")) == []
    assert "A" not in path.read_text(encoding="utf-8")


def test_different_job_requires_explicit_reset(tmp_path):
    path = tmp_path / "out" / "print_progress.json"
    original = PrintProgress.open_for_job(path, [b"A"], "utf-8", {"source": "test"})
    original.mark_sending(1)
    original.mark_sent(1)

    with pytest.raises(NewPrintJobRequired):
        PrintProgress.open_for_job(path, [b"B"], "utf-8", {"source": "test"})

    reset = PrintProgress.open_for_job(path, [b"B"], "utf-8", {"source": "test"}, reset=True)
    assert reset.pending_indexes == [1]
    assert reset.sent_indexes == []


def test_completed_same_job_starts_a_fresh_print_job(tmp_path):
    path = tmp_path / "out" / "print_progress.json"
    first = PrintProgress.open_for_job(path, [b"A"], "utf-8", {"source": "test"})
    first.mark_sending(1)
    first.mark_sent(1)

    second = PrintProgress.open_for_job(path, [b"A"], "utf-8", {"source": "test"})

    assert second.pending_indexes == [1]
    assert second.sent_indexes == []
    assert second.unknown_indexes == []
    assert second.job_fingerprint == first.job_fingerprint
    assert second._data["created_at"] != first._data["created_at"]


def test_corrupt_sidecar_blocks_instead_of_silently_resetting(tmp_path):
    path = tmp_path / "print_progress.json"
    path.write_text(json.dumps({"version": 1, "job_fingerprint": "bad", "items": []}), encoding="utf-8")

    with pytest.raises(PrintProgressError):
        PrintProgress.open_for_job(path, [b"A"], "utf-8", {"source": "test"})
