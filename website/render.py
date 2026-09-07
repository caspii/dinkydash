"""Turning the marketing site's Markdown into HTML.

Everything here is pure: Markdown in, HTML and metadata out. No file is
written and no route is served, so the same functions render a page whether
they are called by a request or by a script.

That split is the point of DIN-27. `build.py` used to own all of this and
wrote the result to `docs/`, which meant every page carried the commit date of
the commit *before* the one it shipped in — the build ran before the commit it
was part of. Rendering when the page is asked for fixes that by construction.

Paths are resolved from this file rather than the working directory, because a
server does not get to choose where it was started from.
"""

import json
import re
import struct
import subprocess
from functools import lru_cache
from pathlib import Path

import markdown
import yaml

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "content"
TEMPLATES = HERE / "templates"
IMAGES = HERE / "images"
STATIC = HERE / "static"

# Canonical origin for canonical tags, og:url and the sitemap. Overridable so a
# staging copy does not tell search engines it is production.
SITE_URL = "https://dinkydash.co"


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
        size = image_size(IMAGES / src[len('/images/'):]) if src.startswith('/images/') else None
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


@lru_cache(maxsize=1)
def last_modified_map():
    """Every tracked file under content/ and templates/, to its last commit date.

    One `git log` rather than one per file. The per-file version meant 34
    subprocesses — two for each page — which cost about seventeen seconds on
    this repository's history and paid it again on every container start.

    The commit date rather than the filesystem mtime, which on a fresh clone or
    a deployed container is just the checkout time.
    """
    try:
        out = subprocess.run(
            # --relative, because git otherwise prints paths from the repository
            # root and the lookup below asks in terms of this directory.
            ["git", "log", "--format=%cs", "--name-only", "--relative",
             "--", "content", "templates"],
            capture_output=True, text=True, check=True, cwd=HERE).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {}

    dates, date = {}, None
    for line in out.splitlines():
        if not line.strip():
            continue
        if len(line) == 10 and line[4] == "-" and line[7] == "-":
            date = line          # git prints the date, then that commit's files
        elif date:
            dates.setdefault(line, date)   # log is newest first, so first wins
    return dates


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


@lru_cache(maxsize=1)
def without_email_obfuscation(html):
    """Keep Cloudflare's hands off code blocks.

    App Platform serves through Cloudflare, whose Email Address Obfuscation
    rewrites anything shaped like an address into a JavaScript-decoded link —
    including `ssh pi@raspberrypi.local` in the setup guide, which is a command
    people are meant to copy. It also injects a script into the page to decode
    it again.

    `<!--email_off-->` is Cloudflare's documented opt-out for a region of a
    page. Applied to `<pre>` blocks only: a real address in prose should still
    be protected from scrapers, but a shell command is not an address.

    Discovered by deploying, not by reading: it does not happen on GitHub Pages,
    so it appeared the moment the apex moved.
    """
    return re.sub(r"(<pre\b.*?</pre>)",
                  r"<!--email_off-->\1<!--email_on-->", html, flags=re.S)


def pages():
    """Every content page: (url_path, source, front_matter, html, last_modified).

    Discovered by walking `content/`, the way the build did, so adding a page
    is still "write a Markdown file" and nothing else. `index.md` is the root;
    everything else gets a clean URL with a trailing slash, which is what the
    canonical tags and the sitemap have always said.
    """
    found = []
    for path in sorted(CONTENT.rglob("*.md")):
        relative = path.relative_to(CONTENT).with_suffix("")
        url = "/" if relative.name == "index" and relative.parent == Path(".") \
            else "/" + str(relative.parent / relative.name if relative.name != "index"
                           else relative.parent).replace("\\", "/") + "/"
        front_matter, html = read_markdown(path)
        html = without_email_obfuscation(html)
        template = front_matter.get("template", "page.html")
        # A page's real content is its Markdown *and* the template rendering it —
        # the home page in particular lives almost entirely in its template.
        modified = last_modified_map()
        dates = [d for d in (modified.get(str(p.relative_to(HERE)))
                             for p in (path, TEMPLATES / template)) if d]
        found.append({
            "url": url,
            "source": path,
            "template": template,
            "front_matter": front_matter,
            "html": html,
            "last_modified": max(dates) if dates else None,
        })
    # A tuple because this is cached: two git subprocesses per page is slow
    # enough to notice in a test suite, and the content cannot change without
    # the process restarting.
    return tuple(found)


def sitemap_xml(found, site_url=SITE_URL):
    """The sitemap, with `noindex` pages rendered but left out of it."""
    from xml.sax.saxutils import escape

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in sorted(found, key=lambda p: p["url"]):
        if page["front_matter"].get("noindex"):
            continue
        lines.append("  <url>")
        lines.append(f'    <loc>{escape(site_url + page["url"])}</loc>')
        if page["last_modified"]:
            lines.append(f'    <lastmod>{page["last_modified"]}</lastmod>')
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def robots_txt(site_url=SITE_URL):
    return f"User-agent: *\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n"
