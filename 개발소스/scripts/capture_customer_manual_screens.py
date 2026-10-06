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

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barcode_label_automation.label_designer_app import LabelDesignerApp
from barcode_label_automation.label_manager_app import LabelManagerApp
from barcode_label_automation.settings_app import SettingsApp


OUTPUT = ROOT / "outputs" / "ui-redesign-preview"
UI_SOURCES = tuple(ROOT / "barcode_label_automation" / name for name in (
    "label_designer_app.py", "label_manager_app.py", "settings_app.py", "ui_tokens.py", "ui_window.py", "ui_style.py", "brand_assets.py",
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
        if (ROOT / "templates").exists():
            shutil.copytree(ROOT / "templates", runtime / "templates", dirs_exist_ok=True)

        sample_template = runtime / "templates" / "sample_excel_product.cllabel"
        if not sample_template.exists():
            raise FileNotFoundError("최신 예제 도안이 없습니다: " + str(sample_template))
        screenshots = []
        designer = LabelDesignerApp(runtime, initial_template_path=sample_template)
        screenshots.append(_capture(designer, OUTPUT / "label-designer-final.png"))
        designer_data = LabelDesignerApp(runtime, initial_template_path=sample_template)
        designer_data.connect_data_source_path(runtime / "barcode_db.xlsx")
        screenshots.append(_capture(designer_data, OUTPUT / "label-designer-data.png"))
        screenshots.append(_capture(LabelManagerApp(runtime), OUTPUT / "label-manager-final.png"))
        screenshots.append(_capture(SettingsApp(runtime / "config.ini"), OUTPUT / "printer-settings.png"))

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
