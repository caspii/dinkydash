"""The hard breaker on what the model costs (DIN-43).

Five claims:

* **a call is charged before it is made**, so a key that fails every time still
  runs out rather than retrying for ever;
* **the per-family cap is exact**, because it is enforced against the locked row
  rather than a value read a moment earlier;
* **the global cap scales with the number of families**, so it does not quietly
  start starving real dashboards as the product grows;
* **a refusal keeps the dashboard that is on the wall.** It arrives as a
  `GenerationError`, which every caller already handles that way, and nothing is
  written;
* **single mode is untouched.** A self-hoster's key is their own bill.

The Postgres half skips without `DINKYDASH_TEST_DATABASE_URL`. What can be
tested without a database — `NoBudget`, the environment parsing, and that a
refusal writes nothing — is tested without one.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

import pytest
import yaml

sys.path.insert(0, os.path.dirname(__file__))

from dinkydash import budget as budget_module      # noqa: E402
from dinkydash import runner                       # noqa: E402
from dinkydash.budget import (FAMILY_CALLS_A_DAY, GLOBAL_FLOOR,  # noqa: E402
                              GLOBAL_PER_FAMILY, NoBudget, OverBudget,
                              PostgresBudget)
from dinkydash.claude_client import GenerationError  # noqa: E402
from dinkydash.store import FileStore              # noqa: E402
from test_generate import FakeClient               # noqa: E402

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
'''


@pytest.fixture
def key(monkeypatch):
    """`write_brief` refuses without one before it reaches anything else."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")


@pytest.fixture
def store(tmp_path):
    (tmp_path / "config.yaml").write_text(CONFIG)
    return FileStore(tmp_path / "config.yaml")


