from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SALES_PAGE = PROJECT_ROOT / "sales-page"


def test_sales_page_loads_versioned_gsap_and_scroll_trigger() -> None:
    document = (SALES_PAGE / "index.html").read_text(encoding="utf-8")

    assert "gsap@3.12.5/dist/gsap.min.js" in document
    assert "gsap@3.12.5/dist/ScrollTrigger.min.js" in document
    assert 'src="animations.js?v=20260710"' in document


def test_motion_respects_accessibility_and_uses_section_level_reveals() -> None:
    script = (SALES_PAGE / "animations.js").read_text(encoding="utf-8")

    assert "prefers-reduced-motion" in script
    assert "gsap.registerPlugin(ScrollTrigger)" in script
    assert "hero-copy h1 span" in script
    assert "hero-proof > div" in script
    assert "once: true" in script
    assert "autoAlpha" in script
    assert " y:" in script
