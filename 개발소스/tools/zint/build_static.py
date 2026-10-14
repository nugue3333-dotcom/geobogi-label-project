"""Reproduce the standalone barcode CLI using the pinned portable Zig toolchain.

Usage: python tools/zint/build_static.py --zig PATH/zig.exe --output PATH/zint.exe
The compiler is a build dependency only; no customer installation is needed.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zig', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='zint-source-') as folder:
        with tarfile.open(root/'zint-2.16.0-src.tar.gz') as archive:
            archive.extractall(folder, filter='data')
        source = Path(folder)/'zint-2.16.0-src'
        # Same source groups as backend/CMakeLists.txt; PNG is an optional output
        # adapter, omitted to avoid libpng/zlib DLL dependencies. BMP/GIF/TIF remain.
        sources = sorted(p for p in (source/'backend').glob('*.c')
                         if p.name not in {'png.c','dllversion.c'})
        command = [str(args.zig.resolve()), 'cc', '-target', 'x86_64-windows-gnu',
                   '-Os', '-s', '-DZINT_NO_PNG', '-DZINT_STATIC', '-I'+str(source/'backend'),
                   *(str(p) for p in sources), str(source/'frontend/main.c'),
                   '-o', str(output)]
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
