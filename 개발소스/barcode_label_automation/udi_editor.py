"""Structured UDI drafts and an embedded input editor (no regulatory issuance)."""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import ttk
from collections.abc import Mapping

from .gs1 import GS1ValidationError, build_gs1, parse_gs1, gs1_date
from .ui_tokens import COLORS

UDI_FIELDS = (
    ('gtin', '제품 식별번호 DI · GTIN 14자리', '01'),
    ('lot', '로트 / 배치번호', '10'),
    ('serial', '일련번호', '21'),
    ('manufacture_date', '제조일 YYYY-MM-DD', '11'),
    ('expiry_date', '사용기한 YYYY-MM-DD', '17'),
)
HIBC_FIELDS = (
    ('lic', '제조사 LIC · 4자리', ''), ('product', '제품번호', ''),
    ('package', '포장단위 · 0~9', ''), *UDI_FIELDS[1:]
)


def _resolve_descriptor(name: str, descriptor: Mapping, row: Mapping) -> object:
    binding = str(descriptor.get('source_field', ''))
    if binding:
        if binding not in row:
            raise ValueError(f'{name}: 연결한 DB 열 {binding}을 찾을 수 없습니다.')
        return row[binding]
    return descriptor.get('value', '')


def resolve_udi_value(element: Mapping, row: Mapping | None = None) -> str:
    """Resolve stored HIBC input exactly once; GS1 uses canonical AI records."""
    data = element.get('udi_data', {})
    row = row or {}
    if data.get('profile') == 'HIBC':
        from .hibc import compose_hibc, resolve_hibc
        if data.get('input_mode') == 'complete':
            return resolve_hibc(str(data.get('complete_value', '')), input_mode='complete')
        kwargs = {name: _resolve_descriptor(label, data.get('fields', {}).get(name, {}), row)
                  for name, label, _ in HIBC_FIELDS}
        for name in ('manufacture_date', 'expiry_date'):
            value = kwargs[name]
            if hasattr(value, 'strftime'):
                kwargs[name] = value.strftime('%Y-%m-%d')
        return compose_hibc(kwargs.pop('lic'), kwargs.pop('product'), kwargs.pop('package'), **kwargs)
    return build_gs1(element.get('gs1_elements', []), row=row).hri


def build_udi_patch(element: Mapping, descriptors: Mapping, *, profile: str = 'GS1',
                    row: Mapping | None = None, code_type: str = 'gs1_datamatrix',
                    complete_value: str = '', market: str = '', packaging: str = '') -> dict:
    """Build a validated patch without mutating the element or partial callbacks."""
    from .barcode_engine import render_barcode
    row = row or {}
    if profile not in ('GS1','HIBC'):
        raise ValueError('UDI 코드체계를 선택하세요.')
    patch = {'udi_profile':profile, 'udi_market':market, 'udi_packaging':packaging, 'barcode_type':code_type}
    if profile == 'GS1':
        if not code_type.startswith('gs1_'):
            raise ValueError('GS1 UDI에는 GS1 기호를 선택하세요.')
        managed = {ai for _,_,ai in UDI_FIELDS}
        records = [copy.deepcopy(record) for record in element.get('gs1_elements', [])
                   if str(record.get('ai')) not in managed]
        for name, label, ai in UDI_FIELDS:
            descriptor = descriptors.get(name, {})
            if name != 'gtin' and not descriptor.get('enabled', False):
                continue
            value = descriptor.get('value', '')
            binding = str(descriptor.get('source_field', ''))
            if name in ('manufacture_date','expiry_date') and not binding:
                value = gs1_date(value, ai=ai)
            record = {'ai':ai, 'value':value if not binding else '', 'source_field':binding}
            if name in ('manufacture_date','expiry_date') and binding:
                record['value_format'] = 'gs1_date'
            records.append(record)
        payload = build_gs1(records, row=row)
        render_barcode(code_type, payload.hri)
        patch.update(gs1_elements=records, text=payload.hri, udi_data={'profile':'GS1'})
    else:
        if not code_type.startswith('hibc'):
            raise ValueError('HIBC UDI에는 HIBC 기호를 선택하세요.')
        data = {'profile':'HIBC', 'fields':{}, 'input_mode':'complete' if complete_value else 'structured'}
        for name, _, _ in HIBC_FIELDS:
            descriptor = descriptors.get(name, {})
            if name in ('lot','serial','manufacture_date','expiry_date') and not descriptor.get('enabled',False):
                descriptor = {'value':'', 'source_field':''}
            data['fields'][name] = {'value':descriptor.get('value',''), 'source_field':descriptor.get('source_field','')}
        if complete_value:
            data['complete_value'] = complete_value
        patch['udi_data'] = data
        payload = resolve_udi_value(patch,row)
        render_barcode(code_type,payload,{'hibc_input_mode':'complete'})
        patch.update(text=payload, gs1_elements=[], barcode_options=dict(element.get('barcode_options',{}), hibc_input_mode='complete'))
    return patch


