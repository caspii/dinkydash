"""Sending one transactional email, and nothing else.

    send(to, subject, text) -> None

Magic links are what this exists for; dunning and the support
inbox are later callers of the same function. Named `mail` rather than `email`
because the standard library owns that name.

**SendGrid, on the account KeepTheScore already sends from.** The
shared sender reputation is the whole point: a login link that lands in spam is
a login that fails. `dinkydash.co` is an authenticated sending domain on that
account, so DKIM signs whatever leaves here.

**No SendGrid SDK.** Sending is one `POST` with a JSON body, and `requests` is
already a dependency because `calendars.py` fetches feeds with it. A new
package in an app holding other families' calendars is a supply-chain decision,
and fifteen saved lines do not pay for one.

**Single mode never calls this.** A self-hosted dashboard has no accounts, so it has
no logins to mail and no dunning to send. Nothing here is imported unless cloud
mode asks for it, and `send` refuses rather than guessing if it is reached
without a key.

The shape follows `calendars.fetch_feed`: a typed error the caller decides
about, a transport that tests replace, and a message that carries no secret.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

SEND_URL = "https://api.sendgrid.com/v3/mail/send"
DEFAULT_TIMEOUT = 10

# Who the mail comes from. A subdomain of the authenticated domain would need
# its own DKIM records; the apex is what SendGrid validated.
DEFAULT_FROM = "hello@dinkydash.co"
DEFAULT_FROM_NAME = "DinkyDash"

# **Where a reply goes, which is not the `From` address.** `dinkydash.co` has no
# MX records — it is authenticated for *sending* and nothing receives on it — so
# anybody replying to a sign-in email was writing to a mailbox that does not
# exist, and the bounce went nowhere either. That is a poor thing to discover
# from the person who was trying to tell you their link did not work.
#
# `keepthescore.com` is on Google Workspace and is the same person, which is
# also what the privacy policy gives as the contact address. When DinkyDash gets
# MX records of its own, this moves and the policy moves with it.
DEFAULT_REPLY_TO = "hi@keepthescore.com"


class MailError(Exception):
    """A message did not go out.

    Raised rather than swallowed, and swallowed rather than retried in a loop:
    whether a failed magic link is worth a second attempt is the caller's
    decision, not this module's. One bad send is a failed login, not a failed
    process.
    """


class MailRefused(MailError):
    """The message was never attempted, because it could not be.

    A missing key or an address that is not an address is a configuration fault
    and will fail identically on every retry. `FeedRefused` subclasses
    `FeedError` for the same reason: a caller that only wants to know "did it
    go" catches the parent, and one that wants to know "is it worth trying
    again" checks the subclass.
    """


def send(to, subject, text, html=None, transport=None, api_key=None,
         sender=None, sender_name=None, timeout=DEFAULT_TIMEOUT):
    """Send one message. Returns None, raises `MailError` if it did not go.

    `transport` is the seam the tests use. It takes the same arguments
    `requests.post` does and must behave the same way, which is why the default
    is literally `requests.post` rather than a wrapper around it.
    """
    recipient = _clean_address(to)
    key = _clean_key(api_key if api_key is not None else os.environ.get("SENDGRID_API_KEY"))
    post = transport or requests.post

    body = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": sender or _sender(), "name": sender_name or DEFAULT_FROM_NAME},
        "reply_to": {"email": _reply_to(), "name": DEFAULT_FROM_NAME},
        "subject": subject,
        "content": _content(text, html),
    }

    try:
        response = post(
            SEND_URL,
            json=body,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            timeout=timeout,
        )
    except requests.exceptions.InvalidHeader:
        # `from None`, and it is the whole point of this branch. `requests`
        # puts the offending header *value* in this exception's message —
        # "...in header value: 'Bearer SG.REALKEY\n'" — and the only variable
        # header here is the Authorization one. Chaining it would print the key
        # in every traceback that reaches a log or Sentry, past the sanitised
        # message. `_clean_key` should mean this never fires; this is the belt
        # to its braces, and it stays even if a future header makes it possible
        # again.
        raise MailError(
            "could not send the email: the request headers were rejected"
        ) from None
    except requests.RequestException as exc:
        raise MailError(f"could not send the email: {_why(exc)}") from exc

    status = getattr(response, "status_code", None)
    if status is None or not 200 <= status < 300:
        raise MailError(f"could not send the email: the server said {status}")

    # The address is personal data and the subject can name a person, so this
    # says that a send happened and nothing about who or what. `calendars`
    # logs the label rather than the URL for the same reason.
    logger.info("Sent one email via SendGrid.")


def _content(text, html):
    """SendGrid wants plain text first when both are present, and wants one of them.

    The order is not cosmetic: it decides which part a client shows when it can
    render both, and getting it backwards means the plain-text fallback wins in
    clients that should show the HTML.
    """
    if not (text or "").strip():
        raise MailRefused("an email needs a plain-text body")
    content = [{"type": "text/plain", "value": text}]
    if html:
        content.append({"type": "text/html", "value": html})
    return content


def _clean_address(to):
    """The recipient, or a refusal. No validation beyond what protects the account.

    Bounces and suppressions are shared across six domains on this account, so a
    malformed address is worth catching here rather than discovering as a hard
    bounce against KeepTheScore's reputation. This is not an attempt to validate
    email addresses properly, which is not possible — it rejects what is
    obviously not one, and lets SendGrid judge the rest.

    A newline is the one that matters. Anything reaching a header is a header
    injection, and although this sends JSON rather than SMTP, the rule holds
    wherever the value ends up next.
    """
    address = (to or "").strip()
    if not address:
        raise MailRefused("no email address to send to")
    if any(c in address for c in "\r\n"):
        raise MailRefused("that email address contains a line break")
    if address.count("@") != 1 or address.startswith("@") or address.endswith("@"):
        raise MailRefused("that does not look like an email address")
    return address


def _clean_key(key):
    """The send-only key, checked before it can reach an HTTP header.

    The key in `.env` is scoped to `mail.send` alone — it cannot read the
    account, mint further keys or touch the other five domains on it. It comes
    from the environment: never a literal, never per-family.

    **This exists to keep the key out of tracebacks.** `requests` validates
    header values and quotes the bad one in `InvalidHeader`, so a key carrying
    a stray newline — the usual shape of a copy-paste or an env var set from a
    file — would put itself in an exception message. Catching it here means the
    request is never built, and none of these messages names the value.

    A trailing newline is repaired rather than refused, because it is almost
    always the transport's fault rather than the operator's. Anything else
    unusual is refused: a key with a space in the middle is a wrong key, and
    guessing at what was meant would send mail on a credential nobody chose.
    """
    if key is None or not key.strip():
        raise MailRefused("SENDGRID_API_KEY is not set")
    cleaned = key.strip()
    if not cleaned.isascii() or any(c.isspace() for c in cleaned):
        raise MailRefused(
            "SENDGRID_API_KEY contains whitespace or non-ASCII characters"
        )
    return cleaned


def _sender():
    return os.environ.get("DINKYDASH_MAIL_FROM") or DEFAULT_FROM


def _reply_to():
    """Where a reply lands. Overridable, and never the send-only address."""
    return os.environ.get("DINKYDASH_MAIL_REPLY_TO") or DEFAULT_REPLY_TO


def _why(exc):
    """Why a send failed, in words that carry no secret.

    `requests` puts the full URL in the message of a connection error, and the
    `Authorization` header can surface in a repr. Neither is something to write
    to a log that a support person reads. The endpoint is not secret, but the
    habit is what keeps `calendars._why` honest, and this module handles magic
    links: **a login link in a log is a login in a log.**
    """
    if isinstance(exc, requests.Timeout):
        return "the server did not answer in time"
    if isinstance(exc, requests.ConnectionError):
        return "could not reach the server"
    return type(exc).__name__
