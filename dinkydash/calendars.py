"""iCal fetching, parsing and merging.

Several feeds go in (one per parent, plus a school calendar or two) and one
chronologically-ordered agenda comes out. Events keep their real start time all
the way through — the old code formatted them to a string too early and then
sorted those strings, which ordered the day alphabetically by weekday name.

A feed can carry a guest list (`shared_with`): a personal calendar full of work
and private appointments then contributes only the events with the other
parent on them. The filter runs at parse time, so a hidden event never exists
as data anywhere downstream.
"""

import ipaddress
import logging
import re
import socket
from contextlib import closing, contextmanager
from datetime import date, datetime, time, timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from icalendar import Calendar
from recurring_ical_events import of as recurring_events_of

log = logging.getLogger(__name__)

DEFAULT_DAYS_AHEAD = 14
DEFAULT_TIMEOUT = 30

# A calendar feed the size of a fortnight's appointments is tens of kilobytes.
# Ten megabytes is generous for a decade of a busy family, and it is the
# difference between a bad URL being an error and a bad URL filling the disk.
MAX_FEED_BYTES = 10 * 1024 * 1024

# Enough for a provider's own shortener or a http->https hop, few enough that a
# redirect loop ends as an error rather than a hang.
MAX_REDIRECTS = 5


class FeedError(Exception):
    """A feed could not be fetched or parsed.

    Its message is shown on the settings page and written to generate.log, so
    it must never carry the URL or the feed's contents — see `_why`.
    """

    def __init__(self, message, *, status_code=None, invalid_data=False):
        super().__init__(message)
        # Let the UI offer a repair without parsing the diagnostic or exposing
        # the original Requests exception, which can contain the private URL.
        self.status_code = status_code
        self.invalid_data = invalid_data


class FeedRefused(FeedError):
    """The URL was refused before any request was made.

    Its own type because the two mean different things to whoever reads the
    message — `FeedError` is "we asked and it went wrong", this is "we are not
    going to ask" — but a *subclass*, deliberately, so that every existing
    `except FeedError` keeps working. One bad URL in a config must not abort
    the whole tick, and a handler nobody remembered to add is exactly how that
    would happen.
    """


def _why(exc):
    """Why a fetch failed, in words that carry no secret.

    An iCal "secret address" is a password in a URL: whoever holds it reads that
    family's whole calendar, indefinitely, and there is no way to see who has.
    `requests` puts the full URL into the message of both `raise_for_status()`
    and every connection error, so wrapping `{exc}` — which this used to do —
    published it to generate.log and to the settings page.

    The label already says *which* calendar, so the URL adds nothing a person
    needs. The host is left out too: `calendar.google.com` is harmless, but a
    self-hosted `calendar.the-smiths.example` is not, and there is no way to
    tell them apart.
    """
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None):
        reason = str(getattr(response, "reason", "") or "").strip()
        return f"the server said {response.status_code}{f' {reason}' if reason else ''}"
    if isinstance(exc, requests.Timeout):
        return "the server did not answer in time"
    if isinstance(exc, requests.TooManyRedirects):
        return "too many redirects"
    if isinstance(exc, requests.ConnectionError):
        return "could not reach the server"
    return type(exc).__name__


