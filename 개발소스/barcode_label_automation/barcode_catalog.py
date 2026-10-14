"""Shared, explicit offline encoder capabilities. IDs are persisted in label files."""
from __future__ import annotations

# Zint 2.16.0 official CLI type numbers; no format substitution is permitted.
_ROWS = (
    ('code128','Code 128',20,1), ('gs1_128','GS1-128',16,1),
    ('code39','Code 39',8,1), ('code39extended','Code 39 Full ASCII',9,1),
    ('code93','Code 93',25,1), ('code11','Code 11',1,1), ('codabar','Codabar',18,1),
    ('ean13','EAN-13',15,1), ('ean8','EAN-8',10,1), ('upca','UPC-A',34,1),
    ('upce','UPC-E',37,1), ('ean2','EAN 2-digit add-on',11,1), ('ean5','EAN 5-digit add-on',12,1),
    ('itf','Interleaved 2 of 5',3,1), ('itf14','ITF-14',89,1),
    ('industrial2of5','Industrial 2 of 5',7,1), ('standard2of5','Standard 2 of 5',2,1),
    ('iata2of5','IATA 2 of 5',4,1), ('datalogic2of5','Datalogic 2 of 5',6,1),
    ('msi','MSI Plessey',47,1), ('plessey','UK Plessey',86,1),
    ('pharmacode','Pharmacode',51,1), ('pharmacode2track','Pharmacode Two-Track',53,1),
    ('code32','Code 32 Italian Pharmacode',129,1), ('pzn','PZN',52,1), ('bc412','BC412',146,1),
    ('channelcode','Channel Code',140,1), ('telepen','Telepen',32,1),
    ('telepennumeric','Telepen Numeric',87,1),
    ('databar','GS1 DataBar Omnidirectional',29,1), ('databarlimited','GS1 DataBar Limited',30,1),
    ('databarexpanded','GS1 DataBar Expanded',31,1), ('databarstacked','GS1 DataBar Stacked',79,1),
    ('databarstackedomni','GS1 DataBar Stacked Omni',80,1),
    ('databarexpandedstacked','GS1 DataBar Expanded Stacked',81,1),
    ('postnet','USPS POSTNET',40,1), ('planet','USPS PLANET',82,1),
    ('uspsintelligentmail','USPS Intelligent Mail',85,1), ('royalmail','Royal Mail 4-State',70,1),
    ('kix','KIX 4-State',90,1), ('japanpost','Japan Post',76,1), ('koreapost','Korea Post',77,1),
    ('australiapost','Australia Post',63,1), ('cepnet','CEPNet',54,1),
    ('deutscheident','Deutsche Post Identcode',22,1), ('deutscheleit','Deutsche Post Leitcode',21,1),
    ('qr','QR Code',58,2), ('gs1_qr','GS1 QR Code',58,2), ('microqr','Micro QR',97,2),
    ('rmqr','rMQR',145,2), ('datamatrix','Data Matrix ECC200',71,2),
    ('gs1_datamatrix','GS1 DataMatrix',71,2), ('pdf417','PDF417',55,2),
    ('compactpdf417','Compact PDF417',56,2), ('micropdf417','MicroPDF417',84,2),
    ('aztec','Aztec',92,2), ('aztecrune','Aztec Rune',128,2), ('maxicode','MaxiCode',57,2),
    ('dotcode','DotCode',115,2), ('hanxin','Han Xin',116,2), ('gridmatrix','Grid Matrix',142,2),
    ('code16k','Code 16K',23,2), ('code49','Code 49',24,2), ('codablockf','Codablock-F',74,2),
    ('gs1_composite','GS1-128 Composite',131,2), ('databar_composite','DataBar Composite',132,2),
    ('databarlimited_composite','DataBar Limited Composite',133,2),
    ('databarexpanded_composite','DataBar Expanded Composite',134,2),
    ('upca_composite','UPC-A Composite',135,2), ('upce_composite','UPC-E Composite',136,2),
    ('ean8_composite','EAN-8 Composite',148,2), ('ean13_composite','EAN-13 Composite',149,2),
    ('hibc128','HIBC Code 128',98,1), ('hibc39','HIBC Code 39',99,1),
    ('hibcdatamatrix','HIBC Data Matrix',102,2), ('hibcqr','HIBC QR',104,2),
    ('hibcpdf417','HIBC PDF417',106,2), ('hibcmicropdf417','HIBC MicroPDF417',108,2),
    ('hibcaztec','HIBC Aztec',112,2), ('hibccodablockf','HIBC Codablock-F',110,2),
)
BARCODE_TYPES = {key: label for key, label, _, _ in _ROWS}
ZINT_TYPES = {key: number for key, _, number, _ in _ROWS}
BARCODE_1D_TYPES = frozenset(key for key, _, _, dimension in _ROWS if dimension == 1)
BARCODE_2D_TYPES = frozenset(BARCODE_TYPES) - BARCODE_1D_TYPES
SUPPORTED_BARCODE_TYPES = frozenset(BARCODE_TYPES)
GS1_TYPES = frozenset({'gs1_128','gs1_qr','gs1_datamatrix','databarexpanded','databarexpandedstacked'})

