from copy import deepcopy
import tkinter as tk
from tkinter import ttk
import pytest
from test_barcode_first_ui import app, settle, install_element, open_editor, widget_with_text, field
from barcode_label_automation import label_designer_app as designer
from barcode_label_automation.value_rules import compile_generated_labels


def test_text_serial_is_inline_without_database_and_cancel_is_safe(app):
    element=designer._element('text','000001',2,2,25,8)
    app.elements=[element];app.selected_id=str(element['id']);app.selected_ids={str(element['id'])};app._reset_history()
    old=deepcopy(element);rules=deepcopy(app.template.get('value_rules',[]));profile=app.template.get('value_profile_id')
    editor=open_editor(app,element)
    assert editor._property_nav.selection()==('data',)
    editor._property_show_page('serial');settle(app)
    widget=editor._serial_editor
    widget.mode.set('increase');widget.start.set('000001');widget.digits.set('6');settle(app)
    assert widget.status.get()==''
    assert '000001' in widget.preview.get() and '000005' in widget.preview.get()
    assert app.template.get('value_rules',[])==rules
    widget_with_text(editor,'취소',ttk.Button).invoke();settle(app)
    assert element==old and app.template.get('value_rules',[])==rules and app.template.get('value_profile_id')==profile


def test_barcode_serial_confirmation_binds_generated_value_without_db_ui(app):
    element=install_element(app);element['text']='000001';element['field']=''
    old=deepcopy(element);editor=open_editor(app,element)
    editor._barcode_show_page('serial');settle(app)
    widget=editor._serial_editor
    widget.mode.set('increase');widget.start.set('000001');widget.digits.set('6');settle(app)
    assert widget.status.get()==''
    assert app.template.get('value_rules',[])==[] and element==old
    editor._barcode_show_page('data');settle(app)
    assert not any(w.winfo_ismapped() for w in editor._barcode_pages['data'].winfo_children() if isinstance(w,ttk.Combobox))
    widget_with_text(editor,'확인',ttk.Button).invoke();settle(app)
    assert not editor.winfo_exists()
    name=element['field'];assert name and element['text']=='{{'+name+'}}'
    assert app.template['value_rules'][0]['start']==1
    values=compile_generated_labels([{}],[3],app.template['value_rules'])
    assert [x.row[name] for x in values]==['000001','000002','000003']


def test_gs1_serial_targets_ai21_and_never_increments_whole_payload(app):
    element=install_element(app)
    editor=open_editor(app,element)
    widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button).invoke();settle(app)
    controller=editor._barcode_controllers['active']
    assert controller.load_complete_example();settle(app)
    selector=field(controller,'선택 AI');selector.set('21 · 일련번호');selector.event_generate('<<ComboboxSelected>>');settle(app)
    value=field(controller,'고정값');value.delete(0,'end');value.insert(0,'000001');settle(app)
    widget_with_text(controller,'추가',ttk.Button).invoke();settle(app)
    assert any(item['ai']=='21' for item in controller.get_records())
    editor._barcode_show_page('serial');settle(app)
    widget=editor._serial_editor
    widget.mode.set('increase');widget.start.set('000001');widget.digits.set('6');settle(app)
    assert widget.status.get()==''
    widget_with_text(editor,'확인',ttk.Button).invoke();settle(app)
    assert not editor.winfo_exists()
    item=next(item for item in element['gs1_elements'] if item['ai']=='21')
    assert item['source_field']==app.template['value_rules'][0]['name']
    generated=compile_generated_labels([{}],[2],app.template['value_rules'])
    assert [row.row[item['source_field']] for row in generated]==['000001','000002']
    actual=[designer._designer_code_value(element, row.row) for row in generated]
    assert actual[0].endswith('(21)000001') and actual[1].endswith('(21)000002')


def test_turning_new_serial_back_off_restores_original_value(app):
    element=install_element(app); element['text']='123456'; element['field']=''
    editor=open_editor(app,element)
    editor._barcode_show_page('serial');settle(app)
    widget=editor._serial_editor
    widget.mode.set('increase');settle(app)
    widget.mode.set('off');settle(app)
    widget_with_text(editor,'확인',ttk.Button).invoke();settle(app)
    assert not editor.winfo_exists()
    assert element['text']=='123456' and element['field']==''
    assert not app.template.get('value_rules')


