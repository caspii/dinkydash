"""The Google Ads conversion decisions, with no Flask and no network.

`dinkydash/ads.py` is deliberately plain: an unset `GOOGLE_ADS_ID` has to mean
every tag renders nothing, and a conversion's value and currency have to come
from the live plan `Billing.prices()` already fetched, never a number written
here.
"""

import pytest

from dinkydash import ads

PRICES = {
    "month": {"id": "price_month_example", "unit_amount": 600, "currency": "usd"},
    "year": {"id": "price_year_example", "unit_amount": 3900, "currency": "usd"},
}


class TestTheBaseTag:
    def test_unset_is_off(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
        assert ads.ads_id() == ""
        assert not ads.enabled()

    def test_a_blank_value_is_off(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_ADS_ID", "   ")
        assert ads.ads_id() == ""
        assert not ads.enabled()

    def test_a_real_one_is_stripped_and_kept(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_ADS_ID", "  AW-123456789  ")
        assert ads.ads_id() == "AW-123456789"
        assert ads.enabled()

    def test_consent_regions_cover_the_eea_plus_gb_and_ch(self):
        for code in ("GB", "CH", "DE", "FR", "IS", "LI", "NO"):
            assert code in ads.CONSENT_REGIONS
        # Not a member of either, and not accidentally swept in.
        assert "US" not in ads.CONSENT_REGIONS


class TestSignupConversion:
    def test_unset_id_renders_nothing(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
        monkeypatch.setenv("GOOGLE_ADS_SIGNUP_LABEL", "signupLabel")
        assert ads.signup_conversion() is None

    def test_unset_label_renders_nothing(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_ADS_ID", "AW-123456789")
        monkeypatch.delenv("GOOGLE_ADS_SIGNUP_LABEL", raising=False)
        assert ads.signup_conversion() is None

    def test_both_set_sends_to_the_container_and_label(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_ADS_ID", "AW-123456789")
        monkeypatch.setenv("GOOGLE_ADS_SIGNUP_LABEL", "signupLabel")
        assert ads.signup_conversion() == {"send_to": "AW-123456789/signupLabel"}


class TestSubscriptionConversion:
    @pytest.fixture(autouse=True)
    def configured(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_ADS_ID", "AW-123456789")
        monkeypatch.setenv("GOOGLE_ADS_PAID_LABEL", "paidLabel")

    def test_value_and_currency_come_from_the_live_price_not_a_constant(self):
        result = ads.subscription_conversion(PRICES, "year", "sub_example")
        assert result == {
            "send_to": "AW-123456789/paidLabel",
            "value": 39.0,
            "currency": "USD",
            "transaction_id": "sub_example",
        }
        # The other interval's price must not leak into this result.
        monthly = ads.subscription_conversion(PRICES, "month", "sub_other")
        assert monthly["value"] == 6.0
        assert monthly["transaction_id"] == "sub_other"

    def test_repeat_calls_with_the_same_subscription_return_the_same_transaction_id(self):
        """Google Ads de-dupes a conversion on `transaction_id`, not on anything we track."""
        first = ads.subscription_conversion(PRICES, "year", "sub_example")
        second = ads.subscription_conversion(PRICES, "year", "sub_example")
        assert first == second
        assert first["transaction_id"] == "sub_example"

    def test_no_subscription_id_is_none(self):
        assert ads.subscription_conversion(PRICES, "year", None) is None
        assert ads.subscription_conversion(PRICES, "year", "") is None

    def test_unpriced_interval_is_none(self):
        assert ads.subscription_conversion(PRICES, "decade", "sub_example") is None
        assert ads.subscription_conversion({}, "year", "sub_example") is None
        assert ads.subscription_conversion(None, "year", "sub_example") is None

    def test_an_invalid_price_is_none(self):
        bad_amount = {"year": {"unit_amount": 0, "currency": "usd"}}
        no_currency = {"year": {"unit_amount": 3900, "currency": ""}}
        assert ads.subscription_conversion(bad_amount, "year", "sub_example") is None
        assert ads.subscription_conversion(no_currency, "year", "sub_example") is None

    def test_unset_env_renders_nothing_even_with_a_real_subscription(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
        assert ads.subscription_conversion(PRICES, "year", "sub_example") is None
        monkeypatch.setenv("GOOGLE_ADS_ID", "AW-123456789")
        monkeypatch.delenv("GOOGLE_ADS_PAID_LABEL", raising=False)
        assert ads.subscription_conversion(PRICES, "year", "sub_example") is None
