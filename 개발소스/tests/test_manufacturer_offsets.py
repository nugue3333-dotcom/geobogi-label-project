"""Regression for the former TSPL-only offset restriction; never transmit."""
from configparser import ConfigParser
from dataclasses import replace

import pytest

from barcode_label_automation.config import DEFAULTS, load_config
from barcode_label_automation.errors import ConfigError
from barcode_label_automation.excel_reader import LabelRow
from barcode_label_automation.label_media import write_config_atomic, save_label_size
from barcode_label_automation.printer_offsets import validate_offsets, slcs_media_commands, zebra_feed_command
from barcode_label_automation.settings_app import load_settings, save_settings, validate_settings
from barcode_label_automation.templates import render_label, mm_to_dots, tspl_media_commands
from barcode_label_automation.template_output import render_command
from barcode_label_automation.label_designer_app import normalize_template


def make_config(tmp_path, brand, *, dpi=203, gap='auto', feed='auto', orientation='normal', dx=0):
    parser = ConfigParser(interpolation=None)
    parser.read_dict(DEFAULTS)
    for section, key, value in [('printer','brand',brand), ('printer','mode','network'),
        ('printer','ip','127.0.0.1'), ('printer','print_orientation',orientation),
        ('printer','media_handling','tear_off'), ('label','width_mm','60.5'),
        ('label','height_mm','50.25'), ('label','dpi',str(dpi)),
        ('label','gap_offset_mm',gap), ('label','feed_offset_mm',feed), ('label','offset_x_mm',str(dx))]:
        parser.set(section,key,str(value))
    parser.set('label','offsets_profile',brand)
    path = tmp_path/'config.ini'
    write_config_atomic(path,parser)
    return path,load_config(path)


@pytest.mark.parametrize('brand,gap,feed',[('bixolon','-1.25','1.5'),('tsc','.25','-1.5'),('zebra','auto','-1.5')])
@pytest.mark.parametrize('dpi',[203,300,600])
def test_settings_config_roundtrip_uses_manufacturer_ranges(tmp_path,brand,gap,feed,dpi):
    path,config=make_config(tmp_path,brand,dpi=dpi,gap=gap,feed=feed)
    settings=load_settings(path)
    assert not validate_settings(settings).errors
    save_settings(path,settings)
    assert load_config(path).label==config.label
    assert path.read_text(encoding='utf-8-sig').find('feed_offset_mm = '+feed)>=0


@pytest.mark.parametrize('brand',['bixolon','zebra','tsc'])
def test_missing_offsets_keep_legacy_defaults_without_device_reset(tmp_path,brand):
    path,_=make_config(tmp_path,brand)
    parser=ConfigParser();parser.read(path,encoding='utf-8-sig')
    parser.remove_option('label','gap_offset_mm');parser.remove_option('label','feed_offset_mm')
    write_config_atomic(path,parser)
    config=load_config(path)
    assert config.label.gap_offset_mm==(0 if brand=='tsc' else None)
    assert config.label.feed_offset_mm is None
    assert load_settings(path).gap_offset_mm==config.label.gap_offset_mm


