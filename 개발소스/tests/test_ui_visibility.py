from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

import pytest

from barcode_label_automation import label_designer_app, label_manager_app, settings_app, ui_window
from barcode_label_automation.settings_app import PrinterSettings, save_settings


WORK_AREA = ui_window.WorkArea(0, 0, 1024, 768)
EXPECTED_CLIENT_SIZE = (976, 720)


def _descendants(parent: tk.Misc) -> list[tk.Misc]:
    widgets: list[tk.Misc] = []
    for child in parent.winfo_children():
        widgets.append(child)
        widgets.extend(_descendants(child))
    return widgets


def _widgets_with_text(parent: tk.Misc, text: str) -> list[tk.Misc]:
    matches: list[tk.Misc] = []
    for widget in _descendants(parent):
        try:
            if str(widget.cget("text")) == text:
                matches.append(widget)
        except tk.TclError:
            continue
    return matches


def _window_with_title(parent: tk.Misc, title: str) -> tk.Toplevel:
    for widget in _descendants(parent):
        if isinstance(widget, tk.Toplevel) and widget.title() == title:
            return widget
    raise AssertionError(f"창을 찾을 수 없습니다: {title}")


def _settle(window: tk.Misc) -> None:
    window.update_idletasks()
    window.update()
    window.update_idletasks()


def _assert_visible_inside(window: tk.Misc, *widgets: tk.Misc) -> None:
    _settle(window)
    left = window.winfo_rootx()
    top = window.winfo_rooty()
    right = left + window.winfo_width()
    bottom = top + window.winfo_height()

    for widget in widgets:
        widget_left = widget.winfo_rootx()
        widget_top = widget.winfo_rooty()
        widget_right = widget_left + widget.winfo_width()
        widget_bottom = widget_top + widget.winfo_height()
        assert widget.winfo_ismapped(), f"{widget!s} is not mapped"
        assert left <= widget_left < widget_right <= right, (
            f"{widget!s} horizontal bounds {(widget_left, widget_right)} exceed {(left, right)}"
        )
        assert top <= widget_top < widget_bottom <= bottom, (
            f"{widget!s} vertical bounds {(widget_top, widget_bottom)} exceed {(top, bottom)}"
        )


def _assert_text_not_clipped(*widgets: tk.Misc) -> None:
    for widget in widgets:
        widget.update_idletasks()
        text = str(widget.cget("text"))
        style_name = str(widget.cget("style")) or widget.winfo_class()
        font_spec = ttk.Style(widget).lookup(style_name, "font")
        text_width = tkfont.Font(root=widget, font=font_spec).measure(text)
        assert widget.winfo_width() >= text_width + 24, (
            f"{widget!s} width {widget.winfo_width()} cannot fit {text!r} "
            f"({text_width}px text plus padding)"
        )


def _only_widget(window: tk.Misc, text: str) -> tk.Misc:
    matches = _widgets_with_text(window, text)
    assert len(matches) == 1, f"expected one {text!r} widget, found {len(matches)}"
    return matches[0]


@pytest.fixture
def large_font_work_area(monkeypatch: pytest.MonkeyPatch) -> None:
    original_tk_init = tk.Tk.__init__

    def scaled_tk_init(self: tk.Tk, *args: object, **kwargs: object) -> None:
        original_tk_init(self, *args, **kwargs)
        self.tk.call("tk", "scaling", 2.0)  # 144 DPI, equivalent to Windows 150%.

    monkeypatch.setattr(tk.Tk, "__init__", scaled_tk_init)
    monkeypatch.setattr(ui_window, "_primary_work_area", lambda _window: WORK_AREA)


