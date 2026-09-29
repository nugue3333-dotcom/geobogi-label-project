from __future__ import annotations

import os
import subprocess
import winreg
from pathlib import Path

from barcode_label_automation.file_association import STABLE_ICON_DIRECTORY, local_app_data_dir


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


def test_customer_file_association_command_uses_white_icon_without_powershell() -> None:
    script = (PROJECT_ROOT / "고객용_실행폴더" / "register_label_filetype.cmd").read_text(encoding="utf-8")

    assert "chcp 65001 >nul" in "\n".join(script.splitlines()[:3])
    assert "powershell" not in script.lower()
    assert "chaeumlab_label_file_icon_white.ico" in script
    assert "ChaeumLAB.LabelFile" in script
    assert "shell\\open\\command" in script
    assert "shell\\print\\command" in script
    assert "LOCAL_APP_DATA=%LOCALAPPDATA%" in script
    assert r"%LOCAL_APP_DATA%\ChaeumLAB\icons" in script
    assert "certutil -hashfile" in script
    assert "chaeumlab_label_file_!ICON_HASH!.ico" in script
    assert "LEGACY_PROG_ID" in script
    assert "ie4uinit.exe" in script
    assert 'if not defined SYSTEM_ROOT set "SYSTEM_ROOT=C:\\Windows"' in script
    assert '"%SYSTEM_ROOT%\\System32\\ie4uinit.exe"' in script


def test_customer_file_association_command_registers_gblabel() -> None:
    if os.name != "nt":
        return

    customer_dir = PROJECT_ROOT / "고객용_실행폴더"
    command_path = customer_dir / "register_label_filetype.cmd"
    designer_path = customer_dir / "라벨디자이너.exe"

    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "call", str(command_path), "-Quiet"],
        cwd=customer_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert ".gblabel 저장파일 연결을 등록했습니다." in completed.stdout
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.gblabel") as key:
        assert winreg.QueryValueEx(key, "")[0] == "ChaeumLAB.LabelFile"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\ChaeumLAB.LabelFile\DefaultIcon") as key:
        registered_icon = winreg.QueryValueEx(key, "")[0]
    icon_path = Path(registered_icon.rsplit(",", 1)[0].strip('"'))
    assert icon_path.parent == local_app_data_dir() / STABLE_ICON_DIRECTORY
    assert icon_path.name.startswith("chaeumlab_label_file_")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\ChaeumLAB.LabelFile\shell\open\command") as key:
        assert winreg.QueryValueEx(key, "")[0] == f'"{designer_path}" "%1"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\ChaeumLAB.LabelFile\shell\print\command") as key:
        assert winreg.QueryValueEx(key, "")[0] == f'"{designer_path}" --print "%1"'
    assert icon_path.read_bytes() == (customer_dir / "assets" / "brand" / "chaeumlab_label_file_icon_white.ico").read_bytes()
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gblabel\OpenWithProgids",
    ) as key:
        assert winreg.QueryValueEx(key, "ChaeumLAB.LabelFile")[1] == winreg.REG_NONE
        try:
            winreg.QueryValueEx(key, "GeobogiDream.LabelFile")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("legacy GeobogiDream.LabelFile association remains")


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