@pytest.mark.parametrize('brand,gap,feed',[('bixolon','-1','1'),('zebra','auto','-1')])
@pytest.mark.parametrize('orientation',['normal','rotate_180','landscape','landscape_180'])
@pytest.mark.parametrize('dx',[0,.25])
def test_every_auto_and_saved_template_path_emits_offsets(tmp_path,brand,gap,feed,orientation,dx):
    path,config=make_config(tmp_path,brand,gap=gap,feed=feed,orientation=orientation,dx=dx)
    label=config.label
    row=LabelRow('001','TEST','001234567890','LOT01',1,137)
    auto=render_label(config.printer.language,row,label.width_mm,label.height_mm,label.dpi,
        print_orientation=orientation,offset_x_mm=dx,gap_offset_mm=label.gap_offset_mm,
        feed_offset_mm=label.feed_offset_mm)
    from barcode_label_automation.media_geometry import logical_size
    width,height=logical_size(label.width_mm,label.height_mm,orientation)
    design=normalize_template({'label':{'width_mm':width,'height_mm':height,'print_orientation':orientation},
        'elements':[{'id':'a','type':'text','text':'TOP 001','x':3,'y':3,'width':20,'height':5,'font_size':9}]})
    saved=render_command(design,{},config,tmp_path,137)
    for command in (auto,saved):
        data=command.encode('cp949') if isinstance(command,str) else command
        if brand=='bixolon':
            assert f'SL{mm_to_dots(label.height_mm,label.dpi)},24,G,-8'.encode() in data
            assert b'TA8' in data and b'SA' not in data
            assert b'SF1' in data
            assert b'P137' in data
        else:
            assert data.startswith(b'~TA-008\n^XA')
            assert b'^PQ137' in data


@pytest.mark.parametrize('value',[None,0,-.25,.25])
@pytest.mark.parametrize('dpi',[203,300,600])
def test_inherit_and_explicit_zero_are_distinct_and_zebra_600_step_is_two_dots(value,dpi):
    slcs=slcs_media_commands(200,24,'gap',dpi,value,value)
    zpl=zebra_feed_command(dpi,value)
    if value is None:
        assert slcs=='SL200,24,G\n' and zpl==''
    else:
        dots=round(value*dpi/25.4)
        steps=round(value*dpi/25.4/(2 if dpi==600 else 1))
        assert slcs==f'SL200,24,G,{dots}\nSF1\nTA{dots}\n'
        assert zpl==f"~TA{'-' if steps<0 else ''}{abs(steps):03d}\n"


def test_bixolon_mark_to_perforation_distance_is_not_limited_by_ta_100_dots():
    # The exact 200-dot distance is inside a 50 mm label and above TA's
    # independent ±100-dot limit. SL p4 may carry this documented distance.
    distance_mm = 200 * 25.4 / 203
    validate_offsets('slcs', 'black_mark', 50, 203, distance_mm, 0, brand='bixolon')
    assert slcs_media_commands(400, 24, 'black_mark', 203, distance_mm, 0) == (
        'SL400,24,B,200\nSF1\nTA0\n'
    )
    with pytest.raises(ValueError, match='용지 길이'):
        validate_offsets('slcs', 'black_mark', 50, 203, 51, 0, brand='bixolon')
    with pytest.raises(ValueError, match='TA'):
        validate_offsets('slcs', 'black_mark', 50, 203, distance_mm, 13, brand='bixolon')


def test_bixolon_200_dot_distance_reaches_auto_and_saved_design_output(tmp_path):
    distance_mm=200*25.4/203
    path,config=make_config(tmp_path,'bixolon',gap=str(distance_mm),feed='0')
    parser=ConfigParser(interpolation=None);parser.read(path,encoding='utf-8-sig')
    parser.set('label','media_type','black_mark');write_config_atomic(path,parser)
    config=load_config(path)
    row=LabelRow('001','TEST','001234567890','LOT01',1,1)
    auto=render_label('slcs',row,100,50,203,3,media_type='black_mark',
                      gap_offset_mm=distance_mm,feed_offset_mm=0)
    design=normalize_template({
        'label':{'width_mm':100,'height_mm':50,'print_orientation':'normal'},
        'elements':[{'id':'text','type':'text','text':'TEST','x':3,'y':3,'width':20,'height':5,'font_size':9}],
    })
    saved=render_command(design,{},config,tmp_path,1)
    outputs=[(auto.encode('cp949') if isinstance(auto,str) else auto).replace(b'\r\n',b'\n'),
             (saved.encode('cp949') if isinstance(saved,str) else saved).replace(b'\r\n',b'\n')]
    expected=b'SL400,24,B,200\nSF1\nTA0\n'
    assert all(expected in output for output in outputs)

    baseline=render_label('slcs',row,100,50,203,3,media_type='black_mark',
                          gap_offset_mm=None,feed_offset_mm=None)
    assert auto.split('SOT\n',1)[1] == baseline.split('SOT\n',1)[1]