def spend_rows(pg_pool, family_id):
    with pg_pool.connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT calls, input_tokens, output_tokens FROM model_spend
                       WHERE family_id = %s AND day = %s""",
                    (family_id, datetime.now(timezone.utc).date()))
        return cur.fetchone()


@pytest.fixture
def clean(pg_pool):
    yield
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM model_spend")


# -- single mode has no ceiling ---------------------------------------------

class TestNoBudget:
    def test_it_allows_everything_for_ever(self):
        empty = NoBudget()
        for _ in range(1000):
            assert empty.allow() is None

    def test_and_recording_is_a_no_op(self):
        assert NoBudget().record(999, 999) is None

    def test_write_brief_needs_no_budget_at_all(self, store, key):
        """A self-hoster brings their own API key, so the bill is theirs. The
        two things that bound a Pi are `schedule.due` and the tick lock, and
        neither is about money."""
        payload = runner.write_brief(store.load_config(), store,
                                     today=date(2026, 9, 3), client=FakeClient())
        assert payload["headline"] == "Big morning"

    def test_self_hosted_generation_keeps_the_configured_model_and_tokens(self, store, key):
        config = dict(store.load_config(), claude_model="self-hosted-model", max_tokens=2048)
        client = FakeClient()
        runner.write_brief(config, store, client=client)
        assert client.messages.calls[0]["model"] == "self-hosted-model"
        assert client.messages.calls[0]["max_tokens"] == 2048


# -- the caps read from the environment -------------------------------------

class TestTheNumbersComeFromTheEnvironment:
    """Raisable without a deploy, which is most of what you want at 2am."""

    def test_unset_is_the_constant(self, monkeypatch):
        monkeypatch.delenv("DINKYDASH_FAMILY_CALLS_A_DAY", raising=False)
        assert budget_module._number("DINKYDASH_FAMILY_CALLS_A_DAY", 12) == 12

    def test_a_number_wins(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_FAMILY_CALLS_A_DAY", "40")
        assert budget_module._number("DINKYDASH_FAMILY_CALLS_A_DAY", 12) == 40

    @pytest.mark.parametrize("typed", ["twelve", "", "  ", "12.5", "-3"])
    def test_anything_else_falls_back_to_the_limit_and_never_to_none(
            self, monkeypatch, typed):
        """**A breaker that fails open because somebody typed `twelve` is not
        one.** Zero is allowed on purpose — it is a way to stop all spending —
        but a negative or unparseable value is a typo, not an intention."""
        monkeypatch.setenv("DINKYDASH_FAMILY_CALLS_A_DAY", typed)
        assert budget_module._number("DINKYDASH_FAMILY_CALLS_A_DAY", 12) == 12

    def test_zero_is_a_real_answer(self, monkeypatch):
        """Stopping every call is a thing somebody might genuinely want to do."""
        monkeypatch.setenv("DINKYDASH_FAMILY_CALLS_A_DAY", "0")
        assert budget_module._number("DINKYDASH_FAMILY_CALLS_A_DAY", 12) == 0


# -- counting, in Postgres --------------------------------------------------

class TestCountingCalls:
    def test_the_first_call_is_allowed_and_recorded(self, pg_pool, pg_family, clean):
        assert PostgresBudget(pg_pool, pg_family).allow() == 1
        assert spend_rows(pg_pool, pg_family)[0] == 1

    def test_each_one_adds_to_the_count(self, pg_pool, pg_family, clean):
        budget = PostgresBudget(pg_pool, pg_family)
        assert [budget.allow() for _ in range(3)] == [1, 2, 3]

    def test_it_is_charged_on_the_attempt_not_on_success(
            self, pg_pool, pg_family, clean):
        """An expired key fails every call and reports no usage, so a breaker
        counting successes would watch a five-minute retry loop for ever."""
        budget = PostgresBudget(pg_pool, pg_family)
        budget.allow()          # and then the call fails; nothing recorded
        assert spend_rows(pg_pool, pg_family) == (1, 0, 0)

    def test_tokens_are_added_afterwards(self, pg_pool, pg_family, clean):
        budget = PostgresBudget(pg_pool, pg_family)
        budget.allow()
        budget.record(1200, 90)
        assert spend_rows(pg_pool, pg_family) == (1, 1200, 90)

    def test_recording_twice_adds_up(self, pg_pool, pg_family, clean):
        budget = PostgresBudget(pg_pool, pg_family)
        budget.allow()
        budget.record(100, 10)
        budget.allow()
        budget.record(200, 20)
        assert spend_rows(pg_pool, pg_family) == (2, 300, 30)

    def test_recording_never_raises(self, pg_pool, pg_family, clean):
        """Bookkeeping, not control. Losing a token count must not turn a dashboard
        that was written into a failure that gets retried and paid for again."""
        budget = PostgresBudget(pg_pool, pg_family)
        budget.allow()
        assert budget.record(None, None) is None
        assert budget.record("nonsense", 3) is None

    def test_used_today_reports_mine_and_everybody_s(
            self, pg_pool, pg_family, clean):
        PostgresBudget(pg_pool, pg_family).allow()
        mine, everyone = PostgresBudget(pg_pool, pg_family).used_today()
        assert mine == 1 and everyone == 1


# -- the per-family cap -----------------------------------------------------

class TestThePerFamilyCap:
    def test_it_refuses_the_one_past_the_limit(self, pg_pool, pg_family, clean):
        budget = PostgresBudget(pg_pool, pg_family, family_a_day=3)
        for _ in range(3):
            budget.allow()
        with pytest.raises(OverBudget):
            budget.allow()

    def test_and_the_count_does_not_keep_climbing(self, pg_pool, pg_family, clean):
        """A refused call is not a call, so it must not be charged for. Otherwise
        a loop hammering a tripped breaker would make the number meaningless."""
        budget = PostgresBudget(pg_pool, pg_family, family_a_day=2)
        budget.allow()
        budget.allow()
        for _ in range(5):
            with pytest.raises(OverBudget):
                budget.allow()
        assert spend_rows(pg_pool, pg_family)[0] == 2
        assert budget.used_today() == (2, 2)

    def test_a_cap_of_zero_refuses_everything(self, pg_pool, pg_family, clean):
        with pytest.raises(OverBudget):
            PostgresBudget(pg_pool, pg_family, family_a_day=0).allow()
        assert PostgresBudget(pg_pool, pg_family).used_today() == (0, 0)

    def test_concurrent_charges_cannot_lose_counts_or_exceed_the_family_cap(
            self, pg_pool, pg_family, clean):
        budget = PostgresBudget(pg_pool, pg_family, family_a_day=3)

        def charge(_):
            try:
                budget.allow()
                return True
            except OverBudget:
                return False

        with ThreadPoolExecutor(max_workers=2) as callers:
            assert sum(callers.map(charge, range(10))) == 3
        assert budget.used_today() == (3, 3)

    def test_the_refusal_is_a_generation_error(self, pg_pool, pg_family, clean):
        """So every caller's existing keep-last-good path handles it. A second
        kind of failure would mean a second such path, and the one written
        second is the one that blanks somebody's screen."""
        budget = PostgresBudget(pg_pool, pg_family, family_a_day=0)
        with pytest.raises(GenerationError):
            budget.allow()

    def test_and_says_the_board_is_unchanged(self, pg_pool, pg_family, clean):
        budget = PostgresBudget(pg_pool, pg_family, family_a_day=0)
        with pytest.raises(OverBudget, match="unchanged"):
            budget.allow()

    def test_yesterday_does_not_count_against_today(
            self, pg_pool, pg_family, clean):
        """The row is per UTC day, so a family that spent everything yesterday
        starts again rather than staying refused."""
        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO model_spend (day, family_id, calls)
                               VALUES (%s, %s, 99)""",
                            (date(2020, 1, 1), pg_family))
        assert PostgresBudget(pg_pool, pg_family, family_a_day=3).allow() == 1


# -- the global cap ---------------------------------------------------------

class TestTheGlobalCap:
    def test_zero_refuses_the_first_call_too(self, pg_pool, pg_family, clean):
        budget = PostgresBudget(pg_pool, pg_family, global_floor=0, global_per_family=0)
        with pytest.raises(OverBudget):
            budget.allow()
        assert budget.used_today() == (0, 0)

    def test_deleting_and_signing_up_again_does_not_refund_calls(
            self, pg_pool, pg_family, clean):
        from dinkydash import accounts

        caps = {"global_floor": 1, "global_per_family": 0}
        address = "spending-parent@example.com"
        family_id = None
        try:
            first = accounts.consume_link(pg_pool, accounts.issue_signup_link(pg_pool, address))
            family_id = first[1]
            budget = PostgresBudget(pg_pool, family_id, **caps)
            budget.allow()
            budget.record(1200, 90)
            assert accounts.delete_family(pg_pool, family_id)
            assert spend_rows(pg_pool, family_id) is None
            with pg_pool.connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = %s", (address,))
                assert cur.fetchone() is None
            assert budget.used_today() == (0, 1)

            second = accounts.consume_link(pg_pool, accounts.issue_signup_link(pg_pool, address))
            family_id = second[1]
            assert family_id != first[1]
            replacement = PostgresBudget(pg_pool, family_id, **caps)
            with pytest.raises(OverBudget):
                replacement.allow()
            assert replacement.used_today() == (0, 1)
        finally:
            if family_id is not None:
                accounts.delete_family(pg_pool, family_id)

    def test_it_refuses_a_family_that_is_within_its_own_limit(
            self, pg_pool, pg_family, clean):
        """The point of having a global one at all: one family behaving normally
        is not what a runaway looks like, and the total is."""
        budget = PostgresBudget(pg_pool, pg_family, family_a_day=1000,
                                global_floor=2, global_per_family=0)
        budget.allow()
        budget.allow()
        with pytest.raises(OverBudget):
            budget.allow()

    def test_it_counts_every_family_together(self, pg_pool, pg_family, clean):
        from dinkydash import config as config_module

        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO families (screen_token, config)
                               VALUES (%s, '{}'::jsonb) RETURNING id""",
                            (config_module.new_screen_token(),))
                other = cur.fetchone()[0]

        caps = {"family_a_day": 1000, "global_floor": 2, "global_per_family": 0}
        PostgresBudget(pg_pool, pg_family, **caps).allow()
        PostgresBudget(pg_pool, other, **caps).allow()
        # Neither family is near its own limit; together they are at the global.
        with pytest.raises(OverBudget):
            PostgresBudget(pg_pool, other, **caps).allow()

        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM families WHERE id = %s", (other,))

    def test_it_scales_with_how_many_families_there_are(
            self, pg_pool, pg_family, clean):
        """A fixed ceiling starts starving real dashboards on the day the product
        grows into it, and the failure looks like a quiet morning."""
        budget = PostgresBudget(pg_pool, pg_family, family_a_day=1000,
                                global_floor=0, global_per_family=3)
        # One family exists, so the ceiling is three.
        for _ in range(3):
            budget.allow()
        with pytest.raises(OverBudget):
            budget.allow()

    def test_the_defaults_are_generous_enough_for_the_product_as_designed(self):
        """One brief a day per family is the design. If the shipped numbers ever
        stop leaving room for that, this is where it should be noticed."""
        assert FAMILY_CALLS_A_DAY > 1
        assert GLOBAL_PER_FAMILY > 1
        assert GLOBAL_FLOOR >= FAMILY_CALLS_A_DAY


