from __future__ import annotations

"""Capture the current source UI used by the customer PDF manuals."""

import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barcode_label_automation.label_designer_app import LabelDesignerApp
from barcode_label_automation.label_manager_app import LabelManagerApp
from barcode_label_automation.settings_app import SettingsApp


OUTPUT = ROOT / "outputs" / "ui-redesign-preview"


def _capture(app, target: Path, geometry: str = "1480x900+40+40") -> None:
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
    app.destroy()


def _copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="chaeumlab-manual-") as temp_dir:
        runtime = Path(temp_dir)
        for filename in ("config.ini", "barcode_db.xlsx", "print_queue.xlsx", "labels.xlsm"):
            _copy_if_exists(ROOT / filename, runtime / filename)
        if (ROOT / "templates").exists():
            shutil.copytree(ROOT / "templates", runtime / "templates", dirs_exist_ok=True)

        sample_template = runtime / "templates" / "sample_excel_product.gblabel"
        designer = LabelDesignerApp(runtime, initial_template_path=sample_template)
        _capture(designer, OUTPUT / "label-designer-final.png")
        designer_data = LabelDesignerApp(runtime, initial_template_path=sample_template)
        designer_data.connect_data_source_path(runtime / "barcode_db.xlsx")
        designer_data.show_property_view("data")
        _capture(designer_data, OUTPUT / "label-designer-data.png")
        _capture(LabelManagerApp(runtime), OUTPUT / "label-manager-final.png")
        _capture(SettingsApp(runtime / "config.ini"), OUTPUT / "printer-settings.png")

    print("CUSTOMER_MANUAL_SCREENS_CAPTURED")
    for filename in ("label-designer-final.png", "label-designer-data.png", "label-manager-final.png", "printer-settings.png"):
        print(OUTPUT / filename)


if __name__ == "__main__":
    main()
