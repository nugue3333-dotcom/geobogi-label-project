"""Create realistic 100 x 100 mm label templates for Danggeun sample photos.

The output intentionally lives outside the customer deployment and does not
modify the blank default template. Each .gblabel can be opened and edited in
채움랩 라벨 디자이너.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from barcode_label_automation.label_designer_app import LabelDesignerApp


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("GEOBOKI_SAMPLE_ROOT") or (PROJECT_ROOT / "outputs" / "danggeun_sample"))
TEMPLATE_DIR = ROOT / "라벨템플릿"
PREVIEW_DIR = ROOT / "미리보기"
VALIDATION_DIR = ROOT / "검증"


def text(identifier: str, value: str, x: float, y: float, width: float, height: float, size: int, *, align: str = "left") -> dict[str, object]:
    return {
        "id": identifier,
        "type": "text",
        "text": value,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "font_size": size,
        "font_name": "Malgun Gothic",
        "align": align,
        "field": "",
        "reverse": False,
        "arrange": "normal",
    }


def line(identifier: str, x: float, y: float, width: float) -> dict[str, object]:
    return {
        "id": identifier,
        "type": "line",
        "text": "",
        "x": x,
        "y": y,
        "width": width,
        "height": 0,
        "stroke_width": 0.45,
        "printable": True,
        "arrange": "normal",
    }


def box(identifier: str, x: float, y: float, width: float, height: float, stroke: float = 0.55) -> dict[str, object]:
    return {
        "id": identifier,
        "type": "box",
        "text": "",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "stroke_width": stroke,
        "printable": True,
        "arrange": "normal",
    }


def barcode(identifier: str, value: str) -> dict[str, object]:
    return {
        "id": identifier,
        "type": "barcode",
        "text": value,
        "x": 8,
        "y": 66,
        "width": 84,
        "height": 22,
        "font_size": 10,
        "font_name": "Malgun Gothic",
        "align": "center",
        "field": "",
        "barcode_type": "code128",
        "reverse": False,
        "arrange": "normal",
    }


def food_elements(product: str, origin: str, weight: str, packed: str, storage: str, code: str) -> list[dict[str, object]]:
    return [
        box("border", 3, 3, 94, 94),
        text("category", "신선식품 상품라벨", 8, 8, 84, 5, 9, align="center"),
        line("title-line", 8, 15, 84),
        text("product", product, 8, 19, 84, 10, 18, align="center"),
        line("product-line", 8, 31, 84),
        text("origin", f"원산지  {origin}", 8, 36, 84, 6, 11),
        text("weight", f"내용량  {weight}", 8, 44, 84, 6, 11),
        text("packed", f"포장일  {packed}", 8, 52, 84, 6, 11),
        text("storage", storage, 8, 59, 84, 5, 9),
        barcode("barcode", code),
        text("code", code, 8, 89, 84, 4, 8, align="center"),
    ]


def accessory_elements(product: str, option: str, price: str, code: str) -> list[dict[str, object]]:
    return [
        box("border", 3, 3, 94, 94),
        text("brand", "FillingLAB SELECT", 8, 8, 84, 5, 9, align="center"),
        line("title-line", 8, 15, 84),
        text("product", product, 8, 20, 84, 10, 18, align="center"),
        text("option", option, 8, 32, 84, 6, 10, align="center"),
        line("detail-line", 8, 41, 84),
        text("item", f"상품코드  {code}", 8, 46, 84, 6, 11),
        text("price", f"판매가  {price}", 8, 55, 84, 7, 14),
        barcode("barcode", code),
        text("code", code, 8, 89, 84, 4, 8, align="center"),
    ]


def sauce_elements() -> list[dict[str, object]]:
    code = "SAUCE25071401"
    return [
        box("border", 3, 3, 94, 94),
        text("brand", "한결소스", 8, 8, 84, 5, 10, align="center"),
        line("brand-line", 8, 15, 84),
        text("product", "고소한 참깨 드레싱소스", 8, 19, 84, 8, 15, align="center"),
        line("product-line", 8, 30, 84),
        {
            **text(
                "ingredients",
                "식품의 유형  소스(살균제품)\n원재료명  정제수, 양조간장, 설탕, 식초,\n참깨, 마늘, 양파, 고춧가루, 변성전분\n알레르기  대두, 밀, 참깨 함유",
                8,
                35,
                84,
                22,
                7,
            ),
            "type": "multiline_text",
        },
        box("allergen-border", 8, 59, 84, 6, 0.35),
        text("allergen", "알레르기 유발성분  대두 · 밀 · 참깨", 10, 60, 80, 4, 8, align="center"),
        text("date", f"제조일자  {date.today()}    내용량  250 g", 8, 68, 84, 5, 9),
        text("storage", "보관방법  직사광선을 피하고 서늘한 곳에 보관", 8, 74, 84, 5, 8),
        {
            **barcode("barcode", code),
            "y": 81,
            "height": 12,
        },
        text("code", code, 8, 94, 84, 3, 7, align="center"),
    ]


SAMPLES: list[tuple[str, str, list[dict[str, object]]]] = [
    ("01_방울토마토_농산물", "농축산물 유통", food_elements("방울토마토", "국내산", "750 g", str(date.today()), "보관방법  냉장보관", "TM250714001")),
    ("02_새송이버섯_농산물", "농축산물 유통", food_elements("새송이버섯", "국내산", "400 g", str(date.today()), "보관방법  냉장보관", "MS250714002")),
    ("03_신선란_농산물", "농축산물 유통", food_elements("신선란", "국내산", "10구", str(date.today()), "보관방법  냉장보관", "EG250714003")),
    ("04_양파_농산물", "농축산물 유통", food_elements("양파", "국내산", "1.5 kg", str(date.today()), "보관방법  서늘한 곳 보관", "ON250714004")),
    ("05_국내산삼겹살_축산물", "농축산물 유통", food_elements("국내산 삼겹살", "국내산", "500 g", str(date.today()), "보관방법  냉장보관", "PK250714005")),
    ("06_미니진주귀걸이_액세서리", "액세서리·잡화", accessory_elements("미니 진주 귀걸이", "SILVER", "12,000원", "AC-EAR-001")),
    ("07_플라워헤어핀_액세서리", "액세서리·잡화", accessory_elements("플라워 헤어핀", "BEIGE", "8,900원", "AC-HP-002")),
    ("08_하트키링_액세서리", "액세서리·잡화", accessory_elements("하트 키링", "PINK", "6,500원", "AC-KR-003")),
    ("09_슬림카드지갑_액세서리", "액세서리·잡화", accessory_elements("슬림 카드지갑", "BLACK", "19,800원", "AC-WL-004")),
    ("10_미니파우치_액세서리", "액세서리·잡화", accessory_elements("미니 파우치", "NAVY", "14,900원", "AC-PC-005")),
    ("11_고소한참깨드레싱소스_식품", "소스·가공식품", sauce_elements()),
]


def render_preview(payload: dict[str, object], target: Path) -> None:
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = ROOT
    app.template = payload
    app.elements = payload["elements"]
    app.preview_row = {}
    LabelDesignerApp.render_preview_image(app).save(target)


def coordinate_validation_fixture(payload: dict[str, object]) -> dict[str, object]:
    """Convert editor millimetres to the validator's explicit millimetre schema."""
    fixtures: list[dict[str, object]] = []
    for element in payload["elements"]:
        fixture = {
            "id": str(element["id"]),
            "units": "mm",
            "x_mm": float(element.get("x", 0)),
            "y_mm": float(element.get("y", 0)),
            "width_mm": float(element.get("width", 0)),
            # Horizontal lines render with a stroke width, not a box height.
            "height_mm": max(0.1, float(element.get("height", 0))),
        }
        fixtures.append(fixture)
    return {
        "label": {"width_mm": 100, "height_mm": 100, "dpi": 203},
        "objects": fixtures,
    }


