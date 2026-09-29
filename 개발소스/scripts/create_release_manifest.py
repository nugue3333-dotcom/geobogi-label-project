from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CUSTOMER_DIR = PROJECT_ROOT / "고객용_실행폴더"
sys.path.insert(0, str(PROJECT_ROOT))

from barcode_label_automation.release_manifest import write_release_manifest


def main() -> int:
    parser = ArgumentParser(description="Create customer deployment manifest files.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_CUSTOMER_DIR)
    parser.add_argument("--package-name", default=None)
    args = parser.parse_args()

    json_path, text_path = write_release_manifest(args.base_dir, package_name=args.package_name)
    print(json_path)
    print(text_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
