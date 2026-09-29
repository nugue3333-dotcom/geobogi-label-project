from __future__ import annotations

"""Create crisp ChaeumLAB assets from the approved supplied logo artwork."""

from argparse import ArgumentParser
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT.parent / "로고기본가로.png"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "brand"


def _is_logo_pixel(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    return alpha > 8 and min(red, green, blue) < 245


def _foreground_box(image: Image.Image) -> tuple[int, int, int, int]:
    pixels = image.convert("RGBA")
    matches = [(x, y) for y in range(pixels.height) for x in range(pixels.width) if _is_logo_pixel(pixels.getpixel((x, y)))]
    if not matches:
        raise ValueError("Approved logo does not contain visible artwork.")
    xs, ys = zip(*matches)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _symbol_box(image: Image.Image, full_box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    rgba = image.convert("RGBA")
    left, top, right, bottom = full_box
    columns = [any(_is_logo_pixel(rgba.getpixel((x, y))) for y in range(top, bottom)) for x in range(left, right)]
    gap_start: int | None = None
    for index, present in enumerate(columns):
        if present:
            gap_start = None
            continue
        if gap_start is None:
            gap_start = index
        if index - gap_start >= 28:
            right = left + gap_start
            break
    symbol_pixels = [
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if _is_logo_pixel(rgba.getpixel((x, y)))
    ]
    xs, ys = zip(*symbol_pixels)
    padding = max(18, round((max(xs) - min(xs) + 1) * 0.12))
    return (
        max(0, min(xs) - padding),
        max(0, min(ys) - padding),
        min(rgba.width, max(xs) + 1 + padding),
        min(rgba.height, max(ys) + 1 + padding),
    )


def _make_transparent(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    data = []
    for red, green, blue, alpha in rgba.getdata():
        # The approved PNG has a white canvas with faint compression halos.
        # Treat near-white pixels as transparent so they do not appear as a box at small icon sizes.
        if red > 220 and green > 220 and blue > 220:
            data.append((255, 255, 255, 0))
        else:
            data.append((red, green, blue, alpha))
    rgba.putdata(data)
    return rgba


def _fit_canvas(image: Image.Image, size: int, *, margin: int = 0) -> Image.Image:
    usable = max(1, size - margin * 2)
    scale = min(usable / image.width, usable / image.height)
    target = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(target, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((size - target[0]) // 2, (size - target[1]) // 2))
    return canvas


def _white_mark(mark: Image.Image) -> Image.Image:
    converted = Image.new("RGBA", mark.size, (0, 0, 0, 0))
    data = []
    for _red, _green, _blue, alpha in mark.getdata():
        if alpha == 0:
            data.append((255, 255, 255, 0))
        else:
            data.append((255, 255, 255, alpha))
    converted.putdata(data)
    return converted


def _app_icon(mark: Image.Image, *, dark_background: bool) -> Image.Image:
    icon = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    if dark_background:
        draw.rounded_rectangle((44, 44, 980, 980), radius=208, fill=(19, 39, 46, 255), outline=(40, 71, 79, 255), width=16)
        icon.alpha_composite(_fit_canvas(_white_mark(mark), 1024, margin=180))
        return icon

    # Explorer usually renders this asset at 16px. A full logo becomes a dark
    # blur at that size, so use the approved C + lime point motif directly.
    tile = (247, 250, 244, 255)
    lime = (151, 211, 46, 255)
    ink = (27, 42, 47, 255)
    draw.rounded_rectangle((34, 34, 990, 990), radius=210, fill=tile, outline=lime, width=34)

    # The cutout intentionally runs past the right edge to preserve the open C
    # form at every ICO size, including 16px.
    draw.rounded_rectangle((214, 236, 790, 788), radius=112, fill=ink)
    draw.rounded_rectangle((365, 356, 854, 670), radius=58, fill=tile)
    draw.rounded_rectangle((596, 470, 716, 590), radius=18, fill=lime)
    return icon


def _label_file_icon() -> Image.Image:
    """Build a document icon that stays legible in Explorer's 16px view."""
    icon = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    paper = (250, 252, 249, 255)
    fold = (222, 238, 210, 255)
    lime = (151, 211, 46, 255)
    ink = (27, 42, 47, 255)
    outline = (82, 103, 108, 255)

    # A document silhouette is easier to distinguish from the application at
    # 16px than the previous rounded tile with a thin lime outline.
    draw.rounded_rectangle((142, 62, 882, 962), radius=104, fill=paper, outline=outline, width=42)
    draw.polygon(((674, 62), (882, 270), (882, 62)), fill=(0, 0, 0, 0))
    draw.polygon(((674, 62), (882, 270), (674, 270)), fill=fold, outline=outline)
    draw.line(((674, 62), (674, 270), (882, 270)), fill=outline, width=42, joint="curve")

    # Bold C + lime point motif. Avoid hairlines because Windows downsamples
    # this frame to 16x16 in a normal Details view.
    draw.rounded_rectangle((270, 350, 728, 790), radius=86, fill=ink)
    draw.rounded_rectangle((388, 446, 778, 694), radius=46, fill=paper)
    draw.rounded_rectangle((566, 510, 666, 610), radius=16, fill=lime)
    return icon


def _save_icon(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def create_assets(source_path: Path, output_dir: Path = OUTPUT_DIR) -> None:
    with Image.open(source_path) as source:
        source = source.convert("RGBA")
        full_box = _foreground_box(source)
        full_logo = _make_transparent(source.crop(tuple(max(0, value - 24) if index < 2 else value + 24 for index, value in enumerate(full_box))))
        mark = _make_transparent(source.crop(_symbol_box(source, full_box)))

    output_dir.mkdir(parents=True, exist_ok=True)
    mark_1024 = _fit_canvas(mark, 1024)
    mark_1024.save(output_dir / "chaeumlab_mark.png")
    mark_1024.save(output_dir / "chaeumlab_logo_compact.png")

    header_2x = full_logo.resize((960, max(1, round(full_logo.height * 960 / full_logo.width))), Image.Resampling.LANCZOS)
    header = header_2x.resize((480, max(1, round(header_2x.height / 2))), Image.Resampling.LANCZOS)
    header_2x.save(output_dir / "chaeumlab_logo_header_2x.png")
    header.save(output_dir / "chaeumlab_logo_header.png")

    white_background_icon = _app_icon(mark, dark_background=False)
    dark_background_icon = _app_icon(mark, dark_background=True)
    label_file_icon = _label_file_icon()
    white_background_icon.save(output_dir / "chaeumlab_app_icon.png")
    white_background_icon.save(output_dir / "chaeumlab_app_icon_white.png")
    label_file_icon.save(output_dir / "chaeumlab_label_file_icon_white.png")
    dark_background_icon.save(output_dir / "chaeumlab_app_icon_dark.png")
    _save_icon(white_background_icon, output_dir / "chaeumlab_app_icon.ico")
    _save_icon(white_background_icon, output_dir / "chaeumlab_app_icon_white.ico")
    _save_icon(label_file_icon, output_dir / "chaeumlab_label_file_icon_white.ico")


def main() -> int:
    parser = ArgumentParser(description="Create the official ChaeumLAB app icons and header assets.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    create_assets(args.source, args.output)
    print(f"브랜드 자산 생성 완료: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
