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
7. Copies images and the static/ root files (favicons, CNAME)
"""

import json
import os
import re
import shutil
import struct
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
        html = markdown.markdown(markdown_content, extensions=['fenced_code', 'tables'])
        return front_matter, enhance_images(html)


def image_size(path):
    """Return (width, height) for a local image, or None if it can't be read.

    Hand-rolled rather than pulling in Pillow: the site only ever ships WebP
    and JPEG, and a build dependency that exists to read four numbers is not
    worth the install.
    """
    try:
        with open(path, 'rb') as f:
            head = f.read(32)
            if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
                chunk = head[12:16]
                if chunk == b'VP8 ':
                    # Lossy: 3-byte frame tag, 3-byte start code, then 14-bit
                    # width and height (the top 2 bits are a scale hint).
                    w, h = struct.unpack('<HH', head[26:30])
                    return w & 0x3FFF, h & 0x3FFF
                if chunk == b'VP8L':
                    bits = struct.unpack('<I', head[21:25])[0]
                    return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
                if chunk == b'VP8X':
                    w = int.from_bytes(head[24:27], 'little') + 1
                    h = int.from_bytes(head[27:30], 'little') + 1
                    return w, h
                return None
            if head[:8] == b'\x89PNG\r\n\x1a\n':
                return struct.unpack('>II', head[16:24])
            if head[:2] == b'\xff\xd8':
                # JPEG: walk the segment chain to the frame header.
                f.seek(2)
                while True:
                    marker = f.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        return None
                    length = struct.unpack('>H', f.read(2))[0]
                    if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                        h, w = struct.unpack('>HH', f.read(5)[1:])
                        return w, h
                    f.seek(length - 2, 1)
    except (OSError, struct.error, IndexError):
        return None
    return None


def enhance_images(html):
    """Add width/height and loading hints to Markdown-generated <img> tags.

    Intrinsic dimensions stop the text below an image from jumping once it
    loads (Cumulative Layout Shift). Everything after the first image is
    lazy-loaded; the first one is left eager because on these pages it sits
    near the top and is usually the Largest Contentful Paint element.
    """
    seen = {'count': 0}

    def replace(match):
        tag, src = match.group(0), match.group(1)
        seen['count'] += 1
        attrs = []
        # Content images are written as /images/foo.webp and live in images/.
        size = image_size(src.lstrip('/')) if src.startswith('/images/') else None
        if size:
            attrs.append(f'width="{size[0]}" height="{size[1]}"')
        attrs.append('decoding="async"')
        if seen['count'] > 1:
            attrs.append('loading="lazy"')
        return tag[:-2].rstrip() + ' ' + ' '.join(attrs) + ' />'

    return re.sub(r'<img[^>]*\bsrc="([^"]+)"[^>]*/>', replace, html)


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


def faq_schema(faq):
    """Render a `faq:` front-matter list as FAQPage JSON-LD, or '' if absent.

    Google stopped showing FAQ rich results for sites like this one in 2023,
    so this is not a snippet play — it is there so answer engines parsing the
    page get the questions and answers as data rather than as prose.
    """
    if not faq:
        return ''
    data = {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': item['q'],
                'acceptedAnswer': {'@type': 'Answer', 'text': item['a']},
            }
            for item in faq
        ],
    }
    return json.dumps(data, indent=2)


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


def copy_static():
    """Copy static/ to the site root.

    These are files that have to sit at the root to work: browsers request
    /favicon.ico without being told to, and iOS looks for /apple-touch-icon.png.
    """
    if not os.path.exists('static'):
        return
    for name in sorted(os.listdir('static')):
        source = os.path.join('static', name)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(OUTPUT_DIR, name))


def generate_pages():
    """Render every Markdown file.

    Returns (sitemap_pages, written_count). These differ because `noindex`
    pages are still rendered, just kept out of the sitemap.
    """
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pages = []
    written = 0

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

                # Same sources the sitemap dates a page by: its Markdown and
                # the template that renders it.
                sources = (file_path, os.path.join('templates', template_name))
                dates = [d for d in (git_last_modified(f) for f in sources) if d]

                output = template.render(
                    content=content,
                    canonical_url=SITE_URL + url_path,
                    last_modified=max(dates) if dates else None,
                    faq_schema=faq_schema(front_matter.get('faq')),
                    **front_matter,
                )

                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Write output
                with open(output_path, 'w') as f:
                    f.write(output)
                written += 1

                # `noindex: true` pages stay out of the sitemap and carry a
                # robots meta tag. Used for pages whose content only exists once
                # query parameters are supplied — indexing the bare URL would
                # just add a thin page.
                if not front_matter.get('noindex'):
                    pages.append((url_path, (file_path, os.path.join('templates', template_name))))

    return pages, written


if __name__ == '__main__':
    # Clear the output directory if it exists. CNAME used to be read out of
    # here and written back afterwards, which meant a build that failed
    # between the two lost the custom domain; it now lives in static/ and is
    # copied in like any other root file.
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    pages, written = generate_pages()
    generate_sitemap(pages)
    generate_robots()
    copy_images()
    copy_static()

    print(f"Site generated in {OUTPUT_DIR} "
          f"({written} pages, {len(pages)} in sitemap)")