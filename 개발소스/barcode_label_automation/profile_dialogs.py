"""Small shared dialogs for workbook selection and actionable validation."""
from __future__ import annotations

import csv
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from .job_profile import workbook_sheets, default_sheet
from .ui_tokens import COLORS
from .ui_window import set_initial_window_size


def choose_sheet(parent, path: Path) -> str | None:
    try:
        sheets = workbook_sheets(path)
    except (ValueError, OSError) as exc:
        messagebox.showerror("상품 엑셀 연결", str(exc), parent=parent)
        return None
    if len(sheets) == 1:
        return sheets[0]
    dialog = tk.Toplevel(parent)
    dialog.title("엑셀 시트 선택")
    dialog.transient(parent)
    dialog.grab_set()
    frame = ttk.Frame(dialog, padding=22)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=path.name, style="Title.TLabel").pack(anchor="w")
    ttk.Label(frame, text="상품 데이터가 들어 있는 시트를 선택하세요.", style="Hint.TLabel").pack(anchor="w", pady=8)
    value = tk.StringVar(value=default_sheet(path))
    ttk.Combobox(frame, textvariable=value, values=sheets, state="readonly", width=38).pack(fill="x")
    result = [None]
    def apply():
        result[0] = value.get()
        dialog.destroy()
    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=(18, 0))
    ttk.Button(actions, text="취소", command=dialog.destroy).pack(side="right")
    ttk.Button(actions, text="연결", style="Primary.TButton", command=apply).pack(side="right", padx=8)
    dialog.bind("<Return>", lambda _event: apply())
    dialog.bind("<Escape>", lambda _event: dialog.destroy())
    parent.wait_window(dialog)
    return result[0]


def show_data_issues(parent, issues, count: int, *, navigate=None):
    dialog = tk.Toplevel(parent)
    dialog.title("전체 데이터 검증")
    dialog.configure(bg=COLORS.background)
    dialog.transient(parent)
    set_initial_window_size(dialog, preferred_width=1000, preferred_height=580, minimum_width=640, minimum_height=380)
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(1, weight=1)
    ttk.Label(dialog, text=f"{count}개 출력 데이터 · 수정할 항목 {len(issues)}건", style="Title.TLabel", padding=16).grid(row=0, column=0, sticky="ew")
    body = ttk.Frame(dialog, padding=(16, 0))
    body.grid(row=1, column=0, sticky="nsew")
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)
    tree = ttk.Treeview(body, columns=("row", "element", "name", "message"), show="headings")
    for key, title, width in (("row", "행", 60), ("element", "개체", 60), ("name", "종류", 100), ("message", "원인 · 해결 방법", 700)):
        tree.heading(key, text=title)
        tree.column(key, width=width, minwidth=width if key != "message" else 280, stretch=key == "message", anchor="w")
    yscroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(body, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    for i, issue in enumerate(issues):
        tree.insert("", "end", iid=str(i), values=(issue.row, issue.element, issue.name, issue.message))
    detail = tk.StringVar(value="문제를 선택하면 전체 안내를 볼 수 있습니다." if issues else "현재 데이터와 도안 검증을 통과했습니다. 실제 출력·스캔 확인은 별도입니다.")
    ttk.Label(dialog, textvariable=detail, style="Hint.TLabel", wraplength=900, padding=16).grid(row=2, column=0, sticky="ew")
    def selected_issue():
        selected = tree.selection()
        return issues[int(selected[0])] if selected else None
    def selection(_event=None):
        issue = selected_issue()
        if issue:
            detail.set(f"{issue.row}행 · {issue.element}번 개체: {issue.message}")
    tree.bind("<<TreeviewSelect>>", selection)
    def fix():
        issue = selected_issue()
        if issue and navigate:
            dialog.destroy()
            navigate(issue)
    def export():
        target = filedialog.asksaveasfilename(parent=dialog, defaultextension=".csv", filetypes=[("CSV", "*.csv")], title="검증 결과 저장")
        if target:
            try:
                with open(target, "w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(("행", "개체", "종류", "원인·해결 방법"))
                    writer.writerows((e.row, e.element, e.name, e.message) for e in issues)
            except OSError as exc:
                messagebox.showerror("저장 실패", str(exc), parent=dialog)
    actions = ttk.Frame(dialog, padding=16)
    actions.grid(row=3, column=0, sticky="ew")
    ttk.Button(actions, text="닫기", command=dialog.destroy).pack(side="right")
    if issues:
        ttk.Button(actions, text="검증 목록 저장", command=export).pack(side="left")
        if navigate:
            ttk.Button(actions, text="선택 문제 수정", command=fix, style="Primary.TButton").pack(side="left", padx=8)
        tree.selection_set("0")
        selection()
    dialog.bind("<Escape>", lambda _event: dialog.destroy())
    return dialog
