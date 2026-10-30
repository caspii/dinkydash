"""The calendar step on a phone: said up front, and emailable to a computer.

Google shows a calendar's secret address on its website and not in its app, so
a parent setting up on a phone cannot finish the calendar step there. Three
claims:

* **The form says so before the button is pressed**, in both modes, rather than
  inside the collapsed steps under it.
* **Hosted, the parent can email themselves the steps**, to the account's own
  address and nobody else's. Nothing of the family goes in the email.
* **The offer and the route agree.** With no account address or no mail
  provider there is no button and the route is a 404.

The Postgres half skips without `DINKYDASH_TEST_DATABASE_URL`.
"""

import pytest
import yaml

from dinkydash import mail
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app

CONFIG = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
"""

ADDRESS = "parent@example.com"
NOTE = "Google only shows this link on a computer."
BUTTON = "Email me the steps"


class Outbox:
    def __init__(self, raises=None):
        self.sent = []
        self.raises = raises

    def __call__(self, to, subject, text, **kwargs):
        self.sent.append({"to": to, "subject": subject, "text": text, **kwargs})
        if self.raises:
            raise self.raises


@pytest.fixture
def outbox(monkeypatch):
    box = Outbox()
    monkeypatch.setattr(mail, "send", box)
    return box


@pytest.fixture(autouse=True)
def a_mail_key(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")


# -- self-hosted ------------------------------------------------------------

@pytest.fixture
def single(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG)
    return client_for(create_app(FileStore(path)))


class TestSelfHosted:
    def test_the_note_is_on_the_form(self, single):
        page = single.get("/settings/calendars/new").get_data(as_text=True)
        assert NOTE in page
        # Before the steps that are folded away, not inside them.
        assert page.index(NOTE) < page.index("Where do I find my calendar link?")

    def test_but_there_is_no_account_to_email(self, single):
        page = single.get("/settings/calendars/new").get_data(as_text=True)
        assert BUTTON not in page
        assert single.post("/settings/calendar-steps").status_code == 404


# -- hosted -----------------------------------------------------------------

@pytest.fixture
def family(pg_pool, pg_family):
    from dinkydash.pgstore import PostgresStore

    PostgresStore(pg_pool, pg_family).save_config(yaml.safe_load(CONFIG))
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                (pg_family, ADDRESS),
            )
            user_id = cur.fetchone()[0]
    return pg_family, user_id


@pytest.fixture
def cloud(pg_pool, monkeypatch):
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    return create_app(pool=pg_pool)


@pytest.fixture
def parent(cloud, family):
    family_id, user_id = family
    client = client_for(cloud)
    with client.session_transaction() as stored:
        stored["user_id"] = user_id
        stored["family_id"] = str(family_id)
    return client


class TestHosted:
    def test_the_button_is_offered(self, parent):
        page = parent.get("/settings/calendars/new").get_data(as_text=True)
        assert BUTTON in page
        assert 'form="calendar-steps"' in page
        assert 'id="calendar-steps"' in page

    def test_it_goes_to_the_account_and_nowhere_else(self, parent, outbox):
        landed = parent.post("/settings/calendar-steps", data={"to": "someone@else.example"})
        assert landed.status_code == 302
        assert landed.headers["Location"].endswith("/settings/calendars/new")
        assert [m["to"] for m in outbox.sent] == [ADDRESS]

    def test_it_says_where_to_go_and_what_to_copy(self, parent, outbox):
        parent.post("/settings/calendar-steps")
        text = outbox.sent[0]["text"]
        assert "/login" in text
        assert "Secret address in iCal format" in text
        assert "Save calendar" in text
        # Nothing of the family: not its name, not its people.
        assert "Wilsons" not in text and "Mia" not in text

    def test_the_page_says_it_went(self, parent, outbox):
        page = parent.post("/settings/calendar-steps",
                           follow_redirects=True).get_data(as_text=True)
        assert f"Sent to {ADDRESS}. Open it on your computer." in page

    def test_a_failed_send_says_so(self, parent, monkeypatch):
        monkeypatch.setattr(mail, "send", Outbox(raises=mail.MailError("refused")))
        page = parent.post("/settings/calendar-steps",
                           follow_redirects=True).get_data(as_text=True)
        assert "That didn&#39;t send." in page

    def test_a_stuck_button_stops_sending(self, parent, outbox):
        for _ in range(5):
            parent.post("/settings/calendar-steps")
        assert len(outbox.sent) == 3

    def test_with_no_mail_provider_there_is_neither(self, parent, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY")
        assert BUTTON not in parent.get("/settings/calendars/new").get_data(as_text=True)
        assert parent.post("/settings/calendar-steps").status_code == 404
