"""Run release tests with native Tk scenarios in fresh Python processes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE_GUI_MODULES = (
    'tests/test_ui_visibility.py',
    'tests/test_barcode_dialogs.py',
    'tests/test_value_rules_dialog.py',
    'tests/test_barcode_first_ui.py',
    'tests/test_barcode_editor_r4_ui.py',
    'tests/test_barcode_editor_r5_ui.py',
    'tests/test_udi_editor.py',
    'tests/test_ai_udi_workflow_ui.py',
    'tests/test_manager_workflow_ui.py',
)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    child_env = os.environ.copy()
    child_env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'outputs/release-tests')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_path = output/'result.json'
    result_path.write_text(json.dumps({'status':'collecting','native_gui_modules':NATIVE_GUI_MODULES},indent=2),encoding='utf-8')
    collection = subprocess.run([sys.executable, '-m', 'pytest', '--collect-only', '-q', *NATIVE_GUI_MODULES], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', env=child_env)
    (output/'gui-collection.log').write_text(collection.stdout+collection.stderr,encoding='utf-8')
    if collection.returncode:
        result_path.write_text(json.dumps({'status':'failed','stage':'collection','exit_code':collection.returncode},indent=2),encoding='utf-8')
        print(collection.stdout+collection.stderr)
        return collection.returncode
    nodes = [line.strip() for line in collection.stdout.splitlines() if any(line.startswith(module+'::') for module in NATIVE_GUI_MODULES)]
    if any(not any(node.startswith(module+'::') for node in nodes) for module in NATIVE_GUI_MODULES):
        result_path.write_text(json.dumps({'status':'failed','stage':'collection','reason':'A native GUI module collected no tests'},indent=2),encoding='utf-8')
        raise RuntimeError('A native GUI module collected no tests')
    (output/'native-gui-nodes.json').write_text(json.dumps(nodes,ensure_ascii=False,indent=2),encoding='utf-8')
    checks = [('unit-integration', ['--ignore='+module for module in NATIVE_GUI_MODULES])]
    checks.extend((f'gui-{index:02}', [node]) for index, node in enumerate(nodes, 1))
    records = []
    for name, arguments in checks:
        xml = output/f'{name}.xml'
        try:
            result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *arguments, f'--basetemp={output / (name + "-tmp")}', f'--junitxml={xml}'], cwd=ROOT, capture_output=True, timeout=180, env=child_env)
        except subprocess.TimeoutExpired as exc:
            (output/f'{name}.log').write_bytes((exc.stdout or b'')+(exc.stderr or b'')+b'\nVerification timed out after 180 seconds.\n')
            result_path.write_text(json.dumps({'status':'failed','failed':1,'failed_check':name,'reason':'timeout','arguments':arguments,'checks':records},ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{name}: timed out',flush=True)
            return 124
        (output/f'{name}.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            result_path.write_text(json.dumps({'status':'failed','failed':1,'failed_check':name,'exit_code':result.returncode,'arguments':arguments,'checks':records},ensure_ascii=False,indent=2),encoding='utf-8')
            print((result.stdout+result.stderr).decode('utf-8', errors='replace'))
            return result.returncode
        suite = ET.parse(xml).getroot().find('testsuite')
        total = int(suite.get('tests', '0'))
        skipped = int(suite.get('skipped', '0'))
        record = {'check': name, 'tests': total, 'passed': total-skipped, 'skipped': skipped, 'failures': int(suite.get('failures', '0')), 'errors': int(suite.get('errors', '0')), 'arguments': arguments}
        records.append(record)
        print(f'{name}: {record["passed"]} passed, {skipped} skipped', flush=True)
    summary = {'status':'passed','passed': sum(row['passed'] for row in records), 'skipped': sum(row['skipped'] for row in records), 'failed': 0, 'native_gui_processes': len(nodes),'native_gui_modules':NATIVE_GUI_MODULES, 'checks': records}
    result_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('RELEASE_TESTS_VERIFIED', summary['passed'], 'passed,', summary['skipped'], 'skipped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
