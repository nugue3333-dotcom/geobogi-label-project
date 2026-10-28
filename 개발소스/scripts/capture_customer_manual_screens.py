from __future__ import annotations

"""Capture the current source UI used by the customer PDF manuals."""

import shutil
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from tkinter import Misc, TclError

from PIL import Image, ImageGrab


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barcode_label_automation.config import DEFAULTS

from barcode_label_automation.label_designer_app import LabelDesignerApp
from barcode_label_automation.label_manager_app import LabelManagerApp
from barcode_label_automation.settings_app import SettingsApp, BRAND_LABELS
from barcode_label_automation.workflow_probe import run_workflow_probe


OUTPUT = ROOT / "outputs" / "ui-redesign-preview"
UI_SOURCES = tuple(ROOT / "barcode_label_automation" / name for name in (
    "config.py", "media_geometry.py", "printer_offsets.py", "templates.py", "compact_auto_layout.py",
    "label_designer_app.py", "label_manager_app.py", "settings_app.py", "ui_tokens.py", "ui_window.py", "ui_style.py", "brand_assets.py",
    "gs1_editor.py", "barcode_options_dialog.py", "barcode_engine.py", "barcode_catalog.py", "gs1.py", "designer_clipboard.py", "label_media.py", "tool_icons.py", "print_quantity.py", "designer_print_dispatch.py",
    "serial_editor.py", "job_profile.py", "template_output.py", "profile_dialogs.py", "value_rules.py", "value_rules_dialog.py", "value_jobs.py", "saved_output.py", "data_store.py", "barcode_layout.py", "hibc.py", "udi_editor.py", "workflow_probe.py", "barcode_editor_preview.py",
))
BRAND_SOURCES = tuple(ROOT / "assets" / "brand" / name for name in (
    "chaeumlab_logo_header_2x.png", "chaeumlab_designer_icon.png", "chaeumlab_manager_icon.png", "chaeumlab_settings_icon.png",
))


