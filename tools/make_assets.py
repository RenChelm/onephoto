"""Generate the launcher icon and presplash used by buildozer.

    python tools/make_assets.py
"""

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets")

BG_TOP = (26, 26, 34)
BG_BOTTOM = (16, 16, 20)
ACCENT = (79, 156, 249)
ACCENT_SOFT = (126, 186, 255)
PAPER = (236, 236, 241)


def _gradient(size, top, bottom):
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        ratio = y / float(size[1] - 1)
        draw.line([(0, y), (size[0], y)],
                  fill=tuple(int(top[i] + (bottom[i] - top[i]) * ratio)
                             for i in range(3)))
    return image


def _logo(draw, cx, cy, unit):
    """A cloud over three photo tiles."""
    # cloud
    # Lobe bottoms are kept level with the base slab so the silhouette
    # unions into one cloud instead of showing a notch.
    for dx, dy, r in ((-0.60, -0.34, 0.44), (0.02, -0.42, 0.58),
                      (0.64, -0.36, 0.40)):
        draw.ellipse([cx + (dx - r) * unit, cy + (dy - r) * unit,
                      cx + (dx + r) * unit, cy + (dy + r) * unit],
                     fill=ACCENT)
    draw.rounded_rectangle(
        [cx - 1.04 * unit, cy - 0.55 * unit, cx + 1.04 * unit, cy + 0.16 * unit],
        radius=0.20 * unit, fill=ACCENT)

    # three tiles below, the middle one lit up
    tile = 0.56 * unit
    gap = 0.16 * unit
    top = cy + 0.50 * unit
    left = cx - (tile * 1.5 + gap)
    for index in range(3):
        x0 = left + index * (tile + gap)
        draw.rounded_rectangle([x0, top, x0 + tile, top + tile],
                               radius=0.16 * unit,
                               fill=PAPER if index == 1 else ACCENT_SOFT)


def make_icon(size=512):
    image = _gradient((size, size), BG_TOP, BG_BOTTOM)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                           radius=int(size * 0.22), fill=255)
    rounded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rounded.paste(image, (0, 0), mask)
    _logo(ImageDraw.Draw(rounded), size / 2.0, size * 0.46, size * 0.19)
    return rounded


def make_presplash(size=1024):
    image = Image.new("RGB", (size, size), BG_BOTTOM)
    _logo(ImageDraw.Draw(image), size / 2.0, size * 0.46, size * 0.13)
    return image


def main():
    os.makedirs(ASSETS, exist_ok=True)
    icon_path = os.path.join(ASSETS, "icon.png")
    splash_path = os.path.join(ASSETS, "presplash.png")
    make_icon().save(icon_path)
    make_presplash().save(splash_path)
    print("wrote %s and %s" % (icon_path, splash_path))


if __name__ == "__main__":
    main()
