from __future__ import annotations

from pathlib import Path
from shutil import copy2

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_DIR = ROOT / "고객용_실행폴더"
OUTPUT_DOCX = CUSTOMER_DIR / "라벨출력패키지_고객용_매뉴얼.docx"

FONT_KO = "맑은 고딕"
# Match the formal print-manual palette used by the three PDF guides.
COLOR_NAVY = "171D23"
COLOR_BLUE = "174B4E"
COLOR_BLUE_DARK = "103A3D"
COLOR_MUTED = "68747C"
COLOR_GRID = "D8DEE0"
COLOR_HEADER_FILL = "F1F7E3"
COLOR_LIGHT_FILL = "F6F7F5"
COLOR_ACCENT_FILL = "F1F7E3"
COLOR_WARNING_FILL = "FFF7E7"


def set_run_font(run, size_pt: float | None = None, bold: bool | None = None, color: str | None = None) -> None:
    run.font.name = FONT_KO
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_KO)
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def set_paragraph_font(paragraph, size_pt: float | None = None, bold: bool | None = None, color: str | None = None) -> None:
    for run in paragraph.runs:
        set_run_font(run, size_pt=size_pt, bold=bold, color=color)


def set_style_font(style, size_pt: float, color: str = "000000", bold: bool = False) -> None:
    style.font.name = FONT_KO
    style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_KO)
    style.font.size = Pt(size_pt)
    style.font.color.rgb = RGBColor.from_string(color)
    style.font.bold = bold


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, left=120, bottom=80, right=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_borders(cell, color: str = COLOR_GRID, size: str = "8") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)
    for edge in ("top", "left", "bottom", "right"):
        tag = f"w:{edge}"
        element = tc_borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            tc_borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_table_borders(table, color: str = COLOR_GRID, size: str = "8") -> None:
    tbl_pr = table._tbl.tblPr
    tbl_borders = tbl_pr.find(qn("w:tblBorders"))
    if tbl_borders is None:
        tbl_borders = OxmlElement("w:tblBorders")
        tbl_pr.append(tbl_borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = tbl_borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            tbl_borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_table_geometry(table, widths_dxa: list[int], indent_dxa: int = 120) -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:type"), "dxa")
    tbl_w.set(qn("w:w"), str(sum(widths_dxa)))

    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:type"), "dxa")
    tbl_ind.set(qn("w:w"), str(indent_dxa))

    tbl_layout = tbl_pr.find(qn("w:tblLayout"))
    if tbl_layout is None:
        tbl_layout = OxmlElement("w:tblLayout")
        tbl_pr.append(tbl_layout)
    tbl_layout.set(qn("w:type"), "fixed")
    set_table_borders(table)

    existing_grid = tbl.find(qn("w:tblGrid"))
    if existing_grid is not None:
        tbl.remove(existing_grid)
    grid = OxmlElement("w:tblGrid")
    for width in widths_dxa:
        grid_col = OxmlElement("w:gridCol")
        grid_col.set(qn("w:w"), str(width))
        grid.append(grid_col)
    tbl.insert(1, grid)

    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            if idx >= len(widths_dxa):
                continue
            cell.width = Inches(widths_dxa[idx] / 1440)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:type"), "dxa")
            tc_w.set(qn("w:w"), str(widths_dxa[idx]))
            set_cell_margins(cell)
            set_cell_borders(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def style_table(table, widths_dxa: list[int], header_rows: int = 1) -> None:
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    set_table_geometry(table, widths_dxa)
    for r_idx, row in enumerate(table.rows):
        for cell in row.cells:
            if r_idx < header_rows:
                set_cell_shading(cell, COLOR_HEADER_FILL)
                for p in cell.paragraphs:
                    for run in p.runs:
                        set_run_font(run, size_pt=10.2, bold=True, color=COLOR_NAVY)
            else:
                for p in cell.paragraphs:
                    for run in p.runs:
                        set_run_font(run, size_pt=10.2, color="111827")
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.3


def fill_cell(cell, text: str, bold: bool = False, color: str = "111827", size_pt: float = 10.2) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.3
    run = p.add_run(text)
    set_run_font(run, size_pt=size_pt, bold=bold, color=color)


def add_heading(doc: Document, text: str, level: int) -> None:
    p = doc.add_heading(text, level=level)
    if level == 1:
        p.paragraph_format.space_before = Pt(22)
        p.paragraph_format.space_after = Pt(12)
        set_paragraph_font(p, size_pt=18, bold=True, color=COLOR_BLUE)
    elif level == 2:
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(8)
        set_paragraph_font(p, size_pt=14, bold=True, color=COLOR_BLUE)
    else:
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(5)
        set_paragraph_font(p, size_pt=12, bold=True, color=COLOR_BLUE_DARK)


def add_body(doc: Document, text: str, bold_prefix: str | None = None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.35
    if bold_prefix and text.startswith(bold_prefix):
        r1 = p.add_run(bold_prefix)
        set_run_font(r1, size_pt=11, bold=True, color=COLOR_NAVY)
        r2 = p.add_run(text[len(bold_prefix) :])
        set_run_font(r2, size_pt=11, color="111827")
    else:
        r = p.add_run(text)
        set_run_font(r, size_pt=11, color="111827")


def add_callout(doc: Document, title: str, body: str, fill: str = COLOR_LIGHT_FILL) -> None:
    table = doc.add_table(rows=1, cols=1)
    style_table(table, [9360], header_rows=0)
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    cell.text = ""
    p_title = cell.paragraphs[0]
    p_title.paragraph_format.space_after = Pt(3)
    r_title = p_title.add_run(title)
    set_run_font(r_title, size_pt=11, bold=True, color=COLOR_NAVY)
    p_body = cell.add_paragraph()
    p_body.paragraph_format.space_after = Pt(0)
    p_body.paragraph_format.line_spacing = 1.3
    r_body = p_body.add_run(body)
    set_run_font(r_body, size_pt=10.2, color="263241")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_footer(section) -> None:
    footer = section.footer
    footer.is_linked_to_previous = False
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run("채움LAB 라벨 출력 패키지 고객용 매뉴얼 | Rev. 2026.09.30")
    set_run_font(run, size_pt=8.5, color=COLOR_MUTED)


def add_cover(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(42)
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run("채움LAB 라벨 출력 패키지")
    set_run_font(r, size_pt=30, bold=True, color=COLOR_NAVY)

    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(26)
    r2 = p2.add_run("고객용 프로그램 매뉴얼")
    set_run_font(r2, size_pt=18, bold=True, color=COLOR_BLUE)

    metadata = doc.add_table(rows=4, cols=2)
    rows = [
        ("문서 용도", "고객 PC 설치 후 Excel에서 라벨을 바로 출력하기 위한 사용 설명서"),
        ("지원 프린터", "BIXOLON, TSC, Zebra, SEWOO(ZPL) 라벨 프린터"),
        ("배포 폴더", "고객용_실행폴더"),
        ("문서 버전", "2.1 / 2026-09-30"),
    ]
    for row, (label, value) in zip(metadata.rows, rows):
        fill_cell(row.cells[0], label, bold=True, color=COLOR_NAVY)
        fill_cell(row.cells[1], value)
    style_table(metadata, [2700, 6660], header_rows=0)
    for row in metadata.rows:
        set_cell_shading(row.cells[0], COLOR_HEADER_FILL)

    add_callout(
        doc,
        "운영 핵심",
        "처음 설치한 PC에서는 시작하기.cmd menu의 처음 실행 점검 또는 처음실행_점검.cmd를 먼저 실행합니다. "
        "이 점검은 실행 전 점검, .gblabel 저장파일 연결, 출력 파일 생성 테스트, 고객 데이터 백업을 한 번에 수행합니다. "
        "PC 교체 후에는 고객데이터_복원.cmd로 백업 ZIP을 선택한 뒤 01_output_check.cmd로 복원 결과를 확인합니다. "
        "고객환경점검.exe로 배포 폴더 상태를 확인한 뒤 프린터설정.exe로 장비 환경을 저장합니다. "
        "config.ini는 설정 프로그램이 자동으로 갱신합니다. "
        "업데이트 배포본을 다시 실행해도 이미 저장된 고객 프린터 설정은 자동으로 덮어쓰지 않습니다.",
        COLOR_ACCENT_FILL,
    )
    doc.add_page_break()


def add_quick_start(doc: Document) -> None:
    add_heading(doc, "1. 빠른 시작", 1)
    add_body(
        doc,
        "처음 설치한 PC에서는 아래 순서대로 준비합니다. 평소에는 시작하기.cmd가 여는 라벨 출력 관리에서 상품을 선택해 인쇄합니다.",
    )
    table = doc.add_table(rows=1, cols=3)
    headers = ("순서", "실행 내용", "완료 기준")
    for cell, header in zip(table.rows[0].cells, headers):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("1", "고객용_실행폴더를 고객 PC의 원하는 위치에 복사합니다.", "폴더 안에 실행 파일, 설정, DB, 템플릿이 함께 있습니다."),
        ("2", "처음실행_점검.cmd를 실행합니다. 시작 메뉴는 시작하기.cmd menu로 열 수 있습니다.", "필수 파일, 설정, 엑셀, .gblabel 파일 연결, 출력 파일 생성 테스트와 고객 데이터 백업을 점검합니다."),
        ("3", "필요하면 시작하기.cmd menu > 버전 정보 보기를 확인합니다.", "지원 문의 시 버전정보.txt와 지원 ZIP을 함께 전달합니다."),
        ("4", "Excel 매크로 방식도 사용할 경우 00_install_trusted_location.cmd를 실행합니다.", "Excel 보안 경고 없이 매크로 버튼을 사용할 준비가 됩니다."),
        ("5", "프린터설정.exe를 열어 브랜드, 연결 방식, 용지 크기, 용지 유형, 인쇄 방식을 입력하고 설정 점검 후 저장합니다.", "config.ini가 자동으로 갱신됩니다."),
        (
            "6",
            "시작하기.cmd로 라벨 출력 관리를 열어 상품을 선택하고 매수를 확인합니다.",
            "선택 항목이 없으면 인쇄가 차단됩니다. 전체가 필요할 때는 전체 선택을 직접 누릅니다.",
        ),
    ]
    for row_data in rows:
        row = table.add_row().cells
        for cell, text in zip(row, row_data):
            fill_cell(cell, text)
    style_table(table, [900, 4300, 4160])

    add_callout(
        doc,
        "고객 안내 문구",
        "실제 프린터로 보내기 전에는 00_고객PC_실행전점검.cmd와 01_output_check.cmd를 순서대로 실행해 주세요. "
        "처음 실행 점검은 저장파일 연결도 PowerShell 없이 register_label_filetype.cmd로 처리합니다. "
        "01/02 배치파일은 라벨작업실행기.exe를 우선 사용하므로 일반적인 출력 점검과 인쇄 명령 생성은 PowerShell 없이 처리됩니다. "
        "일상 사용 중에도 라벨출력관리.exe의 설정 > 실행 전 점검 메뉴로 out\\customer_preflight_report.txt를 즉시 갱신할 수 있습니다. "
        "업데이트 배포본을 복사해도 기존 config.ini가 있으면 고객 프린터 설정은 유지됩니다. 기본값으로 되돌리고 싶을 때만 백업 후 config.example.ini를 참고하세요. "
        "오류 문의 시 라벨출력관리.exe의 설정 > 지원 패키지 생성 메뉴로 out\\customer_support_package.zip을 새로 만든 뒤 함께 전달하면 원인 확인이 빠릅니다. "
        "지원 ZIP에는 원본 DB, 인쇄 데이터, labels.xlsm이 포함되지 않습니다.",
        COLOR_WARNING_FILL,
    )


def add_file_map(doc: Document) -> None:
    add_heading(doc, "2. 배포 폴더 구성", 1)
    add_body(doc, "아래 파일은 같은 폴더 안에 있어야 합니다. 고객 사용 중에는 파일 이름을 바꾸거나 삭제하지 않는 것이 원칙입니다.")
    table = doc.add_table(rows=1, cols=3)
    for cell, header in zip(table.rows[0].cells, ("파일", "용도", "고객 사용 여부")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("시작하기.cmd", "더블클릭하면 라벨 출력 관리가 열립니다. 명령줄에 menu를 붙이면 점검·설정·디자인·백업·복원 메뉴가 열립니다.", "일상 사용"),
        ("처음실행_점검.cmd", "실행 전 점검, .gblabel 저장파일 연결, 출력 파일 생성 테스트, 고객 데이터 백업을 순서대로 실행하는 최초 설치용 점검 파일", "최초 설치 시 실행"),
        ("register_label_filetype.cmd", ".gblabel 저장파일 아이콘, 더블클릭 열기, 우클릭 인쇄 연결을 PowerShell 없이 등록", "최초 설치/문제 복구 시 실행"),
        ("버전정보.txt", "패키지명, 배포 생성시간, 고객 첫 실행 순서, 지원 문의 시 전달할 정보를 적은 버전 확인 파일", "지원/문의용"),
        ("고객데이터_백업.cmd", "설정, 상품 DB, 인쇄 데이터, 템플릿, assets/images 도안 이미지를 out 폴더의 ZIP으로 백업", "PC 교체 전 실행"),
        ("고객데이터_복원.cmd", "백업 ZIP에서 설정, 상품 DB, 인쇄 데이터, 템플릿, assets/images 도안 이미지를 현재 PC로 복원", "PC 교체 후 실행"),
        ("labels.xlsm", "품목 입력 및 라벨 출력 버튼이 들어 있는 Excel 파일", "사용"),
        ("라벨작업실행기.exe", "01/02/03/04 배치파일에서 사용하는 작업 실행기", "내부 실행 파일"),
        ("라벨출력엔진.exe", "라벨 명령 생성 및 프린터 전송 프로그램", "직접 실행하지 않음"),
        ("고객환경점검.exe", "필수 파일, 설정, 엑셀, 인쇄 데이터 바코드/매수, 출력 폴더, dry-run 점검과 지원 ZIP 저장", "최초 설치 또는 지원 요청 시 사용"),
        ("release_manifest.json", "배포 파일 구성과 해시 검증용 목록", "지원/검증용"),
        ("배포_파일목록.txt", "고객이 바로 읽을 수 있는 배포 파일 목록", "확인용"),
        ("라벨출력관리.exe", "DB 조회, 출력 데이터 선택, 인쇄 실행, 설정 메뉴의 실행 전 점검/사용안내 열기/지원 패키지 생성", "일상 사용"),
        ("라벨디자이너.exe", "빈 라벨·예제로 시작해 개체를 배치하고 .gblabel 파일을 저장하거나 .gbproject로 이동용 프로젝트를 내보냅니다.", "양식 제작/수정 시 사용"),
        ("templates\\sample_excel_product.gblabel", "기본 빈 라벨과 별도로 제공하는 상품 엑셀 연결 예제 도안", "처음 디자인 시 사용"),
        ("프린터설정.exe", "프린터 브랜드, 연결 방식, 용지 크기, 용지 유형, 인쇄 방식, 저장 전 점검 설정 프로그램", "설치 담당자 사용"),
        ("config.ini", "프린터 설정 저장 파일", "직접 수정하지 않음"),
        ("00_고객PC_실행전점검.cmd", "고객 환경 점검과 out\\customer_support_package.zip 저장", "최초 설치 시 실행"),
        ("00_install_trusted_location.cmd", "Excel 보안 신뢰 위치 자동 등록", "최초 1회 실행"),
        ("01_output_check.cmd", "프린터 전송 없이 출력 파일만 생성하는 점검용 파일", "문제 점검 시 사용"),
        ("03_open_output_folder.cmd", "생성된 라벨 명령 파일 폴더 열기", "문제 점검 시 사용"),
        ("04_open_last_log.cmd", "마지막 실행 로그 열기", "문제 점검 시 사용"),
    ]
    for row_data in rows:
        row = table.add_row().cells
        for cell, text in zip(row, row_data):
            fill_cell(cell, text)
    style_table(table, [2300, 5100, 1960])


def add_excel_usage(doc: Document) -> None:
    add_heading(doc, "3. Excel 입력 방법", 1)
    add_body(doc, "labels.xlsm의 표 한 줄이 라벨 한 종류입니다. 출력 매수는 print_qty 값으로 결정됩니다.")
    table = doc.add_table(rows=1, cols=4)
    for cell, header in zip(table.rows[0].cells, ("열 이름", "입력 내용", "예시", "비고")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("item_code", "품목 코드", "A1001", "라벨 상단 식별값"),
        ("item_name", "품목명", "센서 브라켓", "한글 입력 가능"),
        ("barcode", "바코드 값", "A1001-250531", "바코드로 실제 인쇄되는 값"),
        ("lot_no", "LOT 번호", "LOT250531", "추적용 LOT 정보"),
        ("qty", "수량", "100", "라벨에 표시되는 기준 수량"),
        ("print_qty", "출력 매수", "1", "해당 행을 몇 장 출력할지 입력"),
    ]
    for row_data in rows:
        row = table.add_row().cells
        for cell, text in zip(row, row_data):
            fill_cell(cell, text)
    style_table(table, [1900, 2500, 2100, 2860])

    add_heading(doc, "출력 흐름", 2)
    workflow = doc.add_table(rows=1, cols=4)
    for cell, header in zip(workflow.rows[0].cells, ("입력", "버튼", "전송", "기록")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    row = workflow.add_row().cells
    for cell, text in zip(
        row,
        (
            "Excel 표 내용을 수정",
            "라벨 출력 클릭",
            "프린터로 즉시 전송",
            "last_run.log와 print_log.xlsx에 결과 저장",
        ),
    ):
        fill_cell(cell, text)
    style_table(workflow, [2340, 2340, 2340, 2340])

    add_callout(
        doc,
        "입력 시 주의",
        "barcode가 비어 있으면 정상 라벨을 만들 수 없습니다. 앞자리 0이 있는 바코드는 Excel에서 문자로 저장하는 것이 가장 안전합니다. "
        "순수한 0 채우기 숫자 서식은 화면 표시값을 읽지만, 복잡한 숫자 서식이나 15자리를 넘는 숫자 값은 확인 후 문자로 고쳐야 합니다. "
        "print_qty는 실제 출력 매수이므로 테스트 후 고객 운영 수량에 맞춰 입력해 주세요.",
    )


def add_daily_operation(doc: Document) -> None:
    add_heading(doc, "4. 일상 사용 절차", 1)
    table = doc.add_table(rows=1, cols=2)
    for cell, header in zip(table.rows[0].cells, ("작업", "상세 설명")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("1. 출력 화면 열기", "시작하기.cmd를 더블클릭해 라벨 출력 관리를 엽니다."),
        ("2. 상품 찾기", "DB 파일 > DB 연결에서 상품 엑셀을 선택하고 상품명·바코드를 검색합니다."),
        ("3. 대상 선택", "인쇄 데이터에서 필요한 행을 직접 선택합니다. 선택 항목이 없으면 인쇄가 시작되지 않습니다."),
        ("4. 매수와 전송", "인쇄를 눌러 1~100장의 매수를 지정하고 대상 건수를 확인한 뒤 인쇄 시작을 누릅니다."),
        ("5. 실물 확인", "전송 완료 안내 후 프린터에서 라벨 배출·위치·바코드 판독을 확인합니다."),
    ]
    for row_data in rows:
        row = table.add_row().cells
        fill_cell(row[0], row_data[0], bold=True, color=COLOR_BLUE_DARK)
        fill_cell(row[1], row_data[1])
    style_table(table, [2300, 7060])

    add_body(
        doc,
        "중요: 전체 인쇄가 필요하면 전체 선택을 직접 누른 뒤 대상 건수와 매수를 확인하세요. 선택 없이 인쇄 버튼을 누르면 출력이 차단됩니다.",
        bold_prefix="중요:",
    )
    add_body(
        doc,
        "인쇄 전 점검: 라벨출력관리.exe는 실제 인쇄 직전에 바코드 누락, 출력 매수 오류, config.ini 프린터 설정 오류를 먼저 확인합니다. 오류가 표시되면 해당 행 또는 프린터 설정을 수정한 뒤 다시 인쇄하세요.",
        bold_prefix="인쇄 전 점검:",
    )
    add_body(
        doc,
        "도움말: 라벨출력관리.exe의 설정 메뉴에서 실행 전 점검, 빠른 사용안내, 상세 매뉴얼, 지원 패키지, 고객 데이터 백업·복원을 열 수 있습니다. 라벨 디자인은 상단의 별도 버튼입니다. 01/02 배치파일은 라벨작업실행기.exe를 우선 사용합니다.",
        bold_prefix="도움말:",
    )
    add_body(
        doc,
        "Excel 매크로 사용: labels.xlsm을 사용하는 사업장은 상품 정보를 수정하고 저장한 뒤 라벨 출력 버튼을 사용합니다. 먼저 00_install_trusted_location.cmd로 Excel 신뢰 위치를 등록하세요. 디자이너의 인쇄파일 생성은 프린터로 보내지 않는 사전 확인입니다.",
        bold_prefix="디자이너 출력:",
    )


def add_label_designer_usage(doc: Document) -> None:
    add_heading(doc, "5. 라벨 디자이너", 1)
    add_body(doc, "라벨디자이너.exe는 양식을 만들거나 수정할 때 사용합니다. 처음 화면에서 빈 라벨, 예제로 시작, 최근 라벨 열기 중 하나를 고릅니다. 기본 템플릿은 개체가 없는 빈 라벨입니다.")

    table = doc.add_table(rows=1, cols=2)
    for cell, header in zip(table.rows[0].cells, ("순서", "작업 방법")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("1. 시작", "예제로 시작을 누르면 상품 엑셀과 예제 도안이 연결됩니다. 자신의 양식은 새 라벨에서 만들고, 작업 파일은 저장 버튼 또는 Ctrl+S로 .gblabel에 저장합니다."),
        ("2. 크기와 개체", "실제 용지의 가로·세로(mm)를 입력하고 텍스트, 1D/2D 바코드, 그림, 박스, 선, 표를 넣습니다. 개체 속성에서 크기와 위치를 확인합니다."),
        ("3. 상품 연결", "상품 엑셀 연결에서 .xlsx/.xlsm을 열고 개체의 열을 연결합니다. 상품 선택에서 출력할 행만 고릅니다."),
        ("4. 출력 전 확인", "인쇄파일을 먼저 생성하고 미리보기·행·매수를 확인합니다. 경계 밖 개체, 비어 있는 필수 값, 작은 QR·글자 축소 경고를 확인한 뒤 실제 인쇄합니다."),
    ]
    for row_data in rows:
        row = table.add_row().cells
        fill_cell(row[0], row_data[0], bold=True, color=COLOR_BLUE_DARK)
        fill_cell(row[1], row_data[1])
    style_table(table, [2200, 7160])

    add_heading(doc, "편집과 복구", 2)
    add_body(doc, "Ctrl+클릭으로 여러 개체를 선택합니다. 복제, 그룹, 그룹 해제, 잠금/해제, 왼쪽 정렬, 가로 간격 맞춤과 눈금 맞춤을 사용할 수 있습니다. 방향키는 1mm, Shift+방향키는 0.1mm씩 이동합니다. 화면 맞춤과 확대·축소는 보기 크기만 바꿉니다.")
    add_body(doc, "Ctrl+Z는 실행취소, Ctrl+Y는 다시실행입니다. 저장하지 않은 변경사항은 파일명과 창 제목의 *로 보입니다. 비정상 종료 후 복구 제안이 나타나면 저장한 원본을 덮어쓰지 않는 작업 사본으로 확인합니다.")

    add_heading(doc, "도안 인식과 이동", 2)
    add_body(doc, "도안 불러오기에서 PNG/JPG/PSD를 선택하고 도안 적용을 누르면 편집 가능한 후보 개체가 생성됩니다. 인식 값 검토에서 원본 이미지와 후보를 나란히 비교해 글자·바코드 값을 직접 수정하고 확인해야 출력할 수 있습니다.")
    add_body(doc, "다른 PC로 옮길 때는 파일 메뉴의 이동용 프로젝트 내보내기로 .gbproject를 만듭니다. 가져온 PC에서는 상품 엑셀 경로를 다시 연결하고, 그림·글꼴·라벨 크기·인쇄 설정을 확인합니다. 프로젝트 가져오기는 기존 고객 데이터를 덮어쓰지 않습니다.")
    add_body(doc, "BarTender .btw 파일은 직접 열 수 없습니다. 원본 도안을 PNG로 내보내어 참고 도안으로 불러온 뒤 개체와 데이터 열을 다시 연결합니다. 수식·변수·프린터 설정까지 자동 변환되는 기능은 아닙니다.")

    add_callout(
        doc,
        "실제 출력 확인",
        "프린터 전송 완료는 라벨이 실제로 나왔다는 뜻이 아닙니다. 프린터에서 배출·위치·스캔을 확인하세요. 전송 중단으로 결과가 미확인인 항목은 실물을 먼저 확인하고 화면에서 전송됨 또는 재전송 대상으로 직접 결정해야 중복 출력을 줄일 수 있습니다.",
        COLOR_ACCENT_FILL,
    )


def add_installer_settings(doc: Document) -> None:
    add_heading(doc, "6. 설치 담당자용 설정", 1)
    add_body(doc, "고객에게 전달하기 전 프린터설정.exe에서 프린터 환경만 맞춰 두면 됩니다. config.ini는 직접 열지 않아도 됩니다.")

    table = doc.add_table(rows=1, cols=3)
    for cell, header in zip(table.rows[0].cells, ("설정 항목", "값", "설명")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("브랜드", "BIXOLON / TSC / Zebra / SEWOO(ZPL)", "고객이 사용하는 프린터 브랜드 한 가지를 선택합니다."),
        ("연결 방식", "LAN / USB", "LAN은 IP 직접 전송, USB는 Windows 프린터 큐를 통해 전송합니다."),
        ("인쇄 방식", "감열 / 열전사", "감열은 리본 없음, 열전사는 리본 사용 환경입니다."),
        ("ip, port", "예: 192.168.0.130 / 9100", "network 방식일 때 프린터 IP와 포트를 입력합니다."),
        ("windows_printer_name", "auto 또는 프린터 이름", "windows_raw 방식일 때 Windows 프린터 이름을 지정합니다."),
        ("width_mm, height_mm", "예: 50 / 30", "라벨 용지 가로, 세로 크기입니다."),
        ("media_type", "gap / black_mark / continuous", "갭 용지, 블랙마크 용지, 연속 용지 중 실제 라벨지를 선택합니다."),
        ("gap_mm", "예: 3", "갭 용지와 블랙마크 용지는 0보다 크게 입력합니다. 연속 용지는 0을 권장합니다."),
    ]
    for row_data in rows:
        row = table.add_row().cells
        for cell, text in zip(row, row_data):
            fill_cell(cell, text)
    style_table(table, [2300, 2700, 4360])

    add_callout(
        doc,
        "브랜드별 기본값",
        "BIXOLON은 cp949 계열 명령 인코딩을 사용하고, TSC, Zebra, SEWOO(ZPL)는 UTF-8 기반 명령을 사용합니다. "
        "language와 command_encoding은 auto 상태로 두면 brand 값에 맞춰 자동 적용됩니다.",
        COLOR_ACCENT_FILL,
    )
    add_callout(
        doc,
        "저장 전 점검",
        "프린터설정.exe의 설정 점검 버튼은 IP/포트, Windows 프린터 이름, 용지 유형, 간격, DPI, 브랜드별 인쇄후작업 지원 여부를 확인합니다. "
        "오류가 표시되면 저장하지 말고 실제 장비 설정과 라벨지를 먼저 맞춘 뒤 다시 저장하세요.",
        COLOR_WARNING_FILL,
    )
    add_callout(
        doc,
        "저장하지 않은 변경사항",
        "프린터설정.exe에서 값을 바꾸면 창 제목 끝에 * 표시가 붙습니다. 저장하지 않은 상태로 현재 설정을 다시 불러오거나 창을 닫으려 하면 확인창이 표시되므로, 실수로 작업 중인 설정을 잃지 않도록 안내에 따라 선택하세요.",
        COLOR_ACCENT_FILL,
    )


def add_troubleshooting(doc: Document) -> None:
    add_heading(doc, "7. 문제 해결", 1)
    table = doc.add_table(rows=1, cols=3)
    for cell, header in zip(table.rows[0].cells, ("증상", "확인할 내용", "조치")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        (
            "처음 설치 후 정상 여부를 모르겠음",
            "배포 폴더 필수 파일, 설정, 엑셀, 인쇄 데이터 바코드/매수, dry-run",
            "00_고객PC_실행전점검.cmd를 실행해 오류 항목을 확인하고 out\\customer_support_package.zip을 보관합니다.",
        ),
        (
            "Excel에서 매크로 보안 경고가 나옴",
            "신뢰 위치 등록 여부",
            "Excel을 닫고 00_install_trusted_location.cmd를 실행한 뒤 다시 엽니다.",
        ),
        (
            "라벨 출력 버튼을 눌러도 출력되지 않음",
            "인쇄 전 점검 메시지, 프린터 전원, 네트워크, config.ini IP",
            "먼저 바코드 누락, 출력 매수 오류, 프린터 설정 오류 메시지를 수정합니다. 이후 04_open_last_log.cmd로 마지막 로그를 열고 IP와 포트 9100 연결 상태를 확인합니다.",
        ),
        (
            "한글이 깨져 출력됨",
            "config.ini의 brand 값과 실제 프린터 브랜드",
            "브랜드 값을 실제 장비에 맞추고, 프린터가 한글 폰트/코드페이지를 지원하는지 확인합니다.",
        ),
        (
            "바코드가 비어 있거나 스캔되지 않음",
            "Excel의 barcode 열",
            "barcode 값을 비우지 말고 스캐너가 읽을 수 있는 값으로 입력합니다.",
        ),
        (
            "원하는 매수보다 많이 출력됨",
            "Excel의 print_qty 열",
            "행별 print_qty 값을 실제 필요한 매수로 수정합니다.",
        ),
        (
            "인쇄할 항목이 없다는 안내가 나옴",
            "인쇄 데이터의 선택 칸",
            "필요한 행을 직접 체크합니다. 전체 인쇄가 의도라면 전체 선택을 누른 뒤 대상 건수와 매수를 다시 확인합니다.",
        ),
        (
            "도안 인식 뒤 출력이 차단됨",
            "인식 값 검토의 미확인 글자·바코드",
            "원본 이미지와 값을 대조하고 인식 값 검토에서 확인합니다. 임시 바코드 값은 원본으로 교체합니다.",
        ),
        (
            "이전 PC의 도안 그림이나 상품 엑셀이 보이지 않음",
            ".gblabel만 복사했는지, .gbproject로 옮겼는지",
            "파일 메뉴의 이동용 프로젝트를 가져오고 새 PC에서 상품 엑셀을 다시 연결합니다. 원본 엑셀 파일은 별도 보관해야 합니다.",
        ),
        (
            "BarTender .btw 파일이 열리지 않음",
            "지원 파일 종류",
            ".btw 직접 열기는 지원하지 않습니다. BarTender에서 PNG로 내보낸 뒤 도안 불러오기로 재작성하고 필드·바코드·인쇄 결과를 확인합니다.",
        ),
        (
            "출력 파일만 생성하고 싶음",
            "프린터 전송 전 사전 점검 필요 여부",
            "01_output_check.cmd를 실행한 뒤 out 폴더의 명령 파일을 확인합니다.",
        ),
        (
            "지원 담당자에게 원인 확인을 요청함",
            "점검 보고서, 마지막 실행 로그, 출력 이력",
            "라벨출력관리.exe의 설정 > 지원 패키지 생성 메뉴를 눌러 out\\customer_support_package.zip을 새로 만든 뒤 전달합니다. "
            "ZIP 안의 environment_summary.txt, file_inventory.txt, release_manifest_summary.txt로 설치 위치와 누락 파일을 확인할 수 있고 원본 DB와 인쇄 데이터는 포함되지 않습니다.",
        ),
        (
            "PC 교체나 재설치 전 데이터 백업",
            "config.ini, DB, 인쇄 데이터, 템플릿, 도안 이미지",
            "라벨출력관리.exe의 설정 > 고객 데이터 백업 또는 고객데이터_백업.cmd를 실행해 out\\chaeumlab_customer_backup_*.zip을 별도 보관합니다.",
        ),
        (
            "PC 교체나 재설치 후 데이터 복원",
            "백업 ZIP, 기존 현재 데이터",
            "고객데이터_복원.cmd에서 백업 ZIP을 선택합니다. 복원 전 현재 데이터는 out 폴더에 pre-restore 백업으로 먼저 저장됩니다.",
        ),
    ]
    for row_data in rows:
        row = table.add_row().cells
        for cell, text in zip(row, row_data):
            fill_cell(cell, text)
    style_table(table, [2700, 2800, 3860])


def add_support(doc: Document) -> None:
    add_heading(doc, "8. 납품 정보", 1)
    add_body(doc, "아래 정보는 실제 판매처 정보로 수정해 고객에게 전달하면 됩니다.")
    table = doc.add_table(rows=4, cols=2)
    rows = [
        ("공급사", "판매처명을 입력하세요"),
        ("담당자", "담당자명을 입력하세요"),
        ("연락처", "전화번호 또는 카카오톡 채널을 입력하세요"),
        ("이메일", "support@example.com"),
    ]
    for row, (label, value) in zip(table.rows, rows):
        fill_cell(row.cells[0], label, bold=True, color=COLOR_NAVY)
        fill_cell(row.cells[1], value)
    style_table(table, [2300, 7060], header_rows=0)
    for row in table.rows:
        set_cell_shading(row.cells[0], COLOR_HEADER_FILL)


def configure_document() -> Document:
    doc = Document()
    section = doc.sections[0]
    section.start_type = WD_SECTION_START.NEW_PAGE
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.right_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)
    add_footer(section)

    styles = doc.styles
    normal = styles["Normal"]
    set_style_font(normal, 11, "111827")
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.35

    set_style_font(styles["Heading 1"], 18, COLOR_BLUE, True)
    styles["Heading 1"].paragraph_format.space_before = Pt(22)
    styles["Heading 1"].paragraph_format.space_after = Pt(12)
    styles["Heading 1"].paragraph_format.line_spacing = 1.25

    set_style_font(styles["Heading 2"], 14, COLOR_BLUE, True)
    styles["Heading 2"].paragraph_format.space_before = Pt(16)
    styles["Heading 2"].paragraph_format.space_after = Pt(8)
    styles["Heading 2"].paragraph_format.line_spacing = 1.25

    set_style_font(styles["Heading 3"], 12, COLOR_BLUE_DARK, True)
    styles["Heading 3"].paragraph_format.space_before = Pt(10)
    styles["Heading 3"].paragraph_format.space_after = Pt(5)
    styles["Heading 3"].paragraph_format.line_spacing = 1.25

    return doc


def main() -> None:
    CUSTOMER_DIR.mkdir(parents=True, exist_ok=True)
    doc = configure_document()
    add_cover(doc)
    add_quick_start(doc)
    add_file_map(doc)
    add_excel_usage(doc)
    add_daily_operation(doc)
    add_label_designer_usage(doc)
    add_installer_settings(doc)
    add_troubleshooting(doc)
    add_support(doc)
    doc.core_properties.title = "채움LAB 라벨 출력 패키지 고객용 프로그램 매뉴얼"
    doc.core_properties.subject = "Excel 기반 라벨 출력 패키지 사용 설명서"
    doc.core_properties.author = "채움LAB"
    doc.save(OUTPUT_DOCX)
    copy2(OUTPUT_DOCX, ROOT / OUTPUT_DOCX.name)
    copy2(OUTPUT_DOCX, ROOT.parent / OUTPUT_DOCX.name)
    print(OUTPUT_DOCX)


if __name__ == "__main__":
    main()
