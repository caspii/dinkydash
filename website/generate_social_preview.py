#!/usr/bin/env python3
"""Generator for the repository's social preview card (GitHub, Slack, Reddit).

Not part of `build.py` — the output is committed, so a normal build needs no
browser. Re-run this only if the card's wording, the palette or the board image
changes:

    python3 generate_social_preview.py     # requires Pillow and Google Chrome

Writes:
    images/social-preview.png       1280x640

That one file is the card in three places: the repository's social preview, the
`og:image` for every page on dinkydash.co (website/templates/base.html), and the
banner at the top of the root README.

Only the first needs a human. GitHub exposes no API for the social preview — it
is a browser-only upload at Settings > General > Social preview — so this
script's job ends at the file and somebody has to click. The 1280x640 size and
the 40pt safe border are GitHub's own recommendation, from their
repository-open-graph-template; their guides are drawn 80px in from every edge,
which is that 40pt at 2x.

WHY A CARD AND NOT A PHOTOGRAPH. The preview that was set before this was
`og-hero.jpg` — a kitchen with an abstract panel on the wall. It is a nice
photograph of a room and it says nothing: no name, no product, and the panel is
not even the board. This card names the thing, says what it is, and shows the
real board, in that order of size, because that is the order a stranger reads
them in.

The board shown is `images/family-dashboard-board.webp`, the marketing site's
own board image, rather than the README's `screenshot.png`. Same dimensions and
same layout; it simply has a fuller day on it and a family name that reads like
a family's — "THE WILSONS" rather than the default config's "OUR FAMILY". Using
the site's image also means the card and the shop window show the same day.

WHY IT IS DRAWN IN A BROWSER. Nunito ships here as woff2 only, which Pillow
cannot read; Chrome can. Rendering the card as HTML also means the palette is
the same set of hex values the board and the site already use, copied from one
place, rather than a second set maintained in an image editor.

Two headless-Chrome traps, both documented in ../CLAUDE.md and both avoided
below: `--window-size` does not reliably produce the viewport it names, so the
card is a fixed-size element captured from the top-left of a deliberately larger
window and cropped to size afterwards; and Chrome silently reuses a running
instance unless each run gets its own `--user-data-dir`.

Everything the page needs is inlined as a data URL — the font and the
screenshot. That keeps the temporary file self-contained, so Chrome needs no
file-access flags and there is no chance of capturing a card with the fallback
font in it.
"""

import base64
import os
import shutil
import subprocess
import sys
import tempfile
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

FONT = os.path.join(HERE, 'static', 'fonts', 'nunito-latin.woff2')
BOARD = os.path.join(HERE, 'images', 'family-dashboard-board.webp')
OUTPUT = os.path.join(HERE, 'images', 'social-preview.png')

WIDTH, HEIGHT = 1280, 640

# Drawn at 2x and downsampled with LANCZOS, the same supersampling trick
# generate_favicon.py uses. Chrome's own text rendering at 1x is fine; the
# screenshot inside the bezel is what benefits, since it is being reduced.
SCALE = 2

CHROME = os.environ.get(
    'CHROME',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
)

# The palette, copied from web/templates/board.html and website/templates/
# base.html. Nothing here is a new colour.
INK = '#2d2319'          # --text
MID = '#5c4a3a'          # --text-mid
CREAM = '#fffaf5'        # site --bg
BEZEL = '#17120f'        # the board's dark-theme --bg, used as a panel frame
ORANGE = '#e85d24'       # --accent
PURPLE = '#7c5cbf'
GREEN = '#16a34a'
BLUE = '#3b82f6'

# The four dots of the mark, in the mark's own order — orange top-left, purple
# top-right, green bottom-left, blue bottom-right — against the four things the
# board puts on the wall. The legend is laid out as a 2x2 grid for the same
# reason: at the size this card is usually seen, the board is an illegible
# rectangle, and this row of colour is what says what is in it.
LEGEND = [
    (ORANGE, "Today's agenda"),
    (PURPLE, 'Whose turn'),
    (GREEN, 'Countdowns'),
    (BLUE, 'A line from Claude'),
]

