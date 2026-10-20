from __future__ import annotations

"""Build customer manuals with a step-first, print-manual layout.

The PDFs deliberately use one clear action area per page.  Screens are cropped
and enlarged instead of being placed as small full-screen captures with labels.
"""

from pathlib import Path
from shutil import copy2

from verify_customer_manuals import capture_contract_errors

from PIL import Image as PilImage
from PIL import ImageDraw, ImageFilter, ImageFont, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "brand"
SCREENSHOTS = ROOT / "outputs" / "ui-redesign-preview"
OUTPUT = ROOT / "docs" / "고객용_매뉴얼"
TOP_LEVEL = ROOT.parent
CUSTOMER_RUNTIME = ROOT / "고객용_실행폴더"

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_X = 20 * mm
MARGIN_TOP = 18 * mm
MARGIN_BOTTOM = 17 * mm
CONTENT_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)

INK = colors.HexColor("#171D23")
INK_SOFT = colors.HexColor("#34414B")
TEAL = colors.HexColor("#143E70")
TEAL_DARK = colors.HexColor("#143E70")
MINT = colors.HexColor("#A3D900")
MINT_PALE = colors.HexColor("#FFFFFF")
PAPER = colors.HexColor("#FFFFFF")
WARM = colors.HexColor("#F3F5F7")
LINE = colors.HexColor("#D8DEE0")
MUTED = colors.HexColor("#68747C")
CAUTION = colors.HexColor("#FFF7E7")


def register_fonts() -> None:
    regular = Path(r"C:\Windows\Fonts\malgun.ttf")
    bold = Path(r"C:\Windows\Fonts\malgunbd.ttf")
    if not regular.exists() or not bold.exists():
        raise RuntimeError("맑은 고딕 Regular/Bold 글꼴을 찾을 수 없습니다.")
    if "ManualMalgun" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("ManualMalgun", str(regular)))
        pdfmetrics.registerFont(TTFont("ManualMalgunBold", str(bold)))
        pdfmetrics.registerFontFamily(
            "ManualMalgun",
            normal="ManualMalgun",
            bold="ManualMalgunBold",
            italic="ManualMalgun",
            boldItalic="ManualMalgunBold",
        )


register_fonts()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    return {
        "eyebrow": ParagraphStyle("Eyebrow", parent=base, fontName="ManualMalgunBold", fontSize=9.2, leading=12, textColor=TEAL, spaceAfter=3),
        "cover": ParagraphStyle("Cover", parent=base, fontName="ManualMalgunBold", fontSize=29, leading=38, textColor=INK),
        "cover_sub": ParagraphStyle("CoverSub", parent=base, fontName="ManualMalgun", fontSize=12.2, leading=20, textColor=INK_SOFT),
        "section_no": ParagraphStyle("SectionNo", parent=base, fontName="ManualMalgunBold", fontSize=27, leading=30, textColor=TEAL, alignment=TA_CENTER),
        "section": ParagraphStyle("Section", parent=base, fontName="ManualMalgunBold", fontSize=19, leading=25, textColor=INK, spaceAfter=2),
        "section_sub": ParagraphStyle("SectionSub", parent=base, fontName="ManualMalgun", fontSize=10.4, leading=16, textColor=MUTED, spaceAfter=7),
        "body": ParagraphStyle("Body", parent=base, fontName="ManualMalgun", fontSize=11.0, leading=18.2, textColor=INK, spaceAfter=5),
        "body_small": ParagraphStyle("BodySmall", parent=base, fontName="ManualMalgun", fontSize=10.0, leading=15.8, textColor=INK_SOFT),
        "step": ParagraphStyle("Step", parent=base, fontName="ManualMalgun", fontSize=11.0, leading=18, textColor=INK),
        "step_title": ParagraphStyle("StepTitle", parent=base, fontName="ManualMalgunBold", fontSize=11.2, leading=16, textColor=INK),
        "note_title": ParagraphStyle("NoteTitle", parent=base, fontName="ManualMalgunBold", fontSize=10.2, leading=14, textColor=TEAL_DARK),
        "note": ParagraphStyle("Note", parent=base, fontName="ManualMalgun", fontSize=10.1, leading=15.5, textColor=INK_SOFT),
        "caption": ParagraphStyle("Caption", parent=base, fontName="ManualMalgun", fontSize=9.4, leading=13.6, alignment=TA_CENTER, textColor=MUTED),
        "toc": ParagraphStyle("Toc", parent=base, fontName="ManualMalgun", fontSize=10.7, leading=17, textColor=INK),
        "toc_no": ParagraphStyle("TocNo", parent=base, fontName="ManualMalgunBold", fontSize=14.2, leading=18, alignment=TA_CENTER, textColor=colors.white),
    }


S = styles()


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), S[style])


def heading(number: str, title: str, subtitle: str, bookmark: str) -> list:
    heading_table = Table(
        [[p(number, "section_no"), [p(title, "section"), p(subtitle, "section_sub")]]],
        colWidths=[18 * mm, CONTENT_WIDTH - 18 * mm],
    )
    heading_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), MINT_PALE),
        ("BOX", (0, 0), (0, 0), 0.5, MINT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 2),
        ("RIGHTPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 0), (0, 0), 7),
        ("BOTTOMPADDING", (0, 0), (0, 0), 7),
        ("LEFTPADDING", (1, 0), (1, 0), 9),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (1, 0), (1, 0), 1),
        ("BOTTOMPADDING", (1, 0), (1, 0), 1),
    ]))
    heading_table.bookmark_name = bookmark
    heading_table.outline_text = f"{number}. {title}"
    return [heading_table, Spacer(1, 5 * mm)]


class ManualDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable) -> None:  # noqa: N802
        bookmark = getattr(flowable, "bookmark_name", None)
        if bookmark:
            self.canv.bookmarkPage(bookmark)
            self.canv.addOutlineEntry(flowable.outline_text, bookmark, level=0, closed=False)


def thin_rule() -> Table:
    rule = Table([[""]], colWidths=[CONTENT_WIDTH], rowHeights=[0.75 * mm])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MINT), ("LINEBELOW", (0, 0), (-1, -1), 0, MINT)]))
    return rule


def note(title: str, body: str, fill: colors.Color = WARM) -> Table:
    data = [[p(title, "note_title")], [p(body, "note")]]
    card = Table(data, colWidths=[CONTENT_WIDTH])
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, MINT),
        ("BOX", (0, 0), (-1, -1), 0.45, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
    ]))
    return card


