# DinkyDash Website

This directory is the DinkyDash marketing site, dinkydash.co. It is a Flask app that renders
Markdown through Jinja **on request** — there is no build step and no committed HTML.

## Structure

- `content/` - Markdown source files for the website pages
- `templates/` - Jinja2 HTML templates
- `images/` - Static images
- `static/` - Root files copied to the site verbatim (favicons, `CNAME`)
- `site.py` - The Flask app that serves the site
- `render.py` - Markdown to HTML, and the page/sitemap metadata
- `generate_favicon.py` - Redraws the favicons from `static/favicon.svg`; run only when that changes
- `generate_social_preview.py` - Draws `images/social-preview.png`, the repository's social preview
  card; run only when its wording, the palette or the board image changes

It used to build to `../docs/` for GitHub Pages. That directory is gone (DIN-27): the pages were
already Jinja templates, so rendering them when they are asked for removed 34 files of generated
HTML from the repository, the "I edited the copy and forgot to rebuild" failure, and a date bug the
build could not avoid — it stamped each page with the commit date of the commit *before* the one it
shipped in, because the build ran before that commit existed.

## Images

`images/` holds two kinds of file, and the difference matters.

**Product screenshots** are the real board and the real settings page, captured from the app running
against an *invented* family — `config.example.yaml`, or a copy of it, plus a payload from
`sample_board.py` or a one-off `generate()` call. Never a real config. Names, birthdays and calendar
URLs are the entire content of this app, and a screenshot published here is as public and as
permanent as a commit. Capture them the way `/preview` does, with a wrapper page holding an iframe
of exactly the target size: `--window-size` is not trustworthy for layout work, and the board's
`<meta http-equiv="refresh">` stops headless Chrome exiting, so wrap the call in `timeout`. Both
gotchas are written up in the root `CLAUDE.md`.

**Room photographs** are generated, by handing the image model a real screenshot and asking it to
reproduce the screen pixel-for-pixel inside a described scene. The screen is therefore the product;
the kitchen around it is not a real kitchen, and copy on the site must not claim it is.

Everything is WebP except the share cards — Open Graph scrapers are still patchy with WebP and a
share card is not worth the risk. `social-preview.png` is the card every page now points at, and the
one PNG: it is flat colour and small type, where PNG beats JPEG, and it doubles as the repository's
social preview, where GitHub's own template ships as a PNG.

`og-hero.jpg` and `og-board-kitchen.jpg` are the room photographs it replaced. Nothing references
them any more, and they stay anyway: every scraper that has already cached a share of this site
holds one of those two URLs, and deleting the file turns an old link preview into a broken image for
no gain. Do not add new references to them.

Nothing generates the card at build time. `generate_social_preview.py` writes it, the output is
committed, and the site serves it from `images/` like any other image. Setting it as the
repository's preview is a separate manual step — Settings → General → Social preview — because
GitHub exposes no API for that field. `render.py` reads intrinsic dimensions out of images referenced from
Markdown, but an image used directly in a template needs `width` and `height` on the tag by hand, or
the text below it jumps when the image lands.

## Building the Website

### Prerequisites

The site's own dependencies are in `requirements-site.txt`, not `requirements.txt` — a Raspberry Pi
has no business rendering landing pages, and `deploy_to_pi.sh` installs the smaller file:

```bash
pip install -r ../requirements-site.txt
```

### Running it

```bash
cd ..
FLASK_APP=website.site flask run --port 5001
```

A request for `/about/` reads `content/about.md`, renders it through the template its front matter
names, and returns it. `/sitemap.xml` and `/robots.txt` are generated the same way. Page discovery
and the git dates behind `lastmod` are read once at start-up, so a content change needs a restart —
which on the server is a deploy.

### How it is deployed

DigitalOcean App Platform, from `.do/app.yaml` at the repo root. Python buildpack, no Dockerfile,
`deploy_on_push` from `main`. To change the spec:

```bash
doctl apps update <app-id> --spec .do/app.yaml
```

**One thing only the dashboard can do**: create an app with a GitHub source. `doctl` has an API
token and no GitHub OAuth session, so it refuses to *introduce* one — though it will happily update
an app that already has one. DigitalOcean also will not let you change a component's source type
after creation, so an app made with a plain git URL has to be recreated rather than converted.

## Adding New Pages

1. Create a new `.md` file in the `content/` directory
2. Add YAML front matter at the top (optional):
   ```yaml
   ---
   title: Page Title
   description: Page description for SEO
   template: page.html
   ---
   ```
3. Write your content in Markdown below the front matter
4. Restart the site; the page is live at its clean URL

## Templates

- `base.html` - Base template with common layout, navigation, and analytics
- `page.html` - Standard page template (extends base.html)
- `index.html` - Homepage template with custom layout

## Deployment

The website is automatically deployed via GitHub Pages from the `docs/` directory when changes are pushed to the main branch.