# The repository description's first sentence, verbatim, minus the list of
# screens a card has no room for. Keeping the words identical to the README's
# first line and to `gh repo view --json description` is the point: the card and
# the line GitHub prints beside it should not disagree.
#
# The breaks are set by hand rather than left to the box. This is a fixed-size
# poster, so the lines can break where the sense breaks.
TAGLINE = ['The digital family', 'calendar for screens', 'you already own.']


def data_url(path, mime):
    with open(path, 'rb') as handle:
        return f'data:{mime};base64,' + base64.b64encode(handle.read()).decode('ascii')


def mark(size):
    """The DinkyDash mark, identical to static/favicon.svg."""
    return f'''<svg class="mark" width="{size}" height="{size}" viewBox="0 0 128 128">
      <rect width="128" height="128" rx="26" ry="26" fill="{ORANGE}"/>
      <g fill="{CREAM}">
        <rect x="20" y="20" width="40" height="40" rx="9"/>
        <rect x="68" y="20" width="40" height="40" rx="9"/>
        <rect x="20" y="68" width="40" height="40" rx="9"/>
        <rect x="68" y="68" width="40" height="40" rx="9"/>
      </g>
      <g>
        <circle cx="40" cy="40" r="8" fill="{ORANGE}"/>
        <circle cx="88" cy="40" r="8" fill="{PURPLE}"/>
        <circle cx="40" cy="88" r="8" fill="{GREEN}"/>
        <circle cx="88" cy="88" r="8" fill="{BLUE}"/>
      </g>
    </svg>'''


def build_html():
    font = data_url(FONT, 'font/woff2')
    board = data_url(BOARD, 'image/webp')
    legend = '\n'.join(
        f'<li><span class="dot" style="background:{colour}"></span>{label}</li>'
        for colour, label in LEGEND
    )
    tagline = '<br>'.join(TAGLINE)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
@font-face {{
    font-family: 'Nunito';
    font-style: normal;
    font-weight: 200 1000;
    font-display: block;
    src: url({font}) format('woff2');
}}

*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

