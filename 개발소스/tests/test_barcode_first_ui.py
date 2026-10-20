"""Actual Tk regression checks for the barcode-first editor and canvas handles.

Run each test in a fresh process through the release verifier, as with the
existing native GUI modules. No test connects to or transmits to a printer.
"""
from __future__ import annotations

from copy import deepcopy
import json
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import pytest

from barcode_label_automation import label_designer_app as designer
from barcode_label_automation.templates import mm_to_dots


def descendants(parent):
    widgets = []
    for child in parent.winfo_children():
        widgets.append(child)
        widgets.extend(descendants(child))
    return widgets


def settle(app):
    app.update_idletasks()
    app.update()
    app.update_idletasks()


def widget_with_text(window, text, kind=None):
    for widget in descendants(window):
        if kind is not None and not isinstance(widget, kind):
            continue
        try:
            if str(widget.cget("text")) == text:
                return widget
        except tk.TclError:
            continue
    raise AssertionError(f"편집 UI에서 {text!r}를 찾을 수 없습니다.")


def field(window, text):
    label = widget_with_text(window, text, ttk.Label)
    info = label.grid_info()
    row, column = int(info["row"]), int(info["column"])
    siblings = [widget for widget in label.master.winfo_children()
                if isinstance(widget, (ttk.Entry, ttk.Combobox, ttk.Spinbox))]
    for candidate in siblings:
        placement = candidate.grid_info()
        if int(placement.get("row", -1)) == row and int(placement.get("column", -1)) > column:
            return candidate
    for candidate in siblings:
        placement = candidate.grid_info()
        if int(placement.get("row", -1)) == row + 1 and int(placement.get("column", -1)) == column:
            return candidate
    raise AssertionError(f"{text!r} 입력란을 찾을 수 없습니다.")


def set_field(app, window, text, value):
    control = field(window, text)
    if isinstance(control, ttk.Combobox):
        control.set(str(value))
        control.event_generate("<<ComboboxSelected>>")
    else:
        variable = str(control.cget("textvariable"))
        assert variable, f"{text!r} 입력란에 실제 편집 변수가 없습니다."
        app.setvar(variable, str(value))
    settle(app)
    return control


def open_editor(app, element):
    app.open_element_editor(element)
    settle(app)
    editor = next(widget for widget in descendants(app)
                if isinstance(widget, tk.Toplevel) and widget.title() in {"요소 편집", "바코드 속성"})
    return editor


def install_element(app, *, legacy=False):
    element = designer._element("barcode", "ABC001", 2, 2, 44, 24,
                                barcode_type="qr", font_size=10)
    element["barcode_options"].update(human_readable=False, quiet_zone=0)
    if legacy:
        element.pop("barcode_layout", None)
    else:
        element["barcode_layout"] = {
            "version": 2, "size_mode": "size", "symbol_width_mm": 10.0,
            "symbol_height_mm": 10.0, "hri_position": "right",
            "hri_gap_mm": 1.0, "hri_font_mode": "auto",
        }
    app.elements = [element]
    app.selected_id = str(element["id"])
    app.selected_ids = {str(element["id"])}
    app._reset_history()
    app.redraw()
    settle(app)
    return element


def rendered_symbol(element, dpi=203):
    return designer._render_engine_barcode_box(
        "qr", str(element["text"]), mm_to_dots(float(element["width"]), dpi),
        mm_to_dots(float(element["height"]), dpi), dict(element, _render_dpi=dpi),
    )


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(designer, "_available_font_names", lambda _root: ["Malgun Gothic"])
    monkeypatch.setattr(designer.LabelDesignerApp, "_offer_start_dialog", lambda _self: None)
    monkeypatch.setattr(designer.LabelDesignerApp, "_offer_recovery", lambda _self: None)
    messages = []
    for name in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(designer.messagebox, name,
                            lambda *args, **kwargs: messages.append(args))
    window = designer.LabelDesignerApp(tmp_path, register_file_association=False)
    window.geometry("1366x768+10+10")
    window._recovery_prompt_pending = False
    settle(window)
    window._qa_messages = messages
    try:
        yield window
    finally:
        window.destroy()


def test_new_matrix_defaults_to_size_first_but_one_d_keeps_existing_layout(app):
    app.add_barcode_element("qr")
    matrix = app.elements[-1]
    assert matrix["barcode_layout"]["version"] == 2
    assert matrix["barcode_layout"]["size_mode"] == "size"
    assert matrix["barcode_layout"]["symbol_width_mm"] > 0
    app.add_barcode_element("code128")
    assert "barcode_layout" not in app.elements[-1]


