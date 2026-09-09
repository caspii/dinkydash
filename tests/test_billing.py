"""Payment boundaries with a real database and signed, reordered deliveries.

The fake replaces Stripe's network only. Sessions, CSRF, transactions, access
checks, signature verification and notification delivery decisions are real.
No test calls Stripe, SendGrid or a model provider.
"""

import copy
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask.testing import FlaskClient

from dinkydash import accounts, billing, lifecycle, mail
from tests.conftest import client_for
from web import create_app


class Stripe:
    def __init__(self):
        self.sessions = {}
        self.attempts = {}
        self.subscriptions = []
        self.customers = {}
        self.v1 = SimpleNamespace(
            prices=SimpleNamespace(retrieve=Mock(side_effect=self.price)),
            customers=SimpleNamespace(create=Mock(side_effect=self.customer),
                                      retrieve=Mock(side_effect=lambda cid: sdk(self.customers[cid])),
                                      delete=Mock(side_effect=self.delete_customer)),
            checkout=SimpleNamespace(sessions=SimpleNamespace(
                create=Mock(side_effect=self.checkout),
                retrieve=Mock(side_effect=lambda sid: sdk(self.sessions[sid])),
            )),
            subscriptions=SimpleNamespace(list=Mock(side_effect=lambda params: sdk({
                "data": copy.deepcopy([s for s in self.subscriptions if s["customer"] == params["customer"]]),
                "has_more": False,
            }))),
            billing_portal=SimpleNamespace(configurations=SimpleNamespace(retrieve=Mock(return_value=sdk({
                "active": True, "features": {
                    "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
                    "invoice_history": {"enabled": True}, "payment_method_update": {"enabled": True},
                    "subscription_update": {"enabled": True, "default_allowed_updates": ["price"],
                        "products": [{"product": "prod_example", "prices": ["price_month_example", "price_year_example"]}]},
                },
            }))), sessions=SimpleNamespace(create=Mock(return_value=sdk({
                "url": "https://billing.stripe.com/p/session_example",
            })))),
            tax=SimpleNamespace(settings=SimpleNamespace(retrieve=Mock(return_value=sdk({"status": "active"})))),
        )

    def price(self, price_id):
        annual = price_id == "price_year_example"
        return sdk({"id": price_id, "active": True, "currency": "usd",
                "unit_amount": 3900 if annual else 600, "tax_behavior": "exclusive",
                "product": "prod_example", "recurring": {
                    "interval": "year" if annual else "month", "interval_count": 1, "usage_type": "licensed",
                }})

    def customer(self, params, options):
        cid = "cus_" + params["metadata"]["family_id"]
        self.customers[cid] = {"id": cid}
        return sdk(self.customers[cid])

    def checkout(self, params, options):
        key = options["idempotency_key"]
        if key in self.attempts:
            old_params, sid = self.attempts[key]
            assert old_params == params
            return sdk(self.sessions[sid])
        sid = "cs_example_" + str(len(self.sessions))
        self.attempts[key] = (copy.deepcopy(params), sid)
        self.sessions[sid] = {"id": sid, "status": "open", "url": f"https://checkout.stripe.com/c/pay/{sid}"}
        return sdk(self.sessions[sid])

    def delete_customer(self, cid):
        self.customers[cid] = {"id": cid, "deleted": True}
        self.subscriptions = [s for s in self.subscriptions if s["customer"] != cid]
        return sdk(self.customers[cid])


def sdk(data):
    import stripe
    return stripe.StripeObject.construct_from(data, None)


@pytest.fixture
def service():
    pytest.importorskip("stripe")
    return billing.Billing(
        secret_key="sk_test_example", webhook_secret="whsec_example",
        monthly_price="price_month_example", yearly_price="price_year_example",
        portal_configuration="bpc_example", automatic_tax=False,
        origin="https://app.example.com", _client=Stripe(),
    )