html, body {{ background: #ffffff; }}

/* The card is a fixed-size element at the top-left of the page. The window
   around it is deliberately bigger and gets cropped away, because Chrome
   cannot be trusted to give the viewport --window-size asks for. */
.card {{
    position: absolute;
    top: 0;
    left: 0;
    width: {WIDTH}px;
    height: {HEIGHT}px;
    background: {CREAM};
    font-family: 'Nunito', sans-serif;
    color: {INK};
    -webkit-font-smoothing: antialiased;

    display: flex;
    align-items: center;
    /* GitHub's own repository-open-graph-template draws its safe-area guides
       at 80px in from every edge on a 1280x640 card — that is the 40pt border
       their note asks for. Nothing but the panel's shadow crosses it. */
    padding: 56px 84px;
}}

/* Exactly as tall as the bezel beside it, with the three blocks pushed to the
   ends. That is the card's only alignment: the mark starts where the panel
   starts and the legend ends where the panel ends. */
.words {{
    width: 440px;
    height: 386px;
    flex: none;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}

.lockup {{ display: flex; align-items: center; gap: 20px; }}
.mark {{ display: block; border-radius: 13px; }}
.wordmark {{
    font-size: 62px;
    font-weight: 800;
    letter-spacing: -0.022em;
    line-height: 1;
}}

.tagline {{
    font-size: 40px;
    font-weight: 700;
    line-height: 1.24;
    letter-spacing: -0.014em;
}}

.legend {{
    list-style: none;
    display: grid;
    /* Content-sized rather than half-and-half: two even columns would push the
       right-hand pair out towards the panel for no reason. */
    grid-template-columns: auto auto;
    justify-content: start;
    column-gap: 30px;
    row-gap: 17px;
}}
.legend li {{
    display: flex;
    align-items: center;
    gap: 11px;
    font-size: 21px;
    font-weight: 600;
    color: {MID};
    white-space: nowrap;
}}
.dot {{
    width: 13px;
    height: 13px;
    border-radius: 50%;
    flex: none;
}}

/* A wall panel, not a browser window: a dark frame the thickness of a real
   bezel, and the dark used is the board's own dark-theme background. On cream
   it is also what gives the card a shape at thumbnail size, where a white
   board on a cream card would disappear. */
.panel {{
    flex: none;
    margin-left: auto;
    padding: 13px;
    border-radius: 21px;
    background: {BEZEL};
    box-shadow: 0 26px 60px rgba(45, 35, 25, 0.17),
                0 5px 14px rgba(45, 35, 25, 0.08);
}}
.panel img {{
    display: block;
    width: 600px;
    height: 360px;   /* 5:3, the 800x480 panel the board is drawn for */
    border-radius: 8px;
}}
</style>
</head>
<body>
<div class="card">
    <div class="words">
        <div class="lockup">
            {mark(58)}
            <div class="wordmark">DinkyDash</div>
        </div>
        <p class="tagline">{tagline}</p>
        <ul class="legend">
{legend}
        </ul>
    </div>
    <div class="panel"><img src="{board}" alt=""></div>
</div>
</body>
</html>'''


def _wait_for(path, process, limit=60.0):
    """Block until `path` has been written and stopped growing, then kill Chrome."""
    deadline = time.monotonic() + limit
    last, stable = -1, 0
    try:
        while time.monotonic() < deadline:
            size = os.path.getsize(path) if os.path.exists(path) else -1
            stable = stable + 1 if size > 0 and size == last else 0
            if stable >= 3:
                return
            # Chrome exiting on its own is not the happy path here — it is a
            # launch failure. Say so now rather than sitting out the deadline.
            if size < 0 and process.poll() is not None:
                sys.exit(f'Chrome exited ({process.returncode}) without writing a screenshot.')
            last = size
            time.sleep(0.25)
        sys.exit('Chrome never wrote a screenshot.')
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def render(html):
    """Screenshot the card with headless Chrome and crop it to size."""
    if not os.path.exists(CHROME):
        sys.exit(f'Chrome not found at {CHROME} — set CHROME to its path.')

    work = tempfile.mkdtemp(prefix='dinkydash-og-')
    try:
        page = os.path.join(work, 'card.html')
        shot = os.path.join(work, 'card.png')
        with open(page, 'w', encoding='utf-8') as handle:
            handle.write(html)

        chrome = subprocess.Popen(
            [
                CHROME,
                '--headless=new',
                '--disable-gpu',
                '--hide-scrollbars',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-sync',
                f'--force-device-scale-factor={SCALE}',
                # Bigger than the card on purpose; the surplus is cropped off.
                f'--window-size={WIDTH + 80},{HEIGHT + 80}',
                # Chrome reuses a running instance without this, and every run
                # after the first silently returns the first one's page.
                f'--user-data-dir={os.path.join(work, "profile")}',
                # Long enough for the inlined font to load and lay out. It is
                # `font-display: block`, so nothing paints in the fallback.
                '--virtual-time-budget=4000',
                f'--screenshot={shot}',
                f'file://{page}',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Chrome writes the screenshot and then does not exit — it sits there
        # until something kills it, the same way `--screenshot` hangs on the
        # board's meta refresh. Waiting on the process is therefore waiting for
        # a timeout; wait for the file instead, and let it settle in case the
        # write is still in flight.
        _wait_for(shot, chrome)

        with Image.open(shot) as raw:
            box = (0, 0, WIDTH * SCALE, HEIGHT * SCALE)
            if raw.width < box[2] or raw.height < box[3]:
                sys.exit(
                    f'Chrome rendered {raw.width}x{raw.height}, too small to '
                    f'crop {box[2]}x{box[3]} from. Raise --window-size.'
                )
            card = raw.convert('RGB').crop(box)
            return card.resize((WIDTH, HEIGHT), Image.LANCZOS)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    for path in (FONT, BOARD):
        if not os.path.exists(path):
            sys.exit(f'missing: {path}')

    card = render(build_html())
    card.save(OUTPUT, optimize=True)
    print(f'wrote {os.path.relpath(OUTPUT, REPO)}  {card.width}x{card.height}')
    print('Run website/build.py to copy it into docs/, then upload it at')
    print('Settings > General > Social preview — GitHub has no API for that one.')


if __name__ == '__main__':
    main()
