from copy import deepcopy
import tkinter as tk
from tkinter import ttk

import pytest

from barcode_label_automation.barcode_options_dialog import edit_barcode_options
from barcode_label_automation.gs1_editor import edit_gs1_data
from barcode_label_automation.gs1 import build_gs1
from barcode_label_automation.ui_style import configure_suite_style


def descendants(parent):
    result=[]
    for child in parent.winfo_children():
        result.append(child); result.extend(descendants(child))
    return result


def button(window,text):
    return next(w for w in descendants(window) if isinstance(w,ttk.Button) and w.cget('text')==text)


def field(window,label):
    label_widget=next(w for w in descendants(window) if isinstance(w,ttk.Label) and w.cget('text')==label)
    parent=label_widget.master
    row=int(label_widget.grid_info()['row'])
    return next(w for w in parent.winfo_children() if isinstance(w,(ttk.Entry,ttk.Combobox)) and int(w.grid_info().get('row',-1))==row)


@pytest.fixture
def root():
    window=tk.Tk();configure_suite_style(window);window.geometry('1100x850+20+20');window.update()
    yield window
    window.destroy()


@pytest.mark.parametrize('kind',['qr','gs1_128','pdf417','datamatrix','maxicode','itf14'])
def test_option_dialog_cancel_does_not_mutate(root,kind):
    original={'quiet_zone':4};baseline=deepcopy(original);calls=[]
    window=edit_barcode_options(root,kind,original,calls.append);root.update()
    button(window,'취소').invoke();root.update()
    assert original==baseline and calls==[]


def test_options_apply_validates_and_preserves_float(root):
    calls=[];window=edit_barcode_options(root,'pdf417',{'pdf417_module_height':10/3},calls.append);root.update()
    button(window,'적용').invoke();root.update()
    assert len(calls)==1 and calls[0]['pdf417_module_height']==pytest.approx(10/3)


def test_options_invalid_value_keeps_dialog_open(root):
    calls=[];window=edit_barcode_options(root,'qr',{'cell_size':-1},calls.append);root.update()
    button(window,'적용').invoke();root.update()
    assert calls==[] and window.winfo_exists()
    assert any('옵션을 적용할 수 없습니다' in w.get('1.0','end') for w in descendants(window) if isinstance(w,tk.Text))


def test_gs1_cancel_after_local_edit_preserves_original(root):
    original=[{'ai':'01','value':'09506000134376','source_field':''}];baseline=deepcopy(original);calls=[]
    window=edit_gs1_data(root,original,{},[],lambda *args:calls.append(args));root.update()
    library=next(w for w in descendants(window) if isinstance(w,ttk.Treeview) and w.cget('columns')==('ai','name'))
    library.selection_set('10');library.event_generate('<<TreeviewSelect>>');root.update()
    fixed=field(window,'고정값');fixed.insert(0,'LOT001');button(window,'추가').invoke();root.update()
    button(window,'취소').invoke();root.update()
    assert original==baseline and calls==[]


def test_gs1_db_binding_resolves_sample_and_keeps_binding(root):
    original=[{'ai':'01','value':'09506000134376','source_field':''},
              {'ai':'10','value':'','source_field':'lot'}, {'ai':'21','value':'','source_field':'serial'}]
    baseline=deepcopy(original);row={'lot':'LOT001','serial':'00042'};calls=[]
    window=edit_gs1_data(root,original,row,['lot','serial'],lambda *args:calls.append(args));root.update()
    button(window,'데이터 검증').invoke();root.update();button(window,'적용').invoke();root.update()
    assert original==baseline and len(calls)==1
    elements,hri=calls[0];assert elements[1]['source_field']=='lot' and elements[2]['source_field']=='serial'
    payload=build_gs1(elements,row=row)
    assert '\x1d21' in payload.payload and hri=='(01)09506000134376(10)LOT001(21)00042'


def test_gs1_invalid_gtin_prevents_apply(root):
    calls=[];window=edit_gs1_data(root,[{'ai':'01','value':'123','source_field':''}],{},[],lambda *args:calls.append(args));root.update()
    button(window,'적용').invoke();root.update()
    assert calls==[] and window.winfo_exists()

