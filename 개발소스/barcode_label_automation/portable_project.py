"""Portable label projects. Excel records are deliberately never embedded."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from .label_file_types import LABEL_FILE_EXTENSION, PROJECT_FILE_EXTENSION, PROJECT_FILE_EXTENSIONS, is_project_file

PROJECT_EXTENSION = PROJECT_FILE_EXTENSION
PROJECT_VERSION = 1
MAX_ASSET_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 150 * 1024 * 1024
MAX_ASSETS = 100
IMAGE_KEYS = ("image_path", "review_image_path")


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def export_portable_project(
    template: dict[str, object],
    base_dir: Path,
    target: Path,
    *,
    data_source_path: Path | None = None,
    data_source_headers: tuple[str, ...] = (),
) -> None:
    """Write a self-contained design archive with an Excel reconnection hint."""
    if target.suffix.lower() not in PROJECT_FILE_EXTENSIONS:
        raise ValueError(f"이동용 프로젝트는 {' 또는 '.join(PROJECT_FILE_EXTENSIONS)} 파일로 저장해야 합니다.")
    portable = copy.deepcopy(template)
    elements = portable.get("elements")
    if not isinstance(elements, list):
        raise ValueError("라벨 개체 목록을 읽을 수 없습니다.")
    assets: dict[str, Path] = {}
    total_bytes = 0
    for element in elements:
        if not isinstance(element, dict):
            raise ValueError("라벨 개체 형식이 올바르지 않습니다.")
        element.pop("source_path", None)
        for key in IMAGE_KEYS:
            raw = str(element.get(key, "")).strip()
            if not raw:
                continue
            source = Path(raw)
            if not source.is_absolute():
                source = base_dir / source
            if not source.is_file():
                raise FileNotFoundError(f"이동할 이미지가 없습니다: {source.name}")
            size = source.stat().st_size
            if size > MAX_ASSET_BYTES:
                raise ValueError(f"이미지 파일이 25MB를 넘습니다: {source.name}")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            name = f"assets/{digest}{source.suffix.lower()}"
            if name not in assets:
                assets[name] = source
                total_bytes += size
            element[key] = name
    if len(assets) > MAX_ASSETS or total_bytes > MAX_TOTAL_BYTES:
        raise ValueError("프로젝트 이미지 수 또는 전체 크기가 허용 범위를 넘습니다.")
    font_names = sorted({
        str(element.get("font_name", "")).strip()
        for element in elements
        if isinstance(element, dict) and element.get("font_name")
    })
    manifest = {
        "format": "chaeumlab-portable-label",
        "version": PROJECT_VERSION,
        "assets": {name: name.split("/")[-1].split(".")[0] for name in assets},
        "fonts": font_names,
        "data_profile": {
            "file_name": data_source_path.name if data_source_path else "",
            "headers": list(data_source_headers),
            "note": "상품 엑셀 원본은 포함하지 않습니다. 새 PC에서 직접 다시 연결하세요.",
        },
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("project.json", _json_bytes(manifest))
            archive.writestr("label.gblabel", _json_bytes(portable))
            for name, source in assets.items():
                archive.write(source, name)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def import_portable_project(source: Path, base_dir: Path) -> tuple[Path, dict[str, object]]:
    """Validate all archive content before creating a unique imported project."""
    if not is_project_file(source):
        raise ValueError(f"이동용 프로젝트는 {' 또는 '.join(PROJECT_FILE_EXTENSIONS)} 파일이어야 합니다.")
    try:
        with ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ASSETS + 2:
                raise ValueError("프로젝트에 파일이 너무 많습니다.")
            if any(entry.file_size > MAX_ASSET_BYTES for entry in entries if entry.filename.startswith("assets/")):
                raise ValueError("25MB가 넘는 이미지가 있습니다.")
            if sum(entry.file_size for entry in entries) > MAX_TOTAL_BYTES:
                raise ValueError("프로젝트 전체 크기가 150MB를 넘습니다.")
            manifest = json.loads(archive.read("project.json"))
            template = json.loads(archive.read("label.gblabel"))
            if not isinstance(manifest, dict) or manifest.get("format") != "chaeumlab-portable-label" or manifest.get("version") != PROJECT_VERSION:
                raise ValueError("지원하지 않는 프로젝트 파일입니다.")
            if not isinstance(template, dict) or not isinstance(template.get("elements"), list):
                raise ValueError("라벨 내용이 올바르지 않습니다.")
            assets = manifest.get("assets")
            if not isinstance(assets, dict) or len(assets) > MAX_ASSETS:
                raise ValueError("프로젝트 이미지 목록이 올바르지 않습니다.")
            expected = {"project.json", "label.gblabel", *assets}
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)) or set(names) != expected:
                raise ValueError("프로젝트 파일 목록이 올바르지 않습니다.")
            fonts = manifest.get("fonts", [])
            if not isinstance(fonts, list) or any(not isinstance(font, str) for font in fonts):
                raise ValueError("프로젝트 글꼴 목록이 올바르지 않습니다.")
            checked_assets: dict[str, bytes] = {}
            for name, digest in assets.items():
                if (not isinstance(name, str) or not name.startswith("assets/")
                        or Path(name).name != name[7:] or not isinstance(digest, str)
                        or any(char in name[7:] for char in '\\/:<>"|?*\x00')
                        or name.endswith((".", " "))):
                    raise ValueError("프로젝트 이미지 경로가 올바르지 않습니다.")
                if not name[7:].startswith(digest) or len(digest) != 64:
                    raise ValueError("프로젝트 이미지 검증 정보가 올바르지 않습니다.")
                data = archive.read(name)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError(f"프로젝트 이미지가 손상되었습니다: {Path(name).name}")
                checked_assets[name] = data
            for element in template["elements"]:
                if not isinstance(element, dict):
                    raise ValueError("라벨 개체 형식이 올바르지 않습니다.")
                for key in IMAGE_KEYS:
                    raw = element.get(key)
                    if raw and (not isinstance(raw, str) or raw not in checked_assets):
                        raise ValueError("프로젝트 이미지 참조가 누락되었습니다.")
    except (BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
        raise ValueError("프로젝트 파일을 읽거나 검증할 수 없습니다.") from exc

    destination_root = base_dir / "templates" / "imported"
    destination_root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="project_", dir=destination_root))
    try:
        elements = template["elements"]
        for element in elements:
            if not isinstance(element, dict):
                raise ValueError("라벨 개체 형식이 올바르지 않습니다.")
            for key in IMAGE_KEYS:
                raw = element.get(key)
                if not raw:
                    continue
                if raw not in checked_assets:
                    raise ValueError("프로젝트 이미지 참조가 누락되었습니다.")
                element[key] = str((folder / raw).relative_to(base_dir))
            element.pop("source_path", None)
        for name, data in checked_assets.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        label_path = folder / f"label{LABEL_FILE_EXTENSION}"
        label_path.write_bytes(_json_bytes(template))
        profile = manifest.get("data_profile")
        safe_profile = dict(profile) if isinstance(profile, dict) else {}
        safe_profile["fonts"] = fonts
        (folder / "project_profile.json").write_bytes(_json_bytes(safe_profile))
        return label_path, safe_profile
    except Exception:
        shutil.rmtree(folder)
        raise
