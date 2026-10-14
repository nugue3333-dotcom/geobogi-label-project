"""Send immutable prepared jobs without accessing Tk from a worker."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Event

from .print_progress import PrintProgress


@dataclass(frozen=True)
class PrintSendResult:
    sent_jobs: int
    sent_labels: int
    error: Exception | None
    cancelled: bool


def send_prepared_jobs(jobs: list[bytes], counts: list[int], progress: PrintProgress,
                       sender: Callable[[bytes], None], cancel: Event,
                       notify: Callable[[int, int], None] | None = None) -> PrintSendResult:
    sent = labels = 0
    for index in list(progress.pending_indexes):
        if cancel.is_set():
            break
        progress.mark_sending(index)
        try:
            sender(jobs[index - 1])
        except Exception as exc:
            # A failed send may already have reached the device in part.
            # Preserve UNKNOWN until the user checks the physical output.
            return PrintSendResult(sent, labels, exc, cancel.is_set())
        progress.mark_sent(index)
        sent += 1
        labels += counts[index - 1]
        if notify is not None:
            notify(sent, labels)
    return PrintSendResult(sent, labels, None, cancel.is_set())
