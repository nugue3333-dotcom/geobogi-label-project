from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "mobile-android-designer"


def read(relative: str) -> str:
    return (APP / relative).read_text(encoding="utf-8")


def test_designer_project_is_branded_android_lan_app():
    assert (APP / "settings.gradle").exists()
    assert (APP / "app/build.gradle").exists()
    build_gradle = read("app/build.gradle")
    manifest = read("app/src/main/AndroidManifest.xml")
    strings = read("app/src/main/res/values/strings.xml")

    assert 'applicationId "kr.chaeumlab.mobilelabel"' in build_gradle
    assert 'namespace "com.geoboki.labeldesigner"' in build_gradle
    assert 'versionCode 4' in build_gradle
    assert "채움LAB 모바일 라벨" in strings
    assert "android.permission.INTERNET" in manifest
    assert "ACCESS_WIFI_STATE" in manifest
    assert "BLUETOOTH" not in manifest


def test_designer_keeps_one_signing_identity_for_future_updates():
    build_script = read("build_apk_manual.ps1")

    assert 'Join-Path $AppRoot "signing"' in build_script
    assert 'chaeumlab-sideload.keystore' in build_script
    assert 'if (-not (Test-Path $DebugKeystore))' in build_script
    assert 'Join-Path $BuildDir "debug.keystore"' not in build_script


def test_designer_supports_pc_template_objects_and_rotation():
    canvas = read("app/src/main/java/com/geoboki/labeldesigner/DesignerCanvasView.java")
    model = read("app/src/main/java/com/geoboki/labeldesigner/LabelElement.java")
    json_codec = read("app/src/main/java/com/geoboki/labeldesigner/TemplateJson.java")
    main = read("app/src/main/java/com/geoboki/labeldesigner/MainActivity.java")

    for object_type in ("text", "barcode", "qr", "box", "line"):
        assert f'"{object_type}"' in model
    for action in ("addText", "addBarcode", "addQr", "addBox", "addLine"):
        assert action in canvas
    assert "ACTION_MOVE" in canvas
    assert "ROTATION_VALUES" in main
    for field in ('"type"', '"text"', '"field"', '"x"', '"y"', '"width"', '"height"', '"rotation"'):
        assert field in json_codec
    assert 'actionButton("파일"' in main
    assert 'actionButton("DB / CSV"' in main
    assert 'actionButton("프린터 설정"' in main


def test_designer_csv_search_and_quantity_contract():
    csv = read("app/src/main/java/com/geoboki/labeldesigner/CsvTable.java")
    main = read("app/src/main/java/com/geoboki/labeldesigner/MainActivity.java")

    assert "String.valueOf(value)" not in csv
    assert "search(String query)" in csv
    assert "headers" in csv and "rows" in csv
    assert "전체 열 검색 및 행 선택" in main
    assert "출력 매수 (1~100)" in main
    assert "CSV 행 선택" in main


def test_designer_renderer_enforces_brand_encoding_and_handling():
    renderer = read("app/src/main/java/com/geoboki/labeldesigner/LabelCommandRenderer.java")
    check = read("app/src/main/java/com/geoboki/labeldesigner/RendererContractCheck.java")
    sender = read("app/src/main/java/com/geoboki/labeldesigner/PrinterSender.java")

    assert "renderTspl" in renderer
    assert "renderZpl" in renderer
    assert "renderSlcs" in renderer
    assert '"CP949"' in renderer
    assert '"UTF-8"' in renderer
    assert 'c.append("B1")' in renderer
    assert 'c.append("B2")' in renderer
    assert 'replace("\\n", "\\r\\n")' in renderer
    assert '+ "P" + settings.printQty + "\\r"' in renderer
    assert '"BARCODE "' in check and '"QRCODE "' in check
    assert '"^BC"' in check and '"^BQ"' in check
    assert 'template.addBarcode("001234567890")' in check
    assert 'template.addQr("QR-001")' in check
    assert "BIXOLON peeler blocked" in check
    assert "SEWOO cutter blocked" in check
    assert "SEWOO peeler blocked" in check
    assert "SEWOO unverified protocol blocked" in check
    assert "expectZebraRotatedQrFailure" in check
    for dpi in ("203", "300", "600"):
        assert dpi in check
    assert "Socket" in sender
    assert "Bluetooth" not in sender


def test_pc_qr_template_type_is_preserved_on_android():
    json_codec = read("app/src/main/java/com/geoboki/labeldesigner/TemplateJson.java")

    assert 'item.optString("barcode_type")' in json_codec
    assert 'value.put("barcode_type", "code128")' in json_codec
    assert 'value.put("barcode_type", "qr")' in json_codec
    assert '"barcode".equals(type)' in json_codec
    assert '"qr".equals(normalizedBarcodeType)' in json_codec


def test_unresolved_barcode_database_fields_are_blocked_before_send():
    renderer = read("app/src/main/java/com/geoboki/labeldesigner/LabelCommandRenderer.java")
    check = read("app/src/main/java/com/geoboki/labeldesigner/RendererContractCheck.java")

    assert "rejectUnresolvedField" in renderer
    assert 'value.contains("{{")' in renderer
    assert "expectUnresolvedFieldFailure" in check


def test_designer_failure_is_retryable_and_success_wording_is_honest():
    main = read("app/src/main/java/com/geoboki/labeldesigner/MainActivity.java")

    assert "setBusy(false" in main
    assert "명령 전송 완료" in main
    assert "실제 라벨 배출 상태를 확인하세요" in main
    assert "다시 시도할 수 있습니다" in main


def test_readme_states_current_scope_and_physical_limit():
    readme = read("README.md")

    for term in ("빈 템플릿", "QR", "CSV", "전체 열 검색", "203, 300, 600", "명령 전송 완료"):
        assert term in readme
    assert "실제 출력 성공" in readme
