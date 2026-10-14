"""SLS 2.6 official examples and byte-preserving carrier regressions."""
import pytest
import zxingcpp

from barcode_label_automation.barcode_engine import render_barcode
from barcode_label_automation.hibc import (
    HIBC_CARRIERS, check_character, compose_hibc, hibc_hri, parse_hibc, resolve_hibc,
)

PRIMARY = '+A123BJC5D6E71G'
OFFICIAL = [PRIMARY, '+$$52001510X3GD', '+A99912345/$$52001510X33',
            '+A99912345/$$52001510X3/16D20111212/S77DEFG457',
            '+A99912345/$10X3/16D20111231/14D202001313',
            '+A99912349/$10X3/16D20111231/14D20200131/Q500Z',
            '+A123BJC5D6E71/$$52001510X3C']


@pytest.mark.parametrize('value', OFFICIAL)
def test_official_sls_examples_remain_exact(value):
    assert resolve_hibc(value) == value
    assert parse_hibc(value).encoded_value == value
    assert parse_hibc('*' + value + '*').encoded_value == value


def test_primary_raw_and_import_are_distinct():
    assert resolve_hibc('A123BJC5D6E71') == PRIMARY
    assert resolve_hibc('A123BJC5D6E71', 'raw') == PRIMARY
    assert resolve_hibc(PRIMARY, 'complete') == PRIMARY
    with pytest.raises(ValueError, match='완성 코드'):
        resolve_hibc(PRIMARY, 'raw')
    with pytest.raises(ValueError, match='완성 HIBC'):
        resolve_hibc('A123BJC5D6E71', 'complete')


def test_official_link_is_checked_against_primary_context():
    assert parse_hibc(OFFICIAL[1], primary=PRIMARY).link_character == 'G'
    other = compose_hibc('A123', 'DIFFERENT', '0')
    with pytest.raises(ValueError, match='연결문자'):
        parse_hibc(OFFICIAL[1], primary=other)


def test_compose_preserves_leading_zeros_and_all_pi():
    value = compose_hibc('A123', '0001', '0', lot='000LOT', serial='000SER',
                         manufacture_date='2026-10-13', expiry_date='2027-10-13')
    payload = parse_hibc(value)
    assert payload.lic == 'A123'
    assert payload.product == '0001'
    assert payload.package == '0'
    assert payload.lot == '000LOT'
    assert payload.serial == '000SER'
    assert payload.manufacture_date == '2026-10-13'
    assert payload.expiry_date == '2027-10-13'
    assert value.startswith('+A12300010/$$7000LOT/S000SER/16D20261013/14D20271013')


@pytest.mark.parametrize('fields', [dict(lot='LOT001'), dict(serial='000SER'),
    dict(manufacture_date='2024-02-29'), dict(expiry_date='2027-10-13'), {}])
def test_compose_optional_pi(fields):
    payload = parse_hibc(compose_hibc('A123', 'BJC5D6E7', '1', **fields))
    for key, value in fields.items():
        assert getattr(payload, key) == value


def test_space_checksum_is_preserved_and_visible_in_hri():
    value = next(compose_hibc('A123', str(index), '0') for index in range(1000)
                 if compose_hibc('A123', str(index), '0').endswith(' '))
    assert resolve_hibc(value) == value
    assert hibc_hri(value, linear=True).endswith('_*')
    assert parse_hibc(hibc_hri(value, linear=True)).encoded_value == value
    assert parse_hibc(hibc_hri(value)).encoded_value == value
    with pytest.raises(ValueError):
        resolve_hibc(value.rstrip())


def test_space_link_and_checksum_hri_roundtrip():
    primary = next(compose_hibc('A123', str(index), '0') for index in range(1000)
                   if compose_hibc('A123', str(index), '0').endswith(' '))
    body = '+$$7LOT001 ' + '/16D20261013'
    value = body + check_character(body)
    payload = parse_hibc(value, primary=primary)
    assert payload.link_character == ' '
    assert parse_hibc(hibc_hri(value, linear=True), primary=primary).encoded_value == value
    assert parse_hibc(hibc_hri(value), primary=primary).encoded_value == value


@pytest.mark.parametrize('raw', ['a123BJC5D6E71', 'A123BJC-0010', 'A1230',
    'A123BJC5D6E7X', 'A123' + 'A' * 19 + '0', 'A123PROD 0', '/ACMRN123456/V200912190833'])
def test_invalid_lic_data_is_not_silently_repaired(raw):
    with pytest.raises(ValueError):
        resolve_hibc(raw, 'raw')