@pytest.fixture
def parent(monkeypatch, pg_pool, pg_family, service):
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "billing-test-session-key")
    app = create_app(pool=pg_pool)
    app.config["BILLING"] = service
    with pg_pool.connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                    (pg_family, "parent@example.com"))
        user_id = cur.fetchone()[0]
    client = client_for(app)
    with client.session_transaction() as session:
        session.update(user_id=user_id, family_id=str(pg_family))
    return client


def state(pool, family_id):
    with pool.connection() as conn, conn.cursor() as cur:
        return billing.family(cur, family_id)


def sql(pool, query, params=()):
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall() if cur.description else []


def subscription(service, family_id, status="active", **changes):
    now = int(time.time())
    result = {"id": "sub_example", "customer": "cus_" + str(family_id),
              "metadata": {"family_id": str(family_id)}, "created": now,
              "status": status, "cancel_at_period_end": False,
              "items": {"data": [{"current_period_start": now, "current_period_end": now + 2592000}]},
              "latest_invoice": {"id": "in_example", "created": now, "status": "paid"}}
    result.update(changes)
    service.client.subscriptions = [result]
    return result


def webhook(client, service, family_id, event_id="evt_example", event_type="invoice.paid", **changes):
    payload = {"id": event_id, "object": "event", "type": event_type, "livemode": False,
               "created": 100, "data": {"object": {"customer": "cus_" + str(family_id)}}}
    payload.update(changes)
    raw = json.dumps(payload).encode()
    stamp = str(int(time.time()))
    digest = hmac.new(service.webhook_secret.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return client.post("/stripe/webhook", data=raw, content_type="application/json",
                       headers={"Stripe-Signature": f"t={stamp},v1={digest}"})


def start(service, pool, family_id):
    return service.checkout(pool, family_id, "year")


def test_signup_and_billing_page_do_not_create_customer(parent, service, pg_pool, pg_family):
    page = parent.get("/settings/billing")
    assert page.status_code == 200
    assert b"$39 / year" in page.data and b"$6 / month" in page.data
    assert not service.client.customers
    assert not state(pg_pool, pg_family)["stripe_customer_id"]
    assert page.headers["Cache-Control"] == "no-store"


def test_checkout_server_owns_price_customer_and_redirects(parent, service, pg_pool, pg_family):
    result = parent.post("/settings/billing/checkout", data={
        "interval": "year", "price": "price_attacker", "customer": "cus_attacker",
        "family_id": "somebody-else", "return_url": "https://example.org/steal",
    })
    assert result.status_code == 303
    params = service.client.v1.checkout.sessions.create.call_args.args[0]
    assert params["customer"] == "cus_" + str(pg_family)
    assert params["line_items"] == [{"price": service.yearly_price, "quantity": 1}]
    assert params["success_url"] == "https://app.example.com/settings/billing?checkout=returned"
    assert params["subscription_data"] == {"metadata": {"family_id": str(pg_family)}}
    assert params["automatic_tax"] == {"enabled": False}
    assert params["payment_method_types"] == ["card"]
    assert state(pg_pool, pg_family)["status"] == "trialing"
    assert b"Payment confirmation" in parent.get("/settings/billing?checkout=returned").data
    assert state(pg_pool, pg_family)["status"] == "trialing"


def test_parallel_checkout_reuses_one_session(service, pg_pool, pg_family):
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: start(service, pg_pool, pg_family), range(2)))
    assert results[0] == results[1]
    assert len(service.client.sessions) == len(service.client.customers) == 1


def test_timeout_after_stripe_accepts_reuses_exact_request(service, pg_pool, pg_family):
    import stripe
    remote = service.client.checkout
    def timeout(params, options):
        remote(params, options)
        raise stripe.APIConnectionError("private billing details must not be exposed")
    service.client.v1.checkout.sessions.create.side_effect = timeout
    with pytest.raises(billing.BillingError, match="temporarily unavailable"):
        start(service, pg_pool, pg_family)
    assert len(service.client.sessions) == 1
    service.client.v1.checkout.sessions.create.side_effect = remote
    service.checkout(pg_pool, pg_family, "month")  # The saved annual request wins.
    assert len(service.client.sessions) == 1
    assert service.client.v1.checkout.sessions.create.call_args.args[0]["line_items"][0]["price"] == service.yearly_price


