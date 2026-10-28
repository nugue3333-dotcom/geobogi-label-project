from __future__ import annotations

import json
from configparser import ConfigParser
from types import SimpleNamespace

import pytest

from barcode_label_automation import cli
from barcode_label_automation.config import DEFAULTS, load_config
from barcode_label_automation.label_designer_app import _element
from barcode_label_automation.saved_output import prepare_saved_output
from barcode_label_automation.value_jobs import ValueJobStore, effective_job_rules
from barcode_label_automation.value_rules import compile_generated_labels
from barcode_label_automation.print_progress import (
    DESIGNER_PROGRESS_FILE_NAME, NewPrintJobRequired, PrintProgress, UnknownPrintItemsError,
)


def serial(name='번호', **changes):
    rule = {'name': name, 'kind': 'serial', 'start': 1, 'digits': 6, 'step': 1,
            'copies_per_value': 1, 'reset': 'continue'}
    rule.update(changes)
    return rule


def setup_saved(tmp_path, *, rules=None, text='{{번호}}'):
    parser = ConfigParser(interpolation=None)
    parser.read_dict(DEFAULTS)
    for section, key, value in [('printer','brand','tsc'), ('printer','language','tspl'),
                                ('printer','mode','network'), ('printer','ip','127.0.0.1'),
                                ('label','width_mm','50'), ('label','height_mm','40'),
                                ('data','excel_file',str(tmp_path/'missing.xlsx')),
                                ('data','output_dir',str(tmp_path/'out'))]:
        parser.set(section,key,value)
    config = tmp_path/'config.ini'
    with config.open('w',encoding='utf-8') as f:
        parser.write(f)
    design = tmp_path/'serial.cllabel'
    design.write_text(json.dumps({'label':{'width_mm':50,'height_mm':40},
        'elements':[_element('text',text,1,1,30,6)],
        'value_rules':rules if rules is not None else [serial()],
        'value_profile_id':'a'*32},ensure_ascii=False),encoding='utf-8')
    return config,design


def args(config, design, **extra):
    values = dict(config=str(config),template=str(design),template_hash=None,value_job=None,
                  limit=None,force_print_qty=6,no_data=True,copies_per_serial=2,new_job=False)
    values.update(extra)
    return SimpleNamespace(**values)


def test_job_copy_override_preserves_existing_continue_sequence_and_snapshot(tmp_path):
    rules=[serial()]
    store=ValueJobStore(tmp_path)
    first=store.prepare_job([{}],[1],rules,template_key='label')
    before_rule=dict(rules[0])
    second=store.prepare_job([{}],[6],rules,template_key='label',copies_per_serial=2)
    assert [(x.row['번호'],x.copies) for x in second.labels] == [('000002',2),('000003',2),('000004',2)]
    assert store.peek_start_overrides('label',rules)=={'번호':5}
    assert rules[0]==before_rule
    assert store.load_job(first.snapshot_id).labels==first.labels
    assert store.load_job(second.snapshot_id).labels==second.labels
    third=store.prepare_job([{}],[3],rules,template_key='label',copies_per_serial=1)
    assert [x.row['번호'] for x in third.labels]==['000005','000006','000007']
    assert store.peek_start_overrides('label',rules)=={'번호':8}


def test_preview_override_does_not_mutate_rules_or_create_ledger(tmp_path):
    rules=[serial()]
    original=dict(rules[0]);store=ValueJobStore(tmp_path)
    labels=compile_generated_labels([{}],[6],effective_job_rules(rules,2),
                                    start_overrides=store.peek_start_overrides('label',rules))
    assert [(x.row['번호'],x.copies) for x in labels]==[('000001',2),('000002',2),('000003',2)]
    assert rules[0]==original
    assert not store.directory.exists()


def test_mixed_legacy_intervals_never_silently_overwritten(tmp_path):
    rules=[serial('첫째',copies_per_value=1),serial('둘째',copies_per_value=3)]
    store=ValueJobStore(tmp_path)
    with pytest.raises(ValueError,match='반복 간격'):
        store.prepare_job([{}],[6],rules,template_key='label',copies_per_serial=2)
    assert not store.path.exists()
    assert [r['copies_per_value'] for r in rules]==[1,3]


