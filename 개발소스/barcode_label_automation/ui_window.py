from __future__ import annotations

import ctypes
import os
import tkinter as tk
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkArea:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(1, self.right - self.left)

    @property
    def height(self) -> int:
        return max(1, self.bottom - self.top)


@dataclass(frozen=True)
class WindowPlacement:
    width: int
    height: int
    x: int
    y: int
    minimum_width: int
    minimum_height: int

    @property
    def geometry(self) -> str:
        return f"{self.width}x{self.height}+{self.x}+{self.y}"


def calculate_window_placement(
    work_area: WorkArea,
    *,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
    margin: int = 24,
) -> WindowPlacement:
    available_width = max(1, work_area.width - (margin * 2))
    available_height = max(1, work_area.height - (margin * 2))
    width = min(max(preferred_width, minimum_width), available_width)
    height = min(max(preferred_height, minimum_height), available_height)
    effective_minimum_width = min(minimum_width, width)
    effective_minimum_height = min(minimum_height, height)
    x = work_area.left + max(0, (work_area.width - width) // 2)
    y = work_area.top + max(0, (work_area.height - height) // 3)
    return WindowPlacement(
        width=width,
        height=height,
        x=x,
        y=y,
        minimum_width=effective_minimum_width,
        minimum_height=effective_minimum_height,
    )


def set_initial_window_size(
    window: tk.Tk,
    *,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
) -> WindowPlacement:
    placement = calculate_window_placement(
        _primary_work_area(window),
        preferred_width=preferred_width,
        preferred_height=preferred_height,
        minimum_width=minimum_width,
        minimum_height=minimum_height,
    )
    window.geometry(placement.geometry)
    window.minsize(placement.minimum_width, placement.minimum_height)
    return placement


def _primary_work_area(window: tk.Misc) -> WorkArea:
    if os.name == "nt":
        try:
            class Rect(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            rect = Rect()
            success = ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            if success and rect.right > rect.left and rect.bottom > rect.top:
                return WorkArea(rect.left, rect.top, rect.right, rect.bottom)
        except (AttributeError, OSError):
            pass
    return WorkArea(0, 0, max(1, window.winfo_screenwidth()), max(1, window.winfo_screenheight()))
