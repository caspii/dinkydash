"""Check every live public page, and say nothing unless one fails.

    python -m website.check_live

Reads dinkydash.co's sitemap, follows every internal link on every page it
finds, and fetches the hosted app's public pages. Each page must answer 200 and
pass `website/content_checks.py`, the same rules `tests/test_site.py` holds a
merge to. The tests check the pages as written; this checks them as served, so
it catches what a merge cannot: a deploy that did not land, a page the server
cannot render, or a link to a page somebody removed.

Prints one line per failure and exits 1, or prints nothing and exits 0, so a
scheduled run is silent until it has something to say
(`.github/workflows/live-check.yml`).

Standard library only, so it runs on a bare Python with nothing installed.
"""

import argparse
from html.parser import HTMLParser
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.request import Request, urlopen

from website import content_checks

SITE = "https://dinkydash.co"
APP = "https://app.dinkydash.co"
# What a visitor can read on the app without signing in.
APP_PUBLIC = ("/login",)
# Files, not pages: fetched for their status, never read for copy.
NOT_A_PAGE = re.compile(r"\.(?:xml|txt|ico|svg|png|jpe?g|webp|gif|css|js|woff2?|webmanifest)$")
# App Platform serves through Cloudflare, which rewrites an email address into
# `[email protected]` and a link to /cdn-cgi/ that its script decodes in the
# browser. A visitor sees the address, so neither half is ours to report.
CLOUDFLARE_EMAIL = re.compile(r'<a\b[^>]*class="__cf_email__"[^>]*>.*?</a>', re.S)
CLOUDFLARE_PATH = "/cdn-cgi/"
USER_AGENT = "dinkydash-live-check (+https://github.com/caspii/dinkydash)"
TIMEOUT = 30


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def fetch(url):
    """(status, body). Redirects are followed, so a link to `/page` that lands
    on `/page/` passes; a network failure is status 0."""
    try:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except HTTPError as error:
        return error.code, ""
    except (URLError, TimeoutError, OSError) as error:
        return 0, str(getattr(error, "reason", error))


def sitemap_urls(site):
    status, body = fetch(f"{site}/sitemap.xml")
    if status != 200:
        return [], [f"{site}/sitemap.xml: status {status}"]
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body), []


def internal_links(page_url, body, site):
    parser = _Links()
    parser.feed(body)
    host = urlsplit(site).netloc
    for href in parser.links:
        url = urldefrag(urljoin(page_url, href)).url
        parts = urlsplit(url)
        if parts.netloc == host and parts.scheme in ("http", "https") \
                and not parts.path.startswith(CLOUDFLARE_PATH):
            yield url


def check(site=SITE, app=APP):
    """Every failure on the live site, as one line each; empty when all pass."""
    queue, failures = sitemap_urls(site)
    queue += [app + path for path in APP_PUBLIC]
    seen = set()
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        status, body = fetch(url)
        if status != 200:
            failures.append(f"{url}: status {status}" + (f" ({body})" if status == 0 else ""))
            continue
        if NOT_A_PAGE.search(urlsplit(url).path):
            continue
        failures += [f"{url}: {problem}"
                     for problem in content_checks.problems(CLOUDFLARE_EMAIL.sub(" ", body))]
        if url.startswith(site):
            queue += [link for link in internal_links(url, body, site) if link not in seen]
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--app", default=APP)
    args = parser.parse_args(argv)
    failures = check(args.site.rstrip("/"), args.app.rstrip("/"))
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
