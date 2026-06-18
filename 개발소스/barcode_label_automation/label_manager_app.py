from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .data_store import (
    DB_HEADERS,
    LABEL_HEADERS,
    load_db_rows,
    load_label_rows,
    lookup_barcode,
    save_db_rows,
    save_label_rows,
)
from .ui_tokens import COLORS, SPACING, TYPOGRAPHY


SELECT_HEADER = "__selected__"
LABEL_DISPLAY_HEADERS = (SELECT_HEADER, *LABEL_HEADERS)
CHECKED = "☑"
UNCHECKED = "☐"

COLUMN_LABELS = {
    SELECT_HEADER: "선택",
    "item_code": "품목 코드",
    "item_name": "품목명",
    "barcode": "바코드",
    "lot_no": "LOT 번호",
    "qty": "수량",
    "print_qty": "출력 매수",
}


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


class LabelManagerApp(tk.Tk):
    def __init__(self, base_dir: Path) -> None:
        super().__init__()
        self.base_dir = base_dir
        self.queue_path = base_dir / "print_queue.xlsx"
        self.db_path = base_dir / "barcode_db.xlsx"
        self.db_upload_dir = base_dir / "db"
        self.config_path = base_dir / "config.ini"
        self.print_exe = base_dir / "print_labels.exe"
        self.settings_exe = _first_existing(base_dir / "\ud504\ub9b0\ud130\uc124\uc815.exe", base_dir / "printer_settings.exe")
        self.label_rows: list[dict[str, str]] = []
        self.db_rows: list[dict[str, str]] = []
        self.selected_label_indexes: set[int] = set()
        self.active_editor: tk.Entry | None = None
        self.scan_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self.title("\ub77c\ubca8 \ucd9c\ub825 \uad00\ub9ac")
        self.geometry("1240x760")
        self.minsize(1080, 680)
        self.configure(bg=COLORS.background)

        self._configure_style()
        self._build_ui()
        self.load_files()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=TYPOGRAPHY.body, background=COLORS.background)
        style.configure("TLabel", font=TYPOGRAPHY.body, foreground=COLORS.text_primary, background=COLORS.surface)
        style.configure("App.TFrame", background=COLORS.background)
        style.configure("Surface.TFrame", background=COLORS.surface)
        style.configure("Header.TFrame", background=COLORS.panel)
        style.configure("Toolbar.TFrame", background=COLORS.surface)
        style.configure(
            "Brand.TLabel",
            font=TYPOGRAPHY.caption,
            foreground="#ffffff",
            background=COLORS.primary,
            padding=(9, 3),
        )
        style.configure(
            "Title.TLabel",
            font=TYPOGRAPHY.page_title,
            foreground=COLORS.text_primary,
            background=COLORS.surface,
        )
        style.configure(
            "HeaderTitle.TLabel",
            font=TYPOGRAPHY.page_title,
            foreground=COLORS.text_primary,
            background=COLORS.panel,
        )
        style.configure(
            "Subtitle.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.text_secondary,
            background=COLORS.panel,
        )
        style.configure(
            "ToolbarStatus.TLabel",
            font=TYPOGRAPHY.caption,
            foreground=COLORS.accent,
            background=COLORS.accent_soft,
            padding=(12, 5),
        )
        style.configure("Hint.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.background)
        style.configure("Status.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.background)
        style.configure(
            "Primary.TButton",
            font=TYPOGRAPHY.button_text,
            foreground="#ffffff",
            background=COLORS.primary,
            bordercolor=COLORS.primary,
            focusthickness=2,
            focuscolor=COLORS.primary,
            padding=(14, 7),
            relief="flat",
            borderwidth=1,
        )
        style.map("Primary.TButton", background=[("active", COLORS.primary_hover), ("pressed", COLORS.primary_hover)])
        style.configure(
            "Secondary.TButton",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface,
            bordercolor=COLORS.border_strong,
            padding=(14, 7),
            relief="flat",
            borderwidth=1,
        )
        style.map("Secondary.TButton", background=[("active", COLORS.surface_muted)])
        style.configure(
            "Danger.TButton",
            font=TYPOGRAPHY.button_text,
            foreground="#ffffff",
            background=COLORS.danger,
            bordercolor=COLORS.danger,
            padding=(14, 7),
            relief="flat",
            borderwidth=1,
        )
        style.map("Danger.TButton", background=[("active", COLORS.primary_hover)])
        style.configure(
            "TNotebook",
            background=COLORS.background,
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            font=TYPOGRAPHY.button_text,
            padding=(18, 9),
            background=COLORS.surface_muted,
            foreground=COLORS.text_secondary,
        )
        style.map("TNotebook.Tab", background=[("selected", COLORS.accent_soft)], foreground=[("selected", COLORS.accent)])
        style.configure(
            "Treeview",
            rowheight=31,
            fieldbackground=COLORS.surface,
            background=COLORS.surface,
            foreground=COLORS.text_primary,
            bordercolor=COLORS.border,
            font=TYPOGRAPHY.table_text,
        )
        style.map("Treeview", background=[("selected", COLORS.graphite)], foreground=[("selected", "#ffffff")])
        style.configure(
            "Treeview.Heading",
            font=TYPOGRAPHY.button_text,
            foreground=COLORS.text_primary,
            background=COLORS.surface_muted,
            bordercolor=COLORS.border,
            padding=(8, 7),
        )
        style.configure("TEntry", padding=(10, 6), fieldbackground=COLORS.surface, bordercolor=COLORS.border_strong)

    def _build_ui(self) -> None:
        top = ttk.Frame(self, style="Header.TFrame", padding=(SPACING.page_padding, 14))
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        title_block = ttk.Frame(top, style="Header.TFrame")
        title_block.grid(row=0, column=0, sticky="w", padx=(0, 26))
        ttk.Label(title_block, text="거복이의꿈", style="Brand.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(title_block, text="\ub77c\ubca8 \ucd9c\ub825 \uad00\ub9ac", style="HeaderTitle.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(
            title_block,
            text="\ucd9c\ub825 \ubaa9\ub85d, \ubc14\ucf54\ub4dc DB, \ud504\ub9b0\ud130 \uc124\uc815",
            style="Subtitle.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

        scan_group = ttk.Frame(top, style="Header.TFrame")
        scan_group.grid(row=0, column=1, sticky="ew")
        scan_group.columnconfigure(1, weight=1)
        ttk.Label(scan_group, text="DB \uc0c1\ud488\uc870\ud68c", style="Subtitle.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10))
        scan_box = ttk.Entry(scan_group, textvariable=self.scan_var, font=("Malgun Gothic", 11))
        scan_box.grid(row=0, column=1, sticky="ew", ipady=4)
        scan_box.bind("<Return>", self.scan_barcode)
        ttk.Button(scan_group, text="\uc870\ud68c", command=self.scan_barcode, style="Secondary.TButton").grid(row=0, column=2, padx=(8, 0))

        separator = tk.Frame(self, bg=COLORS.border, height=1)
        separator.pack(fill="x")

        body = ttk.Frame(self, style="App.TFrame", padding=SPACING.page_padding)
        body.pack(fill="both", expand=True)
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)

        action_card = tk.Frame(body, bg=COLORS.surface, highlightbackground=COLORS.border, highlightthickness=1, bd=0)
        action_card.grid(row=0, column=0, sticky="ew", pady=(0, SPACING.section_gap))
        action_card.columnconfigure(0, weight=1)
        tk.Frame(action_card, bg=COLORS.accent, height=3).grid(row=0, column=0, sticky="ew")
        actions = ttk.Frame(action_card, style="Toolbar.TFrame", padding=(14, 12))
        actions.grid(row=1, column=0, sticky="ew")
        for col in range(7):
            actions.columnconfigure(col, weight=0)
        ttk.Button(actions, text="\uc804\uccb4 \uc120\ud0dd", command=self.select_all_labels, style="Secondary.TButton").grid(row=0, column=0, padx=(0, 5))
        ttk.Button(actions, text="\uc120\ud0dd \ud574\uc81c", command=self.clear_label_selection, style="Secondary.TButton").grid(row=0, column=1, padx=5)
        ttk.Button(actions, text="\uc120\ud0dd \ud56d\ubaa9 \ucd9c\ub825", command=lambda: self.run_print_job("--print", selected_only=True), style="Primary.TButton").grid(row=0, column=2, padx=5)
        ttk.Button(actions, text="DB \uc5d1\uc140 \uc5c5\ub85c\ub4dc", command=self.upload_db_excel, style="Secondary.TButton").grid(row=0, column=3, padx=5)
        ttk.Button(actions, text="\ub77c\ubca8 \uc804\uccb4 \ucd9c\ub825", command=lambda: self.run_print_job("--print"), style="Secondary.TButton").grid(row=0, column=4, padx=5)
        actions.columnconfigure(5, weight=1)
        ttk.Label(actions, textvariable=self.status_var, style="ToolbarStatus.TLabel").grid(row=0, column=5, columnspan=2, sticky="e", padx=(16, 0))
        ttk.Button(actions, text="\uc0c8 \ud589", command=self.add_row, style="Secondary.TButton").grid(row=1, column=0, padx=(0, 5), pady=(7, 0))
        ttk.Button(actions, text="\uc120\ud0dd \uc0ad\uc81c", command=self.delete_selected, style="Danger.TButton").grid(row=1, column=1, padx=5, pady=(7, 0))
        ttk.Button(actions, text="\uc800\uc7a5", command=self.save_files, style="Secondary.TButton").grid(row=1, column=2, padx=5, pady=(7, 0))
        ttk.Button(actions, text="\ucd9c\ub825 \ud30c\uc77c \ud655\uc778", command=lambda: self.run_print_job("--dry-run"), style="Secondary.TButton").grid(row=1, column=3, padx=5, pady=(7, 0))
        ttk.Button(actions, text="\ud504\ub9b0\ud130 \uc124\uc815", command=self.open_settings, style="Secondary.TButton").grid(row=1, column=4, padx=5, pady=(7, 0))
        ttk.Button(actions, text="\ucd9c\ub825\ud3f4\ub354", command=lambda: self.open_path(self.base_dir / "out"), style="Secondary.TButton").grid(row=1, column=5, padx=5, pady=(7, 0), sticky="w")

        self.tabs = ttk.Notebook(body)
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.labels_tree = self._create_table(self.tabs, LABEL_DISPLAY_HEADERS, "\ucd9c\ub825 \ubaa9\ub85d")
        self.db_tree = self._create_table(self.tabs, DB_HEADERS, "\ubc14\ucf54\ub4dc DB")

        ttk.Label(
            body,
            text="\ucd9c\ub825 \ubaa9\ub85d\uc740 DB \ub0b4\uc6a9 \uc804\uccb4\ub97c \ubd88\ub7ec\uc635\ub2c8\ub2e4. \uc88c\uce21 \uc120\ud0dd\uce78\uc744 \uccb4\ud06c\ud55c \ub4a4 \uc120\ud0dd \ud56d\ubaa9 \ucd9c\ub825\uc744 \ub204\ub974\uba74 \uccb4\ud06c\ub41c \ub77c\ubca8\ub9cc \ucd9c\ub825\ub429\ub2c8\ub2e4.",
            style="Hint.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _create_table(self, tabs: ttk.Notebook, headers: tuple[str, ...], title: str) -> ttk.Treeview:
        frame = ttk.Frame(tabs, padding=SPACING.form_gap, style="Surface.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=headers, show="headings", selectmode="browse")
        for header in headers:
            if header == SELECT_HEADER:
                width = 58
                minwidth = 52
                stretch = False
            elif header in {"item_name", "barcode"}:
                width = 250
                minwidth = 120
                stretch = True
            else:
                width = 140
                minwidth = 90
                stretch = True
            tree.heading(header, text=COLUMN_LABELS.get(header, header))
            tree.column(header, width=width, minwidth=minwidth, stretch=stretch, anchor="center" if header == SELECT_HEADER else "w")
        tree.tag_configure("checked", background=COLORS.accent_soft)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        if headers and headers[0] == SELECT_HEADER:
            tree.bind("<Button-1>", self._handle_label_click)
        tree.bind("<Double-1>", lambda event, active_tree=tree: self.begin_edit(active_tree, event))
        tree.bind("<Return>", lambda event, active_tree=tree: self.begin_edit(active_tree, event))
        tabs.add(frame, text=title)
        return tree

    def load_files(self) -> None:
        try:
            self.db_rows = load_db_rows(self.db_path)
            self._sync_labels_from_db(preserve_selection=False)
            save_label_rows(self.queue_path, self.label_rows)
        except Exception as exc:
            messagebox.showerror("\ub370\uc774\ud130 \uc77d\uae30 \uc2e4\ud328", str(exc))
            return
        self.refresh_tables()
        self.status_var.set(f"DB {len(self.db_rows)}건을 출력 목록으로 불러왔습니다.")

    def refresh_tables(self) -> None:
        _fill_tree(self.labels_tree, LABEL_DISPLAY_HEADERS, self.label_rows, self.selected_label_indexes)
        _fill_tree(self.db_tree, DB_HEADERS, self.db_rows)

    def add_row(self) -> None:
        if self.tabs.index(self.tabs.select()) == 0:
            self.label_rows.append({header: "" for header in LABEL_HEADERS})
            self.refresh_tables()
            self._select_last(self.labels_tree)
        else:
            self.db_rows.append({header: "" for header in DB_HEADERS})
            self._sync_labels_from_db(preserve_selection=True)
            self.refresh_tables()
            self._select_last(self.db_tree)

    def delete_selected(self) -> None:
        tree, rows = self._active_tree_and_rows()
        selected = tree.selection()
        if tree is self.labels_tree:
            focused_index = tree.index(selected[0]) if selected else None
            deleted_count = _delete_label_rows(self.label_rows, self.selected_label_indexes, focused_index)
            if not deleted_count:
                return
            self.refresh_tables()
            self.status_var.set(f"{deleted_count}건 삭제했습니다.")
            return
        if not selected:
            return
        index = tree.index(selected[0])
        del rows[index]
        self._sync_labels_from_db(preserve_selection=True)
        self.refresh_tables()
        self.status_var.set("1건 삭제했습니다.")

    def save_files(self) -> None:
        try:
            save_label_rows(self.queue_path, self.label_rows)
            save_db_rows(self.db_path, self.db_rows)
        except Exception as exc:
            messagebox.showerror("\uc800\uc7a5 \uc2e4\ud328", str(exc))
            return
        self.status_var.set("\uc800\uc7a5\ub418\uc5c8\uc2b5\ub2c8\ub2e4.")

    def upload_db_excel(self) -> None:
        source_name = filedialog.askopenfilename(
            parent=self,
            title="DB 엑셀 업로드",
            filetypes=[
                ("Excel 통합 문서", "*.xlsx *.xlsm"),
                ("모든 파일", "*.*"),
            ],
        )
        if not source_name:
            return

        source = Path(source_name)
        try:
            self.db_upload_dir.mkdir(parents=True, exist_ok=True)
            destination = self.db_upload_dir / source.name
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            self.db_rows = load_db_rows(destination)
            self._sync_labels_from_db(preserve_selection=False)
            save_db_rows(self.db_path, self.db_rows)
            save_label_rows(self.queue_path, self.label_rows)
        except Exception as exc:
            messagebox.showerror("DB 업로드 실패", str(exc))
            return

        self.refresh_tables()
        self.tabs.select(self.tabs.tabs()[0])
        self.status_var.set(f"DB 업로드 완료: {len(self.db_rows)}건 / 저장 위치: db\\{destination.name}")

    def scan_barcode(self, event: tk.Event | None = None) -> None:
        barcode = self.scan_var.get().strip()
        if not barcode:
            return
        applied_index = self.apply_barcode_to_label_row(barcode, clear_selection_after=True)
        if applied_index is not None:
            self.select_db_row_by_barcode(barcode, show_tab=False, show_warning=False)
            self.tabs.select(self.tabs.tabs()[0])
        self.scan_var.set("")

    def select_db_row_by_barcode(self, barcode: str, show_tab: bool = True, show_warning: bool = True) -> bool:
        target = barcode.strip()
        for index, row in enumerate(self.db_rows):
            if str(row.get("barcode", "")).strip() == target:
                if show_tab:
                    self.tabs.select(self.tabs.tabs()[1])
                self._select_index(self.db_tree, index)
                item_name = str(row.get("item_name", "")).strip()
                self.status_var.set(f"DB \uc870\ud68c \uc644\ub8cc: {target} / {item_name}")
                return True
        if show_warning:
            messagebox.showwarning("\ubc14\ucf54\ub4dc DB", "DB\uc5d0 \uc5c6\ub294 \ubc14\ucf54\ub4dc \uc785\ub2c8\ub2e4.")
        return False

    def apply_barcode_to_label_row(
        self,
        barcode: str,
        row_index: int | None = None,
        *,
        clear_selection_after: bool = False,
    ) -> int | None:
        result = lookup_barcode(self.db_rows, barcode)
        if result is None:
            messagebox.showwarning("\ubc14\ucf54\ub4dc DB", "DB\uc5d0 \uc5c6\ub294 \ubc14\ucf54\ub4dc \uc785\ub2c8\ub2e4.")
            return None
        if row_index is None:
            row_index = self._selected_label_index_for_scan()
        row_index, appended = _ensure_label_row_index(self.label_rows, row_index)
        self.label_rows[row_index].update(
            {
                "item_code": result.item_code,
                "item_name": result.item_name,
                "barcode": result.barcode,
                "lot_no": result.lot_no,
                "qty": result.qty,
                "print_qty": result.print_qty,
            }
        )
        self.refresh_tables()
        if clear_selection_after:
            self._see_index(self.labels_tree, row_index)
            self.labels_tree.selection_remove(self.labels_tree.selection())
        else:
            self._select_index(self.labels_tree, row_index)
        action = "\ucd9c\ub825 \ubaa9\ub85d\uc5d0 \ucd94\uac00" if appended else "\ucd9c\ub825 \ud589 \uc790\ub3d9 \ucc44\uc6c0"
        self.status_var.set(f"{action}: {result.barcode} / {result.item_name}")
        return row_index

    def begin_edit(self, tree: ttk.Treeview, event: tk.Event) -> None:
        if self.active_editor is not None:
            self.active_editor.destroy()
            self.active_editor = None
        item = tree.identify_row(event.y) if hasattr(event, "y") else (tree.selection()[0] if tree.selection() else "")
        column_id = tree.identify_column(event.x) if hasattr(event, "x") else "#1"
        if not item or column_id == "#0":
            return
        column_index = int(column_id.replace("#", "")) - 1
        headers = LABEL_DISPLAY_HEADERS if tree is self.labels_tree else DB_HEADERS
        if column_index < 0 or column_index >= len(headers):
            return
        header = headers[column_index]
        if header == SELECT_HEADER:
            self._toggle_label_index(tree.index(item))
            return
        bbox = tree.bbox(item, column_id)
        if not bbox:
            return
        x, y, width, height = bbox
        value = tree.set(item, header)
        editor = ttk.Entry(tree)
        editor.insert(0, value)
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        self.active_editor = editor
        committed = {"done": False}

        def commit(_event: tk.Event | None = None) -> None:
            if committed["done"]:
                return
            committed["done"] = True
            new_value = editor.get().strip()
            editor.destroy()
            self.active_editor = None
            self._commit_cell(tree, item, header, new_value)

        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", lambda _event: editor.destroy())

    def _commit_cell(self, tree: ttk.Treeview, item: str, header: str, value: str) -> None:
        rows = self.label_rows if tree is self.labels_tree else self.db_rows
        index = tree.index(item)
        rows[index][header] = value
        if tree is self.labels_tree and header == "barcode" and value:
            self.apply_barcode_to_label_row(value, row_index=index)
            return
        if tree is self.db_tree:
            self._sync_labels_from_db(preserve_selection=True)
        self.refresh_tables()
        self._select_index(tree, index)

    def run_print_job(self, action: str, selected_only: bool = False) -> None:
        rows_to_print = self._selected_print_rows() if selected_only else list(self.label_rows)
        if not rows_to_print:
            messagebox.showwarning("\ucd9c\ub825 \ubaa9\ub85d", "\ucd9c\ub825\ud560 \ud56d\ubaa9\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.")
            return
        try:
            save_label_rows(self.queue_path, self.label_rows)
            save_db_rows(self.db_path, self.db_rows)
            excel_path = self.queue_path
            if selected_only:
                excel_path = _selected_print_queue_path(self.base_dir)
                save_label_rows(excel_path, rows_to_print)
        except Exception as exc:
            messagebox.showerror("\uc800\uc7a5 \uc2e4\ud328", str(exc))
            return
        if not self.print_exe.exists():
            messagebox.showerror("\ucd9c\ub825 \uc2e4\ud328", f"print_labels.exe\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.\n{self.print_exe}")
            return
        args = _build_print_args(self.print_exe, self.config_path, action, excel_path)
        try:
            result = subprocess.run(
                args,
                cwd=self.base_dir,
                text=True,
                capture_output=True,
                check=False,
                creationflags=_creationflags(),
            )
        except OSError as exc:
            messagebox.showerror("\ucd9c\ub825 \uc2e4\ud328", str(exc))
            return
        if result.returncode != 0:
            messagebox.showerror("\ucd9c\ub825 \uc2e4\ud328", (result.stderr or result.stdout or "").strip())
            return
        title = "\ucd9c\ub825 \ud30c\uc77c \uc0dd\uc131 \uc644\ub8cc" if action == "--dry-run" else "\ub77c\ubca8 \ucd9c\ub825 \uc644\ub8cc"
        if selected_only:
            title = f"\uc120\ud0dd {len(rows_to_print)}건 {title}"
        detail = (result.stdout or "").strip()
        self.status_var.set(f"{title}: {detail}" if detail else title)

    def open_settings(self) -> None:
        if self.settings_exe is None:
            messagebox.showwarning("\ud504\ub9b0\ud130 \uc124\uc815", "\ud504\ub9b0\ud130\uc124\uc815.exe\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.")
            return
        subprocess.Popen([str(self.settings_exe)], cwd=self.base_dir, creationflags=_creationflags())

    def open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(path)])

    def select_all_labels(self) -> None:
        self.selected_label_indexes = set(range(len(self.label_rows)))
        self.refresh_tables()
        self.status_var.set(f"전체 {len(self.selected_label_indexes)}건을 선택했습니다.")

    def clear_label_selection(self) -> None:
        self.selected_label_indexes.clear()
        self.refresh_tables()
        self.status_var.set("선택을 해제했습니다.")

    def _handle_label_click(self, event: tk.Event) -> str | None:
        if self.labels_tree.identify_column(event.x) != "#1":
            return None
        item = self.labels_tree.identify_row(event.y)
        if not item:
            return None
        self._toggle_label_index(self.labels_tree.index(item))
        return "break"

    def _toggle_label_index(self, index: int) -> None:
        if index in self.selected_label_indexes:
            self.selected_label_indexes.remove(index)
        else:
            self.selected_label_indexes.add(index)
        self.refresh_tables()
        self._select_index(self.labels_tree, index)
        self.status_var.set(f"선택 {len(self.selected_label_indexes)}건")

    def _sync_labels_from_db(self, preserve_selection: bool = True) -> None:
        selected_barcodes = self._selected_label_barcodes() if preserve_selection else set()
        self.label_rows = _label_rows_from_db_rows(self.db_rows)
        if preserve_selection:
            self.selected_label_indexes = {
                index
                for index, row in enumerate(self.label_rows)
                if str(row.get("barcode", "")).strip() in selected_barcodes
            }
        else:
            self.selected_label_indexes.clear()

    def _selected_label_barcodes(self) -> set[str]:
        return {
            str(self.label_rows[index].get("barcode", "")).strip()
            for index in self.selected_label_indexes
            if 0 <= index < len(self.label_rows) and str(self.label_rows[index].get("barcode", "")).strip()
        }

    def _selected_print_rows(self) -> list[dict[str, str]]:
        return [
            row
            for index, row in enumerate(self.label_rows)
            if index in self.selected_label_indexes and any(str(row.get(header, "")).strip() for header in LABEL_HEADERS)
        ]

    def _active_tree_and_rows(self) -> tuple[ttk.Treeview, list[dict[str, str]]]:
        if self.tabs.index(self.tabs.select()) == 0:
            return self.labels_tree, self.label_rows
        return self.db_tree, self.db_rows

    def _selected_label_index(self) -> int | None:
        selected = self.labels_tree.selection()
        return self.labels_tree.index(selected[0]) if selected else None

    def _selected_label_index_for_scan(self) -> int | None:
        if self.tabs.index(self.tabs.select()) != 0:
            return None
        return self._selected_label_index()

    def _first_empty_label_index(self) -> int:
        for index, row in enumerate(self.label_rows):
            if not any(str(row.get(header, "")).strip() for header in LABEL_HEADERS):
                return index
        self.label_rows.append({header: "" for header in LABEL_HEADERS})
        return len(self.label_rows) - 1

    def _select_last(self, tree: ttk.Treeview) -> None:
        children = tree.get_children()
        if children:
            tree.selection_set(children[-1])
            tree.see(children[-1])

    def _select_index(self, tree: ttk.Treeview, index: int) -> None:
        children = tree.get_children()
        if 0 <= index < len(children):
            tree.selection_set(children[index])
            tree.see(children[index])

    def _see_index(self, tree: ttk.Treeview, index: int) -> None:
        children = tree.get_children()
        if 0 <= index < len(children):
            tree.see(children[index])


def _label_rows_from_db_rows(db_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "item_code": str(row.get("item_code", "")).strip(),
            "item_name": str(row.get("item_name", "")).strip(),
            "barcode": str(row.get("barcode", "")).strip(),
            "lot_no": str(row.get("lot_no", "")).strip(),
            "qty": str(row.get("qty", "")).strip(),
            "print_qty": str(row.get("print_qty", "")).strip() or "1",
        }
        for row in db_rows
        if any(str(row.get(header, "")).strip() for header in DB_HEADERS)
    ]


def _ensure_label_row_index(label_rows: list[dict[str, str]], row_index: int | None) -> tuple[int, bool]:
    if row_index is None or row_index < 0:
        row_index = len(label_rows)
    appended = False
    while row_index >= len(label_rows):
        label_rows.append({header: "" for header in LABEL_HEADERS})
        appended = True
    return row_index, appended


def _delete_label_rows(label_rows: list[dict[str, str]], selected_indexes: set[int], focused_index: int | None) -> int:
    if selected_indexes:
        delete_indexes = {index for index in selected_indexes if 0 <= index < len(label_rows)}
    elif focused_index is not None and 0 <= focused_index < len(label_rows):
        delete_indexes = {focused_index}
    else:
        delete_indexes = set()
    if not delete_indexes:
        return 0
    label_rows[:] = [row for index, row in enumerate(label_rows) if index not in delete_indexes]
    selected_indexes.clear()
    return len(delete_indexes)


def _fill_tree(
    tree: ttk.Treeview,
    headers: tuple[str, ...],
    rows: list[dict[str, str]],
    selected_indexes: set[int] | None = None,
) -> None:
    selected_indexes = selected_indexes or set()
    for item in tree.get_children():
        tree.delete(item)
    for index, row in enumerate(rows):
        values = []
        for header in headers:
            if header == SELECT_HEADER:
                values.append(CHECKED if index in selected_indexes else UNCHECKED)
            else:
                values.append(row.get(header, ""))
        tags = ("checked",) if index in selected_indexes else ()
        tree.insert("", "end", values=values, tags=tags)


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _selected_print_queue_path(base_dir: Path) -> Path:
    return base_dir / "out" / "selected_print_queue.xlsx"


def _build_print_args(print_exe: Path, config_path: Path, action: str, excel_path: Path) -> list[str]:
    args = [str(print_exe), "--config", str(config_path), "--excel", str(excel_path), action]
    if action == "--print":
        args.append("--yes")
    return args


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Label print management app.")
    parser.add_argument("--base-dir", default=None, help="Folder containing config.ini and print_labels.exe")
    parser.add_argument("--smoke-test", action="store_true", help="Load data files and exit")
    args = parser.parse_args(argv)
    base_dir = Path(args.base_dir).resolve() if args.base_dir else app_base_dir()
    if args.smoke_test:
        load_db_rows(base_dir / "barcode_db.xlsx")
        load_label_rows(base_dir / "print_queue.xlsx")
        return 0
    app = LabelManagerApp(base_dir)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
