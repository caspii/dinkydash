"""Signed-in payment actions and the one independently signed Stripe endpoint."""

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from dinkydash import ads
from dinkydash.billing import BillingError, family
from web.family import current_family_id
from web.session import guard

bp = Blueprint("billing", __name__)


@bp.before_request
def authenticate():
    if request.endpoint != "billing.webhook":
        return guard()


@bp.after_request
def private(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.errorhandler(BillingError)
def unavailable(exc):
    flash(str(exc), "error")
    return redirect(url_for("billing.home"))


@bp.get("/settings/billing")
def home():
    with current_app.config["POOL"].connection() as conn, conn.cursor() as cur:
        row = family(cur, current_family_id())
    prices, error = {}, None
    try:
        prices = current_app.config["BILLING"].prices()
    except BillingError as exc:
        error = str(exc)
    returned = request.args.get("checkout") == "returned"
    # Only on the page Checkout redirects back to, and only once a subscription
    # exists to attribute the payment to -- a webhook that has not landed yet
    # means nothing fires here; the next visit that finds one still reports it,
    # because `transaction_id` is what keeps a repeat from double-counting.
    ads_event = (ads.subscription_conversion(prices, row["subscription_interval"],
                                             row["stripe_subscription_id"])
                if returned else None)
    return render_template("settings/billing.html", account=row, prices=prices, error=error,
                           returned=returned, ads_event=ads_event)


@bp.post("/settings/billing/checkout")
def checkout():
    target = current_app.config["BILLING"].checkout(
        current_app.config["POOL"], current_family_id(), request.form.get("interval"),
    )
    return redirect(target, code=303)


@bp.post("/settings/billing/portal")
def portal():
    target = current_app.config["BILLING"].portal(current_app.config["POOL"], current_family_id())
    return redirect(target, code=303)


@bp.post("/settings/billing/sync")
def sync():
    current_app.config["BILLING"].sync(current_app.config["POOL"], current_family_id())
    return redirect(url_for("billing.home"))


@bp.post("/stripe/webhook")
def webhook():
    # A distinct endpoint exemption in check_csrf preserves the unparsed bytes.
    # Payment data is neither logged nor retained; the event id is enough.
    request.max_content_length = 256 * 1024
    import stripe
    try:
        current_app.config["BILLING"].event(
            current_app.config["POOL"], request.get_data(), request.headers.get("Stripe-Signature", ""),
        )
    except (ValueError, stripe.SignatureVerificationError):
        abort(400)
    except BillingError:
        return "Please retry", 503
    return "", 204