# -- what a refusal does to the dashboard ---------------------------------------

class TestARefusalKeepsTheBoard:
    class Broke(NoBudget):
        """A budget that refuses everything, with no database behind it."""

        def allow(self):
            raise OverBudget("no")

        def record(self, *_):  # pragma: no cover - never reached
            raise AssertionError("recorded a call that was refused")

    def test_write_brief_raises_rather_than_writing(self, store, key):
        with pytest.raises(OverBudget):
            runner.write_brief(store.load_config(), store, today=date(2026, 9, 3),
                               client=FakeClient(), budget=self.Broke())
        assert not store.load_payload(store.load_config())

    def test_the_model_is_never_called(self, store, key):
        """Charged before, so a refusal costs nothing at all — which is the
        whole point of checking first rather than counting afterwards."""
        client = FakeClient()
        with pytest.raises(OverBudget):
            runner.write_brief(store.load_config(), store, today=date(2026, 9, 3),
                               client=client, budget=self.Broke())
        assert client.messages.calls == []

    def test_an_existing_board_is_left_exactly_as_it_was(self, store, key):
        config = store.load_config()
        runner.write_brief(config, store, today=date(2026, 9, 3), client=FakeClient())
        before = store.load_payload(config)

        with pytest.raises(OverBudget):
            runner.write_brief(config, store, today=date(2026, 9, 4),
                               client=FakeClient(), budget=self.Broke())
        assert store.load_payload(config) == before

    def test_a_tick_keeps_the_last_good_board_and_says_so(self, store, key, caplog):
        """The refusal takes the path a failed generation already takes. There
        is no second keep-last-good branch, which is why there is nothing new
        here to get wrong."""
        from generate import tick

        config = store.load_config()
        runner.refresh_calendars(config, store, today=date(2026, 9, 3))
        with caplog.at_level("ERROR"):
            assert tick(config, store, budget=self.Broke()) == 1
        assert "Keeping the previous dashboard" in caplog.text

    def test_the_refresh_still_happens(self, store, key):
        """Fetching calendars costs requests, not money. A family who cannot
        afford a new headline today should still have an accurate agenda under
        yesterday's."""
        config = store.load_config()
        with pytest.raises(OverBudget):
            runner.run(config, store, today=date(2026, 9, 3),
                       client=FakeClient(), budget=self.Broke())
        assert store.load_payload(config).get("calendars_fetched_at")


