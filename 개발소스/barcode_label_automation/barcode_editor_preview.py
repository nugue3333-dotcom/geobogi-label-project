"""Print-dot preview for the transactional barcode properties editor."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

from .ui_tokens import COLORS
from .ui_window import set_initial_window_size


class BarcodeEditorPreview(ttk.Frame):
    def __init__(self, parent, *, on_row_change=None):
        super().__init__(parent, style="Surface.TFrame", padding=10)
        self.on_row_change = on_row_change
        self.original = None
        self.photo = None
        self.mode = "fit"
        self.compact = False
        self.result = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text="현재 입력 미리보기", style="HeaderTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        self.row_controls = ttk.Frame(self, style="Surface.TFrame")
        self.row_controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        self.row_var = tk.StringVar(self, "1")
        self.row_combo = ttk.Combobox(self.row_controls, textvariable=self.row_var, state="readonly", width=6)
        ttk.Label(self.row_controls, text="DB 행").pack(side="left")
        ttk.Button(self.row_controls, text="이전", command=lambda: self.move_row(-1)).pack(side="left", padx=4)
        self.row_combo.pack(side="left")
        self.row_count = ttk.Label(self.row_controls)
        self.row_count.pack(side="left", padx=4)
        ttk.Button(self.row_controls, text="다음", command=lambda: self.move_row(1)).pack(side="left")
        self.row_combo.bind("<<ComboboxSelected>>", lambda _e: self.choose_row())
        self.row_controls.grid_remove()
        self.image_host = ttk.Frame(self)
        self.image_host.grid(row=2, column=0, sticky="nsew", pady=(4, 0))
        self.image_host.columnconfigure(0, weight=1)
        self.image_host.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.image_host, width=310, height=250, bg="white", highlightthickness=1, highlightbackground=COLORS.border)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        xbar = ttk.Scrollbar(self.image_host, orient="horizontal", command=self.canvas.xview)
        xbar.grid(row=1, column=0, sticky="ew")
        ybar = ttk.Scrollbar(self.image_host, orient="vertical", command=self.canvas.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        toolbar = ttk.Frame(self, style="Surface.TFrame")
        toolbar.grid(row=3, column=0, sticky="ew", pady=5)
        ttk.Button(toolbar, text="전체 보기", command=lambda: self.set_mode("fit")).pack(side="left")
        ttk.Button(toolbar, text="100%", command=lambda: self.set_mode("actual")).pack(side="left", padx=4)
        ttk.Button(toolbar, text="확대 보기", command=self.open_large).pack(side="left")
        self.details = ttk.Frame(self, style="Surface.TFrame")
        self.details.grid(row=4, column=0, sticky="ew")
        self.details.columnconfigure(0, weight=1)
        self.metrics_var = tk.StringVar(self)
        self.status_var = tk.StringVar(self, "값을 입력하세요.")
        self.scale_var = tk.StringVar(self)
        self.metrics = ttk.Label(self.details, textvariable=self.metrics_var, wraplength=300)
        self.metrics.grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Label(self.details, text="실제 인코딩 값 / 표시문자", style="Hint.TLabel").grid(row=1, column=0, sticky="w")
        self.value_text = tk.Text(self.details, height=3, width=28, wrap="word", relief="solid", bd=1)
        self.value_text.grid(row=2, column=0, sticky="ew", pady=3)
        self.value_text.configure(state="disabled")
        self.status = ttk.Label(self.details, textvariable=self.status_var, wraplength=300, foreground=COLORS.text_secondary)
        self.status.grid(row=3, column=0, sticky="ew", pady=4)
        self.scale_label = ttk.Label(self.details, textvariable=self.scale_var, style="Hint.TLabel", wraplength=300)
        self.scale_label.grid(row=4, column=0, sticky="ew")
        self.details.bind("<Configure>", self.wrap_details)

    def wrap_details(self, event):
        for label in (self.metrics, self.status, self.scale_label):
            label.configure(wraplength=max(160, event.width-8))

    def set_compact(self, compact):
        if self.compact == compact:
            return
        self.compact = compact
        self.canvas.configure(height=140 if compact else 250)
        self.details.grid(row=2 if compact else 4, column=1 if compact else 0, rowspan=2 if compact else 1,
                          sticky="nsew", padx=(10, 0) if compact else 0)
        self.columnconfigure(1, weight=1 if compact else 0)
        self.draw()

    def set_rows(self, count, selected=0):
        self.row_combo.configure(values=[str(i+1) for i in range(count)])
        self.row_count.configure(text=f"/ {count}")
        self.row_var.set(str(selected+1))
        self.row_controls.grid() if count else self.row_controls.grid_remove()

    def move_row(self, step):
        count = len(self.row_combo.cget("values"))
        if count:
            self.row_var.set(str(max(1, min(count, int(self.row_var.get())+step))))
            self.choose_row()

    def choose_row(self):
        if self.on_row_change:
            self.on_row_change(int(self.row_var.get())-1)

    def set_mode(self, mode):
        self.mode = mode
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.draw()

    def set_result(self, bitmap, *, value, hri, metrics, warning=""):
        self.original = bitmap.copy()
        self.result = {"value": value, "hri": hri, "metrics": metrics, "warning": warning}
        self.metrics_var.set(metrics)
        self.value_text.configure(state="normal")
        self.value_text.delete("1.0", "end")
        self.value_text.insert("1.0", f"{value.replace(chr(29), '<GS>')}\n{hri}")
        self.value_text.configure(state="disabled")
        self.status_var.set(f"인쇄 전 조정 필요: {warning}" if warning else "현재 편집 초안 · 적용 전")
        self.draw()

    def set_error(self, message):
        self.original = None
        self.result = {"error": str(message)}
        self.metrics_var.set("")
        self.value_text.configure(state="normal")
        self.value_text.delete("1.0", "end")
        self.value_text.configure(state="disabled")
        self.status_var.set(str(message))
        self.draw()

    def draw(self):
        if not self.canvas.winfo_exists():
            return
        self.canvas.delete("all")
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        if self.original is None:
            self.photo = None
            self.canvas.create_text(w/2, h/2, text="입력값을 확인하세요", fill=COLORS.text_secondary, width=max(120,w-24))
            self.canvas.configure(scrollregion=(0, 0, w, h))
            self.scale_var.set("")
            return
        ratio = min((w-16)/self.original.width, (h-16)/self.original.height) if self.mode == "fit" else 1.0
        ratio = max(.01, ratio)
        displayed = self.original.convert("RGB").resize((max(1,round(self.original.width*ratio)),max(1,round(self.original.height*ratio))),Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(displayed, master=self.canvas)
        left, top = max(8,(w-displayed.width)/2), max(8,(h-displayed.height)/2)
        self.canvas.create_image(left, top, image=self.photo, anchor="nw")
        self.canvas.configure(scrollregion=(0,0,max(w,displayed.width+16),max(h,displayed.height+16)))
        self.scale_var.set(f"화면 배율 {ratio*100:.0f}% · 출력 도트 {self.original.width}×{self.original.height}")

    def open_large(self):
        window = tk.Toplevel(self)
        window.title("현재 편집 초안 · 확대 미리보기")
        set_initial_window_size(window, preferred_width=820, preferred_height=650,
                                minimum_width=520, minimum_height=400)
        window.transient(self.winfo_toplevel())
        panel = BarcodeEditorPreview(window)
        def change_row(index):
            self.row_var.set(str(index+1))
            if self.on_row_change:
                self.on_row_change(index)
            if self.original is not None:
                panel.set_result(self.original, **self.result)
            else:
                panel.set_error(self.status_var.get())
        panel.on_row_change = change_row
        row_count = len(self.row_combo.cget("values"))
        panel.set_rows(row_count, max(0, int(self.row_var.get())-1))
        if self.original is not None:
            panel.set_result(self.original, **self.result)
        else:
            panel.set_error(self.status_var.get())
        panel.set_mode("actual")
        parent = self.winfo_toplevel()
        def close():
            window.destroy()
            if parent.winfo_exists():
                parent.grab_set()
        ttk.Button(window, text="닫기", command=close).pack(side="bottom", pady=8)
        panel.pack(fill="both", expand=True)
        window.bind("<Escape>", lambda _e: close())
        window.protocol("WM_DELETE_WINDOW", close)
        window.grab_set()
