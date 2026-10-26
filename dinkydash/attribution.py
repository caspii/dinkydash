"""First-touch attribution: the campaign that first brought a browser here.

Pure parsing and sanitising, shared by the marketing site's cookie and the
app's signup pages. Nothing here reads a request or a session -- `web/attribution.py`
is where those live -- so the shape of a value can be tested without Flask.
"""

import json
from urllib.parse import unquote

# What `website/templates/base.html`'s cookie script and the app's query
# string are both allowed to carry. Anything else is dropped.
FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
          "gclid", "gbraid", "wbraid")

# The marketing site's first-touch cookie.
COOKIE_NAME = "dd_ft"

LONGEST_VALUE = 200


def _clean(value):
    if not isinstance(value, str):
        return None
    value = value.strip()[:LONGEST_VALUE]
    return value or None


def from_mapping(mapping):
    """Keep only the known fields from `mapping`, trimmed and length-limited.

    `mapping` is anything with `.get` -- a plain dict, parsed cookie JSON, or
    Werkzeug's immutable query-string dict. Everything else in it is dropped.
    """
    if not mapping:
        return {}
    result = {}
    for field in FIELDS:
        value = _clean(mapping.get(field))
        if value:
            result[field] = value
    return result


def from_cookie(raw):
    """Parse the first-touch cookie the marketing site sets, or `{}` if unusable.

    The browser stores it `encodeURIComponent`-escaped, because a cookie value
    cannot hold `{`, `"` or a space unquoted; `unquote` undoes exactly that
    and is a no-op on anything that was not escaped in the first place.
    """
    if not raw:
        return {}
    try:
        decoded = json.loads(unquote(raw))
    except (TypeError, ValueError):
        return {}
    if not isinstance(decoded, dict):
        return {}
    return from_mapping(decoded)
