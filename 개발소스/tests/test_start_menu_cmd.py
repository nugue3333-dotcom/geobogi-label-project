from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_customer_start_menu_help_runs() -> None:
    menu_path = PROJECT_ROOT / "고객용_실행폴더" / "시작하기.cmd"

    completed = subprocess.run(
        ["cmd.exe", "/c", str(menu_path), "help"],
        cwd=PROJECT_ROOT / "고객용_실행폴더",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0
    assert "시작하기.cmd first-run" in completed.stdout
    assert "시작하기.cmd check" in completed.stdout
    assert "시작하기.cmd manager" in completed.stdout
    assert "시작하기.cmd backup" in completed.stdout
    assert "시작하기.cmd restore" in completed.stdout
    assert "시작하기.cmd version" in completed.stdout
    assert "시작하기.cmd file-association" in completed.stdout


def test_customer_start_menu_quit_runs_without_prompt() -> None:
    menu_path = PROJECT_ROOT / "고객용_실행폴더" / "시작하기.cmd"

    completed = subprocess.run(
        ["cmd.exe", "/c", str(menu_path), "quit"],
        cwd=PROJECT_ROOT / "고객용_실행폴더",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0


def test_customer_first_run_script_has_quiet_steps() -> None:
    script = (PROJECT_ROOT / "고객용_실행폴더" / "처음실행_점검.cmd").read_text(encoding="utf-8")

    assert "install_chaeumlab_font.ps1\" -Quiet" in script
    assert "00_고객PC_실행전점검.cmd\" -Quiet" in script
    assert "register_label_filetype.cmd\" -Quiet" in script
    assert "01_output_check.cmd\" -Quiet" in script
    assert "고객데이터_백업.cmd\" -Quiet" in script
    assert "[1/5]" in script
    assert "[5/5]" in script
    assert "처음 실행 점검이 완료되었습니다." in script


def test_file_association_command_delegates_to_verified_designer_cli() -> None:
    script = (PROJECT_ROOT / "register_label_filetype.cmd").read_text(encoding="utf-8")

    assert "chcp 65001 >nul" in "\n".join(script.splitlines()[:3])
    assert "powershell" not in script.lower()
    assert "--register-file-associations" in script
    assert "--restore-file-associations" in script
    assert 'if /I "%~1"=="rollback" goto RESTORE' in script
    assert ".cllabel / .clproject" in script
    assert ".gblabel / .gbproject" in script
    assert "기존 사용자 기본 앱 선택은 유지됩니다." in script
    assert "if errorlevel 1 goto FAILED" in script
    assert "reg add" not in script.lower()
    assert "reg delete" not in script.lower()


def test_file_association_command_missing_designer_fails_without_registry_changes(tmp_path) -> None:
    # Exercise the real batch wrapper in an isolated directory. No EXE is
    # present, so no registration entry point or Windows registry is invoked.
    command_path = tmp_path / "register_label_filetype.cmd"
    shutil.copy2(PROJECT_ROOT / "register_label_filetype.cmd", command_path)

    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "call", str(command_path), "-Quiet"],
        cwd=tmp_path,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "라벨디자이너.exe 파일을 찾을 수 없습니다." in completed.stdout
    assert "등록했습니다" not in completed.stdout


def test_customer_start_menu_version_runs() -> None:
    menu_path = PROJECT_ROOT / "고객용_실행폴더" / "시작하기.cmd"

    completed = subprocess.run(
        ["cmd.exe", "/c", str(menu_path), "version"],
        cwd=PROJECT_ROOT / "고객용_실행폴더",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0
    assert "채움랩 라벨 출력 패키지 버전 정보" in completed.stdout
    assert "out\\customer_support_package.zip" in completed.stdout


def test_customer_start_menu_prefers_docx_manual() -> None:
    script = (PROJECT_ROOT / "고객용_실행폴더" / "시작하기.cmd").read_text(encoding="utf-8")

    docx_index = script.index("라벨출력패키지_고객용_매뉴얼.docx")
    text_index = script.index("설치_및_사용_메뉴얼.txt")
    assert docx_index < text_index
    assert "상세 매뉴얼 파일을 찾을 수 없습니다." in script


def test_customer_restore_command_invokes_job_runner_restore() -> None:
    script = (PROJECT_ROOT / "고객용_실행폴더" / "고객데이터_복원.cmd").read_text(encoding="utf-8")

    assert "chcp 65001 >nul" in "\n".join(script.splitlines()[:3])
    assert "라벨작업실행기.exe\" Restore --backup-zip" in script
    assert "복원할 백업 ZIP 파일 경로를 입력하세요." in script