def step(number: int, title: str, text: str, check: str | None = None) -> Table:
    badge = Table([[p(f"{number:02d}", "toc_no")]], colWidths=[13 * mm], rowHeights=[13 * mm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    body = f'<b>{title}</b><br/>{text}'
    if check:
        body += f'<br/><font color="#143E70"><b>확인</b>  {check}</font>'
    card = Table([[badge, p(body, "step")]], colWidths=[17 * mm, CONTENT_WIDTH - 17 * mm])
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 2),
        ("RIGHTPADDING", (0, 0), (0, -1), 2),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("RIGHTPADDING", (1, 0), (1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return card


def toc(items: list[tuple[str, str]]) -> Table:
    rows = []
    for no, title in items:
        badge = Table([[p(no, "toc_no")]], colWidths=[10 * mm], rowHeights=[10 * mm])
        badge.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), TEAL),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        rows.append([badge, p(title, "toc")])
    table = Table(rows, colWidths=[15 * mm, CONTENT_WIDTH - 15 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.45, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, -1), 2),
        ("RIGHTPADDING", (0, 0), (0, -1), 2),
        ("LEFTPADDING", (1, 0), (1, -1), 9),
        ("RIGHTPADDING", (1, 0), (1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def save_focus(
    source: Path,
    target: Path,
    box: tuple[int, int, int, int],
    label: str,
    callouts: tuple[tuple[int, str, tuple[int, int, int, int]], ...] = (),
) -> Path:
    image = PilImage.open(source).convert("RGB")
    width, height = image.size
    left, top, right, bottom = box
    crop = image.crop((max(0, left), max(0, top), min(width, right), min(height, bottom)))
    scale = 2
    crop = crop.resize((crop.width * scale, crop.height * scale), PilImage.Resampling.LANCZOS)
    margin = 28
    header = 74
    legend_rows = (len(callouts) + 1) // 2
    legend_height = 26 + (legend_rows * 54) if callouts else 22
    canvas_width = crop.width + (margin * 2)
    canvas_height = header + crop.height + legend_height + margin
    canvas = PilImage.new("RGB", (canvas_width, canvas_height), "#F3F5F7")
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 30)
    body_font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 23)
    badge_font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 24)
    draw.text((margin, 18), label, font=title_font, fill="#152126")
    title_width = draw.textbbox((0, 0), label, font=title_font)[2]
    draw.rounded_rectangle(
        (margin + title_width + 18, 28, canvas_width - margin, 35),
        radius=4,
        fill="#A3D900",
    )

    screenshot_xy = (margin, header)
    rounded_mask = PilImage.new("L", crop.size, 0)
    ImageDraw.Draw(rounded_mask).rounded_rectangle((0, 0, crop.width, crop.height), radius=18, fill=255)
    shadow = PilImage.new("RGBA", crop.size, (0, 0, 0, 0))
    shadow.putalpha(rounded_mask.filter(ImageFilter.GaussianBlur(12)))
    shadow_layer = PilImage.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_layer.paste((21, 33, 38, 52), (margin + 2, header + 8), shadow)
    canvas = PilImage.alpha_composite(canvas.convert("RGBA"), shadow_layer).convert("RGB")
    canvas.paste(crop, screenshot_xy, rounded_mask)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (margin, header, margin + crop.width - 1, header + crop.height - 1),
        radius=18,
        outline="#AEBFBA",
        width=3,
    )

    for number, _text, target_box in callouts:
        x1, y1, x2, y2 = target_box
        x1 = margin + max(0, x1 - left) * scale
        y1 = header + max(0, y1 - top) * scale
        x2 = margin + min(right - left, x2 - left) * scale
        y2 = header + min(bottom - top, y2 - top) * scale
        if x2 <= x1 or y2 <= y1:
            continue
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12, outline="#A3D900", width=7)
        badge_size = 42
        badge_box = (x1 + 10, y1 + 10, x1 + 10 + badge_size, y1 + 10 + badge_size)
        draw.ellipse(badge_box, fill="#143E70", outline="#FFFFFF", width=3)
        badge_text = str(number)
        bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        tx = badge_box[0] + (badge_size - (bbox[2] - bbox[0])) / 2
        ty = badge_box[1] + (badge_size - (bbox[3] - bbox[1])) / 2 - 1
        draw.text((tx, ty), badge_text, font=badge_font, fill="#FFFFFF")

    if callouts:
        legend_top = header + crop.height + 20
        column_width = (canvas_width - (margin * 2) - 18) // 2
        for index, (number, text, _target_box) in enumerate(callouts):
            column = index % 2
            row = index // 2
            x = margin + column * (column_width + 18)
            y = legend_top + row * 54
            draw.rounded_rectangle((x, y, x + 38, y + 38), radius=9, fill="#143E70")
            badge_text = str(number)
            bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
            draw.text(
                (x + (38 - (bbox[2] - bbox[0])) / 2, y + (38 - (bbox[3] - bbox[1])) / 2 - 1),
                badge_text,
                font=badge_font,
                fill="#FFFFFF",
            )
            draw.text((x + 50, y + 5), text, font=body_font, fill="#143E70")

    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, format="PNG", optimize=True, dpi=(180, 180))
    return target


def screen(path: Path, max_height_mm: float, caption: str) -> list:
    image = PilImage.open(path)
    ratio = image.height / image.width
    width = min(CONTENT_WIDTH, max_height_mm * mm / ratio)
    height = width * ratio
    return [Image(str(path), width=width, height=height), Spacer(1, 2.3 * mm), p(caption, "caption")]


def page_header(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(MARGIN_X, PAGE_HEIGHT - 11.5 * mm, 22 * mm, 2.2 * mm, fill=1, stroke=0)
    canvas.setFillColor(INK_SOFT)
    canvas.setFont("ManualMalgunBold", 8)
    canvas.drawImage(str(ASSETS / "chaeumlab_logo_header_2x.png"), MARGIN_X, PAGE_HEIGHT - 17.5 * mm, width=22 * mm, height=22 * mm * 309 / 960, mask="auto")
    canvas.setFont("ManualMalgun", 8)
    canvas.drawString(MARGIN_X + 27 * mm, PAGE_HEIGHT - 17.5 * mm, doc.manual_title)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, 12 * mm, PAGE_WIDTH - MARGIN_X, 12 * mm)
    canvas.setFont("ManualMalgun", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN_X, 7.4 * mm, "채움랩 고객용 사용 매뉴얼 | 2026.10.20.01")
    canvas.drawRightString(PAGE_WIDTH - MARGIN_X, 7.4 * mm, str(doc.page))
    canvas.restoreState()


def cover_page(canvas, _doc) -> None:
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(0, PAGE_HEIGHT - 8 * mm, PAGE_WIDTH, 8 * mm, fill=1, stroke=0)
    canvas.setFillColor(MINT)
    canvas.rect(MARGIN_X, PAGE_HEIGHT - 13 * mm, 52 * mm, 2.2 * mm, fill=1, stroke=0)
    canvas.restoreState()


def cover(title: str, subtitle: str, executable: str, purpose: str) -> list:
    logo = ASSETS / "chaeumlab_logo_header_2x.png"
    story: list = [Spacer(1, 25 * mm)]
    if logo.exists():
        story += [Image(str(logo), width=58 * mm, height=58 * mm * 309 / 960), Spacer(1, 12 * mm)]
    icon_names = {"라벨디자이너.exe": "chaeumlab_designer_icon.png", "라벨출력관리.exe": "chaeumlab_manager_icon.png", "프린터설정.exe": "chaeumlab_settings_icon.png"}
    icon = ASSETS / icon_names[executable]
    if icon.exists():
        story += [Image(str(icon), width=16 * mm, height=16 * mm), Spacer(1, 5 * mm)]
    story += [p("채움랩 고객용 사용 매뉴얼", "eyebrow"), p(title, "cover"), Spacer(1, 5 * mm), p(subtitle, "cover_sub"), Spacer(1, 14 * mm), thin_rule(), Spacer(1, 10 * mm)]
    intro = Table([
        [p("대상 프로그램", "note_title"), p(executable, "body")],
        [p("이 문서에서 하는 일", "note_title"), p(purpose, "body")],
        [p("프로그램에서 열기", "note_title"), p("도움말 > 고객용 매뉴얼에서 현재 프로그램의 사용 설명서를 엽니다.", "body")],
        [p("출력 전 원칙", "note_title"), p("설정을 저장한 뒤에는 반드시 수량 1로 시험 출력하고, 실제 배출 위치와 바코드 판독까지 확인합니다.", "body")],
    ], colWidths=[40 * mm, CONTENT_WIDTH - 40 * mm])
    intro.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("BOX", (0, 0), (-1, -1), 0.45, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), MINT_PALE),
    ]))
    story += [intro, NextPageTemplate("body"), PageBreak()]
    return story