def test_element_editor_opens_serial_settings_and_cancel_restores_rule_and_binding(app):
    element = designer._element("text", "고정 문구", 2, 2, 25, 8)
    app.elements = [element]
    app.selected_id = str(element["id"])
    app.selected_ids = {str(element["id"])}
    app._reset_history()
    original_element = deepcopy(element)
    original_rules = deepcopy(app.template.get("value_rules", []))

    editor = open_editor(app, element)
    widget_with_text(editor, "일련화 설정…", ttk.Button).invoke()
    settle(app)
    dialog = next(widget for widget in descendants(editor)
                  if isinstance(widget, tk.Toplevel) and widget.title() == "값 생성 규칙 · 번호 / 날짜 / 문자")
    variables = dialog._value_rules_variables
    rule_name = variables["name"].get()
    assert rule_name.startswith("일련번호")
    variables["start"].set("7")
    variables["digits"].set("3")
    variables["copies_per_value"].set("2")
    variables["direction"].set("감소")
    dialog._value_rules_apply()
    settle(app)
    assert app.template["value_rules"][0]["direction"] == "down"
    assert element["field"] == rule_name
    assert element["text"] == "{{" + rule_name + "}}"
    assert app.preview_row[rule_name] == "007"
    widget_with_text(editor, "취소", ttk.Button).invoke()
    settle(app)
    assert element == original_element
    assert app.template.get("value_rules", []) == original_rules


def test_element_editor_serial_settings_commit_to_template_on_confirm(app):
    element = designer._element("text", "고정 문구", 2, 2, 25, 8)
    app.elements = [element]
    app.selected_id = str(element["id"])
    app.selected_ids = {str(element["id"])}
    app._reset_history()
    editor = open_editor(app, element)
    widget_with_text(editor, "일련화 설정…", ttk.Button).invoke()
    settle(app)
    dialog = next(widget for widget in descendants(editor)
                  if isinstance(widget, tk.Toplevel) and widget.title() == "값 생성 규칙 · 번호 / 날짜 / 문자")
    variables = dialog._value_rules_variables
    variables["alphabet"].set("영문 대문자")
    settle(app)
    rule_name = variables["name"].get()
    assert variables["start"].get() == "A"
    assert variables["width_mode"].get() == "자동 자리수"
    dialog._value_rules_apply()
    settle(app)
    widget_with_text(editor, "확인", ttk.Button).invoke()
    settle(app)
    assert element["field"] == rule_name
    assert app.template["value_rules"][0]["alphabet"] == "uppercase"
    assert app.template["value_rules"][0]["preserve_width"] is False


def test_barcode_editor_serial_settings_generate_preview_and_confirm(app):
    element = install_element(app)
    editor = open_editor(app, element)
    widget_with_text(editor, "일련화 설정…", ttk.Button).invoke()
    settle(app)
    dialog = next(widget for widget in descendants(editor)
                  if isinstance(widget, tk.Toplevel) and widget.title() == "값 생성 규칙 · 번호 / 날짜 / 문자")
    rule_name = dialog._value_rules_variables["name"].get()
    dialog._value_rules_apply()
    settle(app)
    assert app.preview_row[rule_name] == "000001"
    assert editor._barcode_preview_panel.result["value"] == "000001"
    widget_with_text(editor, "확인", ttk.Button).invoke()
    settle(app)
    assert element["field"] == rule_name
    assert app.template["value_rules"][0]["name"] == rule_name


def test_actual_editor_changes_symbol_size_then_places_hri_without_shrinking(app):
    element = install_element(app)
    original = deepcopy(element)
    editor = open_editor(app, element)
    draft = editor._barcode_draft
    widget_with_text(editor, "2D 크기·문자 배치")
    assert field(editor, "크기 방식").get() == "바코드 크기 우선"
    set_field(app, editor, "바코드 가로(mm)", 12)
    set_field(app, editor, "바코드 세로(mm)", 12)
    before = rendered_symbol(draft)
    assert draft["barcode_layout"]["symbol_width_mm"] == pytest.approx(12)
    assert draft["barcode_layout"]["symbol_height_mm"] == pytest.approx(12)
    assert element == original
    editor._barcode_show_page("hri")
    widget_with_text(editor, "바코드 값 표시", ttk.Checkbutton).invoke()
    settle(app)
    with_text = rendered_symbol(draft)
    assert draft["barcode_options"]["human_readable"] is True
    assert element == original
    assert with_text.info["symbol_bounds"] == before.info["symbol_bounds"]
    assert with_text.info["module_dots"] == before.info["module_dots"]
    set_field(app, editor, "문자 위치", "아래")
    set_field(app, editor, "문자 간격(mm)", 1.5)
    set_field(app, editor, "문자 크기", "지정 크기")
    assert draft["barcode_layout"]["hri_position"] == "below"
    assert draft["barcode_layout"]["hri_gap_mm"] == pytest.approx(1.5)
    assert draft["barcode_layout"]["hri_font_mode"] == "fixed"
    below = rendered_symbol(draft)
    assert below.info["symbol_bounds"] == before.info["symbol_bounds"]
    assert below.info["module_dots"] == before.info["module_dots"]
    widget_with_text(editor, "실제 크기 확인", ttk.Button).invoke()
    settle(app)
    assert editor.winfo_exists()
    widget_with_text(editor, "적용", ttk.Button).invoke()
    settle(app)
    assert element["barcode_layout"] == draft["barcode_layout"]
    assert element["barcode_options"]["human_readable"] is True
    widget_with_text(editor, "확인", ttk.Button).invoke()
    settle(app)
    assert not editor.winfo_exists()


