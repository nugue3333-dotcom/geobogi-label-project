from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SALES_PAGE = PROJECT_ROOT / "sales-page"


class _PublicCopyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        for name, value in attrs:
            if name == "alt" and value:
                self.parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data.strip())


def _public_copy(path: Path) -> str:
    parser = _PublicCopyParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return " ".join(parser.parts)


def _public_sales_pages() -> list[Path]:
    pages = [SALES_PAGE / "index.html"]
    product_detail = SALES_PAGE / "product-detail.html"
    if product_detail.exists():
        pages.append(product_detail)
    return pages


def test_sales_pages_use_model_consultation_copy_until_package_approval() -> None:
    index_path = SALES_PAGE / "index.html"
    index_copy = _public_copy(index_path)
    index_document = index_path.read_text(encoding="utf-8")

    assert index_copy.count("상담 후 모델별 확인") >= 5
    assert 'href="naver-openmarket.html"' not in index_document
    for manufacturer in ("BIXOLON", "TSC", "Zebra", "SEWOO"):
        assert manufacturer in index_copy


def test_sales_pages_do_not_publish_unapproved_model_or_full_compatibility_claims() -> None:
    pages = _public_sales_pages()
    public_copy = " ".join(_public_copy(path) for path in pages)
    documents = " ".join(path.read_text(encoding="utf-8") for path in pages)
    unapproved_models = (
        "XD5-40d",
        "XD3-40d",
        "XT5-40",
        "XL5-40",
        "TE200",
        "DA220",
        "TTP-244 Pro",
        "TX 시리즈",
        "ZD421",
        "ZD621",
        "ZT231",
        "ZT400 시리즈",
        "LK-B24",
        "LK-B30",
        "SLK-TL200",
        "LK-P43",
        "DS2208",
        "DS2278",
        "DS4608",
        "QuickScan",
        "Gryphon",
        "Voyager",
        "Xenon",
        "Granit",
    )
    broad_claims = (
        "완전 호환",
        "모든 모델 지원",
        "전 모델 지원",
        "프로그램 지원 제조사별 프린터",
        "ZPL 호환 설정",
    )

    for forbidden in (*unapproved_models, *broad_claims):
        assert forbidden not in public_copy
    assert "<dt>지원 프린터</dt>" not in documents


def test_product_packages_keeps_public_models_unapproved_until_evidence_exists() -> None:
    packages = (PROJECT_ROOT / "docs" / "PRODUCT_PACKAGES.md").read_text(encoding="utf-8")

    assert packages.count("상담 후 모델별 확인") >= 4
    assert "No printer model is currently approved" in packages
    assert "APPROVED_SEWOO_ZPL_MODELS" in packages
