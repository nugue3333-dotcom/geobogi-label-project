from __future__ import annotations

import json
import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from barcode_label_automation.label_designer_app import load_template_file
from barcode_label_automation.portable_project import export_portable_project, import_portable_project


def _project_template(image_path: str) -> dict[str, object]:
    return {
        "version": 1,
        "label": {"width_mm": 50, "height_mm": 40},
        "elements": [{
            "id": "logo",
            "type": "image",
            "x": 2,
            "y": 2,
            "width": 12,
            "height": 8,
            "image_path": image_path,
            "source_path": "C:/private/customer-original.psd",
        }],
    }


@pytest.mark.parametrize("extension", [".clproject", ".gbproject", ".CLPROJECT", ".GBPROJECT"])
def test_portable_project_moves_image_without_embedding_excel_or_original_path(tmp_path: Path, extension: str) -> None:
    old_pc = tmp_path / "old"
    new_pc = tmp_path / "new"
    image_path = old_pc / "assets" / "logo.png"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (24, 16), "red").save(image_path)
    source_excel = old_pc / "customer-products.xlsx"
    source_excel.write_bytes(b"private workbook content")
    target = tmp_path / f"transfer{extension}"

    export_portable_project(
        _project_template("assets/logo.png"), old_pc, target,
        data_source_path=source_excel, data_source_headers=("상품명", "바코드"),
    )
    with ZipFile(target) as archive:
        names = archive.namelist()
        assert "project.json" in names and "label.gblabel" in names
        assert all(not name.endswith(".xlsx") for name in names)
        assert b"private workbook content" not in target.read_bytes()
        assert b"customer-original.psd" not in target.read_bytes()
        manifest = json.loads(archive.read("project.json"))
        assert manifest["data_profile"]["file_name"] == "customer-products.xlsx"

    label_path, profile = import_portable_project(target, new_pc)
    assert label_path.suffix == ".cllabel"
    loaded = load_template_file(label_path)
    imported_image = new_pc / loaded["elements"][0]["image_path"]
    assert imported_image.read_bytes() == image_path.read_bytes()
    assert profile["headers"] == ["상품명", "바코드"]
    assert not (new_pc / source_excel.name).exists()
    second_path, _profile = import_portable_project(target, new_pc)
    assert second_path != label_path
    assert label_path.is_file()


def test_portable_project_missing_image_fails_without_overwriting_target(tmp_path: Path) -> None:
    target = tmp_path / "existing.gbproject"
    target.write_bytes(b"existing")
    with pytest.raises(FileNotFoundError, match="이동할 이미지"):
        export_portable_project(_project_template("missing.png"), tmp_path, target)
    assert target.read_bytes() == b"existing"


def test_portable_project_rejects_label_extension_without_overwriting_label(tmp_path: Path) -> None:
    label_path = tmp_path / "customer_label.gblabel"
    original = b'{"version":1,"elements":[]}'
    label_path.write_bytes(original)

    with pytest.raises(ValueError, match=r"\.gbproject"):
        export_portable_project({"version": 1, "elements": []}, tmp_path, label_path)

    assert label_path.read_bytes() == original


def test_portable_project_rejects_other_extension_without_creating_output(tmp_path: Path) -> None:
    target = tmp_path / "new_folder" / "transfer.zip"

    with pytest.raises(ValueError, match=r"\.gbproject"):
        export_portable_project({"version": 1, "elements": []}, tmp_path, target)

    assert not target.parent.exists()


def test_portable_project_rejects_new_label_extension_without_overwriting(tmp_path: Path) -> None:
    label_path = tmp_path / "customer_label.cllabel"
    label_path.write_bytes(b"original label")
    with pytest.raises(ValueError, match=r"\.clproject"):
        export_portable_project({"version": 1, "elements": []}, tmp_path, label_path)
    assert label_path.read_bytes() == b"original label"


