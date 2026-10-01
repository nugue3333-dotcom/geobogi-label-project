from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_top_brand_labels_use_chaeumlab() -> None:
    files = [
        PROJECT_ROOT / "barcode_label_automation" / "label_designer_app.py",
        PROJECT_ROOT / "barcode_label_automation" / "label_manager_app.py",
        PROJECT_ROOT / "barcode_label_automation" / "settings_app.py",
    ]

    for path in files:
        source = path.read_text(encoding="utf-8")
        assert "load_header_logo" in source
        assert "apply_window_icon" in source
        assert "HeaderLogo.TLabel" in source
        old_brand = "거복이" + "의꿈"
        assert f'text="{old_brand}", style="Brand.TLabel"' not in source


def test_brand_logo_assets_are_present_and_packaged() -> None:
    assert (PROJECT_ROOT / "assets" / "brand" / "chaeumlab_logo_header.png").is_file()
    assert (PROJECT_ROOT / "assets" / "brand" / "chaeumlab_logo_compact.png").is_file()
    assert (PROJECT_ROOT / "assets" / "brand" / "chaeumlab_app_icon.ico").is_file()
    assert (PROJECT_ROOT / "assets" / "brand" / "chaeumlab_app_icon_white.ico").is_file()
    assert (PROJECT_ROOT / "assets" / "brand" / "chaeumlab_label_file_icon_white.ico").is_file()
    assert (PROJECT_ROOT / "assets" / "brand" / "chaeumlab_mark.png").is_file()

    for spec_name in (
        "customer_preflight.spec",
        "label_designer.spec",
        "label_job_runner.spec",
        "label_manager.spec",
        "print_labels.spec",
        "printer_settings.spec",
    ):
        spec = (PROJECT_ROOT / spec_name).read_text(encoding="utf-8")
        assert "assets/brand" in spec
        assert "icon='assets/brand/chaeumlab_app_icon.ico'" in spec


def test_brand_icons_are_high_resolution_symbol_assets() -> None:
    assets = PROJECT_ROOT / "assets" / "brand"
    for name in ("chaeumlab_mark.png", "chaeumlab_app_icon.png", "chaeumlab_app_icon_white.png"):
        with Image.open(assets / name) as image:
            assert image.width >= 1024
            assert image.height >= 1024

    with Image.open(assets / "chaeumlab_app_icon_white.ico") as icon:
        assert icon.width >= 256
        assert icon.height >= 256

    with Image.open(assets / "chaeumlab_label_file_icon_white.ico") as icon:
        assert {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}.issubset(icon.ico.sizes())


def test_program_icon_is_readable_in_explorer_sizes():
    icon_path = PROJECT_ROOT / "assets" / "brand" / "chaeumlab_app_icon.png"
    with Image.open(icon_path) as source:
        image = source.convert("RGBA")
        pixels = list(image.getdata())

    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((512, 512)) == (247, 250, 244, 255)
    assert any(red < 80 and green < 80 and blue < 80 and alpha > 0 for red, green, blue, alpha in pixels)
    assert any(green > red + 30 and green > blue + 20 and alpha > 0 for red, green, blue, alpha in pixels)

    with Image.open(PROJECT_ROOT / "assets" / "brand" / "chaeumlab_app_icon.ico") as icon:
        assert {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}.issubset(icon.ico.sizes())
        for size in (16, 24, 32):
            preview = icon.ico.getimage((size, size)).convert("RGBA")
            preview_pixels = list(preview.getdata())
            # ICO renderers may flatten transparent corners to white. The
            # release requirement is a light Explorer tile, never a dark one.
            corner = preview.getpixel((0, 0))
            assert corner[3] < 20 or min(corner[:3]) >= 220
            assert any(red < 90 and green < 90 and blue < 90 and alpha > 0 for red, green, blue, alpha in preview_pixels)
            assert any(green > red + 20 and green > blue + 15 and alpha > 0 for red, green, blue, alpha in preview_pixels)


def test_saved_label_icon_uses_legible_document_shape_at_small_sizes() -> None:
    path = PROJECT_ROOT / "assets" / "brand" / "chaeumlab_label_file_icon_white.ico"
    with Image.open(path) as icon:
        for size in (16, 24, 32):
            preview = icon.ico.getimage((size, size)).convert("RGBA")
            pixels = list(preview.getdata())
            assert preview.getpixel((0, 0))[3] < 32
            assert any(red < 100 and green < 115 and blue < 120 and alpha > 0 for red, green, blue, alpha in pixels)
            assert any(green > red + 25 and green > blue + 15 and alpha > 0 for red, green, blue, alpha in pixels)


def test_saved_label_file_association_uses_white_file_icon() -> None:
    text = (PROJECT_ROOT / "register_label_filetype.ps1").read_text(encoding="utf-8")

    assert "chaeumlab_label_file_icon_white.ico" in text
    assert 'Set-Item -Path $iconKey -Value "`"$fileIconPath`",0"' in text
    assert 'GetEnvironmentVariable("SystemRoot", "Machine")' in text
    assert '$iconRefresh = Join-Path $systemRoot' in text
    assert 'Write-Verbose "Explorer icon cache refresh was skipped:' in text


def test_window_titles_use_chaeumlab_brand() -> None:
    designer = (PROJECT_ROOT / "barcode_label_automation" / "label_designer_app.py").read_text(encoding="utf-8")
    manager = (PROJECT_ROOT / "barcode_label_automation" / "label_manager_app.py").read_text(encoding="utf-8")
    settings = (PROJECT_ROOT / "barcode_label_automation" / "settings_app.py").read_text(encoding="utf-8")

    assert 'return f"채움랩 라벨 디자이너 - {name}{marker}"' in designer
    assert 'return "채움랩 라벨 디자이너"' in designer
    assert 'self.title("채움랩 라벨 출력 관리")' in manager
    assert 'self._base_title = "채움랩 프린터 설정"' in settings
    assert 'self.title(f"{self._base_title}{\' *\' if dirty else \'\'}")' in settings


def test_customer_visible_helper_files_use_chaeumlab_brand() -> None:
    files = [
        PROJECT_ROOT / "register_label_filetype.ps1",
        PROJECT_ROOT / "scripts" / "install_tesseract_ocr.ps1",
        PROJECT_ROOT / "tools" / "ocr" / "README.txt",
        PROJECT_ROOT / "고객용_실행폴더" / "register_label_filetype.ps1",
        PROJECT_ROOT / "고객용_실행폴더" / "scripts" / "install_tesseract_ocr.ps1",
        PROJECT_ROOT / "고객용_실행폴더" / "tools" / "ocr" / "README.txt",
    ]

    for path in files:
        text = path.read_text(encoding="utf-8-sig")
        text_without_legacy_cleanup = text.replace("GeobogiDream.LabelFile", "")
        assert "채움랩" in text
        assert "Geobogi Dream" not in text
        assert "GeobogiDream" not in text_without_legacy_cleanup
        assert "Geobogi label" not in text