@pytest.mark.parametrize('body', [
    '+A123ABC0/$$3270230LOT', '+A123ABC0/$$521366LOT',
    '+A123ABC0/$$7LOT/16D20260230', '+A123ABC0/$$7LOT/14D202710130',
    '+A123ABC0/$$7LOT/SABC/SDEF', '+A123ABC0/$$7LOT/Q12',
    '+A123ABC9/$$7LOT/Q12/SABC', '+A123ABC0/$$7' + 'A' * 19,
    '+A123ABC0/$$7LOT/14D20270101/14D20270101',
])
def test_invalid_pi_with_valid_checksum_is_rejected(body):
    with pytest.raises(ValueError):
        parse_hibc(body + check_character(body))


@pytest.mark.parametrize('fields', [dict(lic='A12'), dict(product='AB-C'), dict(package='01'),
    dict(lot='lower'), dict(expiry_date='2026-02-30'), dict(manufacture_date='26-01-01')])
def test_structured_input_fields_are_validated_before_combining(fields):
    data = dict(lic='A123', product='ABC', package='0')
    data.update(fields)
    with pytest.raises(ValueError):
        compose_hibc(**data)


@pytest.mark.parametrize('symbology', HIBC_CARRIERS)
@pytest.mark.parametrize('value', ['A123BJC5D6E71', PRIMARY])
def test_all_hibc_carriers_use_one_exact_confirmed_payload(symbology, value):
    options = {'module_width': 3} if symbology in {'hibc128', 'hibc39'} else {'cell_size': 3}
    image = render_barcode(symbology, value, options)
    assert image.info['encoded_value'] == PRIMARY
    assert image.info['hri_value'] == ('*' + PRIMARY + '*' if symbology in {'hibc128', 'hibc39'} else PRIMARY)
    # The generic carrier is byte-identical to the validated LIC payload, with no
    # automatic extra '+' or Mod43. Test this for carriers unavailable in ZXing.
    carrier = HIBC_CARRIERS[symbology]
    normalized_options = dict(options)
    if carrier == 'qr':
        normalized_options['qr_ecc'] = 'M'
    generic = render_barcode(carrier, PRIMARY, normalized_options)
    assert image.size == generic.size
    assert image.tobytes() == generic.tobytes()


@pytest.mark.parametrize('symbology', ['hibc128', 'hibc39', 'hibcdatamatrix', 'hibcqr', 'hibcpdf417', 'hibcmicropdf417', 'hibcaztec'])
@pytest.mark.parametrize('value', [PRIMARY, '+A123BJC5D6E71/$$52001510X3C'])
def test_independent_decode_exact_completed_bytes(symbology, value):
    options = {'module_width': 3} if symbology in {'hibc128', 'hibc39'} else {'cell_size': 3}
    image = render_barcode(symbology, value, options)
    decoded = zxingcpp.read_barcode(image, formats=zxingcpp.BarcodeFormat.Code39Std if symbology == 'hibc39' else zxingcpp.BarcodeFormat.AllReadable)
    assert decoded is not None
    assert bytes(decoded.bytes) == value.encode('ascii')


@pytest.mark.parametrize('symbology', ['hibc128', 'hibc39', 'hibcdatamatrix', 'hibcqr', 'hibcpdf417', 'hibcmicropdf417', 'hibcaztec'])
def test_independent_decode_space_checksum(symbology):
    value = next(compose_hibc('A123', str(index), '0') for index in range(1000)
                 if compose_hibc('A123', str(index), '0').endswith(' '))
    options = {'module_width': 3} if symbology in {'hibc128', 'hibc39'} else {'cell_size': 3}
    image = render_barcode(symbology, value, options)
    decoded = zxingcpp.read_barcode(image, formats=zxingcpp.BarcodeFormat.Code39Std if symbology == 'hibc39' else zxingcpp.BarcodeFormat.AllReadable)
    assert decoded is not None
    assert bytes(decoded.bytes) == value.encode('ascii')


def test_bad_complete_checksum_does_not_get_reencoded_with_new_checksum():
    for symbology in HIBC_CARRIERS:
        with pytest.raises(ValueError, match='체크문자'):
            render_barcode(symbology, PRIMARY[:-1] + 'X')


@pytest.mark.parametrize('symbology', HIBC_CARRIERS)
def test_explicit_input_modes_and_cache_metadata(symbology):
    raw = render_barcode(symbology, 'A123BJC5D6E71', {'hibc_input_mode': 'raw'})
    complete = render_barcode(symbology, PRIMARY, {'hibc_input_mode': 'complete'})
    assert raw.tobytes() == complete.tobytes()
    raw.info['encoded_value'] = 'changed'
    assert render_barcode(symbology, PRIMARY).info['encoded_value'] == PRIMARY
    with pytest.raises(ValueError):
        render_barcode(symbology, PRIMARY, {'hibc_input_mode': 'unsupported'})