def test_source_switch_requires_serial_disable_and_does_not_lose_draft(app):
    element=install_element(app);element['text']='123456';element['field']=''
    editor=open_editor(app,element)
    editor._barcode_show_page('serial');settle(app)
    editor._serial_editor.mode.set('increase');settle(app)
    editor._barcode_show_page('data');settle(app)
    widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button).invoke();settle(app)
    assert editor._barcode_source_kind_var.get()=='general'
    assert editor._serial_editor.mode.get()=='increase'
    editor._barcode_show_page('serial');editor._serial_editor.mode.set('off');settle(app)
    editor._barcode_show_page('data');widget_with_text(editor,'GS1 데이터로 설정…',ttk.Button).invoke();settle(app)
    assert editor._barcode_source_kind_var.get()=='gs1'


def test_designer_serial_print_quantity_uses_one_job_interval(tmp_path):
    import json
    from test_serial_job_options import setup_saved
    from barcode_label_automation.value_jobs import ValueJobStore
    config, path = setup_saved(tmp_path)
    app = designer.LabelDesignerApp.__new__(designer.LabelDesignerApp)
    app.base_dir = tmp_path
    app.config_path = config
    app.template_path = path
    app.template = json.loads(path.read_text(encoding='utf-8'))
    app.elements = app.template['elements']
    rows, job = app._generated_output_rows([{}], [6], reserve=False, copies_per_serial=2)
    assert [(r['번호'], r['print_qty']) for r in rows] == [('000001','2'),('000002','2'),('000003','2')]
    assert job is None and not ValueJobStore(tmp_path).path.exists()
    rows, job = app._generated_output_rows([{}], [6], reserve=True, copies_per_serial=2)
    assert [(r['번호'], r['print_qty']) for r in rows] == [('000001','2'),('000002','2'),('000003','2')]
    assert job is not None
    assert ValueJobStore(tmp_path).peek_start_overrides('a'*32, app.template['value_rules'])=={'번호':4}


@pytest.mark.parametrize('kind,expected,field_label', [
    ('image', ['그림','위치·크기'], '그림 파일'),
    ('line', ['모양','위치·크기'], '선 두께(mm)'),
    ('box', ['모양','위치·크기'], '선 두께(mm)'),
    ('table', ['표 구성','셀 내용','위치·크기'], '행 수'),
])
def test_non_text_object_has_focused_properties_and_cancel(app, kind, expected, field_label):
    element=designer._element(kind, '', 2, 2, 25, 8)
    if kind=='image': element['image_path']='assets/images/example.png'
    app.elements=[element];app.selected_id=str(element['id']);app.selected_ids={str(element['id'])}
    original=deepcopy(element)
    app.open_element_editor(element);settle(app)
    editor=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='요소 편집')
    nav=editor._property_nav
    assert [nav.item(item,'text') for item in nav.get_children()]==expected
    assert widget_with_text(editor,field_label,ttk.Label).winfo_ismapped()
    assert not any(w.winfo_ismapped() for w in editor._property_pages['data'].winfo_children() if isinstance(w,ttk.Combobox))
    editor._property_show_page('size');settle(app)
    assert widget_with_text(editor,'왼쪽 위치(mm)',ttk.Label).winfo_ismapped()
    width=field(editor._property_pages['size'],'전체 가로(mm)')
    width.delete(0,'end');width.insert(0,'31');settle(app)
    widget_with_text(editor,'취소',ttk.Button).invoke();settle(app)
    assert element==original
    app.open_element_editor(element);settle(app)
    editor=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='요소 편집')
    editor._property_show_page('size');settle(app)
    width=field(editor._property_pages['size'],'전체 가로(mm)')
    width.delete(0,'end');width.insert(0,'31');settle(app)
    widget_with_text(editor,'확인',ttk.Button).invoke();settle(app)
    assert not editor.winfo_exists() and element['width']==31
    if kind=='image': assert element['image_path']==original['image_path']
    if kind=='table': assert element['table_rows']==original['table_rows'] and element['table_cols']==original['table_cols']
