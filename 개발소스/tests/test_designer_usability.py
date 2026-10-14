from __future__ import annotations

import copy
import json
import threading
from configparser import ConfigParser
from pathlib import Path

import pytest

from barcode_label_automation.designer_clipboard import PREFIX, clone_objects, decode_objects, encode_objects
from barcode_label_automation.designer_print_dispatch import send_prepared_jobs
from barcode_label_automation.label_designer_app import LabelDesignerApp, _element, default_template
from barcode_label_automation.label_media import outside_elements, read_label_size, save_label_size, write_config_atomic
from barcode_label_automation.print_progress import PrintProgress
from barcode_label_automation.tool_icons import TOOL_ICON_NAMES, render_tool_icon


def test_clipboard_snapshot_preserves_image_db_and_leading_zero(tmp_path):
    elements = [_element('barcode', '001234', 2, 3, 20, 10, field='barcode'),
                _element('image', '', 25, 3, 10, 10)]
    elements[1]['image_path'] = 'assets/sample.png'
    for element in elements:
        element['group_id'] = 'original'
    value = encode_objects(elements, tmp_path)
    elements[0]['text'] = 'changed'
    result = clone_objects(decode_objects(value), 50, 40)
    assert result[0]['text'] == '001234'
    assert result[0]['field'] == 'barcode'
    assert result[1]['image_path'] == str((tmp_path / 'assets/sample.png').resolve())
    assert result[0]['group_id'] == result[1]['group_id'] != 'original'
    assert result[0]['id'] != elements[0]['id']
    assert result[1]['x'] - result[0]['x'] == 23


@pytest.mark.parametrize('offset', [2, 4, 8, 20])
def test_group_spacing_at_edge_never_changes(offset):
    elements = [_element('text', 'A', 30, 30, 10, 5), _element('text', 'B', 40, 35, 10, 5)]
    before = copy.deepcopy(elements)
    result = clone_objects(elements, 50, 40, offset)
    assert elements == before
    assert result[1]['x'] - result[0]['x'] == 10
    assert result[1]['y'] - result[0]['y'] == 5
    assert not outside_elements(result, 50, 40)


@pytest.mark.parametrize('value', ['plain text', PREFIX + '{}', PREFIX + '[]', PREFIX + '[null]',
    PREFIX + '[{"type":"text","x":true,"y":0,"width":1,"height":1}]',
    PREFIX + '[{"type":"text","x":NaN,"y":0,"width":1,"height":1}]'])
def test_invalid_clipboard_is_rejected(value):
    with pytest.raises(ValueError):
        decode_objects(value)


def test_nonfinite_nested_clipboard_value_is_rejected():
    with pytest.raises(ValueError):
        decode_objects(PREFIX + '[{"type":"text","x":0,"y":0,"width":1,"height":1,"font_size":Infinity}]')


def test_oversize_copy_does_not_distort_to_fit():
    with pytest.raises(ValueError, match='현재 라벨보다'):
        clone_objects([_element('text', 'large', 0, 0, 80, 20)], 50, 40)


@pytest.mark.parametrize('name', TOOL_ICON_NAMES)
@pytest.mark.parametrize('size', [24, 30, 36])
def test_tool_icons_have_actual_graphics_at_each_scale(name, size):
    image = render_tool_icon(name, size)
    assert image.size == (size, size)
    assert image.getbbox() is not None
    assert image.mode == 'RGBA'


def _config(path):
    from barcode_label_automation.config import DEFAULTS
    parser = ConfigParser()
    parser.read_dict(DEFAULTS)
    parser.set('printer', 'mode', 'network')
    parser.set('printer', 'ip', '127.0.0.1')
    write_config_atomic(path, parser)
    return parser


def test_shared_paper_save_preserves_all_other_config_sections(tmp_path):
    path = tmp_path / 'config.ini'
    parser = _config(path)
    old = {s: dict(parser[s]) for s in parser.sections() if s != 'label'}
    save_label_size(path, 100, 80)
    assert read_label_size(path) == (100, 80)
    parser.read(path, encoding='utf-8-sig')
    assert {s: dict(parser[s]) for s in parser.sections() if s != 'label'} == old
    assert not list(tmp_path.glob('.label-settings-*.tmp'))


@pytest.mark.parametrize('value', [0, -1, 301, 10.5, True, float('nan'), float('inf')])
def test_invalid_paper_size_cannot_modify_settings(tmp_path, value):
    path = tmp_path / 'config.ini'
    _config(path)
    before = path.read_bytes()
    with pytest.raises((ValueError, OverflowError)):
        save_label_size(path, value, 40)
    assert path.read_bytes() == before


def test_mid_job_stop_keeps_unsent_commands_pending(tmp_path):
    jobs = [b'first', b'second', b'third']
    progress = PrintProgress.open_for_job(tmp_path / 'progress.json', jobs, 'utf-8', {})
    cancel = threading.Event()
    sent = []
    def sender(payload):
        sent.append(payload)
        cancel.set()
    result = send_prepared_jobs(jobs, [10000, 101, 1001], progress, sender, cancel)
    assert result.cancelled and result.sent_labels == 10000 and result.sent_jobs == 1
    assert sent == [b'first']
    assert progress.sent_indexes == [1]
    assert progress.pending_indexes == [2, 3]


def test_handled_transport_failure_is_not_a_success_and_never_auto_retries(tmp_path):
    jobs = [b'first', b'second']
    progress = PrintProgress.open_for_job(tmp_path / 'progress.json', jobs, 'utf-8', {})
    calls = []
    def sender(payload):
        calls.append(payload)
        if payload == b'second':
            raise OSError('offline')
    result = send_prepared_jobs(jobs, [101, 1001], progress, sender, threading.Event())
    assert isinstance(result.error, OSError)
    assert result.sent_jobs == 1 and result.sent_labels == 101
    assert calls == jobs
    assert progress.pending_indexes == []
    assert progress.unknown_indexes == [2]


@pytest.mark.parametrize('quantity', [1, 100, 101, 1000, 1001, 10000])
@pytest.mark.parametrize('language,marker', [('tspl', b'PRINT 1,'), ('zpl', b'^PQ'), ('slcs', b'P')])
def test_designer_commands_retain_requested_quantity(quantity, language, marker):
    from types import SimpleNamespace
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = default_template(50, 40)
    app.elements = [_element('text', '001234', 2, 2, 15, 5)]
    config = SimpleNamespace(printer=SimpleNamespace(language=language, command_encoding='utf-8',
        print_orientation='normal', print_method='direct_thermal', media_handling='tear_off', speed=4, density=8,
        print_speed=4, print_density=8), label=SimpleNamespace(dpi=203, gap_mm=2, media_type='gap'))
    payload = app.render_designer_print_command(config, {'barcode': '001234'}, quantity)
    assert marker + str(quantity).encode('ascii') in payload
