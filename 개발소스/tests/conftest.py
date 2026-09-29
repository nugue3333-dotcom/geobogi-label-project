from __future__ import annotations

import os
import sys
from pathlib import Path


def _configure_tk_library_paths() -> None:
    tcl_root = Path(sys.base_prefix) / "tcl"
    tcl_candidates = sorted(tcl_root.glob("tcl*/auto.tcl"))
    tk_candidates = sorted(tcl_root.glob("tk*/tk.tcl"))
    if tcl_candidates:
        os.environ["TCL_LIBRARY"] = str(tcl_candidates[-1].parent)
    if tk_candidates:
        os.environ["TK_LIBRARY"] = str(tk_candidates[-1].parent)


_configure_tk_library_paths()

import tkinter as tk


_original_tk_init = tk.Tk.__init__


def _stable_tk_init(self: tk.Tk, *args: object, **kwargs: object) -> None:
    try:
        _original_tk_init(self, *args, **kwargs)
    except tk.TclError:
        # Python 3.14/Tk 8.6 can lose the Tcl library search path after a
        # previous root is destroyed. Retry once with the absolute paths.
        _configure_tk_library_paths()
        _original_tk_init(self, *args, **kwargs)


tk.Tk.__init__ = _stable_tk_init
