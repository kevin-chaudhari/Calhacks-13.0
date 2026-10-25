"""Is a vendor found on the web a real business? Three levels from evidence the agent can check.

  verified         on Google Maps with a rating of 4+ from 20+ reviews, and no warning below
  unverified       anything in between: shown with its warnings, never paid before the vendor confirms
  suspected_fraud  a hard red flag: never contacted

Hard red flags:
  * the vendor's own page wants to be paid only by wire, crypto or a payment app, through
    Western Union or MoneyGram, or in gift cards (the sentence that says so is kept as evidence);
  * the website is under 90 days old and the business has no map listing;
  * its price is under half of what the other vendors charge, and it has no map listing or under 5 reviews.
Warnings (keep a vendor at unverified): no map listing, too few or poor reviews, a website under a
year old, a price under half the market. Unknown facts (a failed domain lookup) are neither.

This reduces risk; it can't prove a business is honest.
"""

from __future__ import annotations

import re
import statistics
from datetime import date, datetime

MIN_RATING, MIN_REVIEWS = 4.0, 20
NEW_SITE_DAYS, YOUNG_SITE_DAYS = 90, 365
TOO_CHEAP = 0.5

# Real shops accept Venmo and sell gift cards. Scams make untraceable payment the only option,
# use money-transfer services, or ask to be paid *with* gift cards.
_UNTRACEABLE = re.compile(r"\b(?:bitcoin|btc|crypto(?:currency)?|usdt|wire transfers?|zelle|cash ?app|venmo)\b", re.I)
_ONLY = re.compile(r"\bonly\b", re.I)
_TRANSFER_SERVICE = re.compile(r"\b(?:western union|moneygram)\b", re.I)
_ASKS_TO_PAY = re.compile(r"\b(?:pay|payment|deposit|send)\w*\b", re.I)
_PAID_IN_GIFT_CARDS = re.compile(r"\b(?:pay|payment|deposit)\w*\b[^.]{0,40}\b(?:gift ?cards?|itunes|steam cards?)\b",
                                 re.I)
_POLICY = re.compile(r"\b(?:refunds?|cancell?ations?|cancel)\b", re.I)


def payment_red_flag(page: str | None) -> str | None:
    """The sentence on the vendor's page that asks for an untraceable payment, if any."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", page or ""):
        if ((_UNTRACEABLE.search(sentence) and _ONLY.search(sentence))
                or (_TRANSFER_SERVICE.search(sentence) and _ASKS_TO_PAY.search(sentence))
                or _PAID_IN_GIFT_CARDS.search(sentence)):
            return sentence.strip()[:200]
    return None


def domain_age_days(rdap: dict, today: date) -> int | None:
    """Age of a domain from its RDAP record (the public registry lookup that replaced WHOIS)."""
    for ev in rdap.get("events") or []:
        if ev.get("eventAction") == "registration" and ev.get("eventDate"):
            try:
                registered = datetime.fromisoformat(ev["eventDate"].replace("Z", "+00:00")).date()
            except ValueError:
                return None
            return (today - registered).days
    return None


def cheapest(vendor: dict) -> float | None:
    prices = [t["pricePerPerson"] for t in vendor.get("tiers") or [] if t.get("pricePerPerson")]
    return min(prices) if prices else None


def market_ratio(vendor: dict, others: list[dict]) -> float | None:
    """This vendor's cheapest price / the median of the other vendors' cheapest prices."""
    mine = cheapest(vendor)
    theirs = [p for p in (cheapest(o) for o in others) if p]
    if mine is None or len(theirs) < 2:
        return None
    return mine / statistics.median(theirs)


def assess(vendor: dict, page: str | None, age_days: int | None, ratio: float | None) -> dict:
    """{"level", "reasons", "signals"}: each signal is {kind, ok, detail[, evidence]}."""
    signals: list[dict] = []
    hard: list[str] = []
    warn: list[str] = []

    def signal(kind: str, ok: bool | None, detail: str, evidence: str | None = None) -> None:
        signals.append({"kind": kind, "ok": ok, "detail": detail, **({"evidence": evidence} if evidence else {})})

    listed = bool(vendor.get("mapsLink"))
    signal("listing", listed, "On Google Maps" + (f" at {vendor['address']}" if vendor.get("address") else "")
           if listed else "No Google Maps listing (found only through web search)")
    if not listed:
        warn.append("no Google Maps listing")

    rating, reviews = vendor.get("rating"), vendor.get("reviews") or 0
    good = rating is not None and rating >= MIN_RATING and reviews >= MIN_REVIEWS
    signal("reviews", good if rating is not None else None,
           f"{rating}★ from {reviews} reviews" if rating is not None else "No reviews found")
    if not good:
        warn.append(f"only {reviews} reviews" if rating is not None and rating >= MIN_RATING
                    else f"rated {rating}★" if rating is not None else "no reviews")

    if age_days is None:
        signal("domain_age", None, "Website age unknown")
    else:
        signal("domain_age", age_days >= YOUNG_SITE_DAYS, f"Website registered {age_days} days ago")
        if age_days < NEW_SITE_DAYS and not listed:
            hard.append(f"website only {age_days} days old and no map listing")
        elif age_days < YOUNG_SITE_DAYS:
            warn.append(f"website only {age_days} days old")

    flag = payment_red_flag(page)
    signal("payment", not flag if page else None,
           "Asks for an untraceable payment" if flag else "No payment red flags on its page" if page
           else "Page not read", evidence=flag)
    if flag:
        hard.append("asks to be paid in a way that can't be traced or refunded")

    if ratio is not None:
        cheap = ratio < TOO_CHEAP
        signal("price", not cheap, f"Cheapest price is {ratio:.0%} of what the other vendors charge")
        if cheap and (not listed or reviews < 5):
            hard.append(f"price only {ratio:.0%} of the market from an unknown business")
        elif cheap:
            warn.append(f"price only {ratio:.0%} of the market")

    if page:
        has_policy = bool(_POLICY.search(page))
        signal("policy", has_policy, "Mentions refunds or cancellation" if has_policy
               else "No refund or cancellation terms on the page read")

    level = "suspected_fraud" if hard else "unverified" if warn else "verified"
    return {"level": level, "reasons": hard or warn, "signals": signals}


def partner() -> dict:
    """Shops in Parley's own fixtures: onboarded directly, not found on the web."""
    return {"level": "verified", "reasons": [],
            "signals": [{"kind": "partner", "ok": True, "detail": "Parley partner shop (demo data)"}]}
