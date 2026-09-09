"""Hosted subscriptions. Stripe owns payments; Postgres owns family access.

Only payment entry points import the SDK. Every account action takes a trusted
family id. Billing writes serialize on that family's row, including deletion;
bounded Stripe requests happen while holding it, so two Checkouts cannot race.
Webhook snapshots are notifications to read Stripe's current subscriptions, not
instructions to overwrite state with an old snapshot.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)
PAYMENT_GRACE = timedelta(days=7)
EVENTS = frozenset({
    "checkout.session.completed",
    "customer.subscription.created", "customer.subscription.updated",
    "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed",
    "invoice.payment_action_required",
})
TERMINAL = {"canceled", "incomplete_expired"}


class BillingError(Exception):
    """A safe, parent-facing error; never Stripe's response or billing details."""


@dataclass
class Billing:
    secret_key: str = field(default="", repr=False)
    webhook_secret: str = field(default="", repr=False)
    monthly_price: str = ""
    yearly_price: str = ""
    portal_configuration: str = ""
    automatic_tax: bool | None = None
    origin: str = ""
    _client: object = field(default=None, repr=False)

    @classmethod
    def from_env(cls):
        tax = os.environ.get("STRIPE_AUTOMATIC_TAX", "").lower()
        host = os.environ.get("DINKYDASH_APP_HOST", "").strip()
        return cls(
            secret_key=os.environ.get("STRIPE_SECRET_KEY", ""),
            webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
            monthly_price=os.environ.get("STRIPE_MONTHLY_PRICE_ID", ""),
            yearly_price=os.environ.get("STRIPE_YEARLY_PRICE_ID", ""),
            portal_configuration=os.environ.get("STRIPE_PORTAL_CONFIGURATION_ID", ""),
            automatic_tax={"true": True, "false": False}.get(tax),
            origin=f"https://{host}" if host else "",
        )

    @property
    def ready(self):
        return bool(self.secret_key and self.webhook_secret and self.monthly_price
                    and self.yearly_price and self.portal_configuration
                    and self.automatic_tax is not None and self.origin)

    @property
    def client(self):
        if not self.secret_key:
            raise BillingError("Billing is temporarily unavailable. Please try again later.")
        if self._client is None:
            import stripe
            self._client = stripe.StripeClient(
                self.secret_key, max_network_retries=1,
                http_client=stripe.RequestsClient(timeout=8),
            )
        return self._client

    def call(self, method, *args, **kwargs):
        import stripe
        try:
            return method(*args, **kwargs).to_dict()
        except stripe.StripeError as exc:
            log.warning("Stripe request failed (%s).", type(exc).__name__)
            raise BillingError("Billing is temporarily unavailable. Please try again later.") from None

    def prices(self):
        if not self.ready:
            raise BillingError("Subscriptions are not available yet. Your account stays accessible.")
        prices = {}
        for interval, price_id in (("month", self.monthly_price), ("year", self.yearly_price)):
            price = self.call(self.client.v1.prices.retrieve, price_id)
            recurring = price.get("recurring") or {}
            if (not price.get("active") or price.get("currency") != "usd"
                    or not isinstance(price.get("unit_amount"), int)
                    or price["unit_amount"] <= 0 or recurring.get("interval") != interval
                    or recurring.get("interval_count") != 1
                    or recurring.get("usage_type") != "licensed"
                    or price.get("tax_behavior") not in {"inclusive", "exclusive"}):
                raise BillingError("Subscription pricing is being updated. Please try again later.")
            prices[interval] = {
                "id": price_id, "amount": f"${price['unit_amount'] / 100:g}",
                "tax_included": price["tax_behavior"] == "inclusive",
                "product": price["product"],
            }
        if prices["month"]["product"] != prices["year"]["product"]:
            raise BillingError("Subscription pricing is being updated. Please try again later.")
        return prices

    def checkout(self, pool, family_id, interval):
        if interval not in {"month", "year"}:
            raise BillingError("Choose monthly or yearly billing.")
        prices = self.prices()
        self.check_portal(prices)
        if self.automatic_tax:
            settings = self.call(self.client.v1.tax.settings.retrieve)
            if settings["status"] != "active":
                raise BillingError("Subscription tax setup is being completed. Please try again later.")
        # Commit the customer separately. Checkout cannot start until its owner
        # is durable locally; a retry of customer creation uses fixed parameters.
        with pool.connection() as conn, conn.cursor() as cur:
            row = family(cur, family_id, lock=True)
            if not row["stripe_customer_id"]:
                customer = self.call(
                    self.client.v1.customers.create,
                    {"metadata": {"family_id": str(family_id)}},
                    options={"idempotency_key": f"customer:{family_id}"},
                )
                cur.execute("UPDATE families SET stripe_customer_id = %s WHERE id = %s",
                            (customer["id"], family_id))

        with pool.connection() as conn, conn.cursor() as cur:
            row = family(cur, family_id, lock=True)
            subscriptions = self.subscriptions(row)
            self.apply(cur, row, subscriptions)
            if any(s["status"] not in TERMINAL for s in subscriptions):
                raise BillingError("A subscription already exists. Open Manage subscription to continue.")
            cur.execute("SELECT attempt, params, session_id FROM billing_checkouts WHERE family_id = %s",
                        (family_id,))
            previous = cur.fetchone()
            expired = False
            if previous and previous[2]:
                session = self.call(self.client.v1.checkout.sessions.retrieve, previous[2])
                if session["status"] == "open":
                    return session["url"]
                if session["status"] == "complete":
                    if not subscriptions:
                        raise BillingError("Your payment is being confirmed. Please check back shortly.")
                    expired = True  # A completed, now canceled subscription can restart.
                expired = expired or session["status"] == "expired"
            if expired or not previous or previous[1]["expires_at"] <= row["now"].timestamp():
                params = {
                    "mode": "subscription", "customer": row["stripe_customer_id"],
                    # Delayed bank payments can remain 'active' after failure.
                    # Keep the MVP's subscription-status access rule to cards.
                    "payment_method_types": ["card"],
                    "line_items": [{"price": prices[interval]["id"], "quantity": 1}],
                    "subscription_data": {"metadata": {"family_id": str(family_id)}},
                    "success_url": self.origin + "/settings/billing?checkout=returned",
                    "cancel_url": self.origin + "/settings/billing",
                    "automatic_tax": {"enabled": self.automatic_tax},
                    "billing_address_collection": "required",
                    "customer_update": {"address": "auto", "name": "auto"},
                    "allow_promotion_codes": True,
                    "expires_at": int((row["now"] + timedelta(hours=1)).timestamp()),
                }
                cur.execute(
                    """INSERT INTO billing_checkouts (family_id, params) VALUES (%s, %s::jsonb)
                       ON CONFLICT (family_id) DO UPDATE
                       SET attempt = gen_random_uuid(), params = EXCLUDED.params, session_id = NULL""",
                    (family_id, json.dumps(params)),
                )
        # The attempt and exact parameters survive an API timeout or DB rollback.
        with pool.connection() as conn, conn.cursor() as cur:
            family(cur, family_id, lock=True)
            cur.execute("SELECT attempt, params FROM billing_checkouts WHERE family_id = %s", (family_id,))
            attempt, params = cur.fetchone()
            session = self.call(self.client.v1.checkout.sessions.create, params,
                                options={"idempotency_key": f"checkout:{attempt}"})
            cur.execute("UPDATE billing_checkouts SET session_id = %s WHERE family_id = %s",
                        (session["id"], family_id))
            return session["url"]

    def check_portal(self, prices):
        """Do not accept a first payment into a portal that cannot cancel it."""
        configuration = self.call(self.client.v1.billing_portal.configurations.retrieve,
                                  self.portal_configuration,
                                  {"expand": ["features.subscription_update.products"]})
        features = configuration["features"]
        cancel = features["subscription_cancel"]
        update = features["subscription_update"]
        products = update.get("products") or []
        price_ids = {p["id"] for p in prices.values()}
        changeable = any(p["product"] == prices["month"]["product"]
                         and price_ids.issubset(p["prices"]) for p in products)
        if not (configuration["active"] and cancel["enabled"] and cancel["mode"] == "at_period_end"
                and features["invoice_history"]["enabled"]
                and features["payment_method_update"]["enabled"]
                and update["enabled"] and "price" in update["default_allowed_updates"] and changeable):
            raise BillingError("Subscription management is being set up. Please try again later.")

    def portal(self, pool, family_id):
        if not self.portal_configuration or not self.origin:
            raise BillingError("Subscription management is temporarily unavailable.")
        with pool.connection() as conn, conn.cursor() as cur:
            row = family(cur, family_id, lock=True)
            if not row["stripe_customer_id"]:
                raise BillingError("Choose a subscription first.")
            session = self.call(self.client.v1.billing_portal.sessions.create, {
                "customer": row["stripe_customer_id"],
                "configuration": self.portal_configuration,
                "return_url": self.origin + "/settings/billing",
            })
            return session["url"]

    def subscriptions(self, row):
        if not row["stripe_customer_id"]:
            return []
        result = self.call(self.client.v1.subscriptions.list, {
            "customer": row["stripe_customer_id"], "status": "all", "limit": 100,
            "expand": ["data.latest_invoice"],
        })
        # One plan per family; refusing an unexpected overflow is safer than
        # overlooking a payable subscription and starting another one.
        if result["has_more"]:
            raise BillingError("Please contact support to check your subscription.")
        return list(result["data"])

    def sync(self, pool, family_id):
        with pool.connection() as conn, conn.cursor() as cur:
            row = family(cur, family_id, lock=True)
            self.apply(cur, row, self.subscriptions(row))

    def event(self, pool, raw, signature):
        import stripe
        if not self.webhook_secret or not self.secret_key:
            raise BillingError("Billing is not configured.")
        event = stripe.Webhook.construct_event(raw, signature, self.webhook_secret).to_dict()
        live = self.secret_key.startswith(("sk_live_", "rk_live_"))
        if event.get("livemode") is not live or event.get("account"):
            raise ValueError("Unexpected Stripe mode or connected account.")
        if event["type"] not in EVENTS:
            return
        customer_id = event["data"]["object"].get("customer")
        if not isinstance(customer_id, str):
            return
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM families WHERE stripe_customer_id = %s FOR UPDATE", (customer_id,))
            found = cur.fetchone()
            if not found:  # Deleted accounts and other products never create a family.
                return
            family_id = found[0]
            cur.execute(
                """INSERT INTO stripe_events (event_id, family_id) VALUES (%s, %s)
                   ON CONFLICT DO NOTHING RETURNING event_id""", (event["id"], family_id),
            )
            if not cur.fetchone():
                return
            row = family(cur, family_id)
            self.apply(cur, row, self.subscriptions(row))

    def apply(self, cur, row, subscriptions):
        """Apply current remote state under the family lock, never event order."""
        cur.execute("UPDATE families SET billing_synced_at = now() WHERE id = %s", (row["id"],))
        owned = [s for s in subscriptions if s.get("metadata", {}).get("family_id") == str(row["id"])]
        if not owned:
            return
        # A canceled previous subscription cannot overwrite its replacement.
        subscription = max(owned, key=lambda s: (s["status"] not in TERMINAL, s["created"]))
        remote = subscription["status"]
        items = subscription["items"]["data"]
        period_end = timestamp(max((i["current_period_end"] for i in items), default=0))
        invoice = subscription.get("latest_invoice") or {}
        canceling = bool(subscription.get("cancel_at_period_end") or subscription.get("cancel_at"))
        cancel_at = (timestamp(subscription.get("cancel_at")) or period_end) if canceling else None
        deadline = None
        lapse = row["lapsed_at"]
        if remote in {"active", "trialing"}:
            status = "active"
            if canceling:
                deadline = cancel_at
        elif remote == "past_due":
            # Invoice creation is stable across retries; an old failure event
            # or another retry must not restart the seven-day grace period.
            status = "past_due"
            deadline = timestamp(invoice["created"]) + PAYMENT_GRACE
            if cancel_at:
                deadline = min(deadline, cancel_at)
        elif remote in {"incomplete", "incomplete_expired"}:
            status = "trialing" if row["trial_ends_at"] and row["trial_ends_at"] > row["now"] else "lapsed"
            lapse = lapse or row["trial_ends_at"] or row["now"]
        else:  # canceled, unpaid or paused: no new paid work.
            status = "lapsed"
            lapse = lapse or timestamp(subscription.get("ended_at")) or row["now"]
        if deadline and deadline <= row["now"]:
            status, lapse = "lapsed", deadline
        cur.execute(
            """UPDATE families SET status = %s, lapsed_at = %s, stripe_subscription_id = %s,
                   subscription_status = %s, subscription_period_end = %s,
                   subscription_cancel_at = %s, billing_access_until = %s,
                   billing_synced_at = now(), updated_at = now()
               WHERE id = %s""",
            (status, lapse if status == "lapsed" else None, subscription["id"], remote,
             period_end, cancel_at, deadline, row["id"]),
        )
        if remote in {"past_due", "unpaid"} and invoice.get("id"):
            notice(cur, row["id"], "payment:" + invoice["id"], "payment_failed")
        if canceling and status != "lapsed":
            notice(cur, row["id"], f"cancel:{subscription['id']}:{cancel_at.isoformat()}",
                   "cancellation_scheduled")
        if status == "lapsed" and remote not in {"incomplete", "incomplete_expired"}:
            notice(cur, row["id"], f"ended:{subscription['id']}:{lapse.isoformat()}", "subscription_ended")

    def delete_customer(self, cur, family_id):
        """Called inside account deletion's transaction, before removing its owner.

        Stripe customer deletion immediately cancels every subscription and is
        repeatable if the local commit fails. No local delete on a remote failure.
        """
        row = family(cur, family_id, lock=True)
        if row["stripe_customer_id"]:
            customer = self.call(self.client.v1.customers.retrieve, row["stripe_customer_id"])
            if not customer.get("deleted"):
                self.call(self.client.v1.customers.delete, row["stripe_customer_id"])


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc) if value else None


