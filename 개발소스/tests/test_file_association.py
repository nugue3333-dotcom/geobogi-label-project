from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from barcode_label_automation import file_association as association
from barcode_label_automation.file_association import (
    LABEL_PROG_ID,
    LEGACY_LABEL_PROG_ID,
    PROJECT_PROG_ID,
    STABLE_ICON_DIRECTORY,
    ensure_label_file_association,
    restore_file_association,
)


class _Key:
    def __init__(self, registry, root, path):
        self.registry, self.root, self.path = registry, root, path

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _MemoryRegistry:
    """These tests never access HKCU or invoke the Shell."""
    HKEY_CURRENT_USER = 1
    HKEY_LOCAL_MACHINE = 2
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1
    REG_NONE = 0

    def __init__(self):
        self.values = {(root, r"Software\Classes"): {} for root in (1, 2)}
        self.failure_key = None

    def CreateKeyEx(self, root, path, *_args):
        parts = path.split("\\")
        for count in range(1, len(parts) + 1):
            self.values.setdefault((root, "\\".join(parts[:count])), {})
        return _Key(self, root, path)

    def OpenKey(self, root, path, *_args):
        if (root, path) not in self.values:
            raise FileNotFoundError(path)
        return _Key(self, root, path)

    def QueryValueEx(self, key, name):
        try:
            return self.values[(key.root, key.path)][name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc

    def SetValueEx(self, key, name, _reserved, value_type, value):
        if self.failure_key == key.path:
            self.failure_key = None
            raise OSError("forced registry failure")
        self.values[(key.root, key.path)][name] = (value, value_type)

    def DeleteValue(self, key, name):
        del self.values[(key.root, key.path)][name]

    def QueryInfoKey(self, key):
        prefix = key.path + "\\"
        children = {path[len(prefix):].split("\\")[0] for root, path in self.values
                    if root == key.root and path.startswith(prefix)}
        return len(children), len(self.values[(key.root, key.path)]), 0

    def DeleteKey(self, root, path):
        if any(r == root and p.startswith(path + "\\") for r, p in self.values):
            raise OSError("key still has children")
        del self.values[(root, path)]

    def put(self, path, value, *, name="", root=1):
        with self.CreateKeyEx(root, path) as key:
            self.SetValueEx(key, name, 0, self.REG_SZ, value)

    def get(self, path, name=""):
        with self.OpenKey(self.HKEY_CURRENT_USER, path) as key:
            return self.QueryValueEx(key, name)[0]


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    memory = _MemoryRegistry()
    monkeypatch.setattr(association, "winreg", memory)
    monkeypatch.setattr(association, "_notify_shell_association_changed", lambda: None)
    return memory


def _register(tmp_path):
    designer = tmp_path / "배포 폴더" / "라벨디자이너.exe"
    source = designer.parent / "assets" / "brand"
    source.mkdir(parents=True, exist_ok=True)
    designer.write_bytes(b"designer")
    label_icon = source / "label.ico"
    project_icon = source / "project.ico"
    label_icon.write_bytes(b"label-icon-v1")
    project_icon.write_bytes(b"project-icon-v1")
    return designer, ensure_label_file_association(
        designer, icon_source=label_icon, project_icon_source=project_icon,
        local_app_data=tmp_path / "Local App Data",
    )


def test_file_association_uses_stable_icons_and_quoted_designer(tmp_path, registry):
    designer, result = _register(tmp_path)
    assert result.registered, result.error
    assert result.icon_path.parent == tmp_path / "Local App Data" / STABLE_ICON_DIRECTORY
    assert result.icon_path.read_bytes() == b"label-icon-v1"
    assert result.project_icon_path.read_bytes() == b"project-icon-v1"
    for prog_id in (LABEL_PROG_ID, LEGACY_LABEL_PROG_ID):
        assert registry.get(fr"Software\Classes\{prog_id}\DefaultIcon") == f'"{result.icon_path}",0'
        assert registry.get(fr"Software\Classes\{prog_id}\shell\open\command") == f'"{designer.resolve()}" "%1"'
        assert registry.get(fr"Software\Classes\{prog_id}\shell\print\command") == f'"{designer.resolve()}" --print "%1"'
    assert registry.get(fr"Software\Classes\{PROJECT_PROG_ID}\shell\open\command") == f'"{designer.resolve()}" --import-project "%1"'
    assert not any(path.startswith(fr"Software\Classes\{PROJECT_PROG_ID}\shell\print") for _, path in registry.values)
    assert registry.get(r"Software\Classes\.cllabel") == LABEL_PROG_ID
    assert registry.get(r"Software\Classes\.gblabel") == LEGACY_LABEL_PROG_ID
    assert registry.get(r"Software\Classes\.clproject") == PROJECT_PROG_ID
    assert registry.get(r"Software\Classes\.gbproject") == PROJECT_PROG_ID


@pytest.mark.parametrize("extension, prog_id", [
    (".cllabel", LABEL_PROG_ID), (".gblabel", LEGACY_LABEL_PROG_ID),
    (".clproject", PROJECT_PROG_ID), (".gbproject", PROJECT_PROG_ID),
])
def test_file_association_preserves_other_handler_and_user_choice(tmp_path, registry, extension, prog_id):
    registry.put(fr"Software\Classes\{extension}", "OtherVendor.Label")
    choice = fr"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{extension}\UserChoice"
    registry.put(choice, "OtherVendor.Label", name="ProgId")
    _designer, result = _register(tmp_path)
    assert result.registered
    assert registry.get(fr"Software\Classes\{extension}") == "OtherVendor.Label"
    assert registry.get(choice, "ProgId") == "OtherVendor.Label"
    assert registry.get(fr"Software\Classes\{extension}\OpenWithProgids", prog_id) == b""


def test_file_association_preserves_machine_handler(tmp_path, registry):
    registry.put(r"Software\Classes\.cllabel", "Machine.Label", root=registry.HKEY_LOCAL_MACHINE)
    _designer, result = _register(tmp_path)
    assert result.registered
    assert "" not in registry.values[(registry.HKEY_CURRENT_USER, r"Software\Classes\.cllabel")]


def test_legacy_geobogi_handler_remains_openable(tmp_path, registry):
    registry.put(r"Software\Classes\.gblabel", "GeobogiDream.LabelFile")
    designer, result = _register(tmp_path)
    assert result.registered
    assert registry.get(r"Software\Classes\.gblabel") == "GeobogiDream.LabelFile"
    assert registry.get(r"Software\Classes\GeobogiDream.LabelFile\shell\open\command") == f'"{designer}" "%1"'


def test_file_association_changes_icon_path_when_content_changes(tmp_path):
    designer, first = _register(tmp_path)
    source_icon = designer.parent / "assets" / "brand" / "label.ico"
    source_icon.write_bytes(b"label-icon-v2")
    second = ensure_label_file_association(designer, icon_source=source_icon, local_app_data=tmp_path / "Local App Data")
    assert second.registered
    assert first.icon_path != second.icon_path
    assert first.icon_path.read_bytes() == b"label-icon-v1"
    assert second.icon_path.read_bytes() == b"label-icon-v2"


def test_registration_is_idempotent_and_does_not_create_extra_rollback(tmp_path):
    designer, first = _register(tmp_path)
    second = ensure_label_file_association(
        designer, icon_source=designer.parent / "assets" / "brand" / "label.ico",
        project_icon_source=designer.parent / "assets" / "brand" / "project.ico",
        local_app_data=tmp_path / "Local App Data",
    )
    assert first.rollback_path.is_file()
    assert second.registered and second.rollback_path is None
    assert len(list(first.rollback_path.parent.glob("rollback_*.json"))) == 1


def test_rollback_restores_previous_values_and_keeps_later_user_change(tmp_path, registry):
    registry.put(fr"Software\Classes\{LABEL_PROG_ID}\DefaultIcon", "old-icon")
    _designer, result = _register(tmp_path)
    registry.put(r"Software\Classes\.cllabel", "User.NewChoice")
    restored = restore_file_association(result.rollback_path)
    assert restored.registered, restored.error
    assert registry.get(fr"Software\Classes\{LABEL_PROG_ID}\DefaultIcon") == "old-icon"
    assert registry.get(r"Software\Classes\.cllabel") == "User.NewChoice"
    assert (registry.HKEY_CURRENT_USER, fr"Software\Classes\{PROJECT_PROG_ID}") not in registry.values


def test_registry_failure_rolls_back_partial_registration(tmp_path, registry):
    registry.put(fr"Software\Classes\{LABEL_PROG_ID}\DefaultIcon", "old-icon")
    before = copy.deepcopy(registry.values)
    registry.failure_key = fr"Software\Classes\{PROJECT_PROG_ID}\shell\open\command"
    _designer, result = _register(tmp_path)
    assert not result.registered
    assert "forced registry failure" in result.error
    assert registry.values == before
    assert result.rollback_path.is_file()


def test_rollback_rejects_registry_outside_owned_file_types(tmp_path, registry):
    _designer, result = _register(tmp_path)
    snapshot = json.loads(result.rollback_path.read_text(encoding="utf-8"))
    snapshot["changes"][0]["key"] = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.json\UserChoice"
    malicious = tmp_path / "untrusted.json"
    malicious.write_text(json.dumps(snapshot), encoding="utf-8")
    before = copy.deepcopy(registry.values)
    restored = restore_file_association(malicious)
    assert not restored.registered
    assert registry.values == before


def test_file_association_rejects_missing_designer(tmp_path):
    result = ensure_label_file_association(tmp_path / "missing.exe", local_app_data=tmp_path)
    assert not result.registered
    assert "찾을 수 없습니다" in result.error


def test_rollback_keeps_later_manual_open_command_change(tmp_path, registry):
    _designer, result = _register(tmp_path)
    command_key = fr"Software\Classes\{PROJECT_PROG_ID}\shell\open\command"
    registry.put(command_key, '"C:\\Other Program\\open.exe" "%1"')
    restored = restore_file_association(result.rollback_path)
    assert restored.registered, restored.error
    assert registry.get(command_key) == '"C:\\Other Program\\open.exe" "%1"'


def test_relocation_changes_quoted_commands_and_can_restore_old_location(tmp_path, registry):
    original_designer, first = _register(tmp_path)
    moved = tmp_path / "new location" / "라벨디자이너.exe"
    moved.parent.mkdir()
    moved.write_bytes(b"designer")
    result = ensure_label_file_association(moved, local_app_data=tmp_path / "Local App Data")
    assert result.registered
    command_key = fr"Software\Classes\{PROJECT_PROG_ID}\shell\open\command"
    assert registry.get(command_key) == f'"{moved.resolve()}" --import-project "%1"'
    restored = restore_file_association(result.rollback_path)
    assert restored.registered
    assert registry.get(command_key) == f'"{original_designer.resolve()}" --import-project "%1"'
    assert first.rollback_path.is_file()


def test_rollback_invalid_byte_encoding_never_mutates_registry(tmp_path, registry):
    _designer, result = _register(tmp_path)
    snapshot = json.loads(result.rollback_path.read_text(encoding="utf-8"))
    snapshot["changes"][0]["written"][0] = {"bytes": "not valid base64 @"}
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(snapshot), encoding="utf-8")
    before = copy.deepcopy(registry.values)
    restored = restore_file_association(invalid)
    assert not restored.registered
    assert registry.values == before