def test_expired_checkout_gets_new_attempt(service, pg_pool, pg_family):
    original = start(service, pg_pool, pg_family)
    next(iter(service.client.sessions.values()))["status"] = "expired"
    assert service.checkout(pg_pool, pg_family, "month") != original


@pytest.mark.parametrize("status", ["active", "past_due", "unpaid", "incomplete"])
def test_existing_subscription_prevents_second_charge(service, pg_pool, pg_family, status):
    start(service, pg_pool, pg_family)
    subscription(service, pg_family, status)
    with pytest.raises(billing.BillingError, match="already exists"):
        start(service, pg_pool, pg_family)
    assert len(service.client.sessions) == 1


def test_canceled_subscription_can_restart(service, pg_pool, pg_family):
    original = start(service, pg_pool, pg_family)
    next(iter(service.client.sessions.values()))["status"] = "complete"
    subscription(service, pg_family, "canceled", ended_at=int(time.time()))
    assert start(service, pg_pool, pg_family) != original


def test_complete_trial_paid_cancel_and_reactivate(parent, service, pg_pool, pg_family):
    start(service, pg_pool, pg_family)
    sql(pg_pool, "UPDATE families SET status = 'lapsed' WHERE id = %s", (pg_family,))
    remote = subscription(service, pg_family)
    assert webhook(parent, service, pg_family).status_code == 204
    assert state(pg_pool, pg_family)["status"] == "active"
    assert not lifecycle.access_for(pg_pool, pg_family).ended
    remote["cancel_at_period_end"] = True
    assert webhook(parent, service, pg_family, "evt_cancel", "customer.subscription.updated").status_code == 204
    assert not lifecycle.access_for(pg_pool, pg_family).ended
    assert state(pg_pool, pg_family)["subscription_cancel_at"]
    remote.update(status="canceled", ended_at=int(time.time()))
    assert webhook(parent, service, pg_family, "evt_ended", "customer.subscription.deleted").status_code == 204
    assert lifecycle.access_for(pg_pool, pg_family).ended
    subscription(service, pg_family, id="sub_restarted")
    assert webhook(parent, service, pg_family, "evt_reactivated").status_code == 204
    assert state(pg_pool, pg_family)["lapsed_at"] is None


def test_duplicate_and_out_of_order_events_use_current_subscription(parent, service, pg_pool, pg_family):
    start(service, pg_pool, pg_family)
    old = subscription(service, pg_family, "canceled", ended_at=int(time.time()))
    current = subscription(service, pg_family, id="sub_current", created=int(time.time()) + 1)
    service.client.subscriptions = [old, current]
    for identifier in ("evt_new", "evt_new", "evt_old"):
        assert webhook(parent, service, pg_family, identifier, "customer.subscription.deleted").status_code == 204
    row = state(pg_pool, pg_family)
    assert row["status"] == "active" and row["stripe_subscription_id"] == "sub_current"
    assert len(sql(pg_pool, "SELECT event_id FROM stripe_events WHERE family_id = %s", (pg_family,))) == 2
    assert not sql(pg_pool, "SELECT kind FROM billing_notifications WHERE family_id = %s", (pg_family,))


def test_webhook_failure_rolls_back_dedup_and_retries(parent, service, pg_pool, pg_family):
    import stripe
    start(service, pg_pool, pg_family)
    subscription(service, pg_family)
    listing = service.client.v1.subscriptions.list.side_effect
    service.client.v1.subscriptions.list.side_effect = stripe.APIConnectionError("private billing details")
    assert webhook(parent, service, pg_family).status_code == 503
    assert not sql(pg_pool, "SELECT event_id FROM stripe_events WHERE family_id = %s", (pg_family,))
    service.client.v1.subscriptions.list.side_effect = listing
    assert webhook(parent, service, pg_family).status_code == 204
    assert state(pg_pool, pg_family)["status"] == "active"