def designer_manual(images: dict[str, Path]) -> list:
    story = cover("라벨 디자이너", "라벨 제작, 상품 연결, 검토와 안전한 출력", "라벨디자이너.exe", "예제로 익힌 뒤 자신의 도안을 저장하고 첫 장을 확인합니다.")
    story += heading("01", "첫 라벨은 예제로 익힙니다", "기본 라벨은 빈 상태이며 예제는 별도 파일입니다.", "designer-start")
    story += [
        toc([
            ("01", "처음 시작"), ("02", "화면 구성"), ("03", "라벨 크기와 저장"),
            ("04", "개체 추가"), ("05", "개체 방향"), ("06", "상품 엑셀과 선택"),
            ("07", "정렬과 편집 복구"), ("08", "도안 인식과 출력"),
            ("09", "PC 이동과 BarTender 전환"),
        ]),
        Spacer(1, 4 * mm),
        step(1, "프린터 설정을 확인합니다", "프린터설정.exe에서 브랜드, 연결 방식, 용지 크기와 DPI를 저장합니다."),
        Spacer(1, 2 * mm),
        step(2, "예제로 시작합니다", "처음 화면에서 예제로 시작을 누르면 예제 도안과 상품 엑셀이 연결됩니다."),
        Spacer(1, 2 * mm),
        step(3, "내 도안을 저장합니다", "새 라벨로 시작해 크기와 개체를 배치한 뒤 저장 또는 Ctrl+S를 누릅니다.", "기본 템플릿은 개체가 없는 빈 라벨입니다."),
        Spacer(1, 4 * mm),
        note("작업 전 확인", "라벨 가로·세로와 DPI가 실제 장비 설정과 같아야 합니다. 화면 맞춤은 실물 크기 표시가 아닙니다.", CAUTION), PageBreak(),

        *heading("02", "디자인과 출력 작업을 구분합니다", "저장·상품 연결·개체 도구·상품 DB의 위치를 먼저 익힙니다.", "designer-screen"),
        *screen(images["overview"], 111, "① 파일·상품·출력  ② 개체 도구  ③ 편집 캔버스  ④ 상품 DB"),
        Spacer(1, 3 * mm),
        note("반복 출력 담당자", "보기 메뉴의 반복 출력 화면 또는 상단 반복 출력을 누릅니다. 변경한 도안을 먼저 저장하고 출력 관리의 선택 도안 이름과 현재 도안 미리보기를 확인합니다. 현재 도안·상품 엑셀·시트를 전달합니다."), PageBreak(),

        *heading("03", "공통 용지 규격을 확인하고 저장합니다", "파일명 옆의 별표는 아직 저장하지 않은 변경을 뜻합니다.", "designer-size-save"),
        *screen(images["toolbar"], 72, "① 파일과 변경 이력  ② 라벨 크기  ③ 정렬·설정·출력"),
        Spacer(1, 4 * mm),
        step(1, "공통 용지 설정을 저장합니다", "상단 용지 설정으로 프린터설정.exe를 열어 가로·세로(mm)는 50.5×30.25처럼 소수로 입력합니다. 용지 구역에서 방향과 좌우·상하 보정을 함께 저장합니다. 열린 프로그램에도 공통 규격이 반영됩니다.", "다른 규격 도안을 열면 규격 선택 창에서 기존 도안 유지 또는 공통 규격 적용을 선택합니다. 개체가 영역 밖으로 나가면 변경은 취소됩니다."),
        Spacer(1, 3 * mm),
        step(2, "저장과 최근 라벨을 사용합니다", "저장 또는 Ctrl+S로 .cllabel을 보관합니다. 최근 라벨은 파일 메뉴에서 다시 열 수 있습니다."),
        Spacer(1, 3 * mm),
        step(3, "실수를 되돌립니다", "Ctrl+Z로 실행취소, Ctrl+Y로 다시실행합니다. 비정상 종료 후 복구 제안은 저장 원본을 덮어쓰지 않는 작업 사본입니다."), PageBreak(),

        *heading("04", "필요한 개체를 라벨에 넣습니다", "8종 개체 도구는 아이콘과 이름을 함께 표시합니다. 하나를 넣고 크기와 위치를 먼저 확인합니다.", "designer-objects"),
        *screen(images["canvas"], 114, "① 개체 도구  ② mm 눈금이 보이는 편집 캔버스"),
        Spacer(1, 4 * mm),
        step(1, "텍스트 또는 여러 줄 텍스트를 넣습니다", "품명, 주소, 설명처럼 읽혀야 하는 정보를 넣고 개체를 더블클릭한 편집 창에서 글꼴, 정렬, 위치와 크기를 바꿉니다."),
        Spacer(1, 3 * mm),
        step(2, "1D 또는 2D 코드를 넣습니다", "바코드 값은 텍스트가 아닌 문자열로 입력합니다. Code128, EAN, QR, DataMatrix, PDF417 등 필요한 코드 종류를 선택합니다."),
        Spacer(1, 3 * mm),
        step(3, "그림과 표를 넣습니다", "JPG/PNG 그림, 박스, 선, 표를 넣어 양식을 구성합니다. 필요한 개체만 배치하고 인쇄파일에서 경계를 확인합니다."), PageBreak(),

        *heading("05", "개체 방향을 설정합니다", "텍스트와 바코드만이 아니라 그림, 박스, 선, 표에도 같은 방식으로 적용됩니다.", "designer-rotation"),
        note("방향 설정 위치", "개체를 더블클릭해 편집 창을 열고 방향을 고릅니다. 개체를 선택하지 않으면 방향 값을 바꿀 수 없습니다.", MINT_PALE),
        Spacer(1, 8 * mm),
        step(1, "0도 (기본)", "일반적인 가로 읽기 방향입니다. 새 개체는 이 방향으로 시작합니다."),
        Spacer(1, 4 * mm),
        step(2, "90도 시계 방향 또는 270도 시계 방향", "세로로 읽는 품목명이나 좁은 세로 라벨에 사용합니다. 적용 후 폭과 높이가 바뀌므로 라벨 경계를 다시 확인합니다."),
        Spacer(1, 4 * mm),
        step(3, "180도", "라벨 전체가 뒤집혀 붙는 레이아웃에서 사용합니다. 미리보기와 시험 출력에서 읽는 방향을 확인합니다."),
        Spacer(1, 7 * mm),
        note("저장과 출력", "선택한 방향은 .cllabel 파일에 저장되며, 미리보기와 인쇄파일, 실제 출력에도 같은 각도로 반영됩니다.", CAUTION), PageBreak(),

        *heading("06", "상품 엑셀을 연결하고 행을 고릅니다", "상품 열의 실제 값과 선택 대상을 확인합니다.", "designer-db"),
        *screen(images["db"], 82, "① 상품 엑셀 연결 상태  ② 선택 개체의 상품 열 연결"),
        Spacer(1, 4 * mm),
        step(1, "상품 엑셀 연결을 누릅니다", "오른쪽 상품 DB 카드에서 상품 엑셀 연결을 눌러 .xlsx 또는 .xlsm을 선택합니다. 여러 시트가 있으면 사용할 시트를 고릅니다. 연결 중 취소하면 기존 연결을 유지합니다. 연결 파일·시트·읽은 시각을 확인하세요."),
        Spacer(1, 3 * mm),
        step(2, "개체에 상품 열을 지정합니다", "텍스트·1D 바코드·QR 개체의 편집 화면에서 엑셀에 실제로 있는 열을 고릅니다. 필요한 값은 필수 항목으로 지정합니다."),
        Spacer(1, 3 * mm),
        step(3, "상품 선택에서 행을 고릅니다", "상품 선택을 열어 출력할 행만 체크합니다. 바코드 앞자리 0은 원본 셀 값과 미리보기를 대조합니다."),
        Spacer(1, 3 * mm),
        step(4, "선택 항목 인쇄파일을 만듭니다", "전체 데이터 검증에서 행·개체·원인을 한 번에 확인하고 수정합니다. 엑셀이 바뀌면 엑셀 새로고침 후 열 연결을 확인합니다. 대상과 매수를 확인한 뒤 파일을 먼저 생성합니다."), PageBreak(),

        *heading("07", "개체를 가운데로 맞추고 되돌립니다", "선택과 보기 크기는 저장된 라벨 크기를 바꾸지 않습니다.", "designer-precision"),
        step(1, "선택하고 복사·붙여넣습니다", "Ctrl+클릭으로 여러 개체를 선택합니다. Ctrl+C는 개체 복사, Ctrl+V는 붙여넣기, Ctrl+D는 복제입니다. 그림과 DB 연결도 함께 복사되며 Ctrl+Z로 되돌립니다. 글자 입력칸에서는 입력한 글자의 복사·붙여넣기를 우선합니다. 개체를 더블클릭하면 별도 편집 창에서 값과 크기를 바꿀 수 있습니다. 오른쪽은 상품 DB 연결과 열 선택만 표시합니다."),
        Spacer(1, 4 * mm),
        step(2, "위치와 간격을 맞춥니다", "상단의 좌우 가운데 정렬은 가로 중심으로, 상하 가운데 정렬은 세로 중심으로 이동합니다. 여러 개체는 상대 위치를 유지합니다. 방향키는 1mm, Shift+방향키는 0.1mm 이동합니다."),
        Spacer(1, 4 * mm),
        step(3, "보기 크기와 이력을 확인합니다", "화면 맞춤 또는 +/−로 캔버스를 확대·축소합니다. Ctrl+Z와 Ctrl+Y로 변경을 되돌리고 다시 적용합니다."),
        Spacer(1, 7 * mm),
        note("잠긴 개체", "잠긴 로고나 바코드는 이동·삭제·속성 수정을 막습니다. 수정이 필요할 때만 잠금을 해제하세요.", CAUTION), PageBreak(),

        *heading("08", "도안 인식 값을 검토하고 출력합니다", "자동 인식 결과는 후보이며 사람의 확인이 필요합니다.", "designer-print"),
        step(1, "도안을 불러옵니다", "왼쪽 도안 가져오기 카드의 도안 불러오기에서 실제 PSD/JPG/PNG를 선택하고 도안 적용을 누릅니다. 누운 글자는 인식용 복사본에서 방향을 보정하며 원래 도안 위치·방향을 유지합니다. .btw 파일의 이름만 PNG로 바꾸면 실제 이미지가 되지 않습니다."),
        Spacer(1, 3 * mm),
        step(2, "원본과 인식 값을 비교합니다", "인식 값 전체 확인으로 검토창을 열고 회전 보정 후에도 원본과 모든 값을 대조한 뒤 전체 값 확인을 누릅니다. 이미 잘못 인식한 값은 원본 도안을 다시 적용해 검토합니다. 선택한 값의 수정도 함께 반영됩니다. 빈 값과 임시 바코드는 먼저 수정해야 하며 실패하면 전체 확인을 적용하지 않습니다."),
        Spacer(1, 3 * mm),
        step(3, "출력 전 경고를 처리합니다", "경계 밖 개체와 빈 필수 값을 수정합니다. 글자 축소·작은 QR 경고는 첫 장 출력에서 읽힘을 확인합니다."),
        Spacer(1, 3 * mm),
        step(4, "인쇄파일과 실물을 확인합니다", "인쇄파일 생성은 프린터에 보내지 않습니다. 실제 전송 후에는 라벨 배출·위치·1D와 2D 스캔을 확인합니다."),
        Spacer(1, 5 * mm),
        note("전송이 중단된 경우", "프린터 전송 완료 안내도 실물 확인이 필요합니다. 결과가 미확인인 항목은 실물을 먼저 보고, 다시 인쇄할 때 전송됨 또는 재전송을 직접 선택합니다. 이미 나온 라벨을 다시 보내면 중복될 수 있습니다.", CAUTION), PageBreak(),

        *heading("09", "다른 PC로 작업을 옮깁니다", "도안 파일, 이미지와 원본 상품 엑셀의 역할을 구분합니다.", "designer-transfer"),
        step(1, "이동용 프로젝트를 내보냅니다", "파일 메뉴에서 이동 프로젝트 내보내기를 선택해 .clproject를 보관합니다. 현재 도안과 필요한 이미지를 함께 옮기며 상품 엑셀은 별도로 옮깁니다. 기존 .gblabel·.gbproject도 열 수 있으며, 구형 도안 저장은 원래 파일을 유지합니다. 새 형식으로 전환하려면 다른 이름으로 저장을 사용하세요."),
        Spacer(1, 4 * mm),
        step(2, "새 PC에서 가져옵니다", "이동 프로젝트 가져오기 후 상품 엑셀을 다시 연결합니다. 누락된 파일·글꼴·라벨 크기와 프린터 설정을 확인합니다."),
        Spacer(1, 4 * mm),
        step(3, "기존 BarTender 도안을 다시 만듭니다", ".btw는 직접 열 수 없습니다. 확장자를 .png로 바꾸는 것은 변환이 아닙니다. 원본 프로그램에서 실제 이미지로 내보내거나 인쇄 미리보기를 저장한 뒤 필드와 바코드를 다시 연결합니다."),
        Spacer(1, 7 * mm),
        note("전환 후 첫 장", "원본과 새 도안의 글자·바코드 값, 용지 크기와 방향을 대조하고 실제 프린터에서 1장 출력해 스캔합니다. 수식·변수·프린터 설정은 자동 변환되지 않습니다.", CAUTION),
    ]
    return story


