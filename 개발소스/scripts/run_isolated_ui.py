"""Run native GUI checks on a separate Windows desktop, without switching to it.

Usage: python scripts/run_isolated_ui.py scripts/verify_release_tests.py --output-dir ...
Microsoft: windows/win32/winstation/thread-connection-to-a-desktop
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    if not sys.argv[1:]:
        raise SystemExit("Specify the Python script to run on the test desktop.")
    command = [sys.executable, *sys.argv[1:]]
    if os.name != "nt":
        return subprocess.run(command, check=False).returncode
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
    user32.GetThreadDesktop.restype = wintypes.HANDLE
    user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                     wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    user32.CreateDesktopW.restype = wintypes.HANDLE
    user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
    user32.SetThreadDesktop.restype = wintypes.BOOL
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    user32.CloseDesktop.restype = wintypes.BOOL
    original = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    name = f"ChaeumLAB_QA_{os.getpid()}"
    desktop = user32.CreateDesktopW(name, None, None, 0, 0x10000000, None)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not user32.SetThreadDesktop(original):
            raise ctypes.WinError(ctypes.get_last_error())
        startup = subprocess.STARTUPINFO()
        startup.lpDesktop = name
        print(f"ISOLATED_TEST_DESKTOP {name}", flush=True)
        with subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1],
                              startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace") as child:
            assert child.stdout is not None
            for line in child.stdout:
                print(line, end="", flush=True)
            return child.wait()
    finally:
        if not user32.CloseDesktop(desktop):
            raise ctypes.WinError(ctypes.get_last_error())


if __name__ == "__main__":
    raise SystemExit(main())
