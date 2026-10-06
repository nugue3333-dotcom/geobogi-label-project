"""Build the four-page quick guide using the current desktop print contract."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
pdfmetrics.registerFont(TTFont('QuickKO', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('QuickKOBold', 'C:/Windows/Fonts/malgunbd.ttf'))
NAVY = colors.HexColor('#143E70')
LIME = colors.HexColor('#A3D900')
BODY = ParagraphStyle('quick-body', fontName='QuickKO', fontSize=10, leading=17, wordWrap='CJK', spaceAfter=8)
TITLE = ParagraphStyle('quick-title', parent=BODY, fontName='QuickKOBold', fontSize=20, leading=28, textColor=NAVY, spaceAfter=18)


def paragraph(text, title=False):
    return Paragraph(text, TITLE if title else BODY)


def steps(items):
    rows = [[paragraph(f'<b>{index:02}</b>'), paragraph(f'<b>{title}</b><br/>{text}')] for index, (title, text) in enumerate(items, 1)]
    result = Table(rows, colWidths=[14*mm,160*mm])
    result.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EAF0F6')), ('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#D4DDE6')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    return result


def page(canvas, doc):
    canvas.saveState()
    canvas.drawImage(str(ROOT/'assets/brand/chaeumlab_logo_header.png'),18*mm,280*mm,width=32*mm,height=8*mm,mask='auto',preserveAspectRatio=True)
    canvas.setStrokeColor(LIME)
    canvas.setLineWidth(2)
    canvas.line(18*mm,278*mm,192*mm,278*mm)
    canvas.setFont('QuickKO',8)
    canvas.setFillColor(NAVY)
    canvas.drawString(18*mm,12*mm,'채움랩 · 한눈에 사용안내 · 2026.10.06.01')
    canvas.drawRightString(192*mm,12*mm,str(doc.page))
    canvas.restoreState()


def main():
    story = [paragraph('01  처음 설정',True), paragraph('실제 라벨 규격과 상품 엑셀을 먼저 확인합니다. 기본 도안은 개체가 없는 빈 라벨입니다.'), steps([
        ('프린터 연결과 용지 설정','프린터설정.exe에서 USB/Windows 또는 LAN을 선택합니다. 실제 모델의 mm·DPI·용지·간격을 확인하고 설정 점검 후 저장합니다.'),
        ('상품 엑셀 연결','라벨출력관리.exe의 파일 > 상품 엑셀 연결을 사용합니다. 첫 행은 열 이름이며 바코드 앞자리 0은 엑셀의 문자 값으로 보관합니다.'),
        ('도안 저장과 인식 확인','라벨디자이너.exe에서 예제로 시작 또는 새 라벨을 선택합니다. .cllabel로 저장하고 인식 값 전체 확인에서 원본과 글자·바코드를 비교합니다.'),
        ('한 항목·1매로 첫 장 확인','한 항목을 체크하고 인쇄 매수 선택에서 대상과 1매를 확인합니다. 나온 라벨의 내용·위치와 스캔 결과를 확인합니다.'),
    ]), Spacer(1,12*mm),paragraph('인쇄파일 생성은 프린터에 보내지 않습니다. 전송 완료 표시 후에도 실제 배출과 바코드 판독을 확인합니다.'),PageBreak(),
        paragraph('02  매일 사용하는 순서',True), steps([
        ('찾을 값을 입력하거나 스캔','DB 상품조회 입력칸을 선택하고 바코드·품명·품목 코드·가격 등 DB에 있는 값을 조회합니다. 스캔 후 Enter가 오면 조회합니다.'),
        ('중복 결과에서 필요한 행 선택','같은 값이 여러 행에 있으면 필요한 행만 체크하고 확인합니다. 확인하면 이번 선택으로 기존 체크를 교체합니다. 취소하면 기존 선택을 유지합니다.'),
        ('대상과 매수를 마지막으로 확인','체크한 항목이 있으면 해당 항목, 체크가 없으면 전체 유효 항목이 대상입니다. 인쇄 매수 선택에서 대상 수와 1~100매를 확인합니다.'),
        ('실물 라벨과 스캔 결과 확인','전송 완료는 명령을 보냈다는 뜻입니다. 실제 라벨이 나왔는지, 글자와 방향·바코드 값이 맞는지 확인합니다. 결과가 불명확하면 나온 라벨을 먼저 확인합니다.'),
    ]),Spacer(1,12*mm),paragraph('취소하면 프린터 명령을 전송하지 않습니다. 이번 매수는 임시 큐에만 적용되며 원본 DB와 기본 print_queue.xlsx를 덮어쓰지 않습니다.'),PageBreak(),
        paragraph('03  인쇄 전 여섯 가지 확인',True),steps([
        ('프린터 연결·라벨 규격','IP·포트 또는 Windows 프린터 이름, 실제 mm·DPI·용지·간격을 확인합니다.'),
        ('바코드 문자열과 앞자리 0','원본과 불러온 값이 같고 빈 바코드가 없는지 확인합니다. 앞자리 0은 문자 값으로 저장합니다.'),
        ('도안 인식 값','인식 값 전체 확인에서 원본과 값을 대조하고 잘못된 글자와 임시 바코드를 수정합니다. 빈 필수 값은 전체 확인을 막습니다.'),
        ('출력 대상','선택한 행이 있으면 선택 대상, 없으면 전체 유효 대상입니다. 대상 수를 보고 의도한 범위인지 확인합니다.'),
        ('인쇄 매수','대상 수 × 매수의 총 출력량을 확인합니다. 첫 테스트는 한 항목·1매입니다. 잘못 골랐다면 취소합니다.'),
        ('생성된 파일과 실물','인쇄파일을 먼저 확인하고 실제 첫 장의 글자·위치·1D/2D 스캔까지 확인합니다.'),
    ]),PageBreak(),paragraph('04  설치부터 반복 출력까지',True),steps([
        ('폴더 전체를 보관','EXE만 분리하지 않습니다. tools/ocr·글꼴·설정·DB·템플릿이 있는 폴더 전체를 복사합니다.'),
        ('처음실행_점검.cmd 실행','필수 파일과 파일 연결·출력 파일 생성·고객 데이터 백업을 점검합니다. 실패하면 점검 보고서와 지원 ZIP을 준비합니다.'),
        ('설정과 상품 데이터 확인','프린터설정.exe에서 저장한 뒤 시작하기.cmd로 출력 관리를 엽니다. 원본 엑셀과 상품 값을 비교합니다.'),
        ('도안·인식 값을 저장','새 .cllabel 도안과 필요하면 .clproject를 저장합니다. 기존 .gblabel/.gbproject도 엽니다. 프로젝트에는 엑셀 원본과 글꼴 파일이 포함되지 않습니다.'),
        ('한 항목·1매 확인 후 반복','배출·글자·방향·바코드를 확인하고 필요한 대상과 매수를 지정합니다. 설정/DB 백업은 파일 > 고객 데이터 백업에서 합니다.'),
    ]),Spacer(1,8*mm),paragraph('상세 도움말: 각 프로그램 도움말 > 고객용 매뉴얼. .btw는 직접 열지 않으며 원본 프로그램에서 실제 이미지로 내보낸 뒤 다시 연결합니다. SEWOO는 승인 모델이 없어 출력이 차단됩니다.')]
    target = ROOT/'한눈에_사용안내.pdf'
    SimpleDocTemplate(str(target),pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=28*mm,bottomMargin=20*mm).build(story,onFirstPage=page,onLaterPages=page)
    print(target)


if __name__ == '__main__':
    main()
