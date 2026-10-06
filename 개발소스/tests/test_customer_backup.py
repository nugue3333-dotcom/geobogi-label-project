from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from barcode_label_automation import customer_backup
from barcode_label_automation.customer_backup import CustomerBackupError, create_customer_backup, restore_customer_backup


def _manifest_entry(path: str, content: bytes) -> dict[str, str | int]:
    return {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def _write_backup_zip(
    path: Path,
    payloads: list[tuple[str, bytes]],
    *,
    manifest_entries: list[dict[str, str | int]] | None = None,
    compression: int = zipfile.ZIP_DEFLATED,
) -> None:
    legacy = b"chaeumlab customer backup\n"
    all_payloads = [*payloads, (customer_backup.LEGACY_MANIFEST_FILE, legacy)]
    entries = manifest_entries or [_manifest_entry(name, content) for name, content in all_payloads]
    manifest = {
        "format": customer_backup.BACKUP_FORMAT,
        "version": customer_backup.BACKUP_VERSION,
        "created_at": "2026-07-14T00:00:00+09:00",
        "files": entries,
    }
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, content in all_payloads:
            archive.writestr(name, content)
        archive.writestr(customer_backup.MANIFEST_FILE, json.dumps(manifest).encode("utf-8"))


def test_backup_is_verified_manifest_zip_published_atomically(tmp_path: Path) -> None:
    (tmp_path / "config.ini").write_bytes(b"printer=tsc\n")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "default_label.json").write_bytes(b'{"elements":[]}')

    backup_path = create_customer_backup(tmp_path)

    assert backup_path.suffix == ".zip"
    assert not list((tmp_path / "out").glob("*.partial"))
    with zipfile.ZipFile(backup_path) as archive:
        manifest = json.loads(archive.read(customer_backup.MANIFEST_FILE))
        entries = {entry["path"]: entry for entry in manifest["files"]}
        assert set(entries) == {
            "config.ini",
            "templates/default_label.json",
            customer_backup.LEGACY_MANIFEST_FILE,
        }
        for name, entry in entries.items():
            content = archive.read(name)
            assert entry["size"] == len(content)
            assert entry["sha256"] == hashlib.sha256(content).hexdigest()