def _capture(app, target: Path, geometry: str = "1480x900+40+40") -> dict:
    app.geometry(geometry)
    app.update_idletasks()
    app.update()
    app.lift()
    app.attributes("-topmost", True)
    app.update()
    app.attributes("-topmost", False)
    time.sleep(0.35)
    app.update()
    x = app.winfo_rootx()
    y = app.winfo_rooty()
    width = app.winfo_width()
    height = app.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True).save(target)
    widgets = []
    def record(widget):
        if widget.winfo_ismapped():
            try:
                label = str(widget.cget("text"))
            except TclError:
                label = ""
            widgets.append({"type": widget.winfo_class(), "path": str(widget), "text": label, "bounds": [widget.winfo_rootx()-x, widget.winfo_rooty()-y, widget.winfo_width(), widget.winfo_height()]})
        for child in widget.winfo_children():
            record(child)
    record(app)
    regions = {
        name: [widget.winfo_rootx()-x, widget.winfo_rooty()-y, widget.winfo_width(), widget.winfo_height()]
        for name, widget in vars(app).items()
        if isinstance(widget, Misc) and widget.winfo_ismapped()
    }
    metadata = {"filename": target.name, "size": [width, height], "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "widgets": widgets, "regions": regions}
    app.destroy()
    return metadata


def _copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (*UI_SOURCES, *BRAND_SOURCES)}
    with tempfile.TemporaryDirectory(prefix="chaeumlab-manual-") as temp_dir:
        runtime = Path(temp_dir)
        for filename in ("config.ini", "barcode_db.xlsx", "print_queue.xlsx", "labels.xlsm"):
            _copy_if_exists(ROOT / filename, runtime / filename)
        from configparser import ConfigParser
        from barcode_label_automation.label_media import write_config_atomic
        runtime_config = runtime / "config.ini"
        if not runtime_config.exists():
            parser = ConfigParser(interpolation=None)
            parser.read_dict(DEFAULTS)
            write_config_atomic(runtime_config, parser)
        if (ROOT / "templates").exists():
            shutil.copytree(ROOT / "templates", runtime / "templates", dirs_exist_ok=True)

        sample_template = runtime / "templates" / "sample_excel_product.cllabel"
        if not sample_template.exists():
            raise FileNotFoundError("최신 예제 도안이 없습니다: " + str(sample_template))
        template_media = json.loads(sample_template.read_text(encoding="utf-8"))["label"]
        parser = ConfigParser(interpolation=None)
        parser.read(runtime_config, encoding="utf-8-sig")
        parser.set("label", "width_mm", str(template_media["width_mm"]))
        parser.set("label", "height_mm", str(template_media["height_mm"]))
        write_config_atomic(runtime_config, parser)
        screenshots = []
        designer = LabelDesignerApp(runtime, initial_template_path=sample_template)
        designer.connect_data_source_path(runtime / "barcode_db.xlsx")
        designer.save_template()
        screenshots.append(_capture(designer, OUTPUT / "label-designer-final.png"))
        designer_data = LabelDesignerApp(runtime, initial_template_path=sample_template)
        designer_data.connect_data_source_path(runtime / "barcode_db.xlsx")
        designer_data.save_template()
        screenshots.append(_capture(designer_data, OUTPUT / "label-designer-data.png"))
        screenshots.append(_capture(LabelManagerApp(runtime, template_path=sample_template), OUTPUT / "label-manager-final.png"))
        # This is the printer renderer's real 40x20 output bitmap, not a mock UI.
        from barcode_label_automation.excel_reader import LabelRow
        from barcode_label_automation.templates import render_auto_page
        compact_row = LabelRow(
            '00001', 'SENSOR BRACKET', '001234567890', 'LOT250531', 100, 1,
            source_fields=(('상품명', 'SENSOR BRACKET'), ('상품코드', '00001'), ('LOT', 'LOT250531'), ('수량', '100')),
        )
        compact_image = render_auto_page(compact_row, 40, 20, 203, language='slcs')
        compact_path = OUTPUT / 'manager-compact-preview.png'
        compact_image.save(compact_path)
        screenshots.append({
            'filename': compact_path.name, 'size': list(compact_image.size),
            'sha256': hashlib.sha256(compact_path.read_bytes()).hexdigest(),
            'capture_kind': 'source_renderer_output',
        })
        screenshots.append(_capture(SettingsApp(runtime / "config.ini"), OUTPUT / "printer-settings.png"))
        offsets = SettingsApp(runtime / "config.ini")
        offsets.brand_var.set(BRAND_LABELS['bixolon'])
        offsets._sync_media_handling_state()
        offsets.media_handling_var.set('커터')
        offsets.printer_name_var.set('BIXOLON 프린터 (설치 이름 예시)')
        offsets.gap_offset_var.set('-1')
        offsets.feed_offset_var.set('1')
        offsets._advanced_offset_container.grid(row=10, column=0, columnspan=4, sticky='ew')
        screenshots.append(_capture(offsets, OUTPUT / 'printer-offsets-bixolon.png'))

    if run_workflow_probe(OUTPUT) != 0:
        raise RuntimeError("실제 바코드 속성 UI 검증 또는 GS1/UDI 화면 캡처에 실패했습니다.")
    for filename in ("frozen-udi-content.png", "frozen-udi-size.png"):
        path = OUTPUT / filename
        if not path.is_file():
            raise FileNotFoundError("실제 UDI 편집창 캡처가 없습니다: " + str(path))
        with Image.open(path) as image:
            size = list(image.size)
        screenshots.append({
            "filename": filename,
            "size": size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })

    if any(hashlib.sha256(path.read_bytes()).hexdigest() != expected for path, expected in source_hashes.items()):
        raise RuntimeError("화면 캡처 중 프로그램이나 브랜드 파일이 바뀌었습니다. 변경 완료 후 다시 캡처하세요.")
    metadata = {
        "captured_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "capture_kind": "actual_source_gui",
        "ui_sources": {path.relative_to(ROOT).as_posix(): source_hashes[path] for path in UI_SOURCES},
        "brand_sources": {path.relative_to(ROOT).as_posix(): source_hashes[path] for path in BRAND_SOURCES},
        "screenshots": screenshots,
    }
    (OUTPUT / "customer-manual-capture.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print("CUSTOMER_MANUAL_SCREENS_CAPTURED")
    for filename in ("label-designer-final.png", "label-designer-data.png", "label-manager-final.png", "printer-settings.png"):
        print(OUTPUT / filename)


if __name__ == "__main__":
    main()
