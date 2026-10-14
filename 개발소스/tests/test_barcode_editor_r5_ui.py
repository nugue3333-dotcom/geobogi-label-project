"""Visible GS1 input, resize and wheel regressions: no example injection."""
from copy import deepcopy
from tkinter import ttk
import tkinter as tk
import time
import pytest
from test_barcode_first_ui import app,settle,install_element,open_editor,widget_with_text,descendants,field

def rect(w):return (w.winfo_rootx(),w.winfo_rooty(),w.winfo_width(),w.winfo_height())
def contained(w,parent):
    x,y,a,b=rect(w);px,py,c,d=rect(parent)
    return x>=px and y>=py and x+a<=px+c and y+b<=py+d
def visible(w):
    assert w.winfo_ismapped(),str(w)
    p=w.master
    while p is not None:
        if isinstance(p,(tk.Canvas,tk.Toplevel)):
            assert contained(w,p),(str(w),rect(w),str(p),rect(p))
            if isinstance(p,tk.Toplevel):
                break
        p=p.master
def click(app,w):
    visible(w)
    w.event_generate('<ButtonPress-1>',x=w.winfo_width()//2,y=w.winfo_height()//2)
    w.event_generate('<ButtonRelease-1>',x=w.winfo_width()//2,y=w.winfo_height()//2)
    settle(app)
def reveal(app,controller,w):
    canvas=controller.scroll_canvas
    for _ in range(35):
        if contained(w,canvas):return
        delta=120 if w.winfo_rooty()<canvas.winfo_rooty() else -120
        canvas.event_generate('<MouseWheel>',delta=delta)
        settle(app)
    assert contained(w,canvas),(rect(w),rect(canvas))

@pytest.mark.parametrize('width,height,factor',[(1262,809,1),(1024,740,1),(840,620,1),(1024,740,1.25),(1024,740,1.5),(1024,740,2)])
def test_visible_gs1_manual_add_edit_validate_apply_close(app,width,height,factor):
    app.tk.call('tk','scaling',4/3*factor)
    from tkinter import font as tkfont
    scaled_font=tkfont.Font(root=app,family='Malgun Gothic',size=-round(14*factor))
    style=ttk.Style(app)
    for name in ('TLabel','TEntry','TCombobox','TButton','Hint.TLabel','Status.TLabel'):
        style.configure(name,font=scaled_font)
    element=install_element(app)
    if width==1262:
        element['barcode_type']='code128'
        element.pop('barcode_layout',None)
    original=deepcopy(element)
    editor=open_editor(app,element)
    editor.geometry(f'{width}x{height}+20+20');settle(app)
    click(app,widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button))
    controller=editor._barcode_controllers['active']
    assert not editor._barcode_preview_panel.winfo_ismapped()
    selector=field(controller,'선택 AI')
    reveal(app,controller,selector);visible(selector)
    selector.set('01 · 상품식별번호 GTIN');selector.event_generate('<<ComboboxSelected>>');settle(app)
    value=field(controller,'고정값');reveal(app,controller,value);visible(value)
    value.insert(0,'09506000134376');settle(app)
    # Live preview must not add a row before the user's Add action.
    assert controller.get_records()==[]
    add=widget_with_text(controller,'추가',ttk.Button);reveal(app,controller,add);click(app,add)
    if factor==1 and width>=1024:
        for text in ('추가','선택 수정','삭제','위로','아래로'):
            visible(widget_with_text(controller,text,ttk.Button))
    assert len(controller.get_records())==1
    value.delete(0,'end');value.insert(0,'09506000134376');settle(app)
    update=widget_with_text(controller,'선택 수정',ttk.Button);reveal(app,controller,update);click(app,update)
    click(app,widget_with_text(controller,'데이터 검증',ttk.Button))
    assert element==original
    click(app,widget_with_text(editor,'적용',ttk.Button))
    assert element['gs1_elements']==[{'ai':'01','value':'09506000134376','source_field':''}]
    click(app,widget_with_text(editor,'미리보기',ttk.Button))
    enlarged=next(w for w in descendants(editor) if isinstance(w,tk.Toplevel) and w.title()=='현재 편집 초안 · 확대 미리보기')
    click(app,widget_with_text(enlarged,'닫기',ttk.Button))
    from pathlib import Path
    from PIL import ImageGrab
    output=Path(__file__).resolve().parents[1]/'outputs/editor-r5'
    output.mkdir(exist_ok=True)
    editor.lift();editor.attributes('-topmost',True);editor.focus_force();settle(app);time.sleep(.35)
    x,y,w,h=rect(editor)
    ImageGrab.grab(bbox=(x,y,x+w,y+h),all_screens=True).save(output/f'gs1-{width}-{factor}.png')
    click(app,widget_with_text(editor,'확인',ttk.Button))
    assert not editor.winfo_exists()

def test_udi_wheel_reaches_last_fields_and_cancel(app):
    element=install_element(app);original=deepcopy(element)
    editor=open_editor(app,element);editor.geometry('840x620+20+20');settle(app)
    editor._barcode_option_menu.invoke(0);settle(app)
    controller=editor._barcode_controllers['active']
    before=controller.scroll_canvas.yview()
    controller.scroll_canvas.event_generate('<MouseWheel>',delta=-120);settle(app)
    assert controller.scroll_canvas.yview()!=before
    button=widget_with_text(controller,'데이터 검증',ttk.Button)
    reveal(app,controller,button);click(app,button)
    click(app,widget_with_text(editor,'취소',ttk.Button))
    assert element==original and not editor.winfo_exists()


def test_manual_gs1_invalid_value_recovery_and_db_rows(app,tmp_path):
    app.db_rows=[{'serial':'ROW001'},{'serial':'ROW002'}]
    app.preview_row=app.db_rows[0]
    app.data_source_path=tmp_path/'qa.xlsx'
    app.data_source_headers=('serial',)
    element=install_element(app);original=deepcopy(element)
    editor=open_editor(app,element);editor.geometry('1024x740+20+20');settle(app)
    click(app,widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button))
    controller=editor._barcode_controllers['active']
    selector=field(controller,'선택 AI')
    reveal(app,controller,selector);selector.set('01 · 상품식별번호 GTIN');selector.event_generate('<<ComboboxSelected>>');settle(app)
    value=field(controller,'고정값');reveal(app,controller,value);value.insert(0,'123');settle(app)
    add=widget_with_text(controller,'추가',ttk.Button);reveal(app,controller,add);click(app,add)
    click(app,widget_with_text(editor,'적용',ttk.Button))
    assert element==original and value.get()=='123'
    reveal(app,controller,value);value.delete(0,'end');value.insert(0,'09506000134376');settle(app)
    update=widget_with_text(controller,'선택 수정',ttk.Button);reveal(app,controller,update);click(app,update)
    reveal(app,controller,selector);selector.set('21 · 일련번호');selector.event_generate('<<ComboboxSelected>>');settle(app)
    source=field(controller,'값 원본');reveal(app,controller,source);source.set('DB 열');source.event_generate('<<ComboboxSelected>>');settle(app)
    binding=field(controller,'DB 열');reveal(app,controller,binding);binding.set('serial');binding.event_generate('<<ComboboxSelected>>');settle(app)
    reveal(app,controller,add);click(app,add)
    assert len(controller.get_records())==2
    click(app,widget_with_text(editor,'적용',ttk.Button));assert 'gs1_elements' in element
    panel=editor._barcode_preview_panel
    assert panel.result['hri'].endswith('(21)ROW001')
    click(app,widget_with_text(editor,'미리보기',ttk.Button))
    enlarged=next(w for w in descendants(editor) if isinstance(w,tk.Toplevel) and w.title()=='현재 편집 초안 · 확대 미리보기')
    from barcode_label_automation.barcode_editor_preview import BarcodeEditorPreview
    popup=next(w for w in descendants(enlarged) if isinstance(w,BarcodeEditorPreview))
    visible(popup.row_combo)
    popup.row_combo.set('2');popup.row_combo.event_generate('<<ComboboxSelected>>');settle(app)
    assert popup.result['hri'].endswith('(21)ROW002')
    assert panel.result['hri'].endswith('(21)ROW002')
    click(app,widget_with_text(enlarged,'닫기',ttk.Button))
    committed=deepcopy(element)
    click(app,widget_with_text(editor,'취소',ttk.Button))
    assert element==committed and app.preview_row==app.db_rows[0]
