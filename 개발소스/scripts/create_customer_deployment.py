from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "고객용_실행폴더"
DEFAULT_DEPLOY_ROOT = PROJECT_ROOT.parent / "고객배포"
sys.path.insert(0, str(PROJECT_ROOT))

from barcode_label_automation.customer_deployment import create_customer_deployment


def main() -> int:
    parser = ArgumentParser(description="Create a clean customer deployment folder.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR, help="Customer runtime folder to copy")
    parser.add_argument("--deploy-root", type=Path, default=DEFAULT_DEPLOY_ROOT, help="Folder that receives dated deployments")
    parser.add_argument("--package-prefix", default="채움랩_라벨출력_고객용")
    parser.add_argument("--date-stamp", default=None, help="YYYYMMDD override for repeatable tests")
    args = parser.parse_args()

    result = create_customer_deployment(
        args.source,
        args.deploy_root,
        package_prefix=args.package_prefix,
        date_stamp=args.date_stamp,
    )
    print(f"배포 폴더: {result.target_dir}")
    print(f"복사 파일: {result.files}")
    print(f"복사 용량: {result.bytes / 1024 / 1024:.2f} MB")
    print(f"manifest: {result.manifest_message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
