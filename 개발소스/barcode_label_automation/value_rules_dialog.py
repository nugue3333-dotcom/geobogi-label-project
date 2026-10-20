"""Transactional editor for explicit label value rules, using shared suite styles."""
from __future__ import annotations

import copy
import tkinter as tk
from collections.abc import Callable, Mapping, Sequence
from tkinter import ttk

from .brand_assets import apply_window_icon, load_header_logo
from .ui_tokens import COLORS
from .ui_window import set_initial_window_size
from .value_rules import compile_generated_labels, validate_value_rules

KIND_LABELS = {"일련번호": "serial", "날짜 / 기한": "date", "문자 붙이기": "text", "부분 추출": "slice"}
KIND_NAMES = {value: key for key, value in KIND_LABELS.items()}


def edit_value_rules(
    parent: tk.Misc, rules: Sequence[Mapping[str, object]], headers: Sequence[str],
    on_apply: Callable[[list[dict[str, object]]], None], *, sample_row: Mapping[str, object] | None = None,
    preferred_name: str | None = None,
) -> tk.Toplevel:
    initial_records = validate_value_rules(copy.deepcopy(rules), headers)
    window = tk.Toplevel(parent)
    window.title("값 생성 규칙 · 번호 / 날짜 / 문자")
    window.configure(bg=COLORS.surface)
    window.transient(parent)
    set_initial_window_size(window, preferred_width=900, preferred_height=780, minimum_width=700, minimum_height=500)
    apply_window_icon(window)
    window.columnconfigure(0, weight=1)
    window.rowconfigure(1, weight=1)
    header = ttk.Frame(window, style="Surface.TFrame", padding=(18, 12))
    header.grid(row=0, column=0, sticky="ew")
    logo = load_header_logo(window, max_width=150, max_height=40)
    if logo is not None:
        window._value_rules_logo = logo
        ttk.Label(header, image=logo, style="Surface.TLabel").pack(side="left", padx=(0, 16))
    ttk.Label(header, text="값 생성 규칙", style="PanelTitle.TLabel").pack(side="left")
    scroll_area = ttk.Frame(window, style="Surface.TFrame")
    scroll_area.grid(row=1, column=0, sticky="nsew")
    scroll_area.columnconfigure(0, weight=1)
    scroll_area.rowconfigure(0, weight=1)
    canvas = tk.Canvas(scroll_area, bg=COLORS.surface, highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=canvas.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    canvas.configure(yscrollcommand=scrollbar.set)
    body = ttk.Frame(canvas, style="Surface.TFrame", padding=(18, 0, 18, 12))
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=2)
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(body_id, width=event.width))
    window.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"))
    ttk.Label(body, text="생성 필드는 도안에서 {{필드 이름}} 또는 GS1의 DB 열로 연결합니다. 위에서 아래 순서로 계산합니다.", wraplength=790, style="Status.TLabel").grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
    listing = ttk.Frame(body, style="Surface.TFrame")
    listing.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
    listing.columnconfigure(0, weight=1)
    table = ttk.Treeview(listing, columns=("name", "kind"), show="headings", selectmode="browse", height=8)
    table.heading("name", text="생성 필드")
    table.heading("kind", text="계산 방식")
    table.column("name", width=140, minwidth=90)
    table.column("kind", width=95, minwidth=85)
    table.grid(row=0, column=0, sticky="nsew")
    table_scroll = ttk.Scrollbar(listing, command=table.yview)
    table_scroll.grid(row=0, column=1, sticky="ns")
    table.configure(yscrollcommand=table_scroll.set)
    order = ttk.Frame(listing, style="Surface.TFrame")
    order.grid(row=1, column=0, sticky="ew", pady=8)
    form = ttk.Frame(body, style="Surface.TFrame")
    form.grid(row=1, column=1, sticky="nsew")
    form.columnconfigure(1, weight=1)
    variables = {key: tk.StringVar(value=value) for key, value in {
        "name": "", "kind": "일련번호", "start": "1", "step": "1", "digits": "6", "copies_per_value": "1",
        "reset": "작업마다 시작", "prefix": "", "suffix": "", "direction": "증가", "alphabet": "숫자",
        "target_field": "전체 값", "target_start": "1", "target_length": "6", "width_mode": "자리수 유지",
        "base": "작업 날짜", "field": "",
        "offset_days": "0", "format": "YYYYMMDD", "template": "", "length": "1",
    }.items()}
    form_controls: dict[str, tuple[ttk.Label, tk.Widget]] = {}
    for key, text, choices in (
        ("name", "생성 필드 이름", None), ("kind", "계산 방식", tuple(KIND_LABELS)),
        ("start", "시작 번호 / 추출 위치", None), ("step", "증가량", None), ("digits", "자리수 (앞에 0 채움)", None),
        ("copies_per_value", "같은 번호의 복사 수", None), ("reset", "다음 작업 번호", ("작업마다 시작", "계속 발급")),
        ("direction", "방향", ("증가", "감소")),
        ("alphabet", "순번 방식", ("숫자", "영문 대문자", "영문 소문자", "숫자+영문 대문자")),
        ("width_mode", "문자 수", ("자리수 유지", "자동 자리수")),
        ("target_field", "변경 대상", ("전체 값",) + tuple(headers)),
        ("target_start", "바꿀 위치 (첫 글자=1)", None), ("target_length", "바꿀 글자 수", None),
        ("prefix", "번호 앞 문자", None), ("suffix", "번호 뒤 문자", None),
        ("base", "기준 날짜", ("작업 날짜", "DB 날짜")), ("field", "원본 열", tuple(headers)),
        ("offset_days", "더할 일수 (음수 가능)", None), ("format", "날짜 표시", ("YYYYMMDD", "YYMMDD", "YYYY-MM-DD")),
        ("template", "문자 / {{DB 열}} 결합", None), ("length", "추출 글자 수", None),
    ):
        label = ttk.Label(form, text=text)
        widget = ttk.Entry(form, textvariable=variables[key]) if choices is None else ttk.Combobox(form, textvariable=variables[key], values=choices, state="readonly")
        form_controls[key] = label, widget
    hint = tk.StringVar()
    ttk.Label(body, textvariable=hint, style="Status.TLabel", wraplength=790).grid(row=2, column=0, columnspan=2, sticky="ew", pady=12)
    actions = ttk.Frame(body, style="Surface.TFrame")
    actions.grid(row=3, column=0, columnspan=2, sticky="ew")
    preview = ttk.Treeview(body, columns=("copy", "value"), show="headings", height=3)
    preview.heading("copy", text="라벨 / 복사 수")
    preview.heading("value", text="생성 값 미리보기 · 번호를 소비하지 않습니다")
    preview.column("copy", width=105, stretch=False)
    preview.column("value", width=600)
    preview.grid(row=4, column=0, columnspan=2, sticky="ew", pady=12)
    status = tk.StringVar(value="적용 전 번호는 발급되지 않습니다. 취소하면 도안의 규칙을 유지합니다.")
    footer = ttk.Frame(window, style="Surface.TFrame", padding=(18, 12))
    footer.grid(row=2, column=0, sticky="ew")
    ttk.Label(footer, textvariable=status, style="Status.TLabel", wraplength=790).pack(fill="x", pady=(0, 10))
    records = initial_records
    selected: list[int | None] = [None]
    baseline: list[dict[str, str]] = [{}]
    refreshing = [False]

    def draw_form(*_args) -> None:
        kind = KIND_LABELS[variables["kind"].get()]
        visible = {
            "serial": ("name", "kind", "direction", "alphabet", "width_mode", "start", "step", "digits", "copies_per_value", "reset", "target_field",
                       *( ("target_start", "target_length") if variables["target_field"].get() != "전체 값" else ()),
                       *( ("prefix", "suffix") if variables["target_field"].get() == "전체 값" else ())),
            "date": ("name", "kind", "base", "field", "offset_days", "format"),
            "text": ("name", "kind", "template"), "slice": ("name", "kind", "field", "start", "length"),
        }[kind]
        for label, widget in form_controls.values():
            label.grid_remove()
            widget.grid_remove()
        for row_index, key in enumerate(visible):
            label, widget = form_controls[key]
            if key == "start":
                label.configure(text="시작 위치 (첫 글자=1)" if kind == "slice" else "시작 번호")
            if key == "digits":
                label.configure(text="자리수 / 최대 길이")
            label.grid(row=row_index, column=0, sticky="w", padx=(0, 12), pady=5)
            widget.grid(row=row_index, column=1, sticky="ew", pady=5)
            if key == "field":
                widget.configure(values=tuple(headers) + tuple(str(record.get("name", "")) for record in records[:selected[0] if selected[0] is not None else len(records)]))
                widget.configure(state="disabled" if kind == "date" and variables["base"].get() == "작업 날짜" else "readonly")
            if key == "target_field":
                widget.configure(values=("전체 값",) + tuple(headers))
        hint.set({
            "serial": "증가·감소와 숫자/영문 순번을 선택합니다. 번호당 매수만큼 같은 값을 찍고, 일부 변경은 선택한 DB 열의 자리수만 바꿉니다. 미리보기는 번호를 발급하지 않습니다.",
            "date": "작업 날짜는 작업 시작 시 고정됩니다. DB 날짜는 YYYYMMDD 또는 YYYY-MM-DD입니다. 사용기한은 기준 날짜에 일수를 더해 계산합니다.",
            "text": "예: LOT-{{품번}}-{{일련번호}}. 생성 필드는 앞선 규칙만 참조할 수 있습니다. 원본 DB 열이 없으면 출력 전에 오류를 표시합니다.",
            "slice": "시작 위치는 첫 글자가 1입니다. 예: ABC123에서 시작 4, 길이 3이면 123입니다. 원본을 변경하지 않습니다.",
        }[kind])

    def draft() -> dict[str, object]:
        kind = KIND_LABELS[variables["kind"].get()]
        item: dict[str, object] = {"name": variables["name"].get(), "kind": kind}
        keys = {"serial": ("start", "step", "digits", "copies_per_value", "prefix", "suffix", "target_start", "target_length"), "date": ("field", "offset_days", "format"), "text": ("template",), "slice": ("field", "start", "length")}[kind]
        item.update({key: variables[key].get() for key in keys})
        if kind == "serial":
            item["reset"] = "continue" if variables["reset"].get() == "계속 발급" else "job"
            item["direction"] = "down" if variables["direction"].get() == "감소" else "up"
            item["alphabet"] = {"숫자":"numeric", "영문 대문자":"uppercase", "영문 소문자":"lowercase", "숫자+영문 대문자":"alphanumeric"}[variables["alphabet"].get()]
            item["preserve_width"] = variables["width_mode"].get() == "자리수 유지"
            item["target_field"] = "" if variables["target_field"].get() == "전체 값" else variables["target_field"].get()
        elif kind == "date":
            item["base"] = "field" if variables["base"].get() == "DB 날짜" else "job"
        return item

    def current_values() -> dict[str, str]:
        return {key: variable.get() for key, variable in variables.items()}

    def adjust_serial_start(*_args) -> None:
        if refreshing[0]:
            return
        alphabet = {
            "숫자": "0123456789", "영문 대문자": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "영문 소문자": "abcdefghijklmnopqrstuvwxyz", "숫자+영문 대문자": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        }.get(variables["alphabet"].get(), "0123456789")
        start = variables["start"].get()
        if not start or any(char not in alphabet for char in start):
            variables["start"].set(alphabet[0])
            variables["width_mode"].set("자동 자리수" if variables["alphabet"].get() != "숫자" else "자리수 유지")

    def refresh(index: int | None = None) -> None:
        refreshing[0] = True
        table.delete(*table.get_children())
        for number, record in enumerate(records):
            table.insert("", "end", iid=str(number), values=(record.get("name", ""), KIND_NAMES.get(str(record.get("kind")), "확인 필요")))
        selected[0] = index
        if index is not None:
            table.selection_set(str(index))
            record = records[index]
            for key, variable in variables.items():
                if key in record and key not in ("kind", "base", "reset"):
                    variable.set(str(record[key]))
            variables["kind"].set(KIND_NAMES.get(str(record.get("kind")), "일련번호"))
            variables["reset"].set("계속 발급" if record.get("reset") == "continue" else "작업마다 시작")
            variables["base"].set("DB 날짜" if record.get("base") == "field" else "작업 날짜")
            variables["direction"].set("감소" if record.get("direction") == "down" else "증가")
            variables["alphabet"].set({"numeric":"숫자", "uppercase":"영문 대문자", "lowercase":"영문 소문자", "alphanumeric":"숫자+영문 대문자"}.get(str(record.get("alphabet", "numeric")), "숫자"))
            variables["target_field"].set(str(record.get("target_field") or "전체 값"))
            variables["width_mode"].set("자리수 유지" if record.get("preserve_width", record.get("alphabet", "numeric") == "numeric") else "자동 자리수")
        else:
            variables["direction"].set("증가")
            variables["alphabet"].set("숫자")
            variables["target_field"].set("전체 값")
            variables["width_mode"].set("자리수 유지")
        baseline[0] = current_values()
        refreshing[0] = False
        draw_form()

    def commit_selected() -> None:
        if selected[0] is not None and current_values() != baseline[0]:
            proposed = copy.deepcopy(records)
            proposed[selected[0]] = draft()
            normalized = validate_value_rules(proposed, headers)
            records[:] = normalized
            baseline[0] = current_values()
        elif selected[0] is None and variables["name"].get().strip():
            raise ValueError("새 규칙은 '추가'를 눌러 목록에 넣으세요.")

    def selection_changed(_event=None) -> None:
        if refreshing[0]:
            return
        chosen = table.selection()
        if not chosen or int(chosen[0]) == selected[0]:
            return
        try:
            commit_selected()
            refresh(int(chosen[0]))
            status.set("선택한 규칙을 편집합니다. 입력 변경은 적용 전에 자동 반영합니다.")
        except ValueError as exc:
            if selected[0] is not None:
                table.selection_set(str(selected[0]))
            status.set(str(exc))

    def add() -> None:
        try:
            item = draft()
            normalized = validate_value_rules(records + [item], headers)
            records[:] = normalized
            refresh(len(records) - 1)
            status.set("규칙을 추가했습니다. 적용하면 도안에 저장됩니다.")
        except ValueError as exc:
            status.set(str(exc))

    def change() -> None:
        try:
            if selected[0] is None:
                raise ValueError("수정할 규칙을 목록에서 선택하세요.")
            commit_selected()
            refresh(selected[0])
            status.set("변경한 규칙을 반영했습니다.")
        except ValueError as exc:
            status.set(str(exc))

    def delete() -> None:
        if selected[0] is not None:
            records.pop(selected[0])
            variables["name"].set("")
            refresh()
            status.set("규칙을 삭제했습니다. 다른 규칙의 참조가 남았다면 적용 전에 수정하세요.")

    def move(delta: int) -> None:
        try:
            commit_selected()
            index = selected[0]
            if index is None or not 0 <= index + delta < len(records):
                return
            proposed = copy.deepcopy(records)
            proposed[index], proposed[index + delta] = proposed[index + delta], proposed[index]
            records[:] = validate_value_rules(proposed, headers)
            refresh(index + delta)
        except ValueError as exc:
            status.set(str(exc))

    def show_preview() -> None:
        try:
            commit_selected()
            normalized = validate_value_rules(records, headers)
            labels = compile_generated_labels([dict(sample_row or {})], [4], normalized)
            preview.delete(*preview.get_children())
            for index, label in enumerate(labels[:4], start=1):
                values = " · ".join(f"{rule['name']}={label.row[str(rule['name'])]}" for rule in normalized)
                preview.insert("", "end", values=(f"{index} / {label.copies}장", values or "생성 규칙 없음"))
            status.set("규칙 시작값으로 4장을 미리 봅니다. 실제 계속 발급 번호는 출력 화면에서 확인하며 이 미리보기는 번호를 소비하지 않습니다.")
        except ValueError as exc:
            preview.delete(*preview.get_children())
            status.set(f"미리보기 확인 필요: {exc}")

    def apply() -> None:
        try:
            commit_selected()
            normalized = validate_value_rules(records, headers)
            on_apply(copy.deepcopy(normalized))
            window.destroy()
        except ValueError as exc:
            status.set(f"적용할 수 없습니다: {exc}")

    ttk.Button(order, text="위로", command=lambda: move(-1)).pack(side="left")
    ttk.Button(order, text="아래로", command=lambda: move(1)).pack(side="left", padx=6)
    for text, command in (("추가", add), ("선택 수정", change), ("삭제", delete), ("4장 미리보기", show_preview)):
        ttk.Button(actions, text=text, command=command).pack(side="left", padx=(0, 8))
    ttk.Button(footer, text="취소", command=window.destroy).pack(side="right")
    ttk.Button(footer, text="적용", command=apply, style="Primary.TButton").pack(side="right", padx=8)
    table.bind("<<TreeviewSelect>>", selection_changed)
    variables["kind"].trace_add("write", draw_form)
    variables["base"].trace_add("write", draw_form)
    variables["target_field"].trace_add("write", draw_form)
    variables["alphabet"].trace_add("write", adjust_serial_start)
    window.bind("<Escape>", lambda _event: window.destroy())
    # Named handles support the same real-Tk regression checks as the suite.
    window._value_rules_variables = variables
    window._value_rules_table = table
    window._value_rules_apply = apply
    window._value_rules_preview = show_preview
    window._value_rules_status = status
    preferred_index = next((index for index, record in enumerate(records) if record.get("name") == preferred_name), None)
    refresh(preferred_index if preferred_index is not None else (0 if records else None))
    window.grab_set()
    return window
