from __future__ import annotations

"""Build customer manuals with a step-first, print-manual layout.

The PDFs deliberately use one clear action area per page.  Screens are cropped
and enlarged instead of being placed as small full-screen captures with labels.
"""

from pathlib import Path
from shutil import copy2

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
TEAL = colors.HexColor("#174B4E")
TEAL_DARK = colors.HexColor("#103A3D")
MINT = colors.HexColor("#B7DE67")
MINT_PALE = colors.HexColor("#F1F7E3")
PAPER = colors.HexColor("#FCFDFC")
WARM = colors.HexColor("#F6F7F5")
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
        body += f'<br/><font color="#174B4E"><b>확인</b>  {check}</font>'
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
        badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TEAL), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
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
    canvas = PilImage.new("RGB", (canvas_width, canvas_height), "#F3F6F5")
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 30)
    body_font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 23)
    badge_font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 24)
    draw.text((margin, 18), label, font=title_font, fill="#152126")
    title_width = draw.textbbox((0, 0), label, font=title_font)[2]
    draw.rounded_rectangle(
        (margin + title_width + 18, 28, canvas_width - margin, 35),
        radius=4,
        fill="#72A91B",
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
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12, outline="#72A91B", width=7)
        badge_size = 42
        badge_box = (x1 + 10, y1 + 10, x1 + 10 + badge_size, y1 + 10 + badge_size)
        draw.ellipse(badge_box, fill="#123F46", outline="#FFFFFF", width=3)
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
            draw.rounded_rectangle((x, y, x + 38, y + 38), radius=9, fill="#123F46")
            badge_text = str(number)
            bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
            draw.text(
                (x + (38 - (bbox[2] - bbox[0])) / 2, y + (38 - (bbox[3] - bbox[1])) / 2 - 1),
                badge_text,
                font=badge_font,
                fill="#FFFFFF",
            )
            draw.text((x + 50, y + 5), text, font=body_font, fill="#23474D")

    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, format="PNG", optimize=True, dpi=(180, 180))
    return target


def screen(path: Path, max_height_mm: float, caption: str) -> list:
    image = PilImage.open(path)
    ratio = image.height / image.width
    width = CONTENT_WIDTH
    height = min(max_height_mm * mm, width * ratio)
    return [Image(str(path), width=width, height=height), Spacer(1, 2.3 * mm), p(caption, "caption")]


