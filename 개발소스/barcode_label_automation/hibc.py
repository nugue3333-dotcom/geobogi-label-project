"""HIBC LIC SLS 2.6 (R2026) data validation, independent of the carrier.

References: HIBCC SLS sections 2.1, 2.2, 2.3, 4.1 and appendices B/E/F.
Identifiers are never allocated, padded, uppercased or silently compressed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%'
HIBC_CARRIERS = {
    'hibc128': 'code128', 'hibc39': 'code39',
    'hibcdatamatrix': 'datamatrix', 'hibcqr': 'qr',
    'hibcpdf417': 'pdf417', 'hibcmicropdf417': 'micropdf417',
    'hibcaztec': 'aztec', 'hibccodablockf': 'codablockf',
}


@dataclass(frozen=True)
class HIBCPayload:
    encoded_value: str
    kind: str
    lic: str = ''
    product: str = ''
    package: str = ''
    lot: str = ''
    serial: str = ''
    manufacture_date: str = ''
    expiry_date: str = ''
    quantity: str = ''
    link_character: str = ''


def check_character(body: str) -> str:
    if not isinstance(body, str) or not body:
        raise ValueError('HIBC 데이터는 비어 있지 않은 문자열이어야 합니다.')
    if any(char not in ALPHABET for char in body):
        raise ValueError('HIBC에는 대문자, 숫자와 표준의 구분·체크 문자만 사용할 수 있습니다.')
    return ALPHABET[sum(ALPHABET.index(char) for char in body) % 43]


def _identifier(value: str, name: str, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f'{name}: 문자열로 입력하여 선행 0을 보존하세요.')
    if not value and empty:
        return value
    if not re.fullmatch(r'[A-Z0-9.-]{1,18}', value):
        raise ValueError(f'{name}: 대문자·숫자·점·하이픈 1~18자로 입력하세요.')
    return value


def _date(value: str, name: str) -> str:
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError(f'{name}: YYYY-MM-DD 형식으로 입력하세요.')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(f'{name}: 실제 달력에 있는 날짜를 입력하세요.') from None


def _primary(body: str) -> dict:
    if not re.fullmatch(r'\+[A-Z][A-Z0-9]{3}[A-Z0-9]{1,18}[0-9]', body):
        raise ValueError('HIBC DI: LIC 4자(첫 자 대문자), 제품번호 1~18자(대문자·숫자), 포장단위 0~9를 확인하세요.')
    return {'lic': body[1:5], 'product': body[5:-1], 'package': body[-1]}


def _expiry(value: str, mode: str) -> str:
    """Validate historical date formats without inventing a century.

    Two-digit years retain their encoded representation (not a guessed YYYY).
    """
    length = {'month': 4, '2': 6, '3': 6, '4': 8, '5': 5, '6': 7}[mode]
    if len(value) != length or not value.isascii() or not value.isdigit():
        raise ValueError('HIBC 사용기한: 날짜 길이와 숫자 형식을 확인하세요.')
    if mode == 'month':
        if not 1 <= int(value[:2]) <= 12:
            raise ValueError('HIBC 사용기한: 월은 01~12입니다.')
    elif mode in {'2', '3', '4'}:
        yy, mm, dd = (value[4:6], value[:2], value[2:4]) if mode == '2' else (value[:2], value[2:4], value[4:6])
        try:
            date(2000 + int(yy), int(mm), int(dd))
        except ValueError:
            raise ValueError('HIBC 사용기한: 실제 달력 날짜를 확인하세요.') from None
    else:
        yy, ordinal = int(value[:2]), int(value[2:5])
        year = 2000 + yy
        max_day = (date(year + 1, 1, 1) - date(year, 1, 1)).days
        if not 1 <= ordinal <= max_day:
            raise ValueError('HIBC 사용기한: 율리우스 날짜 범위를 확인하세요.')
    if mode in {'4', '6'} and not 0 <= int(value[-2:]) <= 23:
        raise ValueError('HIBC 사용기한: 시간은 00~23(GMT)입니다.')
    return value


def _secondary(body: str) -> dict:
    segments = body.split('/')
    base = segments[0]
    result = {'lot': '', 'serial': '', 'expiry_date': '', 'manufacture_date': '', 'quantity': ''}
    serial = base.startswith('$$+') or base.startswith('$+')
    if base.startswith('$$'):
        rest = base[3:] if serial else base[2:]
        if not rest or rest[0] not in '01234567':
            raise ValueError('HIBC PI: 날짜 형식 식별자가 없거나 올바르지 않습니다.')
        mode = rest[0]
        if mode in '01':
            size, date_mode, rest = 4, 'month', rest
        elif mode == '7':
            size, date_mode, rest = 0, '', rest[1:]
        else:
            size, date_mode, rest = {'2': 6, '3': 6, '4': 8, '5': 5, '6': 7}[mode], mode, rest[1:]
        if size:
            result['expiry_date'] = _expiry(rest[:size], date_mode)
        identifier = rest[size:]
    elif base.startswith('$'):
        identifier = base[2:] if serial else base[1:]
        if not identifier:
            raise ValueError('HIBC PI: 로트 또는 일련번호가 비어 있습니다.')
    elif re.match(r'[0-9]', base):
        result['expiry_date'] = _expiry(base[:5], '5')
        identifier = base[5:]
        if len(identifier) > 13:
            raise ValueError('HIBC 이전 날짜 형식의 로트는 최대 13자입니다.')
    else:
        raise ValueError('HIBC PI: 지원되는 로트·일련번호·날짜 식별자가 필요합니다.')
    result['serial' if serial else 'lot'] = _identifier(identifier, 'HIBC 일련번호' if serial else 'HIBC 로트', empty=True)
    seen = set()
    for index, field in enumerate(segments[1:]):
        if field.startswith('16D') or field.startswith('14D'):
            key = 'manufacture_date' if field.startswith('16D') else 'expiry_date'
            raw = field[3:]
            if not re.fullmatch(r'[0-9]{8}', raw):
                raise ValueError('HIBC 보충 날짜는 YYYYMMDD 8자리입니다.')
            value = _date(raw[:4] + '-' + raw[4:6] + '-' + raw[6:], 'HIBC 보충 날짜')
        elif field.startswith('S'):
            key, value = 'serial', _identifier(field[1:], 'HIBC 일련번호')
        elif field.startswith('Q'):
            key, value = 'quantity', field[1:]
            if not re.fullmatch(r'[0-9]{1,5}', value) or index != len(segments) - 2:
                raise ValueError('HIBC 수량은 1~5자리 숫자이며 마지막 보충 필드에 위치해야 합니다.')
        else:
            raise ValueError('HIBC 보충 항목: S, 16D, 14D, Q 식별자를 확인하세요.')
        if key in seen or result[key]:
            raise ValueError('HIBC PI: 같은 생산 정보가 중복되었습니다.')
        seen.add(key)
        result[key] = value
    return result


def parse_hibc(value: str, *, primary: str = '') -> HIBCPayload:
    """Validate a completed LIC code; preserve its exact machine bytes.

    A separate secondary's link is checked against `primary` when supplied.
    Without it, only the link character/secondary structure/checksum can be checked.
    """
    if not isinstance(value, str):
        raise ValueError('HIBC 값은 문자열이어야 합니다. 선행 0을 보존하세요.')
    if value.startswith('*') or value.endswith('*'):
        if not (value.startswith('*') and value.endswith('*')):
            raise ValueError('HIBC 표시문자 경계 별표는 양쪽에 있어야 합니다.')
        value = value[1:-1]
    # HRI of both linear and matrix codes represents a space check/link as '_'.
    # Decode only these known positions, then verify the entire Mod43 and data
    # structure. An underscore anywhere else remains an invalid data character.
    if value.startswith('+') and value.endswith('_'):
        value = value[:-1] + ' '
    if value.startswith('+$') or re.match(r'\+[0-9]', value):
        first, *supplements = value[:-1].split('/')
        if first.endswith('_'):
            first = first[:-1] + ' '
            value = '/'.join([first, *supplements]) + value[-1]
    if len(value) < 3 or not value.startswith('+'):
        raise ValueError('완성 HIBC는 + 접두와 마지막 체크문자를 포함해야 합니다.')
    body, checksum = value[:-1], value[-1]
    if check_character(body) != checksum:
        raise ValueError('HIBC 전체 체크문자가 올바르지 않습니다. 원문 끝의 공백 체크문자도 보존하세요.')
    if re.match(r'\+[A-Z]', body):
        di, separator, secondary = body.partition('/')
        fields = _primary(di)
        kind = 'concatenated' if separator else 'primary'
        if separator:
            fields.update(_secondary(secondary))
            if fields.get('quantity') and fields['package'] != '9':
                raise ValueError('HIBC 수량은 포장단위 9에만 사용합니다.')
        return HIBCPayload(value, kind, **fields)
    if body.startswith('+$') or re.match(r'\+[0-9]', body):
        first, *supplements = body[1:].split('/')
        if len(first) < 2:
            raise ValueError('HIBC PI 연결문자가 없습니다.')
        link = first[-1]
        fields = _secondary('/'.join([first[:-1], *supplements]))
        if primary:
            di = parse_hibc(primary)
            if di.kind != 'primary' or di.encoded_value[-1] != link:
                raise ValueError('HIBC PI 연결문자가 제품 DI 체크문자와 일치하지 않습니다.')
            if fields['quantity'] and di.package != '9':
                raise ValueError('HIBC 수량은 포장단위 9에만 사용합니다.')
        return HIBCPayload(value, 'secondary', link_character=link, **fields)
    raise ValueError('HIBC LIC 구조가 아닙니다. 제품 DI 또는 연결된 생산 정보를 확인하세요.')


def resolve_hibc(value: str, input_mode: str = 'auto') -> str:
    if input_mode not in {'auto', 'raw', 'complete'}:
        raise ValueError('HIBC 입력 방식은 auto, raw, complete 중 하나입니다.')
    if not isinstance(value, str):
        raise ValueError('HIBC 값은 문자열이어야 합니다. 선행 0을 보존하세요.')
    if input_mode == 'complete' or input_mode == 'auto' and value.startswith(('+', '*')):
        return parse_hibc(value).encoded_value
    if value.startswith(('+', '*')):
        raise ValueError('원본 생성 입력에는 접두·체크문자를 넣지 마세요. 완성 코드 가져오기를 선택하세요.')
    body = '+' + value
    completed = body + check_character(body)
    return parse_hibc(completed).encoded_value


def compose_hibc(lic: str, product: str, package: str, *, lot: str = '',
                 serial: str = '', manufacture_date: str = '', expiry_date: str = '') -> str:
    """Build DI or concatenated DI/PI. Dates use unambiguous 16D/14D YYYYMMDD."""
    if not all(isinstance(value, str) for value in (lic, product, package, lot, serial, manufacture_date, expiry_date)):
        raise ValueError('HIBC 입력은 문자열이어야 합니다. 선행 0을 보존하세요.')
    if not re.fullmatch(r'[A-Z][A-Z0-9]{3}', lic):
        raise ValueError('HIBC LIC: 첫 자는 대문자이며 대문자·숫자 4자입니다.')
    if not re.fullmatch(r'[A-Z0-9]{1,18}', product):
        raise ValueError('HIBC 제품번호: 대문자·숫자 1~18자로 입력하세요.')
    if not re.fullmatch(r'[0-9]', package):
        raise ValueError('HIBC 포장단위: 0~9 한 자리입니다.')
    body = '+' + lic + product + package
    _primary(body)
    if lot or serial or manufacture_date or expiry_date:
        _identifier(lot, 'HIBC 로트', empty=True)
        _identifier(serial, 'HIBC 일련번호', empty=True)
        body += '/$$7' + lot if lot or not serial else '/$$+7' + serial
        if lot and serial:
            body += '/S' + serial
        if manufacture_date:
            body += '/16D' + _date(manufacture_date, '제조일').replace('-', '')
        if expiry_date:
            body += '/14D' + _date(expiry_date, '사용기한').replace('-', '')
    return parse_hibc(body + check_character(body)).encoded_value


def hibc_hri(value: str, *, linear: bool = False) -> str:
    """Exact data, with official visible checksum-space and linear boundaries."""
    payload = parse_hibc(value)
    text = payload.encoded_value
    if text.endswith(' '):
        text = text[:-1] + '_'
    if payload.kind == 'secondary' and payload.link_character == ' ':
        first, *rest = text[:-1].split('/')
        first = first[:-1] + '_'
        text = '/'.join([first, *rest]) + text[-1]
    return '*' + text + '*' if linear else text
