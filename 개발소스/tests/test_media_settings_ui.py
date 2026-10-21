from configparser import ConfigParser
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import pytest

from barcode_label_automation.config import DEFAULTS, load_config
from barcode_label_automation.label_media import write_config_atomic
from barcode_label_automation.settings_app import (
    SettingsApp,
    PRINT_ORIENTATION_LABELS,
    BRAND_LABELS,
    MEDIA_TYPE_LABELS,
)
from barcode_label_automation.templates import tspl_media_commands


def make_app(tmp_path):
    parser=ConfigParser(interpolation=None)
    parser.read_dict(DEFAULTS)
    parser.set('printer','brand','tsc')
    parser.set('printer','mode','network')
    parser.set('printer','ip','127.0.0.1')
    path=tmp_path/'config.ini'
    write_config_atomic(path,parser)
    return SettingsApp(path),path


def settle(app):
    for _ in range(4):
        app.update_idletasks()
        app.update()


def test_bixolon_standard_offsets_are_visible_without_expansion(tmp_path):
    app, path = make_app(tmp_path)
    try:
        app.brand_var.set(BRAND_LABELS['bixolon'])
        app._sync_media_handling_state()
        settle(app)
        assert not hasattr(app, '_device_media_button')
        assert not hasattr(app, '_extended_stop_check')
        assert not app.media_handling_buttons['printer_default'].winfo_ismapped()
        assert app._advanced_offset_widgets[1].winfo_ismapped()
        assert '-12~12mm' in app._advanced_offset_hint.cget('text')
        app.feed_offset_var.set('12')
        from barcode_label_automation.settings_app import save_settings
        save_settings(path, app._collect_settings())
        assert load_config(path).label.feed_offset_mm == 12
        app.feed_offset_var.set('12.1')
        with pytest.raises(ValueError, match='범위'):
            app._collect_settings()
    finally:
        app.destroy()


@pytest.mark.parametrize('scale',[1,1.25,1.5,2])
def test_media_settings_footer_and_draft_preview_in_small_window(tmp_path,monkeypatch,scale):
    # Font scaling exercises widget layout; it is not a claim of changing
    # or verifying the Windows desktop's actual DPI setting.
    app,path=make_app(tmp_path)
    try:
        app.tk.call('tk','scaling',4/3*scale)
        style=ttk.Style(app)
        for name in ('TLabel','TEntry','TCombobox','TButton','Hint.TLabel'):
            style.configure(name,font=('Malgun Gothic',round(10*scale)))
        app.geometry('1024x740+20+20')
        app.width_var.set('50.5')
        app.height_var.set('30.25')
        app.offset_x_var.set('1.25')
        app.offset_y_var.set('-0.5')
        app.print_orientation_var.set(PRINT_ORIENTATION_LABELS['landscape'])
        settle(app)
        for button in (app._footer_save_button,app._cancel_button):
            assert button.winfo_ismapped()
            assert button.winfo_rooty()+button.winfo_height() <= app.winfo_rooty()+app.winfo_height()
            assert button.winfo_rootx()+button.winfo_width() <= app.winfo_rootx()+app.winfo_width()
        before=path.read_bytes()
        app._show_media_preview()
        settle(app)
        dialogs=[w for w in app.winfo_children() if isinstance(w,tk.Toplevel)]
        assert len(dialogs)==1
        assert dialogs[0].title()=='방향·위치 미리보기'
        dialogs[0].destroy()
        assert path.read_bytes()==before
        monkeypatch.setattr('barcode_label_automation.settings_app.messagebox.askyesno',lambda *a,**kw:True)
        app._confirm_close()
        assert path.read_bytes()==before
    finally:
        try:app.destroy()
        except tk.TclError:pass


def test_settings_save_decimal_direction_offsets_and_invalid_draft(tmp_path,monkeypatch):
    app,path=make_app(tmp_path)
    try:
        messages=[]
        monkeypatch.setattr('barcode_label_automation.settings_app.messagebox.showinfo',lambda *a,**kw:None)
        monkeypatch.setattr('barcode_label_automation.settings_app.messagebox.showerror',lambda *a,**kw:messages.append(a))
        monkeypatch.setattr('barcode_label_automation.settings_app.messagebox.showwarning',lambda *a,**kw:messages.append(a))
        app.width_var.set('101.6');app.height_var.set('152.4')
        app.offset_x_var.set('-1.25');app.offset_y_var.set('0.75')
        app.print_orientation_var.set(PRINT_ORIENTATION_LABELS['landscape_180'])
        app.gap_offset_var.set('0.25');app.feed_offset_var.set('0')
        app.save_to_file()
        config=load_config(path)
        assert (config.label.width_mm,config.label.height_mm)==(101.6,152.4)
        assert config.printer.print_orientation=='landscape_180'
        assert (config.label.offset_x_mm,config.label.offset_y_mm)==(-1.25,.75)
        assert config.label.gap_offset_mm==.25 and config.label.feed_offset_mm==0
        before=path.read_bytes()
        app.width_var.set('nan');app.save_to_file()
        assert messages and path.read_bytes()==before
    finally:
        app.destroy()


