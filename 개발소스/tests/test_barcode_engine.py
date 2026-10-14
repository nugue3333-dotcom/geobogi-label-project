from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

import pytest
import zxingcpp

from barcode_label_automation.barcode_catalog import BARCODE_TYPES, SAMPLE_VALUES, option_definitions, sample_options
from barcode_label_automation.barcode_engine import BarcodeEncodingError, render_barcode, normalize_options


@pytest.mark.parametrize('symbology', BARCODE_TYPES)
def test_every_registered_barcode_renders_offline(symbology):
    image = render_barcode(symbology, SAMPLE_VALUES[symbology], sample_options(symbology))
    assert image.mode == 'L'
    assert min(image.size) > 0
    assert image.getextrema() == (0, 255)


@pytest.mark.parametrize('symbology', ['qr','datamatrix','pdf417','aztec','code128','code39extended'])
def test_original_data_preserved(symbology):
    value = 'https://example.com/p?id=001&lot=A/B' if symbology != 'code39extended' else 'a#001?/='
    image = render_barcode(symbology, value, {'cell_size':3} if symbology in {'qr','datamatrix','pdf417','aztec'} else {'module_width':3})
    result = zxingcpp.read_barcode(image)
    assert result is not None
    assert result.text == value


@pytest.mark.parametrize('symbology,aim', [('gs1_128',']C1'),('gs1_datamatrix',']d2'),('gs1_qr',']Q3')])
def test_gs1_multiple_ai_separator_and_identifier(symbology, aim):
    result = zxingcpp.read_barcode(render_barcode(symbology, SAMPLE_VALUES[symbology], {'module_width':3} if symbology == 'gs1_128' else {'cell_size':3}))
    assert result is not None
    assert result.symbology_identifier == aim
    assert bytes(result.bytes) == b'010950600013437610LOT123\x1d21SER001'


def test_qr_version_ecc_mask_and_integer_modules():
    a = render_barcode('qr','12345',{'version':2,'qr_ecc':'H','data_mask':0,'cell_size':2})
    b = render_barcode('qr','12345',{'version':2,'qr_ecc':'H','data_mask':1,'cell_size':2})
    assert a.size == (66,66)
    assert a.tobytes() != b.tobytes()
    assert zxingcpp.read_barcode(a).ec_level == 'H'
    assert zxingcpp.read_barcode(a).text == '12345'


def test_pdf417_rows_columns_security_and_row_height():
    a = render_barcode('pdf417','12345',{'pdf417_rows':10,'pdf417_columns':5,'pdf417_security':2})
    b = render_barcode('pdf417','12345',{'pdf417_rows':10,'pdf417_columns':5,'pdf417_security':4})
    c = render_barcode('pdf417','12345',{'pdf417_rows':10,'pdf417_columns':5,'pdf417_module_height':6})
    assert a.size == (158,34)
    assert a.tobytes() != b.tobytes()
    assert c.size == (158,64)
    assert zxingcpp.read_barcode(a.resize((316,68))).text == '12345'


def test_datamatrix_version_and_square():
    assert render_barcode('datamatrix','12345',{'version':3}).size == (16,16)
    image = render_barcode('datamatrix','12345',{'force_square':True})
    assert image.width == image.height


@pytest.mark.parametrize('symbology,value,options', [
    ('qr','test',{'version':41}),('qr','test',{'data_mask':8}),
    ('qr','test',{'pdf417_columns':5}),('qr','test',{'version':1.5}),
    ('qr','test',{'unknown_option':True}),('code128','한글',{}),
    ('gs1_128','(01)09506000134377',{}),('qr','',{}),
    ('iQR','123',{}),('code39','ABC',{'check_digit':'mod11'}),
])
def test_invalid_or_non_applicable_settings_are_not_ignored(symbology,value,options):
    with pytest.raises(ValueError):
        render_barcode(symbology,value,options)


def test_cache_isolation_and_long_data():
    image = render_barcode('qr','A'*80)
    image.putpixel((0,0),0)
    again = render_barcode('qr','A'*80,{'cell_size':3})
    assert zxingcpp.read_barcode(again).text == 'A'*80


def test_gs1_literal_parentheses_and_no_implicit_padding():
    result = zxingcpp.read_barcode(render_barcode('gs1_qr','(01)09506000134376(10)A(B)C',{'cell_size':3}))
    assert result.bytes == b'010950600013437610A(B)C'
    with pytest.raises(ValueError):
        render_barcode('ean13','1234')
    with pytest.raises(ValueError):
        render_barcode('code39','lowercase')


def test_vendor_binary_and_corresponding_source_pinned():
    root = Path(__file__).resolve().parents[1]
    vendor = root/'barcode_label_automation/vendor/zint'
    provenance = json.loads((vendor/'provenance.json').read_text())
    assert hashlib.sha256((vendor/'zint.exe').read_bytes()).hexdigest() == provenance['binary_sha256']
    assert hashlib.sha256((root/provenance['source_archive']).read_bytes()).hexdigest() == provenance['source_sha256']
    assert 'GNU GENERAL PUBLIC LICENSE' in (vendor/'COPYING').read_text()


def test_standalone_encoder_has_no_visual_cpp_dependency(tmp_path):
    import pefile
    root = Path(__file__).resolve().parents[1]
    source = root/'barcode_label_automation/vendor/zint/zint.exe'
    executable = tmp_path/'zint.exe'
    shutil.copy2(source, executable)
    pe = pefile.PE(str(executable))
    assert pe.FILE_HEADER.Machine == 0x8664
    imports = [entry.dll.decode().lower() for entry in pe.DIRECTORY_ENTRY_IMPORT]
    assert all(name == 'kernel32.dll' or name.startswith('api-ms-win-crt-') for name in imports)
    assert not any('vcruntime' in name or 'msvcp' in name for name in imports)
    (tmp_path/'input.txt').write_text('https://example.com/p?id=001&lot=A/B',encoding='utf-8')
    result = subprocess.run([str(executable),'--barcode=58','--notext','--scale=1.5',
                             '--quietzones','--input=input.txt','--output=barcode.bmp'],
                            cwd=tmp_path, env={'SystemRoot':os.environ['SystemRoot'],
                                              'PATH':os.environ['SystemRoot']+'\\System32'},
                            capture_output=True,timeout=10,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert result.returncode == 0, result.stderr
    from PIL import Image
    with Image.open(tmp_path/'barcode.bmp') as image:
        assert zxingcpp.read_barcode(image).text == 'https://example.com/p?id=001&lot=A/B'
