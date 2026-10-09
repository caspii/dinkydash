"""Cookieless visit counts on the public sign-in pages, and nowhere else.

Fathom is loaded only where somebody has not signed in yet: the form that
asks for a link, the "check your email" page, and the button at the end of
that link. The dashboard, the settings and the billing pages do not load it.
A self-hosted dashboard has no sign-in pages, and an unset or unusable
`FATHOM_SITE_ID` loads nothing in cloud mode either.

The site id is public. It is the same string the marketing site already
embeds, and it is rendered into the page. What must not be rendered with it
is a credential: the pageview URL is the path alone, so a magic-link token
in the query string is not the URL we send.
"""

import os
import re

# What a new account counts as. One word, no address and no family in it.
SIGNUP = "signup"

# Eight characters today. Long enough for a typo, short enough that a value
# with markup in it cannot be a site id.
_SITE_ID = re.compile(r"[A-Za-z0-9]{1,32}\Z")


def site_id():
    """The public site id, or `""` when counting is off.

    Read when the page is rendered, so setting the variable takes effect
    without rebuilding the app. Anything that is not a site id is off too:
    the value is interpolated into a script tag, and an empty string is the
    safe answer to a bad one.
    """
    raw = os.environ.get("FATHOM_SITE_ID", "").strip()
    if not _SITE_ID.fullmatch(raw):
        return ""
    return raw