def contact_sheet(preview_paths: list[Path]) -> None:
    tile_w, tile_h, padding, columns = 400, 400, 24, 2
    rows = (len(preview_paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_w + (columns + 1) * padding, rows * tile_h + (rows + 1) * padding), "#e9edf2")
    draw = ImageDraw.Draw(sheet)
    for index, preview in enumerate(preview_paths):
        image = Image.open(preview).convert("RGB")
        image.thumbnail((360, 330))
        x = padding + (index % columns) * (tile_w + padding) + (tile_w - image.width) // 2
        y = padding + (index // columns) * (tile_h + padding) + 38
        sheet.paste(image, (x, y))
        draw.text((padding + (index % columns) * (tile_w + padding) + 12, padding + (index // columns) * (tile_h + padding) + 10), preview.stem.replace("_", " "), fill="#17202a")
    sheet.save(ROOT / "당근_실제출력샘플_미리보기.png")


def main() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    previews: list[Path] = []
    summary = ["# 당근 실제 출력 샘플", "", "라벨 규격: 100 x 100 mm", "", "## 구성"]
    for name, category, elements in SAMPLES:
        payload: dict[str, object] = {
            "version": 1,
            "label": {"width_mm": 100, "height_mm": 100},
            "elements": elements,
        }
        template_path = TEMPLATE_DIR / f"{name}.gblabel"
        preview_path = PREVIEW_DIR / f"{name}.png"
        template_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        validation_path = VALIDATION_DIR / f"{name}.json"
        validation_path.write_text(
            json.dumps(coordinate_validation_fixture(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        render_preview(payload, preview_path)
        previews.append(preview_path)
        summary.append(f"- {category}: {template_path.name}")
    contact_sheet(previews)
    (ROOT / "샘플_출력안내.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"templates={len(SAMPLES)}")
    print(f"root={ROOT}")


if __name__ == "__main__":
    main()
