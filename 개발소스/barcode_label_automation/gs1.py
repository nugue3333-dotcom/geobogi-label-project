"""GS1 element strings backed by the pinned official syntax dictionary.

Unknown semantic linters fail closed by default; catalogue coverage is not a
claim that every GS1 linter or company-prefix allocation has been verified.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
import json
import re
import string
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Sequence

GS = "\x1d"
DICTIONARY_RELEASE = "2026-01-27"
CSET82 = set('!"%&\'()*+,-./:;<=>?_' + string.ascii_letters + string.digits)
CSET39 = set('#-/' + string.ascii_uppercase + string.digits)


class GS1ValidationError(ValueError):
    """Invalid, ambiguous, or not fully supported GS1 input."""

    def __init__(self, message: str, *, ai: str = '', requirements: tuple[str, ...] = (), category: str = 'value', affected_ais: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        matched = re.match(r'\((\d{2,4})\)', message)
        self.ai = ai or (matched.group(1) if matched else '')
        self.requirements = requirements
        self.category = category
        self.affected_ais = affected_ais or ((self.ai,) if self.ai else ())


AI_NAMES = {
    '00': '물류단위 SSCC', '01': '상품식별번호 GTIN', '02': '내용물 상품번호 GTIN',
    '03': '주문생산 상품번호 GTIN', '10': '배치/로트', '11': '생산일', '12': '납기일',
    '13': '포장일', '15': '품질유지기한', '16': '판매기한', '17': '사용기한',
    '20': '상품 변형 번호', '21': '일련번호', '22': '소비자 상품 변형',
    '30': '가변 수량', '37': '포함 수량', '240': '추가 상품번호',
    '241': '고객 부품번호', '250': '추가 일련번호', '251': '원본 참조 번호',
    '400': '주문번호', '410': '배송지 위치번호 GLN', '411': '청구처 위치번호 GLN',
    '412': '공급처 위치번호 GLN', '414': '실제 위치번호 GLN', '420': '배송지 우편번호',
    '8006': '개별 거래 품목 ITIP', '8020': '지급 참조 번호',
}
AI_SEARCH_ALIASES = {
    '00': '박스 물류 팔레트 배송', '01': '상품번호 제품번호 품목번호 상품식별번호',
    '10': '로트 롯트 LOT 배치 생산번호', '15': '유통기한 품질기한',
    '17': '소비기한 유효기한 만료일', '21': '시리얼 serial 제조번호',
}
COMMON_AIS = ('00', '01', '10', '11', '13', '15', '17', '21', '30', '37', '240', '241', '400', '410')
AI_EXAMPLES = {'00': '106141411234567897', '01': '09506000134376', '10': 'LOT001',
               '11': '261008', '13': '261008', '15': '271008', '17': '271008',
               '21': 'SER0001', '30': '12', '37': '24', '240': 'PART001',
               '241': 'CUSTOMER001', '400': 'ORDER001', '410': '9506000134352'}


@dataclass(frozen=True)
class AIComponent:
    charset: str
    min_length: int
    max_length: int
    optional: bool
    linters: tuple[str, ...]


@dataclass(frozen=True)
class AIInfo:
    ai: str
    title: str
    min_length: int
    max_length: int
    predefined_length: bool
    components: tuple[AIComponent, ...]
    requirements: tuple[str, ...]
    exclusions: tuple[str, ...]

    @property
    def label(self) -> str:
        return AI_NAMES.get(self.ai, self.title)


@dataclass(frozen=True)
class GS1Element:
    ai: str
    value: str = ''
    source_field: str = ''
    value_format: str = ''


@dataclass(frozen=True)
class GS1Payload:
    payload: str
    hri: str
    elements: tuple[GS1Element, ...]
    warnings: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def ai_dictionary() -> dict[str, AIInfo]:
    result = {}
    text = (Path(__file__).parent / 'resources' / 'gs1-syntax-dictionary.txt').read_text(encoding='utf-8')
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        body, _, title = line.partition('#')
        tokens = body.split()
        pattern = tokens.pop(0)
        flags = tokens.pop(0) if tokens and not re.match(r'\[?[NXYZ]', tokens[0]) else ''
        components, requirements, exclusions = [], [], []
        for token in tokens:
            match = re.fullmatch(r'(\[?)([NXYZ])(\.\.)?(\d+)(\]?)(.*)', token)
            if match:
                opening, charset, variable, length, closing, suffix = match.groups()
                optional = bool(opening)
                maximum = int(length)
                components.append(AIComponent(charset, 0 if optional else (1 if variable else maximum),
                                               maximum, optional, tuple(x for x in suffix.lstrip(',').split(',') if x)))
            elif token.startswith('req='):
                requirements.append(token[4:])
            elif token.startswith('ex='):
                exclusions.extend(token[3:].split(','))
        if not components:
            raise RuntimeError(f'GS1 사전 구성 오류: {pattern}')
        if '-' in pattern:
            first, last = pattern.split('-')
            ais = (str(n).zfill(len(first)) for n in range(int(first), int(last) + 1))
        else:
            ais = (pattern,)
        for ai in ais:
            result[ai] = AIInfo(ai, title.strip() or ai, sum(c.min_length for c in components),
                                sum(c.max_length for c in components), '*' in flags,
                                tuple(components), tuple(requirements), tuple(exclusions))
    return result


def search_ai(query: str = '') -> list[AIInfo]:
    query = str(query).casefold().strip()
    return [info for info in ai_dictionary().values()
            if query in f'{info.ai} {info.title} {info.label} {AI_SEARCH_ALIASES.get(info.ai, "")}'.casefold()]


def requirement_candidates(requirements: Sequence[str]) -> tuple[str, ...]:
    """Expand pinned dictionary requirements for navigation, never invent values."""
    patterns = [p for r in requirements for group in r.split(',') for p in group.split('+')]
    return tuple(ai for ai in ai_dictionary() if any(_matches(p, ai) for p in patterns))


def requirement_description(requirement: str) -> str:
    groups = []
    for group in requirement.split(','):
        parts = [f'{AI_NAMES.get(p, "AI")}({p})' for p in group.split('+')]
        groups.append(' 및 '.join(parts))
    return ' 또는 '.join(groups)


def _info(ai: str) -> AIInfo:
    try:
        return ai_dictionary()[ai]
    except KeyError:
        raise GS1ValidationError(f'등록되지 않은 GS1 응용식별자: {ai}') from None


def parse_gs1(value: str) -> list[GS1Element]:
    """Parse bracketed HRI or scanner raw data (optional AIM prefix)."""
    if not isinstance(value, str) or not value:
        raise GS1ValidationError('GS1 데이터가 비어 있습니다.')
    if value.startswith((']C1', ']d2', ']Q3')):
        value = value[3:]
    if value.startswith(GS):
        value = value[1:]
    if value.startswith('('):
        matches = list(re.finditer(r'\((\d{2,4})\)', value))
        if not matches or matches[0].start() != 0:
            raise GS1ValidationError('GS1 괄호 형식이 올바르지 않습니다.')
        result = [GS1Element(m.group(1), value[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(value)])
                  for i, m in enumerate(matches)]
        for item in result:
            _info(item.ai)
        return result
    result, position = [], 0
    while position < len(value):
        if value[position] == GS:
            raise GS1ValidationError('불필요하거나 중복된 GS1 구분자입니다.')
        info = next((ai_dictionary().get(value[position:position+n]) for n in (2, 3, 4)
                     if value[position:position+n] in ai_dictionary()), None)
        if info is None:
            raise GS1ValidationError(f'GS1 식별자를 읽을 수 없습니다: 위치 {position + 1}')
        position += len(info.ai)
        if info.predefined_length:
            end = position + info.max_length
            if end > len(value) or GS in value[position:end]:
                raise GS1ValidationError(f'({info.ai}) 고정 길이 데이터가 부족합니다.')
        else:
            end = value.find(GS, position)
            if end < 0:
                end = len(value)
        result.append(GS1Element(info.ai, value[position:end]))
        position = end
        if position < len(value) and value[position] == GS:
            position += 1
            if position == len(value):
                raise GS1ValidationError('마지막 데이터 뒤의 GS1 구분자는 제거해 주세요.')
    return result


def _elements(elements: Sequence[GS1Element | Mapping], row: Mapping | None) -> tuple[GS1Element, ...]:
    result = []
    for item in elements:
        item = item if isinstance(item, GS1Element) else GS1Element(str(item['ai']), item.get('value', ''), item.get('source_field', ''), item.get('value_format', ''))
        value = item.value
        if item.source_field:
            if row is None or item.source_field not in row:
                raise GS1ValidationError(f'GS1 DB 열을 찾을 수 없습니다: {item.source_field}')
            value = row[item.source_field]
        if item.value_format:
            if item.value_format != 'gs1_date' or item.ai not in {'11','12','13','15','16','17'}:
                raise GS1ValidationError(f'({item.ai}) 지원하지 않는 값 변환 방식입니다.')
            value = gs1_date(value, ai=item.ai)
        if not isinstance(value, str):
            raise GS1ValidationError(f'({item.ai}) 값은 선행 0을 보존하는 문자열이어야 합니다.')
        result.append(GS1Element(item.ai, value, item.source_field, item.value_format))
    if not result:
        raise GS1ValidationError('GS1 응용식별자를 하나 이상 추가해 주세요.')
    return tuple(result)


def _matches(pattern: str, ai: str) -> bool:
    return bool(re.fullmatch(pattern.replace('n', '[0-9]'), ai))


@lru_cache(maxsize=1)
def _linter_tables() -> dict:
    return json.loads((Path(__file__).parent / 'resources' / 'gs1-linter-tables.json').read_text(encoding='utf8'))


def _lint(name: str, value: str, ai: str) -> None:
    invalid = False
    numeric = {'csum', 'yymmd0', 'yymmdd', 'yyyymmdd', 'yyyymmd0', 'hh', 'mi', 'ss',
               'hhmi', 'zero', 'nonzero', 'nozeroprefix', 'pieceoftotal', 'latitude',
               'longitude', 'mediatype'}
    if name in numeric and (not re.fullmatch(r'[0-9]*', value) or (not value and name != 'nozeroprefix')):
        raise GS1ValidationError(f'({ai}) {name} 숫자 검증 실패')
    fixed_lengths = {'yymmd0': 6, 'yymmdd': 6, 'yyyymmdd': 8, 'yyyymmd0': 8,
                     'hh': 2, 'mi': 2, 'ss': 2, 'hhmi': 4}
    if name in fixed_lengths and len(value) != fixed_lengths[name]:
        raise GS1ValidationError(f'({ai}) {name} 길이 검증 실패')
    if name == 'csum':
        invalid = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(reversed(value))) % 10 != 0
    elif name in ('yymmd0', 'yymmdd', 'yyyymmdd', 'yyyymmd0'):
        year_digits = 4 if name.startswith('yyyy') else 2
        year = int(value[:year_digits]) + (2000 if year_digits == 2 else 0)
        month, day = int(value[year_digits:year_digits+2]), int(value[year_digits+2:])
        invalid = not (1 <= month <= 12)
        if not invalid:
            invalid = day > calendar.monthrange(year, month)[1] or day < (0 if name.endswith('0') else 1)
    elif name in ('hh', 'mi', 'ss', 'hhmi'):
        invalid = int(value[:2]) > (23 if name.startswith('hh') else 59)
        if name == 'hhmi':
            invalid = invalid or int(value[2:]) > 59
    elif name == 'zero':
        invalid = any(c != '0' for c in value)
    elif name == 'nonzero':
        invalid = int(value) == 0
    elif name == 'nozeroprefix':
        invalid = value.startswith('0')
    elif name == 'hasnondigit':
        invalid = not value or value.isdigit()
    elif name == 'pieceoftotal':
        invalid = len(value) % 2 != 0
        if not invalid:
            invalid = not (1 <= int(value[:len(value)//2]) <= int(value[len(value)//2:]))
    elif name == 'hyphen':
        invalid = not value or any(c != '-' for c in value)
    elif name in ('yesno', 'iso5218', 'winding'):
        allowed = {'yesno': ('0', '1'), 'iso5218': ('0', '1', '2', '9'), 'winding': ('0', '1', '9')}[name]
        invalid = value not in allowed
    elif name in ('latitude', 'longitude'):
        invalid = len(value) != 10 or int(value) > (1800000000 if name == 'latitude' else 3600000000)
    elif name == 'importeridx':
        invalid = len(value) != 1 or value not in string.ascii_letters + string.digits + '-_'
    elif name == 'mediatype':
        invalid = len(value) != 2 or int(value) not in (*range(1, 11), *range(80, 100))
    elif name == 'posinseqslash':
        match = re.fullmatch(r'([1-9][0-9]*)/([1-9][0-9]*)', value)
        invalid = match is None or int(match.group(1)) > int(match.group(2))
    elif name == 'pcenc':
        invalid = bool(re.search(r'%(?![0-9A-Fa-f]{2})', value))
    elif name in ('iso3166', 'iso3166999', 'iso3166alpha2', 'iso4217', 'packagetype'):
        table = 'iso3166' if name == 'iso3166999' else name
        invalid = value not in _linter_tables()[table] and not (name == 'iso3166999' and value == '999')
    elif name == 'iban':
        invalid = not (10 < len(value) <= 34) or value[:2] not in _linter_tables()['iso3166alpha2']
        invalid = invalid or not re.fullmatch(r'[A-Z0-9]+', value)
        if not invalid:
            digits = ''.join(c if c in string.digits else str(ord(c)-55) for c in value[4:]+value[:4])
            invalid = int(digits) % 97 != 1
    elif name == 'csumalpha':
        chars = ''.join(sorted(CSET82))
        checkchars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
        invalid = not (2 <= len(value) <= 99) or any(c not in CSET82 for c in value[:-2])
        if not invalid:
            primes = _linter_tables()['alpha_primes']
            total = sum(chars.index(c)*primes[len(value)-3-i] for i,c in enumerate(value[:-2])) % 1021
            invalid = value[-2:] != checkchars[total >> 5] + checkchars[total & 31]
    elif name == 'couponcode':
        _lint_coupon(value, ai)
    elif name == 'couponposoffer':
        invalid = not bool(re.fullmatch(r'[0-9]+', value)) or len(value) < 2
        if not invalid:
            invalid = value[0] not in '01' or value[1] not in '0123456'
        if not invalid:
            serial_vli_position = 2 + int(value[1]) + 6 + 6
            invalid = len(value) <= serial_vli_position
            if not invalid:
                invalid = len(value) != serial_vli_position + 1 + int(value[serial_vli_position]) + 6
    elif name in ('gcppos1', 'gcppos2'):
        # Reference linter validates numeric prefix; allocation membership is outside its scope.
        start = 0 if name == 'gcppos1' else 1
        invalid = not re.fullmatch(r'[0-9]{4}', value[start:start+4])
    else:
        raise GS1ValidationError(f'({ai}) 세부 검증 {name}은 아직 지원되지 않아 출력을 차단했습니다.')
    if invalid:
        raise GS1ValidationError(f'({ai}) {name} 검증 실패')


def validate_gs1(elements: Sequence[GS1Element | Mapping], row: Mapping | None = None,
                 strict_associations: bool = True) -> tuple[GS1Element, ...]:
    resolved = _elements(elements, row)
    ais = [e.ai for e in resolved]
    if len(ais) != len(set(ais)):
        raise GS1ValidationError('같은 GS1 응용식별자가 중복되어 있습니다.')
    for element in resolved:
        info = _info(element.ai)
        if not info.min_length <= len(element.value) <= info.max_length:
            raise GS1ValidationError(f'({element.ai}) 길이는 {info.min_length}~{info.max_length}자여야 합니다.')
        offset = 0
        for component in info.components:
            remaining = len(element.value) - offset
            if component.optional and remaining == 0:
                continue
            size = min(component.max_length, remaining)
            part = element.value[offset:offset+size]
            if size < component.min_length or (component.min_length == component.max_length and size != component.max_length):
                raise GS1ValidationError(f'({element.ai}) 구성 필드 길이가 잘못되었습니다.')
            allowed = {'N': set(string.digits), 'X': CSET82, 'Y': CSET39,
                       'Z': set(string.ascii_letters + string.digits + '-_')}[component.charset]
            if any(c not in allowed for c in part):
                raise GS1ValidationError(f'({element.ai}) 허용되지 않는 문자입니다 ({component.charset}).')
            for linter in component.linters:
                _lint(linter, part, element.ai)
            offset += size
        for exclusion in info.exclusions:
            if any(other != element.ai and _matches(exclusion, other) for other in ais):
                raise GS1ValidationError(f'({element.ai})와 {exclusion}은 함께 사용할 수 없습니다.')
    if strict_associations:
        missing = [(element.ai, requirement) for element in resolved
                   for requirement in _info(element.ai).requirements
                   if not any(all(any(_matches(p, other) for other in ais) for p in group.split('+'))
                              for group in requirement.split(','))]
        if missing:
            descriptions = '; '.join(f'{_info(ai).label}({ai}): {requirement_description(req)}'
                                     for ai, req in missing)
            raise GS1ValidationError('필수 조합이 부족합니다. ' + descriptions
                                     + '. 필수 AI를 선택하고 실제 값 또는 DB 열을 추가하세요.',
                                     ai=missing[0][0], requirements=tuple(dict.fromkeys(req for _, req in missing)),
                                     category='association', affected_ais=tuple(dict.fromkeys(ai for ai, _ in missing)))
    return resolved


def build_gs1(elements: Sequence[GS1Element | Mapping], row: Mapping | None = None,
              strict_associations: bool = True) -> GS1Payload:
    resolved = validate_gs1(elements, row, strict_associations)
    payload = ''.join(e.ai + e.value + (GS if i < len(resolved)-1 and not _info(e.ai).predefined_length else '')
                      for i, e in enumerate(resolved))
    return GS1Payload(payload, ''.join(f'({e.ai}){e.value}' for e in resolved), resolved)



def _lint_coupon(value: str, ai: str) -> None:
    """Port of GS1 AISBL Apache-2.0 couponcode reference linter.

    Optional fields must occur in official sequence; no GCP allocation lookup.
    """
    position = 0
    if not re.fullmatch(r'[0-9]+', value):
        raise GS1ValidationError(f'({ai}) 쿠폰은 숫자로 구성해야 합니다.')

    def take(count: int) -> str:
        nonlocal position
        if position + count > len(value):
            raise GS1ValidationError(f'({ai}) 쿠폰 데이터가 부족합니다.')
        result = value[position:position+count]
        position += count
        return result

    def code(allowed: str) -> str:
        result = take(1)
        if result not in allowed:
            raise GS1ValidationError(f'({ai}) 쿠폰 코드가 잘못되었습니다.')
        return result

    def variable(allowed: str, base: int = 0, nine_empty: bool = False, gcp: bool = False) -> str:
        indicator = code(allowed)
        count = 0 if nine_empty and indicator == '9' else int(indicator) + base
        result = take(count)
        if gcp and count:
            _lint('gcppos1', result, ai)
        return result

    def optional(marker: str) -> bool:
        nonlocal position
        if position < len(value) and value[position] == marker:
            position += 1
            return True
        return False

    variable('0123456', 6, gcp=True)
    take(6)  # Offer code
    variable('12345')  # Save value
    variable('12345')  # First purchase requirement
    code('012349')
    take(3)  # Family code
    if optional('1'):
        code('0123')
        variable('12345')
        code('012349')
        take(3)
        variable('01234569', 6, nine_empty=True, gcp=True)
    if optional('2'):
        variable('12345')
        code('012349')
        take(3)
        variable('01234569', 6, nine_empty=True, gcp=True)
    expiry = None
    if optional('3'):
        expiry = take(6)
        _lint('yymmdd', expiry, ai)
    if optional('4'):
        start = take(6)
        _lint('yymmdd', start, ai)
        if expiry is not None and start > expiry:
            raise GS1ValidationError(f'({ai}) 쿠폰 시작일이 종료일보다 늦습니다.')
    if optional('5'):
        variable('0123456789', 6)
    if optional('6'):
        variable('1234567', 6, gcp=True)
    if optional('9'):
        code('01256')
        code('012')
        take(1)
        code('01')
    if position != len(value):
        raise GS1ValidationError(f'({ai}) 쿠폰에 잉여 데이터 또는 잘못된 선택 필드가 있습니다.')


def gs1_date(value: object, *, ai: str = '') -> str:
    """Explicit UDI date conversion; never convert numeric identifiers."""
    if isinstance(value, (datetime, date)):
        if not 2000 <= value.year <= 2099:
            raise GS1ValidationError(f'({ai}) 날짜는 2000~2099년 범위에서 입력하세요.')
        return value.strftime('%y%m%d')
    if isinstance(value, str) and re.fullmatch(r'[0-9]{6}', value):
        _lint('yymmd0', value, ai)
        return value
    if isinstance(value, str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        try:
            return gs1_date(date.fromisoformat(value), ai=ai)
        except ValueError as exc:
            raise GS1ValidationError(f'({ai}) 유효한 날짜 YYYY-MM-DD를 입력하세요: {exc}', ai=ai) from None
    raise GS1ValidationError(f'({ai}) 날짜는 YYYY-MM-DD 또는 YYMMDD 형식이어야 합니다.', ai=ai)


def example_elements(ai_or_profile: str = '01', *, symbology: str = 'gs1_datamatrix') -> list[dict[str, str]]:
    """Reviewed complete TEST groups; encoder validation before returning."""
    from .barcode_engine import render_barcode
    if ai_or_profile == 'udi':
        selected = ('01','11','17','10','21')
    elif ai_or_profile == 'sscc' or ai_or_profile == '37':
        selected = ('00','02','37')
    elif ai_or_profile in {'00','01','400','410'}:
        selected = (ai_or_profile,)
    elif ai_or_profile in AI_EXAMPLES:
        selected = ('01', ai_or_profile)
    else:
        raise GS1ValidationError('이 AI에는 조합 검증된 완성 예제가 없습니다. 실제 발급값을 입력하세요.')
    values = dict(AI_EXAMPLES, **{'02': AI_EXAMPLES['01']})
    records = [{'ai':ai, 'value':values[ai], 'source_field':''} for ai in selected]
    payload = build_gs1(records)
    render_barcode(symbology, payload.hri)
    return records
