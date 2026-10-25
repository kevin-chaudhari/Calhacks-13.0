"""Vendor trust levels: verified, unverified, suspected fraud, each for a stated reason."""
from datetime import date

import pytest

from rally import trust

LISTED = {"mapsLink": "https://maps.google.com/?cid=1", "address": "Yosemite Village, CA", "rating": 4.8,
          "reviews": 412}
UNLISTED = {"mapsLink": None, "rating": None, "reviews": None}
FINE_PAGE = "Go Climb a Rock: $172 per person. Cancellation: full refund up to 48 hours before."


@pytest.mark.parametrize("sentence", [
    "We accept Visa, Mastercard, Venmo and Zelle.",
    "Gift cards available in our shop.",
    "Wire transfers accepted for corporate groups, or pay by card.",
    "Book online only.",
])
def test_ordinary_payment_wording_is_not_a_red_flag(sentence):
    assert trust.payment_red_flag(sentence) is None


@pytest.mark.parametrize("sentence", [
    "Payment by Zelle or wire transfer only.",
    "We only accept Bitcoin or USDT.",
    "Send your deposit through Western Union to confirm.",
    "Please pay the balance with Apple gift cards.",
])
def test_untraceable_payment_demands_are_red_flags(sentence):
    assert trust.payment_red_flag(f"Welcome! {sentence} See you soon.") == sentence


def test_domain_age_comes_from_the_registration_event():
    rdap = {"events": [{"eventAction": "last changed", "eventDate": "2026-01-01T00:00:00Z"},
                       {"eventAction": "registration", "eventDate": "2016-10-24T12:00:00Z"}]}
    assert trust.domain_age_days(rdap, date(2026, 10, 24)) == 3652
    assert trust.domain_age_days({"events": []}, date(2026, 10, 24)) is None


def test_well_reviewed_listed_business_is_verified():
    t = trust.assess(LISTED, FINE_PAGE, age_days=4000, ratio=1.05)
    assert t["level"] == "verified" and t["reasons"] == []


def test_unknown_facts_are_neither_good_nor_bad():
    assert trust.assess(LISTED, None, age_days=None, ratio=None)["level"] == "verified"


@pytest.mark.parametrize("vendor, age, ratio, reason", [
    (UNLISTED, 4000, 1.0, "no Google Maps listing"),
    ({**LISTED, "reviews": 6}, 4000, 1.0, "only 6 reviews"),
    ({**LISTED, "rating": 3.1}, 4000, 1.0, "rated 3.1★"),
    (LISTED, 200, 1.0, "website only 200 days old"),
    (LISTED, 4000, 0.4, "price only 40% of the market"),          # cheap, but a known business
])
def test_warnings_keep_a_vendor_unverified(vendor, age, ratio, reason):
    t = trust.assess(vendor, FINE_PAGE, age, ratio)
    assert t["level"] == "unverified" and reason in t["reasons"]


@pytest.mark.parametrize("vendor, page, age, ratio, reason", [
    (LISTED, "Pay by Zelle only.", 4000, 1.0, "asks to be paid in a way that can't be traced or refunded"),
    (UNLISTED, FINE_PAGE, 30, 1.0, "website only 30 days old and no map listing"),
    (UNLISTED, FINE_PAGE, 4000, 0.3, "price only 30% of the market from an unknown business"),
])
def test_hard_red_flags_mean_suspected_fraud(vendor, page, age, ratio, reason):
    t = trust.assess(vendor, page, age, ratio)
    assert t["level"] == "suspected_fraud" and reason in t["reasons"]


def test_the_payment_flag_keeps_its_evidence():
    t = trust.assess(LISTED, "Hi. Payment by Zelle or wire transfer only. Bye.", 4000, 1.0)
    pay = next(s for s in t["signals"] if s["kind"] == "payment")
    assert pay["evidence"] == "Payment by Zelle or wire transfer only."


def test_market_ratio_needs_two_other_vendors():
    v = {"tiers": [{"pricePerPerson": 60}]}
    others = [{"tiers": [{"pricePerPerson": p}]} for p in (150, 160, 172)]
    assert trust.market_ratio(v, others) == 60 / 160
    assert trust.market_ratio(v, others[:1]) is None