def page_header(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(MARGIN_X, PAGE_HEIGHT - 11.5 * mm, 22 * mm, 2.2 * mm, fill=1, stroke=0)
    canvas.setFillColor(INK_SOFT)
    canvas.setFont("ManualMalgunBold", 8)
    canvas.drawString(MARGIN_X, PAGE_HEIGHT - 17.5 * mm, "채움LAB")
    canvas.setFont("ManualMalgun", 8)
    canvas.drawString(MARGIN_X + 18 * mm, PAGE_HEIGHT - 17.5 * mm, doc.manual_title)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, 12 * mm, PAGE_WIDTH - MARGIN_X, 12 * mm)
    canvas.setFont("ManualMalgun", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN_X, 7.4 * mm, "채움LAB 고객용 사용 매뉴얼 | Rev. 2026.09.30")
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
        story += [Image(str(logo), width=58 * mm, height=17 * mm), Spacer(1, 20 * mm)]
    story += [p("CUSTOMER GUIDE", "eyebrow"), p(title, "cover"), Spacer(1, 5 * mm), p(subtitle, "cover_sub"), Spacer(1, 24 * mm), thin_rule(), Spacer(1, 10 * mm)]
    intro = Table([
        [p("대상 프로그램", "note_title"), p(executable, "body")],
        [p("이 문서에서 하는 일", "note_title"), p(purpose, "body")],
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
            ("07", "정밀 편집과 복구"), ("08", "도안 인식과 출력"),
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

        *heading("02", "디자인과 출력 작업을 구분합니다", "저장·상품 연결·도구·속성의 위치를 먼저 익힙니다.", "designer-screen"),
        *screen(images["overview"], 111, "① 파일·상품·출력  ② 개체 도구  ③ 편집 캔버스  ④ 속성·상품 데이터"),
        Spacer(1, 3 * mm),
        note("반복 출력 담당자", "양식을 고치지 않는다면 반복 출력 화면을 눌러 라벨 출력 관리로 이동합니다. 상품 선택, 매수, 전송에 집중할 수 있습니다."), PageBreak(),

        *heading("03", "크기를 적용하고 작업 파일을 저장합니다", "파일명 옆의 별표는 아직 저장하지 않은 변경을 뜻합니다.", "designer-size-save"),
        *screen(images["toolbar"], 72, "① 상품 엑셀·라벨 크기  ② 파일·실행취소  ③ 출력"),
        Spacer(1, 4 * mm),
        step(1, "가로와 세로를 입력합니다", "실제 라벨 한 장의 mm 값을 넣고 크기 적용을 누릅니다.", "캔버스 눈금 끝값이 입력한 크기와 같아야 합니다."),
        Spacer(1, 3 * mm),
        step(2, "저장과 최근 라벨을 사용합니다", "저장 또는 Ctrl+S로 .gblabel을 보관합니다. 최근 라벨은 파일 메뉴에서 다시 열 수 있습니다."),
        Spacer(1, 3 * mm),
        step(3, "실수를 되돌립니다", "Ctrl+Z로 실행취소, Ctrl+Y로 다시실행합니다. 비정상 종료 후 복구 제안은 저장 원본을 덮어쓰지 않는 작업 사본입니다."), PageBreak(),

        *heading("04", "필요한 개체를 라벨에 넣습니다", "한 번에 많이 넣기보다, 하나를 넣고 크기와 위치를 먼저 확인합니다.", "designer-objects"),
        *screen(images["canvas"], 114, "① 개체 도구  ② mm 눈금이 보이는 편집 캔버스"),
        Spacer(1, 4 * mm),
        step(1, "텍스트 또는 여러 줄 텍스트를 넣습니다", "품명, 주소, 설명처럼 읽혀야 하는 정보를 넣고 선택 개체 편집에서 글꼴, 정렬, 위치와 크기를 바꿉니다."),
        Spacer(1, 3 * mm),
        step(2, "1D 또는 2D 코드를 넣습니다", "바코드 값은 텍스트가 아닌 문자열로 입력합니다. Code128, EAN, QR, DataMatrix, PDF417 등 필요한 코드 종류를 선택합니다."),
        Spacer(1, 3 * mm),
        step(3, "그림과 표를 넣습니다", "JPG/PNG 그림, 박스, 선, 표를 넣어 양식을 구성합니다. 필요한 개체만 배치하고 인쇄파일에서 경계를 확인합니다."), PageBreak(),

        *heading("05", "개체 방향을 설정합니다", "텍스트와 바코드만이 아니라 그림, 박스, 선, 표에도 같은 방식으로 적용됩니다.", "designer-rotation"),
        note("방향 설정 위치", "개체를 선택한 뒤 선택 개체 편집을 열고 방향을 고릅니다. 개체를 선택하지 않으면 방향 값을 바꿀 수 없습니다.", MINT_PALE),
        Spacer(1, 8 * mm),
        step(1, "0도 (기본)", "일반적인 가로 읽기 방향입니다. 새 개체는 이 방향으로 시작합니다."),
        Spacer(1, 4 * mm),
        step(2, "90도 시계 방향 또는 270도 시계 방향", "세로로 읽는 품목명이나 좁은 세로 라벨에 사용합니다. 적용 후 폭과 높이가 바뀌므로 라벨 경계를 다시 확인합니다."),
        Spacer(1, 4 * mm),
        step(3, "180도", "라벨 전체가 뒤집혀 붙는 레이아웃에서 사용합니다. 미리보기와 시험 출력에서 읽는 방향을 확인합니다."),
        Spacer(1, 7 * mm),
        note("저장과 출력", "선택한 방향은 .gblabel 파일에 저장되며, 미리보기와 인쇄파일, 실제 출력에도 같은 각도로 반영됩니다.", CAUTION), PageBreak(),

        *heading("06", "상품 엑셀을 연결하고 행을 고릅니다", "상품 열의 실제 값과 선택 대상을 확인합니다.", "designer-db"),
        *screen(images["db"], 106, "① 상품 엑셀 연결 상태  ② 선택 개체의 상품 열 연결"),
        Spacer(1, 4 * mm),
        step(1, "상품 엑셀 연결을 누릅니다", "상단에서 .xlsx 또는 .xlsm을 선택합니다. 연결 중 취소하면 새 결과를 적용하지 않고 기존 연결을 유지합니다."),
        Spacer(1, 3 * mm),
        step(2, "개체에 상품 열을 지정합니다", "텍스트·1D 바코드·QR 개체의 편집 화면에서 엑셀에 실제로 있는 열을 고릅니다. 필요한 값은 필수 항목으로 지정합니다."),
        Spacer(1, 3 * mm),
        step(3, "상품 선택에서 행을 고릅니다", "상품 선택을 열어 출력할 행만 체크합니다. 바코드 앞자리 0은 원본 셀 값과 미리보기를 대조합니다."),
        Spacer(1, 3 * mm),
        step(4, "선택 항목 인쇄파일을 만듭니다", "대상과 매수를 확인한 뒤 파일을 먼저 생성합니다. 실제 인쇄는 실물 확인이 가능한 상태에서 시작합니다."), PageBreak(),

        *heading("07", "개체를 정밀하게 맞추고 되돌립니다", "선택과 보기 크기는 저장된 라벨 크기를 바꾸지 않습니다.", "designer-precision"),
        step(1, "여러 개체를 선택합니다", "Ctrl+클릭으로 필요한 개체를 더 고른 뒤 복제, 그룹, 그룹 해제, 잠금/해제를 사용합니다."),
        Spacer(1, 4 * mm),
        step(2, "위치와 간격을 맞춥니다", "왼쪽 정렬, 가로 간격 맞춤, 눈금 맞춤을 사용합니다. 방향키는 1mm, Shift+방향키는 0.1mm씩 움직입니다."),
        Spacer(1, 4 * mm),
        step(3, "보기 크기와 이력을 확인합니다", "화면 맞춤 또는 +/−로 캔버스를 확대·축소합니다. Ctrl+Z와 Ctrl+Y로 변경을 되돌리고 다시 적용합니다."),
        Spacer(1, 7 * mm),
        note("잠긴 개체", "잠긴 로고나 바코드는 이동·삭제·속성 수정을 막습니다. 수정이 필요할 때만 잠금을 해제하세요.", CAUTION), PageBreak(),

        *heading("08", "도안 인식 값을 검토하고 출력합니다", "자동 인식 결과는 후보이며 사람의 확인이 필요합니다.", "designer-print"),
        step(1, "도안을 불러옵니다", "도안 불러오기에서 PSD/JPG/PNG를 선택하고 도안 적용을 누릅니다."),
        Spacer(1, 3 * mm),
        step(2, "원본과 인식 값을 비교합니다", "인식 값 검토에서 이미지와 후보 글자·바코드를 나란히 보고 임시 값은 직접 수정해 확인합니다. 미확인 값이 있으면 출력이 차단됩니다."),
        Spacer(1, 3 * mm),
        step(3, "출력 전 경고를 처리합니다", "경계 밖 개체와 빈 필수 값을 수정합니다. 글자 축소·작은 QR 경고는 첫 장 출력에서 읽힘을 확인합니다."),
        Spacer(1, 3 * mm),
        step(4, "인쇄파일과 실물을 확인합니다", "인쇄파일 생성은 프린터에 보내지 않습니다. 실제 전송 후에는 라벨 배출·위치·1D와 2D 스캔을 확인합니다."),
        Spacer(1, 5 * mm),
        note("전송이 중단된 경우", "프린터 전송 완료 안내도 실물 확인이 필요합니다. 결과가 미확인인 항목은 실물을 먼저 보고, 다시 인쇄할 때 전송됨 또는 재전송을 직접 선택합니다. 이미 나온 라벨을 다시 보내면 중복될 수 있습니다.", CAUTION), PageBreak(),

        *heading("09", "다른 PC로 작업을 옮깁니다", "도안 파일, 이미지와 원본 상품 엑셀의 역할을 구분합니다.", "designer-transfer"),
        step(1, "이동용 프로젝트를 내보냅니다", "파일 메뉴에서 이동용 프로젝트 내보내기를 선택해 .gbproject를 보관합니다. 현재 도안과 필요한 이미지를 함께 옮깁니다."),
        Spacer(1, 4 * mm),
        step(2, "새 PC에서 가져옵니다", "이동용 프로젝트 가져오기 후 상품 엑셀을 다시 연결합니다. 누락된 파일·글꼴·라벨 크기와 프린터 설정을 확인합니다."),
        Spacer(1, 4 * mm),
        step(3, "기존 BarTender 도안을 다시 만듭니다", ".btw는 직접 열 수 없습니다. BarTender에서 PNG로 내보낸 다음 도안 불러오기로 참고 이미지를 열고 필드와 바코드를 다시 연결합니다."),
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
        step(1, "DB 파일 메뉴에서 DB 연결을 선택합니다", "상품 엑셀 파일을 선택합니다. 첫 행은 반드시 열 제목이어야 합니다."), Spacer(1, 3 * mm),
        step(2, "불러온 열과 행 수를 확인합니다", "인쇄 데이터와 원본 DB 탭을 모두 열어 값이 누락되지 않았는지 봅니다."), Spacer(1, 3 * mm),
        step(3, "행을 편집하고 저장합니다", "셀을 더블클릭하거나 Enter로 수정한 뒤 DB 파일 메뉴에서 저장합니다."), Spacer(1, 5 * mm),
        note("원본 DB를 바꾸기 전", "삭제나 대량 수정 전에 원본 파일을 백업합니다. 저장 후에는 인쇄 데이터의 현재 값도 다시 확인합니다.", CAUTION), PageBreak(),

        *heading("04", "검색 결과와 중복 행을 선택합니다", "중복 값은 자동으로 하나를 고르지 않습니다. 원하는 행을 직접 선택합니다.", "manager-search"),
        step(1, "찾을 값을 입력하거나 스캔합니다", "상단 DB 상품조회에 바코드, 품명, 품목 코드, 가격처럼 DB에 있는 값을 입력한 뒤 조회합니다."), Spacer(1, 3 * mm),
        step(2, "중복 선택 창에서 필요한 행만 고릅니다", "기본 상태는 아무 행도 선택되지 않습니다. 원하는 행만 체크하거나 전체 선택을 사용합니다."), Spacer(1, 3 * mm),
        step(3, "확인을 눌러 인쇄 데이터에 반영합니다", "확인을 누르면 이번 선택이 인쇄 데이터에 적용됩니다. 취소하면 기존 선택을 유지합니다."), Spacer(1, 5 * mm),
        note("중복 선택 주의", "확인하면 기존 체크가 이번 선택으로 교체됩니다. 전체 출력이 필요하지 않다면 대상 행과 수량을 다시 확인합니다.", CAUTION), PageBreak(),

        *heading("05", "선택한 항목만 인쇄합니다", "출력 작업 영역에서 대상과 수량을 마지막으로 확인합니다.", "manager-print"),
        *screen(images["print"], 87, "① 인쇄 범위와 실행  ② 출력 대상 선택  ③ 점검과 설정"),
        Spacer(1, 4 * mm),
        step(1, "인쇄 데이터의 선택 칸을 체크합니다", "출력할 행만 체크하고, 라벨 크기에 맞춰 텍스트와 바코드가 자동 배치되는지 미리 확인합니다."), Spacer(1, 3 * mm),
        step(2, "실행 전 점검을 누릅니다", "DB, 프린터 설정과 오류 여부를 먼저 확인합니다."), Spacer(1, 3 * mm),
        step(3, "인쇄 매수를 선택하고 시작합니다", "인쇄를 누르면 인쇄 매수 선택 창이 열립니다. 1장부터 100장까지 입력하거나 1·3·5·10장 빠른 선택을 누른 뒤 인쇄 시작을 선택합니다."), Spacer(1, 5 * mm),
        note("선택 항목에 같은 매수 적용", "체크한 행이 있으면 선택한 각 항목에 같은 인쇄 매수가 적용됩니다. 취소를 누르면 출력 명령을 보내지 않습니다."), Spacer(1, 3 * mm),
        note("체크가 0개일 때", "선택 항목이 없으면 인쇄가 차단됩니다. 전체 출력이 필요할 때만 전체 선택을 누르고 대상 건수와 수량을 확인합니다.", CAUTION), PageBreak(),

        *heading("06", "점검 결과와 로그로 문제를 찾습니다", "출력 문제가 생기면 같은 작업을 반복하기 전에 점검 결과를 먼저 봅니다.", "manager-help"),
        step(1, "실행 전 점검 결과를 엽니다", "out/customer_preflight_report.txt에서 DB, 설정과 필수 파일 오류를 확인합니다."), Spacer(1, 3 * mm),
        step(2, "지원 패키지를 만듭니다", "설정 메뉴의 지원 패키지 생성으로 out/customer_support_package.zip을 만듭니다. 고객 데이터 백업·복원도 설정 메뉴에 있고 라벨 디자인은 상단의 별도 버튼입니다."), Spacer(1, 3 * mm),
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
        note("공용 설정", "저장한 config.ini는 라벨 디자이너와 라벨 출력 관리가 함께 사용합니다. 장비나 라벨 규격이 바뀌면 다시 저장합니다.", MINT_PALE), PageBreak(),

        *heading("02", "설정 화면을 먼저 확인합니다", "한 화면에서 브랜드, 연결, 용지와 바코드 기본값을 모두 점검합니다.", "settings-screen"),
        *screen(images["overview"], 112, "① 불러오기·점검·저장  ② 설정 흐름과 검증  ③ 장비와 연결  ④ 용지와 바코드"),
        Spacer(1, 4 * mm),
        note("입력 전 원칙", "알 수 없는 값은 추측해서 넣지 않습니다. 프린터의 실제 모델 설명서와 설치된 Windows 프린터 이름을 기준으로 확인합니다."), PageBreak(),

        *heading("03", "브랜드와 인쇄후작업을 정합니다", "프린터에 없는 옵션을 설정하면 동작하지 않습니다.", "settings-printer"),
        *screen(images["printer"], 101, "① 제조사와 출력 방식  ② 연결 방식"),
        Spacer(1, 4 * mm),
        step(1, "실제 브랜드를 선택합니다", "BIXOLON/빅솔론, TSC, Zebra/제브라, SEWOO/세우테크(ZPL) 중 장비와 같은 브랜드를 선택합니다."), Spacer(1, 3 * mm),
        step(2, "인쇄 방식을 고릅니다", "감열지는 감열/리본 없음을, 리본을 쓰는 라벨은 열전사/리본 사용을 선택합니다."), Spacer(1, 3 * mm),
        step(3, "인쇄후작업과 방향을 정합니다", "뜯어내기, 커터, 필러는 장비에 실제로 장착된 기능만 고릅니다. 전체 라벨을 뒤집어야 할 때만 180도 회전을 선택합니다."), PageBreak(),

        *heading("04", "연결 방식을 설정합니다", "LAN과 USB/Windows 프린터는 확인 방법이 다릅니다.", "settings-connect"),
        step(1, "LAN/네트워크를 쓸 때", "프린터 IP와 포트를 입력합니다. 일반적인 포트는 9100이지만 프린터 설정값을 우선합니다."), Spacer(1, 3 * mm),
        step(2, "USB/Windows 프린터를 쓸 때", "목록 새로고침 후 Windows에 설치된 프린터 이름을 정확히 선택합니다."), Spacer(1, 3 * mm),
        step(3, "연결 확인을 실행합니다", "LAN은 IP/포트 TCP 접속을, USB는 Windows 프린터 이름의 존재 여부를 확인합니다."), Spacer(1, 5 * mm),
        note("연결 확인의 한계", "연결 확인 성공은 장비가 보인다는 1차 결과입니다. 명령 수신과 출력 품질은 반드시 1장 출력으로 확인합니다.", CAUTION), PageBreak(),

        *heading("05", "용지 크기와 DPI를 실제 규격에 맞춥니다", "라벨 크기와 DPI가 다르면 출력 위치도 달라집니다.", "settings-media"),
        *screen(images["media"], 99, "① 용지 가로·세로·간격·DPI  ② 기본 바코드 배치"),
        Spacer(1, 4 * mm),
        step(1, "가로와 세로를 mm로 입력합니다", "실제 라벨 한 장의 폭과 높이를 입력하고 라벨 디자이너의 크기도 같게 맞춥니다."), Spacer(1, 3 * mm),
        step(2, "용지 유형과 간격을 정합니다", "갭·블랙마크 용지는 간격을 0보다 크게, 연속 용지는 0을 권장합니다."), Spacer(1, 3 * mm),
        step(3, "DPI와 바코드 배치를 확인합니다", "장비 사양에 맞춰 203/300/600을 고릅니다. 자동 가운데 배치를 끄면 X/Y 위치를 직접 확인합니다."), PageBreak(),

        *heading("06", "점검하고 1장으로 끝까지 확인합니다", "저장 성공만으로 프린터 설정이 끝난 것은 아닙니다.", "settings-help"),
        step(1, "설정 점검을 누릅니다", "브랜드, 연결 방식, 용지 유형, 간격, DPI와 바코드 기본값의 오류를 확인합니다."), Spacer(1, 3 * mm),
        step(2, "설정 저장을 누릅니다", "오류가 없을 때 저장합니다. 고객 실행 폴더의 config.ini에 반영됩니다."), Spacer(1, 3 * mm),
        step(3, "라벨출력관리에서 1장을 출력합니다", "크기, 180도 방향, 농도, 커터/필러와 바코드 판독을 순서대로 확인합니다."), Spacer(1, 5 * mm),
        note("완료 기준", "연결 확인과 설정 저장 뒤 실제 라벨 1장이 정상 위치에 배출되고, 인쇄후작업과 바코드 판독까지 맞아야 설정이 완료됩니다.", CAUTION),
    ]
    return story


def build_pdf(path: Path, story: list, manual_title: str) -> None:
    doc = ManualDocTemplate(
        str(path), pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=path.stem, author="채움LAB",
    )
    doc.manual_title = manual_title
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="content", showBoundary=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover_page),
        PageTemplate(id="body", frames=[frame], onPage=page_header),
    ])
    doc.build(story)


