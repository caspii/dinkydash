"""What a phone needs to keep a DinkyDash page on its home screen.

Two pages are worth saving and they want different things: the dashboard opens full
screen on a wall panel, the settings UI opens like an app on a phone. So there
are two manifests over one set of icons, each with its own `id` — share an id
and the phone treats them as one app, and whichever was saved second wins.

Both keep `scope` at "/", so a page of the saved app's own opens inside it rather
than throwing the browser open: the settings pages in one, the dashboard in the
other. The one link that leaves on purpose is "View dashboard" on the settings home,
which opens the dashboard in its own tab — inside the standalone settings app the
dashboard is a dead end with no Back button, and `settings/home.html` says so where
the link is.
"""

from flask import jsonify

from .assets import static_url

# Android reads these. iOS ignores them and uses the `apple-touch-icon` link in
# the page head, which is why both are set.
ICONS = [
    ("icon-192.png", "192x192", "any"),
    ("icon-512.png", "512x512", "any"),
    # Drawn full bleed with the mark inside the safe circle, because an adaptive
    # launcher crops whatever it is given.
    ("icon-maskable-512.png", "512x512", "maskable"),
]


def response(**fields):
    """A manifest as a response: the shared keys, plus what the caller sets."""
    manifest = {
        "scope": "/",
        "display": "standalone",
        "lang": "en-GB",
        "icons": [
            {"src": static_url(name), "sizes": sizes,
             "type": "image/png", "purpose": purpose}
            for name, sizes, purpose in ICONS
        ],
    }
    manifest.update(fields)
    out = jsonify(manifest)
    # Chrome accepts application/json, but this is the registered type.
    out.mimetype = "application/manifest+json"
    return out