@pytest.mark.parametrize('scaling',[1.33333,2.0,2.66667])
def test_gs1_small_window_keeps_composition_and_actions_accessible(root,scaling):
    root.tk.call('tk','scaling',scaling)
    window=edit_gs1_data(root,[{'ai':'01','value':'09506000134376','source_field':''}],{},[],lambda *_:None)
    window.geometry('700x560+50+50');root.update()
    items=next(w for w in descendants(window) if isinstance(w,ttk.Treeview) and w.cget('columns')==('ai','source','value'))
    assert items.winfo_ismapped() and items.winfo_height()>=80, '구성 목록이 사라지거나 읽을 수 없는 높이입니다.'
    for title in ('추가','선택 수정','삭제','위로','아래로'):
        control=button(window,title)
        assert control.winfo_ismapped(), f'{title} 동작이 숨겨졌습니다.'
        assert control.winfo_rootx()+control.winfo_width()<=window.winfo_rootx()+window.winfo_width(), f'{title} 버튼이 잘립니다.'


def test_designer_type_change_discards_inapplicable_advanced_options(tmp_path,monkeypatch):
    from barcode_label_automation.label_designer_app import LabelDesignerApp, BARCODE_TYPES
    from barcode_label_automation.barcode_catalog import option_definitions
    from barcode_label_automation import label_designer_app as designer
    monkeypatch.setattr(designer,"_available_font_names",lambda _root:["Malgun Gothic"])
    monkeypatch.setattr(LabelDesignerApp,"_offer_recovery",lambda self:None)
    for method in ("showerror","showwarning","showinfo"):
        monkeypatch.setattr(designer.messagebox,method,lambda *a,**k:None)
    monkeypatch.setattr(LabelDesignerApp,"_offer_start_dialog",lambda self:None)
    app=LabelDesignerApp(tmp_path,register_file_association=False)
    try:
        element={'id':'qa-barcode','type':'barcode','barcode_type':'qr','text':'ABC123','x':1,'y':1,'width':50,'height':30,
                 'barcode_options':{'version':40,'qr_ecc':'H','human_readable':False,'cell_size':0}}
        app.elements=[element];app.update();app.open_element_editor(element);app.update()
        editor=next(w for w in descendants(app) if isinstance(w,tk.Toplevel) and w.title()=='바코드 속성')
        combo=next(w for w in descendants(editor) if isinstance(w,ttk.Combobox) and BARCODE_TYPES['qr'] in w.cget('values') and BARCODE_TYPES['code39'] in w.cget('values'))
        combo.set(BARCODE_TYPES['code39']);combo.event_generate('<<ComboboxSelected>>');app.update()
        assert element['barcode_type']=='qr'
        next(w for w in descendants(editor) if isinstance(w,ttk.Button) and str(w.cget('text'))=='확인').invoke();app.update()
        assert not editor.winfo_exists()
        assert element['barcode_type']=='code39'
        specs=option_definitions('code39')
        assert not any(k not in specs and v != designer.BARCODE_OPTION_DEFAULTS.get(k) for k,v in element['barcode_options'].items()), str(element['barcode_options'])
    finally:
        app.destroy()


def composition_tree(window):
    return next(w for w in descendants(window) if isinstance(w,ttk.Treeview) and w.cget('columns')==('ai','source','value'))


def select_composition(root, window, index):
    tree=composition_tree(window)
    tree.selection_set(str(index)); tree.event_generate('<<TreeviewSelect>>'); root.update()


@pytest.mark.parametrize('mode',['fixed','field','ai'])
def test_gs1_apply_commits_selected_draft_without_update_button(root,mode):
    original=[{'ai':'01','value':'09506000134376','source_field':''},
              {'ai':'21','value':'OLD001','source_field':''}]
    baseline=deepcopy(original);calls=[]
    window=edit_gs1_data(root,original,{'serial':'DB002'},['serial'],lambda *args:calls.append(args));root.update()
    select_composition(root,window,1)
    if mode=='fixed':
        entry=field(window,'고정값');entry.delete(0,'end');entry.insert(0,'NEW002')
    elif mode=='field':
        field(window,'값 원본').set('DB 열');field(window,'DB 열').set('serial')
    else:
        library=next(w for w in descendants(window) if isinstance(w,ttk.Treeview) and w.cget('columns')==('ai','name'))
        library.selection_set('10');library.event_generate('<<TreeviewSelect>>');root.update()
        field(window,'고정값').insert(0,'LOT002')
    button(window,'적용').invoke();root.update()
    assert original==baseline and len(calls)==1
    record=calls[0][0][1]
    if mode=='fixed':
        assert record['value']=='NEW002'
    elif mode=='field':
        assert record['source_field']=='serial'
    else:
        assert record['ai']=='21' and record['value']=='OLD001'
        assert calls[0][0][2]['ai']=='10' and calls[0][0][2]['value']=='LOT002'


