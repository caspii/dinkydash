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
from datetime import date, datetime, time, timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
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
            # family board is the family's own timezone.
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
    hidden appointment never reaches the payload, the board or the prompt. And
    the dict carries no addresses: nobody's guest list is written anywhere.
    """
    return _events(_occurrences(ical_text, start, end), tzinfo, label, shared_with)


def _occurrences(ical_text, start, end):
    """Every event in the window, with recurrences expanded."""
    try:
        cal = Calendar.from_ical(ical_text)
    except Exception as exc:
        # Not `{exc}`: a parser error quotes the line it choked on, which is
        # somebody's appointment.
        raise FeedError(f"could not read the calendar data ({type(exc).__name__})") from exc
    return list(recurring_events_of(cal).between(start, end + timedelta(days=1)))


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


def _check_address(hostname):
    """Refuse a host that resolves anywhere it has no business being.

    The board fetches URLs a person typed. On a Pi that person owns the
    network. Hosted it is our infrastructure dialling whatever a stranger
    pasted, and the interesting targets are all *inside*: the cloud metadata
    endpoint on 169.254.169.254, a database on 127.0.0.1, anything on the
    platform's own private range.

    Every resolved address has to pass, not just the first, because a host with
    one public and one private address is otherwise a way through.

    **This does not close DNS rebinding.** Between this check and the socket,
    a hostile resolver can answer differently. Closing that means connecting to
    the checked address with an explicit Host header, which is a bigger change
    than this and is written down rather than implied.
    """
    try:
        infos = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FeedRefused("that server name does not resolve") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (address.is_private or address.is_loopback or address.is_link_local
                or address.is_reserved or address.is_multicast
                or address.is_unspecified):
            # Deliberately does not say which address. The answer would
            # otherwise be a way to map the inside of the network from outside.
            raise FeedRefused("that link points inside a private network")


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

    for _hop in range(MAX_REDIRECTS + 1):
        parts = urlsplit(target)
        _check_address(parts.hostname)
        try:
            response = requests.get(target, timeout=timeout, stream=True,
                                    allow_redirects=False)
        except Exception as exc:
            raise FeedError(f"could not fetch the calendar: {_why(exc)}") from exc

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location", "")
            response.close()
            if not location:
                raise FeedError("could not fetch the calendar: a redirect with nowhere to go")
            # urljoin covers all three legal shapes of a Location: absolute,
            # root-relative and relative. normalise_url then re-applies the
            # scheme rule, so a 302 to http:// or file:// is refused here too.
            target = normalise_url(urljoin(target, location))
            continue

        try:
            response.raise_for_status()
        except Exception as exc:
            response.close()
            raise FeedError(f"could not fetch the calendar: {_why(exc)}") from exc
        return _read_capped(response)

    raise FeedError("could not fetch the calendar: too many redirects")


def _read_capped(response):
    """The body, refusing anything over MAX_FEED_BYTES.

    Content-Length is checked first because it is free, and then the read is
    budgeted anyway — a server that omits the header, or lies in it, must not
    be able to hand us an unbounded body.
    """
    declared = response.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > MAX_FEED_BYTES:
        response.close()
        raise FeedError("could not fetch the calendar: it is too big to be a calendar")

    chunks, total = [], 0
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            total += len(chunk)
            if total > MAX_FEED_BYTES:
                raise FeedError("could not fetch the calendar: it is too big to be a calendar")
            chunks.append(chunk)
    finally:
        response.close()
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

    One broken feed must not empty the board, so a failing feed is logged and
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


def describe_feed(url, tzinfo, today=None, days_ahead=DEFAULT_DAYS_AHEAD,
                  timeout=DEFAULT_TIMEOUT, shared_with=None):
    """Check a pasted URL and describe what came back.

    Used by the settings UI so pasting a link answers with a real event count
    and the next thing in it, rather than a silent success. With `shared_with`
    set it also counts the events *before* the filter, because a guest list
    that matches nobody looks exactly like an empty calendar from the board,
    and telling the two apart is the whole point of pressing the button.
    """
    today = today or date.today()
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
