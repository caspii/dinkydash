"""Google Ads conversion tags: env-driven switches, and what each one sends.

`GOOGLE_ADS_ID` (an "AW-..." container id) turns the base tag on, everywhere
it is included -- the marketing site and the app's signed-out pages, and the
one billing page that needs it to report a payment. Unset, nothing here
renders and nothing here fires, the same way `FATHOM_SITE_ID` works.

Consent Mode v2's region list is here too, because it is a fact about where
Google Ads applies the EU/UK/CH default rather than something a template
should know on its own.
"""

import os

# The regions Consent Mode v2 defaults to denied: the EEA (EU plus Iceland,
# Liechtenstein and Norway), the UK and Switzerland. Every other region gets
# the second, granting default.
CONSENT_REGIONS = (
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE", "IS", "LI", "NO", "GB", "CH",
)


def ads_id():
    """The public container id, or `""` when the base tag should render nothing."""
    return os.environ.get("GOOGLE_ADS_ID", "").strip()


def enabled():
    return bool(ads_id())


def signup_conversion():
    """What the one-shot post-signup page sends, or `None` when there is nothing to send.

    `GOOGLE_ADS_SIGNUP_LABEL` has to be set alongside the id -- a label with
    no id, or an id with no label, fires nothing rather than an incomplete
    `send_to`.
    """
    label = os.environ.get("GOOGLE_ADS_SIGNUP_LABEL", "").strip()
    if not enabled() or not label:
        return None
    return {"send_to": f"{ads_id()}/{label}"}


def subscription_conversion(prices, interval, subscription_id):
    """What the billing-success page sends for a first paid subscription.

    `value` and `currency` come from `prices[interval]` -- the live Stripe
    price `Billing.prices()` already fetched for this family's plan -- never
    a number written in this module. `transaction_id` is the Stripe
    subscription id, which is how Google Ads treats a conversion reported
    more than once for the same payment as one: firing this on every visit to
    the billing-success page is safe as long as the subscription id has not
    changed.

    `None` when ads tracking is off, the label is unset, there is no
    subscription yet to attribute a payment to, or the price is not one
    `Billing.prices()` would consider valid.
    """
    label = os.environ.get("GOOGLE_ADS_PAID_LABEL", "").strip()
    if not enabled() or not label or not subscription_id:
        return None
    price = (prices or {}).get(interval)
    if not price:
        return None
    amount, currency = price.get("unit_amount"), price.get("currency")
    if not isinstance(amount, int) or amount <= 0 or not currency:
        return None
    return {
        "send_to": f"{ads_id()}/{label}",
        "value": amount / 100,
        "currency": currency.upper(),
        "transaction_id": subscription_id,
    }
