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

    def fail_pre_backup(base_dir: Path, *, allow_empty: bool, ledger_locked: bool = False) -> Path:
        if allow_empty:
            raise CustomerBackupError("pre-restore backup failed")
        return original_create(base_dir, allow_empty=allow_empty, ledger_locked=ledger_locked)

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


def _issued_job(base: Path):
    from barcode_label_automation.value_jobs import ValueJobStore
    store = ValueJobStore(base)
    rule = {"name": "serial", "kind": "serial", "start": 1, "step": 1, "digits": 6, "copies_per_value": 1, "reset": "continue"}
    job = store.prepare_job([{"barcode": "00123"}], [1], [rule], template_key="customer-template", job_date="2026-10-08")
    return store, rule, job


def test_backup_includes_only_value_ledger_from_output_folder(tmp_path: Path) -> None:
    store, _rule, job = _issued_job(tmp_path)
    (tmp_path / "out/last_run.log").write_text("private log", encoding="utf-8")
    (tmp_path / "out/customer_support_package.zip").write_bytes(b"support")
    backup = create_customer_backup(tmp_path)
    with zipfile.ZipFile(backup) as archive:
        assert customer_backup.VALUE_LEDGER_FILE in archive.namelist()
        assert "out/last_run.log" not in archive.namelist()
        assert "out/customer_support_package.zip" not in archive.namelist()
        assert "out/value_jobs/ledger.lock" not in archive.namelist()
    restored = tmp_path / "other-pc"
    restore_customer_backup(restored, backup)
    from barcode_label_automation.value_jobs import ValueJobStore
    moved = ValueJobStore(restored)
    assert moved.load_job(job.snapshot_id).labels == store.load_job(job.snapshot_id).labels
    assert moved.peek_start_overrides("customer-template", [_rule]) == {"serial": 2}


def test_restore_rejects_old_issued_numbers_before_changing_live_data(tmp_path: Path) -> None:
    (tmp_path / "config.ini").write_bytes(b"older config")
    store, rule, _job = _issued_job(tmp_path)
    backup = create_customer_backup(tmp_path)
    store.prepare_job([{"barcode": "00123"}], [2], [rule], template_key="customer-template", job_date="2026-10-08")
    (tmp_path / "config.ini").write_bytes(b"current config")
    ledger = store.path.read_bytes()
    with pytest.raises(CustomerBackupError, match="발급 번호"):
        restore_customer_backup(tmp_path, backup)
    assert (tmp_path / "config.ini").read_bytes() == b"current config"
    assert store.path.read_bytes() == ledger


def test_restore_old_backup_without_ledger_keeps_current_issued_records(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "config.ini").write_bytes(b"incoming")
    backup = create_customer_backup(source)
    store, _rule, _job = _issued_job(target)
    ledger = store.path.read_bytes()
    with pytest.raises(CustomerBackupError, match="발급 기록이 없습니다"):
        restore_customer_backup(target, backup)
    assert store.path.read_bytes() == ledger
    assert not (target / "config.ini").exists()


def test_restore_rejects_value_ledger_semantic_corruption_with_valid_zip_hash(tmp_path: Path) -> None:
    backup = tmp_path / "invalid-ledger.zip"
    _write_backup_zip(backup, [(customer_backup.VALUE_LEDGER_FILE, b'{"version":1,"jobs":{},"sequences":{}}'), ("config.ini", b"incoming")])
    target = tmp_path / "target"
    target.mkdir()
    (target / "config.ini").write_bytes(b"current")
    with pytest.raises(CustomerBackupError, match="값 발급 기록 검증 실패"):
        restore_customer_backup(target, backup)
    assert (target / "config.ini").read_bytes() == b"current"


def test_backup_rejects_active_value_ledger_lock(tmp_path: Path) -> None:
    store, _rule, _job = _issued_job(tmp_path)
    store.lock_path.write_text("other process", encoding="utf-8")
    with pytest.raises(CustomerBackupError, match="발급 기록이 사용 중"):
        create_customer_backup(tmp_path)
    assert store.lock_path.read_text(encoding="utf-8") == "other process"


def test_restore_rejects_lost_existing_snapshot_even_when_sequence_is_current(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    store, _rule, _job = _issued_job(target)
    source_ledger = source / customer_backup.VALUE_LEDGER_FILE
    source_ledger.parent.mkdir(parents=True)
    data = json.loads(store.path.read_bytes())
    data.pop("checksum")
    data["jobs"] = {}
    checksum = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    source_ledger.write_text(json.dumps(data | {"checksum": checksum}), encoding="utf-8")
    backup = create_customer_backup(source)
    original = store.path.read_bytes()
    with pytest.raises(CustomerBackupError, match="출력 값 기록이 누락"):
        restore_customer_backup(target, backup)
    assert store.path.read_bytes() == original


def test_restore_identical_ledger_keeps_next_serial_and_existing_snapshots(tmp_path: Path) -> None:
    store, rule, job = _issued_job(tmp_path)
    backup = create_customer_backup(tmp_path)
    restore_customer_backup(tmp_path, backup)
    assert store.peek_start_overrides("customer-template", [rule]) == {"serial": 2}
    assert store.load_job(job.snapshot_id).labels[0].row["barcode"] == "00123"


def test_restore_rejects_corrupt_live_ledger_without_replacing_data(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    _issued_job(source)
    (source / "config.ini").write_bytes(b"incoming")
    backup = create_customer_backup(source)
    store, _rule, _job = _issued_job(target)
    store.path.write_bytes(b"corrupt issued data")
    (target / "config.ini").write_bytes(b"current")
    with pytest.raises(CustomerBackupError, match="값 발급 기록 검증 실패"):
        restore_customer_backup(target, backup)
    assert store.path.read_bytes() == b"corrupt issued data"
    assert (target / "config.ini").read_bytes() == b"current"


def test_ledger_install_failure_rolls_back_configuration_and_issued_values(monkeypatch, tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    store, _rule, _job = _issued_job(target)
    original_ledger = store.path.read_bytes()
    incoming = source / customer_backup.VALUE_LEDGER_FILE
    incoming.parent.mkdir(parents=True)
    incoming.write_bytes(original_ledger)
    (source / "config.ini").write_bytes(b"incoming")
    (target / "config.ini").write_bytes(b"current")
    backup = create_customer_backup(source)
    original_replace = customer_backup.os.replace
    def fail_ledger(source_path, destination_path):
        if "payload" in str(source_path) and str(source_path).endswith("ledger.json"):
            raise OSError("forced ledger install failure")
        return original_replace(source_path, destination_path)
    monkeypatch.setattr(customer_backup.os, "replace", fail_ledger)
    with pytest.raises(CustomerBackupError, match="rollback했습니다"):
        restore_customer_backup(target, backup)
    assert store.path.read_bytes() == original_ledger
    assert (target / "config.ini").read_bytes() == b"current"
