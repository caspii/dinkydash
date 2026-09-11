"""The operator's page at /admin: who may open it, and what it shows (DIN-37).

* **single mode has no such page.** One family, nothing to count, and no
  session to check — a 404 with no database at all;
* **cloud mode puts it behind the login, then behind a list.** Signed out is a
  redirect to `/login` like every other page a person signs into; signed in
  and not on `DINKYDASH_ADMIN_EMAILS` is a 404, never a 403;
* **an empty list is nobody**, including the person who would obviously be
  on it. A new deployment is closed until somebody opens it;
* **the page is counts, and a bounded roster.** The counts read no family
  row at all. The roster reads the address and the platform's bookkeeping on
  the newest families and never the config — no name, no calendar, no child's
  date of birth — and no family id is rendered or taken from anywhere.

The chart's arithmetic is tested with no database. The rest skips without
`DINKYDASH_TEST_DATABASE_URL`.
"""

import re
from datetime import date, timedelta

import pytest

from dinkydash import growth
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app
from web.routes import admin

ADDRESS = "owner@example.com"


def test_single_mode_has_no_admin_page(tmp_path, monkeypatch):
    monkeypatch.delenv("DINKYDASH_MODE", raising=False)
    monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", ADDRESS)
    (tmp_path / "config.yaml").write_text('family_name: "The Wilsons"\n')
    client = client_for(create_app(FileStore(tmp_path / "config.yaml")))
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/").status_code == 404


# -- the drawing, with no database ------------------------------------------

class TestTheChart:
    @pytest.mark.parametrize("highest,expected", [
        (0, (1, 1)), (1, (1, 1)), (4, (4, 1)), (5, (5, 1)), (6, (6, 2)), (7, (8, 2)),
        (11, (15, 5)), (23, (25, 5)), (26, (30, 10)), (51, (60, 20)), (999, (1000, 200)),
    ])
    def test_the_axis_ends_on_a_clean_number_with_at_most_five_lines(self, highest, expected):
        ceiling, step = admin.scale(highest)
        assert (ceiling, step) == expected
        assert ceiling // step <= admin.MOST_GRIDLINES

    def weeks(self, n, values=()):
        values = dict(values)
        return [growth.Week(date(2026, 1, 5) + timedelta(weeks=i), *values.get(i, (0, 0)))
                for i in range(n)]

    def test_one_column_pair_per_week_and_nothing_drawn_for_a_zero(self):
        drawn = admin.chart(self.weeks(3, {1: (2, 1)}))
        assert len(drawn["columns"]) == 3
        assert [bar["path"] for bar in drawn["columns"][0]["bars"]] == ["", ""]
        assert all(bar["path"].startswith("M") for bar in drawn["columns"][1]["bars"])

    def test_columns_stay_thin_and_two_always_fit_in_their_week(self):
        for n in (1, 4, 12, 26, admin.MOST_WEEKS):
            drawn = admin.chart(self.weeks(n, {0: (3, 1)}))
            assert drawn["thickness"] <= admin.THICKEST
            slot = drawn["columns"][0]["slot_w"]
            assert 2 * drawn["thickness"] + admin.GAP <= slot + 0.01, n

    def test_the_tallest_column_reaches_no_higher_than_the_top_gridline(self):
        drawn = admin.chart(self.weeks(2, {1: (7, 3)}))
        top = min(line["y"] for line in drawn["gridlines"])
        tallest = min(bar["y"] for column in drawn["columns"] for bar in column["bars"])
        assert tallest >= top
        assert drawn["gridlines"][0]["y"] == drawn["baseline"]

    def test_only_the_latest_week_is_marked_for_direct_labels(self):
        drawn = admin.chart(self.weeks(5, {0: (4, 2), 4: (1, 0)}))
        assert [column["last"] for column in drawn["columns"]] == [False] * 4 + [True]

    def test_week_labels_thin_out_but_the_latest_week_always_has_one(self):
        for n in (1, 12, 26, admin.MOST_WEEKS):
            drawn = admin.chart(self.weeks(n))
            labelled = [column for column in drawn["columns"] if column["label"]]
            assert 1 <= len(labelled) <= admin.MOST_WEEK_LABELS + 1, n
            assert drawn["columns"][-1]["label"], n

    def test_a_column_is_rounded_on_top_and_square_at_the_foot(self):
        path = admin.column_path(10, 100, 20, 50)
        assert path.startswith("M10.00,150.00 V104.00 Q10.00,100.00 14.00,100.00")
        assert path.endswith("V150.00 Z")
        assert admin.column_path(10, 100, 20, 0) == ""

    @pytest.mark.parametrize("raw,weeks", [
        (None, 12), ("", 12), ("abc", 12), ("12", 12), ("26", 26),
        ("0", 1), ("-4", 1), ("52", 52), ("9999", 52), ("3.5", 12),
    ])
    def test_the_span_is_bounded(self, raw, weeks):
        assert admin.span(raw) == weeks


