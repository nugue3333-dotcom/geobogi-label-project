import hashlib
import json
from pathlib import Path
import pytest
from barcode_label_automation.gs1 import (GS, GS1Element, GS1ValidationError, ai_dictionary,
                                         build_gs1, parse_gs1, search_ai)

GTIN = '(01)09506000134376'


def test_full_dictionary_and_provenance():
    assert len(ai_dictionary()) == 541
    root = Path(__file__).resolve().parents[1] / 'barcode_label_automation/resources'
    metadata = json.loads((root / 'gs1-provenance.json').read_text())
    assert hashlib.sha256((root / 'gs1-syntax-dictionary.txt').read_bytes()).hexdigest() == metadata['sha256']
    assert search_ai('로트')[0].ai == '10'
    assert any(x.ai == '3105' for x in search_ai('WEIGHT'))


@pytest.mark.parametrize('query,ai',[('상품번호','01'),('로트','10'),('시리얼','21'),('일련번호','21'),('소비기한','17'),('SSCC','00'),('포장일','13')])
def test_common_ai_korean_search(query,ai):
    assert any(info.ai==ai for info in search_ai(query))


def test_missing_association_exposes_navigation_and_plain_language():
    from barcode_label_automation.gs1 import requirement_candidates
    with pytest.raises(GS1ValidationError) as caught:
        build_gs1([{'ai':'21','value':'01.03.8006'}])
    assert caught.value.ai=='21'
    assert set(requirement_candidates(caught.value.requirements))=={'01','03','8006'}
    assert '또는' in str(caught.value) and '실제 값' in str(caught.value)


def test_lot_serial_separator_roundtrip():
    hri = GTIN + '(10)LOT123(21)SER001'
    data = build_gs1(parse_gs1(hri))
    assert data.payload == '010950600013437610LOT123' + GS + '21SER001'
    assert build_gs1(parse_gs1(']C1' + data.payload)).hri == hri
    assert not data.payload.startswith(GS)


@pytest.mark.parametrize('date', ['261231', '260200', '240229'])
def test_valid_expiry(date):
    assert build_gs1(parse_gs1(GTIN + '(17)' + date)).hri.endswith(date)


@pytest.mark.parametrize('date', ['260229', '261332', '260431', '260000'])
def test_invalid_expiry(date):
    with pytest.raises(GS1ValidationError):
        build_gs1(parse_gs1(GTIN + '(17)' + date))


@pytest.mark.parametrize('value', ['(01)09506000134377', '(01)0950600013437', '(10)LOT', GTIN+'(10)LOT A', GTIN+'(21)한글'])
def test_invalid_checksum_length_association_charset(value):
    with pytest.raises(GS1ValidationError):
        build_gs1(parse_gs1(value))


def test_row_source_preserves_zero_and_rejects_number():
    items = [GS1Element('01', source_field='GTIN'), {'ai': '21', 'source_field': 'SER'}]
    assert build_gs1(items, {'GTIN': '09506000134376', 'SER': '00001'}).hri.endswith('(21)00001')
    with pytest.raises(GS1ValidationError):
        build_gs1(items, {'GTIN': 9506000134376, 'SER': '00001'})
    with pytest.raises(GS1ValidationError):
        build_gs1(items, {})


def test_fixed_not_predefined_needs_separator():
    # AI 8005 is a six-digit field but lacks the dictionary '*' flag.
    data = build_gs1(parse_gs1(GTIN + '(8005)001234(21)001'))
    assert '8005001234' + GS + '21' in data.payload
    assert parse_gs1(data.payload) == list(data.elements)


def test_requirement_and_exclusion():
    with pytest.raises(GS1ValidationError):
        build_gs1(parse_gs1('(02)09506000134376'))
    assert build_gs1(parse_gs1('(00)000000000000000000(02)09506000134376(37)12'))
    with pytest.raises(GS1ValidationError):
        build_gs1(parse_gs1(GTIN + '(37)12'))


def test_repeated_requirement_groups():
    with pytest.raises(GS1ValidationError):
        build_gs1(parse_gs1(GTIN + '(250)001'))
    assert build_gs1(parse_gs1(GTIN + '(21)A(250)001'))


def test_unsupported_semantic_validator_fails_closed():
    with pytest.raises(GS1ValidationError):
        build_gs1(parse_gs1('(8110)ABC'))


@pytest.mark.parametrize('value', ['88123', '\x1d\x1d0109506000134376', '0109506000134376\x1d', '(88)123'])
def test_malformed_raw(value):
    with pytest.raises(GS1ValidationError):
        parse_gs1(value)


def test_optional_components_and_time():
    assert build_gs1(parse_gs1(GTIN + '(8008)26100823'))
    assert build_gs1(parse_gs1(GTIN + '(8008)261008235959'))
    with pytest.raises(GS1ValidationError):
        build_gs1(parse_gs1(GTIN + '(8008)2610082460'))


