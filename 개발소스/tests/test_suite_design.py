from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from barcode_label_automation import label_designer_app as designer
from barcode_label_automation.brand_assets import APP_ROLE_ICONS
from barcode_label_automation.label_file_types import LABEL_OPEN_FILE_TYPES, LABEL_SAVE_FILE_TYPES
from barcode_label_automation.portable_project import export_portable_project
from barcode_label_automation.ui_tokens import COLORS, TYPOGRAPHY, UI_FONT_FAMILY

ROOT = Path(__file__).resolve().parents[1]


def test_approved_suite_palette_and_interface_font():
    assert COLORS.primary.lower() == '#143e70'
    assert COLORS.accent.lower() == '#a3d900'
    assert COLORS.surface.lower() == '#ffffff'
    assert TYPOGRAPHY.body[0] == UI_FONT_FAMILY == 'Malgun Gothic'
    assert designer.DEFAULT_FONT_NAME != UI_FONT_FAMILY
    assert LABEL_OPEN_FILE_TYPES[0][1] == '*.cllabel *.gblabel'
    assert LABEL_SAVE_FILE_TYPES[0][1] == '*.cllabel'


def test_program_roles_and_documents_have_distinct_multisize_icons():
    assets = [*APP_ROLE_ICONS.values(), Path('assets/brand/chaeumlab_label_file_icon_white.ico'), Path('assets/brand/chaeumlab_project_file_icon_white.ico')]
    payloads = [(ROOT / path).read_bytes() for path in assets]
    assert len(set(payloads)) == 5
    for path in assets:
        with Image.open(ROOT / path) as icon:
            assert {(n, n) for n in (16, 24, 32, 48, 64, 128, 256)} <= icon.ico.sizes()
            for size in (16, 24, 32):
                pixels = list(icon.ico.getimage((size, size)).convert('RGBA').getdata())
                assert any(g > r + 20 and g > b + 15 and a > 0 for r, g, b, a in pixels)
                assert any(b > r + 15 and a > 0 for r, g, b, a in pixels)


@pytest.mark.parametrize('extension', ['.clproject', '.gbproject', '.CLPROJECT'])
def test_project_cli_resolution_imports_zip_as_a_label(tmp_path, extension):
    source = tmp_path / f'도안 이동{extension}'
    payload = designer.default_template(50, 40)
    export_portable_project(payload, tmp_path, source)
    label, profile = designer._resolve_initial_document(source, tmp_path / 'new pc')
    assert label.suffix == '.cllabel'
    assert designer.load_template_file(label)['label'] == payload['label']
    assert profile is not None


def test_project_cannot_enter_unconfirmed_direct_print_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(designer, 'import_portable_project', lambda *_args: pytest.fail('reject before importing or printing'))
    with pytest.raises(ValueError, match='바로 인쇄'):
        designer._resolve_initial_document(tmp_path / 'p.clproject', tmp_path, print_requested=True)


def test_register_cli_returns_without_creating_gui(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(designer, 'executable_dir', lambda: tmp_path)
    monkeypatch.setattr(designer, 'ensure_label_file_association', lambda path: calls.append(path) or SimpleNamespace(registered=True, error='', rollback_path=None))
    monkeypatch.setattr(designer, 'LabelDesignerApp', lambda *_args, **_kwargs: pytest.fail('registration must not create a GUI'))
    assert designer.main(['--register-file-associations']) == 0
    assert calls == [tmp_path / '라벨디자이너.exe']


def test_recent_files_include_both_formats_without_discarding_legacy(tmp_path):
    import json
    (tmp_path / 'out').mkdir()
    files = [tmp_path / name for name in ('new.cllabel', 'old.gblabel', 'label.json', 'skip.xlsx')]
    for path in files:
        path.write_text('{}', encoding='utf-8')
    (tmp_path / 'out/designer_recent_files.json').write_text(json.dumps({'paths': [str(path) for path in files]}), encoding='utf-8')
    app = designer.LabelDesignerApp.__new__(designer.LabelDesignerApp)
    app.base_dir = tmp_path
    assert app._recent_template_paths() == files[:3]


def test_designer_manual_opens_pdf_file_without_creating_a_directory(tmp_path, monkeypatch):
    relative = Path('docs/고객용_매뉴얼/채움랩_라벨디자이너_고객용_매뉴얼.pdf')
    pdf = tmp_path / relative
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b'%PDF-1.4 test fixture')
    opened = []
    monkeypatch.setattr(designer.os, 'startfile', opened.append)
    app = SimpleNamespace(install_dir=tmp_path, base_dir=tmp_path / 'user-data')
    designer.LabelDesignerApp.open_customer_manual(app)
    assert opened == [pdf]
    assert pdf.is_file()


def test_designer_manual_reports_missing_pdf_handler(tmp_path, monkeypatch):
    pdf = tmp_path / 'docs/고객용_매뉴얼/채움랩_라벨디자이너_고객용_매뉴얼.pdf'
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b'%PDF-1.4 test fixture')
    def fail(_path):
        raise OSError('PDF handler unavailable')
    notices = []
    monkeypatch.setattr(designer.os, 'startfile', fail)
    monkeypatch.setattr(designer.messagebox, 'showerror', lambda title, text, **kwargs: notices.append((title, text)))
    designer.LabelDesignerApp.open_customer_manual(SimpleNamespace(install_dir=tmp_path, base_dir=tmp_path))
    assert len(notices) == 1
    assert 'PDF' in notices[0][1]
