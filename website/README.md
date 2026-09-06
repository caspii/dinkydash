# DinkyDash Website

This directory contains the static site generator for the DinkyDash website.

## Structure

- `content/` - Markdown source files for the website pages
- `templates/` - Jinja2 HTML templates
- `images/` - Static images
- `static/` - Root files copied to the site verbatim (favicons, `CNAME`)
- `build.py` - Static site generator script
- `generate_favicon.py` - Redraws the favicons from `static/favicon.svg`; run only when that changes

The build writes to `../docs/`, which is what GitHub Pages serves. There is no `output/` directory —
`build.py` deletes and rewrites `../docs/` on every run.

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