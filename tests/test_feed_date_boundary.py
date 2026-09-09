"""Calendar checks use the family's day even across midnight on the server."""

from datetime import datetime

import pytest

from dinkydash import config as config_module
from dinkydash.store import FileStore
from tests.conftest import client_for
from tests.test_calendars import all_day, ical
from web import create_app


@pytest.mark.parametrize("mode", ["single", "cloud"])
@pytest.mark.parametrize("timezone,instant,expected", [
    ("Europe/Berlin", "2026-09-02T23:30:00+00:00", "2026-09-03"),
    ("America/Los_Angeles", "2026-09-03T01:30:00+00:00", "2026-09-02"),
])
def test_check_uses_the_family_date(mode, timezone, instant, expected,
                                    monkeypatch, tmp_path, request):
    now = datetime.fromisoformat(instant)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz)

    monkeypatch.setattr(config_module, "datetime", Clock)
    monkeypatch.setenv("DINKYDASH_MODE", mode)
    config = config_module.with_defaults({"timezone": timezone})
    if mode == "single":
        store = FileStore(tmp_path / "config.yaml")
        store.save_config(config)
        app = create_app(store)
    else:
        from dinkydash.pgstore import PostgresStore

        pool = request.getfixturevalue("pg_pool")
        family_id = request.getfixturevalue("pg_family")
        PostgresStore(pool, family_id).save_config(config)
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "test-calendar-date-secret")
        app = create_app(pool=pool)

    # Exercise the real describe/parse path; only the network and clock are fake.
    feed = ical(*(all_day(day, day.replace("-", ""), f"Plans for {day}")
                  for day in ["2026-09-02", "2026-09-03", "2026-09-04"]))
    monkeypatch.setattr("dinkydash.calendars.fetch_text", lambda *a, **kw: feed)
    client = client_for(app)
    if mode == "cloud":
        with client.session_transaction() as session:
            session["user_id"] = "test-calendar-user"
            session["family_id"] = str(family_id)

    response = client.post("/settings/calendars/new", data={
        "action": "check", "label": "Family", "url": "https://calendar.example/test.ics",
    })
    assert response.status_code == 200
    assert f"Next up: Plans for {expected}, {expected}" in response.get_data(as_text=True)
