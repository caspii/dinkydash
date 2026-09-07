"""What the fetch layer refuses to do.

`fetch_feed` is pointed at a URL somebody typed. On a Pi that somebody owns the
network, so the worst case is their own business. Hosted, it is our
infrastructure dialling whatever a stranger pasted, and everything worth
reaching is *inside*: the cloud metadata endpoint, a database on loopback, the
platform's own private range.

So the rules are: https only, every hop checked, and a body that cannot grow
without limit. Nothing here touches the network — the resolver and the HTTP
call are both replaced.
"""

import socket
from datetime import date

import pytest
import requests

from dinkydash import calendars
from dinkydash.calendars import (MAX_FEED_BYTES, FeedError, FeedRefused,
                                 fetch_feed, normalise_url, zone)

START, END = date(2026, 9, 7), date(2026, 9, 21)
SECRET = "https://calendar.google.com/calendar/ical/x/private-DEADBEEF/basic.ics"

ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Swimming
DTSTART:20260908T153000Z
DTEND:20260908T163000Z
END:VEVENT
END:VCALENDAR
"""


def resolves_to(monkeypatch, *addresses):
    """Pin what every hostname resolves to."""
    def fake(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses]
    monkeypatch.setattr(calendars.socket, "getaddrinfo", fake)


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None, location=None):
        self.status_code = status
        self.headers = dict(headers or {})
        if location:
            self.headers["Location"] = location
        self._body = body
        self.encoding = "utf-8"
        self.closed = False
        self.reason = "OK" if status == 200 else "Moved"

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308)

    is_permanent_redirect = property(lambda self: self.status_code in (301, 308))

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def close(self):
        self.closed = True


def serves(monkeypatch, *responses):
    """Answer each successive GET with the next response. Records the URLs."""
    asked = []
    queue = list(responses)

    def fake_get(url, **kwargs):
        asked.append(url)
        return queue.pop(0) if queue else FakeResponse(body=ICS.encode())
    monkeypatch.setattr(calendars.requests, "get", fake_get)
    return asked


def never_called(monkeypatch):
    def fake_get(url, **kwargs):
        raise AssertionError(f"a request was made to {url}")
    monkeypatch.setattr(calendars.requests, "get", fake_get)


class TestTheSchemeRule:
    def test_https_is_kept(self):
        assert normalise_url(SECRET) == SECRET

    def test_webcal_becomes_https(self):
        """What Apple hands people when they share a calendar."""
        assert normalise_url("webcal://p1.icloud.com/published/2/abc") == \
            "https://p1.icloud.com/published/2/abc"
        assert normalise_url("webcals://p1.icloud.com/x") == "https://p1.icloud.com/x"

    @pytest.mark.parametrize("url", [
        "http://example.com/cal.ics",     # cleartext: the secret address on the wire
        "file:///etc/passwd",
        "ftp://example.com/cal.ics",
        "gopher://example.com/",
        "",
    ])
    def test_everything_else_is_refused(self, url):
        with pytest.raises(FeedRefused, match="https"):
            normalise_url(url)

    def test_a_url_with_no_host_is_refused(self):
        with pytest.raises(FeedRefused, match="server name"):
            normalise_url("https:///cal.ics")

    def test_a_refusal_never_names_the_url(self, monkeypatch):
        never_called(monkeypatch)
        with pytest.raises(FeedError) as caught:
            fetch_feed("http://host/private-DEADBEEF/x.ics", START, END, zone("UTC"))
        assert "DEADBEEF" not in str(caught.value)


class TestWhereItWillNotGo:
    @pytest.mark.parametrize("address,what", [
        ("127.0.0.1", "loopback"),
        ("169.254.169.254", "the cloud metadata endpoint"),
        ("10.1.2.3", "private"),
        ("192.168.1.10", "private"),
        ("172.16.5.4", "private"),
        ("0.0.0.0", "unspecified"),
        ("224.0.0.1", "multicast"),
    ])
    def test_it_refuses_and_does_not_even_ask(self, monkeypatch, address, what):
        resolves_to(monkeypatch, address)
        never_called(monkeypatch)   # the point: no request is made at all
        with pytest.raises(FeedRefused, match="private network"):
            fetch_feed("https://sneaky.example/cal.ics", START, END, zone("UTC"))

    def test_a_public_address_is_allowed(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        serves(monkeypatch, FakeResponse(body=ICS.encode()))
        events = fetch_feed(SECRET, START, END, zone("UTC"), label="Family")
        assert [e["title"] for e in events] == ["Swimming"]

    def test_every_resolved_address_has_to_pass(self, monkeypatch):
        """One public and one private answer is otherwise a way through."""
        resolves_to(monkeypatch, "142.250.185.174", "127.0.0.1")
        never_called(monkeypatch)
        with pytest.raises(FeedRefused, match="private network"):
            fetch_feed(SECRET, START, END, zone("UTC"))

    def test_it_does_not_say_which_address(self, monkeypatch):
        # Otherwise the error is a way to map the inside of the network.
        resolves_to(monkeypatch, "10.1.2.3")
        never_called(monkeypatch)
        with pytest.raises(FeedRefused) as caught:
            fetch_feed(SECRET, START, END, zone("UTC"))
        assert "10.1.2.3" not in str(caught.value)

    def test_a_name_that_does_not_resolve_is_refused(self, monkeypatch):
        def boom(*args, **kwargs):
            raise socket.gaierror("nope")
        monkeypatch.setattr(calendars.socket, "getaddrinfo", boom)
        never_called(monkeypatch)
        with pytest.raises(FeedRefused, match="does not resolve"):
            fetch_feed(SECRET, START, END, zone("UTC"))


class TestRedirects:
    """A public URL that 302s inward is the whole attack."""

    def test_a_redirect_to_a_private_address_is_caught_at_the_hop(self, monkeypatch):
        seen = {"n": 0}

        def fake(host, port, **kwargs):
            seen["n"] += 1
            addr = "142.250.185.174" if seen["n"] == 1 else "169.254.169.254"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, port))]
        monkeypatch.setattr(calendars.socket, "getaddrinfo", fake)
        serves(monkeypatch, FakeResponse(302, location="https://inside.example/meta"))

        with pytest.raises(FeedRefused, match="private network"):
            fetch_feed(SECRET, START, END, zone("UTC"))

    def test_a_redirect_to_http_is_refused(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        serves(monkeypatch, FakeResponse(302, location="http://example.com/cal.ics"))
        with pytest.raises(FeedRefused, match="https"):
            fetch_feed(SECRET, START, END, zone("UTC"))

    def test_an_ordinary_redirect_is_followed(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        asked = serves(monkeypatch,
                       FakeResponse(301, location="https://elsewhere.example/real.ics"),
                       FakeResponse(body=ICS.encode()))
        events = fetch_feed(SECRET, START, END, zone("UTC"))
        assert [e["title"] for e in events] == ["Swimming"]
        assert asked[1] == "https://elsewhere.example/real.ics"

    def test_a_relative_location_resolves_against_the_url_it_came_from(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        asked = serves(monkeypatch,
                       FakeResponse(302, location="/moved/real.ics"),
                       FakeResponse(body=ICS.encode()))
        fetch_feed("https://host.example/a/b.ics", START, END, zone("UTC"))
        assert asked[1] == "https://host.example/moved/real.ics"

    def test_a_redirect_loop_ends_as_an_error(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        loop = [FakeResponse(302, location="https://host.example/again")
                for _ in range(calendars.MAX_REDIRECTS + 2)]
        serves(monkeypatch, *loop)
        with pytest.raises(FeedError, match="too many redirects"):
            fetch_feed("https://host.example/x", START, END, zone("UTC"))

    def test_a_redirect_with_no_location_is_an_error(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        serves(monkeypatch, FakeResponse(302))
        with pytest.raises(FeedError, match="nowhere to go"):
            fetch_feed(SECRET, START, END, zone("UTC"))


class TestTheSizeCap:
    def test_a_declared_size_over_the_cap_is_refused(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        serves(monkeypatch, FakeResponse(
            headers={"Content-Length": str(MAX_FEED_BYTES + 1)}, body=b"x"))
        with pytest.raises(FeedError, match="too big"):
            fetch_feed(SECRET, START, END, zone("UTC"))

    def test_a_body_over_the_cap_is_refused_even_with_no_header(self, monkeypatch):
        # A server that omits Content-Length, or lies in it, must not be able
        # to hand us an unbounded body.
        resolves_to(monkeypatch, "142.250.185.174")
        serves(monkeypatch, FakeResponse(body=b"x" * (MAX_FEED_BYTES + 1024)))
        with pytest.raises(FeedError, match="too big"):
            fetch_feed(SECRET, START, END, zone("UTC"))

    def test_an_ordinary_calendar_is_well_under_it(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        serves(monkeypatch, FakeResponse(
            headers={"Content-Length": str(len(ICS))}, body=ICS.encode()))
        assert len(fetch_feed(SECRET, START, END, zone("UTC"))) == 1

    def test_the_response_is_closed_even_when_refused(self, monkeypatch):
        resolves_to(monkeypatch, "142.250.185.174")
        response = FakeResponse(body=b"x" * (MAX_FEED_BYTES + 1))
        serves(monkeypatch, response)
        with pytest.raises(FeedError):
            fetch_feed(SECRET, START, END, zone("UTC"))
        assert response.closed, "a refused body must not leave the socket open"


class TestOneBadFeedDoesNotBreakTheRest:
    def test_a_refused_url_is_a_failed_feed_not_a_failed_tick(self, monkeypatch):
        """FeedRefused subclasses FeedError precisely so this keeps working."""
        resolves_to(monkeypatch, "142.250.185.174")
        serves(monkeypatch, FakeResponse(body=ICS.encode()))
        events, statuses = calendars.fetch_events([
            {"label": "Bad", "url": "http://169.254.169.254/", "enabled": True},
            {"label": "Good", "url": SECRET, "enabled": True},
        ], START, zone("UTC"))
        assert [s["ok"] for s in statuses] == [False, True]
        assert [e["title"] for e in events] == ["Swimming"]
        assert "DEADBEEF" not in statuses[0]["detail"]
