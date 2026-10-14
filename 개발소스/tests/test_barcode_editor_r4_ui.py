"""Visible, transactional barcode properties flows. Each runs in a fresh Tk process."""
from copy import deepcopy
from tkinter import ttk
import pytest
import zxingcpp
from test_barcode_first_ui import app, settle, install_element, open_editor, widget_with_text, descendants


@pytest.mark.parametrize('width,height', [(1280,800),(1024,740),(840,620)])
def test_initial_data_visible_gs1_and_footer_with_persistent_preview(app, width, height):
    element = install_element(app)
    editor = open_editor(app, element)
    editor.geometry(f'{width}x{height}+5+5'); settle(app)
    assert editor._barcode_nav.selection() == ('data',)
    assert editor._barcode_pages['data'].winfo_ismapped()
    for text in ('GS1 데이터로 설정…','적용','확인','취소'):
        control = widget_with_text(editor,text,ttk.Button)
        assert control.winfo_ismapped()
        assert 0 <= control.winfo_rooty()-editor.winfo_rooty() < height-15
        if text=='GS1 데이터로 설정…':
            viewport=editor._barcode_pages['data']
            assert viewport.winfo_rooty() <= control.winfo_rooty()
            assert control.winfo_rooty()+control.winfo_height() <= viewport.winfo_rooty()+viewport.winfo_height()
    panel = editor._barcode_preview_panel
    assert not panel.winfo_ismapped()
    assert widget_with_text(editor, '미리보기', ttk.Button).winfo_ismapped()
    assert panel.original is not None
    assert zxingcpp.read_barcode(panel.original.convert('L')).text == element['text']
    assert panel.status.master is not panel.canvas
    assert panel.result['value'] == element['text']
    assert len(editor._barcode_nav.get_children()) == 3
    from pathlib import Path
    from PIL import ImageGrab
    output=Path(__file__).resolve().parents[1]/'outputs/editor-r4'
    output.mkdir(parents=True,exist_ok=True)
    editor.lift();editor.attributes('-topmost',True);editor.focus_force();settle(app)
    import time
    time.sleep(.35)
    settle(app)
    x,y=editor.winfo_rootx(),editor.winfo_rooty()
    ImageGrab.grab(bbox=(x,y,x+width,y+height),all_screens=True).save(output/f'data-{width}.png')


def test_general_gs1_udi_drafts_return_without_data_loss(app):
    element = install_element(app); before=deepcopy(element)
    editor=open_editor(app,element)
    widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button).invoke();settle(app)
    gs1=editor._barcode_controllers['active']
    assert editor._barcode_source_kind_var.get()=='gs1'
    assert gs1.load_complete_example()
    settle(app)
    gs1_text=editor._barcode_draft['text']
    assert gs1_text and editor._barcode_preview_panel.original is not None
    editor._barcode_show_page('data')
    widget_with_text(editor,'일반 데이터 원본으로 전환',ttk.Button).invoke();settle(app)
    assert editor._barcode_draft['text']==before['text']
    assert editor._barcode_draft['barcode_type']==before['barcode_type']
    widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button).invoke();settle(app)
    assert editor._barcode_controllers['active'] is gs1
    assert editor._barcode_draft['text']==gs1_text
    editor._barcode_show_page('data');editor._barcode_option_menu.invoke(0);settle(app)
    udi=editor._barcode_controllers['active']
    assert udi.load_complete_example();settle(app)
    editor._barcode_show_page('data')
    widget_with_text(editor,'일반 데이터 원본으로 전환',ttk.Button).invoke();settle(app)
    assert editor._barcode_draft['text']==before['text']
    assert element==before
    widget_with_text(editor,'취소',ttk.Button).invoke();settle(app)
    assert element==before


def test_invalid_data_clears_stale_preview_and_apply_is_blocked(app):
    element=install_element(app);before=deepcopy(element)
    editor=open_editor(app,element)
    widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button).invoke();settle(app)
    assert editor._barcode_preview_panel.original is None
    assert editor._barcode_preview_panel.status_var.get()
    widget_with_text(editor,'적용',ttk.Button).invoke();settle(app)
    assert element==before and editor.winfo_exists()
    assert not any('출력 원본으로 사용' in str(w.cget('text')) for w in descendants(editor) if isinstance(w,ttk.Checkbutton))
    widget_with_text(editor,'취소',ttk.Button).invoke();settle(app)
    assert element==before


def test_db_preview_row_restores_original_and_empty_general_cannot_apply(app):
    element=install_element(app)
    element.update(text='{{serial}}',field='serial')
    app.db_rows=[{'serial':'ROW001'},{'serial':'ROW002'}]
    app.preview_row=app.db_rows[0]
    original_row=app.preview_row
    editor=open_editor(app,element);panel=editor._barcode_preview_panel
    panel.move_row(1);settle(app)
    assert panel.result['value']=='ROW002'
    assert zxingcpp.read_barcode(panel.original.convert('L')).text=='ROW002'
    widget_with_text(editor,'취소',ttk.Button).invoke();settle(app)
    assert app.preview_row is original_row
    element.update(text='ABC001',field='')
    before=deepcopy(element)
    editor=open_editor(app,element)
    editor._barcode_text_editor.delete('1.0','end')
    editor._barcode_text_editor.edit_modified(True);settle(app)
    widget_with_text(editor,'적용',ttk.Button).invoke();settle(app)
    assert element==before
    assert '바코드 값' in editor._barcode_editor_status_var.get()


def test_preview_one_bit_white_pixels_and_zoom_close(app):
    from PIL import Image
    element=install_element(app)
    editor=open_editor(app,element);panel=editor._barcode_preview_panel
    bitmap=Image.new('1',(100,50),1)
    bitmap.putpixel((5,5),0)
    panel.set_result(bitmap,value='ABC',hri='ABC',metrics='203 dpi')
    panel.set_mode('actual');settle(app)
    panel.draw()
    assert panel.tk.call(str(panel.photo),'get',50,25)==(255,255,255)
    assert panel.tk.call(str(panel.photo),'get',5,5)==(0,0,0)
    panel.open_large();settle(app)
    enlarged=next(w for w in descendants(editor) if getattr(w,'title',lambda:'' )()=='현재 편집 초안 · 확대 미리보기')
    widget_with_text(enlarged,'닫기',ttk.Button).invoke();settle(app)
    assert not enlarged.winfo_exists() and editor.grab_current() is editor


def test_gs1_source_cannot_silently_encode_as_ordinary_barcode(app):
    from barcode_label_automation import label_designer_app as designer
    element=install_element(app);before=deepcopy(element)
    editor=open_editor(app,element)
    widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button).invoke();settle(app)
    assert editor._barcode_controllers['active'].load_complete_example();settle(app)
    editor._barcode_code_var.set(designer.BARCODE_TYPES['code128']);settle(app)
    assert editor._barcode_preview_panel.original is None
    widget_with_text(editor,'적용',ttk.Button).invoke();settle(app)
    assert element==before
    assert 'GS1 바코드 종류' in editor._barcode_editor_status_var.get()