SAMPLE_VALUES = {key: '123456' for key in BARCODE_TYPES}
SAMPLE_VALUES.update({key:'(01)09506000134376(10)LOT123(21)SER001' for key in GS1_TYPES})
SAMPLE_VALUES.update({key:'09506000134376' for key in ('databar','databarlimited','databarstacked','databarstackedomni','itf14')})
SAMPLE_VALUES.update(ean13='5901234123457',ean8='96385074',upca='012345678905',upce='0123456',
                     ean2='12',ean5='12345',codabar='A123456B',postnet='12345',planet='12345678901',
                     cepnet='12345678',uspsintelligentmail='01234567094987654321',australiapost='12345678',
                     deutscheident='12345678901',deutscheleit='1234567890123',japanpost='1234567ABCD',
                     pzn='1234567',aztecrune='123',bc412='1234567',pharmacode='123',pharmacode2track='123')
SAMPLE_VALUES.update({key:'A123BJC5D6E71' for key in BARCODE_TYPES if key.startswith('hibc')})
SAMPLE_VALUES.update({key:'(10)LOT123' for key in BARCODE_TYPES if key.endswith('_composite')})

def sample_options(symbology: str) -> dict:
    if symbology.endswith('_composite'):
        primary = '(01)09506000134376' if symbology == 'gs1_composite' else '012345678905' if symbology == 'upca_composite' else '0123456' if symbology == 'upce_composite' else '96385074' if symbology == 'ean8_composite' else '5901234123457' if symbology == 'ean13_composite' else '(01)09506000134376' if symbology == 'databarexpanded_composite' else '09506000134376'
        return {'primary':primary}
    return {}