def test_no_db_saved_design_dry_run_and_record_use_same_values(tmp_path):
    config,design=setup_saved(tmp_path)
    options=args(config,design)
    labels,commands,context=prepare_saved_output(options,load_config(config),dry_run=True)
    assert [x.print_qty for x in labels]==[2,2,2]
    assert not (tmp_path/'out'/'value_jobs').exists()
    _,real_commands,context=prepare_saved_output(options,load_config(config),dry_run=False)
    job=ValueJobStore(tmp_path).load_job(context['snapshot_id'])
    assert commands==real_commands
    assert [(x.row['번호'],x.copies) for x in job.labels]==[('000001',2),('000002',2),('000003',2)]
    assert ValueJobStore(tmp_path).peek_start_overrides('a'*32,[serial()])=={'번호':4}


def test_changed_job_copy_count_has_distinct_resume_request_key(tmp_path):
    config,design=setup_saved(tmp_path)
    a=prepare_saved_output(args(config,design),load_config(config),dry_run=False)
    b=prepare_saved_output(args(config,design,copies_per_serial=3),load_config(config),dry_run=False)
    assert a[2]['snapshot_id'] != b[2]['snapshot_id']
    store=ValueJobStore(tmp_path)
    assert store.load_job(a[2]['snapshot_id']).request_key != store.load_job(b[2]['snapshot_id']).request_key
    assert [(x.row['번호'],x.copies) for x in store.load_job(b[2]['snapshot_id']).labels] == [('000004',3),('000005',3)]


def test_conflicting_partial_job_does_not_reserve_new_numbers(tmp_path):
    config, design = setup_saved(tmp_path)
    loaded = load_config(config)
    first = prepare_saved_output(args(config, design), loaded, dry_run=False)
    progress = PrintProgress.open_for_job(tmp_path/'out'/DESIGNER_PROGRESS_FILE_NAME,
                                         first[1], loaded.printer.command_encoding, first[2])
    progress.mark_sending(1)
    progress.mark_sent(1)
    store = ValueJobStore(tmp_path)
    before = store.path.read_bytes()
    with pytest.raises(NewPrintJobRequired):
        prepare_saved_output(args(config, design, copies_per_serial=3), loaded, dry_run=False)
    assert store.path.read_bytes() == before
    resumed = prepare_saved_output(args(config, design), loaded, dry_run=False)
    assert resumed[2]['snapshot_id'] == first[2]['snapshot_id']


def test_unknown_output_blocks_even_explicit_new_job_without_allocating(tmp_path):
    config, design = setup_saved(tmp_path)
    loaded = load_config(config)
    first = prepare_saved_output(args(config, design), loaded, dry_run=False)
    progress = PrintProgress.open_for_job(tmp_path/'out'/DESIGNER_PROGRESS_FILE_NAME,
                                         first[1], loaded.printer.command_encoding, first[2])
    progress.mark_sending(1)
    store = ValueJobStore(tmp_path)
    before = store.path.read_bytes()
    with pytest.raises(UnknownPrintItemsError):
        prepare_saved_output(args(config, design, new_job=True), loaded, dry_run=False)
    assert store.path.read_bytes() == before


def test_cli_reprint_cannot_overwrite_unknown_progress(monkeypatch, tmp_path):
    config, design = setup_saved(tmp_path)
    loaded = load_config(config)
    first = prepare_saved_output(args(config, design), loaded, dry_run=False)
    path = tmp_path/'out'/DESIGNER_PROGRESS_FILE_NAME
    progress = PrintProgress.open_for_job(path, first[1], loaded.printer.command_encoding, first[2])
    progress.mark_sending(1)
    original = path.read_bytes()
    monkeypatch.setattr(cli, '_send_to_printer', lambda *a: pytest.fail('must not transmit'))
    assert cli.main(['--config', str(config), '--template', str(design), '--value-job',
                     first[2]['snapshot_id'], '--new-job', '--print', '--yes']) == 1
    assert path.read_bytes() == original


def test_no_db_mode_blocks_missing_required_field_before_reservation(tmp_path):
    config,design=setup_saved(tmp_path,text='{{상품명}} {{번호}}')
    with pytest.raises(ValueError,match='상품명'):
        prepare_saved_output(args(config,design),load_config(config),dry_run=False)
    assert not (tmp_path/'out'/'value_jobs'/'ledger.json').exists()


@pytest.mark.parametrize('argv',[
    ['--no-data','--dry-run'],
    ['--copies-per-serial','2','--dry-run'],
    ['--template','fake.cllabel','--no-data','--excel','x.xlsx','--dry-run'],
    ['--template','fake.cllabel','--value-job','id','--copies-per-serial','2','--dry-run'],
])
def test_conflicting_cli_modes_fail_before_opening_config(argv):
    assert cli.main(argv)==1
