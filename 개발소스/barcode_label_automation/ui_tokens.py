from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorTokens:
    background: str = "#f6f8fb"
    surface: str = "#ffffff"
    surface_muted: str = "#eef3f8"
    surface_subtle: str = "#f8fbff"
    border: str = "#d8e2ee"
    border_strong: str = "#c6d4e5"
    text_primary: str = "#0b1b31"
    text_secondary: str = "#4d5e72"
    text_tertiary: str = "#7d899a"
    primary: str = "#07306f"
    primary_hover: str = "#042657"
    accent: str = "#1f7a5a"
    accent_hover: str = "#145c42"
    accent_soft: str = "#edf7f1"
    danger: str = "#ba1a1a"
    warning: str = "#b86b18"
    success: str = "#1f7a5a"
    graphite: str = "#0f2742"
    panel: str = "#f7fafd"


@dataclass(frozen=True)
class TypographyTokens:
    page_title: tuple[str, int, str] = ("Malgun Gothic", 20, "bold")
    section_title: tuple[str, int, str] = ("Malgun Gothic", 11, "bold")
    body: tuple[str, int] = ("Malgun Gothic", 10)
    caption: tuple[str, int] = ("Malgun Gothic", 9)
    table_text: tuple[str, int] = ("Malgun Gothic", 9)
    button_text: tuple[str, int, str] = ("Malgun Gothic", 10, "bold")


@dataclass(frozen=True)
class SpacingTokens:
    page_padding: int = 20
    section_gap: int = 12
    card_padding: int = 16
    form_gap: int = 10
    table_cell_padding: int = 8


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
