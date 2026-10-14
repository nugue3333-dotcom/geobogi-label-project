from dataclasses import replace
from configparser import ConfigParser
import json

from PIL import Image
import pytest

from barcode_label_automation import templates
from barcode_label_automation.barcode_catalog import SUPPORTED_BARCODE_TYPES, BARCODE_TYPES
from barcode_label_automation.config import load_config, read_encoder_options
from barcode_label_automation.errors import ConfigError
from barcode_label_automation.excel_reader import LabelRow
from barcode_label_automation.settings_app import PrinterSettings, load_settings, save_settings, validate_settings


def settings(**kw):
    return PrinterSettings(brand='tsc', mode='network', print_method='direct_thermal',
                           ip='127.0.0.1', port=9100, windows_printer_name='auto',
                           width_mm=100, height_mm=100, dpi=203, gap_mm=3, **kw)


def row(value):
    return LabelRow('001', '상품', value, 'LOT', 1, 1)


def test_all_settings_types_match_shared_catalogue():
    from barcode_label_automation.settings_app import BARCODE_TYPE_LABELS
    assert set(BARCODE_TYPE_LABELS) == set(BARCODE_TYPES) == set(SUPPORTED_BARCODE_TYPES)


@pytest.mark.parametrize('kind,options', [('qr', {'qr_ecc':'H','cell_size':3}),
                                        ('gs1_128',{'module_width':2}),
                                        ('maxicode',{'primary':'A% B','mode':4})])
def test_advanced_options_roundtrip(tmp_path,kind,options):
    target=tmp_path/'config.ini'
    original=settings(barcode_type=kind,encoder_options=options)
    save_settings(target,original)
    assert load_settings(target)==original
    assert load_config(target).barcode.encoder_options==options


@pytest.mark.parametrize('value', ['[]','null','{"bogus":1}','{"cell_size":-1}','{"cell_size":true}','{"qr_ecc":"Z"}'])
def test_invalid_options_fail_safely(value):
    parser=ConfigParser(interpolation=None)
    parser.read_dict({'barcode':{'options_json':value}})
    with pytest.raises(ConfigError):
        read_encoder_options(parser,'qr')


def test_settings_validation_reports_bad_options():
    assert not validate_settings(settings(barcode_type='qr',encoder_options={'cell_size':-1})).ok


@pytest.mark.parametrize('language,token',[('tspl',b'BITMAP '),('slcs',b'BMP'),('zpl',b'^GFA')])
@pytest.mark.parametrize('kind',['qr','gs1_128','datamatrix','dotcode'])
def test_shared_encoder_preserves_payload_and_options(monkeypatch,language,token,kind):
    calls=[]
    def render(code,value,options):
        calls.append((code,value,options))
        return Image.new('1',(60,60),1)
    monkeypatch.setattr(templates,'render_barcode',render)
    value='https://example.com/p?id=001&lot=A/B'
    config=replace(templates.default_barcode_config(),barcode_type=kind,one_d_human_readable=False,
                   encoder_options={'human_readable':False})
    output=templates.render_label(language,row(value),100,100,203,barcode_config=config)
    output=output.encode('utf-8') if isinstance(output,str) else output
    assert token in output
    assert calls[0][0:2]==(kind,value)
    assert calls[0][2]['human_readable'] is False


@pytest.mark.parametrize('language',['slcs','tspl','zpl'])
def test_unsafe_native_characters_use_bitmap(monkeypatch,language):
    monkeypatch.setattr(templates,'render_barcode',lambda *args: Image.new('1',(60,60),1))
    config=replace(templates.default_barcode_config(),one_d_human_readable=False)
    value='001"\'~^XZ'
    result=templates.render_label(language,row(value),100,100,203,barcode_config=config)
    encoded=result.encode('utf-8') if isinstance(result,str) else result
    assert value.encode('ascii') not in encoded
    assert b'BITMAP' in encoded or b'BMP' in encoded or b'^GFA' in encoded


def test_oversized_symbols_raise_instead_of_shrinking(monkeypatch):
    monkeypatch.setattr(templates,'render_barcode',lambda *args: Image.new('1',(900,900),1))
    config=replace(templates.default_barcode_config(),barcode_type='qr')
    with pytest.raises(ValueError,match='라벨 영역'):
        templates.render_label('tspl',row('001'),60,40,203,barcode_config=config)


def test_safe_native_one_d_output_preserved():
    result=templates.render_label('zpl',row('001234567890'),60,40,203)
    assert '^BC' in result and '^GFA' not in result


@pytest.mark.parametrize('language',['slcs','tspl','zpl'])
def test_print_bitmap_independently_decodes_original_url(language):
    import io
    import re
    import zxingcpp
    value='https://example.com/p?id=001&lot=A/B'+'A'*80
    config=replace(templates.default_barcode_config(),barcode_type='qr',auto_layout=False,x=10,y=10,
                   encoder_options={'cell_size':2,'qr_ecc':'H'})
    output=templates._barcode_output(language,value,config,2000,2000,{'barcode_y':10})
    if language=='slcs':
        data=output.split(b'\r\n',1)[1]
        image=Image.open(io.BytesIO(data)).copy()
    elif language=='tspl':
        match=re.match(rb'BITMAP \d+,\d+,(\d+),(\d+),0,',output)
        w,h=map(int,match.groups())
        image=Image.frombytes('1',(w*8,h),output[match.end():match.end()+w*h])
    else:
        match=re.search(r'\^GFA,\d+,\d+,(\d+),([0-9A-F]+)\^FS',output)
        w=int(match.group(1)); raw=bytes.fromhex(match.group(2));h=len(raw)//w
        image=Image.frombytes('1',(w*8,h),bytes(byte^255 for byte in raw))
    decoded=zxingcpp.read_barcode(image)
    assert decoded is not None and decoded.text==value


@pytest.mark.parametrize('language',['slcs','tspl','zpl'])
def test_native_invalid_ean_data_rejected(language):
    config=replace(templates.default_barcode_config(),barcode_type='ean13')
    with pytest.raises(ValueError):
        templates.render_label(language,row('ABC123'),100,100,203,barcode_config=config)


@pytest.mark.parametrize('kind', sorted(SUPPORTED_BARCODE_TYPES))
def test_every_catalogue_type_all_printer_languages(kind):
    from barcode_label_automation.barcode_catalog import SAMPLE_VALUES, sample_options
    options={**sample_options(kind),'human_readable':False}
    config=replace(templates.default_barcode_config(),barcode_type=kind,auto_layout=False,x=10,y=10,
                   encoder_options=options)
    for language in ('slcs','tspl','zpl'):
        payload=templates.render_label(language,row(SAMPLE_VALUES[kind]),300,300,203,barcode_config=config)
        assert isinstance(payload,(str,bytes)) and payload
