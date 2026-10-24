"""First-touch parsing, with no Flask and no database.

`dinkydash/attribution.py` only ever keeps the eight known fields, trimmed and
length-limited, so a cookie or a query string cannot smuggle anything else
into a family's `first_touch` column. `web.attribution.capture` takes its
request and session as plain duck-typed objects, so it is tested the same
way, with no app context.
"""

from types import SimpleNamespace

from dinkydash import attribution
from web import attribution as web_attribution


def _request(cookies=None, args=None):
    return SimpleNamespace(cookies=cookies or {}, args=args or {})


class TestFromMapping:
    def test_keeps_only_the_known_fields(self):
        result = attribution.from_mapping({
            "utm_source": "google", "utm_medium": "cpc", "gclid": "abc123",
            "password": "shh", "<script>": "x",
        })
        assert result == {"utm_source": "google", "utm_medium": "cpc", "gclid": "abc123"}
        assert "password" not in result

    def test_drops_non_string_and_empty_values(self):
        result = attribution.from_mapping({
            "utm_source": "", "utm_medium": None, "gclid": 12345,
        })
        assert result == {}

    def test_trims_a_value_past_the_length_limit(self):
        long_value = "a" * 500
        result = attribution.from_mapping({"gclid": long_value})
        assert result == {"gclid": "a" * attribution.LONGEST_VALUE}

    def test_strips_surrounding_whitespace(self):
        assert attribution.from_mapping({"utm_source": "  google  "}) == {"utm_source": "google"}

    def test_empty_or_missing_mapping_is_empty(self):
        assert attribution.from_mapping({}) == {}
        assert attribution.from_mapping(None) == {}

    def test_every_documented_field_is_kept(self):
        full = {field: field for field in attribution.FIELDS}
        assert attribution.from_mapping(full) == full


class TestFromCookie:
    def test_parses_json_and_sanitises_it_the_same_way(self):
        raw = '{"utm_source": "google", "gclid": "abc123", "evil": "<script>"}'
        assert attribution.from_cookie(raw) == {"utm_source": "google", "gclid": "abc123"}

    def test_unparsable_values_are_empty(self):
        assert attribution.from_cookie("") == {}
        assert attribution.from_cookie(None) == {}
        assert attribution.from_cookie("not json") == {}
        assert attribution.from_cookie("[1, 2, 3]") == {}
        assert attribution.from_cookie('"just a string"') == {}


class TestCapture:
    def test_the_cookie_wins_over_the_query_string(self):
        request = _request(
            cookies={"dd_ft": '{"utm_source": "cookie"}'},
            args={"utm_source": "query"},
        )
        session = {}
        assert web_attribution.capture(request, session) == {"utm_source": "cookie"}
        assert session[web_attribution.SESSION_KEY] == {"utm_source": "cookie"}

    def test_the_query_string_is_a_fallback_when_there_is_no_cookie(self):
        request = _request(args={"gclid": "abc123"})
        session = {}
        assert web_attribution.capture(request, session) == {"gclid": "abc123"}

    def test_nothing_to_find_leaves_the_session_untouched(self):
        request = _request()
        session = {}
        assert web_attribution.capture(request, session) == {}
        assert web_attribution.SESSION_KEY not in session

    def test_a_remembered_value_survives_a_later_request_with_nothing_on_it(self):
        """The `/login` POST and the magic-link click are different requests."""
        session = {}
        web_attribution.capture(_request(args={"utm_source": "first"}), session)
        again = web_attribution.capture(_request(), session)
        assert again == {"utm_source": "first"}

    def test_a_remembered_value_is_not_replaced_by_a_later_request(self):
        session = {}
        web_attribution.capture(_request(args={"utm_source": "first"}), session)
        web_attribution.capture(_request(args={"utm_source": "second"}), session)
        assert session[web_attribution.SESSION_KEY] == {"utm_source": "first"}
