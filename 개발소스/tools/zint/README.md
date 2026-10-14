# Zint 2.16.0 corresponding source

The customer package must include this directory alongside the GPL CLI license
in `barcode_label_automation/vendor/zint/COPYING` (or the customer licenses folder).
`zint-2.16.0-src.tar.gz` is the complete, unmodified Zint corresponding source archive
downloaded from SourceForge. It contains build scripts,
frontend source, backend source and license notices. Build instructions are in
the archive's `README` and `win32/` directories. Binary/source SHA-256 hashes and
the original download URLs are pinned in `vendor/zint/provenance.json`.

The app invokes the unmodified CLI as a separate process with temporary files;
it does not link the GPL frontend into the application. No runtime download is
used. Zint's barcode backend is BSD licensed, its CLI frontend is GPLv3.

The shipped CLI is compiled locally from that source with the portable Zig
0.15.2 C compiler for AMD64 Windows. `build_static.py` records the full build
procedure. PNG support is disabled; the application reads BMP output through
Pillow instead. This avoids external libpng/zlib and VCRUNTIME140 dependencies.
Zig and MinGW license notices are included in the vendor folder. Toolchain
download URL/hash, compiler flags, PE imports and the resulting binary hash are
recorded in `provenance.json`.

Only Windows 10/11 built-in Universal C Runtime and KERNEL32 APIs are imported.
An isolated executable-copy check with a minimal system PATH verifies the
import boundary, but it does not replace testing on a clean customer Windows VM.
