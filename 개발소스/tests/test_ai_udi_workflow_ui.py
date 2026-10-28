"""Real Tk regressions for the approved AI/UDI and corrective editing flow."""
from copy import deepcopy
import json
from types import SimpleNamespace
from tkinter import ttk

import pytest
import zxingcpp
from test_barcode_first_ui import (app, settle, descendants, widget_with_text, field, set_field,
                                   install_element, open_editor)
from barcode_label_automation import label_designer_app as designer
from barcode_label_automation.gs1 import build_gs1, parse_gs1
from barcode_label_automation.templates import mm_to_dots


def choose_purpose(app, editor, purpose):
    editor._barcode_show_page('data')
    if purpose == 'GS1':
        widget_with_text(editor, 'GS1 데이터로 설정…', ttk.Button).invoke()
    else:
        widget_with_text(editor, '기타 데이터 옵션…', ttk.Menubutton)
        editor._barcode_option_menu.invoke(0)
    settle(app)
    return editor._barcode_controllers['active']


def test_unified_udi_example_apply_fit_save_reopen_and_decode(app, tmp_path, monkeypatch):
    app.template['label'].update(width_mm=60,height_mm=35)
    element=install_element(app)
    editor=open_editor(app,element)
    controller=choose_purpose(app,editor,'의료기기 UDI')
    assert controller.load_complete_example()
    assert controller.validate(True)
    assert 'udi_profile' not in element and element['barcode_type']=='qr'
    assert editor._barcode_draft['udi_profile']=='GS1' and editor._barcode_draft['barcode_type']=='gs1_datamatrix'
    editor._barcode_show_page('size')
    set_field(app,editor,'문자 위치','아래')
    set_field(app,editor,'바코드 가로(mm)',10)
    if not editor._barcode_draft['barcode_options']['human_readable']:
        editor._barcode_show_page('hri')
        widget_with_text(editor,'바코드 값 표시',ttk.Checkbutton).invoke()
    settle(app)
    widget_with_text(editor,'확인',ttk.Button).invoke()
    settle(app)
    assert not editor.winfo_exists()
    assert element['udi_profile']=='GS1' and element['barcode_type']=='gs1_datamatrix'
    raw=designer._designer_code_value(element,{})
    path=tmp_path/'verified.cllabel'
    path.write_text(json.dumps(app.template_payload(),ensure_ascii=False),encoding='utf-8')
    reopened=designer.load_template_file(path)['elements'][0]
    assert reopened['udi_profile']=='GS1'
    assert designer._designer_code_value(reopened,{})==raw
    dpi=app._validation_dpi()
    image=app._render_element_bitmap(reopened,{},mm_to_dots(reopened['width'],dpi),mm_to_dots(reopened['height'],dpi),transparent=False)
    decoded=zxingcpp.read_barcode(image.convert('L'))
    assert decoded and decoded.bytes==build_gs1(parse_gs1(raw)).payload.encode('ascii')
    assert ''.join(image.info['hri_lines'])==raw
    from barcode_label_automation.template_output import validate_rows
    assert validate_rows(app.template_payload(),[app.preview_row],app.base_dir,dpi=dpi)==[]


def test_unified_udi_cancel_restores_all_original_values(app):
    element=install_element(app)
    before=deepcopy(element)
    editor=open_editor(app,element)
    controller=choose_purpose(app,editor,'의료기기 UDI')
    assert controller.load_complete_example() and controller.validate(True)
    assert element==before
    widget_with_text(editor,'취소',ttk.Button).invoke()
    settle(app)
    assert element==before


@pytest.mark.parametrize('close_mode',['cancel','escape','window_close'])
def test_invalid_udi_can_always_be_discarded_and_closed(app,close_mode):
    element=install_element(app);before=deepcopy(element)
    editor=open_editor(app,element)
    controller=choose_purpose(app,editor,'의료기기 UDI')
    assert not controller.validate(False)
    if close_mode=='cancel':
        widget_with_text(editor,'취소',ttk.Button).invoke()
    elif close_mode=='escape':
        escape_target=next(w for w in descendants(controller)
                           if isinstance(w,ttk.Entry) and w.winfo_ismapped())
        escape_target.focus_force()
        escape_target.event_generate('<Escape>',when='tail')
    else:
        protocol=editor.protocol('WM_DELETE_WINDOW')
        editor.tk.call(protocol)
    settle(app)
    assert not editor.winfo_exists()
    assert element==before


