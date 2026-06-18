from __future__ import annotations

from pathlib import Path

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
COLOR_NAVY = "0B2545"
COLOR_BLUE = "2E74B5"
COLOR_BLUE_DARK = "1F4D78"
COLOR_MUTED = "5B677A"
COLOR_GRID = "D8DEE8"
COLOR_HEADER_FILL = "E8EEF5"
COLOR_LIGHT_FILL = "F4F6F9"
COLOR_ACCENT_FILL = "EAF4FF"
COLOR_WARNING_FILL = "FFF7E0"


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
                        set_run_font(run, size_pt=9.5, bold=True, color=COLOR_NAVY)
            else:
                for p in cell.paragraphs:
                    for run in p.runs:
                        set_run_font(run, size_pt=9.2, color="111827")
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.15


def fill_cell(cell, text: str, bold: bool = False, color: str = "111827", size_pt: float = 9.2) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    set_run_font(run, size_pt=size_pt, bold=bold, color=color)


def add_heading(doc: Document, text: str, level: int) -> None:
    p = doc.add_heading(text, level=level)
    if level == 1:
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(10)
        set_paragraph_font(p, size_pt=16, bold=True, color=COLOR_BLUE)
    elif level == 2:
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(7)
        set_paragraph_font(p, size_pt=13, bold=True, color=COLOR_BLUE)
    else:
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(5)
        set_paragraph_font(p, size_pt=12, bold=True, color=COLOR_BLUE_DARK)


