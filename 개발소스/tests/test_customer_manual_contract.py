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
    assert "run_workflow_probe(OUTPUT)" in source


@pytest.mark.parametrize("path", verifier.FORBIDDEN_MENU_PATHS)
def test_manual_verifier_rejects_obsolete_menu_paths(path):
    assert verifier.text_contract_errors(path, ()) == ["obsolete menu path: " + path]


def test_release_version_and_new_help_file_names():
    assert verifier.MANUAL_VERSION == "2026.10.20.01"
    for name in ("build_customer_manuals.py", "create_customer_manual.py"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert verifier.MANUAL_VERSION in source
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
    for name in ("label-designer-final.png", "label-designer-data.png", "label-manager-final.png", "manager-compact-preview.png", "printer-settings.png", "frozen-udi-content.png", "frozen-udi-size.png"):
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


def test_manual_builders_document_current_usability_contract():
    for name in ("build_customer_manuals.py", "create_customer_manual.py", "build_quick_customer_guide.py"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert not verifier.text_contract_errors(source, ())
        assert verifier.MANUAL_VERSION in source
    designer = verifier.EXPECTED["채움랩_라벨디자이너_고객용_매뉴얼.pdf"][2]
    assert all(phrase in designer for phrase in ("Ctrl+C", "Ctrl+V", "Ctrl+D", "공통 규격", "용지 설정"))
    manager = verifier.EXPECTED["채움랩_라벨출력관리_고객용_매뉴얼.pdf"][2]
    assert all(phrase in manager for phrase in ("상한 없이", "양의 정수", "이미 프린터"))


def test_compact_automatic_layout_has_current_manual_and_capture_contract():
    required = ("40×20mm", "최소 5pt", "두 열")
    manager = verifier.EXPECTED["채움랩_라벨출력관리_고객용_매뉴얼.pdf"][2]
    assert all(phrase in manager for phrase in required)
    source = (ROOT/'scripts/build_customer_manuals.py').read_text(encoding='utf-8')
    assert verifier.text_contract_errors(source, required) == []
    assert "barcode_label_automation/compact_auto_layout.py" in verifier.REQUIRED_UI_SOURCES
    assert "manager-compact-preview.png" in source


def test_manual_capture_tracks_usability_modules():
    source = (ROOT / "scripts/capture_customer_manual_screens.py").read_text(encoding="utf-8")
    for name in ("designer_clipboard.py", "label_media.py", "tool_icons.py", "print_quantity.py", "designer_print_dispatch.py"):
        assert f'"{name}"' in source
        assert f"barcode_label_automation/{name}" in verifier.REQUIRED_UI_SOURCES


def test_manual_capture_tracks_barcode_layout_calculation():
    source = (ROOT / "scripts/capture_customer_manual_screens.py").read_text(encoding="utf-8")
    assert '"barcode_layout.py"' in source
    assert "barcode_label_automation/barcode_layout.py" in verifier.REQUIRED_UI_SOURCES


def test_manual_builders_document_barcode_size_first_without_automatic_migration():
    required = ("2D 크기·문자 배치", "바코드 크기 우선", "기존 배치", "실제 크기 확인")
    for name in ("build_customer_manuals.py", "create_customer_manual.py", "build_quick_customer_guide.py"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert verifier.text_contract_errors(source, required) == []
    for name in ("README_먼저읽기.txt", "설치_및_사용_메뉴얼.txt", "사용안내.txt"):
        source = (ROOT / name).read_text(encoding="utf-8-sig")
        assert verifier.text_contract_errors(source, required) == []
    required_in_pdf = verifier.EXPECTED["채움랩_라벨디자이너_고객용_매뉴얼.pdf"][2]
    assert all(phrase in required_in_pdf for phrase in required)


def test_detailed_manuals_distinguish_target_size_quiet_zone_and_group_bounds():
    required = ("바코드 가로(mm)", "바코드 세로(mm)", "필수 여백", "정수 모듈 도트", "전체 가로·세로", "자동 맞춤", "지정 크기")
    for name in ("build_customer_manuals.py", "create_customer_manual.py"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert verifier.text_contract_errors(source, required) == []


def test_migration_guide_uses_current_extensions_and_menu():
    text = (ROOT / "docs/BARTENDER_MIGRATION.md").read_text(encoding="utf-8")
    assert ".cllabel" in text and ".clproject" in text
    assert "파일 → 이동 프로젝트 내보내기" in text
    assert "편집·이동 →" not in text
    assert "손실 없는 자동 변환·완전 호환을 약속하지 않습니다" in text


def test_acceptance_and_commercial_forms_do_not_invent_approval():
    device = (ROOT / "docs/DEVICE_ACCEPTANCE_RECORD.md").read_text(encoding="utf-8")
    commercial = (ROOT / "docs/PAID_SUPPORT_TERMS_DRAFT.md").read_text(encoding="utf-8")
    migration = (ROOT / "docs/TEMPLATE_MIGRATION_CHECKLIST.md").read_text(encoding="utf-8")
    assert "현재 승인 모델은 없습니다" in device
    assert "물리 출력·스캔 검증: 미실행" in migration
    assert "가격·지원·환불·라이선스 조건 미확정" in commercial
    assert "구매 안내나 약정으로 사용하지 않습니다" in commercial


def test_manual_capture_tracks_hibc_and_udi_modules():
    source = (ROOT / "scripts/capture_customer_manual_screens.py").read_text(encoding="utf-8")
    for name in ("hibc.py", "udi_editor.py"):
        assert f'"{name}"' in source
        assert f"barcode_label_automation/{name}" in verifier.REQUIRED_UI_SOURCES


def test_ai_udi_guides_document_input_recovery_and_print_boundary():
    required = ("시험용 완성 예제로 시작", "전체 GS1 데이터 가져오기", "의료기기 UDI", "완성 코드 가져오기", "현재 라벨에 맞추기", "GS1 데이터로 설정", "기타 데이터 옵션", "Esc", "전체 데이터 검증", "규제 승인", "손잡이")
    for name in ("build_customer_manuals.py", "create_customer_manual.py", "build_quick_customer_guide.py"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert verifier.text_contract_errors(source, required) == []
        assert "내용 / 크기·표시문자 / 출력 확인 탭" not in source
    for name in ("README_먼저읽기.txt", "설치_및_사용_메뉴얼.txt", "사용안내.txt"):
        source = (ROOT / name).read_text(encoding="utf-8-sig")
        assert verifier.text_contract_errors(source, required) == []
        assert "내용 / 크기·표시문자 / 출력 확인 탭" not in source


def test_guides_do_not_require_manual_add_before_new_ai_validation():
    obsolete = ("새 AI는 값을 입력하고 추가합니다", "새 AI는 값을 입력한 뒤 추가합니다", "새 AI는 값 입력 후 추가")
    for name in ("scripts/build_customer_manuals.py", "scripts/create_customer_manual.py", "scripts/build_quick_customer_guide.py", "README_먼저읽기.txt", "설치_및_사용_메뉴얼.txt", "사용안내.txt"):
        source = (ROOT / name).read_text(encoding="utf-8-sig")
        assert all(phrase not in source for phrase in obsolete)
