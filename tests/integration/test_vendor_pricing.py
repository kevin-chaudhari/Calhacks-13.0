"""Vendor price input is checked before anything is saved: NaN, Infinity, negative or impossible
prices are refused, a refused edit changes nothing, and the feed and deal pages keep working."""
import time

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_flow import h

STAFF, PROVIDER = "v_lena", "p_kelpline"
JSON = {"Content-Type": "application/json"}


@pytest.fixture()
def client():
    from rally.main import _buckets, app, rally
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        c.rally, c.buckets = rally, _buckets
        yield c


def patch_raw(c, body: str):
    return c.request("PATCH", "/v1/vendor/provider", content=body, headers={**h(c, STAFF), **JSON})


def still_serving(c):
    assert c.get("/v1/providers").status_code == 200
    assert c.get("/v1/vendor/dashboard", headers=h(c, STAFF)).status_code == 200
    assert c.get("/v1/feed", headers=h(c, "u_kevin")).status_code == 200


@pytest.mark.parametrize("body, field", [
    ('{"tiers": [{"min": 1, "max": 8, "pricePerPerson": "nan"}]}', "tiers"),
    ('{"tiers": [{"min": 1, "max": 8, "pricePerPerson": NaN}]}', "tiers"),
    ('{"tiers": [{"min": 1, "max": 8, "pricePerPerson": Infinity}]}', "tiers"),
    ('{"tiers": [{"min": 1, "max": 8, "pricePerPerson": "inf"}]}', "tiers"),
    ('{"tiers": [{"min": 1, "max": 8, "pricePerPerson": -10}]}', "tiers"),
    ('{"tiers": [{"min": 1, "max": 8, "pricePerPerson": 0}]}', "tiers"),
    ('{"tiers": [{"min": -5, "max": 0, "pricePerPerson": 10}]}', "tiers"),
    ('{"tiers": [{"min": 4, "max": 2, "pricePerPerson": 10}]}', "tiers"),
    ('{"tiers": [{"min": 1.5, "max": 4, "pricePerPerson": 10}]}', "tiers"),
    ('{"tiers": [{"min": 1, "max": 4, "pricePerPerson": 150}, {"min": 3, "max": 8, "pricePerPerson": 120}]}', "tiers"),
    ('{"tiers": []}', "tiers"),
    ('{"tiers": "cheap"}', "tiers"),
    ('{"modifiers": {"gear_included": {"true": "nan"}}}', "modifiers"),
    ('{"modifiers": {"gear_included": {"true": Infinity}}}', "modifiers"),
    ('{"modifiers": {"gear_included": {"true": -1000}}}', "modifiers"),   # would make prices negative
    ('{"autoQuote": "false"}', "autoQuote"),                              # a string, not a boolean
    ('{"availableDates": "2026-11-14"}', "availableDates"),
])
def test_bad_price_rules_are_refused_and_nothing_is_saved(client, body, field):
    before = {k: client.rally.provider(PROVIDER).get(k) for k in ("tiers", "modifiers", "autoQuote", "availableDates")}
    r = patch_raw(client, body)
    assert r.status_code == 422 and field in r.json()["error"]["fields"], r.text
    assert {k: client.rally.provider(PROVIDER).get(k) for k in before} == before
    still_serving(client)


def test_a_refused_field_saves_none_of_the_others(client):
    auto = client.rally.provider(PROVIDER).get("autoQuote", True)
    r = patch_raw(client, '{"autoQuote": %s, "tiers": [{"min": 1, "max": 8, "pricePerPerson": NaN}]}'
                  % ("false" if auto else "true"))
    assert r.status_code == 422
    assert client.rally.provider(PROVIDER).get("autoQuote", True) == auto


def test_good_price_rules_still_save(client):
    tiers = [{"min": 1, "max": 3, "pricePerPerson": 180}, {"min": 4, "max": 8, "pricePerPerson": 150}]
    r = client.patch("/v1/vendor/provider", headers=h(client, STAFF),
                     json={"tiers": tiers, "modifiers": {"dive_type": {"shore": -40}}, "autoQuote": False})
    assert r.status_code == 200, r.text
    prov = client.rally.provider(PROVIDER)
    assert [t["pricePerPerson"] for t in prov["tiers"]] == [180, 150]
    assert prov["modifiers"] == {"dive_type": {"shore": -40.0}} and prov["autoQuote"] is False


def deal_awaiting_review(c):
    c.patch("/v1/vendor/provider", headers=h(c, STAFF), json={"autoQuote": False})
    c.buckets.clear()
    deal_id = c.post("/v1/demo/launch", json={"scenario": "solo"}, headers=h(c, "u_kevin")).json()["dealId"]
    end = time.time() + 10
    while time.time() < end:
        s = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
        if s["deal"]["vendorReview"]:
            return s
        time.sleep(0.05)
    raise AssertionError("no quote to review")


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-Infinity", "-5", "0"])
def test_staff_cant_approve_a_quote_at_an_impossible_price(client, price):
    s = deal_awaiting_review(client)
    staff = {"p_kelpline": "v_lena", "p_ottercove": "v_marcus"}[s["deal"]["vendorReview"]["providerId"]]
    r = client.request("POST", f"/v1/vendor/requests/{s['deal']['id']}/quote", headers={**h(client, staff), **JSON},
                       content='{"action": "approve", "pricePerPerson": %s}' % price)
    assert r.status_code == 422 and r.json()["error"]["code"] == "PRICE_NOT_ALLOWED", r.text
    assert client.get(f"/v1/deals/{s['deal']['id']}/snapshot", headers=h(client, "u_kevin")).status_code == 200
    still_serving(client)


def test_staff_can_still_lower_a_quote(client):
    s = deal_awaiting_review(client)
    review = s["deal"]["vendorReview"]
    staff = {"p_kelpline": "v_lena", "p_ottercove": "v_marcus"}[review["providerId"]]
    lower = round(review["draft"]["pricePerPerson"] - 10.004, 3)
    r = client.post(f"/v1/vendor/requests/{s['deal']['id']}/quote", headers=h(client, staff),
                    json={"action": "approve", "pricePerPerson": lower})
    assert r.status_code == 200, r.text
    snap = client.get(f"/v1/deals/{s['deal']['id']}/snapshot", headers=h(client, "u_kevin")).json()
    q = next(x for x in snap["quotes"] if x["id"] == snap["deal"]["chosenQuoteId"])
    assert q["pricePerPerson"] == round(lower, 2) and q["total"] == round(round(lower, 2) * q["groupSize"], 2)