@pytest.mark.parametrize('brand,gap,feed',[('bixolon','-1.25','1.5'),('zebra','현재 프린터 설정 사용','-1.5')])
def test_non_tsc_offset_inputs_are_enabled_saved_and_drafts_survive_brand_switch(tmp_path,monkeypatch,brand,gap,feed):
    app,path=make_app(tmp_path)
    try:
        app.brand_var.set(BRAND_LABELS[brand])
        advanced=app._advanced_offset_container
        advanced.grid(row=10,column=0,columnspan=4,sticky='ew')
        settle(app)
        sensor,stop=app._advanced_offset_widgets
        assert str(stop.cget('state'))=='normal' and stop.winfo_ismapped()
        assert sensor.winfo_ismapped()==(brand=='bixolon')
        app.gap_offset_var.set(gap);app.feed_offset_var.set(feed)
        assert app.gap_offset_var.get()==gap and app.feed_offset_var.get()==feed
        before=path.read_bytes()
        app.brand_var.set(BRAND_LABELS['tsc'])
        assert app.feed_offset_var.get()=='현재 프린터 설정 사용'
        app.brand_var.set(BRAND_LABELS[brand])
        assert (app.gap_offset_var.get(),app.feed_offset_var.get())==(gap,feed)
        assert path.read_bytes()==before
        monkeypatch.setattr('barcode_label_automation.settings_app.messagebox.showinfo',lambda *a,**kw:None)
        app.save_to_file()
        config=load_config(path)
        assert config.printer.brand==brand
        assert config.label.feed_offset_mm==float(feed)
        assert config.label.gap_offset_mm==(float(gap) if brand=='bixolon' else None)
        # Changing DPI updates the hint without destroying a typed value.
        app.dpi_var.set('600')
        assert app.feed_offset_var.get()==feed
        assert '600' in app._advanced_offset_hint.cget('text') if brand=='zebra' else '-4.2~4.2mm' in app._advanced_offset_hint.cget('text')
    finally:
        app.destroy()


def test_tsc_black_mark_distance_is_visible_saved_and_generates_bline(tmp_path,monkeypatch):
    app,path=make_app(tmp_path)
    try:
        app.media_type_var.set(MEDIA_TYPE_LABELS['black_mark'])
        settle(app)
        sensor,stop=app._advanced_offset_widgets
        assert sensor.winfo_ismapped()
        assert app._advanced_offset_labels[0].cget('text')=='감지 후 추가 배출(mm)'
        app.gap_offset_var.set('4.5')
        app.feed_offset_var.set('현재 프린터 설정 사용')
        monkeypatch.setattr('barcode_label_automation.settings_app.messagebox.showinfo',lambda *a,**kw:None)
        app.save_to_file()
        config=load_config(path)
        assert config.label.media_type=='black_mark'
        assert config.label.gap_offset_mm==4.5
        assert tspl_media_commands(config.label.gap_mm,'black_mark',config.label.gap_offset_mm) == (
            'BLINE 3 mm,4.5 mm\n'
        )
        assert str(stop.cget('state'))=='normal'
    finally:
        app.destroy()


def test_old_bixolon_disabled_zero_loads_as_inherit_but_explicit_new_zero_resets(tmp_path):
    parser=ConfigParser(interpolation=None);parser.read_dict(DEFAULTS)
    parser.set('printer','brand','bixolon');parser.set('printer','mode','network')
    parser.set('printer','ip','127.0.0.1');parser.set('label','gap_offset_mm','0')
    path=tmp_path/'config.ini';write_config_atomic(path,parser)
    before=path.read_bytes();app=SettingsApp(path)
    try:
        assert app.gap_offset_var.get()=='별도 보정 없음'
        assert not app._settings_dirty and path.read_bytes()==before
        app.gap_offset_var.set('0');app.save_to_file()
        assert load_config(path).label.gap_offset_mm==0
    finally:
        app.destroy()