def main() -> None:
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
                (1, "파일·상품·출력", (20, 88, 1460, 226)),
                (2, "개체 도구", (20, 239, 356, 857)),
                (3, "편집 캔버스", (369, 239, 1131, 857)),
                (4, "속성·상품 데이터", (1143, 239, 1459, 857)),
            ),
        ),
        "toolbar": save_focus(
            designer_source,
            generated / "designer-toolbar-focus.png",
            (18, 88, 1462, 228),
            "상품 연결 · 파일 · 출력",
            (
                (1, "상품 엑셀과 라벨 크기", (20, 89, 692, 225)),
                (2, "파일과 실행취소", (693, 89, 1080, 225)),
                (3, "출력", (1060, 89, 1458, 225)),
            ),
        ),
        "canvas": save_focus(
            designer_source,
            generated / "designer-canvas-focus.png",
            (18, 238, 1132, 860),
            "개체 도구와 편집 캔버스",
            (
                (1, "개체 도구", (20, 239, 356, 857)),
                (2, "mm 편집 캔버스", (369, 239, 1131, 857)),
            ),
        ),
        "db": save_focus(
            designer_data_source,
            generated / "designer-db-focus.png",
            (1141, 238, 1462, 860),
            "상품 데이터 영역",
            (
                (1, "상품 엑셀 연결 상태", (1143, 239, 1459, 488)),
                (2, "선택 개체의 상품 열", (1143, 489, 1459, 857)),
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
                (1, "DB 상품조회", (20, 0, 1460, 92)),
                (2, "메뉴와 인쇄", (20, 112, 1460, 178)),
                (3, "인쇄 데이터", (20, 190, 1130, 858)),
                (4, "출력 작업", (1142, 190, 1459, 858)),
            ),
        ),
        "data": save_focus(
            manager_source,
            generated / "manager-data-focus.png",
            (18, 188, 1132, 861),
            "인쇄 데이터와 원본 DB",
            (
                (1, "인쇄 데이터 / 원본 DB", (20, 190, 1130, 228)),
                (2, "행 선택과 데이터", (20, 228, 1130, 858)),
            ),
        ),
        "print": save_focus(
            manager_source,
            generated / "manager-print-focus.png",
            (18, 112, 1462, 861),
            "선택 인쇄와 출력 작업",
            (
                (1, "인쇄 범위와 실행", (20, 112, 1460, 178)),
                (2, "출력 대상 선택", (20, 190, 1130, 858)),
                (3, "점검과 설정", (1142, 190, 1459, 858)),
            ),
        ),
    }
    settings_images = {
        "overview": save_focus(
            settings_source,
            generated / "settings-overview-focus.png",
            (10, 8, 1470, 600),
            "프린터 설정 전체 화면",
            (
                (1, "불러오기·점검·저장", (12, 92, 1468, 135)),
                (2, "설정 흐름과 검증", (12, 144, 1468, 195)),
                (3, "장비와 연결", (12, 204, 736, 597)),
                (4, "용지와 바코드", (743, 204, 1468, 558)),
            ),
        ),
        "printer": save_focus(
            settings_source,
            generated / "settings-printer-focus.png",
            (10, 202, 738, 600),
            "장비와 연결",
            (
                (1, "제조사와 출력", (12, 204, 736, 403)),
                (2, "연결 방식", (12, 410, 736, 597)),
            ),
        ),
        "media": save_focus(
            settings_source,
            generated / "settings-media-focus.png",
            (741, 202, 1470, 562),
            "용지 크기와 바코드 설정",
            (
                (1, "용지 규격", (743, 204, 1468, 358)),
                (2, "바코드 기본값", (743, 365, 1468, 558)),
            ),
        ),
    }

    manuals = {
        "채움LAB_라벨디자이너_고객용_매뉴얼.pdf": (designer_manual(designer_images), "라벨 디자이너"),
        "채움LAB_라벨출력관리_고객용_매뉴얼.pdf": (manager_manual(manager_images), "라벨 출력 관리"),
        "채움LAB_프린터설정_고객용_매뉴얼.pdf": (settings_manual(settings_images), "프린터 설정"),
    }
    for filename, (story, manual_title) in manuals.items():
        build_pdf(OUTPUT / filename, story, manual_title)

    for destination in (CUSTOMER_RUNTIME / "고객용_매뉴얼", TOP_LEVEL / "고객용_매뉴얼"):
        destination.mkdir(parents=True, exist_ok=True)
        for filename in manuals:
            copy2(OUTPUT / filename, destination / filename)

    print("CUSTOMER_MANUALS_BUILT")
    for filename in manuals:
        print(OUTPUT / filename)


if __name__ == "__main__":
    main()
