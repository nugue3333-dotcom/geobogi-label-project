"""Build the approved role badges around the unmodified official brand mark."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/brand"
BLUE = "#143e70"
LIME = "#a3d900"
SIZES = [(value, value) for value in (16, 24, 32, 48, 64, 128, 256)]


def create_suite_icons(output: Path = ASSETS) -> list[Path]:
    with Image.open(ASSETS / "chaeumlab_mark.png") as source:
        mark = source.convert("RGBA")
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    names = {
        "designer": "chaeumlab_designer_icon",
        "manager": "chaeumlab_manager_icon",
        "settings": "chaeumlab_settings_icon",
        "document": "chaeumlab_label_file_icon_white",
        "project": "chaeumlab_project_file_icon_white",
    }
    for role, name in names.items():
        image = Image.new("RGBA", (1024, 1024))
        draw = ImageDraw.Draw(image)
        if role == "document":
            draw.rounded_rectangle((150, 48, 870, 966), radius=66, fill="white", outline=BLUE, width=30)
            draw.rounded_rectangle((246, 116, 774, 184), radius=12, fill=LIME)
            frame = (230, 220, 800, 790)
        elif role == "project":
            draw.rounded_rectangle((68, 190, 944, 962), radius=70, fill="white", outline=BLUE, width=30)
            draw.rounded_rectangle((80, 88, 504, 252), radius=26, fill=BLUE)
            frame = (210, 280, 810, 880)
        else:
            draw.rounded_rectangle((40, 40, 984, 984), radius=182, fill="white", outline=BLUE, width=30)
            frame = (130, 130, 890, 890)
        scaled = mark.resize((frame[2] - frame[0], frame[3] - frame[1]), Image.Resampling.LANCZOS)
        image.alpha_composite(scaled, frame[:2])
        badge = (642, 654, 982, 994)
        draw.rounded_rectangle(badge, radius=52, fill=BLUE)
        x, y = 642, 654
        if role == "designer":
            draw.line(((x + 80, y + 254), (x + 264, y + 70)), fill="white", width=30)
            draw.polygon(((x + 62, y + 280), (x + 76, y + 224), (x + 120, y + 270)), fill="white")
        elif role == "manager":
            draw.rounded_rectangle((x + 52, y + 110, x + 288, y + 248), radius=16, outline="white", width=26)
            draw.line(((x + 98, y + 58), (x + 244, y + 58)), fill="white", width=26)
            draw.line(((x + 98, y + 290), (x + 244, y + 290)), fill="white", width=26)
        elif role == "settings":
            points = []
            for index in range(32):
                angle = math.tau * index / 32
                radius = 126 if index % 4 in (1, 2) else 94
                points.append((x + 170 + radius * math.cos(angle), y + 170 + radius * math.sin(angle)))
            draw.polygon(points, fill="white")
            draw.ellipse((x + 98, y + 98, x + 242, y + 242), fill=BLUE)
            draw.ellipse((x + 137, y + 137, x + 203, y + 203), fill="white")
        elif role == "document":
            for row in (90, 170, 250):
                draw.line(((x + 78, y + row), (x + 270, y + row)), fill="white", width=30)
        else:
            draw.line(((x + 62, y + 170), (x + 264, y + 170)), fill="white", width=30)
            draw.line(((x + 190, y + 90), (x + 272, y + 170), (x + 190, y + 250)), fill="white", width=30)
        for extension in ("png", "ico"):
            path = output / f"{name}.{extension}"
            if extension == "ico":
                image.save(path, format="ICO", sizes=SIZES)
            else:
                image.save(path)
            paths.append(path)
    return paths


if __name__ == "__main__":
    print("SUITE_ICON_FILES:", len(create_suite_icons()))
