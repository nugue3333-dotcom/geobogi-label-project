from __future__ import annotations

"""Verify PDF structure, readable text and synchronized customer copies."""

import hashlib
from pathlib import Path

from docx import Document
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "고객용_매뉴얼"
COPIES = (
    ROOT / "고객용_실행폴더" / "고객용_매뉴얼",
    ROOT.parent / "고객용_매뉴얼",
)

EXPECTED = {
    "채움LAB_라벨디자이너_고객용_매뉴얼.pdf": (10, 9, ("예제로 시작", "상품 엑셀 연결", "인식 값 검토", ".gbproject", ".btw", "프린터 전송 완료")),
    "채움LAB_라벨출력관리_고객용_매뉴얼.pdf": (7, 6, ("중복 선택 창", "체크가 0개일 때", "인쇄가 차단됩니다", "지원 패키지 생성")),
    "채움LAB_프린터설정_고객용_매뉴얼.pdf": (7, 6, ("180도 회전", "연결 확인", "BIXOLON/빅솔론")),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors: list[str] = []
    for filename, (expected_pages, expected_bookmarks, phrases) in EXPECTED.items():
        source = SOURCE / filename
        if not source.exists():
            errors.append(f"missing: {source}")
            continue
        reader = PdfReader(str(source))
        if len(reader.pages) != expected_pages:
            errors.append(f"{filename}: pages={len(reader.pages)}, expected={expected_pages}")
        if len(reader.outline) < expected_bookmarks:
            errors.append(f"{filename}: bookmarks={len(reader.outline)}, expected>={expected_bookmarks}")
        texts = [(page.extract_text() or "").strip() for page in reader.pages]
        for index, text in enumerate(texts, 1):
            if len(text) < 80:
                errors.append(f"{filename}: page {index} is blank or unreadable")
            if "\ufffd" in text:
                errors.append(f"{filename}: page {index} contains replacement glyphs")
        full_text = "\n".join(texts)
        for phrase in phrases:
            if phrase not in full_text:
                errors.append(f"{filename}: missing required phrase: {phrase}")
        source_hash = digest(source)
        for copy_dir in COPIES:
            copied = copy_dir / filename
            if not copied.exists() or digest(copied) != source_hash:
                errors.append(f"{filename}: copy mismatch: {copied}")
        print(f"OK {filename}: pages={len(reader.pages)}, bookmarks={len(reader.outline)}, sha256={source_hash[:12]}")

    docx_name = "라벨출력패키지_고객용_매뉴얼.docx"
    docx_source = ROOT / "고객용_실행폴더" / docx_name
    if not docx_source.exists():
        errors.append(f"missing: {docx_source}")
    else:
        document = Document(docx_source)
        docx_text = "\n".join(
            [paragraph.text for paragraph in document.paragraphs]
            + [cell.text for table in document.tables for row in table.rows for cell in row.cells]
        )
        for phrase in ("예제로 시작", "인식 값 검토", ".gbproject", ".btw", "선택 항목이 없으면", "실제 출력 확인"):
            if phrase not in docx_text:
                errors.append(f"{docx_name}: missing required phrase: {phrase}")
        source_hash = digest(docx_source)
        for copy in (ROOT / docx_name, ROOT.parent / docx_name):
            if not copy.exists() or digest(copy) != source_hash:
                errors.append(f"{docx_name}: copy mismatch: {copy}")
        print(f"OK {docx_name}: sha256={source_hash[:12]}")

    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print("CUSTOMER_MANUALS_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
