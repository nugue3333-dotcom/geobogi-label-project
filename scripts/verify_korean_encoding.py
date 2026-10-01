from __future__ import annotations

import subprocess
import tempfile
import re
from pathlib import Path

from openpyxl import Workbook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXE_PATH = PROJECT_ROOT / "고객용_실행폴더" / "라벨출력엔진.exe"
KOREAN_NAME = "한글 브라켓"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gbdream_korean_") as temp_name:
        work_dir = Path(temp_name)
        queue_path = work_dir / "print_queue.xlsx"
        _write_queue(queue_path)

        checks = {
            "bixolon": ("slcs", "cp949"),
            "tsc": ("tspl", "cp949"),
            "zebra": ("zpl", "utf-8"),
            "sewoo": ("zpl", "utf-8"),
        }
        for brand, (extension, encoding) in checks.items():
            config_path = work_dir / f"config_{brand}.ini"
            output_dir = work_dir / f"out_{brand}"
            _write_config(config_path, brand, output_dir)

            result = subprocess.run(
                [str(EXE_PATH), "--config", str(config_path), "--dry-run"],
                cwd=work_dir,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                print(result.stdout)
                print(result.stderr)
                return result.returncode

            label_path = output_dir / f"label_001.{extension}"
            payload = label_path.read_bytes()
            expected = KOREAN_NAME.encode(encoding)
            if brand != "tsc" and expected not in payload:
                print(f"{brand}: missing {encoding} encoded Korean text in {label_path}")
                return 1
            if brand == "bixolon" and b"CS13,0" not in payload:
                print("bixolon: missing Korean character set command CS13,0")
                return 1
            if brand == "bixolon" and re.search(rb"\nT\d+,\d+,b,", payload) is None:
                print("bixolon: missing Korean resident font command")
                return 1
            if brand == "tsc" and b"CODEPAGE 949" not in payload:
                print("tsc: missing Korean code page command")
                return 1
            if brand == "tsc" and b"BITMAP " not in payload:
                print("tsc: missing Korean text bitmap command")
                return 1
            print(f"{brand}: OK ({extension}, {encoding})")

    return 0


def _write_queue(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Labels"
    sheet.append(["item_code", "item_name", "barcode", "lot_no", "qty", "print_qty"])
    sheet.append(["A1001", KOREAN_NAME, "A1001-250531", "LOT250531", 100, 1])
    workbook.save(path)


def _write_config(path: Path, brand: str, output_dir: Path) -> None:
    path.write_text(
        f"""
[printer]
brand = {brand}
mode = network
language = auto
command_encoding = auto
ip = 127.0.0.1
port = 9100
windows_printer_name = auto

[brand.bixolon]
language = slcs
command_encoding = cp949
windows_printer_name = BIXOLON Label Printer

[brand.tsc]
language = tspl
command_encoding = cp949
windows_printer_name = TSC Label Printer

[brand.zebra]
language = zpl
command_encoding = utf-8
windows_printer_name = ZDesigner Label Printer

[brand.sewoo]
language = zpl
command_encoding = utf-8
windows_printer_name = SEWOO Label Printer

[label]
width_mm = 50
height_mm = 30
dpi = 203
gap_mm = 3

[data]
excel_file = {path.parent / "print_queue.xlsx"}
output_dir = {output_dir}
""".strip(),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