def test_legacy_editor_preserves_layout_until_explicit_conversion_and_undo(app):
    element = install_element(app, legacy=True)
    before = deepcopy(element)
    editor = open_editor(app, element)
    assert field(editor, "크기 방식").get() == "기존 배치"
    assert "barcode_layout" not in element
    widget_with_text(editor, "취소", ttk.Button).invoke()
    settle(app)
    assert "barcode_layout" not in element
    assert element["width"] == before["width"] and element["height"] == before["height"]
    editor = open_editor(app, element)
    set_field(app, editor, "크기 방식", "바코드 크기 우선")
    draft = editor._barcode_draft
    assert draft["barcode_layout"]["version"] == 2
    assert (draft["width"],draft["height"]) != (before["width"],before["height"])
    assert draft["width"] > 0 and draft["height"] > 0
    assert element == before
    widget_with_text(editor, "적용", ttk.Button).invoke()
    settle(app)
    assert element["barcode_layout"]["version"] == 2
    widget_with_text(editor, "확인", ttk.Button).invoke()
    settle(app)
    app.undo()
    settle(app)
    assert "barcode_layout" not in app.elements[0]
    app.redo()
    settle(app)
    assert app.elements[0]["barcode_layout"]["version"] == 2


def test_module_fixed_editor_has_no_canvas_size_handles(app):
    element = install_element(app)
    original = deepcopy(element)
    editor = open_editor(app, element)
    set_field(app, editor, "크기 방식", "모듈 크기 고정")
    draft = editor._barcode_draft
    assert draft["barcode_layout"]["size_mode"] == "module"
    assert int(draft["barcode_options"]["cell_size"]) >= 1
    assert element == original
    widget_with_text(editor, "적용", ttk.Button).invoke()
    settle(app)
    assert element["barcode_layout"]["size_mode"] == "module"
    widget_with_text(editor, "확인", ttk.Button).invoke()
    settle(app)
    app.redraw()
    settle(app)
    assert element != original
    assert not app.canvas.find_withtag("resize-handle")
    for _name, x, y in app._resize_handle_points(*app.element_bbox(element)):
        assert app.resize_handle_at(x, y, element) is None


@pytest.mark.parametrize("invalid", ["", "nan", "1.5"])
def test_invalid_module_entry_can_be_corrected_without_sticking_editor(app, invalid):
    element = install_element(app)
    original = deepcopy(element)
    callback_errors = []
    app.report_callback_exception = lambda *error: callback_errors.append(error)
    editor = open_editor(app, element)
    set_field(app, editor, "크기 방식", "모듈 크기 고정")
    draft = editor._barcode_draft
    before = deepcopy(draft)
    set_field(app, editor, "셀 크기(dot, 0=자동)", invalid)
    assert callback_errors == []
    assert draft["barcode_options"]["cell_size"] == before["barcode_options"]["cell_size"]
    assert draft["barcode_layout"] == before["barcode_layout"]
    assert element == original
    set_field(app, editor, "셀 크기(dot, 0=자동)", 2)
    assert draft["barcode_options"]["cell_size"] == 2
    set_field(app, editor, "문자 간격(mm)", 1.75)
    assert draft["barcode_layout"]["hri_gap_mm"] == pytest.approx(1.75)
    set_field(app, editor, "문자 위치", "아래")
    assert draft["barcode_layout"]["hri_position"] == "below"
    assert rendered_symbol(draft).info["module_dots"] == 2
    assert callback_errors == []
    widget_with_text(editor, "취소", ttk.Button).invoke()
    settle(app)
    assert element == original