def build_udi_editor(parent, element: Mapping, row: Mapping, fields, on_change,
                     on_symbol_change=None, *, show_apply_button: bool = True) -> ttk.Frame:
    """Input within the barcode editor; drafts stay local until validation passes."""
    shell = ttk.Frame(parent, style='Surface.TFrame')
    shell.columnconfigure(0, weight=1); shell.rowconfigure(0, weight=1)
    canvas = tk.Canvas(shell, highlightthickness=0)
    canvas.grid(row=0, column=0, sticky='nsew')
    scrollbar = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
    scrollbar.grid(row=0, column=1, sticky='ns')
    canvas.configure(yscrollcommand=scrollbar.set)
    shell.scroll_canvas = canvas
    frame = ttk.Frame(canvas, style='Surface.TFrame', padding=12)
    handle = canvas.create_window((0, 0), window=frame, anchor='nw')
    frame.bind('<Configure>', lambda _event:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda event:canvas.itemconfigure(handle, width=event.width))
    frame.columnconfigure(1,weight=1); frame.columnconfigure(2,weight=1)
    initial = copy.deepcopy(dict(element))
    profile = tk.StringVar(master=frame,value=str(element.get('udi_profile','GS1')))
    market = tk.StringVar(master=frame,value=str(element.get('udi_market','선택 안 함')))
    packaging = tk.StringVar(master=frame,value=str(element.get('udi_packaging','')))
    symbol = tk.StringVar(master=frame,value=str(element.get('barcode_type','gs1_datamatrix')))
    status = tk.StringVar(master=frame,value='의료기기 UDI · 발급받은 DI와 제품에 필요한 PI를 입력하세요. 생성은 발급·등록·규제 승인을 뜻하지 않습니다.')
    ttk.Label(frame,text='코드체계').grid(row=0,column=0,sticky='w')
    profile_combo = ttk.Combobox(frame,textvariable=profile,values=('GS1','HIBC'),state='readonly')
    profile_combo.grid(row=0,column=1,sticky='ew',padx=8)
    ttk.Label(frame,text='시장 정보').grid(row=1,column=0,sticky='w')
    ttk.Combobox(frame,textvariable=market,values=('선택 안 함','대한민국','미국','유럽연합','기타'),state='readonly').grid(row=1,column=1,sticky='ew',padx=8,pady=4)
    ttk.Label(frame,text='포장 수준 · 관리 메모').grid(row=2,column=0,sticky='w')
    ttk.Entry(frame,textvariable=packaging).grid(row=2,column=1,columnspan=2,sticky='ew',padx=8,pady=4)
    ttk.Label(frame,text='항목 / 필요 여부').grid(row=3,column=0,sticky='w',pady=6)
    ttk.Label(frame,text='고정값').grid(row=3,column=1,sticky='w',padx=8)
    ttk.Label(frame,text='DB 열 · 비워 두면 고정값').grid(row=3,column=2,sticky='w',padx=8)
    all_fields = {name:(label,ai) for name,label,ai in (*UDI_FIELDS,*HIBC_FIELDS)}
    values = {}; sources = {}; enabled = {}; controls = {}
    imported = ''; loading = False; previous_draft = None
    for number,(name,(label,ai)) in enumerate(all_fields.items(),4):
        record = next((x for x in element.get('gs1_elements',[]) if x.get('ai')==ai),{}) if ai else {}
        hibc_descriptor = element.get('udi_data',{}).get('fields',{}).get(name,{})
        record = hibc_descriptor or record
        values[name]=tk.StringVar(master=frame,value=str(record.get('value','')))
        sources[name]=tk.StringVar(master=frame,value=str(record.get('source_field','')))
        enabled[name]=tk.BooleanVar(master=frame,value=bool(record))
        if name in ('lot','serial','manufacture_date','expiry_date'):
            label_widget=ttk.Checkbutton(frame,text=label,variable=enabled[name])
        else:
            label_widget=ttk.Label(frame,text=label)
        label_widget.grid(row=number,column=0,sticky='w',pady=4)
        entry=ttk.Entry(frame,textvariable=values[name]); entry.grid(row=number,column=1,sticky='ew',padx=8,pady=4)
        source=ttk.Combobox(frame,textvariable=sources[name],values=('',*fields),state='readonly')
        source.grid(row=number,column=2,sticky='ew',padx=8,pady=4)
        controls[name]=(label_widget,entry,source)
    end=4+len(all_fields)
    full=tk.StringVar(master=frame)
    ttk.Label(frame,text='완성 GS1 / HIBC 원문').grid(row=end,column=0,sticky='w',pady=6)
    ttk.Entry(frame,textvariable=full).grid(row=end,column=1,columnspan=2,sticky='ew',padx=8)
    ttk.Label(frame,textvariable=status,style='Status.TLabel',wraplength=680).grid(row=end+2,column=0,columnspan=3,sticky='ew',pady=8)
    buttons=ttk.Frame(frame,style='Surface.TFrame'); buttons.grid(row=end+3,column=0,columnspan=3,sticky='ew')

    def snapshot():
        return {name:{'value':values[name].get(), 'source_field':sources[name].get(), 'enabled':enabled[name].get()} for name in all_fields}

    def changed(*_args):
        nonlocal imported
        if loading:
            return
        imported=''
        for name, (_,entry,source) in controls.items():
            optional=name in ('lot','serial','manufacture_date','expiry_date')
            active=not optional or enabled[name].get()
            entry.configure(state='normal' if active and not sources[name].get() else 'disabled')
            source.configure(state='readonly' if active else 'disabled')
        status.set('입력 중입니다. 데이터 검증 또는 적용 시 선택 기호로 생성 확인합니다.')
        if not show_apply_button:
            shell.event_generate('<<BarcodeDraftChanged>>', when='tail')

    def check(apply=False):
        try:
            patch=build_udi_patch(initial,snapshot(),profile=profile.get(),row=row,code_type=symbol.get(),
                                  complete_value=imported,market=market.get(),packaging=packaging.get())
            status.set('DI/PI 값과 선택 기호 생성 검증을 통과했습니다. 전체 DB 행과 라벨 경계는 메인 화면의 전체 데이터 검증에서 확인하세요.')
            switch.configure(state='disabled')
            if apply:
                on_change(copy.deepcopy(patch))
            return True
        except ValueError as exc:
            from .barcode_engine import BarcodeEncodingError
            category='선택 기호 생성 / 용량' if isinstance(exc,BarcodeEncodingError) else '필수 조합' if isinstance(exc,GS1ValidationError) and exc.category=='association' else '입력값'
            status.set(f'{category} 오류: {exc}. 입력 데이터는 유지됩니다.')
            switch.configure(state='normal' if isinstance(exc,BarcodeEncodingError) and on_symbol_change else 'disabled')
            return False

    def use_example():
        nonlocal loading, imported, previous_draft
        previous_draft=(snapshot(),profile.get(),imported,copy.deepcopy(initial))
        loading=True; imported=''
        samples={'gtin':'09506000134376','lot':'LOT001','serial':'SER0001','manufacture_date':'2026-10-13','expiry_date':'2027-10-13','lic':'A123','product':'BJC5D6E','package':'1'}
        for name in all_fields:
            values[name].set(samples[name]); sources[name].set(''); enabled[name].set(name in ('lot','serial','manufacture_date','expiry_date'))
        loading=False; changed(); undo.configure(state='normal')
        okay=check()
        status.set(('시험용 예제 생성 성공. ' if okay else status.get()+' ')+'실제 발급값으로 교체하세요. 예제 되돌리기가 가능합니다.')
        return okay

    def undo_example():
        nonlocal loading, imported, previous_draft, initial
        if previous_draft is None:
            return
        descriptors,prev_profile,raw,initial=previous_draft; loading=True; profile.set(prev_profile)
        for name,d in descriptors.items():
            values[name].set(d['value']);sources[name].set(d['source_field']);enabled[name].set(d['enabled'])
        loading=False; changed(); imported=raw; previous_draft=None
        undo.configure(state='disabled'); status.set('시험 예제 이전 입력을 복원했습니다.')

    def import_value(raw=None):
        nonlocal loading, imported, initial
        raw=full.get() if raw is None else raw
        try:
            if profile.get()=='HIBC':
                from .hibc import parse_hibc
                result=parse_hibc(raw)
                descriptors={name:getattr(result,name,'') for name in all_fields}
            else:
                parsed=parse_gs1(raw);build_gs1(parsed)
                descriptors={name:next((x.value for x in parsed if x.ai==ai),'') for name,(_,ai) in all_fields.items()}
            loading=True
            for name in all_fields:
                values[name].set(str(descriptors[name]));sources[name].set('');enabled[name].set(bool(descriptors[name]))
            if profile.get()=='GS1':
                initial=dict(initial,gs1_elements=[{'ai':x.ai,'value':x.value,'source_field':''} for x in parsed])
            loading=False;changed(); imported=raw if profile.get()=='HIBC' else ''
            okay=check();status.set(('가져오기 검증 성공. ' if okay else status.get()+' ')+'원문을 삭제하거나 잘라내지 않았습니다.')
            return okay
        except ValueError as exc:
            loading=False; status.set(f'원문 가져오기 오류: {exc}. 기존 입력을 유지했습니다.'); return False

    def choose_profile(*_args, notify=True):
        is_hibc=profile.get()=='HIBC'
        for name,widgets in controls.items():
            visible=name!='gtin' if is_hibc else name not in ('lic','product','package')
            for widget in widgets:
                widget.grid() if visible else widget.grid_remove()
        target='hibcdatamatrix' if is_hibc else 'gs1_datamatrix'
        if not symbol.get().startswith('hibc' if is_hibc else 'gs1_'):
            symbol.set(target)
            if notify and on_symbol_change:
                on_symbol_change(target)
        changed()

    def to_datamatrix():
        target='hibcdatamatrix' if profile.get()=='HIBC' else 'gs1_datamatrix'
        symbol.set(target)
        if on_symbol_change:
            on_symbol_change(target)
        check()

    ttk.Button(buttons,text='시험용 UDI 예제',command=use_example).pack(side='left',padx=4)
    undo=ttk.Button(buttons,text='예제 되돌리기',command=undo_example,state='disabled');undo.pack(side='left',padx=4)
    ttk.Button(buttons,text='전체 원문 가져오기',command=import_value).pack(side='left',padx=4)
    ttk.Button(buttons,text='데이터 검증',command=check).pack(side='left',padx=4)
    if show_apply_button:
        ttk.Button(buttons,text='UDI 적용',command=lambda:check(True),style='Primary.TButton').pack(side='left',padx=4)
    switch=ttk.Button(frame,text='DataMatrix로 변경',command=to_datamatrix,state='disabled');switch.grid(row=end+1,column=0,sticky='w',pady=6)
    profile_combo.bind('<<ComboboxSelected>>',choose_profile)
    for variable in (*values.values(),*sources.values(),*enabled.values()):
        variable.trace_add('write',changed)
    choose_profile(notify=False)
    imported=str(element.get('udi_data',{}).get('complete_value','')) if profile.get()=='HIBC' else ''
    frame.validate=check;frame.get_draft=snapshot;frame.load_complete_example=use_example
    frame.import_value=import_value;frame.status_var=status;frame.set_symbol=symbol.set
    frame.field_vars=values;frame.source_vars=sources;frame.enabled_vars=enabled;frame.profile_var=profile
    for name in ('validate', 'get_draft', 'load_complete_example', 'import_value', 'status_var', 'set_symbol',
                 'field_vars', 'source_vars', 'enabled_vars', 'profile_var'):
        setattr(shell, name, getattr(frame, name))
    return shell