# -- and the browser path, which was the unbounded one ----------------------

class TestRewriteNowIsChargedToo:
    """`POST /settings/generate` was the one route to Anthropic with no limit on
    it at all — a signed-in parent holding the button down is an unbounded bill
    from one browser. It spends the same money out of the same account as the
    worker, so it is counted in the same place."""

    @pytest.fixture
    def cloud(self, pg_pool, pg_family, monkeypatch, key):
        from dinkydash.pgstore import PostgresStore
        from web import create_app

        PostgresStore(pg_pool, pg_family).save_config(yaml.safe_load(CONFIG))
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
        # The model call itself, replaced. Everything before it — the budget
        # check — is what this is about, and no test may cost money.
        monkeypatch.setattr(runner, "generate", lambda *a, **k: {
            "headline": "Big morning", "note": "An octopus fact.",
            "note_kind": "fact", "generated_for_date": "2026-09-03",
            "generated_at": "2026-09-03T04:00:00+00:00",
            "model": "claude-haiku-4-5", "input_tokens": 1200, "output_tokens": 90})
        return create_app(pool=pg_pool)

    @pytest.fixture
    def parent(self, cloud, pg_family):
        from tests.conftest import client_for

        client = client_for(cloud)
        with client.session_transaction() as stored:
            stored["user_id"] = 1
            stored["family_id"] = str(pg_family)
        return client

    def test_pressing_it_is_counted(self, parent, pg_pool, pg_family, clean):
        parent.post("/settings/generate")
        assert spend_rows(pg_pool, pg_family) == (1, 1200, 90)

    def test_pressing_it_repeatedly_runs_out(self, parent, pg_pool, pg_family,
                                             monkeypatch, clean):
        monkeypatch.setenv("DINKYDASH_FAMILY_CALLS_A_DAY", "2")
        for _ in range(5):
            parent.post("/settings/generate")
        assert spend_rows(pg_pool, pg_family)[0] == 2

    def test_and_says_so_rather_than_failing(self, parent, monkeypatch, clean):
        monkeypatch.setenv("DINKYDASH_FAMILY_CALLS_A_DAY", "0")
        landed = parent.post("/settings/generate", follow_redirects=True)
        assert landed.status_code == 200
        assert "limit on rewriting the dashboard" in landed.get_data(as_text=True)

    def test_a_refused_press_leaves_the_written_board_alone(
            self, parent, pg_pool, pg_family, monkeypatch, clean):
        """**The brief half, not the whole payload.** "Rewrite now" refreshes
        the calendars first and that is deliberately outside the budget — a
        fetch costs requests rather than money — so `calendars_fetched_at`
        moves and should. What must not change is the model's words, and this
        asserts exactly that rather than the looser thing."""
        from dinkydash.pgstore import PostgresStore

        brief = ("headline", "note", "note_kind", "generated_for_date",
                 "generated_at", "input_tokens", "output_tokens")
        store = PostgresStore(pg_pool, pg_family)
        parent.post("/settings/generate")
        before = {k: store.load_payload(store.load_config()).get(k) for k in brief}

        monkeypatch.setenv("DINKYDASH_FAMILY_CALLS_A_DAY", "1")
        parent.post("/settings/generate")
        after = {k: store.load_payload(store.load_config()).get(k) for k in brief}
        assert after == before

    def test_but_the_calendars_are_still_refreshed(self, parent, pg_pool,
                                                   pg_family, monkeypatch, clean):
        """A family who cannot afford a new headline today should still have an
        accurate agenda under yesterday's."""
        from dinkydash.pgstore import PostgresStore

        monkeypatch.setenv("DINKYDASH_FAMILY_CALLS_A_DAY", "0")
        parent.post("/settings/generate")
        store = PostgresStore(pg_pool, pg_family)
        assert store.load_payload(store.load_config()).get("calendars_fetched_at")


