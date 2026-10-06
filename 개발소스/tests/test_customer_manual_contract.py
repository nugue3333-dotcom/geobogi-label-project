from pathlib import Path
import importlib.util

import pytest


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("manual_verifier", ROOT / "scripts" / "verify_customer_manuals.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def test_current_manual_filenames_and_extension_contract():
    assert len(verifier.EXPECTED) == 3
    assert all(name.startswith("채움랩_") for name in verifier.EXPECTED)
    designer = verifier.EXPECTED["채움랩_라벨디자이너_고객용_매뉴얼.pdf"][2]
    assert all(extension in designer for extension in (".cllabel", ".clproject", ".gblabel", ".gbproject"))


@pytest.mark.parametrize("policy", verifier.FORBIDDEN_POLICIES)
def test_manual_verifier_rejects_obsolete_no_selection_policy(policy):
    assert verifier.text_contract_errors(policy, ()) == ["obsolete print policy: " + policy]


def test_manual_verifier_requires_all_target_temporary_queue_and_cancel():
    required = ("전체 항목", "임시 큐", "취소하면 명령을 전송하지 않습니다")
    assert verifier.text_contract_errors("전체 항목 / 임시 큐 / 취소하면 명령을 전송하지 않습니다", required) == []
    assert verifier.text_contract_errors("선택한 항목", required) == ["missing required phrase: " + p for p in required]


def test_pdf_text_contract_tolerates_line_wrapping_without_hiding_old_policy():
    assert verifier.text_contract_errors("취소하면 명령을 전송하지\n않습니다", ("취소하면 명령을 전송하지 않습니다",)) == []
    old_policy = "선택된 행이 없으면 인쇄를 시작하지 않습니다"
    assert verifier.text_contract_errors(old_policy.replace("시작하지", "시작하\n지"), ()) == ["obsolete print policy: " + old_policy]


def test_manual_capture_uses_current_example_and_actual_source_screen():
    source = (ROOT / "scripts" / "capture_customer_manual_screens.py").read_text(encoding="utf-8")
    assert "sample_excel_product.cllabel" in source
    assert '"capture_kind": "actual_source_gui"' in source
    assert "ImageGrab.grab" in source
    assert "design-review-20261001" not in source
    assert '"ui_style.py"' in source
    assert '"brand_sources"' in source


@pytest.mark.parametrize("path", verifier.FORBIDDEN_MENU_PATHS)
def test_manual_verifier_rejects_obsolete_menu_paths(path):
    assert verifier.text_contract_errors(path, ()) == ["obsolete menu path: " + path]


def test_release_version_and_new_help_file_names():
    assert verifier.MANUAL_VERSION == "2026.10.06.01"
    for name in ("build_customer_manuals.py", "create_customer_manual.py"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "2026.10.06.01" in source
        assert "capture_contract_errors(ROOT)" in source


def test_capture_provenance_requires_style_and_all_current_screens(tmp_path):
    import json
    import hashlib

    output = tmp_path / "outputs/ui-redesign-preview"
    output.mkdir(parents=True)
    metadata = {"capture_kind": "actual_source_gui", "ui_sources": {}, "brand_sources": {}, "screenshots": []}
    for name in (*verifier.REQUIRED_UI_SOURCES, *verifier.REQUIRED_BRAND_SOURCES):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
        group = "ui_sources" if name in verifier.REQUIRED_UI_SOURCES else "brand_sources"
        metadata[group][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("label-designer-final.png", "label-designer-data.png", "label-manager-final.png", "printer-settings.png"):
        path = output / name
        path.write_bytes(name.encode("utf-8"))
        metadata["screenshots"].append({"filename": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = output / "customer-manual-capture.json"
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    assert verifier.capture_contract_errors(tmp_path) == []
    (tmp_path / "barcode_label_automation/ui_style.py").write_text("changed", encoding="utf-8")
    assert verifier.capture_contract_errors(tmp_path) == ["capture source changed: barcode_label_automation/ui_style.py"]
    metadata["ui_sources"].pop("barcode_label_automation/ui_style.py")
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    assert "capture provenance missing: barcode_label_automation/ui_style.py" in verifier.capture_contract_errors(tmp_path)


@pytest.mark.parametrize("filename", ("README_먼저읽기.txt", "설치_및_사용_메뉴얼.txt", "사용안내.txt"))
def test_text_guides_match_current_menu_and_print_contract(filename):
    text = (ROOT / filename).read_text(encoding="utf-8-sig")
    required = (".cllabel", ".clproject", ".gblabel", ".gbproject", "전체 항목", "임시 큐", "도움말 > 지원 패키지 생성", verifier.MANUAL_VERSION)
    assert verifier.text_contract_errors(text, required) == []


def test_word_manual_preserves_table_rows_across_page_breaks():
    from zipfile import ZipFile
    from xml.etree import ElementTree

    with ZipFile(ROOT / "채움랩_라벨출력패키지_고객용_매뉴얼.docx") as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    rows = document.findall(".//w:tbl/w:tr", namespace)
    assert rows
    assert all(row.find("w:trPr/w:cantSplit", namespace) is not None for row in rows)