def test_gs1_draft_invalidates_validation_and_row_switch_preserves_edit(root):
    calls=[];window=edit_gs1_data(root,[{'ai':'01','value':'09506000134376','source_field':''},
        {'ai':'21','value':'OLD001','source_field':''}],{},[],lambda *args:calls.append(args));root.update()
    select_composition(root,window,1);button(window,'데이터 검증').invoke();root.update()
    entry=field(window,'고정값');entry.delete(0,'end');entry.insert(0,'NEW002')
    labels=[root.getvar(w.cget('textvariable')) for w in descendants(window) if isinstance(w,ttk.Label) and w.cget('textvariable')]
    assert any('입력값이 변경' in x for x in labels)
    select_composition(root,window,0);button(window,'적용').invoke();root.update()
    assert calls[0][0][1]['value']=='NEW002'


def test_gs1_missing_requirement_navigation_never_invents_value(root):
    calls=[];window=edit_gs1_data(root,[{'ai':'21','value':'01.03.8006','source_field':''}],{},[],lambda *args:calls.append(args));root.update()
    button(window,'적용').invoke();root.update()
    assert calls==[] and button(window,'필수 AI 선택').instate(['!disabled'])
    button(window,'필수 AI 선택').invoke();root.update()
    library=next(w for w in descendants(window) if isinstance(w,ttk.Treeview) and w.cget('columns')==('ai','name'))
    assert set(library.get_children())=={'01','03','8006'}
    assert field(window,'고정값').get()==''
    library.selection_set('01');library.event_generate('<<TreeviewSelect>>');root.update()
    entry=field(window,'고정값');entry.insert(0,'09506000134376');button(window,'추가').invoke();root.update()
    button(window,'적용').invoke();root.update()
    assert len(calls)==1 and calls[0][0][0]['value']=='01.03.8006'


def test_gs1_new_unadded_draft_is_committed_on_apply(root):
    calls=[];window=edit_gs1_data(root,[{'ai':'01','value':'09506000134376','source_field':''}],{},[],lambda *args:calls.append(args));root.update()
    library=next(w for w in descendants(window) if isinstance(w,ttk.Treeview) and w.cget('columns')==('ai','name'))
    library.selection_set('10');library.event_generate('<<TreeviewSelect>>');root.update()
    field(window,'고정값').insert(0,'LOT001');button(window,'적용').invoke();root.update()
    assert len(calls)==1 and calls[0][0][-1]['ai']=='10' and calls[0][0][-1]['value']=='LOT001'


def test_options_current_value_renderer_rechecks_every_apply(root):
    from PIL import Image
    calls=[];renders=[]
    def render(options):
        renders.append(dict(options))
        if len(renders)>1:
            raise ValueError('현재 개체가 너무 작습니다')
        return Image.new('1',(25,25),1)
    window=edit_barcode_options(root,'qr',{},calls.append,preview_value='ACTUAL001',preview_renderer=render);root.update()
    assert any(isinstance(w,ttk.Entry) and w.get()=='ACTUAL001' for w in descendants(window))
    button(window,'미리보기 및 생성 검증').invoke();root.update()
    assert window._barcode_preview_image is not None
    button(window,'적용').invoke();root.update()
    assert len(renders)==2 and calls==[] and window.winfo_exists()


def test_options_actual_qr_capacity_rejected_before_callback(root):
    calls=[];window=edit_barcode_options(root,'qr',{'version':1,'qr_ecc':'H'},calls.append,preview_value='A'*300);root.update()
    button(window,'적용').invoke();root.update()
    assert calls==[] and window.winfo_exists()


def test_options_sample_notice_does_not_claim_current_data_check(root):
    window=edit_barcode_options(root,'qr',{},lambda *_:None);root.update()
    button(window,'미리보기 및 생성 검증').invoke();root.update()
    assert any('실제 DB 값과 인쇄 영역은 아직 검증하지 않았습니다' in w.get('1.0','end') for w in descendants(window) if isinstance(w,tk.Text))


