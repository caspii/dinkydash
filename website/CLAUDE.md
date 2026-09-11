# The marketing site

Guidance for `website/`. The root `CLAUDE.md` holds the rules that apply to every change.
`website/README.md` is the fuller guide to building the site and to what belongs in
`images/` — read it before adding an image or a page.

**`website/` never runs on the dashboard**, and that is what settles most questions here.

- **Its dependencies go in `requirements-site.txt`, never `requirements.txt`.** The runtime
  list is what `deploy_to_pi.sh` installs on a Pi, and a Pi serves no marketing site. The
  site needs `markdown`, `pyyaml` and `gunicorn`; the two image scripts need `Pillow` and
  live in `requirements-dev.txt`, and `generate_social_preview.py` also wants Chrome, which
  pip cannot install. `requirements-cloud.txt` pulls in the site's list, because one
  container serves both hostnames.
- **There is no build step and no `docs/` directory.** This said the opposite until DIN-27:
  `build.py` used to write `docs/` and GitHub Pages served it, so a template change was not
  finished until the site was rebuilt and the output committed. None of that is true now.
  `website/site.py` is a Flask app rendering `content/*.md` through `templates/` on request,
  deployed on the same App Platform container as the dashboard with `wsgi.py` routing on the
  `Host` header. **Adding a page is writing a Markdown file, and nothing else.**
- **GitHub Pages is switched off**, and it took until 8 September to notice. The setting outlived
  the directory: it kept failing on every push *and* kept serving the last good build, so a stale
  copy of this whole site sat on `caspii.github.io` for a fortnight. See
  [doc/operations.md](../doc/operations.md). Nothing here should ever be written to be served from
  two places at once.
- **Every link to the hosted app is written as `https://app.dinkydash.co/...` and rewritten
  at request time.** `render.APP_URL` is the origin the content and the homepage name;
  `site.py` swaps it for `DINKYDASH_APP_URL` when that is set, or for `127.0.0.1` on
  `CONDUCTOR_PORT` when only that is — Conductor sets it for every run script and it is the
  dashboard's port, so a preview's "Start your free trial" opens the dashboard being worked on
  rather than production even though Conductor reads its scripts from the main checkout. Keep
  writing the real address in Markdown — the file is the document a reader sees — and never a
  bare local port. `tests/test_site.py` checks every direction.
- **Nunito lives here twice on purpose.** `website/static/fonts/` and `web/static/fonts/`
  are separate deployables, so editing one means editing both. The site's copy carries the
  italic pair as well; the dashboard's does not, because the dashboard never sets italic.

## The per-provider calendar guides

`google-calendar-ical-link`, `icloud-calendar-link`, `outlook-calendar-ics-link` and
`cozi-calendar-display` are one page per provider: the onboarding documentation we owe
users either way. `getting-started` keeps the short steps and links out to each. The case
for them having their own URLs rather than being three bullets is in DIN-14.

Two things they need that no other page does:

- **Every example address is visibly fake**, with an `xxxx` run in it, the way
  `config.example.yaml` writes `private-xxxx`. `tests/test_site.py` walks `content/` and
  `templates/` and fails on a feed URL without one. gitleaks catches a real Google or iCloud
  address over the whole history; that test is what catches the shapes it has no rule for,
  before the commit. **Neither can read a screenshot** — check the address bar by hand.
- **An address goes in a ` ```url ` block, not a bare ` ``` ` one.** Code blocks scroll
  sideways on purpose, because wrapping a shell command invites somebody to paste half of it.
  A calendar address running off the right edge of the page that explains it is no use, so
  `base.html` gives `code.language-url` alone `white-space: pre-wrap`.

Only claim a step, a button name or a URL shape that a current provider support page confirms.
A guide that is confidently wrong about somebody else's settings screen is worse than no
guide, and these are the pages a stranger meets first.

## The per-device pages

`ipad-`, `android-tablet-`, `smart-tv-`, `fire-tv-` and `echo-show-calendar-display`, plus
`raspberry-pi-family-calendar`, which predates them. One page per screen somebody might
already own (DIN-13). Each links to the other five and to the provider guides, so the two
sets close a loop: *where do I get my calendar link* and *what do I put it on*.

Three rules, and the third is the one that will be tempting to break:

- **Every one of them states the architecture.** DinkyDash is a web page and something has to
  serve it — a Pi or an old computer on the network, or the hosted version. The device is the
  *screen*. Left implicit, every page reads as "install DinkyDash on your Fire TV", which is
  not a thing and never will be.
- **Nothing claims a native app**, because there is none. The wording is that it opens in the
  browser the device already has.
- **The verdicts are honest, including the negative one.** The Echo Show page says *do not*,
  because Silk closes itself after ten to fifteen minutes and Amazon exposes no way to stop
  it; the TV pages say a television is built to stop showing a still image. That page is the
  highest-volume term of the five, and answering it truthfully is the point rather than a cost.
  **Do not quietly upgrade a verdict to sell better.** If a device's behaviour changes, change
  the page and say what changed.

**None of this has been checked on real hardware.** The device claims come from current
manufacturer documentation and widely reported behaviour; the DinkyDash claims come from the
code — the meta-refresh reload, the aspect-ratio switch, flexbox `gap` as the oldest thing the
layout needs. Hands-on verification is [DIN-58](https://linear.app/keepthescore/issue/DIN-58),
and it is what should correct these pages. Nothing on them says "we tested this", and nothing
should until that is done.

The two dashboard screenshots — `family-calendar-tv-board.webp` (16:9) and
`family-calendar-tablet-board.webp` (portrait, which is what shows the single-column layout) —
are the real dashboard against `config.example.yaml` with a hand-written payload, the way
`README.md` describes. Regenerate them the same way rather than editing the images.

## The legal pages

`content/privacy.md` and `content/terms.md` are the hosted service's, and they are **claims
about what the code does**. A retention period is a promise that a `DELETE` exists; a
sub-processor list is a promise that nothing else is called. Changing what the app stores,
what it sends, or who it sends it to means changing those pages in the same commit — a
policy that has drifted from the code is worse than no policy, because somebody relied on it.

The contact address is `hi@keepthescore.com` on purpose: **`dinkydash.co` has no MX records**,
so it sends email and receives none. `dinkydash/mail.py` sets the same address as `Reply-To`
for that reason. When DinkyDash gets a mailbox, all three move together.

## The two image generators

Both are one-off scripts whose outputs are committed, so a normal build needs neither Pillow
nor a browser.

- **`generate_favicon.py`** redraws every raster icon from the same mark as
  `static/favicon.svg` — the site's `.ico` and apple-touch icon, and the app icons in
  `web/static/`. **Editing `favicon.svg` means re-running it**, or the `.ico` and the PNGs
  keep serving the old mark: `website/static/favicon.ico` sat two weeks behind its own SVG
  that way.
- **`generate_social_preview.py`** draws `images/social-preview.png`, which is the `og:image`
  for every page, the banner at the top of the root README, and the repository's social
  preview. Its own docstring carries the reasoning, including the two headless-Chrome traps
  it works around and why it renders HTML rather than drawing with Pillow. Setting the
  repository preview is a manual browser step; GitHub exposes no API for that field.
