"""The marketing site, served rather than built.

`dinkydash.co` used to be 34 files of committed HTML in `docs/`, written by
`build.py` and served by GitHub Pages. This renders the same pages on request
from the same Markdown and the same Jinja templates (DIN-27).

Three things that were wrong with building are right by construction here:

* **The dates.** `build.py` stamped each page with the git commit date of its
  Markdown — but the build ran *before* the commit it was part of, so every
  page shipped carrying the date of the commit before it. Rendering after the
  commit cannot get that wrong.
* **The double diff.** A copy change showed up twice, once as Markdown and once
  as machine-written HTML.
* **The forgotten rebuild.** Editing copy and not running the build shipped
  nothing at all.

**This is a separate Flask app from the board**, not a blueprint on it, and
deliberately so: the board owns `/` on a Pi, the site owns `/` here, and one
process trying to be both would need a host check in a codebase whose rule is
that mode gates four things and no others. Two entry points, one codebase —
the same arrangement `app.py` and `generate.py` already have.
"""

import os

from flask import Flask, Response, abort, redirect, render_template, request

from . import render

# What `copy_static` used to copy to the site root: the files a browser asks
# for without being told to, plus the self-hosted font.
ROOT_FILES = {
    "favicon.ico": "image/x-icon",
    "favicon.svg": "image/svg+xml",
    "apple-touch-icon.png": "image/png",
    "fonts.css": "text/css",
    "CNAME": "text/plain",
}


def create_site_app(site_url=None):
    app = Flask(
        __name__,
        template_folder=str(render.TEMPLATES),
        static_folder=None,          # the routes below are the static story
    )
    app.config["SITE_URL"] = site_url or os.environ.get("DINKYDASH_SITE_URL",
                                                        render.SITE_URL)

    # Read every page once, at start-up. The site redeploys when its content
    # changes, so re-reading Markdown per request would buy nothing and cost a
    # disk read on every hit.
    pages = {page["url"]: page for page in render.pages()}
    app.config["PAGES"] = pages

    def render_page(page):
        front_matter = page["front_matter"]
        return render_template(
            page["template"],
            content=page["html"],
            canonical_url=app.config["SITE_URL"] + page["url"],
            last_modified=page["last_modified"],
            faq_schema=render.faq_schema(front_matter.get("faq")),
            **front_matter,
        )

    @app.route("/")
    def home():
        return render_page(pages["/"])

    @app.route("/<path:slug>/")
    def page(slug):
        found = pages.get(f"/{slug}/")
        if not found:
            abort(404)
        return render_page(found)

    @app.route("/sitemap.xml")
    def sitemap():
        return Response(
            render.sitemap_xml(pages.values(), app.config["SITE_URL"]),
            mimetype="application/xml")

    @app.route("/robots.txt")
    def robots():
        return Response(render.robots_txt(app.config["SITE_URL"]),
                        mimetype="text/plain")

    @app.route("/images/<path:filename>")
    def image(filename):
        return _send(render.IMAGES, filename)

    @app.route("/fonts/<path:filename>")
    def font(filename):
        return _send(render.STATIC / "fonts", filename)

    @app.route("/<filename>")
    def root_file(filename):
        """The files a browser asks for unprompted, plus the font stylesheet.

        Narrowed to a known list, so it cannot turn the static directory into a
        file browser. It also has to hand back the trailing-slash redirect it
        would otherwise swallow: this rule matches `/about` before Flask can
        offer `/about/`, and a 404 there would break every link written without
        the slash.
        """
        if filename in ROOT_FILES:
            return _send(render.STATIC, filename, ROOT_FILES[filename])
        if f"/{filename}/" in pages:
            return redirect(f"/{filename}/", code=308)
        abort(404)

    @app.route("/healthz")
    def healthz():
        """Up, and which commit. Reads nothing, like the board's."""
        return {"status": "ok", "commit": os.environ.get("GIT_SHA", "unknown")}, 200, {
            "Cache-Control": "no-store", "X-Robots-Tag": "noindex"}

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html",
                               canonical_url=app.config["SITE_URL"]), 404

    @app.before_request
    def canonical_host():
        """Send `www` to the bare domain, the way GitHub Pages did.

        `docs/CNAME` named the apex, so Pages 301'd www to it and every link and
        every ranking signal has pointed there for as long as the site has
        existed. Serving both would be the same pages on two hostnames.
        """
        host = (request.host or "").split(":")[0]
        canonical = _bare_host(app)
        if host == f"www.{canonical}":
            return redirect(app.config["SITE_URL"] + request.full_path.rstrip("?"), 301)

    @app.after_request
    def headers(response):
        # Same promise the board makes: never tell a third party what URL the
        # reader was on.
        response.headers.setdefault("Referrer-Policy", "no-referrer")

        # Every copy of this site that is not the canonical origin asks not to
        # be indexed. App Platform hands out an .ondigitalocean.app hostname
        # whatever else is configured, and a preview or staging name is a
        # second crawlable copy of pages the whole acquisition argument rests
        # on. The canonical tag already points home; this is the belt to its
        # braces, and it costs one header.
        if request.host and request.host not in _canonical_hosts(app):
            response.headers.setdefault("X-Robots-Tag", "noindex")
        return response

    return app


def _bare_host(app):
    from urllib.parse import urlsplit
    return urlsplit(app.config["SITE_URL"]).netloc


def _canonical_hosts(app):
    """The hostnames this site is allowed to serve as itself.

    `www` is deliberately absent: it redirects rather than serving, so it never
    needs to be indexable.
    """
    return {_bare_host(app)}


def _send(directory, filename, mimetype=None):
    from flask import send_from_directory
    try:
        return send_from_directory(str(directory), filename, mimetype=mimetype,
                                   max_age=60 * 60 * 24 * 30)
    except Exception:
        abort(404)


app = create_site_app()