def test_backup_and_restore_preserve_new_and_legacy_documents(tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    templates.mkdir()
    expected = {}
    for suffix in (".cllabel", ".gblabel", ".clproject", ".gbproject"):
        path = templates / ("customer" + suffix)
        expected[path] = ("original " + suffix).encode("utf-8")
        path.write_bytes(expected[path])
    sample = tmp_path / "sample_direct_open.cllabel"
    sample.write_bytes(b"new-format sample")
    expected[sample] = b"new-format sample"
    backup = create_customer_backup(tmp_path)
    for path in expected:
        path.write_bytes(b"modified")
    restored = restore_customer_backup(tmp_path, backup)
    assert restored.restored_files == len(expected)
    for path, content in expected.items():
        assert path.read_bytes() == content


def test_backup_validation_failure_never_publishes_partial_zip(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "config.ini").write_bytes(b"printer=tsc\n")

    def fail_validation(_path: Path, extract_dir: Path | None = None):
        del extract_dir
        raise CustomerBackupError("forced validation failure")

    monkeypatch.setattr(customer_backup, "_validate_backup_archive", fail_validation)

    with pytest.raises(CustomerBackupError, match="forced validation failure"):
        create_customer_backup(tmp_path)

    assert not list((tmp_path / "out").iterdir())


@pytest.mark.parametrize(
    "member_name, message",
    [
        ("../config.ini", "허용되지 않는 경로"),
        ("templates/CON.txt", "예약 이름"),
        ("templates/design.json:secret", "위험한 경로"),
        ("templates/trailing. ", "위험한 경로"),
    ],
)
def test_restore_rejects_unsafe_zipinfo_paths(tmp_path: Path, member_name: str, message: str) -> None:
    backup_path = tmp_path / "unsafe.zip"
    _write_backup_zip(backup_path, [(member_name, b"unsafe")])

    with pytest.raises(CustomerBackupError, match=message):
        restore_customer_backup(tmp_path / "target", backup_path)


def test_restore_rejects_case_insensitive_duplicate_paths(tmp_path: Path) -> None:
    backup_path = tmp_path / "duplicate.zip"
    legacy = b"chaeumlab customer backup\n"
    entries = [
        _manifest_entry("config.ini", b"first"),
        _manifest_entry(customer_backup.LEGACY_MANIFEST_FILE, legacy),
    ]
    manifest = {
        "format": customer_backup.BACKUP_FORMAT,
        "version": customer_backup.BACKUP_VERSION,
        "created_at": "2026-07-14T00:00:00+09:00",
        "files": entries,
    }
    with zipfile.ZipFile(backup_path, "w") as archive:
        archive.writestr("config.ini", b"first")
        archive.writestr("CONFIG.INI", b"second")
        archive.writestr(customer_backup.LEGACY_MANIFEST_FILE, legacy)
        archive.writestr(customer_backup.MANIFEST_FILE, json.dumps(manifest))

    with pytest.raises(CustomerBackupError, match="중복 경로"):
        restore_customer_backup(tmp_path / "target", backup_path)


def test_restore_rejects_declared_file_over_size_limit(monkeypatch, tmp_path: Path) -> None:
    backup_path = tmp_path / "large.zip"
    _write_backup_zip(backup_path, [("config.ini", b"12345")])
    monkeypatch.setattr(customer_backup, "MAX_FILE_SIZE", 4)

    with pytest.raises(CustomerBackupError, match="크기"):
        restore_customer_backup(tmp_path / "target", backup_path)


def test_restore_rejects_crc_corruption_before_mutating_target(tmp_path: Path) -> None:
    backup_path = tmp_path / "crc.zip"
    original = b"unique-crc-payload"
    _write_backup_zip(backup_path, [("config.ini", original)], compression=zipfile.ZIP_STORED)
    damaged = backup_path.read_bytes().replace(original, b"X" + original[1:], 1)
    backup_path.write_bytes(damaged)
    target = tmp_path / "target"
    target.mkdir()
    (target / "config.ini").write_bytes(b"old")

    with pytest.raises(CustomerBackupError, match="무결성 검증"):
        restore_customer_backup(target, backup_path)

    assert (target / "config.ini").read_bytes() == b"old"
    assert not list((target / "out").glob("chaeumlab_customer_backup_*.zip"))


def test_restore_rejects_sha256_mismatch_before_pre_restore_backup(tmp_path: Path) -> None:
    backup_path = tmp_path / "hash.zip"
    legacy = b"chaeumlab customer backup\n"
    entries = [
        _manifest_entry("config.ini", b"expected"),
        _manifest_entry(customer_backup.LEGACY_MANIFEST_FILE, legacy),
    ]
    _write_backup_zip(backup_path, [("config.ini", b"tampered")], manifest_entries=entries)
    target = tmp_path / "target"
    target.mkdir()
    (target / "config.ini").write_bytes(b"old")

    with pytest.raises(CustomerBackupError, match="SHA-256"):
        restore_customer_backup(target, backup_path)

    assert (target / "config.ini").read_bytes() == b"old"
    assert not list((target / "out").glob("chaeumlab_customer_backup_*.zip"))


def test_restore_requires_successful_pre_restore_backup(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "config.ini").write_bytes(b"new")
    (target / "config.ini").write_bytes(b"old")
    backup_path = create_customer_backup(source)
    original_create = customer_backup._create_customer_backup

    def fail_pre_backup(base_dir: Path, *, allow_empty: bool) -> Path:
        if allow_empty:
            raise CustomerBackupError("pre-restore backup failed")
        return original_create(base_dir, allow_empty=allow_empty)

    monkeypatch.setattr(customer_backup, "_create_customer_backup", fail_pre_backup)

    with pytest.raises(CustomerBackupError, match="pre-restore backup failed"):
        restore_customer_backup(target, backup_path)

    assert (target / "config.ini").read_bytes() == b"old"


def test_restore_applies_exact_managed_snapshot_and_keeps_unmanaged_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "config.ini").write_bytes(b"new")
    (source / "assets" / "images").mkdir(parents=True)
    (source / "assets" / "images" / "new.png").write_bytes(b"new-image")
    (target / "config.ini").write_bytes(b"old")
    (target / "barcode_db.xlsx").write_bytes(b"stale-db")
    (target / "templates").mkdir()
    (target / "templates" / "stale.json").write_bytes(b"stale")
    (target / "assets" / "images").mkdir(parents=True)
    (target / "assets" / "images" / "stale.png").write_bytes(b"stale-image")
    (target / "assets" / "brand").mkdir(parents=True)
    (target / "assets" / "brand" / "logo.png").write_bytes(b"keep")
    backup_path = create_customer_backup(source)

    result = restore_customer_backup(target, backup_path)

    assert result.pre_restore_backup is not None and result.pre_restore_backup.is_file()
    assert result.restored_files == 2
    assert (target / "config.ini").read_bytes() == b"new"
    assert not (target / "barcode_db.xlsx").exists()
    assert not (target / "templates").exists()
    assert not (target / "assets" / "images" / "stale.png").exists()
    assert (target / "assets" / "images" / "new.png").read_bytes() == b"new-image"
    assert (target / "assets" / "brand" / "logo.png").read_bytes() == b"keep"


def test_restore_rolls_back_all_managed_targets_when_apply_fails(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "config.ini").write_bytes(b"new-config")
    (source / "barcode_db.xlsx").write_bytes(b"new-db")
    (target / "config.ini").write_bytes(b"old-config")
    (target / "barcode_db.xlsx").write_bytes(b"old-db")
    (target / "templates").mkdir()
    (target / "templates" / "old.json").write_bytes(b"old-template")
    backup_path = create_customer_backup(source)
    real_replace = customer_backup.os.replace
    failed = False

    def fail_second_staged_install(source_path, destination_path):
        nonlocal failed
        source_text = str(source_path)
        if not failed and "payload" in source_text and source_text.endswith("barcode_db.xlsx"):
            failed = True
            raise OSError("forced apply failure")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(customer_backup.os, "replace", fail_second_staged_install)

    with pytest.raises(CustomerBackupError, match="rollback했습니다"):
        restore_customer_backup(target, backup_path)

    assert (target / "config.ini").read_bytes() == b"old-config"
    assert (target / "barcode_db.xlsx").read_bytes() == b"old-db"
    assert (target / "templates" / "old.json").read_bytes() == b"old-template"
    assert list((target / "out").glob("chaeumlab_customer_backup_*.zip"))
