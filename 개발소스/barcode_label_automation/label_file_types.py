"""Customer document names; legacy files keep their contents and extensions."""

from __future__ import annotations

from pathlib import Path


LABEL_FILE_EXTENSION = ".cllabel"
LEGACY_LABEL_FILE_EXTENSION = ".gblabel"
LABEL_FILE_EXTENSIONS = (LABEL_FILE_EXTENSION, LEGACY_LABEL_FILE_EXTENSION)
LABEL_OPEN_FILE_TYPES = (
    ("채움랩 라벨 도안", "*.cllabel *.gblabel"),
    ("라벨 템플릿 JSON", "*.json"),
)
LABEL_SAVE_FILE_TYPES = (
    ("채움랩 라벨 도안", "*.cllabel"),
    ("이전 버전 라벨 파일", "*.gblabel"),
    ("라벨 템플릿 JSON", "*.json"),
)

PROJECT_FILE_EXTENSION = ".clproject"
LEGACY_PROJECT_FILE_EXTENSION = ".gbproject"
PROJECT_FILE_EXTENSIONS = (PROJECT_FILE_EXTENSION, LEGACY_PROJECT_FILE_EXTENSION)
PROJECT_OPEN_FILE_TYPES = (("채움랩 이동 프로젝트", "*.clproject *.gbproject"),)
PROJECT_SAVE_FILE_TYPES = (
    ("채움랩 이동 프로젝트", "*.clproject"),
    ("이전 버전 이동 프로젝트", "*.gbproject"),
)


def is_label_file(path: str | Path, *, include_json: bool = False) -> bool:
    suffix = Path(path).suffix.casefold()
    return suffix in LABEL_FILE_EXTENSIONS or (include_json and suffix == ".json")


def is_project_file(path: str | Path) -> bool:
    return Path(path).suffix.casefold() in PROJECT_FILE_EXTENSIONS
