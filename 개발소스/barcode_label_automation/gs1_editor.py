"""Transactional GS1 AI composition dialog using the suite's existing styles."""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import ttk
from collections.abc import Callable, Mapping, Sequence

from .brand_assets import apply_window_icon, load_header_logo
from .gs1 import (AI_EXAMPLES, COMMON_AIS, GS1ValidationError, build_gs1, parse_gs1,
                  requirement_candidates, search_ai, example_elements)
from .ui_tokens import COLORS
from .ui_window import set_initial_window_size


def edit_gs1_data(parent: tk.Misc, elements: Sequence[Mapping[str, object]],
                  row: Mapping[str, object], fields: Sequence[str],
                  callback: Callable[[list[dict[str, str]], str], None], *, value: str = '',
                  code_type: str = 'gs1_datamatrix', on_symbol_change=None) -> tk.Toplevel:
    window = tk.Toplevel(parent)
    window.title('GS1 데이터 구성 · 응용식별자(AI)')
    window.configure(bg=COLORS.surface); window.transient(parent)
    set_initial_window_size(window, preferred_width=940, preferred_height=760,
                            minimum_width=700, minimum_height=560)
    apply_window_icon(window)
    window.columnconfigure(0, weight=1); window.rowconfigure(0, weight=1)
    def applied(records, hri):
        callback(records, hri); window.destroy()
    frame = build_gs1_editor(window, elements, row, fields, applied, value=value,
                             code_type=code_type, on_symbol_change=on_symbol_change, on_cancel=window.destroy)
    frame.grid(row=0, column=0, sticky='nsew')
    window.bind('<Escape>', lambda _event:window.destroy())
    window.grab_set()
    return window


