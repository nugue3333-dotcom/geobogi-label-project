"""Offline barcode rendering through the separately distributed Zint CLI.

No printer transport, lossy sanitization, image fitting or network access occurs here.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import math
import subprocess
import tempfile

from PIL import Image

from .barcode_catalog import BARCODE_TYPES, BARCODE_1D_TYPES, GS1_TYPES, ZINT_TYPES, option_definitions
from .hibc import HIBC_CARRIERS, hibc_hri, resolve_hibc


class BarcodeEncodingError(ValueError):
    """The selected data/options cannot be represented by this symbology."""


def encoder_path() -> Path:
    path = Path(__file__).parent / 'vendor' / 'zint' / 'zint.exe'
    if not path.is_file():
        raise BarcodeEncodingError('바코드 엔진 파일이 없습니다. 고객 배포 파일을 다시 설치해 주세요.')
    return path


def normalize_options(symbology: str, options: dict | None = None) -> dict:
    definitions = option_definitions(symbology)
    if not definitions:
        raise BarcodeEncodingError(f'지원하지 않는 바코드 종류: {symbology}')
    result = {}
    for key, spec in definitions.items():
        value = (options or {}).get(key, spec['default'])
        if spec.get('type') == 'bool':
            if not isinstance(value, bool):
                raise BarcodeEncodingError(f"{spec['label']}: 참/거짓 값이어야 합니다.")
        elif spec.get('type') == 'text':
            value = str(value)
        elif 'choices' in spec:
            value = str(value)
            if value not in spec['choices']:
                raise BarcodeEncodingError(f"{spec['label']}: 허용하지 않는 선택입니다.")
        elif spec.get('type') == 'float':
            try:
                value = float(value)
            except (ValueError, TypeError, OverflowError):
                raise BarcodeEncodingError(f"{spec['label']}: 숫자를 입력해 주세요.") from None
            if not math.isfinite(value) or not spec['min'] <= value <= spec['max']:
                raise BarcodeEncodingError(f"{spec['label']}: {spec['min']}~{spec['max']} 범위입니다.")
        else:
            try:
                integer = int(value)
                if isinstance(value, bool) or float(value) != integer:
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                raise BarcodeEncodingError(f"{spec['label']}: 정수를 입력해 주세요.") from None
            if not spec['min'] <= integer <= spec['max']:
                raise BarcodeEncodingError(f"{spec['label']}: {spec['min']}~{spec['max']} 범위입니다.")
            value = integer
        result[key] = value
    # Do not silently accept newly supplied options the encoder does not implement.
    # Historical designer dictionaries contain defaults for every format; callers
    # may keep those keys for backwards compatibility, but only defaults are valid.
    historical = {'wide_ratio':2.5,'module_width':0,'cell_size':0,'qr_ecc':'M',
                  'pdf417_rows':0,'pdf417_columns':0,'pdf417_security':2,'check_digit':'auto'}
    for key, value in (options or {}).items():
        if key not in definitions and key not in {'gs1_items'}:
            if key not in historical or value != historical[key]:
                raise BarcodeEncodingError(f'{BARCODE_TYPES[symbology]}에 적용할 수 없는 옵션: {key}')
    return result


def _check_version(symbology: str, options: dict) -> None:
    if symbology in {'dotcode','hanxin','gridmatrix'}:
        if symbology == 'dotcode' and options.get('version'):
            raise BarcodeEncodingError('DotCode는 크기 번호 대신 열 수를 사용합니다.')
        if symbology != 'dotcode' and options.get('columns'):
            raise BarcodeEncodingError('Han Xin/Grid Matrix는 열 수 대신 크기 번호를 사용합니다.')
    if symbology == 'gridmatrix' and options.get('version', 0) > 13:
        raise BarcodeEncodingError('Grid Matrix 크기 번호는 1~13입니다.')
    if symbology in {'code16k','code49'} and options.get('columns'):
        raise BarcodeEncodingError('Code16K/Code49는 열 수를 지정할 수 없습니다.')


def _checksum_options(symbology: str, mode: str) -> list[str]:
    if mode == 'auto':
        return []
    maps = {
        'code39':{'none':0,'mod43':1}, 'code39extended':{'none':0,'mod43':1},
        'code11':{'none':2,'mod11':1},
        'msi':{'none':0,'mod10':1,'mod1010':2,'mod11':3,'mod1110':4,'mod11ncr':5,'mod11ncr10':6},
        'codabar':{'none':0,'mod16':1},
    }
    mapping = maps.get(symbology, {'none':0,'mod10':1})
    if mode not in mapping:
        raise BarcodeEncodingError(f'{BARCODE_TYPES[symbology]}에서 허용하지 않는 체크숫자 방식입니다.')
    return [f'--vers={mapping[mode]}']


def _command_options(symbology: str, options: dict) -> list[str]:
    _check_version(symbology, options)
    dots = options.get('module_width', options.get('cell_size', 0)) or 1
    command = [f'--barcode={ZINT_TYPES[symbology]}', '--notext', '--quietzones', f'--scale={dots / 2}',
               f"--whitesp={options['quiet_zone']}", '--werror']
    for key, flag in {'version':'vers','data_mask':'mask','pdf417_rows':'rows',
                      'pdf417_columns':'cols','pdf417_security':'secure','ecc_level':'secure',
                      'rows':'rows','columns':'cols','mode':'mode','eci':'eci'}.items():
        value = options.get(key)
        if value is not None and (value > 0 or key in {'pdf417_security','data_mask'} and value >= 0):
            command.append(f'--{flag}={value}')
    if options.get('qr_ecc'):
        command.append(f"--secure={('L','M','Q','H').index(options['qr_ecc']) + 1}")
    if options.get('primary'):
        command.append(f"--primary={options['primary']}")
    if options.get('force_square'):
        command.append('--square')
    if options.get('dmre'):
        command.append('--dmre')
    if options.get('bar_height'):
        command.append(f"--height={options['bar_height']:.7g}")
    if options.get('pdf417_module_height'):
        command.extend(['--heightperrow',f"--height={options['pdf417_module_height']:.7g}"])
    if options.get('reader_init'):
        command.append('--init')
    if options.get('structured_append'):
        import re
        if not re.fullmatch(r'[0-9]+,[0-9]+(?:,[A-Za-z0-9]+)?', options['structured_append']):
            raise BarcodeEncodingError('구조적 연결 형식은 번호,총수[,ID]입니다.')
        command.append(f"--structapp={options['structured_append']}")
    if options.get('addon_gap'):
        command.append(f"--addongap={options['addon_gap']}")
    if 'bearer_style' in options:
        style = options['bearer_style']
        command.extend(['--bind' if style == 'bind' else '--box',f"--border={options['bearer_width'] if style != 'none' else 0}"])
    if 'check_digit' in options:
        command.extend(_checksum_options(symbology, options['check_digit']))
    if symbology in GS1_TYPES or symbology.endswith('_composite'):
        command.extend(['--gs1','--gs1parens'])
    return command


@lru_cache(maxsize=128)
def _render_cached(symbology: str, value: str, option_items: tuple) -> Image.Image:
    options = dict(option_items)
    if not value:
        raise BarcodeEncodingError('바코드 데이터가 비어 있습니다.')
    if '\0' in value:
        raise BarcodeEncodingError('NUL 문자는 바코드 데이터에 사용할 수 없습니다.')
    if len(value.encode('utf-8')) > 20000:
        raise BarcodeEncodingError('바코드 데이터가 인코더의 최대 입력 크기를 초과했습니다.')
    required_lengths = {'ean13':(12,13),'ean8':(7,8),'upca':(11,12),
                        'upce':(6,7,8),'ean2':(2,),'ean5':(5,),
                        'itf14':(13,14),'databar':(13,14),'databarlimited':(13,14),
                        'databarstacked':(13,14),'databarstackedomni':(13,14)}
    if symbology in required_lengths:
        main = value.split('+')[0]
        if not main.isascii() or not main.isdigit() or len(main) not in required_lengths[symbology]:
            raise BarcodeEncodingError(f'{BARCODE_TYPES[symbology]} 데이터 길이/숫자 형식을 확인해 주세요. 선행 0은 자동 추가하지 않습니다.')
    if symbology == 'code39' and value != value.upper():
        raise BarcodeEncodingError('Code39는 대문자만 지원합니다. Full ASCII 형식을 선택해 주세요.')
    if symbology in GS1_TYPES:
        from .gs1 import build_gs1, parse_gs1
        payload = build_gs1(parse_gs1(value))
        # Opening parentheses within AI data need an escape in Zint's delimiter
        # syntax. The payload itself remains unchanged after validation.
        value = ''.join('(' + item.ai + ')' + item.value.replace('(', '\\(') for item in payload.elements)
    command = [str(encoder_path()), *_command_options(symbology, options)]
    if symbology in HIBC_CARRIERS:
        try:
            value = resolve_hibc(value, options['hibc_input_mode'])
        except ValueError as exc:
            raise BarcodeEncodingError(str(exc)) from None
        # Completed LIC data already includes its flag and Mod43. Zint's HIBC
        # modes append both again, so use the matching ordinary carrier.
        command[1] = f'--barcode={ZINT_TYPES[HIBC_CARRIERS[symbology]]}'
    with tempfile.TemporaryDirectory(prefix='chaeum-barcode-') as directory:
        folder = Path(directory)
        # Zint Windows CLI uses narrow file APIs; relative ASCII filenames avoid
        # loss of Korean Windows profile paths. Never put input data on a command line.
        (folder / 'input.txt').write_bytes(value.encode('utf-8'))
        command.extend(['--input=input.txt','--output=barcode.bmp'])
        try:
            result = subprocess.run(command, cwd=folder, capture_output=True, timeout=10,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired:
            raise BarcodeEncodingError('바코드 생성 시간이 초과되었습니다. 데이터와 설정을 확인해 주세요.') from None
        except OSError:
            raise BarcodeEncodingError('바코드 엔진을 실행하지 못했습니다. 배포 파일과 실행 권한을 확인해 주세요.') from None
        if result.returncode:
            detail = result.stderr.decode('utf-8', errors='replace').strip()
            # CLI does not echo data in normal errors; still redact supplied values.
            detail = detail.replace(value, '[데이터]')
            if 'Invalid check digit' in detail:
                detail = '체크디지트가 올바르지 않습니다. ' + detail
            raise BarcodeEncodingError(f'바코드 데이터/옵션 오류: {detail or result.returncode}')
        with Image.open(folder / 'barcode.bmp') as image:
            image = image.convert('L').copy()
    image.info['module_dots'] = options.get('module_width', options.get('cell_size', 0)) or 1
    image.info['symbology'] = symbology
    if symbology in HIBC_CARRIERS:
        image.info['encoded_value'] = value
        image.info['hri_value'] = hibc_hri(value, linear=symbology in BARCODE_1D_TYPES)
    return image


def render_barcode(symbology: str, value: str, options: dict | None = None) -> Image.Image:
    """Return natural pixel dimensions, compliant quiet zones, and no HRI.

    Callers must enlarge with integer modules or reject boxes smaller than this
    image; fitting to an arbitrary rectangle would corrupt module dimensions.
    """
    if not isinstance(value, str):
        raise BarcodeEncodingError('바코드 값은 문자열이어야 합니다. 선행 0을 보존해 주세요.')
    normalized = normalize_options(symbology, options)
    return _render_cached(symbology, value, tuple(sorted(normalized.items()))).copy()


def validate_barcode(symbology: str, value: str, options: dict | None = None) -> None:
    render_barcode(symbology, value, options)
