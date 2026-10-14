"""Build the five-page quick guide using the current desktop print contract."""
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
    canvas.drawString(18*mm,12*mm,'채움랩 · 한눈에 사용안내 · 2026.10.13.05')
    canvas.drawRightString(192*mm,12*mm,str(doc.page))
    canvas.restoreState()


def main():
    story = [paragraph('01  처음 설정',True), paragraph('실제 라벨 규격과 상품 엑셀을 먼저 확인합니다. 기본 도안은 개체가 없는 빈 라벨입니다.'), steps([
        ('프린터 연결과 용지 설정','프린터설정.exe에서 USB/Windows 또는 LAN을 선택합니다. 실제 모델의 mm·DPI·용지·간격을 확인하고 설정 점검 후 저장합니다. 열린 디자이너·출력 관리에도 공통 규격을 적용합니다. 디자이너는 용지 설정 바로가기를 사용합니다.'),
        ('상품 엑셀 연결','라벨출력관리.exe의 파일 > 상품 엑셀 연결을 사용합니다. 첫 행은 열 이름이며 바코드 앞자리 0은 엑셀의 문자 값으로 보관합니다.'),
        ('도안 저장과 인식 확인','라벨디자이너.exe에서 예제로 시작 또는 새 라벨을 선택해 .cllabel로 저장합니다. Ctrl+C/V/D로 개체를 복사·붙여넣기·복제합니다. 글자 입력칸은 글자 편집을 우선합니다. 크기·표시문자 탭의 2D 크기·문자 배치에서 바코드 크기 우선을 확인하고 실제 크기 확인 후 문자를 배치합니다. 기존 도안은 기존 배치를 유지하며 직접 전환합니다.'),
        ('한 항목·1매로 첫 장 확인','한 항목을 체크하고 인쇄 매수 선택에서 대상과 1매를 확인합니다. 나온 라벨의 내용·위치와 스캔 결과를 확인합니다.'),
    ]), Spacer(1,12*mm),paragraph('인쇄파일 생성은 프린터에 보내지 않습니다. 전송 완료 표시 후에도 실제 배출과 바코드 판독을 확인합니다.'),PageBreak(),
        paragraph('02  매일 사용하는 순서',True), steps([
        ('찾을 값을 입력하거나 스캔','DB 상품조회 입력칸을 선택하고 바코드·품명·품목 코드·가격 등 DB에 있는 값을 조회합니다. 스캔 후 Enter가 오면 조회합니다.'),
        ('중복 결과에서 필요한 행 선택','같은 값이 여러 행에 있으면 필요한 행만 체크하고 확인합니다. 확인하면 이번 선택으로 기존 체크를 교체합니다. 취소하면 기존 선택을 유지합니다.'),
        ('대상과 매수를 마지막으로 확인','체크한 항목이 있으면 해당 항목, 체크가 없으면 전체 유효 항목이 대상입니다. 인쇄 매수 선택에서 대상 수와 양의 정수 매수·총 매수를 확인합니다.'),
        ('실물 라벨과 스캔 결과 확인','전송 완료는 명령을 보냈다는 뜻입니다. 실제 라벨이 나왔는지, 글자와 방향·바코드 값이 맞는지 확인합니다. 결과가 불명확하면 나온 라벨을 먼저 확인합니다.'),
    ]),Spacer(1,12*mm),paragraph('시작 전 취소하면 프린터 명령을 전송하지 않습니다. 전송 중 중단은 아직 보내지 않은 작업을 멈춥니다. 이미 프린터가 받은 작업의 중단이나 실제 배출 중지는 보장하지 않습니다. 이번 매수는 임시 큐에만 적용되며 원본 DB와 기본 print_queue.xlsx를 덮어쓰지 않습니다.'),PageBreak(),
        paragraph('03  인쇄 전 여섯 가지 확인',True),steps([
        ('프린터 연결·라벨 규격','IP·포트 또는 Windows 프린터 이름, 실제 mm·DPI·용지·간격을 확인합니다.'),
        ('바코드 문자열과 앞자리 0','원본과 불러온 값이 같고 빈 바코드가 없는지 확인합니다. 앞자리 0은 문자 값으로 저장합니다.'),
        ('도안 인식 값과 2D 크기','인식 값 전체 확인에서 원본과 값을 대조합니다. 2D는 필수 여백을 포함한 코드 크기를 먼저 정하고 문자 위치를 오른쪽/아래로 배치합니다. 문자를 바꾸어도 코드는 축소하지 않습니다. 문자 공간 오류 중에도 코드를 보고 손잡이로 크기를 조절합니다. 현재 라벨에 맞추기 또는 문자 아래 배치 후 다시 검증합니다.'),
        ('출력 대상','선택한 행이 있으면 선택 대상, 없으면 전체 유효 대상입니다. 대상 수를 보고 의도한 범위인지 확인합니다.'),
        ('인쇄 매수','대상 수 × 매수의 총 출력량을 확인합니다. 첫 테스트는 한 항목·1매입니다. 잘못 골랐다면 취소합니다.'),
        ('생성된 파일과 실물','인쇄파일을 먼저 확인하고 실제 첫 장의 글자·위치·1D/2D 스캔까지 확인합니다.'),
    ]),PageBreak(),paragraph('04  설치부터 반복 출력까지',True),steps([
        ('폴더 전체를 보관','EXE만 분리하지 않습니다. tools/ocr·글꼴·설정·DB·템플릿이 있는 폴더 전체를 복사합니다.'),
        ('처음실행_점검.cmd 실행','필수 파일과 파일 연결·출력 파일 생성·고객 데이터 백업을 점검합니다. 실패하면 점검 보고서와 지원 ZIP을 준비합니다.'),
        ('설정과 상품 데이터 확인','프린터설정.exe에서 저장한 뒤 시작하기.cmd로 출력 관리를 엽니다. 원본 엑셀과 상품 값을 비교합니다.'),
        ('같은 도안으로 반복 출력','.cllabel 도안을 저장한 뒤 반복 출력으로 이동합니다. 출력 관리의 선택 도안 이름·현재 도안 미리보기를 확인합니다. 자동 기본 배치는 별도 모드입니다. 기존 .gblabel/.gbproject도 엽니다.'),
        ('값 생성과 전체 데이터 검증','디자이너 도구 > 값 생성 규칙에서 번호·날짜·문자를 정합니다. 미리보기는 번호를 소비하지 않습니다. 전체 데이터 검증에서 행·개체·오류를 한 번에 확인하고 엑셀 파일·시트가 바뀌면 재연결합니다.'),
        ('한 항목·1매 확인 후 반복','배출·글자·방향·바코드를 확인하고 필요한 대상과 매수를 지정합니다. 설정/DB 백업은 파일 > 고객 데이터 백업에서 합니다.'),
    ]),Spacer(1,8*mm),paragraph('상세 도움말: 각 프로그램 도움말 > 고객용 매뉴얼. .clproject에는 엑셀 원본과 글꼴 파일이 포함되지 않습니다. .btw는 실제 이미지로 내보내 다시 연결합니다. 발급 기록은 고객 백업에 포함하며 오래된 번호로 복원하면 차단합니다. SEWOO는 승인 모델이 없어 출력이 차단됩니다.')]
    story.extend([PageBreak(), paragraph('05  AI·UDI와 바코드 크기 조절', True), steps([
        ('데이터 원본부터 입력','바코드를 더블클릭하면 데이터 원본부터 열립니다. 직접 입력 / DB·엑셀 연결을 선택합니다. GS1 데이터로 설정…은 첫 화면, 의료기기 UDI는 기타 데이터 옵션…입니다. 원본별 초안은 전환해도 보존됩니다. 작은 창은 선택 AI 목록에서 고르고 마우스 휠과 Tab으로 입력칸을 이동합니다. 상단 미리보기 버튼을 눌러 DB 행·인코딩 값·표시문자·DPI·실제 mm를 보고 100%·확대 보기를 사용합니다.'),
        ('시험 예제와 실제 값 구분','시험용 완성 예제로 시작은 시험용입니다. 실제 번호 또는 DB 열로 교체합니다. 필수 AI 선택에서 부족한 조합을 함께 확인합니다. 새 AI 값은 검증·적용 전에 자동 반영합니다. 전체 문자열은 전체 GS1 데이터 가져오기로 미리봅니다.'),
        ('UDI 원문과 기호 확인','제품 식별번호(DI)·생산 정보(PI)를 입력하고 GS1과 HIBC를 구분합니다. UDI 선택은 초안에만 반영됩니다. 편집창 하단의 적용 또는 확인으로 저장합니다. HIBC의 원본으로 생성과 완성 코드 가져오기는 다른 입력입니다. 완성 원문의 +접두·체크문자·공백을 보존합니다. 긴 UDI는 값 삭제 없이 GS1 DataMatrix 전환을 검토합니다.'),
        ('손잡이와 라벨 맞춤','정사각형은 바코드 한 변(mm), 직사각형은 원래 비율로 조절합니다. 문자·경계 오류 중에도 코드 크기 조절과 실행취소를 사용합니다. 현재 라벨에 맞추기 또는 문자 아래 배치를 검토합니다. 모듈 크기 고정은 도트로 변경하며 손잡이는 잠깁니다.'),
    ]), Spacer(1, 8*mm), paragraph('UDI/GS1 화면을 열어도 출력 원본은 바뀌지 않습니다. 구성을 편집한 뒤 편집창 하단의 적용 또는 확인을 누르세요. 취소·Esc는 마지막 적용 상태를 보존합니다. 목표 mm와 실제 mm·모듈 도트를 확인하고 메인 화면의 전체 데이터 검증 후 저장합니다. 해결되지 않은 오류는 인쇄를 차단합니다. 국내 프로필은 기관 등록·규제 승인 완료가 아닙니다. 실제 첫 장의 크기·표시문자·스캔 값을 확인하세요.')])
    target = ROOT/'한눈에_사용안내.pdf'
    SimpleDocTemplate(str(target),pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=28*mm,bottomMargin=20*mm).build(story,onFirstPage=page,onLaterPages=page)
    print(target)
    from shutil import copy2
    for destination in (ROOT/'고객용_실행폴더', ROOT.parent):
        copy2(target, destination/target.name)


if __name__ == '__main__':
    main()