def build_gs1_editor(parent: tk.Misc, elements: Sequence[Mapping[str, object]],
                     row: Mapping[str, object], fields: Sequence[str], callback, *, value: str = '',
                     code_type: str = 'gs1_datamatrix', on_symbol_change=None,
                     on_cancel=None, example_profile: str | None = None,
                     show_apply_button: bool = True) -> ttk.Frame:
    """Embedded transactional editor; no nested window or grab."""
    window = ttk.Frame(parent, style='Surface.TFrame')
    window.columnconfigure(0, weight=1); window.rowconfigure(1, weight=1)
    header = ttk.Frame(window, style='Surface.TFrame', padding=(18, 8))
    header.grid(row=0, column=0, sticky='ew')
    ttk.Label(header, text='GS1 데이터 구성', style='PanelTitle.TLabel').pack(side='left')
    if not show_apply_button:
        header.grid_remove()
    symbol = tk.StringVar(master=window, value=code_type)
    scroll_area = ttk.Frame(window, style='Surface.TFrame')
    scroll_area.grid(row=1,column=0,sticky='nsew')
    scroll_area.columnconfigure(0,weight=1); scroll_area.rowconfigure(0,weight=1)
    canvas=tk.Canvas(scroll_area,bg=COLORS.surface,highlightthickness=0)
    window.scroll_canvas = canvas
    canvas.grid(row=0,column=0,sticky='nsew')
    body_scroll=ttk.Scrollbar(scroll_area,orient='vertical',command=canvas.yview)
    body_scroll.grid(row=0,column=1,sticky='ns'); canvas.configure(yscrollcommand=body_scroll.set)
    body = ttk.Frame(canvas, style='Surface.TFrame', padding=(18, 0, 18, 12))
    body_id=canvas.create_window((0,0),window=body,anchor='nw')
    body.bind('<Configure>',lambda _event:canvas.configure(scrollregion=canvas.bbox('all')))
    def resize_body(event):
        if event.width < 760:
            library_frame.grid_remove()
            compose.grid_configure(column=0, columnspan=2)
        else:
            library_frame.grid()
            compose.grid_configure(column=1, columnspan=1)
        minimum = max(1, body.winfo_reqheight() - items.winfo_reqheight() + 75)
        canvas.itemconfigure(body_id, width=event.width, height=max(event.height, minimum))
    canvas.bind('<Configure>',resize_body)
    window.bind('<MouseWheel>',lambda event:canvas.yview_scroll(-1 if event.delta>0 else 1,'units'))
    body.columnconfigure(0, weight=1, minsize=220)
    body.columnconfigure(1, weight=2)
    body.rowconfigure(1, weight=1, minsize=230)
    query = tk.StringVar()
    ttk.Label(body, text='AI 번호 또는 의미 검색').grid(row=0, column=0, sticky='w')
    search = ttk.Entry(body, textvariable=query)
    search.grid(row=0, column=1, sticky='ew', padx=(10, 0))
    library_frame = ttk.Frame(body)
    library_frame.grid(row=1, column=0, sticky='nsew', pady=(8, 0), padx=(0, 12))
    library_frame.rowconfigure(1, weight=1)
    library_frame.columnconfigure(0, weight=1)
    library = ttk.Treeview(library_frame, columns=('ai', 'name'), show='headings', selectmode='browse')
    library.heading('ai', text='AI'); library.heading('name', text='의미')
    library.column('ai', width=55, stretch=False); library.column('name', width=160, minwidth=100)
    common_only = tk.BooleanVar(value=False)
    ttk.Checkbutton(library_frame, text='자주 사용하는 AI', variable=common_only,
                    command=lambda:search_changed()).grid(row=0,column=0,sticky='w',pady=(0,6))
    library.grid(row=1, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(library_frame, orient='vertical', command=library.yview)
    scroll.grid(row=1, column=1, sticky='ns'); library.configure(yscrollcommand=scroll.set)
    compose = ttk.Frame(body, style='Surface.TFrame')
    compose.grid(row=1, column=1, sticky='nsew', pady=(8, 0))
    compose.columnconfigure(1, weight=1)
    compose.rowconfigure(0, weight=1, minsize=75)
    items = ttk.Treeview(compose, columns=('ai', 'source', 'value'), show='headings', height=7, selectmode='browse')
    for name, label, width in (('ai','AI',50), ('source','값 원본',110), ('value','고정값 / DB 열',230)):
        items.heading(name, text=label); items.column(name, width=width, stretch=name=='value')
    items.grid(row=0, column=0, columnspan=2, sticky='nsew')
    item_scroll = ttk.Scrollbar(compose, orient='vertical', command=items.yview)
    item_scroll.grid(row=0, column=2, sticky='ns'); items.configure(yscrollcommand=item_scroll.set)
    status = tk.StringVar()
    records = [dict(x) for x in copy.deepcopy(elements)]
    if not records and value:
        try:
            records = [{'ai':x.ai, 'value':x.value, 'source_field':x.source_field} for x in parse_gs1(value)]
        except ValueError as exc:
            status.set(f'기존 값 확인 필요: {exc}')
    ai = tk.StringVar(master=window); source = tk.StringVar(value='고정값'); fixed = tk.StringVar(); field = tk.StringVar()
    hint = tk.StringVar(value='왼쪽 목록에서 AI를 선택한 뒤 값을 추가하세요.')
    hint_label = ttk.Label(compose, textvariable=hint, wraplength=470, style='Status.TLabel')
    hint_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=8)
    compose.bind('<Configure>',lambda event:hint_label.configure(wraplength=max(180,event.width-20)))
    ttk.Label(compose, text='선택 AI').grid(row=2, column=0, sticky='w')
    ai_choice = tk.StringVar(master=window)
    ai_selector = ttk.Combobox(compose, textvariable=ai_choice, state='readonly',
                               values=[f'{info.ai} · {info.label}' for info in search_ai()])
    ai_selector.grid(row=2, column=1, sticky='ew')
    ttk.Label(compose, text='값 원본').grid(row=3, column=0, sticky='w', pady=6)
    source_combo = ttk.Combobox(compose, textvariable=source, values=('고정값','DB 열'), state='readonly')
    source_combo.grid(row=3, column=1, sticky='ew')
    ttk.Label(compose, text='고정값').grid(row=4, column=0, sticky='w')
    value_entry = ttk.Entry(compose, textvariable=fixed)
    value_entry.grid(row=4, column=1, sticky='ew')
    ttk.Label(compose, text='DB 열').grid(row=5, column=0, sticky='w', pady=6)
    field_combo = ttk.Combobox(compose, textvariable=field, values=tuple(fields), state='disabled')
    field_combo.grid(row=5, column=1, sticky='ew')
    payload_var = tk.StringVar(); hri_var = tk.StringVar()
    draft_index: int | None = None
    loading = False
    dirty = False
    missing: tuple[str, ...] = ()
    items.tag_configure('error', foreground='#B42318')

    def invalidate(*_args: object) -> None:
        nonlocal dirty, missing
        if loading:
            return
        dirty = True
        missing = ()
        payload_var.set(''); hri_var.set('')
        status.set('입력값이 변경되었습니다. 검증 또는 적용할 때 선택 행에 자동 반영합니다.')
        required_button.configure(state='disabled')
        if not show_apply_button:
            window.event_generate('<<BarcodeDraftChanged>>', when='tail')

    def refresh_list(selected: int | None = None) -> None:
        items.delete(*items.get_children())
        for index, record in enumerate(records):
            binding = str(record.get('source_field',''))
            items.insert('', 'end', iid=str(index), values=(record['ai'], 'DB 열' if binding else '고정값', binding or record.get('value','')))
        if selected is not None and 0 <= selected < len(records):
            items.selection_set(str(selected)); items.see(str(selected))
        payload_var.set(''); hri_var.set('')
        if not show_apply_button:
            window.event_generate('<<BarcodeDraftChanged>>', when='tail')

    def search_changed(*_args: object) -> None:
        library.delete(*library.get_children())
        for info in search_ai(query.get()):
            if not common_only.get() or info.ai in COMMON_AIS:
                library.insert('', 'end', iid=info.ai, values=(info.ai, info.label))

    def select_ai(_event: object = None, *, selected_ai: str | None = None) -> None:
        nonlocal draft_index, loading, dirty
        selected = (selected_ai,) if selected_ai else library.selection()
        if not selected:
            return
        try:
            if draft_index is not None or fixed.get() or field.get():
                commit_draft()
        except ValueError as exc:
            status.set(str(exc)); return
        info = next(x for x in search_ai(selected[0]) if x.ai == selected[0])
        # Catalogue navigation starts a NEW draft, never retypes a selected record.
        loading = True; draft_index = None
        items.selection_remove(*items.selection())
        ai.set(info.ai); fixed.set(''); field.set(''); source.set('고정값')
        ai_choice.set(f'{info.ai} · {info.label}')
        loading = False; dirty = False
        example = AI_EXAMPLES.get(info.ai, '')
        hint.set(f'{info.label} · {info.title} · {info.min_length}~{info.max_length}자'
                 + (f' · 형식 예: {example} (단일 값 형식 · 완성 예제와 구분)' if example else ' · 조합 검증된 완성 예제 없음')
                 + ' · 입력 후 검증/적용하면 새 행에 자동 반영합니다.')

    def sync_source(*_args: object) -> None:
        value_entry.configure(state='normal' if source.get()=='고정값' else 'disabled')
        field_combo.configure(state='readonly' if source.get()=='DB 열' else 'disabled')

    def selected_record(_event: object = None) -> None:
        nonlocal draft_index, loading, dirty
        selected = items.selection()
        if not selected:
            return
        index = int(selected[0])
        if draft_index == index:
            return
        try:
            commit_draft()
        except ValueError as exc:
            status.set(str(exc))
            if draft_index is not None:
                items.selection_set(str(draft_index))
            return
        record = records[index]
        loading = True
        ai.set(str(record['ai'])); fixed.set(str(record.get('value',''))); field.set(str(record.get('source_field','')))
        ai_choice.set(str(record['ai']))
        source.set('DB 열' if field.get() else '고정값')
        loading = False; dirty = False; draft_index = index

    def commit_draft() -> None:
        nonlocal dirty, draft_index
        if not dirty:
            return
        if draft_index is None:
            if not ai.get():
                return
            records.append(current_record()); draft_index = len(records)-1
            refresh_list()
        else:
            records[draft_index] = current_record()
        binding = records[draft_index]['source_field']
        items.item(str(draft_index), values=(ai.get(), 'DB 열' if binding else '고정값', binding or fixed.get()))
        dirty = False

    def current_record() -> dict[str, str]:
        if not ai.get():
            raise ValueError('응용식별자(AI)를 먼저 선택하세요.')
        if source.get()=='DB 열' and field.get() not in fields:
            raise ValueError('연결할 DB 열을 선택하세요.')
        if source.get()=='고정값' and not fixed.get():
            raise ValueError(f'AI {ai.get()}의 고정값을 입력하거나 DB 열을 연결하세요.')
        record = {'ai':ai.get(), 'value':fixed.get() if source.get()=='고정값' else '',
                  'source_field':field.get() if source.get()=='DB 열' else ''}
        if draft_index is not None and records[draft_index].get('value_format') and ai.get() in {'11','12','13','15','16','17'}:
            record['value_format'] = str(records[draft_index]['value_format'])
        return record

    def change(action: str) -> None:
        nonlocal draft_index, dirty
        try:
            selected = items.selection(); index = int(selected[0]) if selected else None
            if action=='add':
                records.append(current_record()); index=len(records)-1
            elif index is None:
                raise ValueError('변경할 구성 행을 선택하세요.')
            elif action=='update':
                records[index]=current_record()
            elif action=='delete':
                records.pop(index); index=min(index,len(records)-1)
            else:
                commit_draft()
                target=index+(-1 if action=='up' else 1)
                if 0 <= target < len(records):
                    records[index],records[target]=records[target],records[index]; index=target
            draft_index = None; dirty = False
            refresh_list(index)
            if index is not None and index >= 0:
                selected_record()
            else:
                ai.set(''); ai_choice.set(''); fixed.set(''); field.set(''); dirty = False
            status.set('구성을 변경했습니다. 데이터 검증 후 적용하세요.')
        except ValueError as exc:
            status.set(str(exc))

    buttons = ttk.Frame(compose, style='Surface.TFrame')
    buttons.grid(row=6, column=0, columnspan=2, sticky='ew', pady=10)
    action_buttons=[]
    for action, label in (('add','추가'),('update','선택 수정'),('delete','삭제'),('up','위로'),('down','아래로')):
        action_buttons.append(ttk.Button(buttons,text=label,width=0,command=lambda a=action:change(a)))
    def wrap_buttons(event: object = None) -> None:
        available=getattr(event,'width',buttons.winfo_width())
        columns=max(1,min(5,int(available)//max(80,max(x.winfo_reqwidth()+5 for x in action_buttons))))
        for index,button in enumerate(action_buttons):
            button.grid(row=index//columns,column=index%columns,sticky='ew',padx=(0,5),pady=3)
    buttons.bind('<Configure>',wrap_buttons); window.after_idle(wrap_buttons)
    preview = ttk.Frame(window, style='Surface.TFrame', padding=(18, 8))
    preview.grid(row=2, column=0, sticky='ew'); preview.columnconfigure(1,weight=1)
    for number, title, variable in ((0,'표시문자',hri_var),(1,'인코딩 데이터',payload_var)):
        ttk.Label(preview,text=title).grid(row=number,column=0,sticky='w',padx=(0,10),pady=4)
        ttk.Entry(preview,textvariable=variable,state='readonly').grid(row=number,column=1,sticky='ew')
    ttk.Label(preview,textvariable=status,wraplength=860,style='Status.TLabel').grid(row=2,column=0,columnspan=2,sticky='w',pady=6)
    bottom = ttk.Frame(window, style='Surface.TFrame', padding=(18, 8, 18, 16))
    bottom.grid(row=3,column=0,sticky='ew')

    def check(apply: bool = False, *, preview_only: bool = False) -> bool:
        nonlocal missing
        try:
            if preview_only:
                candidate = copy.deepcopy(records)
                if dirty and ai.get():
                    record = current_record()
                    if draft_index is None:
                        candidate.append(record)
                    else:
                        candidate[draft_index] = record
            else:
                commit_draft()
                candidate = records
            payload=build_gs1(candidate,row=row)
            from .barcode_engine import render_barcode
            render_barcode(symbol.get(), payload.hri)
            missing = (); required_button.configure(state='disabled'); switch_button.configure(state='disabled')
            for iid in items.get_children():
                items.item(iid,tags=())
            hri_var.set(payload.hri); payload_var.set(payload.payload.replace('\x1d','<GS>'))
            status.set('현재 샘플 행의 AI 길이·문자·체크숫자·조합 검증을 통과했습니다. 전체 DB 행과 라벨 경계는 메인 화면의 전체 데이터 검증에서 확인하세요.')
            if apply:
                callback(copy.deepcopy(candidate),payload.hri)
            return True
        except ValueError as exc:
            hri_var.set(''); payload_var.set('')
            category = exc.category if isinstance(exc, GS1ValidationError) else 'capacity'
            category_label = {'value':'값 형식', 'association':'필수 조합', 'capacity':'선택 기호 생성'}.get(category, category)
            status.set(f'{category_label} 오류: {exc}')
            switch_button.configure(state='normal' if category == 'capacity' and on_symbol_change else 'disabled')
            if isinstance(exc, GS1ValidationError):
                missing = requirement_candidates(exc.requirements) if exc.requirements else ()
                required_button.configure(state='normal' if missing else 'disabled')
                for index, record in enumerate(records):
                    if record.get('ai') in exc.affected_ais:
                        items.item(str(index), tags=('error',))
                        items.see(str(index))
            return False

    def select_required() -> None:
        nonlocal draft_index, loading, dirty
        candidates = missing
        if not candidates:
            return
        commit_draft()
        common_only.set(False); query.set(''); search_changed()
        library.delete(*library.get_children())
        for info in search_ai():
            if info.ai in candidates:
                library.insert('', 'end', iid=info.ai, values=(info.ai, info.label))
        items.selection_remove(*items.selection())
        draft_index = None; loading = True
        ai.set(''); ai_choice.set(''); fixed.set(''); field.set(''); source.set('고정값')
        loading = False; dirty = False
        hint.set('필수 AI 후보입니다. 해당 상품의 실제 식별번호 또는 DB 열을 지정한 뒤 추가하세요.')
        status.set('후보가 “또는”으로 연결되면 한 가지를 선택합니다. “및” 조합은 필요한 AI 모두 추가하세요.')
        library.focus_set()

    saved_example: tuple | None = None

    def replace_records(candidate) -> None:
        nonlocal records, draft_index, loading, dirty
        records = copy.deepcopy(candidate); draft_index = None; dirty = False; loading = True
        ai.set(''); ai_choice.set(''); fixed.set(''); field.set(''); source.set('고정값')
        loading = False; refresh_list()

    def load_example(profile=None) -> bool:
        nonlocal saved_example
        try:
            candidate = example_elements(profile or example_profile or ai.get() or '01', symbology=symbol.get())
            saved_example = (copy.deepcopy(records), draft_index, dirty, ai.get(), source.get(), fixed.get(), field.get())
            replace_records(candidate)
            undo_button.configure(state='normal')
            check()
            status.set('시험용 완성 예제입니다. 실제 발급값과 DB 연결로 교체하세요. 되돌리기로 이전 입력을 복원할 수 있습니다.')
            return True
        except ValueError as exc:
            status.set(f'예제 생성 오류: {exc}. 입력은 유지했습니다.'); return False

    def undo_example() -> None:
        nonlocal saved_example, draft_index, dirty, loading
        if saved_example is not None:
            previous, previous_index, previous_dirty, previous_ai, previous_source, previous_fixed, previous_field = saved_example
            replace_records(previous); saved_example = None; loading = True
            ai.set(previous_ai); source.set(previous_source); fixed.set(previous_fixed); field.set(previous_field)
            loading = False; draft_index = previous_index; dirty = previous_dirty
            if draft_index is not None:
                items.selection_set(str(draft_index))
            undo_button.configure(state='disabled'); status.set('예제 적용 전 입력으로 되돌렸습니다.')

    def import_value(raw: str) -> bool:
        try:
            parsed = parse_gs1(raw)
            candidate = [{'ai':x.ai, 'value':x.value, 'source_field':x.source_field} for x in parsed]
            payload = build_gs1(candidate)
            from .barcode_engine import render_barcode
            render_barcode(symbol.get(), payload.hri)
            replace_records(candidate); check()
            status.set('전체 GS1 원문을 해석했습니다. AI 값과 인코딩 데이터를 확인한 뒤 적용하세요.')
            return True
        except ValueError as exc:
            status.set(f'전체 데이터 가져오기 오류: {exc}. 기존 입력은 유지했습니다.'); return False

    def switch_symbol() -> None:
        if on_symbol_change is not None:
            on_symbol_change('gs1_datamatrix'); symbol.set('gs1_datamatrix'); check()

    tools = ttk.Frame(body, style='Surface.TFrame')
    tools.grid(row=2,column=0,columnspan=2,sticky='ew',pady=(10,0))
    ttk.Button(tools,text='시험용 완성 예제로 시작',command=load_example).pack(side='left')
    undo_button = ttk.Button(tools,text='예제 되돌리기',command=undo_example,state='disabled')
    undo_button.pack(side='left',padx=6)
    import_text = tk.StringVar(master=window)
    ttk.Label(body,text='전체 GS1 데이터 가져오기').grid(row=3,column=0,sticky='w',pady=6)
    ttk.Entry(body,textvariable=import_text).grid(row=3,column=1,sticky='ew')
    ttk.Button(tools,text='전체 데이터 가져오기',command=lambda:import_value(import_text.get())).pack(side='left')
    switch_button = ttk.Button(bottom,text='DataMatrix로 변경',command=switch_symbol,state='disabled')
    switch_button.pack(side='left',padx=6)

    ttk.Button(bottom,text='데이터 검증',command=check).pack(side='left')
    required_button = ttk.Button(bottom,text='필수 AI 선택',command=select_required,state='disabled')
    required_button.pack(side='left',padx=8)
    if on_cancel is not None:
        ttk.Button(bottom,text='취소',command=on_cancel).pack(side='right')
    if show_apply_button:
        ttk.Button(bottom,text='적용',command=lambda:check(True),style='Primary.TButton').pack(side='right',padx=8)
    query.trace_add('write',search_changed); source.trace_add('write',sync_source)
    for variable in (ai, source, fixed, field):
        variable.trace_add('write',invalidate)
    library.bind('<<TreeviewSelect>>',select_ai); items.bind('<<TreeviewSelect>>',selected_record)
    ai_selector.bind('<<ComboboxSelected>>',lambda _event:select_ai(selected_ai=ai_choice.get().split(' · ',1)[0]))
    def resize_preview(event: tk.Event) -> None:
        if event.widget is window:
            for label in preview.winfo_children():
                if isinstance(label,ttk.Label):
                    label.configure(wraplength=max(300,event.width-40))
    window.bind('<Configure>',resize_preview,add='+')
    search_changed(); refresh_list(); search.focus_set()
    window.validate = check
    window.preview = lambda:check(True, preview_only=True)
    window.get_records = lambda:copy.deepcopy(records)
    window.load_complete_example = load_example
    window.import_value = import_value
    window.status_var = status
    window.set_symbol = symbol.set
    return window