def test_portable_project_rejects_unlisted_or_corrupt_asset(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.gbproject"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("project.json", json.dumps({
            "format": "chaeumlab-portable-label", "version": 1,
            "assets": {"assets/" + ("a" * 64) + ".png": "a" * 64},
        }))
        archive.writestr("label.gblabel", json.dumps(_project_template("assets/" + ("a" * 64) + ".png")))
        archive.writestr("assets/" + ("a" * 64) + ".png", b"corrupt")
    with pytest.raises(ValueError, match="손상"):
        import_portable_project(archive_path, tmp_path / "new")
    assert not (tmp_path / "new" / "templates").exists()


def _write_v1_project(path, *, asset_name=None, template=None, fonts=None, label_bytes=None):
    content = b"image payload"
    assets = {asset_name: hashlib.sha256(content).hexdigest()} if asset_name else {}
    manifest = {"format": "chaeumlab-portable-label", "version": 1, "assets": assets}
    if fonts is not None:
        manifest["fonts"] = fonts
    with ZipFile(path, "w") as archive:
        archive.writestr("project.json", json.dumps(manifest))
        archive.writestr("label.gblabel", label_bytes if label_bytes is not None else json.dumps(
            template if template is not None else {"version": 1, "elements": []}
        ))
        if asset_name:
            archive.writestr(asset_name, content)


@pytest.mark.parametrize("suffix", [":hidden", ".png:stream", ".png ", ".png.", "/nested.png", "\\nested.png"])
def test_portable_project_rejects_windows_unsafe_asset_names_before_writing(tmp_path, suffix):
    digest = hashlib.sha256(b"image payload").hexdigest()
    name = "assets/" + digest + suffix
    project = tmp_path / "unsafe.clproject"
    _write_v1_project(project, asset_name=name)

    with pytest.raises(ValueError, match="올바르지"):
        import_portable_project(project, tmp_path / "new")

    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("fonts", ["Moneygraphy", 5, ["valid", {"bad": "font"}]])
def test_portable_project_rejects_malformed_font_metadata_before_writing(tmp_path, fonts):
    project = tmp_path / "bad.clproject"
    _write_v1_project(project, fonts=fonts)
    with pytest.raises(ValueError, match="글꼴"):
        import_portable_project(project, tmp_path / "new")
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("elements", [["bad object"], [{"image_path": ["bad reference"]}], [{"review_image_path": "assets/missing.png"}]])
def test_portable_project_validates_all_element_references_before_writing(tmp_path, elements):
    project = tmp_path / "bad.gbproject"
    _write_v1_project(project, template={"version": 1, "elements": elements})
    with pytest.raises(ValueError):
        import_portable_project(project, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_portable_project_reports_invalid_json_encoding_as_validation_error(tmp_path):
    project = tmp_path / "bad.clproject"
    _write_v1_project(project, label_bytes=b"\xff\xfeinvalid")
    with pytest.raises(ValueError, match="읽거나 검증"):
        import_portable_project(project, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_import_rejects_wrong_extension_before_creating_any_files(tmp_path):
    project = tmp_path / "archive.zip"
    _write_v1_project(project)
    with pytest.raises(ValueError, match=r"\.clproject"):
        import_portable_project(project, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_v1_roundtrip_preserves_label_units_font_and_db_field_mapping(tmp_path):
    template = {"version": 1, "label": {"width_mm": 58, "height_mm": 40}, "elements": [{
        "type": "text", "id": "product", "font_name": "Moneygraphy Rounded",
        "db_column": "상품명", "text": "{상품명}", "x": 2, "y": 3, "width": 35, "height": 8,
    }]}
    project = tmp_path / "mapped.clproject"
    export_portable_project(template, tmp_path, project, data_source_headers=("상품명", "바코드"))
    with ZipFile(project) as archive:
        assert archive.namelist() == ["project.json", "label.gblabel"]
        assert json.loads(archive.read("project.json"))["version"] == 1
    label, profile = import_portable_project(project, tmp_path / "new")
    assert json.loads(label.read_text(encoding="utf-8")) == template
    assert profile["fonts"] == ["Moneygraphy Rounded"]
    assert profile["headers"] == ["상품명", "바코드"]
