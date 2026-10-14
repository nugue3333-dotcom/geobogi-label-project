"""Consistent pictograms, independent of installed symbol fonts."""
from __future__ import annotations

from PIL import Image, ImageDraw

TOOL_ICON_NAMES = ('text', 'multiline_text', 'barcode', 'qr', 'image', 'box', 'line', 'table')


def render_tool_icon(name: str, size: int = 24) -> Image.Image:
    if name not in TOOL_ICON_NAMES:
        raise ValueError(f'Unknown tool icon: {name}')
    image = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = '#143E70'
    def line(points):
        draw.line(points, fill=color, width=6)
    if name in ('text', 'multiline_text'):
        line((15, 18, 81, 18)); line((48, 18, 48, 78)); line((32, 78, 64, 78))
        if name == 'multiline_text':
            line((20, 90, 76, 90))
    elif name == 'barcode':
        for x, width in ((12, 4), (23, 7), (37, 3), (48, 6), (61, 3), (71, 7), (84, 3)):
            draw.rectangle((x, 13, x + width, 83), fill=color)
    elif name == 'qr':
        for x, y in ((12, 12), (56, 12), (12, 56)):
            draw.rectangle((x, y, x + 27, y + 27), outline=color, width=4)
            draw.rectangle((x + 9, y + 9, x + 18, y + 18), fill=color)
        for x, y in ((56, 56), (75, 56), (56, 75), (75, 75)):
            draw.rectangle((x, y, x + 8, y + 8), fill=color)
    elif name == 'image':
        draw.rectangle((10, 12, 86, 84), outline=color, width=5)
        line((12, 74, 36, 40, 56, 66, 70, 50, 84, 70))
        draw.ellipse((61, 25, 73, 37), fill=color)
    elif name == 'box':
        draw.rectangle((12, 12, 84, 84), outline=color, width=5)
    elif name == 'line':
        line((14, 82, 82, 14))
    else:
        draw.rectangle((10, 12, 86, 84), outline=color, width=4)
        for x in (35, 61):
            line((x, 12, x, 84))
        for y in (36, 60):
            line((10, y, 86, y))
    return image.resize((size, size), Image.Resampling.LANCZOS)
