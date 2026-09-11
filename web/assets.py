"""Static files: a version in every URL, and a year in the browser's cache.

Flask serves a static file with `Cache-Control: no-cache`: keep a copy, but
ask before using it. So every page of the settings UI paid for the stylesheet
and then the font again, one round trip after the other, after the page
itself, before it could draw a word in the right face. From a desk near
Frankfurt each of those is fifty milliseconds; on a phone over mobile data it
is a few hundred, and that was the whole of what made a tap feel like a
reload. It was a reload.

Two halves, and they only work together:

* `static_url(filename)` is `url_for('static', ...)` with a `v=` that is a
  prefix of the file's SHA-256. Every template goes through it, so the URL
  changes exactly when the file does, and never otherwise.
* A request carrying the current `v=` is answered with a year of
  `Cache-Control` and `immutable`, so the browser never asks again. A bare
  `/static/...` URL, or one with the version from before a deploy, keeps
  Flask's `no-cache`, so a hand-typed URL and a page left open across a
  deploy both still show the current file.

The version is the content rather than the commit, because a font that has
not changed should not be downloaded again after a deploy — and because a Pi
has no `GIT_SHA`. Hashes are cached per process and re-read when the file's
mtime or size moves, which is what happens to a file being edited under the
reloader.

The third half is in `web/session.py`: a static response must carry neither
`Set-Cookie` nor `Vary: Cookie`, or the year is a year of never matching.

This reads files under `web/static/` — the app's own, shipped with the code —
and none of a family's, so it sits in neither mode's storage seam.
"""

import hashlib
import os
from pathlib import Path

from flask import current_app, request, url_for
from werkzeug.security import safe_join

# What a versioned static file is told. A year is the longest lifetime RFC 9111
# asks a cache to honour; `immutable` stops a browser re-checking it on reload.
A_YEAR = 60 * 60 * 24 * 365
CACHED_FOR_A_YEAR = f"public, max-age={A_YEAR}, immutable"

# How much of the hash rides on the URL: 48 bits, which tells one revision of a
# font from every other and is still short enough to read in a log line.
VERSION_LENGTH = 12

_versions = {}  # absolute path -> (mtime_ns, size, version)

# What `board_version()` hashes: the templates that draw the dashboard, and the
# fonts its head names. Nothing a family controls is in it, so every family on
# one deploy shares one version.
BOARD_TEMPLATES = ("board.html", "_fonts.html")
BOARD_STATIC = ("fonts/nunito-latin.woff2", "fonts/nunito-latin-ext.woff2")


def configure(app):
    """`static_url()` for the templates, and the cache header for what it emits."""
    app.jinja_env.globals["static_url"] = static_url
    app.jinja_env.globals["board_version"] = board_version
    app.after_request(_cache_versioned)


def static_url(filename):
    """The URL of a file in `web/static/`, with its content version on it."""
    version = version_of(filename)
    if version is None:
        # No such file. The bare URL 404s the way it always did, in the open.
        return url_for("static", filename=filename)
    return url_for("static", filename=filename, v=version)


def version_of(filename):
    """The current version of a static file, or None if there is no such file."""
    path = safe_join(current_app.static_folder, filename)
    return _version_at(path) if path else None


def board_version():
    """The version of the dashboard page, as opposed to any one file in it.

    The dashboard refreshes itself by fetching a copy and swapping the <body>
    in; the <head> — the CSS, the fonts, the script doing the swapping — stays
    as it was when the page loaded, which on a wall panel is months ago. A
    deploy that changes any of that would never reach the panel, and could
    hand old styles new markup. So the body carries this, the script compares
    each copy's against its own, and a difference is the one thing that earns
    a real reload (`board.html`). Content rather than commit, for the reasons
    `static_url` gives: a Pi has no `GIT_SHA`, and a deploy that changes none
    of these files should not reload a wall.
    """
    folder = Path(current_app.root_path) / current_app.template_folder
    parts = [_version_at(str(folder / name)) or "" for name in BOARD_TEMPLATES]
    parts += [version_of(name) or "" for name in BOARD_STATIC]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:VERSION_LENGTH]


def _version_at(path):
    """The content version of the file at that absolute path, or None without one."""
    if not os.path.isfile(path):
        return None
    stat = os.stat(path)
    known = _versions.get(path)
    if known and known[:2] == (stat.st_mtime_ns, stat.st_size):
        return known[2]
    version = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:VERSION_LENGTH]
    _versions[path] = (stat.st_mtime_ns, stat.st_size, version)
    return version


def _cache_versioned(response):
    """A year for a file asked for by its current version; Flask's default otherwise."""
    if request.endpoint != "static" or response.status_code not in (200, 304):
        return response
    asked = request.args.get("v")
    if asked and asked == version_of((request.view_args or {}).get("filename", "")):
        response.headers["Cache-Control"] = CACHED_FOR_A_YEAR
    return response
