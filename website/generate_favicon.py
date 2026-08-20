#!/usr/bin/env python3
"""One-off generator for the marketing site's raster icons.

Not part of `build.py` — the outputs are committed, so a normal build needs no
image library. Re-run this only if `static/favicon.svg` changes:

    python3 generate_favicon.py     # requires Pillow

It redraws the same mark as `static/favicon.svg` (2x2 dashboard grid, site
palette) rather than rasterising the SVG, which avoids depending on an SVG
renderer. Keep the two in sync by hand — the shape is simple enough that this
is cheaper than adding cairosvg to the toolchain.

Writes:
    static/favicon.ico          16/32/48/64 — the /favicon.ico browsers guess at
    static/apple-touch-icon.png 180x180 — iOS home screen
"""

import os

from PIL import Image, ImageDraw

ORANGE = (232, 93, 36, 255)      # --accent
CREAM = (255, 250, 245, 255)     # --bg
DOTS = [
    (232, 93, 36, 255),          # --accent
    (124, 92, 191, 255),         # --purple
    (22, 163, 74, 255),          # --green
    (59, 130, 246, 255),         # --blue
]

# Supersampling factor. The mark is drawn large and downscaled with LANCZOS,
# which is what keeps the rounded corners clean at 16px.
SS = 8
BASE = 128


def draw_mark(size):
    """Render the icon at `size` px, drawn at SS x and downsampled."""
    px = size * SS
    scale = px / BASE
    img = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def s(v):
        return v * scale

    d.rounded_rectangle([0, 0, px - 1, px - 1], radius=s(26), fill=ORANGE)

    cells = [(20, 20), (68, 20), (20, 68), (68, 68)]
    for i, (x, y) in enumerate(cells):
        d.rounded_rectangle(
            [s(x), s(y), s(x + 40) - 1, s(y + 40) - 1], radius=s(9), fill=CREAM
        )
        # Dots read as colour at 32px+ and blur harmlessly at 16px.
        cx, cy, r = s(x + 20), s(y + 20), s(8)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DOTS[i])

    return img.resize((size, size), Image.LANCZOS)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, 'static')
    os.makedirs(out, exist_ok=True)

    # Pillow's ICO writer derives every size from the one image it is given and
    # silently drops any size larger than the source — so hand it the largest
    # render, not the smallest.
    sizes = [16, 32, 48, 64]
    draw_mark(max(sizes)).save(
        os.path.join(out, 'favicon.ico'),
        format='ICO',
        sizes=[(s, s) for s in sizes],
    )

    draw_mark(180).save(os.path.join(out, 'apple-touch-icon.png'), format='PNG')

    print(f"Wrote favicon.ico ({', '.join(str(s) for s in sizes)}) "
          f"and apple-touch-icon.png (180) to {out}")


if __name__ == '__main__':
    main()
