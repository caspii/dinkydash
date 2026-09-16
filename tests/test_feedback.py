"""The feedback form: what it sends, what it refuses, and what it never says (DIN-34).

Four claims, and each is the reason a test below exists:

* **A message reaches a person, with a way to answer it.** It goes to the
  support address with the family's own address as the reply-to, so replying is
  Reply rather than a copy and paste.
* **It carries nothing from the dashboard.** The page says so beside the box —
  no name, no calendar, no written line — and a page that makes a claim is a
  page whose claim is worth asserting. What goes is the words, the address and
  the family id.
* **What somebody wrote is theirs.** It is never logged, on the way out or on
  the way to a failure, and a failed send says so without quoting it.
* **The offer and the route agree.** With no mail provider there is no pill, no
  row on the settings home and no page — a button that could not work is worse
  than no button.

The Postgres half skips without `DINKYDASH_TEST_DATABASE_URL`; the unit tests
and the single-mode ones run anywhere.
"""

import logging

import pytest
import yaml

from dinkydash import mail
from dinkydash.store import FileStore
from tests.conftest import board_path, client_for
from web import create_app, feedback

CONFIG = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
calendars:
  - id: cal12345
    label: "School"
    url: "https://example.com/private-xxxx/basic.ics"
    enabled: true
"""

ADDRESS = "parent@example.com"
MESSAGE = "The countdown for half term is a day out."

# The dock itself, not its class: the stylesheet is shared, so every page
# carries the rule whether or not it carries the pill.
PILL = 'id="feedback-dock"'


class Outbox:
    """A stand-in for `mail.send` that remembers what it was asked to send."""

    def __init__(self, raises=None):
        self.sent = []
        self.raises = raises

    def __call__(self, to, subject, text, **kwargs):
        self.sent.append({"to": to, "subject": subject, "text": text, **kwargs})
        if self.raises:
            raise self.raises

    @property
    def only(self):
        assert len(self.sent) == 1, f"expected one email, got {len(self.sent)}"
        return self.sent[0]


@pytest.fixture
def outbox(monkeypatch):
    box = Outbox()
    monkeypatch.setattr(mail, "send", box)
    return box


@pytest.fixture(autouse=True)
def a_mail_key(monkeypatch):
    """The form is offered because there is somewhere to send it."""
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")


# -- what a message is made of ----------------------------------------------

class TestComposing:
    def test_the_message_comes_first(self):
        assert feedback.compose(MESSAGE).startswith(MESSAGE)

    def test_the_address_is_under_it(self):
        assert f"From: {ADDRESS}" in feedback.compose(MESSAGE, address=ADDRESS)

    def test_the_family_is_named_so_a_question_can_be_looked_into(self):
        body = feedback.compose(MESSAGE, address=ADDRESS, family_id="f-1")
        assert "Family: f-1" in body

    def test_a_self_hosted_message_has_no_family_and_says_so(self):
        body = feedback.compose(MESSAGE)
        assert "Family:" not in body
        assert "self-hosted" in body

    def test_the_subject_names_the_sender_so_a_mailbox_can_thread(self):
        assert feedback.subject_for(ADDRESS) == f"DinkyDash feedback from {ADDRESS}"
        assert feedback.subject_for(None) == "DinkyDash feedback (self-hosted)"

    def test_line_endings_are_normalised_and_the_words_are_not_touched(self):
        assert feedback.clean("  one\r\ntwo  ") == "one\ntwo"

    def test_nothing_written_cleans_to_nothing(self):
        assert feedback.clean("   \r\n  ") == ""
        assert feedback.clean(None) == ""


class TestWhetherItExists:
    def test_it_is_off_without_a_way_to_send(self, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY")
        assert feedback.enabled() is False

    def test_a_blank_key_is_no_key(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "   ")
        assert feedback.enabled() is False

    def test_it_is_on_with_one(self):
        assert feedback.enabled() is True


# -- self-hosted ------------------------------------------------------------

@pytest.fixture
def single(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG)
    return client_for(create_app(FileStore(path)))


class TestSelfHosted:
    def test_the_page_is_there(self, single):
        assert single.get("/settings/feedback").status_code == 200

    def test_it_sends_with_no_account_behind_it(self, single, outbox):
        single.post("/settings/feedback", data={"message": MESSAGE})
        assert outbox.only["text"].startswith(MESSAGE)
        assert outbox.only["reply_to"] is None

    def test_with_no_mail_provider_there_is_no_page(self, single, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY")
        assert single.get("/settings/feedback").status_code == 404

    def test_and_no_pill(self, single, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY")
        assert PILL not in single.get("/settings/").get_data(as_text=True)


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


class TestSending:
    def test_it_goes_to_the_support_inbox(self, parent, outbox):
        parent.post("/settings/feedback", data={"message": MESSAGE})
        assert outbox.only["to"] == mail.support_address()

    def test_a_reply_lands_with_the_family_that_wrote(self, parent, outbox):
        parent.post("/settings/feedback", data={"message": MESSAGE})
        assert outbox.only["reply_to"] == ADDRESS

    def test_the_words_and_the_family_go_and_nothing_else_does(self, parent, outbox, family):
        parent.post("/settings/feedback", data={"message": MESSAGE})
        body = outbox.only["text"]
        assert MESSAGE in body
        assert ADDRESS in body
        assert str(family[0]) in body
        # The dashboard stays out of it, which is what the page promises.
        assert "Mia" not in body
        assert "School" not in body
        assert "private-xxxx" not in body

    def test_it_says_so_and_goes_back_to_the_settings(self, parent, outbox):
        response = parent.post("/settings/feedback", data={"message": MESSAGE},
                               follow_redirects=True)
        assert "gone to a person" in response.get_data(as_text=True)

    def test_a_signed_out_caller_is_sent_to_the_login(self, cloud):
        response = client_for(cloud).get("/settings/feedback")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestRefusing:
    def test_an_empty_message_sends_nothing_and_says_why(self, parent, outbox):
        response = parent.post("/settings/feedback", data={"message": "   "})
        assert outbox.sent == []
        assert "Write something first" in response.get_data(as_text=True)

    def test_too_long_sends_nothing_and_offers_the_address_instead(self, parent, outbox):
        response = parent.post("/settings/feedback",
                               data={"message": "x" * (feedback.LONGEST + 1)})
        assert outbox.sent == []
        assert mail.support_address() in response.get_data(as_text=True)

    def test_what_was_typed_is_handed_back_rather_than_lost(self, parent, outbox):
        response = parent.post("/settings/feedback",
                               data={"message": "x" * (feedback.LONGEST + 1)})
        assert "x" * 100 in response.get_data(as_text=True)

    def test_the_limit_stops_the_next_one(self, parent, outbox):
        from web.routes.settings import MOST_FEEDBACK

        for _ in range(MOST_FEEDBACK):
            parent.post("/settings/feedback", data={"message": MESSAGE})
        response = parent.post("/settings/feedback", data={"message": MESSAGE})
        assert len(outbox.sent) == MOST_FEEDBACK
        assert "more than this form takes" in response.get_data(as_text=True)

    def test_a_send_that_fails_apologises_and_keeps_the_words(self, parent, monkeypatch):
        monkeypatch.setattr(mail, "send", Outbox(raises=mail.MailError("nope")))
        response = parent.post("/settings/feedback", data={"message": MESSAGE})
        page = response.get_data(as_text=True)
        assert "did not send" in page
        assert MESSAGE in page


class TestWhatIsNeverWritten:
    def test_a_sent_message_is_not_in_the_log(self, parent, outbox, caplog):
        with caplog.at_level(logging.DEBUG):
            parent.post("/settings/feedback", data={"message": MESSAGE})
        assert MESSAGE not in caplog.text
        assert ADDRESS not in caplog.text

    def test_nor_is_one_that_failed(self, parent, monkeypatch, caplog):
        monkeypatch.setattr(mail, "send", Outbox(raises=mail.MailError("nope")))
        with caplog.at_level(logging.DEBUG):
            parent.post("/settings/feedback", data={"message": MESSAGE})
        assert MESSAGE not in caplog.text


class TestWhereThePillIs:
    def test_on_a_settings_page(self, parent):
        assert PILL in parent.get("/settings/").get_data(as_text=True)

    def test_and_on_the_pages_below_it(self, parent):
        assert PILL in parent.get("/settings/system").get_data(as_text=True)

    def test_never_on_the_dashboard(self, parent, pg_pool, family):
        page = parent.get(board_path(pg_pool, family[0])).get_data(as_text=True)
        assert PILL not in page

    def test_not_on_the_sign_in_page(self, cloud):
        page = client_for(cloud).get("/login").get_data(as_text=True)
        assert PILL not in page

    def test_not_on_the_page_it_leads_to(self, parent):
        assert PILL not in parent.get("/settings/feedback").get_data(as_text=True)

    def test_the_settings_home_keeps_a_way_in_that_cannot_be_dismissed(self, parent):
        assert "/settings/feedback" in parent.get("/settings/").get_data(as_text=True)