@pytest.mark.parametrize('media,command', [
    ('gap', 'GAP 3 mm,4 mm\n'),
    ('black_mark', 'BLINE 3 mm,4 mm\n'),
])
def test_tspl_sensor_mode_and_explicit_extra_feed_are_sent_together(media, command):
    assert tspl_media_commands(3, media, 4, None) == command
    assert tspl_media_commands(3, media, 0, None) == command.replace('4 mm', '0 mm')
    assert tspl_media_commands(3, media, None, None) == ''


def test_tspl_extra_feed_and_stop_offset_are_separate_commands():
    assert tspl_media_commands(3, 'black_mark', 4.5, -1.25) == (
        'BLINE 3 mm,4.5 mm\nOFFSET -1.25 mm\n'
    )
    assert tspl_media_commands(3, 'black_mark', None, -1.25) == 'OFFSET -1.25 mm\n'


@pytest.mark.parametrize('brand,gap,feed',[('bixolon','51','auto'),('bixolon','auto','-13'),
    ('zebra','1','auto'),('zebra','auto','16'),('tsc','-1','auto'),('tsc','auto','26')])
def test_invalid_offsets_rejected_by_settings_and_config(tmp_path,brand,gap,feed):
    path,_=make_config(tmp_path,brand)
    before=path.read_bytes()
    settings=replace(load_settings(path),gap_offset_mm=None if gap=='auto' else float(gap),
                     feed_offset_mm=None if feed=='auto' else float(feed))
    assert validate_settings(settings).errors
    with pytest.raises(ValueError):save_settings(path,settings)
    assert path.read_bytes()==before
    parser=ConfigParser();parser.read(path,encoding='utf-8-sig')
    parser.set('label','gap_offset_mm',gap);parser.set('label','feed_offset_mm',feed)
    write_config_atomic(path,parser)
    with pytest.raises(ConfigError):load_config(path)


def test_tsc_continuous_media_rejects_nonzero_extra_feed():
    with pytest.raises(ValueError,match='연속 용지'):
        validate_offsets('tspl','continuous',50,203,1,None,brand='tsc')


def test_bixolon_negative_sensor_offset_survives_paper_resize(tmp_path):
    path,_=make_config(tmp_path,'bixolon',gap='-1')
    save_label_size(path,40.5,30.25)
    assert load_config(path).label.gap_offset_mm==-1


def test_sewoo_and_hc100_are_not_assumed_to_support_generic_zebra_range():
    with pytest.raises(ValueError,match='세우테크'):zebra_feed_command(203,0,brand='sewoo')
    with pytest.raises(ValueError,match='HC100'):zebra_feed_command(203,-1,model='HC100')


@pytest.mark.parametrize('value',[float('inf'),float('nan'),True])
def test_offset_validation_rejects_nonfinite_or_boolean_values(value):
    with pytest.raises(ValueError):validate_offsets('slcs','gap',40,203,value,None)


def test_legacy_disabled_bixolon_zero_preserves_existing_device_offset(tmp_path):
    path,_=make_config(tmp_path,'bixolon',gap='0')
    parser=ConfigParser();parser.read(path,encoding='utf-8-sig')
    parser.remove_option('label','offsets_profile');write_config_atomic(path,parser)
    before=path.read_bytes()
    assert load_config(path).label.gap_offset_mm is None
    assert load_settings(path).gap_offset_mm is None
    assert path.read_bytes()==before
    save_settings(path,replace(load_settings(path),gap_offset_mm=0))
    assert load_config(path).label.gap_offset_mm==0
    parser.read(path,encoding='utf-8-sig')
    assert parser.get('label','offsets_profile')=='bixolon'
