"""Shared desktop controls for the approved ChaeumLAB white/blue/lime suite."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import font as tkfont, ttk

from .ui_tokens import COLORS, TYPOGRAPHY, UI_FONT_FAMILY


def configure_suite_style(root: tk.Misc, style: ttk.Style | None = None) -> ttk.Style:
    style = style or ttk.Style(root)
    style.theme_use("clam")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name, root=root).configure(family=UI_FONT_FAMILY, size=10)
    root.option_add("*Font", TYPOGRAPHY.body)
    root.option_add("*Menu.Font", TYPOGRAPHY.body)
    root.option_add("*TCombobox*Listbox.font", TYPOGRAPHY.body)
    root.option_add("*Menu.background", COLORS.surface)
    root.option_add("*Menu.foreground", COLORS.text_primary)
    root.option_add("*Menu.activeBackground", COLORS.primary)
    root.option_add("*Menu.activeForeground", "#ffffff")
    style.configure(".", font=TYPOGRAPHY.body, background=COLORS.background)
    for name in ("App", "Body", "Workbench"):
        style.configure(f"{name}.TFrame", background=COLORS.background)
    for name in ("Surface", "Header", "Toolbar", "Ribbon", "SidePanel", "RibbonGroup", "RibbonGroupBody", "PropertyGroup"):
        style.configure(f"{name}.TFrame", background=COLORS.surface)
    style.configure("StatusBar.TFrame", background=COLORS.primary)
    style.configure("TLabel", font=TYPOGRAPHY.body, foreground=COLORS.text_primary, background=COLORS.surface)
    style.configure("Title.TLabel", font=TYPOGRAPHY.section_title, foreground=COLORS.text_primary, background=COLORS.surface)
    style.configure("HeaderLogo.TLabel", background=COLORS.surface)
    style.configure("HeaderTitle.TLabel", font=TYPOGRAPHY.section_title, foreground=COLORS.text_primary, background=COLORS.surface)
    style.configure("HeaderSub.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.surface)
    for name in ("SidePanelTitle", "PanelTitle", "CardTitle", "PropertyGroupTitle"):
        style.configure(f"{name}.TLabel", font=TYPOGRAPHY.section_title, foreground="#ffffff", background=COLORS.primary, padding=(10, 8))
    for name in ("SidePanelBody", "RibbonCaption", "RibbonGroupTitle", "Status"):
        style.configure(f"{name}.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.surface)
    style.configure("Hint.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.text_secondary, background=COLORS.surface)
    style.configure("FooterStatus.TLabel", font=TYPOGRAPHY.caption, foreground="#ffffff", background=COLORS.primary)
    style.configure("StatusPill.TLabel", font=TYPOGRAPHY.caption, foreground=COLORS.primary, background=COLORS.accent_soft, padding=(8, 4))
    style.configure("TSeparator", background=COLORS.border_subtle)
    for name in ("TButton", "Ribbon.TButton", "Tool.TButton", "Secondary.TButton", "Primary.TButton", "Danger.TButton", "TMenubutton"):
        primary = name == "Primary.TButton"
        danger = name == "Danger.TButton"
        fill = COLORS.accent if primary else COLORS.danger if danger else COLORS.surface
        foreground = "#ffffff" if danger else COLORS.text_primary
        style.configure(name, font=TYPOGRAPHY.button_text, foreground=foreground, background=fill,
                        bordercolor=COLORS.primary if not danger else COLORS.danger,
                        lightcolor=fill, darkcolor=fill, padding=(10, 6), relief="flat", borderwidth=1)
        hover = COLORS.accent_hover if primary else "#941e14" if danger else COLORS.surface_muted
        style.map(name, background=[("disabled", COLORS.surface_muted), ("pressed", hover), ("active", hover)],
                  foreground=[("disabled", COLORS.text_secondary)],
                  bordercolor=[("focus", COLORS.primary), ("active", COLORS.primary)],
                  relief=[("pressed", "sunken"), ("!pressed", "flat")])
    style.configure("Tool.TButton", anchor="w")
    style.configure("Blue.TButton", font=TYPOGRAPHY.button_text, foreground="#ffffff", background=COLORS.primary,
                    bordercolor=COLORS.primary, lightcolor=COLORS.primary, darkcolor=COLORS.primary, padding=(10, 6))
    style.map("Blue.TButton", background=[("active", COLORS.primary_hover)], bordercolor=[("focus", COLORS.accent)])
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, padding=(8, 5), fieldbackground=COLORS.surface, foreground=COLORS.text_primary,
                        bordercolor=COLORS.border_strong, lightcolor=COLORS.surface, darkcolor=COLORS.surface)
        style.map(name, bordercolor=[("focus", COLORS.primary)],
                  fieldbackground=[("disabled", COLORS.surface_muted), ("readonly", COLORS.surface)],
                  foreground=[("disabled", COLORS.text_secondary)])
    for name in ("TCheckbutton", "TRadiobutton"):
        style.configure(name, background=COLORS.surface, foreground=COLORS.text_primary, font=TYPOGRAPHY.body)
        style.map(name, background=[("active", COLORS.surface)], foreground=[("disabled", COLORS.text_secondary)])
    style.configure("Treeview", background=COLORS.surface, fieldbackground=COLORS.surface, foreground=COLORS.text_primary,
                    rowheight=32, font=TYPOGRAPHY.table_text, bordercolor=COLORS.border)
    style.configure("Treeview.Heading", font=TYPOGRAPHY.button_text, foreground="#ffffff", background=COLORS.primary,
                    bordercolor=COLORS.primary, padding=(8, 7), relief="flat")
    style.map("Treeview.Heading", background=[("active", COLORS.primary_hover)])
    style.map("Treeview", background=[("selected", COLORS.primary)], foreground=[("selected", "#ffffff")])
    style.configure("TNotebook", background=COLORS.background, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(12, 7), font=TYPOGRAPHY.button_text, background=COLORS.surface, foreground=COLORS.text_primary)
    style.map("TNotebook.Tab", background=[("selected", COLORS.primary)], foreground=[("selected", "#ffffff")])
    return style


def build_suite_menu_bar(
    parent: tk.Misc,
    menus: Sequence[tuple[str, Sequence[tuple[str | None, Callable[[], object] | None]]]],
) -> ttk.Frame:
    bar = ttk.Frame(parent, style="Toolbar.TFrame", padding=(8, 0))
    for title, entries in menus:
        if not entries:
            continue
        button = ttk.Menubutton(bar, text=title, takefocus=True)
        menu = tk.Menu(button, tearoff=False)
        for label, command in entries:
            if label is None:
                menu.add_separator()
            else:
                menu.add_command(label=label, command=command)
        button.configure(menu=menu)
        button.pack(side="left", padx=(0, 4))
    return bar


def build_command_bar(
    parent: tk.Misc,
    commands: Sequence[tuple[str, Callable[[], object], str]],
) -> ttk.Frame:
    """Wrap a finite set of real commands using measured widget widths."""
    bar = ttk.Frame(parent, style="Toolbar.TFrame")
    buttons = [ttk.Button(bar, text=label, command=command, style=style) for label, command, style in commands]
    previous: list[tuple[int, int]] = []

    def layout(event: tk.Event | None = None) -> None:
        nonlocal previous
        width = max(1, event.width if event is not None else bar.winfo_width())
        positions = []
        row = 0
        column = 0
        used = 0
        for button in buttons:
            requested = button.winfo_reqwidth() + 6
            if used and used + requested > width:
                row += 1
                column = 0
                used = 0
            positions.append((row, column))
            used += requested
            column += 1
        if positions == previous:
            return
        previous = positions
        for button, (row, column) in zip(buttons, positions):
            button.grid(row=row, column=column, padx=(0, 6), pady=3, sticky="w")
    bar.bind("<Configure>", layout)
    for column, button in enumerate(buttons):
        button.grid(row=0, column=column, padx=(0, 6), pady=3, sticky="w")
    return bar