def family(cur, family_id, *, lock=False):
    cur.execute(
        """SELECT id, status, trial_ends_at, lapsed_at, stripe_customer_id,
                  stripe_subscription_id, subscription_status, subscription_period_end,
                  subscription_cancel_at, billing_access_until, now() AS now
           FROM families WHERE id = %s""" + (" FOR UPDATE" if lock else ""), (family_id,),
    )
    row = cur.fetchone()
    if row is None:
        from .pgstore import NoSuchFamily
        raise NoSuchFamily(f"No family {family_id}")
    return dict(zip((column.name for column in cur.description), row))


def notice(cur, family_id, key, kind):
    cur.execute(
        """INSERT INTO billing_notifications (family_id, notice_key, kind)
           VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""", (family_id, key, kind),
    )


def housekeeping(pool, billing):
    """Recover missed webhooks hourly, then deliver pending lifecycle mail.

    The existing worker supplies the schedule. At most twenty accounts per pass
    keeps payment-provider trouble from starving the board tick indefinitely.
    """
    if not billing.secret_key:
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id FROM families WHERE stripe_customer_id IS NOT NULL
               AND (billing_synced_at IS NULL OR billing_synced_at < now() - interval '1 hour')
               ORDER BY billing_synced_at NULLS FIRST LIMIT 20""",
        )
        ids = [r[0] for r in cur.fetchall()]
    for family_id in ids:
        try:
            billing.sync(pool, family_id)
        except BillingError:
            log.warning("Subscription reconciliation will retry next pass.")
            break  # An API outage should cost one bounded request, not twenty.
    if not billing.ready:
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO billing_notifications (family_id, notice_key, kind)
               SELECT id, 'trial-ending', 'trial_ending' FROM families
               WHERE status = 'trialing' AND trial_ends_at > now()
                 AND trial_ends_at <= now() + interval '3 days'
               ON CONFLICT DO NOTHING""",
        )
    deliver_notifications(pool, billing.origin)