def test_duplicate_and_unicode_digits_rejected():
    for value in [GTIN + '(21)A(21)B', '(01)０９５０６０００１３４３７６']:
        with pytest.raises(GS1ValidationError):
            build_gs1(parse_gs1(value))

@pytest.mark.parametrize('name,good,bad', [
    ('yesno','1','2'), ('iso5218','9','3'), ('winding','9','2'),
    ('latitude','1800000000','1800000001'), ('longitude','3600000000','3600000001'),
    ('hyphen','-','A'), ('importeridx','_','!'), ('mediatype','80','79'),
    ('posinseqslash','1/2','2/1'), ('pcenc','NAME%20X','NAME%2X'),
    ('nozeroprefix','1','0'), ('gcppos1','1234A','123A'),
])
def test_reference_common_linters(name, good, bad):
    from barcode_label_automation.gs1 import _lint
    _lint(name,good,'TEST')
    with pytest.raises(GS1ValidationError):
        _lint(name,bad,'TEST')


def _official_linter_vectors():
    import re
    import codecs
    root = Path(__file__).resolve().parents[1] / 'barcode_label_automation/resources'
    result = []
    for name in sorted({l for info in ai_dictionary().values() for c in info.components for l in c.linters}):
        text = (root / f'gs1-lint_{name}.c').read_text(encoding='utf8')
        # These optional custom allocation-lookup tests require a live GCP hook.
        text = re.sub(r'#ifdef GS1_LINTER_CUSTOM_GCP_LOOKUP(?:_H)?.*?#endif', '', text, flags=re.S)
        for outcome, literal in re.findall(r'UNIT_TEST_(PASS|FAIL)\(gs1_lint_'+name+r',\s*((?:"(?:[^"\\]|\\.)*"\s*)+)' , text):
            result.append((name, ''.join(codecs.decode(part, 'unicode_escape') for part in re.findall(r'"((?:[^"\\]|\\.)*)"', literal)), outcome == 'PASS'))
    return result


@pytest.mark.parametrize('name,value,expected', _official_linter_vectors())
def test_official_extended_linter_vectors(name, value, expected):
    from barcode_label_automation.gs1 import _lint
    if expected:
        _lint(name, value, 'TEST')
    else:
        with pytest.raises(GS1ValidationError):
            _lint(name, value, 'TEST')


def test_shipping_country_and_currency_db_bindings():
    elements = [{'ai':'01','source_field':'GTIN'}, {'ai':'422','source_field':'COUNTRY'},
                {'ai':'30','value':'1'}, {'ai':'3932','source_field':'PRICE'}]
    result = build_gs1(elements, {'GTIN':'09506000134376','COUNTRY':'410','PRICE':'410000123'})
    assert result.hri == GTIN + '(422)410(30)1(3932)410000123'
    with pytest.raises(GS1ValidationError):
        build_gs1(elements, {'GTIN':'09506000134376','COUNTRY':'999','PRICE':'410000123'})


@pytest.mark.parametrize('ai', ['00','01','10','11','13','15','17','21','30','37','240','241','400','410'])
@pytest.mark.parametrize('kind', ['gs1_128','gs1_qr','gs1_datamatrix','databarexpanded','databarexpandedstacked'])
def test_complete_example_groups_validated_by_actual_encoder(ai,kind):
    from barcode_label_automation.gs1 import example_elements
    records=example_elements(ai,symbology=kind)
    payload=build_gs1(records)
    assert payload.elements and all(not x['source_field'] for x in records)
    if ai=='37':
        assert [x['ai'] for x in records]==['00','02','37']


def test_all_missing_ai37_requirements_reported_at_once():
    with pytest.raises(GS1ValidationError) as error:
        build_gs1([{'ai':'37','value':'24'}])
    assert error.value.category=='association'
    assert set(error.value.requirements)=={'00','02,8026'}
    assert '00' in str(error.value) and '02' in str(error.value) and '8026' in str(error.value)


def test_udi_date_db_explicit_conversion_preserves_binding():
    from datetime import datetime
    records=[{'ai':'01','value':'09506000134376'},
             {'ai':'11','source_field':'manufactured','value_format':'gs1_date'}]
    result=build_gs1(records,{'manufactured':datetime(2026,10,13)})
    assert result.hri.endswith('(11)261013')
    assert result.elements[-1].source_field=='manufactured'
    assert result.elements[-1].value_format=='gs1_date'


@pytest.mark.parametrize('value',['2026-02-30','2026/10/13',261013,'1999-12-31','2100-01-01'])
def test_invalid_udi_dates_never_auto_correct(value):
    from barcode_label_automation.gs1 import gs1_date
    with pytest.raises(GS1ValidationError):
        gs1_date(value,ai='11')


def test_examples_fail_closed_for_unsupported_ai_and_selected_capacity():
    from barcode_label_automation.gs1 import example_elements
    with pytest.raises(GS1ValidationError):
        example_elements('422')
    with pytest.raises(ValueError):
        example_elements('udi',symbology='gs1_128')