def _localise(value, tzinfo):
    """Return an aware datetime in `tzinfo` for an iCal DTSTART value."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # A floating time means "whatever the local clock says", which for a
            # family dashboard is the family's own timezone.
            return value.replace(tzinfo=tzinfo)
        return value.astimezone(tzinfo)
    # A bare date is an all-day event; anchor it to midnight for ordering.
    return datetime.combine(value, time.min, tzinfo=tzinfo)


def addresses(value):
    """A `shared_with` value as a list of lowercase email addresses.

    Takes whatever config.yaml or a form might hold — a list, one string with
    commas or spaces between the addresses, or nothing at all — and gives back
    one shape, so the comparison in `_people_on` is exact. `mailto:` is
    stripped because that is how an iCal file spells an address.
    """
    if not value:
        return []
    if isinstance(value, str):
        value = re.split(r"[,;\s]+", value)
    found = []
    for item in value:
        address = str(item or "").strip().lower()
        if address.startswith("mailto:"):
            address = address[len("mailto:"):]
        if address and address not in found:
            found.append(address)
    return found


def _people_on(component):
    """Everyone on an event: the guests, and whoever organised it.

    Both, because "shared with Jessica" runs in either direction. An event Sam
    made and invited her to lists her as an ATTENDEE; one she made and invited
    Sam to lists her as its ORGANIZER — and a Google feed does not always list
    the organiser as a guest of their own event. The filter this replaced
    looked at ATTENDEE alone, and so missed everything she had arranged.
    """
    people = set()
    for key in ("ATTENDEE", "ORGANIZER"):
        value = component.get(key)
        if value is None:
            continue
        for entry in value if isinstance(value, list) else [value]:
            people.update(addresses([str(entry)]))
    return people


def parse_feed(ical_text, start, end, tzinfo, label=None, shared_with=None):
    """Parse iCal text into event dicts between `start` and `end` (dates).

    `shared_with` is a list of email addresses. Given one, only the events with
    one of those people on them — as a guest or as the organiser — come out.
    The rest of the calendar is dropped here, before an event dict exists, so a
    hidden appointment never reaches the payload, the dashboard or the prompt. And
    the dict carries no addresses: nobody's guest list is written anywhere.
    """
    return _events(_occurrences(ical_text, start, end), tzinfo, label, shared_with)


def _occurrences(ical_text, start, end):
    """Every event in the window, with recurrences expanded."""
    try:
        cal = Calendar.from_ical(_trim(ical_text, start, end))
    except Exception as exc:
        # Not `{exc}`: a parser error quotes the line it choked on, which is
        # somebody's appointment.
        raise FeedError(f"could not read the calendar data ({type(exc).__name__})",
                        invalid_data=True) from exc
    return list(recurring_events_of(cal).between(start, end + timedelta(days=1)))


# A personal Google calendar is a decade of appointments in one file — 8 MB and
# 14,000 events is an ordinary one — and `icalendar` builds an object for every
# property of every one of them. Measured on such a feed: ~200 MB to parse and
# ~250 MB kept by the process afterwards, because Python does not hand arenas
# back. Two gunicorn workers each holding that is more than a 512 MB container,
# and the container's log shows nothing but the exit. The dashboard only ever
# wants a fortnight, so `_trim` drops, as text and before the parser sees them,
# the events that cannot fall in the window.
#
# Whatever the parser needs to get the window right is kept regardless of its
# date: recurring events (their EXDATEs ride on them), extra dates, the
# exceptions that move one occurrence, VTIMEZONE blocks, and any event whose
# dates this cannot read. Over-keeping is always safe — the parsed result is
# windowed again by `recurring_ical_events` — so every doubt resolves to keep.
_TRIM_MARGIN = timedelta(days=2)   # a timezone moves a date by a day at most; be generous
_RECURRENCE_LINE = re.compile(r"^(RRULE|RDATE|RECURRENCE-ID)[;:]", re.IGNORECASE)
_DATE_LINE = re.compile(r"^(DTSTART|DTEND)(?:;[^:]*)?:(\d{4})(\d{2})(\d{2})", re.IGNORECASE)
_DURATION_LINE = re.compile(r"^DURATION(?:;[^:]*)?:-?P(?:(\d+)W)?(?:(\d+)D)?", re.IGNORECASE)


def _trim(ical_text, start, end):
    """The feed as text, minus every VEVENT that cannot touch [start, end]."""
    lo, hi = start - _TRIM_MARGIN, end + _TRIM_MARGIN
    kept, block = [], None
    for line in ical_text.splitlines(keepends=True):
        if block is None:
            if line.rstrip("\r\n").upper() == "BEGIN:VEVENT":
                block = [line]
            else:
                kept.append(line)
            continue
        block.append(line)
        if line.rstrip("\r\n").upper() == "END:VEVENT":
            if _may_touch(block, lo, hi):
                kept.extend(block)
            block = None
    if block is not None:
        kept.extend(block)   # unterminated: the parser's complaint to make
    return "".join(kept)


def _may_touch(block, lo, hi):
    """Whether an event, as its raw lines, could have an occurrence in [lo, hi].

    Reads DTSTART, DTEND and DURATION only, and only their date digits. A line
    it cannot read — a folded value, a parameter with a colon in it — means
    keep: the parser decides, exactly as it did before the trim existed.
    """
    first = last = None
    duration_days = 0
    for line in block:
        if _RECURRENCE_LINE.match(line):
            return True
        found = _DATE_LINE.match(line)
        if found:
            try:
                day = date(int(found[2]), int(found[3]), int(found[4]))
            except ValueError:
                return True
            if found[1].upper() == "DTSTART":
                first = day
            else:
                last = day
            continue
        found = _DURATION_LINE.match(line)
        if found:
            duration_days = int(found[1] or 0) * 7 + int(found[2] or 0)
    if first is None:
        return True
    if last is None:
        last = first + timedelta(days=duration_days + 1)
    return first <= hi and max(first, last) >= lo


def _events(occurrences, tzinfo, label, shared_with):
    wanted = set(addresses(shared_with))
    events = []
    for component in occurrences:
        if wanted and not wanted & _people_on(component):
            continue
        dtstart = component.get("DTSTART")
        if dtstart is None:
            continue
        raw = dtstart.dt
        all_day = not isinstance(raw, datetime)
        starts_at = _localise(raw, tzinfo)

        events.append({
            "title": str(component.get("SUMMARY", "Untitled")).strip() or "Untitled",
            "start": starts_at.isoformat(),
            "date": starts_at.date().isoformat(),
            "time": None if all_day else starts_at.strftime("%H:%M"),
            "all_day": all_day,
            "location": str(component.get("LOCATION", "")).strip() or None,
            "calendar": label,
        })
    return events


def normalise_url(url):
    """The URL we will actually fetch, or a refusal.

    Two jobs. `webcal://` is what Apple hands people when they share a
    calendar, and it is an ordinary HTTPS URL wearing a different scheme, so it
    is translated rather than rejected — the alternative is a support question
    from everybody with an iPhone.

    Then: **https only**. Plain http sends the secret address in cleartext to
    every hop, so an http feed was never safe, and Google, iCloud and Outlook
    are all https. This is a real change for anyone with an internal http feed,
    and it applies on a Pi too — the fetch layer sits below the seam and does
    not know which mode it is in.
    """
    parts = urlsplit((url or "").strip())
    if parts.scheme in ("webcal", "webcals"):
        parts = parts._replace(scheme="https")
    if parts.scheme != "https":
        raise FeedRefused(
            f"the link has to start with https:// (this one starts with "
            f"{parts.scheme or 'nothing'}://)")
    if not parts.hostname:
        raise FeedRefused("the link has no server name in it")
    return urlunsplit(parts)


def _check_address(hostname, port=443):
    """Resolve once and return only checked public addresses, in resolver order.

    Every answer must pass before any connection is attempted. The transport
    connects to these numeric addresses, so later DNS answers cannot redirect it.
    """
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FeedRefused("that server name does not resolve") from exc

    checked = []
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_reserved or address.is_multicast:
            # Deliberately does not say which address. The answer would
            # otherwise be a way to map the inside of the network from outside.
            raise FeedRefused("that link points inside a private network")
        if str(address) not in checked:
            checked.append(str(address))
    if not checked:
        raise FeedRefused("that server name does not resolve")
    return checked


class _PinnedHTTPSAdapter(HTTPAdapter):
    """Connect to a checked IP; authenticate and address the original hostname."""

    def __init__(self, address):
        self.address = address
        super().__init__()

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        host, tls = super().build_connection_pool_key_attributes(request, verify, cert)
        tls.update(server_hostname=host['host'], assert_hostname=host['host'])
        host['host'] = self.address
        request.headers['Host'] = urlsplit(request.url).netloc.rsplit('@', 1)[-1]
        return host, tls


@contextmanager
def _open_public(url, timeout):
    # Prepare first so resolution, TLS and Host agree on IDNA/escaped hostnames.
    request = requests.Request('GET', url, headers=requests.utils.default_headers()).prepare()
    parts = urlsplit(request.url)
    addresses = _check_address(parts.hostname, parts.port or 443)
    for index, address in enumerate(addresses):
        with closing(_PinnedHTTPSAdapter(address)) as adapter:
            try:
                # Send directly: environment proxies could resolve the hostname
                # elsewhere, and Session would read a redirect body to build its
                # automatic next request even with allow_redirects=False.
                response = adapter.send(request, timeout=timeout, stream=True, verify=True)
            except requests.ConnectionError:
                if index == len(addresses) - 1:
                    raise
                continue  # Preserve IPv6/IPv4 fallback using only the checked answers.
            with closing(response):
                yield response
            return


def fetch_feed(url, start, end, tzinfo, label=None, timeout=DEFAULT_TIMEOUT,
               shared_with=None):
    """Fetch one iCal URL and return its events — `fetch_text`, then `parse_feed`.

    Raises FeedRefused if the URL is one we will not ask for, and FeedError if
    asking went wrong.
    """
    return parse_feed(fetch_text(url, timeout=timeout), start, end, tzinfo,
                      label=label, shared_with=shared_with)


def fetch_text(url, timeout=DEFAULT_TIMEOUT):
    """Fetch one iCal URL and return its body, unparsed.

    Raises FeedRefused if the URL is one we will not ask for, and FeedError if
    asking went wrong. Redirects are followed by hand rather than by requests,
    because a public URL that 302s to 169.254.169.254 is the whole attack and
    `allow_redirects=True` would walk straight into it.
    """
    target = normalise_url(url)

    try:
        for _hop in range(MAX_REDIRECTS + 1):
            with _open_public(target, timeout) as response:
                if response.is_redirect or response.is_permanent_redirect:
                    location = response.headers.get("Location", "")
                    if not location:
                        raise FeedError("could not fetch the calendar: a redirect with nowhere to go")
                    target = normalise_url(urljoin(target, location))
                    continue
                response.raise_for_status()
                return _read_capped(response)
    except FeedError:
        raise
    except Exception as exc:
        response = getattr(exc, "response", None)
        raise FeedError(f"could not fetch the calendar: {_why(exc)}",
                        status_code=getattr(response, "status_code", None)) from exc

    raise FeedError("could not fetch the calendar: too many redirects")


def _read_capped(response):
    """The body, refusing anything over MAX_FEED_BYTES.

    Content-Length is checked first because it is free, and then the read is
    budgeted anyway — a server that omits the header, or lies in it, must not
    be able to hand us an unbounded body.
    """
    declared = response.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > MAX_FEED_BYTES:
        raise FeedError("could not fetch the calendar: it is too big to be a calendar")

    chunks, total = [], 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        total += len(chunk)
        if total > MAX_FEED_BYTES:
            raise FeedError("could not fetch the calendar: it is too big to be a calendar")
        chunks.append(chunk)
    return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")


def sort_key(event):
    """Chronological, with all-day events leading their day."""
    return (event["date"], 0 if event["all_day"] else 1, event["start"])


def feed_label(entry):
    """The label a calendar entry's events are filed under.

    One place for the fallback, because the label is the key that everything
    downstream uses — `_with_last_known` keeps events by it, and the settings
    UI forgets them by it — and the two have to agree about a nameless feed.
    """
    return entry.get("label") or "Calendar"


def fetch_events(calendars, today, tzinfo, days_ahead=DEFAULT_DAYS_AHEAD,
                 timeout=DEFAULT_TIMEOUT):
    """Fetch every enabled feed and merge into one ordered agenda.

    One broken feed must not empty the dashboard, so a failing feed is logged and
    skipped. The second return value reports per-feed status so the settings
    page can show which one needs attention.
    """
    end = today + timedelta(days=days_ahead)
    merged = []
    statuses = []

    for entry in calendars or []:
        label = feed_label(entry)
        if not entry.get("enabled", True):
            statuses.append({"label": label, "ok": None, "detail": "paused", "count": 0})
            continue
        url = entry.get("url", "")
        if not url:
            statuses.append({"label": label, "ok": False, "detail": "no URL set", "count": 0})
            continue
        wanted = addresses(entry.get("shared_with"))
        try:
            events = fetch_feed(url, today, end, tzinfo, label=label, timeout=timeout,
                                shared_with=wanted)
        except FeedError as exc:
            log.warning("Calendar %r failed: %s", label, exc)
            statuses.append({"label": label, "ok": False, "detail": str(exc), "count": 0})
            continue
        merged.extend(events)
        statuses.append({"label": label, "ok": True, "detail": "", "count": len(events)})
        # How many addresses, not which: they are people, and this is a log.
        note = f" (only those shared with {len(wanted)} address(es))" if wanted else ""
        log.info("Calendar %r: %d events%s", label, len(events), note)

    merged.sort(key=sort_key)
    return merged, statuses


def events_on(events, day):
    """The subset of `events` that fall on `day`, in order."""
    wanted = day.isoformat()
    return [e for e in events if e.get("date") == wanted]


def describe_feed(url, tzinfo, today, days_ahead=DEFAULT_DAYS_AHEAD,
                  timeout=DEFAULT_TIMEOUT, shared_with=None):
    """Check a pasted URL and describe what came back.

    The caller supplies today's date in the family's timezone.
    Used by the settings UI so pasting a link answers with a real event count
    and the next thing in it, rather than a silent success. With `shared_with`
    set it also counts the events *before* the filter, because a guest list
    that matches nobody looks exactly like an empty calendar from the dashboard,
    and telling the two apart is the whole point of pressing the button.
    """
    end = today + timedelta(days=days_ahead)
    occurrences = _occurrences(fetch_text(url, timeout=timeout), today, end)
    wanted = addresses(shared_with)
    everything = _events(occurrences, tzinfo, None, None)
    events = _events(occurrences, tzinfo, None, wanted) if wanted else everything
    events.sort(key=sort_key)
    upcoming = [e for e in events if e["date"] >= today.isoformat()]
    return {
        "count": len(events),
        "total": len(everything),
        "shared_with": wanted,
        "next": upcoming[0] if upcoming else None,
        "days_ahead": days_ahead,
    }


def zone(name):
    """ZoneInfo for a configured timezone name, falling back to UTC."""
    try:
        return ZoneInfo(name)
    except Exception:
        log.warning("Unknown timezone %r, falling back to UTC", name)
        return ZoneInfo("UTC")