def test_webhook_requires_signature_correct_mode_and_size(parent, service, pg_pool, pg_family):
    start(service, pg_pool, pg_family)
    subscription(service, pg_family)
    plain = FlaskClient(parent.application, parent.application.response_class)
    assert plain.post("/stripe/webhook", data=b"{}").status_code == 400
    assert webhook(plain, service, pg_family, livemode=True).status_code == 400
    assert webhook(plain, service, pg_family, account="acct_other").status_code == 400
    assert plain.post("/stripe/webhook", data=b" " * (256 * 1024 + 1)).status_code == 413
    assert state(pg_pool, pg_family)["status"] == "trialing"
    assert webhook(plain, service, pg_family).status_code == 204  # No session or CSRF needed here alone.


@pytest.mark.parametrize("path", ["checkout", "portal", "sync"])
def test_payment_actions_require_session_and_csrf(parent, service, pg_pool, pg_family, path):
    plain = FlaskClient(parent.application, parent.application.response_class)
    assert plain.post("/settings/billing/" + path).status_code == 400
    anonymous = client_for(parent.application)
    assert anonymous.post("/settings/billing/" + path).location.endswith("/login")
    assert anonymous.get("/settings/billing").location.endswith("/login")
    assert not service.client.customers


def test_portal_customer_comes_only_from_session(parent, service, pg_pool, pg_family):
    start(service, pg_pool, pg_family)
    result = parent.post("/settings/billing/portal", data={"customer": "cus_someone_else"})
    assert result.status_code == 303
    assert service.client.v1.billing_portal.sessions.create.call_args.args[0] == {
        "customer": "cus_" + str(pg_family), "configuration": "bpc_example",
        "return_url": "https://app.example.com/settings/billing",
    }


def test_failed_payment_grace_is_not_extended_by_duplicate_events(parent, service, pg_pool, pg_family):
    start(service, pg_pool, pg_family)
    now = int(time.time())
    remote = subscription(service, pg_family, "past_due", latest_invoice={"id": "in_unpaid", "created": now})
    assert webhook(parent, service, pg_family).status_code == 204
    assert not lifecycle.access_for(pg_pool, pg_family).ended
    deadline = state(pg_pool, pg_family)["billing_access_until"]
    assert deadline == billing.timestamp(now) + timedelta(days=7)
    assert webhook(parent, service, pg_family, "evt_retry", "invoice.payment_failed").status_code == 204
    assert state(pg_pool, pg_family)["billing_access_until"] == deadline
    remote["latest_invoice"]["created"] = now - 8 * 86400
    assert webhook(parent, service, pg_family, "evt_late").status_code == 204
    assert lifecycle.access_for(pg_pool, pg_family).ended
    remote["status"] = "active"
    assert webhook(parent, service, pg_family, "evt_recovered").status_code == 204
    assert not lifecycle.access_for(pg_pool, pg_family).ended


def test_deadline_enforced_without_webhook_or_worker(service, pg_pool, pg_family):
    from worker import family_ids
    sql(pg_pool, """UPDATE families SET status = 'active',
        billing_access_until = now() - interval '1 day' WHERE id = %s""", (pg_family,))
    before = lifecycle.access_for(pg_pool, pg_family)
    assert before.ended and pg_family not in family_ids(pg_pool)
    lifecycle.expire_trials(pg_pool)
    assert lifecycle.access_for(pg_pool, pg_family).lapsed_at == before.lapsed_at


