import tkinter as tk

import pytest

from barcode_label_automation.value_rules_dialog import edit_value_rules


@pytest.fixture
def root():
    window = tk.Tk()
    window.withdraw()
    yield window
    window.destroy()


def test_edit_then_apply_commits_current_draft(root):
    applied = []
    original = [{"name": "번호", "kind": "serial", "start": 1, "digits": 4}]
    window = edit_value_rules(root, original, ["품번"], applied.append, sample_row={"품번": "001"})
    root.update()
    window._value_rules_variables["start"].set("12")
    window._value_rules_apply()
    assert applied[0][0]["start"] == 12
    assert original[0]["start"] == 1


def test_cancel_never_calls_apply(root):
    applied = []
    window = edit_value_rules(root, [], [], applied.append)
    root.update()
    window._value_rules_variables["name"].set("번호")
    window.destroy()
    assert applied == []


def test_new_unadded_draft_blocks_apply(root):
    applied = []
    window = edit_value_rules(root, [], [], applied.append)
    root.update()
    window._value_rules_variables["name"].set("번호")
    window._value_rules_apply()
    assert applied == []
    assert "추가" in window._value_rules_status.get()
    window.destroy()


def test_invalid_draft_and_kind_switch_are_safe(root):
    applied = []
    window = edit_value_rules(root, [{"name": "번호", "kind": "serial"}], [], applied.append)
    root.update()
    window._value_rules_variables["step"].set("0")
    window._value_rules_apply()
    assert not applied
    assert "증가량" in window._value_rules_status.get()
    window._value_rules_variables["kind"].set("날짜 / 기한")
    window._value_rules_variables["offset_days"].set("30")
    root.update()
    window._value_rules_apply()
    assert applied[0][0]["kind"] == "date"
    assert applied[0][0]["offset_days"] == 30


def test_selection_changes_do_not_reuse_another_rules_defaults(root):
    applied = []
    window = edit_value_rules(root, [{"name": "먼저", "kind": "serial", "start": 99}, {"name": "다음", "kind": "serial"}], [], applied.append)
    root.update()
    window._value_rules_table.selection_set("1")
    root.update()
    assert window._value_rules_variables["name"].get() == "다음"
    assert window._value_rules_variables["start"].get() == "1"
    window._value_rules_variables["start"].set("3")
    window._value_rules_table.selection_set("0")
    root.update()
    window._value_rules_apply()
    assert applied[0][0]["start"] == 99
    assert applied[0][1]["start"] == 3


def test_preview_commits_draft_locally_without_external_callback(root):
    applied = []
    window = edit_value_rules(root, [{"name": "번호", "kind": "serial", "start": 1}], [], applied.append)
    root.update()
    window._value_rules_variables["start"].set("5")
    window._value_rules_preview()
    assert applied == []
    assert "번호를 소비하지" in window._value_rules_status.get()
    window._value_rules_apply()
    assert applied[0][0]["start"] == 5
