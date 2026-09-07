# The marketing site

Guidance for `website/`. The root `CLAUDE.md` holds the rules that apply to every change.
`website/README.md` is the fuller guide to building the site and to what belongs in
`images/` — read it before adding an image or a page.

**`website/` never runs on the board**, and that is what settles most questions here.

- **Its dependencies go in `requirements-dev.txt`, never `requirements.txt`.** The runtime
  list is what `deploy_to_pi.sh` installs on a Pi, and a Pi serves no marketing site. The
  site generator needs `jinja2`, `markdown` and `pyyaml`; the two image scripts need
  `Pillow`, and `generate_social_preview.py` also wants Chrome, which pip cannot install.
- **`docs/` is the build output, not a place to put documentation.** `build.py` deletes and
  rewrites it on every run, so a markdown file left there dies at the next build. It is
  committed because GitHub Pages serves it, which means a template change is not finished
  until the site is rebuilt.
- **Nunito lives here twice on purpose.** `website/static/fonts/` and `web/static/fonts/`
  are separate deployables, so editing one means editing both. The site's copy carries the
  italic pair as well; the board's does not, because the board never sets italic.

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