def add_body(doc: Document, text: str, bold_prefix: str | None = None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.25
    if bold_prefix and text.startswith(bold_prefix):
        r1 = p.add_run(bold_prefix)
        set_run_font(r1, size_pt=10.5, bold=True, color=COLOR_NAVY)
        r2 = p.add_run(text[len(bold_prefix) :])
        set_run_font(r2, size_pt=10.5, color="111827")
    else:
        r = p.add_run(text)
        set_run_font(r, size_pt=10.5, color="111827")


def add_callout(doc: Document, title: str, body: str, fill: str = COLOR_LIGHT_FILL) -> None:
    table = doc.add_table(rows=1, cols=1)
    style_table(table, [9360], header_rows=0)
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    cell.text = ""
    p_title = cell.paragraphs[0]
    p_title.paragraph_format.space_after = Pt(3)
    r_title = p_title.add_run(title)
    set_run_font(r_title, size_pt=10.5, bold=True, color=COLOR_NAVY)
    p_body = cell.add_paragraph()
    p_body.paragraph_format.space_after = Pt(0)
    p_body.paragraph_format.line_spacing = 1.2
    r_body = p_body.add_run(body)
    set_run_font(r_body, size_pt=9.5, color="263241")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_footer(section) -> None:
    footer = section.footer
    footer.is_linked_to_previous = False
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run("라벨 출력 패키지 고객용 매뉴얼 | 2026-06-01")
    set_run_font(run, size_pt=8.5, color=COLOR_MUTED)


def add_cover(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run("라벨 출력 패키지")
    set_run_font(r, size_pt=28, bold=True, color=COLOR_NAVY)

    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(20)
    r2 = p2.add_run("고객용 프로그램 매뉴얼")
    set_run_font(r2, size_pt=18, bold=True, color=COLOR_BLUE)

    metadata = doc.add_table(rows=4, cols=2)
    rows = [
        ("문서 용도", "고객 PC 설치 후 Excel에서 라벨을 바로 출력하기 위한 사용 설명서"),
        ("지원 프린터", "BIXOLON, TSC, Zebra 라벨 프린터"),
        ("배포 폴더", "고객용_실행폴더"),
        ("문서 버전", "1.0 / 2026-06-01"),
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
        "고객은 프린터설정.exe로 장비 환경을 저장한 뒤 labels.xlsm에서 라벨 출력 버튼만 누르면 됩니다. "
        "config.ini는 설정 프로그램이 자동으로 갱신합니다.",
        COLOR_ACCENT_FILL,
    )
    doc.add_page_break()


def add_quick_start(doc: Document) -> None:
    add_heading(doc, "1. 빠른 시작", 1)
    add_body(
        doc,
        "처음 설치한 PC에서는 아래 순서대로 한 번만 준비하면 됩니다. 이후에는 Excel 파일을 열고 라벨 출력 버튼만 사용합니다.",
    )
    table = doc.add_table(rows=1, cols=3)
    headers = ("순서", "실행 내용", "완료 기준")
    for cell, header in zip(table.rows[0].cells, headers):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("1", "고객용_실행폴더를 고객 PC의 원하는 위치에 복사합니다.", "폴더 안에 labels.xlsm, print_labels.exe, config.ini가 함께 있습니다."),
        ("2", "00_install_trusted_location.cmd를 마우스 오른쪽 버튼으로 실행합니다.", "Excel 보안 경고 없이 매크로 버튼을 사용할 준비가 됩니다."),
        ("3", "프린터설정.exe를 열어 브랜드, 연결 방식, 용지 크기, 인쇄 방식을 저장합니다.", "config.ini가 자동으로 갱신됩니다."),
        ("4", "labels.xlsm을 열고 품목 정보를 입력한 뒤 라벨 출력 버튼을 누릅니다.", "확인창 없이 즉시 출력 작업이 실행됩니다."),
    ]
    for row_data in rows:
        row = table.add_row().cells
        for cell, text in zip(row, row_data):
            fill_cell(cell, text)
    style_table(table, [900, 4300, 4160])

    add_callout(
        doc,
        "고객 안내 문구",
        "라벨 출력 버튼은 누르는 즉시 프린터로 전송됩니다. 테스트가 필요하면 설치 담당자가 먼저 01_output_check.cmd로 출력 파일 생성만 확인해 주세요.",
        COLOR_WARNING_FILL,
    )


def add_file_map(doc: Document) -> None:
    add_heading(doc, "2. 배포 폴더 구성", 1)
    add_body(doc, "아래 파일은 같은 폴더 안에 있어야 합니다. 고객 사용 중에는 파일 이름을 바꾸거나 삭제하지 않는 것이 원칙입니다.")
    table = doc.add_table(rows=1, cols=3)
    for cell, header in zip(table.rows[0].cells, ("파일", "용도", "고객 사용 여부")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("labels.xlsm", "품목 입력 및 라벨 출력 버튼이 들어 있는 Excel 파일", "사용"),
        ("print_labels.exe", "라벨 명령 생성 및 프린터 전송 프로그램", "직접 실행하지 않음"),
        ("프린터설정.exe", "프린터 브랜드, 연결 방식, 용지 크기, 인쇄 방식 설정 프로그램", "설치 담당자 사용"),
        ("config.ini", "프린터 설정 저장 파일", "직접 수정하지 않음"),
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
        "barcode가 비어 있으면 정상 라벨을 만들 수 없습니다. print_qty는 실제 출력 매수이므로 테스트 후 고객 운영 수량에 맞춰 입력해 주세요.",
    )


def add_daily_operation(doc: Document) -> None:
    add_heading(doc, "4. 일상 사용 절차", 1)
    table = doc.add_table(rows=1, cols=2)
    for cell, header in zip(table.rows[0].cells, ("작업", "상세 설명")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("1. Excel 열기", "고객용_실행폴더 안의 labels.xlsm을 엽니다."),
        ("2. 데이터 입력", "품목 코드, 품목명, 바코드, LOT 번호, 수량, 출력 매수를 행별로 입력합니다."),
        ("3. 라벨 출력", "화면 오른쪽의 빨간 라벨 출력 버튼을 클릭합니다. 별도 확인창 없이 바로 실행됩니다."),
        ("4. 결과 확인", "프린터 출력물을 확인합니다. 필요하면 04_open_last_log.cmd로 마지막 실행 내용을 확인합니다."),
    ]
    for row_data in rows:
        row = table.add_row().cells
        fill_cell(row[0], row_data[0], bold=True, color=COLOR_BLUE_DARK)
        fill_cell(row[1], row_data[1])
    style_table(table, [2300, 7060])

    add_body(
        doc,
        "중요: 같은 Excel 파일에서 내용을 수정한 뒤 라벨 출력 버튼을 다시 누르면, 수정된 현재 표 내용이 새로 반영되어 출력됩니다.",
        bold_prefix="중요:",
    )


def add_installer_settings(doc: Document) -> None:
    add_heading(doc, "5. 설치 담당자용 설정", 1)
    add_body(doc, "고객에게 전달하기 전 프린터설정.exe에서 프린터 환경만 맞춰 두면 됩니다. config.ini는 직접 열지 않아도 됩니다.")

    table = doc.add_table(rows=1, cols=3)
    for cell, header in zip(table.rows[0].cells, ("설정 항목", "값", "설명")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        ("브랜드", "BIXOLON / TSC / Zebra", "고객이 사용하는 프린터 브랜드 한 가지를 선택합니다."),
        ("연결 방식", "LAN / USB", "LAN은 IP 직접 전송, USB는 Windows 프린터 큐를 통해 전송합니다."),
        ("인쇄 방식", "감열 / 열전사", "감열은 리본 없음, 열전사는 리본 사용 환경입니다."),
        ("ip, port", "예: 192.168.0.130 / 9100", "network 방식일 때 프린터 IP와 포트를 입력합니다."),
        ("windows_printer_name", "auto 또는 프린터 이름", "windows_raw 방식일 때 Windows 프린터 이름을 지정합니다."),
        ("width_mm, height_mm", "예: 50 / 30", "라벨 용지 가로, 세로 크기입니다."),
        ("gap_mm", "예: 3", "라벨 간격입니다. 갭 라벨 기준으로 사용합니다."),
    ]
    for row_data in rows:
        row = table.add_row().cells
        for cell, text in zip(row, row_data):
            fill_cell(cell, text)
    style_table(table, [2300, 2700, 4360])

    add_callout(
        doc,
        "브랜드별 기본값",
        "BIXOLON과 TSC는 한글 출력을 위해 cp949 계열 명령 인코딩을 사용하고, Zebra는 UTF-8 기반 ZPL을 사용합니다. "
        "language와 command_encoding은 auto 상태로 두면 brand 값에 맞춰 자동 적용됩니다.",
        COLOR_ACCENT_FILL,
    )


def add_troubleshooting(doc: Document) -> None:
    add_heading(doc, "6. 문제 해결", 1)
    table = doc.add_table(rows=1, cols=3)
    for cell, header in zip(table.rows[0].cells, ("증상", "확인할 내용", "조치")):
        fill_cell(cell, header, bold=True, color=COLOR_NAVY)
    rows = [
        (
            "Excel에서 매크로 보안 경고가 나옴",
            "신뢰 위치 등록 여부",
            "Excel을 닫고 00_install_trusted_location.cmd를 실행한 뒤 다시 엽니다.",
        ),
        (
            "라벨 출력 버튼을 눌러도 출력되지 않음",
            "프린터 전원, 네트워크, config.ini IP",
            "04_open_last_log.cmd로 마지막 로그를 열고, IP와 포트 9100 연결 상태를 확인합니다.",
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
            "출력 파일만 생성하고 싶음",
            "프린터 전송 전 사전 점검 필요 여부",
            "01_output_check.cmd를 실행한 뒤 out 폴더의 명령 파일을 확인합니다.",
        ),
    ]
    for row_data in rows:
        row = table.add_row().cells
        for cell, text in zip(row, row_data):
            fill_cell(cell, text)
    style_table(table, [2700, 2800, 3860])


def add_support(doc: Document) -> None:
    add_heading(doc, "7. 납품 정보", 1)
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
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    set_style_font(styles["Heading 1"], 16, COLOR_BLUE, True)
    styles["Heading 1"].paragraph_format.space_before = Pt(18)
    styles["Heading 1"].paragraph_format.space_after = Pt(10)
    styles["Heading 1"].paragraph_format.line_spacing = 1.25

    set_style_font(styles["Heading 2"], 13, COLOR_BLUE, True)
    styles["Heading 2"].paragraph_format.space_before = Pt(14)
    styles["Heading 2"].paragraph_format.space_after = Pt(7)
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
    add_installer_settings(doc)
    add_troubleshooting(doc)
    add_support(doc)
    doc.core_properties.title = "라벨 출력 패키지 고객용 프로그램 매뉴얼"
    doc.core_properties.subject = "Excel 기반 라벨 출력 패키지 사용 설명서"
    doc.core_properties.author = "라벨 출력 패키지"
    doc.save(OUTPUT_DOCX)
    print(OUTPUT_DOCX)


if __name__ == "__main__":
    main()
