from copy import deepcopy
from datetime import date
import tkinter as tk
from tkinter import ttk

import pytest

from barcode_label_automation.udi_editor import build_udi_patch, build_udi_editor, resolve_udi_value
from barcode_label_automation.gs1 import build_gs1


def descriptor(value='',source_field='',enabled=True):
    return {'value':value,'source_field':source_field,'enabled':enabled}


def gs1_descriptors():
    return {'gtin':descriptor('09506000134376'), 'lot':descriptor('LOT001'),
            'serial':descriptor('SER0001'), 'manufacture_date':descriptor('2026-10-13'),
            'expiry_date':descriptor('2027-10-13')}


def test_udi_gs1_structured_dates_and_original_fields_preserved():
    original={'gs1_elements':[{'ai':'240','value':'PART001','source_field':''}]}
    baseline=deepcopy(original); patch=build_udi_patch(original,gs1_descriptors())
    assert original==baseline
    assert build_gs1(patch['gs1_elements']).hri=='(240)PART001(01)09506000134376(10)LOT001(21)SER0001(11)261013(17)271013'
    assert patch['udi_profile']=='GS1'


def test_udi_gs1_db_descriptors_and_date_cells_resolve_every_row():
    data=gs1_descriptors();data['gtin']=descriptor(source_field='DI');data['manufacture_date']=descriptor(source_field='MADE')
    patch=build_udi_patch({},data,row={'DI':'09506000134376','MADE':date(2026,10,13)})
    record=next(x for x in patch['gs1_elements'] if x['ai']=='11')
    assert record=={'ai':'11','value':'','source_field':'MADE','value_format':'gs1_date'}
    assert resolve_udi_value(patch,{'DI':'09506000134376','MADE':'2026-10-14'}).endswith('(11)261014(17)271013')
    with pytest.raises(ValueError):
        resolve_udi_value(patch,{'DI':'09506000134376','MADE':'2026-02-30'})


@pytest.mark.parametrize('field,bad',[('gtin','123'),('gtin',9506000134376),('manufacture_date','2026-02-30'),('expiry_date','2027/10/13')])
def test_invalid_udi_never_partial_mutates_element(field,bad):
    data=gs1_descriptors();data[field]=descriptor(bad);original={'text':'OLD'}
    with pytest.raises(ValueError):
        build_udi_patch(original,data)
    assert original=={'text':'OLD'}


def test_udi_capacity_change_keeps_all_pi():
    data=gs1_descriptors();baseline=deepcopy(data)
    with pytest.raises(ValueError):
        build_udi_patch({},data,code_type='gs1_128')
    patch=build_udi_patch({},data,code_type='gs1_datamatrix')
    assert data==baseline and len(patch['gs1_elements'])==5


def hibc_descriptors():
    return {'lic':descriptor('A123'),'product':descriptor('BJC5D6E'),'package':descriptor('1'),
            'lot':descriptor('LOT001'),'serial':descriptor('SER0001'),
            'manufacture_date':descriptor('2026-10-13'),'expiry_date':descriptor('2027-10-13')}


def test_hibc_full_import_preserves_every_byte():
    patch=build_udi_patch({},hibc_descriptors(),profile='HIBC',code_type='hibcdatamatrix',complete_value='+A123BJC5D6E71G')
    assert patch['text']=='+A123BJC5D6E71G'
    assert resolve_udi_value(patch)==patch['text']
    assert patch['barcode_options']['hibc_input_mode']=='complete'


def test_hibc_udi_structured_bindings_resolve_and_validate():
    from barcode_label_automation.hibc import parse_hibc
    data=hibc_descriptors();data['serial']=descriptor(source_field='SER')
    patch=build_udi_patch({},data,profile='HIBC',code_type='hibcdatamatrix',row={'SER':'SER0001'})
    assert patch['udi_data']['fields']['serial']['source_field']=='SER'
    assert parse_hibc(resolve_udi_value(patch,{'SER':'SER0002'})).serial=='SER0002'
    with pytest.raises(ValueError):
        resolve_udi_value(patch,{})


@pytest.fixture
def root():
    from barcode_label_automation.ui_style import configure_suite_style
    window=tk.Tk();configure_suite_style(window);window.geometry('1100x850+20+20');window.update()
    yield window
    window.destroy()


def test_udi_embedded_example_apply_undo_and_no_nested_popup(root):
    calls=[];frame=build_udi_editor(root,{'barcode_type':'gs1_datamatrix'}, {},[],calls.append)
    frame.pack(fill='both',expand=True);root.update()
    frame.field_vars['gtin'].set('09506000134376');frame.field_vars['serial'].set('ORIGINAL001');frame.enabled_vars['serial'].set(True)
    assert frame.load_complete_example() and frame.validate(True)
    assert calls[-1]['text'].startswith('(01)09506000134376')
    def descendants(w):
        return [c for x in w.winfo_children() for c in [x,*descendants(x)]]
    next(x for x in descendants(frame) if isinstance(x,ttk.Button) and x.cget('text')=='예제 되돌리기').invoke();root.update()
    assert frame.field_vars['serial'].get()=='ORIGINAL001'
    assert not any(isinstance(x,tk.Toplevel) for x in descendants(root))


def test_udi_import_long_gs1_keeps_data_and_symbol_switch_recovers(root):
    switched=[];calls=[];frame=build_udi_editor(root,{'barcode_type':'gs1_128'}, {},[],calls.append,switched.append)
    frame.pack(fill='both',expand=True);root.update()
    raw='(01)09506000134376(11)261013(17)271013(10)LOT001(21)SER0001'
    assert not frame.import_value(raw) and not calls
    assert frame.field_vars['serial'].get()=='SER0001'
    def descendants(w):
        return [c for x in w.winfo_children() for c in [x,*descendants(x)]]
    next(x for x in descendants(frame) if isinstance(x,ttk.Button) and x.cget('text')=='DataMatrix로 변경').invoke();root.update()
    assert switched[-1]=='gs1_datamatrix' and frame.validate(True)
    assert calls[-1]['text']=='(01)09506000134376(10)LOT001(21)SER0001(11)261013(17)271013'
