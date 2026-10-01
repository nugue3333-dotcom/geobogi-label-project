from __future__ import annotations

from dataclasses import dataclass

from .font_assets import APP_FONT_FAMILY, register_bundled_font


register_bundled_font()


@dataclass(frozen=True)
class ColorTokens:
    background: str = "#f3f6f5"
    surface: str = "#ffffff"
    surface_muted: str = "#eaf0ee"
    surface_subtle: str = "#f7f9f8"
    border: str = "#cfd9d6"
    border_subtle: str = "#e4eae8"
    border_strong: str = "#aebfba"
    grid: str = "#dde7e4"
    text_primary: str = "#152126"
    text_secondary: str = "#52666a"
    text_tertiary: str = "#596b6e"
    primary: str = "#123f46"
    primary_hover: str = "#0b3137"
    accent: str = "#72a91b"
    accent_hover: str = "#5f8f13"
    accent_soft: str = "#edf5dd"
    danger: str = "#c34b43"
    warning: str = "#b97b24"
    success: str = "#17785b"
    graphite: str = "#23474d"
    panel: str = "#f9fbfa"


@dataclass(frozen=True)
class TypographyTokens:
    page_title: tuple[str, int, str] = (APP_FONT_FAMILY, 20, "bold")
    section_title: tuple[str, int, str] = (APP_FONT_FAMILY, 12, "bold")
    body: tuple[str, int] = (APP_FONT_FAMILY, 10)
    caption: tuple[str, int] = (APP_FONT_FAMILY, 9)
    table_text: tuple[str, int] = (APP_FONT_FAMILY, 10)
    button_text: tuple[str, int, str] = (APP_FONT_FAMILY, 10, "bold")


@dataclass(frozen=True)
class SpacingTokens:
    page_padding: int = 20
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