def manager_manual(images: dict[str, Path]) -> list:
    story = cover("라벨 출력 관리", "상품을 찾아 필요한 행과 매수만 출력하는 방법", "라벨출력관리.exe", "시작하기.cmd로 열고 상품을 선택한 뒤 대상과 매수를 확인합니다.")
    story += heading("01", "출력 전 작업 순서를 확인합니다", "DB 값과 실제 출력 대상을 분리해서 확인하는 것이 핵심입니다.", "manager-start")
    story += [
        toc([("01", "출력 전 작업 순서"), ("02", "화면 구성"), ("03", "DB 연결과 인쇄 데이터"), ("04", "검색, 스캔, 중복 선택"), ("05", "선택 인쇄"), ("06", "점검과 문제 해결")]),
        Spacer(1, 7 * mm),
        step(1, "출력 화면을 엽니다", "시작하기.cmd를 더블클릭합니다. 라벨 크기, DPI, 연결 방식도 확인합니다."), Spacer(1, 3 * mm),
        step(2, "DB를 연결하고 검색합니다", "바코드뿐 아니라 품명, 품목 코드, 가격 등 DB의 모든 셀에서 찾을 수 있습니다."), Spacer(1, 3 * mm),
        step(3, "인쇄할 행과 수량을 확인합니다", "체크된 행이 맞는지 보고, 첫 출력은 수량 1로 시작합니다."), Spacer(1, 5 * mm),
        note("출력 성공 안내", "프린터 전송 완료는 실제 인쇄 완료가 아닙니다. 라벨 배출과 바코드 판독은 장비에서 별도로 확인해야 합니다.", CAUTION), PageBreak(),

        *heading("02", "화면을 네 영역으로 나눠 봅니다", "검색, 데이터, 메뉴, 출력 작업을 구분하면 실수가 줄어듭니다.", "manager-screen"),
        *screen(images["overview"], 112, "① DB 상품조회  ② 메뉴와 인쇄  ③ 인쇄 데이터  ④ 출력 작업"),
        Spacer(1, 4 * mm),
        note("검색할 때", "스캐너를 사용할 때는 검색 입력칸을 먼저 클릭합니다. 스캐너가 Enter를 보내는 설정이면 바로 조회됩니다."), PageBreak(),

        *heading("03", "DB를 연결하고 인쇄 데이터를 확인합니다", "원본 DB와 인쇄 데이터 탭을 번갈아 보며 값이 맞는지 확인합니다.", "manager-db"),
        *screen(images["data"], 106, "① 인쇄 데이터/원본 DB 탭  ② 행 선택과 데이터 표"),
        Spacer(1, 4 * mm),
        step(1, "상품 엑셀 연결을 선택합니다", "상품 엑셀 파일을 선택합니다. 첫 행은 반드시 열 제목이어야 합니다."), Spacer(1, 3 * mm),
        step(2, "불러온 열과 행 수를 확인합니다", "인쇄 데이터와 원본 DB 탭을 모두 열어 값이 누락되지 않았는지 봅니다."), Spacer(1, 3 * mm),
        step(3, "행을 편집하고 저장합니다", "셀을 더블클릭하거나 Enter로 수정한 뒤 파일 메뉴에서 저장합니다."), Spacer(1, 5 * mm),
        note("원본 DB를 바꾸기 전", "삭제나 대량 수정 전에 원본 파일을 백업합니다. 저장 후에는 인쇄 데이터의 현재 값도 다시 확인합니다.", CAUTION), PageBreak(),

        *heading("04", "검색 결과와 중복 행을 선택합니다", "중복 값은 자동으로 하나를 고르지 않습니다. 원하는 행을 직접 선택합니다.", "manager-search"),
        step(1, "찾을 값을 입력하거나 스캔합니다", "상단 검색 입력칸에 바코드, 품명, 품목 코드, 가격처럼 DB에 있는 값을 입력한 뒤 조회합니다."), Spacer(1, 3 * mm),
        step(2, "중복 선택 창에서 필요한 행만 고릅니다", "기본 상태는 아무 행도 선택되지 않습니다. 원하는 행만 체크하거나 전체 선택을 사용합니다."), Spacer(1, 3 * mm),
        step(3, "확인을 눌러 인쇄 데이터에 반영합니다", "확인을 누르면 이번 선택이 인쇄 데이터에 적용됩니다. 취소하면 기존 선택을 유지합니다."), Spacer(1, 5 * mm),
        note("중복 선택 주의", "확인하면 기존 체크가 이번 선택으로 교체됩니다. 전체 출력이 필요하지 않다면 대상 행과 수량을 다시 확인합니다.", CAUTION), PageBreak(),

        *heading("05", "대상과 매수를 확인하고 인쇄합니다", "출력 작업 영역에서 대상과 수량을 마지막으로 확인합니다.", "manager-print"),
        *screen(images["print"], 65, "① 인쇄 범위와 실행  ② 출력 대상 선택  ③ 점검과 설정"),
        Spacer(1, 4 * mm),
        step(1, "출력 도안과 대상 행을 확인합니다", "출력 도안 선택으로 저장한 .cllabel을 연결하고 현재 도안 미리보기를 확인합니다. 자동 기본 배치 사용은 프린터 설정의 기본 배치로 되돌립니다. 출력할 행만 체크합니다."), Spacer(1, 3 * mm),
        step(2, "전체 데이터 검증과 실행 전 점검을 합니다", "행·개체·오류를 확인하고 상품 엑셀과 도안을 수정합니다. 원본 참조/가져온 복사본·시트·갱신 시각과 프린터 설정을 확인합니다."), Spacer(1, 3 * mm),
        step(3, "인쇄 매수를 선택하고 시작합니다", "인쇄를 누르면 인쇄 매수 선택 창이 열립니다. 양의 정수를 상한 없이 입력하거나 1·3·5·10장 빠른 선택을 누른 뒤 인쇄 시작을 선택합니다. 전송 중 중단은 아직 보내지 않은 작업만 멈춥니다. 이미 프린터가 받은 작업의 중단은 보장하지 않습니다."), Spacer(1, 5 * mm),
        note("선택 항목에 같은 매수 적용", "체크한 행이 있으면 선택한 각 항목에 같은 인쇄 매수가 적용됩니다. 체크가 없으면 전체 항목이 대상입니다. 취소하면 명령을 전송하지 않습니다."), Spacer(1, 3 * mm),
        note("체크가 0개일 때", "선택 항목이 없으면 전체 항목에 같은 매수가 적용됩니다. 인쇄 매수 선택 창에서 전체 대상 건수와 총 매수를 확인하세요. 선택 매수는 임시 큐에만 반영되며 원본 DB와 기본 인쇄 데이터의 저장값은 바뀌지 않습니다.", CAUTION), PageBreak(),

        *heading("06", "점검 결과와 로그로 문제를 찾습니다", "출력 문제가 생기면 같은 작업을 반복하기 전에 점검 결과를 먼저 봅니다.", "manager-help"),
        step(1, "실행 전 점검 결과를 엽니다", "out/customer_preflight_report.txt에서 DB, 설정과 필수 파일 오류를 확인합니다."), Spacer(1, 3 * mm),
        step(2, "지원 패키지를 만듭니다", "도움말 메뉴의 지원 패키지 생성으로 out/customer_support_package.zip을 만듭니다. 고객 데이터 백업·복원은 파일 메뉴에 있고 라벨 디자인은 상단의 별도 버튼입니다."), Spacer(1, 3 * mm),
        step(3, "인쇄 로그를 확인합니다", "print_log.xlsx와 last_run.log에서 마지막으로 전송한 값과 결과를 확인합니다."), Spacer(1, 5 * mm),
        note("문의할 때 준비할 내용", "프린터 모델명, 연결 방식, 오류 화면, customer_preflight_report.txt, customer_support_package.zip과 문제 발생 시간을 함께 전달합니다."),
    ]
    return story