def test_settings_and_manager_actions_stay_visible_at_150_percent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    large_font_work_area: None,
) -> None:
    config_path = tmp_path / "config.ini"
    save_settings(
        config_path,
        PrinterSettings(
            brand="tsc",
            mode="network",
            print_method="direct_thermal",
            ip="192.168.0.10",
            port=9100,
            windows_printer_name="auto",
            width_mm=60,
            height_mm=40,
            dpi=203,
            gap_mm=3,
        ),
    )
    monkeypatch.setattr(settings_app, "installed_printers", lambda: [])
    monkeypatch.setattr(settings_app, "load_header_logo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(settings_app, "apply_window_icon", lambda *_args, **_kwargs: None)
    app = settings_app.SettingsApp(config_path)
    try:
        app.wait_window = lambda _window: None  # type: ignore[method-assign]
        app.db_headers = tuple(label_manager_app.DB_HEADERS)  # type: ignore[attr-defined]
        _settle(app)
        assert (app.winfo_width(), app.winfo_height()) == EXPECTED_CLIENT_SIZE
        label_manager_app.LabelManagerApp._configure_style(app)

        matches = [
            (0, {header: f"첫째 {header}" for header in app.db_headers}),
            (1, {header: f"둘째 {header}" for header in app.db_headers}),
        ]
        label_manager_app.LabelManagerApp._choose_db_matches(app, "중복값", matches)
        duplicate_dialog = _window_with_title(app, "중복 DB 항목 선택")
        _assert_visible_inside(
            duplicate_dialog,
            _only_widget(duplicate_dialog, "선택 메뉴"),
            _only_widget(duplicate_dialog, "취소"),
            _only_widget(duplicate_dialog, "확인"),
        )
        duplicate_dialog.destroy()

        label_manager_app.LabelManagerApp.ask_print_quantity(app, default_quantity=1)
        quantity_dialog = _window_with_title(app, "인쇄 매수 선택")
        _assert_visible_inside(
                quantity_dialog,
                _only_widget(quantity_dialog, "취소"),
                _only_widget(quantity_dialog, "인쇄 시작"),
            )
        quantity_dialog.destroy()

        settings_app.SettingsApp._configure_style(app)
        _settle(app)
        check_buttons = _widgets_with_text(app, "설정 점검")
        save_buttons = _widgets_with_text(app, "설정 저장")
        assert check_buttons and save_buttons
        bottom_check = max(check_buttons, key=lambda widget: widget.winfo_rooty())
        bottom_save = max(save_buttons, key=lambda widget: widget.winfo_rooty())
        assert isinstance(bottom_check, ttk.Button)
        assert isinstance(bottom_save, ttk.Button)
        _assert_visible_inside(app, bottom_check, bottom_save)
    finally:
        app.destroy()


def test_designer_dialog_actions_stay_visible_at_150_percent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    large_font_work_area: None,
) -> None:
    monkeypatch.setattr(label_designer_app, "load_header_logo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(label_designer_app, "apply_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(label_designer_app.LabelDesignerApp, "_apply_window_icon", lambda _self: None)
    monkeypatch.setattr(label_designer_app, "_available_font_names", lambda _root: ["Malgun Gothic"])
    app = label_designer_app.LabelDesignerApp(tmp_path)
    try:
        app.wait_window = lambda _window: None  # type: ignore[method-assign]
        _settle(app)
        assert (app.winfo_width(), app.winfo_height()) == EXPECTED_CLIENT_SIZE
        tool_action_labels = (
            "텍스트",
            "여러 줄",
            "1D 바코드",
            "2D 코드",
            "그림",
            "도안 불러오기",
            "도안 적용",
            "박스",
            "선",
            "표",
        )
        main_action_labels = (
            "상품 엑셀 연결",
            "상품 선택",
            "프린터 설정",
            "인쇄파일 생성",
            "새 라벨",
            "열기",
            "저장",
        )
        main_actions: list[tk.Misc] = []
        for text in main_action_labels:
            matches = _widgets_with_text(app, text)
            assert matches, f"메뉴를 찾을 수 없습니다: {text}"
            main_actions.extend(matches)
        _assert_visible_inside(app, *main_actions)
        _assert_text_not_clipped(*main_actions)
        tools_canvas = next(
            widget for widget in _descendants(app._tools_card)
            if isinstance(widget, tk.Canvas)
        )
        scroll_height = max(1, tools_canvas.bbox("all")[3])
        for text in tool_action_labels:
            matches = _widgets_with_text(app, text)
            assert matches, f"도구를 찾을 수 없습니다: {text}"
            button = matches[0]
            tools_canvas.yview_moveto(min(1.0, max(0.0, button.winfo_y() / scroll_height - 0.1)))
            _assert_visible_inside(app, button)
            _assert_text_not_clipped(button)

        app.data_source_path = tmp_path / "barcode_db.xlsx"
        app.data_source_headers = ("barcode", "item_name")
        app.db_rows = [{"barcode": "001234", "item_name": "대형 글꼴 테스트"}]
        app.preview_row = app.db_rows[0]
        app.open_data_source_window()
        data_dialog = _window_with_title(app, "데이터 소스 선택")
        _assert_visible_inside(
            data_dialog,
            _only_widget(data_dialog, "전체 선택"),
            _only_widget(data_dialog, "선택 해제"),
            _only_widget(data_dialog, "새로고침"),
            _only_widget(data_dialog, "선택 완료"),
        )
        app.close_data_source_window()

        app.open_template_window()
        template_dialog = _window_with_title(app, "파일")
        _assert_visible_inside(
            template_dialog,
            *[
                _only_widget(template_dialog, text)
                for text in (
                    "저장",
                    "다른 이름으로 저장",
                    "기존 파일 불러오기",
                    "닫기",
                )
            ],
        )
        app.close_template_window()

        app.ask_print_quantity()
        quantity_dialog = _window_with_title(app, "인쇄 매수 선택")
        _assert_visible_inside(
            quantity_dialog,
            _only_widget(quantity_dialog, "취소"),
            _only_widget(quantity_dialog, "인쇄 시작"),
        )
    finally:
        app.destroy()


def test_manager_main_workflow_actions_stay_visible_at_150_percent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    large_font_work_area: None,
) -> None:
    monkeypatch.setattr(label_manager_app, "load_header_logo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(label_manager_app, "apply_window_icon", lambda *_args, **_kwargs: None)
    app = label_manager_app.LabelManagerApp(tmp_path)
    try:
        _settle(app)
        assert (app.winfo_width(), app.winfo_height()) == EXPECTED_CLIENT_SIZE
        for text in ("DB 파일", "설정", "출력", "열기", "연결", "점검", "인쇄"):
            candidates = _widgets_with_text(app, text)
            assert candidates, f"메뉴를 찾을 수 없습니다: {text}"
            visible = [widget for widget in candidates if widget.winfo_ismapped()]
            assert visible, f"표시된 메뉴가 없습니다: {text}"
            _assert_visible_inside(app, *visible)
    finally:
        app.destroy()