def test_size_handles_target_code_box_and_drag_recalculates_group_dimensions(app):
    element = install_element(app)
    image = rendered_symbol(element)
    symbol_width_mm, symbol_height_mm = image.info["actual_symbol_mm"]
    x1, y1, x2, y2 = app.element_bbox(element)
    symbol_x2 = x1 + symbol_width_mm * app.scale
    symbol_y2 = y1 + symbol_height_mm * app.scale
    assert app.resize_handle_at(symbol_x2, symbol_y2, element) == "se"
    assert app.resize_handle_at(x2, y2, element) is None
    before = deepcopy(element)
    start = SimpleNamespace(x=symbol_x2, y=symbol_y2, state=0)
    app.on_canvas_press(start)
    assert app.drag_state and app.drag_state["handle"] == "se"
    app.on_canvas_drag(SimpleNamespace(x=symbol_x2 + 2 * app.scale,
                                       y=symbol_y2 + 2 * app.scale, state=0))
    app.on_canvas_release(start)
    settle(app)
    assert element["barcode_layout"]["symbol_width_mm"] > before["barcode_layout"]["symbol_width_mm"]
    assert element["barcode_layout"]["symbol_height_mm"] > before["barcode_layout"]["symbol_height_mm"]
    assert element["width"] < before["width"] and element["height"] < before["height"]
    assert element["x"] == before["x"] and element["y"] == before["y"]
    app.undo()
    settle(app)
    assert app.elements[0]["barcode_layout"] == before["barcode_layout"]


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotated_code_handle_grows_right_and_down_with_anchored_symbol_origin(app, rotation):
    app.template["label"].update(width_mm=80, height_mm=60)
    app._load_values_to_controls()
    element = install_element(app)
    element.update(x=10.0, y=10.0, width=20.0, height=20.0, rotation=rotation)
    app._reset_history()
    app.redraw()
    settle(app)
    before = deepcopy(element)
    bounds = app._barcode_canvas_bounds(element)
    assert bounds is not None
    left, top, right, bottom = bounds
    assert app.resize_handle_at(right, bottom, element) == "se"
    start = SimpleNamespace(x=right, y=bottom, state=0)
    app.on_canvas_press(start)
    assert app.drag_state and app.drag_state["handle"] == "se"
    app.on_canvas_drag(SimpleNamespace(x=right + 3 * app.scale,
                                       y=bottom + 3 * app.scale, state=0))
    app.on_canvas_release(start)
    settle(app)
    after = app._barcode_canvas_bounds(element)
    assert after is not None
    assert after[0] == pytest.approx(left, abs=0.01)
    assert after[1] == pytest.approx(top, abs=0.01)
    assert after[2] > right
    assert after[3] > bottom
    assert element["width"] != before["width"] or element["height"] != before["height"]
    assert element["rotation"] == rotation
    assert 0 <= element["x"] <= 80 - element["width"]
    assert 0 <= element["y"] <= 60 - element["height"]
    app.undo()
    settle(app)
    restored = app.elements[0]
    assert restored["x"] == before["x"] and restored["y"] == before["y"]
    assert restored["barcode_layout"] == before["barcode_layout"]


def test_editor_metadata_survives_save_reload_and_unsaved_recovery(app, tmp_path):
    element = install_element(app)
    original = deepcopy(element)
    editor = open_editor(app, element)
    draft = editor._barcode_draft
    set_field(app, editor, "바코드 가로(mm)", 11)
    set_field(app, editor, "바코드 세로(mm)", 11)
    set_field(app, editor, "문자 위치", "아래")
    set_field(app, editor, "문자 간격(mm)", 2)
    expected = deepcopy(draft["barcode_layout"])
    assert element == original
    app._save_recovery()
    recovery = json.loads(app._recovery_path().read_text(encoding="utf-8"))
    assert recovery["snapshot"]["elements"][0] == original
    widget_with_text(editor, "적용", ttk.Button).invoke()
    settle(app)
    assert element["barcode_layout"] == expected
    widget_with_text(editor, "확인", ttk.Button).invoke()
    settle(app)
    app._save_recovery()
    recovery = json.loads(app._recovery_path().read_text(encoding="utf-8"))
    assert recovery["snapshot"]["elements"][0]["barcode_layout"] == expected
    path = tmp_path / "barcode-first.cllabel"
    path.write_text(json.dumps(app.template_payload(), ensure_ascii=False), encoding="utf-8")
    loaded = designer.load_template_file(path)
    assert loaded["elements"][0]["barcode_layout"] == expected
    assert loaded["elements"][0]["width"] == element["width"]
    assert loaded["elements"][0]["height"] == element["height"]


@pytest.mark.parametrize("scaling", [1.33333, 2.0, 2.66667])
def test_size_first_editor_actions_stay_accessible_at_display_scaling(app, scaling):
    app.tk.call("tk", "scaling", scaling)
    element = install_element(app)
    editor = open_editor(app, element)
    editor.geometry("760x640+20+20")
    settle(app)
    controls = [field(editor, "크기 방식"), widget_with_text(editor, "실제 크기 확인", ttk.Button)]
    for control in controls:
        assert control.winfo_ismapped()
        assert editor.winfo_rootx() <= control.winfo_rootx()
        assert control.winfo_rootx() + control.winfo_width() <= editor.winfo_rootx() + editor.winfo_width()
    assert "바코드 크기 우선" in field(editor, "크기 방식").cget("values")