def test_confirmation_is_atomic_and_cancel_preserves_last_confirmed_barcode(app):
    element=install_element(app);baseline=deepcopy(element)
    editor=open_editor(app,element)
    draft=editor._barcode_draft
    editor._barcode_show_page('data')
    editor._barcode_text_editor.delete('1.0','end')
    editor._barcode_text_editor.insert('1.0','COMMITTED001')
    editor._barcode_text_editor.edit_modified(True)
    settle(app)
    assert element==baseline
    widget_with_text(editor,'확인',ttk.Button).invoke();settle(app)
    assert element['text']=='COMMITTED001'
    assert not editor.winfo_exists()
    committed=deepcopy(element)
    editor=open_editor(app,element)
    editor._barcode_text_editor.delete('1.0','end')
    editor._barcode_text_editor.insert('1.0','')
    editor._barcode_text_editor.edit_modified(True)
    settle(app)
    assert element==committed
    widget_with_text(editor,'취소',ttk.Button).invoke();settle(app)
    assert element==committed


def test_invalid_hri_keeps_code_preview_and_blocks_output(app):
    element=install_element(app)
    element.update(width=10,height=10)
    element['barcode_options']['human_readable']=True
    element['barcode_layout'].update(symbol_width_mm=10,symbol_height_mm=10)
    dpi=app._validation_dpi()
    with pytest.raises(ValueError,match='표시문자'):
        app._render_element_bitmap(element,{},mm_to_dots(10,dpi),mm_to_dots(10,dpi),transparent=False)
    preview=app._render_2d_preview_bitmap(element,{},120,120)
    assert preview.info['layout_error'] and preview.info['symbol_bounds']
    assert zxingcpp.read_barcode(preview.convert('L')).text==element['text']
    assert app._barcode_canvas_bounds(element)


def test_corrective_resize_all_axes_zoom_dpi_then_fit_and_undo(app, monkeypatch):
    app.template['label'].update(width_mm=40,height_mm=20)
    app._load_values_to_controls()
    element=install_element(app)
    for dpi in (203,300,600):
        monkeypatch.setattr(app,'_validation_dpi',lambda:dpi)
        for zoom in (.5,1,1.5,2):
            app.scale=12*zoom
            for dx,dy in ((-10,0),(0,-10),(-10,-10)):
                element.update(x=2,y=2,width=70,height=40)
                element['barcode_layout'].update(symbol_width_mm=20,symbol_height_mm=20,hri_position='right')
                element['barcode_options']['human_readable']=True
                before=deepcopy(element)
                bounds=app._barcode_canvas_bounds(element)
                start=SimpleNamespace(x=bounds[2],y=bounds[3],state=0)
                app.on_canvas_press(start)
                assert app.drag_state.get('mode')=='resize'
                app.on_canvas_drag(SimpleNamespace(x=bounds[2]+dx*app.scale,y=bounds[3]+dy*app.scale,state=0))
                app.on_canvas_release(start)
                assert element['barcode_layout']['symbol_width_mm']<20
                assert element['barcode_layout']['symbol_width_mm']==element['barcode_layout']['symbol_height_mm']
                assert element['width']<70 and element['height']<40
                assert app._barcode_canvas_bounds(element)[2]>app._barcode_canvas_bounds(element)[0]
    # Fit offers an explicit review, preserves data, and participates in undo.
    monkeypatch.setattr(designer.messagebox,'askyesno',lambda *a,**k:True)
    element.update(x=25,y=15,width=60,height=40)
    element['barcode_layout'].update(symbol_width_mm=16,symbol_height_mm=16)
    app._reset_history()
    previous=deepcopy(element)
    app.fit_selected_barcode()
    assert element['x']+element['width']<=40+1e-7
    assert element['y']+element['height']<=20+1e-7
    assert element['text']==previous['text']
    app.undo();settle(app)
    assert app.elements[0]==previous


def test_hibc_udi_import_hri_and_saved_db_binding(app,tmp_path):
    from barcode_label_automation.udi_editor import build_udi_patch
    from barcode_label_automation.hibc import parse_hibc
    element=install_element(app)
    patch=build_udi_patch(element,{},profile='HIBC',code_type='hibcdatamatrix',complete_value='+A123BJC5D6E71G')
    element.update(patch)
    app._reflow_barcode_element(element)
    serialized=designer._normalize_element(element)
    assert serialized['udi_data']['complete_value']=='+A123BJC5D6E71G'
    value=designer._designer_code_value(serialized,{})
    dpi=app._validation_dpi()
    image=app._render_element_bitmap(serialized,{},mm_to_dots(serialized['width'],dpi),mm_to_dots(serialized['height'],dpi),transparent=False)
    decoded=zxingcpp.read_barcode(image.convert('L'))
    assert decoded.text==value=='+A123BJC5D6E71G'
    assert parse_hibc(image.info['hri_value']).encoded_value==value