def notification_text(kind, row):
    """Recheck relevance at send time: a recovered payment needs no warning."""
    if kind == "trial_ending" and row["status"] == "trialing" and row["trial_ends_at"] > row["now"]:
        return ("Your DinkyDash trial is ending",
                f"Your trial ends on {row['trial_ends_at']:%-d %B %Y}. Choose a subscription "
                "to keep your board updating. No payment has been scheduled.")
    if kind == "payment_failed" and row["subscription_status"] in {"past_due", "unpaid"}:
        return ("Your DinkyDash payment needs attention",
                "Your subscription payment could not be completed. Please update your payment "
                "method in Manage subscription. Board updates pause seven days after the "
                "unpaid invoice was created, or sooner if the subscription ends.")
    if kind == "cancellation_scheduled" and row["subscription_cancel_at"] and row["status"] != "lapsed":
        return ("Your DinkyDash cancellation is scheduled",
                f"Your subscription will end on {row['subscription_cancel_at']:%-d %B %Y}. "
                "You can undo cancellation in Manage subscription. Any unpaid invoices still need attention.")
    if kind == "subscription_ended" and row["status"] == "lapsed":
        return ("Your DinkyDash subscription has ended",
                "Board updates are paused. The last saved board remains on your screen for "
                "30 days. You can still sign in to restart, export your data or delete your account.")
    return None


