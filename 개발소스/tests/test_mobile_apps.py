from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_existing_android_quick_print_app_remains_lan_only():
    manifest = read("mobile-android/app/src/main/AndroidManifest.xml")
    sender = read("mobile-android/app/src/main/java/com/geoboki/labelprinter/PrinterSender.java")

    assert "android.permission.INTERNET" in manifest
    assert "BLUETOOTH" not in manifest
    assert "Bluetooth" not in sender
    assert "Socket" in sender


def test_ios_project_is_chaeum_branded_and_lan_only():
    pbxproj = read("mobile-ios/GeobogiLabelMobile.xcodeproj/project.pbxproj")
    client = read("mobile-ios/GeobogiLabelMobile/PrinterLANClient.swift")
    readme = read("mobile-ios/README.md")

    assert 'INFOPLIST_KEY_CFBundleDisplayName = "채움LAB 모바일"' in pbxproj
    assert "INFOPLIST_KEY_NSLocalNetworkUsageDescription" in pbxproj
    assert "kr.chaeumlab.labelmobile" in pbxproj
    assert "NWConnection" in client
    assert "Bluetooth" not in client
    assert "USB" not in client
    assert "무선 LAN" in readme


def test_ios_supports_template_csv_and_mobile_workflow():
    models = read("mobile-ios/GeobogiLabelMobile/MobileModels.swift")
    view = read("mobile-ios/GeobogiLabelMobile/AppView.swift")
    documents = read("mobile-ios/GeobogiLabelMobile/DocumentServices.swift")

    assert "case text, barcode, qr, box, line" in models
    assert "case degree0 = 0, degree90 = 90, degree180 = 180, degree270 = 270" in models
    for pc_field in ("type, text", "field, rotation", "x, y, width, height"):
        assert pc_field in models
    assert "CSVDatabaseService" in documents
    assert "모든 열을 검색" in view
    assert "case template, data, print, settings" in view


def test_ios_renderer_matches_safe_brand_contract():
    models = read("mobile-ios/GeobogiLabelMobile/MobileModels.swift")
    renderer = read("mobile-ios/GeobogiLabelMobile/LabelCommandRenderer.swift")
    view = read("mobile-ios/GeobogiLabelMobile/AppView.swift")

    assert "case tsc, bixolon, zebra, sewoo" in models
    assert "case dpi203 = 203, dpi300 = 300, dpi600 = 600" in models
    assert "SET PEEL ON" in renderer
    assert "^MMP" in renderer
    assert "BLINE " in renderer
    assert "GAP 0,0" in renderer
    assert "case .bixolon: return [.tearOff, .cutter]" in view
    assert "case .sewoo: return [.tearOff]" in view


def test_ios_retry_and_send_wording_are_explicit():
    models = read("mobile-ios/GeobogiLabelMobile/MobileModels.swift")
    store = read("mobile-ios/GeobogiLabelMobile/AppStore.swift")
    view = read("mobile-ios/GeobogiLabelMobile/AppView.swift")

    assert 'case .sent: return "명령 전송 완료"' in models
    assert "retryLastPrint" in store
    assert "canRetry" in store
    assert "실제 인쇄 완료와는 구분" in view