def test_delete_stops_stripe_before_erasing_family(parent, service, pg_pool, pg_family):
    start(service, pg_pool, pg_family)
    subscription(service, pg_family)
    assert parent.post("/settings/account", data={"confirm": "parent@example.com"}).status_code == 302
    assert service.client.customers["cus_" + str(pg_family)]["deleted"]
    assert not sql(pg_pool, "SELECT id FROM families WHERE id = %s", (pg_family,))
    assert not sql(pg_pool, "SELECT family_id FROM billing_checkouts WHERE family_id = %s", (pg_family,))
    assert webhook(parent, service, pg_family).status_code == 204
    assert not sql(pg_pool, "SELECT id FROM families WHERE id = %s", (pg_family,))


def test_delete_failure_keeps_account_and_can_retry(parent, service, pg_pool, pg_family):
    import stripe
    start(service, pg_pool, pg_family)
    service.client.v1.customers.delete.side_effect = stripe.APIConnectionError("private billing details")
    result = parent.post("/settings/account", data={"confirm": "parent@example.com"}, follow_redirects=True)
    assert b"account has been kept" in result.data
    assert b"private billing details" not in result.data
    assert state(pg_pool, pg_family)
    service.client.customers["cus_" + str(pg_family)]["deleted"] = True  # Remote success, lost response.
    assert accounts.delete_family(pg_pool, pg_family, billing=service)


def test_notifications_retry_dedup_and_recheck_relevance(parent, service, pg_pool, pg_family, monkeypatch):
    sql(pg_pool, "UPDATE families SET trial_ends_at = now() + interval '2 days' WHERE id = %s", (pg_family,))
    sender = Mock(side_effect=mail.MailError("offline"))
    monkeypatch.setattr(mail, "send", sender)
    billing.housekeeping(pg_pool, service)
    assert sender.call_count == 1
    billing.housekeeping(pg_pool, service)
    assert sender.call_count == 1  # Backoff, no duplicated queue entry.
    sql(pg_pool, "UPDATE billing_notifications SET retry_at = now() WHERE family_id = %s", (pg_family,))
    sender.side_effect = None
    billing.housekeeping(pg_pool, service)
    assert sender.call_count == 2
    assert sender.call_args.args[0] == "parent@example.com"
    assert "https://app.example.com/settings/billing" in sender.call_args.args[2]
    billing.housekeeping(pg_pool, service)
    assert sender.call_count == 2
    start(service, pg_pool, pg_family)
    remote = subscription(service, pg_family, "past_due")
    webhook(parent, service, pg_family)
    remote["status"] = "active"
    webhook(parent, service, pg_family, "evt_recovery")
    billing.deliver_notifications(pg_pool, service.origin)
    assert sender.call_count == 2  # Recovery made the unsent failure mail stale.


@pytest.mark.parametrize("kind", ["payment_failed", "cancellation_scheduled", "subscription_ended"])
def test_required_subscription_notifications(parent, service, pg_pool, pg_family, monkeypatch, kind):
    start(service, pg_pool, pg_family)
    changes = {"status": "past_due"} if kind == "payment_failed" else (
        {"cancel_at_period_end": True} if kind == "cancellation_scheduled" else {"status": "canceled"})
    subscription(service, pg_family, **changes)
    webhook(parent, service, pg_family)
    sender = Mock()
    monkeypatch.setattr(mail, "send", sender)
    billing.deliver_notifications(pg_pool, service.origin)
    assert sender.call_count == 1
    webhook(parent, service, pg_family, "evt_duplicate_object")
    billing.deliver_notifications(pg_pool, service.origin)
    assert sender.call_count == 1


def test_missing_configuration_disables_checkout_but_not_account(parent, service, pg_pool, pg_family):
    service.automatic_tax = None  # Tax treatment must be an explicit operator choice.
    page = parent.get("/settings/billing")
    assert page.status_code == 200 and b"not available yet" in page.data
    result = parent.post("/settings/billing/checkout", data={"interval": "year"}, follow_redirects=True)
    assert b"not available yet" in result.data
    assert not service.client.customers
    assert parent.get("/settings/account/export").status_code == 200