def deliver_notifications(pool, origin):
    """At-least-once mail delivery, retried after failures without storing bodies.

    A crash after SendGrid accepts a message but before commit can repeat it;
    ordinary webhook retries and concurrent workers cannot enqueue it twice.
    """
    from . import mail
    for _ in range(20):
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT n.family_id, n.notice_key, n.kind,
                          (SELECT email FROM users WHERE family_id = n.family_id ORDER BY id LIMIT 1)
                   FROM billing_notifications n
                   WHERE n.sent_at IS NULL AND n.retry_at <= now()
                   ORDER BY n.created_at FOR UPDATE OF n SKIP LOCKED LIMIT 1""",
            )
            pending = cur.fetchone()
            if not pending:
                return
            family_id, key, kind, address = pending
            message = notification_text(kind, family(cur, family_id))
            try:
                if message and address:
                    subject, body = message
                    mail.send(address, subject, body + "\n\n" + origin + "/settings/billing")
            except mail.MailError:
                log.warning("A billing notification could not be sent; retrying later.")
                cur.execute(
                    """UPDATE billing_notifications SET retry_at = now() + interval '15 minutes'
                       WHERE family_id = %s AND notice_key = %s""", (family_id, key),
                )
            else:
                cur.execute(
                    """UPDATE billing_notifications SET sent_at = now()
                       WHERE family_id = %s AND notice_key = %s""", (family_id, key),
                )
