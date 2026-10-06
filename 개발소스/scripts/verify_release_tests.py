"""Run release tests with native Tk scenarios in fresh Python processes."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'outputs/release-tests')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    collection = subprocess.run([sys.executable, '-m', 'pytest', '--collect-only', '-q', 'tests/test_ui_visibility.py'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if collection.returncode:
        print(collection.stderr)
        return collection.returncode
    nodes = [line.strip() for line in collection.stdout.splitlines() if line.startswith('tests/test_ui_visibility.py::')]
    if not nodes:
        raise RuntimeError('No native GUI tests collected')
    checks = [('unit-integration', ['--ignore=tests/test_ui_visibility.py'])]
    checks.extend((f'gui-{index:02}', [node]) for index, node in enumerate(nodes, 1))
    records = []
    for name, arguments in checks:
        xml = output/f'{name}.xml'
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *arguments, f'--junitxml={xml}'], cwd=ROOT, capture_output=True, timeout=180)
        (output/f'{name}.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            print((result.stdout+result.stderr).decode('utf-8', errors='replace'))
            return result.returncode
        suite = ET.parse(xml).getroot().find('testsuite')
        total = int(suite.get('tests', '0'))
        skipped = int(suite.get('skipped', '0'))
        record = {'check': name, 'tests': total, 'passed': total-skipped, 'skipped': skipped, 'failures': int(suite.get('failures', '0')), 'errors': int(suite.get('errors', '0')), 'arguments': arguments}
        records.append(record)
        print(f'{name}: {record["passed"]} passed, {skipped} skipped', flush=True)
    summary = {'passed': sum(row['passed'] for row in records), 'skipped': sum(row['skipped'] for row in records), 'failed': 0, 'native_gui_processes': len(nodes), 'checks': records}
    (output/'result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('RELEASE_TESTS_VERIFIED', summary['passed'], 'passed,', summary['skipped'], 'skipped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