def test_portal_must_support_cancellation_before_customer_created(service, pg_pool, pg_family):
    portal = service.client.v1.billing_portal.configurations.retrieve.return_value
    portal["features"]["subscription_cancel"]["enabled"] = False
    with pytest.raises(billing.BillingError, match="being set up"):
        start(service, pg_pool, pg_family)
    assert not service.client.customers


def test_portal_products_are_only_returned_when_expanded(service):
    retrieve = service.client.v1.billing_portal.configurations.retrieve
    configuration = retrieve.return_value.to_dict()

    def response(configuration_id, params=None):
        result = copy.deepcopy(configuration)
        if "features.subscription_update.products" not in (params or {}).get("expand", []):
            result["features"]["subscription_update"].pop("products")
        return sdk(result)

    retrieve.side_effect = response
    service.check_portal(service.prices())


def test_portal_with_no_update_products_is_unavailable(service):
    portal = service.client.v1.billing_portal.configurations.retrieve.return_value
    portal["features"]["subscription_update"]["products"] = None
    with pytest.raises(billing.BillingError, match="being set up"):
        service.check_portal(service.prices())


def test_billing_migration_preserves_existing_trials_and_paid_accounts(pg_pool):
    from dinkydash import db
    with pg_pool.connection() as conn, conn.transaction(force_rollback=True), conn.cursor() as cur:
        cur.execute("CREATE SCHEMA billing_migration_test")
        cur.execute("SET LOCAL search_path TO billing_migration_test, public")
        upgrade = db.MIGRATIONS_DIR / "006_billing.sql"
        for path in db.migrations():
            if path == upgrade:
                break
            cur.execute(path.read_text())
        cur.execute("""INSERT INTO families (screen_token, status, stripe_customer_id)
                       VALUES ('legacy-trial', 'trialing', NULL),
                              ('legacy-paid', 'active', 'cus_legacy_example'),
                              ('legacy-ended', 'lapsed', NULL)""")
        cur.execute("SELECT id, status, trial_ends_at, stripe_customer_id, lapsed_at FROM families ORDER BY id")
        original = cur.fetchall()
        cur.execute(upgrade.read_text())
        cur.execute("SELECT id, status, trial_ends_at, stripe_customer_id, lapsed_at FROM families ORDER BY id")
        assert cur.fetchall() == original
        cur.execute("SELECT billing_access_until, subscription_cancel_at FROM families")
        assert cur.fetchall() == [(None, None)] * 3


def test_automatic_tax_requires_active_setup(service, pg_pool, pg_family):
    service.automatic_tax = True
    service.client.v1.tax.settings.retrieve.return_value = sdk({"status": "pending"})
    with pytest.raises(billing.BillingError, match="tax setup"):
        start(service, pg_pool, pg_family)
    assert not service.client.customers
    service.client.v1.tax.settings.retrieve.return_value = sdk({"status": "active"})
    start(service, pg_pool, pg_family)
    assert service.client.v1.checkout.sessions.create.call_args.args[0]["automatic_tax"] == {"enabled": True}


@pytest.mark.parametrize("changes", [
    {"currency": "eur"}, {"unit_amount": None}, {"active": False},
    {"tax_behavior": "unspecified"}, {"recurring": {"interval": "week"}},
])
def test_unsupported_prices_are_not_offered(service, changes):
    def changed_price(pid):
        price = service.client.price(pid).to_dict()
        price.update(changes)
        return sdk(price)
    service.client.v1.prices.retrieve.side_effect = changed_price
    with pytest.raises(billing.BillingError, match="pricing is being updated"):
        service.prices()


