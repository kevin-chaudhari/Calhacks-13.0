"""Any activity, anywhere: a goal outside the seeded sports finds real vendors through Bright Data
(mocked at the HTTP layer), negotiates on their listed prices, and every price shown can be traced to
a sentence on the vendor's own page."""
import httpx
import pytest
from fastapi.testclient import TestClient

from rally.core import Settings
from rally.discovery import VendorFinder
from tests.integration.test_api_flow import h, settle, wait_for
from tests.unit.test_discovery import PAGES, fake_model, handler

GOAL = "Rock climbing in Yosemite next month under $400, I'm a beginner"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from rally.main import app, rally
    monkeypatch.setenv("RALLY_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "k")
    monkeypatch.setenv("BRIGHTDATA_SERP_ZONE", "serp_z")
    monkeypatch.setenv("BRIGHTDATA_UNLOCKER_ZONE", "unl_z")
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        rally.finder = VendorFinder(Settings(), transport=httpx.MockTransport(handler([])), llm=fake_model)
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        c.rally = rally
        yield c
    rally.finder = VendorFinder(Settings())


def publish(c, text, who="u_kevin", size=1):
    g = c.post("/v1/goals:compile", json={"text": text}, headers=h(c, who)).json()
    assert g["draft"]["activity"] == "rock_climbing" and g["draft"]["location"]["label"] == "Yosemite Valley, CA"
    g = c.patch(f"/v1/goals/{g['id']}", json={"groupMax": size, "groupMin": 1 if size == 1 else 2},
                headers=h(c, who)).json()
    return c.post("/v1/intents", json={"goalId": g["id"], "privatePrefs": g["suggestedPrefs"]}, headers=h(c, who)).json()


def test_discover_shows_real_vendors_with_evidence(client):
    r = client.get("/v1/discover", params={"q": "rock climbing in Yosemite"}, headers=h(client, "u_kevin"))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["activity"] == "rock_climbing" and d["place"] == "Yosemite Valley, CA" and d["mode"] == "brightdata"
    yms = d["vendors"][0]
    assert yms["name"] == "Yosemite Mountaineering School" and yms["rating"] == 4.8
    assert all(o["evidence"] in PAGES["ymsclimb.example"] and o["sourceUrl"] == "https://ymsclimb.example"
               for o in yms["listedOffers"])
    assert d["deals"][0]["source"] == "groupon.com"
    assert client.get("/v1/discover", params={"q": "climbing"}, headers=h(client, "u_kevin")).status_code == 422


def test_solo_climber_books_at_a_real_listed_price(client):
    c = client
    intent = publish(c, GOAL)
    deal = c.post("/v1/deals", json={"intentId": intent["id"], "solo": True}, headers=h(c, "u_kevin")).json()
    snap = settle(c, deal["id"])
    assert snap["deal"]["status"] == "AWAITING_APPROVAL", snap["deal"]["conflicts"]
    chosen = next(q for q in snap["quotes"] if q["id"] == snap["deal"]["chosenQuoteId"])
    assert (chosen["providerName"], chosen["pricePerPerson"]) == ("Tuolumne Climbing Collective", 145.0)  # cheapest group lesson
    other = next(q for q in snap["quotes"] if q["providerName"] == "Yosemite Mountaineering School")
    assert other["pricePerPerson"] == 172.0
    assert other["evidence"] == "Go Climb a Rock (beginner group class): $172 per person, 7 hours."
    assert chosen["evidence"] == "Intro to granite: $145 per person, half day."
    assert chosen["provenance"] == "cached" and chosen["binding"] is False and chosen["sourceUrl"]
    assert chosen["pricePerPerson"] <= 400
    msgs = [m["summary"] for m in snap["agentMessages"]]
    assert any("vendors found" in m and "with prices on their own site" in m for m in msgs)
    assert any(m.startswith("Listed price $") for m in msgs)
    assert any(m.startswith("Listed on ymsclimb.example: Go Climb a Rock $172 per person. Source: “Go Climb a Rock") for m in msgs)
    plan = snap["proposals"][-1]
    r = c.post(f"/v1/deals/{deal['id']}/approvals",
               json={"proposalVersion": plan["version"], "quoteId": chosen["id"], "decision": "approve",
                     "autoCommit": True}, headers=h(c, "u_kevin"))
    assert r.status_code == 200, r.text
    done = wait_for(c, deal["id"], "u_kevin", {"COMMITTED"})
    assert done["commitments"][0]["amount"] == chosen["pricePerPerson"]


def test_no_vendors_says_why_instead_of_failing_silently(client):
    c = client
    c.rally.finder = VendorFinder(Settings(), transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"organic": [], "snack_pack": []})))
    intent = publish(c, GOAL)
    deal = c.post("/v1/deals", json={"intentId": intent["id"], "solo": True}, headers=h(c, "u_kevin")).json()
    snap = wait_for(c, deal["id"], "u_kevin", {"NO_AGREEMENT"})
    assert snap["deal"]["conflicts"] == ["No vendor with a listed price was found for rock climbing near Yosemite Valley, CA"]