def settings_manual(images: dict[str, Path]) -> list:
    story = cover("프린터 설정", "브랜드, 연결 방식, 용지, DPI와 인쇄후작업을 장비에 맞게 저장하는 방법", "프린터설정.exe", "프린터 환경을 한 번 저장하고 라벨 디자이너와 라벨 출력 관리에서 공통으로 사용합니다.")
    story += heading("01", "설정은 이 순서로 저장합니다", "브랜드와 연결을 먼저 잡고, 용지와 DPI를 맞춘 뒤 1장으로 확인합니다.", "settings-start")
    story += [
        toc([("01", "설정 저장 순서"), ("02", "화면 구성"), ("03", "브랜드와 인쇄후작업"), ("04", "연결 방식"), ("05", "용지, DPI와 바코드"), ("06", "점검과 실제 출력")]),
        Spacer(1, 7 * mm),
        step(1, "현재 설정을 다시 불러옵니다", "기존 config.ini에 저장된 값을 확인합니다."), Spacer(1, 3 * mm),
        step(2, "브랜드, 연결, 용지와 DPI를 저장합니다", "실제 장비 사양과 다른 값이 없는지 설정 점검으로 확인합니다."), Spacer(1, 3 * mm),
        step(3, "수량 1로 실제 출력합니다", "크기, 방향, 농도, 바코드 판독과 인쇄후작업까지 확인합니다."), Spacer(1, 5 * mm),
        note("공용 설정", "저장한 config.ini는 라벨 디자이너와 라벨 출력 관리가 함께 사용합니다. 장비나 라벨 규격이 바뀌면 다시 저장합니다. 열린 디자이너와 출력 관리에 공통 규격이 반영됩니다. 다른 규격의 도안을 열면 기존 도안 규격을 사용할지 공통 규격에 맞출지 선택합니다. 영역 밖으로 개체가 나가는 규격 변경은 취소되며 기존 도안을 유지합니다.", MINT_PALE), PageBreak(),

        *heading("02", "설정 화면을 먼저 확인합니다", "한 화면에서 브랜드, 연결, 용지와 바코드 기본값을 모두 점검합니다.", "settings-screen"),
        *screen(images["overview"], 112, "① 불러오기·점검·저장  ② 설정 흐름과 검증  ③ 장비와 연결  ④ 용지와 바코드"),
        Spacer(1, 4 * mm),
        note("입력 전 원칙", "알 수 없는 값은 추측해서 넣지 않습니다. 프린터의 실제 모델 설명서와 설치된 Windows 프린터 이름을 기준으로 확인합니다."), PageBreak(),

        *heading("03", "브랜드와 인쇄후작업을 정합니다", "프린터에 없는 옵션을 설정하면 동작하지 않습니다.", "settings-printer"),
        *screen(images["printer"], 101, "① 제조사와 출력 방식  ② 연결 방식"),
        Spacer(1, 4 * mm),
        step(1, "실제 브랜드를 선택합니다", "BIXOLON/빅솔론, TSC, Zebra/제브라, SEWOO/세우테크(ZPL) 중 장비와 같은 브랜드를 선택합니다."), Spacer(1, 3 * mm),
        step(2, "인쇄 방식을 고릅니다", "감열지는 감열/리본 없음을, 리본을 쓰는 라벨은 열전사/리본 사용을 선택합니다."), Spacer(1, 3 * mm),
        step(3, "인쇄후작업과 방향을 정합니다", "뜯어내기, 커터, 필러는 장비에 실제로 장착된 기능만 고릅니다. 용지 구역에서 세로·가로·세로 180도·가로 180도를 고릅니다. 가로는 전체 내용을 반시계 90도 회전합니다."), PageBreak(),

        *heading("04", "연결 방식을 설정합니다", "LAN과 USB/Windows 프린터는 확인 방법이 다릅니다.", "settings-connect"),
        step(1, "LAN/네트워크를 쓸 때", "프린터 IP와 포트를 입력합니다. 일반적인 포트는 9100이지만 프린터 설정값을 우선합니다."), Spacer(1, 3 * mm),
        step(2, "USB/Windows 프린터를 쓸 때", "목록 새로고침 후 Windows에 설치된 프린터 이름을 정확히 선택합니다."), Spacer(1, 3 * mm),
        step(3, "연결 확인을 실행합니다", "LAN은 IP/포트 TCP 접속을, USB는 Windows 프린터 이름의 존재 여부를 확인합니다."), Spacer(1, 5 * mm),
        note("연결 확인의 한계", "연결 확인 성공은 장비가 보인다는 1차 결과입니다. 명령 수신과 출력 품질은 반드시 1장 출력으로 확인합니다.", CAUTION), PageBreak(),

        *heading("05", "용지 크기와 DPI를 실제 규격에 맞춥니다", "라벨 크기와 DPI가 다르면 출력 위치도 달라집니다.", "settings-media"),
        *screen(images["media"], 99, "① 용지 가로·세로·간격·DPI  ② 기본 바코드 배치"),
        Spacer(1, 4 * mm),
        step(1, "가로와 세로를 mm로 입력합니다", "실제 라벨 한 장의 폭·길이를 50.5×30.25처럼 소수로 입력합니다. 방향과 좌우·상하 보정도 용지 구역에서 함께 저장합니다. 열린 라벨 디자이너의 공통 규격 표시와 캔버스에도 같은 크기가 반영됩니다."), Spacer(1, 3 * mm),
        step(2, "용지 유형과 간격을 정합니다", "갭·블랙마크 용지는 간격을 0보다 크게, 연속 용지는 0을 권장합니다."), Spacer(1, 3 * mm),
        step(3, "DPI와 바코드 배치를 확인합니다", "장비 사양에 맞춰 203/300/600을 고릅니다. 자동 가운데 배치를 끄면 X/Y 위치를 직접 확인합니다."), PageBreak(),

        *heading("06", "점검하고 1장으로 끝까지 확인합니다", "저장 성공만으로 프린터 설정이 끝난 것은 아닙니다.", "settings-help"),
        step(1, "설정 점검을 누릅니다", "브랜드, 연결 방식, 용지 유형, 간격, DPI와 바코드 기본값의 오류를 확인합니다."), Spacer(1, 3 * mm),
        step(2, "설정 저장을 누릅니다", "오류가 없을 때 저장합니다. 현재 사용하는 config.ini에 반영되며 폴더 쓰기가 제한된 PC는 안내된 사용자 데이터 폴더에 저장됩니다."), Spacer(1, 3 * mm),
        step(3, "라벨출력관리에서 1장을 출력합니다", "소수 규격, 네 방향, 좌우·상하 위치, 배출 정지 위치와 다음 장 시작 위치, 바코드 판독을 확인합니다."), Spacer(1, 5 * mm),
        note("완료 기준", "연결 확인과 설정 저장 뒤 실제 라벨 1장이 정상 위치에 배출되고, 인쇄후작업과 바코드 판독까지 맞아야 설정이 완료됩니다.", CAUTION),
    ]
    return story


