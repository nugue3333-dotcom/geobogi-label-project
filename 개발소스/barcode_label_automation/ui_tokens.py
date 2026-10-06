from __future__ import annotations

from dataclasses import dataclass

UI_FONT_FAMILY = "Malgun Gothic"


@dataclass(frozen=True)
class ColorTokens:
    background: str = "#e8edf2"
    surface: str = "#ffffff"
    surface_muted: str = "#e8edf2"
    surface_subtle: str = "#f3f5f7"
    border: str = "#adb7c0"
    border_subtle: str = "#d3dbe3"
    border_strong: str = "#8f9eac"
    grid: str = "#e7eaed"
    workspace: str = "#c9d0d8"
    text_primary: str = "#171a1e"
    text_secondary: str = "#4c5863"
    text_tertiary: str = "#4c5863"
    primary: str = "#143e70"
    primary_hover: str = "#0f3058"
    accent: str = "#a3d900"
    accent_hover: str = "#8cbd00"
    accent_soft: str = "#eef3e4"
    danger: str = "#b42318"
    warning: str = "#855a00"
    success: str = "#146b48"
    graphite: str = "#143e70"
    panel: str = "#ffffff"


@dataclass(frozen=True)
class TypographyTokens:
    page_title: tuple[str, int, str] = (UI_FONT_FAMILY, 16, "bold")
    section_title: tuple[str, int, str] = (UI_FONT_FAMILY, 11, "bold")
    body: tuple[str, int] = (UI_FONT_FAMILY, 10)
    caption: tuple[str, int] = (UI_FONT_FAMILY, 9)
    table_text: tuple[str, int] = (UI_FONT_FAMILY, 10)
    button_text: tuple[str, int, str] = (UI_FONT_FAMILY, 10, "bold")


@dataclass(frozen=True)
class SpacingTokens:
    page_padding: int = 12
    section_gap: int = 12
    card_padding: int = 16
    form_gap: int = 10
    table_cell_padding: int = 10


@dataclass(frozen=True)
class RadiusTokens:
    small: int = 4
    medium: int = 6
    large: int = 6


@dataclass(frozen=True)
class ShadowTokens:
    card_relief: str = "flat"
    elevation_relief: str = "solid"
    elevation_border_width: int = 1


COLORS = ColorTokens()
TYPOGRAPHY = TypographyTokens()
SPACING = SpacingTokens()
RADIUS = RadiusTokens()
SHADOWS = ShadowTokens()
