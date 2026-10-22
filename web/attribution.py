"""Where first-touch attribution is read on a request, and carried to signup.

The cookie wins when it is set: it names whatever first brought this browser
to the site, which can be an earlier visit to the marketing site rather than
this request. The query string is read only as a fallback, for a sign-in page
reached directly by a paid link with nothing to set the cookie yet.
"""

from dinkydash import attribution

SESSION_KEY = "first_touch"


def capture(request, session):
    """Read this request's first-touch signal and remember it for the session.

    Returns what should end up on the family, or `{}` when there is nothing
    to attribute. Once something is remembered it is kept: a sign-up's
    `/login` request and the magic-link click that later creates the family
    are different requests, and the session is what carries it between them.
    """
    remembered = session.get(SESSION_KEY)
    if remembered:
        return remembered
    found = attribution.from_cookie(request.cookies.get(attribution.COOKIE_NAME))
    if not found:
        found = attribution.from_mapping(request.args)
    if found:
        session[SESSION_KEY] = found
    return found