def build_pdf(path: Path, story: list, manual_title: str) -> None:
    doc = ManualDocTemplate(
        str(path), pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=path.stem, author="채움랩",
    )
    doc.manual_title = manual_title
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="content", showBoundary=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover_page),
        PageTemplate(id="body", frames=[frame], onPage=page_header),
    ])
    doc.build(story)


def main() -> None:
    capture_errors = capture_contract_errors(ROOT)
    if capture_errors:
        raise RuntimeError("최신 실제 화면 캡처 확인 실패: " + "; ".join(capture_errors))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    generated = OUTPUT / "_generated"
    generated.mkdir(parents=True, exist_ok=True)

    designer_source = SCREENSHOTS / "label-designer-final.png"
    designer_data_source = SCREENSHOTS / "label-designer-data.png"
    manager_source = SCREENSHOTS / "label-manager-final.png"
    settings_source = SCREENSHOTS / "printer-settings.png"
    missing = [str(path) for path in (designer_source, designer_data_source, manager_source, settings_source) if not path.exists()]
    if missing:
        raise FileNotFoundError("최신 프로그램 화면 캡처가 없습니다: " + ", ".join(missing))

    designer_images = {
        "overview": save_focus(
            designer_source,
            generated / "designer-overview-focus.png",
            (12, 8, 1468, 890),
            "라벨 디자이너 전체 화면",
            (
                (1, "파일·상품·출력", (12, 103, 1468, 274)),
                (2, "아이콘과 이름이 표시된 개체 도구", (12, 285, 249, 839)),
                (3, "편집 캔버스", (261, 285, 1139, 839)),
                (4, "상품 DB", (1151, 285, 1468, 839)),
            ),
        ),
        "toolbar": save_focus(
            designer_source,
            generated / "designer-toolbar-focus.png",
            (12, 95, 1468, 274),
            "파일 · 라벨 크기 · 출력",
            (
                (1, "파일과 변경 이력", (12, 103, 430, 180)),
                (2, "라벨 크기", (12, 184, 640, 217)),
                (3, "정렬·설정·출력", (440, 103, 1115, 180)),
            ),
        ),
        "canvas": save_focus(
            designer_source,
            generated / "designer-canvas-focus.png",
            (12, 285, 1140, 839),
            "개체 도구와 편집 캔버스",
            (
                (1, "아이콘과 이름이 표시된 개체 도구", (12, 285, 249, 839)),
                (2, "mm 편집 캔버스", (261, 285, 1139, 839)),
            ),
        ),
        "db": save_focus(
            designer_data_source,
            generated / "designer-db-focus.png",
            (1151, 285, 1468, 839),
            "상품 DB 영역",
            (
                (1, "상품 엑셀 연결 상태", (1162, 296, 1442, 570)),
                (2, "선택 개체의 상품 열", (1162, 580, 1442, 751)),
            ),
        ),
    }
    manager_images = {
        "overview": save_focus(
            manager_source,
            generated / "manager-overview-focus.png",
            (12, 6, 1468, 890),
            "라벨 출력 관리 전체 화면",
            (
                (1, "DB 상품조회", (12, 161, 1468, 209)),
                (2, "메뉴와 인쇄", (12, 60, 1468, 153)),
                (3, "인쇄 데이터", (12, 217, 1163, 847)),
                (4, "출력 작업", (1173, 217, 1468, 847)),
            ),
        ),
        "data": save_focus(
            manager_source,
            generated / "manager-data-focus.png",
            (12, 217, 1163, 847),
            "인쇄 데이터와 원본 DB",
            (
                (1, "인쇄 데이터 / 원본 DB", (12, 217, 1163, 264)),
                (2, "행 선택과 데이터", (24, 264, 1136, 820)),
            ),
        ),
        "print": save_focus(
            manager_source,
            generated / "manager-print-focus.png",
            (12, 101, 1468, 847),
            "선택 인쇄와 출력 작업",
            (
                (1, "인쇄 범위와 실행", (12, 60, 1468, 153)),
                (2, "출력 대상 선택", (12, 217, 1163, 847)),
                (3, "점검과 설정", (1173, 217, 1468, 847)),
            ),
        ),
    }
    settings_images = {
        "overview": save_focus(
            settings_source,
            generated / "settings-overview-focus.png",
            (10, 8, 1470, 654),
            "프린터 설정 전체 화면",
            (
                (1, "불러오기·점검·저장", (16, 101, 504, 136)),
                (2, "설정 흐름과 검증", (13, 153, 1467, 207)),
                (3, "장비와 연결", (12, 216, 736, 646)),
                (4, "용지와 바코드", (744, 216, 1468, 598)),
            ),
        ),
        "printer": save_focus(
            settings_source,
            generated / "settings-printer-focus.png",
            (12, 216, 736, 646),
            "장비와 연결",
            (
                (1, "제조사와 출력", (12, 216, 736, 434)),
                (2, "연결 방식", (12, 442, 736, 646)),
            ),
        ),
        "media": save_focus(
            settings_source,
            generated / "settings-media-focus.png",
            (744, 216, 1468, 598),
            "용지 크기와 바코드 설정",
            (
                (1, "용지 규격", (744, 216, 1468, 381)),
                (2, "바코드 기본값", (744, 390, 1468, 598)),
            ),
        ),
    }

    manuals = {
        "채움랩_라벨디자이너_고객용_매뉴얼.pdf": (designer_manual(designer_images), "라벨 디자이너"),
        "채움랩_라벨출력관리_고객용_매뉴얼.pdf": (manager_manual(manager_images), "라벨 출력 관리"),
        "채움랩_프린터설정_고객용_매뉴얼.pdf": (settings_manual(settings_images), "프린터 설정"),
    }
    manuals["채움랩_라벨출력관리_고객용_매뉴얼.pdf"][0].extend([
        PageBreak(), *heading("추가", "작은 라벨에서도 자동 배치를 확인합니다", "40×20mm의 네 항목을 누락 없이 배치합니다.", "compact-auto-layout"),
        Image(str(SCREENSHOTS / 'manager-compact-preview.png'), width=174*mm, height=84.6*mm), Spacer(1, 4*mm),
        step(1, "자동 기본 배치 사용을 선택합니다", "출력 작업에서 자동 기본 배치 사용을 고릅니다. 프린터 설정의 용지·방향·위치 보정을 적용합니다. 저장한 사용자 도안의 배치는 자동으로 바뀌지 않습니다."),
        Spacer(1, 3*mm),
        step(2, "현재 도안 미리보기를 누릅니다", "첫 출력 대상의 전체 항목과 바코드를 실제 출력용 이미지로 확인합니다. 짧은 항목은 두 열로 배치하며, 실제 글자 폭·높이를 측정해 8pt부터 최소 5pt까지 맞춥니다. 미리보기는 DB·기본 인쇄 데이터·설정을 바꾸거나 프린터로 전송하지 않습니다. 닫기 또는 Esc로 돌아갑니다."),
        Spacer(1, 3*mm),
        step(3, "긴 값과 첫 장을 확인합니다", "값을 자르거나 항목을 버리지 않습니다. 2D의 설정 모듈과 필수 여백을 유지하며, 1D 자동 너비는 정수 도트로 맞춥니다. 최소 5pt에서도 내용이 들어가지 않으면 용지 크기나 저장 도안을 조정합니다. 실제 글자 크기와 스캔 결과는 첫 장으로 확인하세요."),
    ])
    manuals["채움랩_프린터설정_고객용_매뉴얼.pdf"][0].extend([
        PageBreak(), *heading("추가", "용지 배출과 절취 위치를 조정합니다", "용지 종류 아래에서 센서·절취선 거리를 설정합니다.", "manufacturer-offsets"),
        Image(str(SCREENSHOTS / "printer-offsets-bixolon.png"), width=150*mm, height=91.2*mm), Spacer(1, 3*mm),
        step(1, "내용 위치와 배출 위치를 구분합니다", "좌우·상하 보정은 인쇄 내용을 이동합니다. 고급 보정은 센서 기준이나 인쇄 후 정지 위치를 바꿉니다. 방향·위치 미리보기에는 실물 센서·배출 이동이 나타나지 않습니다."),
        step(2, "용지 종류별 실제 배출 보정을 입력합니다", "빅솔론 SL p4는 마크-절취선 거리(매뉴얼 예: 200도트)입니다. 제조사 최대값은 미기재라 앱은 라벨 길이와 SL p1 2432도트 중 작은 값을 상한으로 둡니다. TA ±100도트와 별개입니다. TSC GAP/BLINE 추가 이송은 0~라벨 길이, OFFSET 공급 보정은 ±25.4mm입니다. Zebra ~TA는 ±120단계(600 DPI는 2도트)."),
        step(3, "설정값과 실제 장비를 각각 확인합니다", "TSC의 ‘현재 프린터 설정 사용’은 GAP/BLINE 전체 명령을 생략하고 0은 선택 용지의 추가 이송 0입니다. 빅솔론 p4는 SL과 인쇄 전 후진용 SF1을 보내며, TA ±100도트는 인쇄 시 프린터에 영구 저장됩니다. 저장은 config.ini만 바꿉니다. 실물 1매로 위치와 절취를 확인하세요."),
        note("모델별 확인", "세우테크는 승인 모델 전 고급 배출 보정을 제공하지 않습니다. 현재 설정 사용은 과거 TA 값을 복원하지 않습니다. 첫 장·다음 장의 위치와 배출·스캔을 실물로 확인하세요.", CAUTION),
    ])
    barcode_help = [
        PageBreak(), *heading("추가", "GS1과 바코드 세부 옵션", "종류에 맞는 옵션과 실제 출력 가능 범위를 확인합니다.", "barcode-gs1-options"),
        step(1, "바코드 종류를 선택합니다", "80개 선택 항목에는 1D, 2D, GS1, HIBC, 우편 및 복합 코드가 포함됩니다. 세부 옵션은 선택한 종류에 맞게 표시됩니다."),
        step(2, "GS1 데이터 구성 (AI)을 엽니다", "AI 번호·한국어 의미로 검색하거나 자주 사용하는 AI를 고릅니다. 새 AI와 선택 행의 수정값은 검증·적용 전에 자동 반영합니다. 필수 AI 선택에서 부족한 필드를 한 번에 확인합니다. 취소는 원본을 유지합니다."),
        step(3, "인쇄값과 필수 조합을 확인합니다", "AI21 일련번호는 01·03·8006 중 해당 상품의 식별번호와 함께 사용합니다. 필수 AI 선택에서 후보를 찾고 실제 값 또는 DB 열을 추가합니다. 임의 번호를 만들지 않습니다. 표시문자의 괄호와 인쇄 데이터의 GS 구분자를 구분합니다."),
        step(4, "세부 옵션과 라벨 크기를 맞춥니다", "QR 오류복원·버전·마스크, PDF417 행·열·보안 수준, Data Matrix 크기 등 해당 종류의 옵션을 설정합니다. 실제 도트 크기로 라벨을 넘으면 출력을 차단합니다."),
        p("URL, 긴 문자열과 특수문자는 임의로 제거하거나 잘라내지 않습니다. 지원하지 않는 문자·옵션이나 잘못된 데이터는 오류를 확인한 뒤 수정해야 합니다."),
        p("GS1 DataMatrix: 표시문자를 켜면 (01)상품식별번호, (17)사용기한, (10)로트 등 AI별 데이터를 표시합니다. 새 배치에서는 문자 위치를 오른쪽 또는 아래로 선택할 수 있습니다. AI와 값은 중간에 잘라내지 않습니다. GS1-128은 아래에 AI 괄호를 포함한 전체 값을 표시합니다. 괄호는 표시용이며 바코드 데이터에는 인코딩하지 않습니다."),
        p("지원 범위: BarTender 2022 Professional 공식 69개 형식 주제 중 57개에 대응합니다. iQR, 2D Pharmacode, Anker, 원형 바코드 4종, Code 93i, NEC 2 of 5, OPC, PosiCode, Singapore Post는 미지원입니다. 모든 950개 참조 옵션과 완전 동등한 제품은 아닙니다. 실제 프린터와 스캐너로 첫 장을 확인하세요.", "body_small"),
    ]
    for story, _title in manuals.values():
        story.extend(barcode_help)
        story.extend([
            PageBreak(), *heading("추가", "2D 바코드 크기를 먼저 정합니다", "바코드와 필수 여백을 확정한 뒤 표시문자를 배치합니다.", "barcode-size-first"),
            step(1, "2D 크기·문자 배치를 엽니다", "2D 개체를 더블클릭하고 크기 방식을 확인합니다. 새 2D 개체는 바코드 크기 우선으로 시작합니다. 기존 도안은 기존 배치를 유지하며 이 창에서 바코드 크기 우선을 선택하여 명시적으로 전환합니다."),
            Spacer(1, 3 * mm),
            step(2, "바코드 한 변(mm) 또는 바코드 가로(mm)·바코드 세로(mm)를 정합니다", "입력 크기는 표시문자를 제외하고 필수 여백을 포함한 바코드 영역의 목표입니다. 원래 코드 비율과 정수 모듈 도트를 유지하므로 실제 크기는 목표와 다를 수 있습니다. 실제 크기 확인에서 현재 데이터와 DPI 기준 결과를 확인합니다. 정사각형은 한 변으로, 직사각형은 원래 비율로 가로·세로·대각선 손잡이를 조절합니다."),
            Spacer(1, 3 * mm),
            step(3, "모듈 크기 고정을 구분합니다", "고급 크기 방식인 모듈 크기 고정은 모듈 도트를 기준으로 합니다. mm 목표와 도트를 동시에 독립적으로 지정하지 않습니다. 손잡이 조절은 잠기며 도트 설정으로 크기를 변경합니다. 데이터 길이나 코드 버전이 달라지면 모듈 수와 실제 전체 크기를 다시 확인합니다."),
            Spacer(1, 3 * mm),
            step(4, "문자 위치·간격·크기를 정합니다", "문자 위치는 오른쪽 또는 아래, 문자 간격(mm)은 바코드의 필수 여백 밖 간격입니다. 문자 크기는 자동 맞춤 또는 지정 크기를 선택합니다. 표시문자 켜기/끄기와 글꼴·위치 변경으로 이미 정한 바코드 크기가 줄어들지 않습니다."),
            Spacer(1, 3 * mm),
            step(5, "전체 개체와 라벨 경계를 확인합니다", "개체 전체 가로·세로는 바코드와 표시문자에서 계산합니다. 문자 공간이 부족해도 코드 그림을 유지합니다. 손잡이로 크기를 조절하거나 현재 라벨에 맞추기와 문자 아래 배치를 사용합니다. 바코드를 몰래 축소하거나 값을 잘라 해결하지 않으며 해결되지 않은 크기 오류는 인쇄 전에 수정해야 합니다."),
            note("실제 크기와 첫 장 확인", "목표 mm는 모든 용도의 규격 승인값이 아닙니다. 저장한 도안, 반복 출력 미리보기, 인쇄파일에서 같은 값을 확인하고 실제 프린터 DPI와 스캐너로 첫 장을 확인하세요. 1D의 기존 배치 방식은 유지합니다.", CAUTION),
        ])
    for filename in ("채움랩_라벨디자이너_고객용_매뉴얼.pdf", "채움랩_라벨출력관리_고객용_매뉴얼.pdf"):
        manuals[filename][0].extend([
            PageBreak(), *heading("추가", "같은 도안으로 반복 출력하고 값을 만듭니다", "도안·엑셀 연결·생성 규칙과 발급 기록을 함께 확인합니다.", "paid-workflow"),
            step(1, "출력 모드를 확인합니다", "디자이너에서 저장 후 반복 출력으로 이동합니다. 출력 관리의 선택 도안 이름·현재 도안 미리보기를 확인하세요. 자동 기본 배치는 사용자 도안과 다른 모드입니다."),
            Spacer(1, 3 * mm),
            step(2, "엑셀 파일·시트·열을 확인합니다", "도안에는 연결 파일 경로·시트·열 목록과 변경 확인값을 저장합니다. 원본 데이터는 포함하지 않습니다. 다른 PC나 파일 이동 뒤에는 상품 엑셀을 재연결하고 다시 검증합니다."),
            Spacer(1, 3 * mm),
            step(3, "값 생성 규칙을 만듭니다", "디자이너 도구 > 값 생성 규칙에서 일련번호, 날짜 / 기한, 문자 붙이기, 부분 추출을 고릅니다. 생성 필드는 {{필드 이름}} 또는 GS1의 DB 열로 연결하고 도안을 저장합니다."),
            Spacer(1, 3 * mm),
            step(4, "번호와 날짜의 기준을 정합니다", "일련번호의 시작 번호·증가량·자리수·같은 번호의 복사 수를 정합니다. 작업마다 시작 또는 계속 발급을 구분합니다. 날짜는 작업 날짜나 DB 날짜에 일수를 더하고 표시 형식을 정합니다."),
            Spacer(1, 3 * mm),
            step(5, "미리보기와 전체 검증을 합니다", "4장 미리보기는 번호를 소비하지 않습니다. 실제 계속 발급 번호와 모든 출력 데이터는 출력 전에 확인합니다. 작업이 확정되면 값과 기준일을 저장하므로 재개할 때 임의로 다시 계산하지 않습니다."),
            Spacer(1, 4 * mm),
            note("번호 발급 후 주의", "전송 결과가 불확실하면 실물부터 확인합니다. 새 번호 발급과 기존 값 재인쇄는 다른 작업입니다. 고객 백업에 out/value_jobs/ledger.json을 포함하며 오래된 번호나 누락된 작업 기록으로 복원하면 중복 위험 때문에 차단합니다. 발급 기록을 삭제해 차단을 우회하지 마세요.", CAUTION),
            p("출력 관리의 마지막 생성 작업 재인쇄는 저장된 번호·날짜·행을 다시 사용하며 새 번호를 발급하지 않습니다. 원본 엑셀이 없어도 같은 도안 버전이면 재인쇄할 수 있습니다. 디자이너의 번호 발급 초기화는 중복 위험을 확인한 뒤 해당 필드에만 적용합니다."),
        ])
    manuals["채움랩_라벨디자이너_고객용_매뉴얼.pdf"][0].extend([
        PageBreak(), *heading("추가", "AI와 UDI를 한 편집창에서 구성합니다", "시험 예제와 실제 식별번호를 구분하고 확정한 원문을 확인합니다.", "ai-udi-workflow"),
        step(1, "데이터 원본부터 입력합니다", "바코드를 더블클릭하면 데이터 원본부터 열립니다. 직접 입력 또는 DB / 엑셀 연결을 선택합니다. GS1 데이터로 설정…은 첫 화면에서 바로 열고 의료기기 UDI는 기타 데이터 옵션…에서 선택합니다. 바코드 종류·크기와 표시문자는 별도 메뉴입니다. 원본을 전환해도 각 입력 초안은 보존됩니다."),
        p("상단 미리보기 버튼을 눌러 DB 행, 실제 인코딩 값과 표시문자, DPI와 실제 mm를 확인합니다. 전체 보기·100%·확대 보기를 사용하세요. 오류는 이미지 밖에 표시됩니다. 편집창 하단의 적용·확인으로만 저장하며 취소·Esc·창 닫기는 마지막 적용값을 보존합니다.", "body_small"),
        step(2, "시험용 완성 예제로 시작합니다", "완성 예제는 필요한 조합을 갖춘 시험용 데이터입니다. 실제 운영 전 발급·관리하는 번호 또는 DB 열로 바꿉니다. 필수 AI 선택에서 부족한 항목을 한 번에 확인합니다. AI21과 AI37의 필요 조합은 서로 다르며 임의의 실제 번호를 채우지 않습니다."),
        step(3, "값 입력과 전체 가져오기를 구분합니다", "새 AI와 수정 중인 행은 검증·적용 전에 자동 반영합니다. 한 AI의 값 칸에는 값만 입력합니다. AI 괄호나 스캐너 구분자가 포함된 문자열은 전체 GS1 데이터 가져오기에서 미리보고 항목·값·선행 0을 확인합니다."),
        step(4, "UDI를 쓸 때만 DI와 PI를 구성합니다", "의료기기 UDI 구성에서 제품 식별번호(DI)와 로트·일련번호·제조일·사용기한(PI)을 입력하고 고정값 또는 DB 열을 연결합니다. 구성을 선택하면 편집 초안에 반영됩니다. 창 하단의 적용 또는 확인으로 저장합니다. 긴 UDI의 GS1-128 용량 오류는 값을 유지한 채 GS1 DataMatrix 전환을 검토합니다."),
        note("원문 보존과 적용 범위", "HIBC의 원본으로 생성과 완성 코드 가져오기를 구분합니다. 완성 코드의 +접두·체크문자·공백을 임의로 제거하거나 중복 추가하지 않습니다. 국내 프로필은 기관 등록·규제 승인 완료가 아닙니다. Basic UDI-DI는 GTIN과 별도 정보입니다.", CAUTION),
        p("적용은 편집 초안을 반영하고 확인은 반영 후 창을 닫습니다. 취소·Esc·창 닫기는 마지막 적용 상태를 보존합니다. 전체 DB 행과 라벨 경계는 메인 화면의 전체 데이터 검증에서 확인한 뒤 저장·출력하세요. 해결되지 않은 값·필수 조합·용량·문자 공간·라벨 경계·DB 행 오류는 인쇄를 차단합니다. 실제 프린터와 스캐너로 첫 장을 확인하세요.", "body_small"),
    ])
    udi_screen = SCREENSHOTS / "frozen-udi-content.png"
    if not udi_screen.is_file():
        raise FileNotFoundError("최신 UDI 입력 화면 캡처가 없습니다.")
    with PilImage.open(udi_screen) as current_ui:
        image_height = 174 * mm * current_ui.height / current_ui.width
    manuals["채움랩_라벨디자이너_고객용_매뉴얼.pdf"][0].extend([
        PageBreak(), *heading("화면", "의료기기 UDI 입력 예제", "실제 편집창에서 제품 식별번호와 생산 정보를 한 번에 구성합니다.", "udi-input-screen"),
        Image(str(udi_screen), width=174 * mm, height=image_height), Spacer(1, 5 * mm),
        step(1, "한글 필드에 값 또는 DB 열을 지정합니다", "제품 식별번호의 선행 0을 유지합니다. 필요한 로트·일련번호·날짜를 선택하고 YYYY-MM-DD 날짜를 입력합니다. 고정값과 연결한 DB 열은 같은 행에서 확인합니다."),
        step(2, "초안을 적용하고 전체 데이터를 검증합니다", "선택 기호 용량, 실제 바코드 크기와 표시문자를 확인한 뒤 창 하단에서 적용 또는 확인을 누릅니다. 메인 화면의 전체 데이터 검증으로 모든 DB 행과 라벨 경계를 확인합니다. 예제는 시험용입니다. 저장·재열기 후 실제 첫 장을 확인합니다."),
    ])
    guide_steps = [
        step(1, "소수 규격과 네 방향을 저장합니다", "용지 구역에서 50.5×30.25mm처럼 폭·길이를 입력합니다. 세로·가로·세로 180도·가로 180도를 선택하고 방향·위치 미리보기로 TOP 방향을 확인합니다. 가로는 반시계 90도이며 작업면 폭·높이를 교환합니다."),
        step(2, "내용 위치와 용지 배출 보정을 구분합니다", "좌우·상하 보정의 양수는 인쇄된 용지의 오른쪽·아래쪽입니다. 내용이 라벨 밖으로 나가면 인쇄를 차단합니다. 센서·절취선 거리는 용지 종류 아래에서 조정합니다. BIXOLON p4와 TSC GAP/BLINE은 용지 이동에 적용되며, TSC의 현재 설정 사용은 GAP/BLINE 전체 명령을 생략합니다. 명시적 0은 선택한 용지 유형의 추가 이송 0입니다. BIXOLON TA 절취·커터 정지 보정은 별도이며 인쇄 시 장비에 영구 저장됩니다. 구버전의 비활성 BIXOLON 칸에 저장된 기본 0은 장비 설정 유지로 불러옵니다."),
        step(3, "회전 도안을 다시 인식하고 원본을 대조합니다", "누운 글자는 인식용 복사본에서 방향과 격자를 보정하고 원래 도안 위치·방향으로 복원합니다. 인식 값 전체 확인으로 글자·숫자·앞자리 0을 확인합니다. 이미 틀린 값은 원본을 다시 적용해야 합니다. BarTender 파일을 PNG로 이름만 바꾸면 이미지가 되지 않습니다."),
        note("마지막 확인", "도안의 규격·방향은 저장파일에, 장비별 위치 보정은 config.ini에 저장됩니다. 다른 규격 도안은 열 때 적용 방법을 선택합니다. 인쇄파일과 미리보기를 확인한 뒤 실제 장비 1매의 규격·위치·배출·스캔을 확인하세요.", CAUTION),
    ]
    for filename, (story, manual_title) in manuals.items():
        story.extend([PageBreak(), *heading("추가", "소수 규격과 도안 방향을 확인합니다", "2026.10.20.01 용지와 도안 인식 사용법", "media-ocr"), *guide_steps])
        build_pdf(OUTPUT / filename, story, manual_title)

    for destination in (CUSTOMER_RUNTIME / "docs/고객용_매뉴얼", TOP_LEVEL / "docs/고객용_매뉴얼"):
        destination.mkdir(parents=True, exist_ok=True)
        for filename in manuals:
            copy2(OUTPUT / filename, destination / filename)

    print("CUSTOMER_MANUALS_BUILT")
    for filename in manuals:
        print(OUTPUT / filename)


if __name__ == "__main__":
    main()

