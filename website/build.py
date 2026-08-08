"""
DinkyDash Static Site Generator

This script builds the DinkyDash website by converting Markdown files to HTML
using Jinja2 templates. It processes content from the 'content/' directory
and outputs static HTML files to the '../docs/' directory for GitHub Pages.

Usage:
    python build.py

The build process:
1. Reads Markdown files from content/ directory
2. Extracts YAML front matter (title, description, template)
3. Converts Markdown to HTML
4. Renders content using Jinja2 templates
5. Outputs static HTML with clean URLs (e.g., about.md → about/index.html)
6. Writes sitemap.xml and robots.txt
7. Copies images and preserves CNAME file
"""

import os
import shutil
import subprocess
from xml.sax.saxutils import escape
from jinja2 import Environment, FileSystemLoader
import markdown
import yaml

# Set up Jinja2 environment. Autoescaping keeps a title or description
# containing & or " from breaking the meta tags it gets rendered into;
# the converted Markdown is passed through with `| safe`.
env = Environment(loader=FileSystemLoader('templates'), autoescape=True)

# Set output directory to '../docs'
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs'))

# Canonical origin, used for canonical tags, og:url and the sitemap
SITE_URL = 'https://dinkydash.co'


def read_markdown(filename):
    with open(filename, 'r') as file:
        content = file.read().split('---', 2)
        if len(content) > 2:
            front_matter = yaml.safe_load(content[1])
            markdown_content = content[2]
        else:
            front_matter = {}
            markdown_content = content[0]
        return front_matter, markdown.markdown(markdown_content, extensions=['fenced_code', 'tables'])


def git_last_modified(file_path):
    """Return the file's last commit date as YYYY-MM-DD, or None if unavailable.

    Uses the commit date rather than the filesystem mtime, which would just be
    the checkout time on a fresh clone. Uncommitted edits are not reflected,
    which is correct: what gets deployed is what was committed.
    """
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%cs', '--', file_path],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip() or None


def generate_sitemap(pages):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url_path, source_files in sorted(pages):
        lines.append('  <url>')
        lines.append(f'    <loc>{escape(SITE_URL + url_path)}</loc>')
        # A page's real content is its Markdown plus the template rendering it —
        # the home page in particular lives almost entirely in its template.
        dates = [d for d in (git_last_modified(f) for f in source_files) if d]
        if dates:
            lines.append(f'    <lastmod>{max(dates)}</lastmod>')
        lines.append('  </url>')
    lines.append('</urlset>')

    with open(os.path.join(OUTPUT_DIR, 'sitemap.xml'), 'w') as f:
        f.write('\n'.join(lines) + '\n')


def generate_robots():
    content = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
    with open(os.path.join(OUTPUT_DIR, 'robots.txt'), 'w') as f:
        f.write(content)


def copy_images():
    if os.path.exists('images'):
        output_image_dir = os.path.join(OUTPUT_DIR, 'images')
        if os.path.exists(output_image_dir):
            shutil.rmtree(output_image_dir)
        shutil.copytree('images', output_image_dir)


def generate_pages():
    """Render every Markdown file, returning (url_path, source_files) per page."""
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pages = []

    for root, dirs, files in os.walk('content'):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                front_matter, content = read_markdown(file_path)

                # Determine output path and the clean URL it will be served at
                rel_path = os.path.relpath(file_path, 'content')
                base_name = os.path.splitext(rel_path)[0]

                if base_name == 'index':
                    # For index.md, keep it at the root of its directory
                    output_path = os.path.join(OUTPUT_DIR, os.path.dirname(rel_path), 'index.html')
                    url_path = '/'
                else:
                    # For other files, create a subdirectory
                    output_path = os.path.join(OUTPUT_DIR, base_name, 'index.html')
                    url_path = '/' + base_name.replace(os.sep, '/') + '/'

                template_name = front_matter.get('template', 'page.html')
                template = env.get_template(template_name)

                output = template.render(
                    content=content,
                    canonical_url=SITE_URL + url_path,
                    **front_matter,
                )

                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Write output
                with open(output_path, 'w') as f:
                    f.write(output)

                pages.append((url_path, (file_path, os.path.join('templates', template_name))))

    return pages


def preserve_cname():
    cname_path = os.path.join(OUTPUT_DIR, 'CNAME')
    if os.path.exists(cname_path):
        with open(cname_path, 'r') as f:
            cname_content = f.read()
        return cname_content
    return None


def restore_cname(cname_content):
    if cname_content:
        cname_path = os.path.join(OUTPUT_DIR, 'CNAME')
        with open(cname_path, 'w') as f:
            f.write(cname_content)


if __name__ == '__main__':
    # Preserve CNAME content
    cname_content = preserve_cname()

    # Clear the output directory if it exists
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    pages = generate_pages()
    generate_sitemap(pages)
    generate_robots()
    copy_images()

    # Restore CNAME file
    restore_cname(cname_content)

    print(f"Site generated in {OUTPUT_DIR} ({len(pages)} pages)")