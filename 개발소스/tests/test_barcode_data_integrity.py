from copy import deepcopy
import pytest
import zxingcpp
from openpyxl import Workbook
from barcode_label_automation.excel_reader import read_labels
from barcode_label_automation.label_designer_app import _normalize_element, _designer_code_value, _render_engine_barcode_box


def test_gs1_db_bindings_survive_normalization_and_resolve_all_fields():
    model = {"id":"gs1", "type":"barcode", "barcode_type":"gs1_128", "text":"", "x":0,"y":0,"width":80,"height":30,
             "gs1_elements":[{"ai":"01","value":"09506000134376","source_field":""},
                              {"ai":"10","value":"","source_field":"lot"},
                              {"ai":"21","value":"","source_field":"serial"}]}
    original=deepcopy(model)
    normalized=_normalize_element(model)
    assert normalized["gs1_elements"] == original["gs1_elements"]
    assert _designer_code_value(normalized,{"lot":"LOT001","serial":"00042"}) == "(01)09506000134376(10)LOT001(21)00042"
    assert model == original


@pytest.mark.parametrize("value", ["https://example.com/p?id=001&lot=A/B&text=%20", "A"*100, " 001 002 "])
def test_designer_qr_roundtrip_keeps_every_character(value):
    element={"barcode_options":{"cell_size":3,"human_readable":False,"quiet_zone":0}}
    image=_render_engine_barcode_box("qr",value,400,400,element)
    decoded=zxingcpp.read_barcode(image)
    assert decoded and decoded.text==value


def test_fixed_module_size_is_rejected_instead_of_shrunk():
    with pytest.raises(ValueError):
        _render_engine_barcode_box("qr","ABC123",80,80,{"barcode_options":{"cell_size":8,"human_readable":False,"quiet_zone":0}})


def test_excel_barcode_string_is_not_trimmed(tmp_path):
    book=Workbook();sheet=book.active
    sheet.append(["item_code","item_name","barcode","lot_no","qty","print_qty"])
    sheet.append(["1","상품"," 001 002 ","",1,1]);target=tmp_path/"labels.xlsx";book.save(target)
    assert read_labels(target)[0].barcode==" 001 002 "
