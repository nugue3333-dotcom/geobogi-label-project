from __future__ import annotations

import os
from pathlib import Path

import pytest

from barcode_label_automation.file_association import (
    LABEL_PROG_ID,
    STABLE_ICON_DIRECTORY,
    ensure_label_file_association,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def restore_project_file_association() -> None:
    yield
    if os.name != "nt":
        return
    customer_dir = PROJECT_ROOT / "고객용_실행폴더"
    designer = customer_dir / "라벨디자이너.exe"
    icon = customer_dir / "assets" / "brand" / "chaeumlab_label_file_icon_white.ico"
    if designer.is_file():
        ensure_label_file_association(designer, icon_source=icon)


@pytest.mark.skipif(os.name != "nt", reason="Windows file associations only")
def test_file_association_uses_stable_icon_and_current_designer(tmp_path: Path) -> None:
    import winreg

    designer = tmp_path / "배포 폴더" / "라벨디자이너.exe"
    source_icon = designer.parent / "assets" / "brand" / "chaeumlab_label_file_icon_white.ico"
    source_icon.parent.mkdir(parents=True)
    designer.write_bytes(b"designer")
    source_icon.write_bytes(b"icon-v1")

    result = ensure_label_file_association(
        designer,
        icon_source=source_icon,
        local_app_data=tmp_path / "Local App Data",
    )

    expected_icon = next((tmp_path / "Local App Data" / STABLE_ICON_DIRECTORY).glob("chaeumlab_label_file_*.ico"))
    assert result.registered is True
    assert result.icon_path == expected_icon
    assert expected_icon.read_bytes() == b"icon-v1"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{LABEL_PROG_ID}\DefaultIcon") as key:
        assert winreg.QueryValueEx(key, "")[0] == f'"{expected_icon}",0'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{LABEL_PROG_ID}\shell\open\command") as key:
        assert winreg.QueryValueEx(key, "")[0] == f'"{designer.resolve()}" "%1"'


@pytest.mark.skipif(os.name != "nt", reason="Windows file associations only")
def test_file_association_changes_icon_path_when_icon_content_changes(tmp_path: Path) -> None:
    designer = tmp_path / "라벨디자이너.exe"
    source_icon = tmp_path / "file.ico"
    designer.write_bytes(b"designer")
    source_icon.write_bytes(b"icon-v1")
    first = ensure_label_file_association(designer, icon_source=source_icon, local_app_data=tmp_path / "Local")

    source_icon.write_bytes(b"icon-v2")
    second = ensure_label_file_association(designer, icon_source=source_icon, local_app_data=tmp_path / "Local")

    assert first.icon_path != second.icon_path
    assert first.icon_path is not None and first.icon_path.read_bytes() == b"icon-v1"
    assert second.icon_path is not None and second.icon_path.read_bytes() == b"icon-v2"


def test_file_association_rejects_missing_designer(tmp_path: Path) -> None:
    result = ensure_label_file_association(tmp_path / "missing.exe", local_app_data=tmp_path)

    assert result.registered is False
    assert "찾을 수 없습니다" in result.error
