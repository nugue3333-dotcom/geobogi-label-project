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


from dataclasses import dataclass


@dataclass(frozen=True)
class SerialPrintQuantity:
    """Number of distinct serial values and identical labels for each value."""
    serial_numbers: int
    copies_per_serial: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "serial_numbers", parse_print_quantity(self.serial_numbers))
        object.__setattr__(self, "copies_per_serial", parse_print_quantity(self.copies_per_serial))

    @property
    def total_per_target(self) -> int:
        return self.serial_numbers * self.copies_per_serial


def serial_rule_copies(rules: object) -> int | None:
    """Get a common existing interval; never silently replace differing intervals."""
    if not isinstance(rules, (list, tuple)):
        return None
    intervals = {parse_print_quantity(rule.get("copies_per_value", 1))
                 for rule in rules if isinstance(rule, dict) and rule.get("kind") == "serial"}
    if len(intervals) > 1:
        raise ValueError("이 도안의 일련번호마다 반복 간격이 다릅니다. 개체의 일련화 추가 설정에서 간격을 확인한 뒤 인쇄하세요.")
    return next(iter(intervals), None)


def rules_for_serial_job(rules: object, copies_per_serial: int | None) -> list[dict]:
    """Apply a job-only interval on a copy; persistent document rules stay unchanged."""
    from .value_jobs import effective_job_rules
    return effective_job_rules(rules or [], copies_per_serial)



def ask_serial_print_quantity(parent, *, target_count: int = 1,
                              default_serial_numbers: int = 1,
                              default_copies: int = 1) -> SerialPrintQuantity | None:
    """Ask once for N distinct values and C copies per value. No allocation occurs."""
    import tkinter as tk
    from tkinter import ttk, messagebox
    from .ui_tokens import COLORS
    from .ui_window import set_initial_window_size

    target_count = parse_print_quantity(target_count)
    default_serial_numbers = parse_print_quantity(default_serial_numbers)
    default_copies = parse_print_quantity(default_copies)
    dialog = tk.Toplevel(parent)
    dialog.title("일련번호 인쇄 수량")
    dialog.configure(bg=COLORS.surface)
    dialog.transient(parent)
    dialog.resizable(True, True)
    set_initial_window_size(dialog, preferred_width=520, preferred_height=350,
                            minimum_width=400, minimum_height=310)
    footer = ttk.Frame(dialog, style="Surface.TFrame", padding=(18, 12))
    footer.pack(side="bottom", fill="x")
    frame = ttk.Frame(dialog, style="Surface.TFrame", padding=18)
    frame.pack(side="top", fill="both", expand=True)
    frame.columnconfigure(1, weight=1)
    ttk.Label(frame, text="일련번호 인쇄 수량", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))
    numbers = tk.StringVar(dialog, value=str(default_serial_numbers))
    copies = tk.StringVar(dialog, value=str(default_copies))
    summary = tk.StringVar(dialog)
    ttk.Label(frame, text="서로 다른 번호 개수").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=5)
    number_entry = ttk.Entry(frame, textvariable=numbers)
    number_entry.grid(row=1, column=1, sticky="ew", pady=5)
    ttk.Label(frame, text="번호당 매수").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=5)
    copies_entry = ttk.Entry(frame, textvariable=copies)
    copies_entry.grid(row=2, column=1, sticky="ew", pady=5)
    ttk.Label(frame, textvariable=summary, style="Hint.TLabel", justify="left", wraplength=450).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(14, 4))
    result: list[SerialPrintQuantity | None] = [None]

    def refresh(*_args: object) -> None:
        try:
            value = SerialPrintQuantity(parse_print_quantity(numbers.get()), parse_print_quantity(copies.get()))
            summary.set(f"대상 {target_count}건 × 번호 {value.serial_numbers}개 × 번호당 {value.copies_per_serial}장 = 총 {target_count * value.total_per_target}장\n인쇄 시작을 누르면 프린터로 전송합니다.")
        except ValueError:
            summary.set("번호 개수와 번호당 매수는 1 이상의 정수로 입력하세요.")

    def confirm() -> None:
        try:
            result[0] = SerialPrintQuantity(parse_print_quantity(numbers.get()), parse_print_quantity(copies.get()))
        except ValueError:
            messagebox.showwarning("인쇄 수량", "번호 개수와 번호당 매수는 1 이상의 정수로 입력하세요.", parent=dialog)
            return
        dialog.destroy()

    def cancel() -> None:
        dialog.destroy()

    ttk.Button(footer, text="인쇄 시작", command=confirm, style="Primary.TButton").pack(side="right")
    ttk.Button(footer, text="취소", command=cancel, style="Secondary.TButton").pack(side="right", padx=(0, 8))
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.bind("<Escape>", lambda _event: cancel())
    dialog.bind("<Return>", lambda _event: confirm())
    numbers.trace_add("write", refresh); copies.trace_add("write", refresh)
    refresh()
    # Named references permit keyboard-accessibility and GUI smoke checks.
    dialog._serial_numbers_var = numbers
    dialog._serial_copies_var = copies
    dialog._serial_summary_var = summary
    dialog._serial_confirm = confirm
    dialog._serial_cancel = cancel
    number_entry.focus_set(); number_entry.select_range(0, "end")
    dialog.grab_set()
    parent.wait_window(dialog)
    return result[0]