def option_definitions(symbology: str) -> dict[str, dict[str, object]]:
    """Only options actually passed to the encoder are offered by the UI."""
    if symbology not in BARCODE_TYPES:
        return {}
    result = {
        'cell_size' if symbology in BARCODE_2D_TYPES else 'module_width':
            {'label':'모듈 크기 (도트, 0=자동)', 'min':0, 'max':20, 'default':0},
        'quiet_zone': {'label':'추가 좌우 여백 (모듈)', 'min':0, 'max':40, 'default':0},
        'human_readable': {'label':'표시문자', 'type':'bool', 'default':True},
    }
    if symbology in BARCODE_1D_TYPES:
        result['bar_height']={'label':'바 높이 (모듈, 0=기본)','type':'float','min':0,'max':2000,'default':0}
    if symbology.startswith('hibc'):
        result['hibc_input_mode'] = {'label':'HIBC 입력 방식', 'choices':('auto','raw','complete'), 'default':'auto'}
    if symbology in {'qr','gs1_qr','microqr','rmqr','hibcqr'}:
        result['qr_ecc'] = {'label':'오류 복원','choices':('M','H') if symbology == 'rmqr' else ('L','M','Q') if symbology == 'microqr' else ('L','M','Q','H'), 'default':'M'}
        result['version'] = {'label':'버전 (0=자동)','min':0,'max':4 if symbology == 'microqr' else 38 if symbology == 'rmqr' else 40,'default':0}
        if symbology != 'rmqr':
            result['data_mask'] = {'label':'마스크 (-1=자동)','min':-1,'max':3 if symbology == 'microqr' else 7,'default':-1}
    if symbology in {'pdf417','compactpdf417','hibcpdf417'}:
        result.update(pdf417_rows={'label':'행 (0=자동)','min':0,'max':90,'default':0},pdf417_columns={'label':'열 (0=자동)','min':0,'max':30,'default':0},pdf417_security={'label':'오류 복원 레벨','min':0,'max':8,'default':2})
        result['pdf417_module_height']={'label':'행 높이 (모듈)','type':'float','min':3,'max':100,'default':3}
    if symbology in {'datamatrix','gs1_datamatrix','hibcdatamatrix'}:
        result.update(version={'label':'크기 번호 (0=자동)','min':0,'max':48,'default':0},force_square={'label':'정사각형만 사용','type':'bool','default':False},dmre={'label':'직사각형 확장 DMRE','type':'bool','default':False})
    if symbology in {'aztec','hibcaztec'}:
        result.update(version={'label':'크기 번호 (0=자동)','min':0,'max':36,'default':0},ecc_level={'label':'오류 복원 레벨 (1~4)','min':1,'max':4,'default':2})
    if symbology == 'micropdf417':
        result['columns']={'label':'열 (0=자동)','min':0,'max':4,'default':0}
    if symbology in {'codablockf','code16k','code49','databarexpandedstacked'}:
        result['rows']={'label':'행 (0=자동)','min':0,'max':16 if symbology == 'code16k' else 8 if symbology == 'code49' else 44,'default':0}
        if symbology in {'codablockf','databarexpandedstacked'}:
            result['columns']={'label':'열/세그먼트 (0=자동)','min':0,'max':67 if symbology == 'codablockf' else 22,'default':0}
    if symbology == 'maxicode' or symbology.endswith('_composite'):
        result['mode']={'label':'인코딩 모드','min':2 if symbology == 'maxicode' else 1,'max':6 if symbology == 'maxicode' else 3,'default':4 if symbology == 'maxicode' else 1}
        result['primary']={'label':'주 메시지/선형 구성 데이터','type':'text','default':''}
    if symbology in {'dotcode','hanxin','gridmatrix'}:
        if symbology == 'dotcode':
            result['columns']={'label':'열 (0=자동)','min':0,'max':200,'default':0}
            result['data_mask']={'label':'마스크 (-1=자동)','min':-1,'max':7,'default':-1}
        else:
            result['version']={'label':'크기 번호 (0=자동)','min':0,'max':84 if symbology == 'hanxin' else 13,'default':0}
            result['ecc_level']={'label':'오류 복원 레벨','min':1,'max':4 if symbology == 'hanxin' else 5,'default':2}
    if symbology in {'code39','code39extended','code11','msi','itf','industrial2of5','standard2of5','iata2of5','datalogic2of5','codabar'}:
        choices = ('auto','none','mod43') if symbology in {'code39','code39extended'} else ('auto','none','mod11') if symbology == 'code11' else ('auto','none','mod10','mod11','mod1010','mod1110','mod11ncr','mod11ncr10') if symbology == 'msi' else ('auto','none','mod16') if symbology == 'codabar' else ('auto','none','mod10')
        result['check_digit']={'label':'체크숫자','choices':choices,'default':'auto'}
    if symbology in {'qr','datamatrix','pdf417','aztec','dotcode','hanxin','gridmatrix','maxicode','micropdf417','rmqr'}:
        result['eci']={'label':'ECI (0=자동)','min':0,'max':999999,'default':0}
    if symbology in {'qr','gs1_qr','datamatrix','gs1_datamatrix','aztec','pdf417','maxicode','dotcode','gridmatrix'}:
        result['structured_append']={'label':'구조적 연결 (번호,총수[,ID])','type':'text','default':''}
    if symbology in {'datamatrix','aztec','pdf417','micropdf417','dotcode','gridmatrix','code128'}:
        result['reader_init']={'label':'스캐너 초기화 심볼','type':'bool','default':False}
    if symbology in {'ean13','ean8','upca','upce'}:
        result['addon_gap']={'label':'추가부호 간격 (모듈, 0=기본)','min':0,'max':50,'default':0}
    if symbology == 'itf14':
        result['bearer_style']={'label':'베어러 바','choices':('box','bind','none'),'default':'box'}
        result['bearer_width']={'label':'베어러 폭 (모듈)','min':0,'max':16,'default':5}
    return result
