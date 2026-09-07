#!/usr/bin/env python3
"""One-off generator for every raster icon a browser can't take from the SVG.

Run by hand, not by the site — the outputs are committed, so serving needs no
image library. Re-run this only if `static/favicon.svg` changes:

    python3 generate_favicon.py     # requires Pillow

It redraws the same mark as `static/favicon.svg` and `../web/static/favicon.svg`
(2x2 dashboard grid, site palette) rather than rasterising the SVG, which avoids
depending on an SVG renderer. Keep the three in sync by hand — the shape is
simple enough that this is cheaper than adding cairosvg to the toolchain.

Writes, for the marketing site:
    static/favicon.ico              16/32/48/64 — the /favicon.ico browsers guess at
    static/apple-touch-icon.png     180x180 — iOS home screen

and, for the app itself (the settings UI and the board, saved to a phone or a
tablet home screen from `/settings/manifest.webmanifest`):
    ../web/static/apple-touch-icon.png    180 — iOS, full bleed: iOS rounds it itself
    ../web/static/icon-192.png            192 — Android, rounded like the favicon
    ../web/static/icon-512.png            512 — Android, the install and splash icon
    ../web/static/icon-maskable-512.png   512 — Android adaptive, drawn inside the safe circle
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

# An Android maskable icon may be cropped to a circle of 80% of the width, so
# the grid has to sit inside that. At 0.72 the grid spans 50% of the width and
# its corners land at 70% — inside the safe circle with room to spare.
MASKABLE_GRID = 0.72


def draw_mark(size, radius=26, grid=1.0):
    """Render the icon at `size` px, drawn at SS x and downsampled.

    `radius` is the corner rounding in 128ths; pass 0 for a full-bleed square,
    which is what iOS and Android adaptive icons want — they apply their own
    mask, and rounded corners inside a rounded mask read as a shrunken icon.
    `grid` shrinks the four tiles about the centre without moving the edge.
    """
    px = size * SS
    scale = px / BASE
    img = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def s(v):
        return v * scale

    def g(v):
        """A 128-grid coordinate, pulled towards the centre by `grid`."""
        return s(64 + (v - 64) * grid)

    if radius:
        d.rounded_rectangle([0, 0, px - 1, px - 1], radius=s(radius), fill=ORANGE)
    else:
        d.rectangle([0, 0, px - 1, px - 1], fill=ORANGE)

    cells = [(20, 20), (68, 20), (20, 68), (68, 68)]
    for i, (x, y) in enumerate(cells):
        d.rounded_rectangle(
            [g(x), g(y), g(x + 40) - 1, g(y + 40) - 1], radius=s(9 * grid), fill=CREAM
        )
        # Dots read as colour at 32px+ and blur harmlessly at 16px.
        cx, cy, r = g(x + 20), g(y + 20), s(8 * grid)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DOTS[i])

    return img.resize((size, size), Image.LANCZOS)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, 'static')
    app = os.path.join(os.path.dirname(here), 'web', 'static')
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

    app_icons = [
        ('apple-touch-icon.png', draw_mark(180, radius=0)),
        ('icon-192.png', draw_mark(192)),
        ('icon-512.png', draw_mark(512)),
        ('icon-maskable-512.png', draw_mark(512, radius=0, grid=MASKABLE_GRID)),
    ]
    for name, img in app_icons:
        img.save(os.path.join(app, name), format='PNG')

    print(f"Wrote favicon.ico ({', '.join(str(s) for s in sizes)}) "
          f"and apple-touch-icon.png (180) to {out}")
    print(f"Wrote {', '.join(name for name, _ in app_icons)} to {app}")


if __name__ == '__main__':
    main()