@pytest.mark.parametrize('scaling',[1.33333,2.0,2.66667])
def test_options_small_window_dpi_keeps_footer_accessible(root,scaling):
    root.tk.call('tk','scaling',scaling)
    window=edit_barcode_options(root,'qr',{},lambda *_:None);window.geometry('500x650+50+50');root.update()
    for text in ('미리보기 및 생성 검증','적용','취소'):
        control=button(window,text)
        assert control.winfo_ismapped()
        assert control.winfo_rootx()+control.winfo_width()<=window.winfo_rootx()+window.winfo_width()
        assert control.winfo_rooty()+control.winfo_height()<=window.winfo_rooty()+window.winfo_height()


def test_embedded_gs1_has_no_popup_and_example_undo_preserves_bindings(root):
    from barcode_label_automation.gs1_editor import build_gs1_editor
    original=[{'ai':'01','value':'09506000134376'}, {'ai':'21','source_field':'serial'}]
    frame=build_gs1_editor(root,original,{'serial':'00001'},['serial'],lambda *_:None)
    frame.pack(fill='both',expand=True);root.update()
    assert not any(isinstance(x,tk.Toplevel) for x in descendants(root))
    assert frame.load_complete_example('37')
    assert [x['ai'] for x in frame.get_records()]==['00','02','37']
    button(frame,'예제 되돌리기').invoke();root.update()
    assert frame.get_records()==original


def test_gs1_full_import_atomic_failure_and_scanner_roundtrip(root):
    from barcode_label_automation.gs1_editor import build_gs1_editor
    original=[{'ai':'01','value':'09506000134376'}]
    frame=build_gs1_editor(root,original,{},[],lambda *_:None)
    frame.pack(fill='both',expand=True);root.update()
    assert not frame.import_value('(01)123')
    assert frame.get_records()==original
    raw=build_gs1([*original,{'ai':'21','value':'00001'}]).payload
    assert frame.import_value(']d2'+raw)
    assert frame.get_records()[-1]['value']=='00001'


def test_gs1_ai37_reports_all_missing_requirements_gui(root):
    window=edit_gs1_data(root,[{'ai':'37','value':'24'}],{},[],lambda *_:None);root.update()
    button(window,'데이터 검증').invoke();root.update()
    button(window,'필수 AI 선택').invoke();root.update()
    library=next(x for x in descendants(window) if isinstance(x,ttk.Treeview) and x.cget('columns')==('ai','name'))
    assert set(library.get_children())=={'00','02','8026'}
    assert field(window,'고정값').get()==''


def test_gs1_long_udi_capacity_switch_keeps_original_data(root):
    from barcode_label_automation.gs1_editor import build_gs1_editor
    original=[{'ai':'01','value':'09506000134376'}, {'ai':'11','value':'261013'},
              {'ai':'17','value':'271013'}, {'ai':'10','value':'LOT001'}, {'ai':'21','value':'SER0001'}]
    switched=[];calls=[]
    frame=build_gs1_editor(root,original,{},[],lambda *x:calls.append(x),code_type='gs1_128',on_symbol_change=switched.append)
    frame.pack(fill='both',expand=True);root.update()
    assert not frame.validate(True) and not calls
    assert frame.get_records()==original
    button(frame,'DataMatrix로 변경').invoke();root.update()
    assert switched==['gs1_datamatrix'] and frame.validate(True)
    assert calls[0][0]==original


def test_gs1_catalogue_selection_preserves_dirty_existing_row(root):
    calls=[];window=edit_gs1_data(root,[{'ai':'01','value':'09506000134376'},
        {'ai':'21','value':'OLD001','source_field':''}],{},[],lambda *args:calls.append(args));root.update()
    select_composition(root,window,1)
    entry=field(window,'고정값');entry.delete(0,'end');entry.insert(0,'NEW002')
    library=next(w for w in descendants(window) if isinstance(w,ttk.Treeview) and w.cget('columns')==('ai','name'))
    library.selection_set('10');library.event_generate('<<TreeviewSelect>>');root.update()
    assert field(window,'고정값').get()==''
    field(window,'고정값').insert(0,'LOT003')
    button(window,'적용').invoke();root.update()
    assert calls[0][0][1]['value']=='NEW002' and calls[0][0][1]['ai']=='21'
    assert calls[0][0][2]['value']=='LOT003'
