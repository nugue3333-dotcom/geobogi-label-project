from barcode_label_automation.ui_tokens import COLORS


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_small_secondary_text_has_readable_contrast_on_light_surfaces() -> None:
    for background in (COLORS.surface, COLORS.surface_subtle, COLORS.background, COLORS.surface_muted):
        assert _contrast(COLORS.text_tertiary, background) >= 4.5