# -- the words on the roster, with no database -------------------------------

def an_account(**over):
    from datetime import datetime, timezone
    fields = dict(email="parent@example.com",
                  created_at=datetime(2026, 9, 1, 8, tzinfo=timezone.utc),
                  activated_at=None, status="trialing",
                  trial_ends_at=datetime(2026, 9, 15, 8, tzinfo=timezone.utc),
                  lapsed_at=None, last_login_at=None)
    fields.update(over)
    return growth.Account(**fields)


class TestDescribingAnAccount:
    TODAY = date(2026, 9, 10)

    def test_a_fresh_trial(self):
        shown = admin.describe(an_account(), self.TODAY)
        assert shown["status"] == "Trial to 15 Sep 2026"
        assert shown["tone"] == "warm"
        assert shown["detail"] == "Signed up 1 Sep 2026 · not activated yet · never signed in"

    def test_an_activated_family_that_signs_in(self):
        from datetime import datetime, timezone
        shown = admin.describe(an_account(
            activated_at=datetime(2026, 9, 2, 9, tzinfo=timezone.utc),
            last_login_at=datetime(2026, 9, 9, 21, tzinfo=timezone.utc)), self.TODAY)
        assert shown["detail"] == ("Signed up 1 Sep 2026 · activated 2 Sep 2026 · "
                                   "last sign-in 9 Sep 2026")

    def test_a_trial_past_its_deadline_reads_as_ended_before_the_sweep(self):
        from datetime import datetime, timezone
        shown = admin.describe(an_account(
            trial_ends_at=datetime(2026, 9, 9, 8, tzinfo=timezone.utc)), self.TODAY)
        assert shown["status"] == "Trial ended 9 Sep 2026"
        assert shown["tone"] == "muted"

    def test_the_other_statuses(self):
        from datetime import datetime, timezone
        assert admin.describe(an_account(status="active"), self.TODAY)["status"] == "Active"
        assert admin.describe(an_account(status="active"), self.TODAY)["tone"] == "good"
        assert admin.describe(an_account(status="past_due"), self.TODAY)["status"] == "Past due"
        assert admin.describe(an_account(status="canceled"), self.TODAY)["status"] == "Cancelled"
        lapsed = admin.describe(an_account(
            status="lapsed", lapsed_at=datetime(2026, 9, 3, 8, tzinfo=timezone.utc)), self.TODAY)
        assert lapsed["status"] == "Lapsed 3 Sep 2026"
        assert lapsed["tone"] == "muted"

    def test_dates_are_utc_days(self):
        from datetime import datetime, timezone, timedelta
        # 23:30 in UTC-2 is 01:30 the next day in UTC; the page writes UTC.
        late = datetime(2026, 9, 1, 23, 30, tzinfo=timezone(timedelta(hours=-2)))
        assert admin.describe(an_account(created_at=late), self.TODAY)["detail"].startswith(
            "Signed up 2 Sep 2026")


# -- who gets in, in Postgres ------------------------------------------------

@pytest.fixture
def user(pg_pool, pg_family):
    with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                    (pg_family, ADDRESS))
        return pg_family, cur.fetchone()[0]


@pytest.fixture
def cloud(pg_pool, monkeypatch):
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    monkeypatch.delenv("DINKYDASH_ADMIN_EMAILS", raising=False)
    return create_app(pool=pg_pool)


def signed_in(app, user):
    family_id, user_id = user
    client = client_for(app)
    with client.session_transaction() as stored:
        stored["user_id"] = user_id
        stored["family_id"] = str(family_id)
    return client


