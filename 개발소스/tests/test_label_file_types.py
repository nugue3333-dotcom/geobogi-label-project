from pathlib import Path

import pytest

from barcode_label_automation.label_file_types import (
    LABEL_FILE_EXTENSION,
    LABEL_OPEN_FILE_TYPES,
    LABEL_SAVE_FILE_TYPES,
    PROJECT_FILE_EXTENSION,
    PROJECT_OPEN_FILE_TYPES,
    PROJECT_SAVE_FILE_TYPES,
    is_label_file,
    is_project_file,
)


def test_new_defaults_and_legacy_open_filters():
    assert LABEL_FILE_EXTENSION == ".cllabel"
    assert PROJECT_FILE_EXTENSION == ".clproject"
    assert LABEL_SAVE_FILE_TYPES[0][1] == "*.cllabel"
    assert PROJECT_SAVE_FILE_TYPES[0][1] == "*.clproject"
    assert LABEL_OPEN_FILE_TYPES[0][1] == "*.cllabel *.gblabel"
    assert PROJECT_OPEN_FILE_TYPES[0][1] == "*.clproject *.gbproject"


@pytest.mark.parametrize("suffix", [".cllabel", ".gblabel", ".CLLABEL", ".GBLABEL"])
def test_new_and_legacy_label_names_are_recognized(suffix):
    assert is_label_file(Path(f"한글 도안{suffix}"))
    assert not is_project_file(Path(f"한글 도안{suffix}"))


@pytest.mark.parametrize("suffix", [".clproject", ".gbproject", ".CLPROJECT", ".GBPROJECT"])
def test_new_and_legacy_project_names_are_recognized(suffix):
    assert is_project_file(Path(f"이동 프로젝트{suffix}"))
    assert not is_label_file(Path(f"이동 프로젝트{suffix}"))


def test_json_opening_is_explicit_and_standard_extensions_are_not_claimed():
    assert not is_label_file("template.json")
    assert is_label_file("template.json", include_json=True)
    for suffix in (".xlsx", ".xlsm", ".ini", ".pdf", ".docx", ".exe", ".btw", ".png"):
        assert not is_label_file("file" + suffix)
        assert not is_project_file("file" + suffix)
