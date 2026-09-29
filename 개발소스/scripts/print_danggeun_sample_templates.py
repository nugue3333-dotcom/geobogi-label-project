"""Render and print the saved Danggeun sample labels through the designer renderer.

This uses the currently saved top-level application config, rather than source
defaults, so the generated SLCS payload has the same connection, cutter,
density, and media settings as the live label designer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barcode_label_automation.config import load_config
from barcode_label_automation.label_designer_app import LabelDesignerApp, load_template_file


APP_DIR = Path(__file__).resolve().parents[1]
APP_DIR = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("GEOBOKI_SAMPLE_ROOT") or (APP_DIR / "outputs" / "danggeun_sample"))
TEMPLATE_DIR = ROOT / "라벨템플릿"
PRINT_DIR = ROOT / "인쇄기록"
CONFIG_PATH = APP_DIR / "config.ini"


def designer_for(payload: dict[str, object]) -> LabelDesignerApp:
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = ROOT
    app.config_path = CONFIG_PATH
    app.template = payload
    app.elements = payload["elements"]
    app.preview_row = {}
    return app


def required_live_settings(config: object) -> None:
    printer = config.printer  # type: ignore[attr-defined]
    label = config.label  # type: ignore[attr-defined]
    actual = {
        "brand": str(printer.brand).lower(),
        "mode": str(printer.mode).lower(),
        "width_mm": float(label.width_mm),
        "height_mm": float(label.height_mm),
        "dpi": int(label.dpi),
    }
    expected = {
        "brand": "bixolon",
        "mode": "windows_raw",
        "width_mm": 100.0,
        "height_mm": 100.0,
        "dpi": 203,
    }
    if actual != expected or not str(printer.windows_printer_name).strip():
        raise RuntimeError(f"현재 저장 설정이 요청값과 다릅니다: {actual}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", action="store_true", help="Send the already saved commands to the configured printer.")
    args = parser.parse_args()
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"현재 저장 프린터 설정을 찾을 수 없습니다: {CONFIG_PATH}")

    config = load_config(CONFIG_PATH)
    required_live_settings(config)
    template_paths = sorted(TEMPLATE_DIR.glob("*.gblabel"))
    if len(template_paths) != 11:
        raise RuntimeError(f"샘플 템플릿 11개가 필요합니다. 현재: {len(template_paths)}개")

    command_dir = PRINT_DIR / "명령어"
    command_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_PATH, PRINT_DIR / "현재_저장된_프린터설정.ini")
    jobs: list[tuple[Path, bytes, LabelDesignerApp]] = []
    for template_path in template_paths:
        payload = load_template_file(template_path)
        if payload["label"] != {"width_mm": 100.0, "height_mm": 100.0}:
            raise RuntimeError(f"100x100mm 템플릿이 아닙니다: {template_path.name}")
        app = designer_for(payload)
        LabelDesignerApp._validate_output_row(app, {}, row_number=len(jobs) + 1)
        command = LabelDesignerApp.render_designer_print_command(app, config, {}, 1)
        command_path = command_dir / f"{template_path.stem}.slcs"
        command_path.write_bytes(command)
        jobs.append((template_path, command, app))

    results: list[dict[str, object]] = []
    for index, (template_path, command, app) in enumerate(jobs, start=1):
        result: dict[str, object] = {
            "index": index,
            "template": str(template_path),
            "bytes": len(command),
            "sha256": hashlib.sha256(command).hexdigest(),
            "status": "generated",
        }
        if args.print:
            try:
                LabelDesignerApp._send_designer_print(app, config, command)
            except Exception as exc:
                result["status"] = "failed"
                result["error"] = str(exc)
                results.append(result)
                break
            result["status"] = "sent"
        results.append(result)

    record = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "print" if args.print else "dry-run",
        "config": str(CONFIG_PATH),
        "printer": str(config.printer.windows_printer_name),
        "brand": str(config.printer.brand),
        "language": str(config.printer.language),
        "label_mm": [float(config.label.width_mm), float(config.label.height_mm)],
        "dpi": int(config.label.dpi),
        "jobs": results,
    }
    target = PRINT_DIR / ("실제출력_기록.json" if args.print else "명령생성_기록.json")
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [result for result in results if result["status"] == "failed"]
    print(f"mode={record['mode']} jobs={len(results)} failed={len(failed)} log={target}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