class TestWhoMayLook:
    def test_signed_out_is_sent_to_the_login_like_any_other_page(self, cloud, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", ADDRESS)
        response = client_for(cloud).get("/admin")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_with_no_list_nobody_is_an_admin(self, cloud, user):
        assert signed_in(cloud, user).get("/admin").status_code == 404

    def test_with_an_empty_list_nobody_is_an_admin(self, cloud, user, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", " , ,")
        assert signed_in(cloud, user).get("/admin").status_code == 404

    def test_somebody_else_on_the_list_is_a_404_and_never_a_403(self, cloud, user, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", "somebody@example.com")
        assert signed_in(cloud, user).get("/admin").status_code == 404

    def test_the_address_on_the_list_gets_in_however_it_is_written(self, cloud, user, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", "other@example.com,  Owner@Example.COM ")
        response = signed_in(cloud, user).get("/admin")
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert "Growth" in response.get_data(as_text=True)

    def test_a_trailing_slash_is_the_same_page(self, cloud, user, monkeypatch):
        """The first real visit was to `/admin/`, and it was a 404 — before the
        admin check ran, so it looked exactly like not being on the list."""
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", ADDRESS)
        response = signed_in(cloud, user).get("/admin/")
        assert response.status_code == 200
        assert "Growth" in response.get_data(as_text=True)

    def test_a_trailing_slash_opens_nothing_for_anybody_else(self, cloud, user, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", "somebody@example.com")
        assert signed_in(cloud, user).get("/admin/").status_code == 404
        signed_out = client_for(cloud).get("/admin/")
        assert signed_out.status_code == 302
        assert signed_out.headers["Location"].endswith("/login")

    def test_a_session_naming_a_user_that_is_gone_is_a_404(self, cloud, user, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", ADDRESS)
        client = signed_in(cloud, user)
        with pg_pool_of(cloud).connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user[1],))
        assert client.get("/admin").status_code == 404


def pg_pool_of(app):
    return app.config["POOL"]


# -- the way in: the settings home says who is signed in ---------------------

class TestTheSettingsHomeSaysWhoIsSignedIn:
    """The app bar carries the signed-in address and, for the listed address
    and nobody else, the one link there is to the operator's page."""

    def home(self, client):
        response = client.get("/settings/")
        assert response.status_code == 200
        return response.get_data(as_text=True)

    def test_the_address_is_on_the_page(self, cloud, user):
        assert ADDRESS in self.home(signed_in(cloud, user))

    def test_with_no_list_there_is_no_link_to_the_admin_page(self, cloud, user):
        html = self.home(signed_in(cloud, user))
        assert "View admin" not in html
        assert 'href="/admin"' not in html

    def test_somebody_else_on_the_list_gets_no_link_either(self, cloud, user, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", "somebody@example.com")
        html = self.home(signed_in(cloud, user))
        assert ADDRESS in html
        assert "View admin" not in html
        assert 'href="/admin"' not in html

    def test_the_listed_address_gets_the_link_and_it_opens(self, admin_client):
        html = self.home(admin_client)
        assert ADDRESS in html
        assert "View admin" in html
        assert 'href="/admin"' in html
        assert admin_client.get("/admin").status_code == 200

    def test_a_session_naming_a_user_that_is_gone_still_gets_its_settings(
            self, cloud, user, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", ADDRESS)
        client = signed_in(cloud, user)
        with pg_pool_of(cloud).connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user[1],))
        html = self.home(client)
        assert ADDRESS not in html
        assert "View admin" not in html

    def test_a_self_hoster_sees_neither(self, tmp_path, monkeypatch):
        """Single mode has nobody signed in and no pool to ask. With the list
        set, the page must render rather than reach for a database."""
        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", ADDRESS)
        (tmp_path / "config.yaml").write_text('family_name: "The Wilsons"\n')
        html = self.home(client_for(create_app(FileStore(tmp_path / "config.yaml"))))
        assert ADDRESS not in html
        assert "View admin" not in html
        assert "/admin" not in html


# -- what it shows -----------------------------------------------------------

@pytest.fixture
def admin_client(cloud, user, monkeypatch):
    monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", ADDRESS)
    return signed_in(cloud, user)


def rows_in_the_table(html):
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S).group(1)
    return re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>", body, re.S)


class TestWhatItShows:
    def test_the_numbers_come_from_the_counter(self, admin_client, monkeypatch):
        from datetime import datetime, timezone
        this_monday = growth.week_of(datetime.now(timezone.utc).date())
        monkeypatch.setattr(growth, "history", lambda pool: [
            (date(2025, 1, 6), 5, 2),          # long ago: in the totals, off the chart
            (this_monday, 3, 1),               # this week
        ])
        monkeypatch.setattr(growth, "families_now", lambda pool: 6)
        html = admin_client.get("/admin").get_data(as_text=True)
        # The tiles: 8 signups, 3 activations (38%), 6 families, 2 deleted.
        tiles = re.findall(r'<div class="value">(\d+)</div>', html)
        assert tiles == ["8", "3", "6"]
        assert "38% of signups" in html
        assert "2 deleted" in html
        assert "3 this week" in html
        # The table: twelve weeks, latest first, this week's row on top.
        rows = rows_in_the_table(html)
        assert len(rows) == 12
        assert rows[0][1:] == ("3", "1")
        assert rows[0][0] == this_monday.strftime("%-d %b %Y")
        assert all(row[1:] == ("0", "0") for row in rows[1:])

    def test_a_real_signup_appears(self, admin_client, pg_pool):
        # The fixture's own family was created moments ago, so this week has
        # at least one signup in it and the page says so.
        html = admin_client.get("/admin").get_data(as_text=True)
        rows = rows_in_the_table(html)
        assert int(rows[0][1]) >= 1
        assert int(re.findall(r'<div class="value">(\d+)</div>', html)[2]) >= 1

    def test_the_span_is_read_from_the_query_string_and_bounded(self, admin_client):
        for query, expected in (("", 12), ("?weeks=26", 26), ("?weeks=9999", 52),
                                ("?weeks=abc", 12), ("?weeks=0", 1)):
            html = admin_client.get("/admin" + query).get_data(as_text=True)
            assert len(rows_in_the_table(html)) == expected, query

    def test_a_deleted_account_is_still_counted(self, admin_client, pg_pool):
        from dinkydash import accounts
        from dinkydash import config as config_module

        with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO families (screen_token, config) VALUES (%s, %s::jsonb) "
                        "RETURNING id", (config_module.new_screen_token(),
                                         '{"calendars": [{"url": "https://example.com/x.ics"}]}'))
            other = cur.fetchone()[0]
        before = rows_in_the_table(admin_client.get("/admin").get_data(as_text=True))[0]
        assert accounts.delete_family(pg_pool, other)
        after = rows_in_the_table(admin_client.get("/admin").get_data(as_text=True))[0]
        assert after == before

    def test_the_page_makes_no_third_party_request(self, admin_client):
        html = admin_client.get("/admin").get_data(as_text=True)
        assert not re.search(r'(src|href)="https?://', html.replace("https://dinkydash.co", ""))
        assert "<script" not in html


# -- the roster ----------------------------------------------------------------

A_FAMILY_CONFIG = {
    "family_name": "The Zebedees",
    "people": [{"id": "zeb12345", "name": "Zebedee", "date_of_birth": "2015-04-01"}],
    "calendars": [{"id": "cal12345", "label": "Zebra school",
                   "url": "https://example.com/private-zzzz/basic.ics", "enabled": True}],
}


@pytest.fixture
def another_family(pg_pool):
    """A second family with a parent, a name, a child and a calendar — none of
    which but the address may appear on the operator's page."""
    from dinkydash import config as config_module
    from dinkydash.pgstore import PostgresStore

    with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO families (screen_token) VALUES (%s) RETURNING id",
                    (config_module.new_screen_token(),))
        family_id = cur.fetchone()[0]
        cur.execute("INSERT INTO users (family_id, email, last_login_at) "
                    "VALUES (%s, %s, now()) RETURNING id", (family_id, "zebedee@example.org"))
    PostgresStore(pg_pool, family_id).save_config(dict(A_FAMILY_CONFIG))
    yield family_id
    with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM families WHERE id = %s", (family_id,))


class TestTheRoster:
    def test_the_newest_families_are_listed_with_their_address(
            self, admin_client, another_family, pg_family):
        html = admin_client.get("/admin").get_data(as_text=True)
        assert "zebedee@example.org" in html
        assert ADDRESS in html
        # Newest first: the second family was made after the fixture's.
        assert html.index("zebedee@example.org") < html.index(ADDRESS)
        assert "activated" in html and "Trial to" in html

    def test_nothing_from_the_config_is_on_the_page(self, admin_client, another_family):
        html = admin_client.get("/admin").get_data(as_text=True)
        for private in ("Zebedee", "Zebra school", "private-zzzz", "2015-04-01", "The Zebedees"):
            assert private not in html, private

    def test_no_family_id_is_rendered(self, admin_client, another_family, pg_family):
        html = admin_client.get("/admin").get_data(as_text=True)
        assert str(pg_family) not in html
        assert str(another_family) not in html
        assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", html)

    def test_a_family_with_no_parent_row_is_still_listed(self, admin_client, pg_pool):
        # The signed-in fixture family has a parent; make one by hand without.
        from dinkydash import config as config_module
        with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO families (screen_token) VALUES (%s) RETURNING id",
                        (config_module.new_screen_token(),))
            orphan = cur.fetchone()[0]
        try:
            html = admin_client.get("/admin").get_data(as_text=True)
            assert "No address on file" in html
        finally:
            with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
                cur.execute("DELETE FROM families WHERE id = %s", (orphan,))

    def test_a_deleted_family_leaves_the_list(self, admin_client, another_family, pg_pool):
        from dinkydash import accounts
        assert "zebedee@example.org" in admin_client.get("/admin").get_data(as_text=True)
        assert accounts.delete_family(pg_pool, another_family)
        assert "zebedee@example.org" not in admin_client.get("/admin").get_data(as_text=True)

    def test_the_list_is_capped_and_says_so(self, admin_client, monkeypatch):
        monkeypatch.setattr(growth, "MOST_IN_ROSTER", 1)
        monkeypatch.setattr(growth, "families_now", lambda pool: 3)
        html = admin_client.get("/admin").get_data(as_text=True)
        assert "newest 1 of 3" in html
        assert html.count('class="row account"') == 1