@pytest.mark.parametrize("caller", ["worker", "rewrite"])
@pytest.mark.parametrize("stored_tokens", [100000, "invalid", 0])
def test_hosted_callers_enforce_model_policy_at_the_api(
        pg_pool, pg_family, key, monkeypatch, caller, stored_tokens):
    import anthropic
    from dinkydash.claude_client import DEFAULT_MAX_TOKENS, DEFAULT_MODEL
    from dinkydash.pgstore import PostgresStore
    from tests.conftest import client_for
    from web import create_app
    from worker import tick_all

    store = PostgresStore(pg_pool, pg_family)
    store.save_config(dict(yaml.safe_load(CONFIG), brief_time="00:00",
                           claude_model="legacy-expensive-model", max_tokens=stored_tokens))
    model = FakeClient()
    monkeypatch.setattr(anthropic, "Anthropic", lambda: model)
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "test-session-key")
    parent = client_for(create_app(pool=pg_pool))
    with parent.session_transaction() as session:
        session["user_id"] = 1
        session["family_id"] = str(pg_family)

    assert parent.post("/settings/system", data={
        "family_name": "The Wilsons", "claude_model": "posted-expensive-model",
        "max_tokens": "200000",
    }).status_code == 302
    before = store.load_config()
    assert before["claude_model"] == "legacy-expensive-model"
    assert before["max_tokens"] == stored_tokens

    if caller == "worker":
        assert tick_all(pg_pool).ticked == 1
    else:
        assert parent.post("/settings/generate").status_code == 302

    assert len(model.messages.calls) == 1
    sent = model.messages.calls[0]
    assert sent["model"] == DEFAULT_MODEL
    assert sent["max_tokens"] == DEFAULT_MAX_TOKENS
    assert store.load_payload(before)["model"] == DEFAULT_MODEL
    assert store.load_config() == before
    assert PostgresBudget(pg_pool, pg_family).used_today() == (1, 1)
