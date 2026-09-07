# DinkyDash Website

This directory contains the static site generator for the DinkyDash website.

## Structure

- `content/` - Markdown source files for the website pages
- `templates/` - Jinja2 HTML templates
- `images/` - Static images
- `static/` - Root files copied to the site verbatim (favicons, `CNAME`)
- `build.py` - Static site generator script
- `generate_favicon.py` - Redraws the favicons from `static/favicon.svg`; run only when that changes
- `generate_social_preview.py` - Draws `images/social-preview.png`, the repository's social preview
  card; run only when its wording, the palette or the board image changes

The build writes to `../docs/`, which is what GitHub Pages serves. There is no `output/` directory —
`build.py` deletes and rewrites `../docs/` on every run.

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
committed, and `build.py` copies it to `docs/images/` like any other image. Setting it as the
repository's preview is a separate manual step — Settings → General → Social preview — because
GitHub exposes no API for that field. `build.py` reads intrinsic dimensions out of images referenced from
Markdown, but an image used directly in a template needs `width` and `height` on the tag by hand, or
the text below it jumps when the image lands.

## Building the Website

### Prerequisites

The site generator's dependencies are in the repo's `requirements-dev.txt`, not `requirements.txt`
— they are build-time only and are never installed on the Pi:

```bash
pip install -r ../requirements-dev.txt
```

### Build Process

To build the website, run:

```bash
cd website
python build.py
```

This will:
1. Read all Markdown files from the `content/` directory
2. Process YAML front matter in each Markdown file
3. Convert Markdown content to HTML
4. Apply Jinja2 templates from the `templates/` directory
5. Generate static HTML files in the `../docs/` directory
6. Copy images to the output directory
7. Preserve the CNAME file for custom domain

The generated files in `../docs/` are served by GitHub Pages at https://dinkydash.co/

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
4. Run `python build.py` to generate the HTML

## Templates

- `base.html` - Base template with common layout, navigation, and analytics
- `page.html` - Standard page template (extends base.html)
- `index.html` - Homepage template with custom layout

## Deployment

The website is automatically deployed via GitHub Pages from the `docs/` directory when changes are pushed to the main branch.