def test_real_sdk_serializes_checkout_and_normalizes_resources(service):
    import stripe
    from urllib.parse import parse_qs
    class Transport(stripe.HTTPClient):
        name = "test"
        def request(self, method, url, headers, post_data=None, **kwargs):
            assert method == "post" and url == "https://api.stripe.com/v1/checkout/sessions"
            assert headers["Stripe-Version"] == stripe.api_version
            assert headers["Idempotency-Key"] == "saved-attempt"
            data = parse_qs(post_data)
            assert data["automatic_tax[enabled]"] == ["true"]
            assert data["line_items[0][price]"] == ["price_year_example"]
            return json.dumps({"id": "cs_example", "object": "checkout.session",
                               "status": "open", "url": "https://checkout.stripe.com/example"}), 200, {}
    service._client = stripe.StripeClient("sk_test_example", http_client=Transport(), max_network_retries=0)
    session = service.call(service.client.v1.checkout.sessions.create, {
        "mode": "subscription", "automatic_tax": {"enabled": True},
        "line_items": [{"price": "price_year_example", "quantity": 1}],
    }, options={"idempotency_key": "saved-attempt"})
    assert session.get("status") == "open"


def test_old_or_modified_signatures_fail_before_database_access(service):
    import stripe
    raw = b'{"id":"evt_example","object":"event","type":"invoice.paid"}'
    stamp = str(int(time.time()) - 600)
    digest = hmac.new(service.webhook_secret.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    with pytest.raises(stripe.SignatureVerificationError):
        service.event(None, raw, f"t={stamp},v1={digest}")
    with pytest.raises(stripe.SignatureVerificationError):
        service.event(None, raw + b" ", f"t={stamp},v1={digest}")


def test_parallel_deliveries_only_apply_one_event(parent, service, pg_pool, pg_family):
    start(service, pg_pool, pg_family)
    subscription(service, pg_family, "past_due")
    service.client.v1.subscriptions.list.reset_mock()
    def deliver(_):
        return webhook(parent.application.test_client(), service, pg_family).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(deliver, range(2))) == [204, 204]
    assert service.client.v1.subscriptions.list.call_count == 1
    assert len(sql(pg_pool, "SELECT notice_key FROM billing_notifications WHERE family_id = %s", (pg_family,))) == 1


def test_cancellation_deadline_precedes_payment_grace(parent, service, pg_pool, pg_family):
    start(service, pg_pool, pg_family)
    end = int(time.time()) + 86400
    subscription(service, pg_family, "past_due", cancel_at=end)
    webhook(parent, service, pg_family)
    row = state(pg_pool, pg_family)
    assert row["billing_access_until"] == row["subscription_cancel_at"] == billing.timestamp(end)


def test_worker_recovers_missing_webhook_and_export_excludes_checkout_credentials(parent, service, pg_pool, pg_family, monkeypatch):
    monkeypatch.setattr(mail, "send", Mock())
    start(service, pg_pool, pg_family)
    subscription(service, pg_family)
    sql(pg_pool, "UPDATE families SET billing_synced_at = NULL WHERE id = %s", (pg_family,))
    billing.housekeeping(pg_pool, service)
    assert state(pg_pool, pg_family)["status"] == "active"
    export = parent.get("/settings/account/export").get_json()
    assert export["family"]["stripe_subscription_id"] == "sub_example"
    assert "checkout.stripe.com" not in json.dumps(export)
    assert "cs_example" not in json.dumps(export)


def test_single_mode_never_imports_stripe(monkeypatch, tmp_path):
    import builtins
    from dinkydash.store import FileStore
    original = builtins.__import__
    def refuse(name, *args, **kwargs):
        if name == "stripe" or name.startswith("stripe."):
            raise AssertionError("A self-hoster imported Stripe")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", refuse)
    monkeypatch.setenv("DINKYDASH_MODE", "single")
    app = create_app(FileStore(tmp_path / "config.yaml"))
    client = app.test_client()
    assert client.get("/settings/billing").status_code == 404
    assert client.get("/stripe/webhook").status_code == 404
    assert all(rule.endpoint != "billing.webhook" for rule in app.url_map.iter_rules())
