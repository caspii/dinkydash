# The marketing site

Guidance for `website/`. The root `CLAUDE.md` holds the rules that apply to every change.
`website/README.md` is the fuller guide to building the site and to what belongs in
`images/` — read it before adding an image or a page.

**`website/` never runs on the board**, and that is what settles most questions here.

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
  deployed on the same App Platform container as the board with `wsgi.py` routing on the
  `Host` header. **Adding a page is writing a Markdown file, and nothing else.**
- **GitHub Pages is switched off**, and it took until 8 September to notice. The setting outlived
  the directory: it kept failing on every push *and* kept serving the last good build, so a stale
  copy of this whole site sat on `caspii.github.io` for a fortnight. See
  [doc/operations.md](../doc/operations.md). Nothing here should ever be written to be served from
  two places at once.
- **Nunito lives here twice on purpose.** `website/static/fonts/` and `web/static/fonts/`
  are separate deployables, so editing one means editing both. The site's copy carries the
  italic pair as well; the board's does not, because the board never sets italic.

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
