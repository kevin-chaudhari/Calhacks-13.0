"""Solo mode: nobody fits (or the person wants to go alone), and the personal agent negotiates with
vendor agents directly. Shops' already-booked trips let a solo traveller ride along at a group rate."""
import time

import pytest
from fastapi.testclient import TestClient

from rally.negotiation.engine import ProviderSheet
from rally.providers import load_providers, quote_for, sheets
from tests.integration.test_api_flow import h, settle, wait_for

GOALS = {
    "scuba": "I want to go scuba diving in Monterey next month for under $300. I am Open Water certified.",
    "skydiving": "I want to go skydiving near Santa Cruz next month for under $400, first jump.",
    "kayaking": "Sea kayaking in Monterey next month, under $120 per person.",
}


@pytest.fixture()
def client():
    from rally.main import app
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        yield c


def publish(c, text, who="u_kevin"):
    g = c.post("/v1/goals:compile", json={"text": text}, headers=h(c, who)).json()
    g = c.patch(f"/v1/goals/{g['id']}", json={"groupMax": 1, "groupMin": 1}, headers=h(c, who)).json()
    return c.post("/v1/intents", json={"goalId": g["id"], "privatePrefs": g["suggestedPrefs"]}, headers=h(c, who)).json()


def test_open_group_pricing_only_applies_in_solo_mode():
    kelp = next(p for p in load_providers() if p["id"] == "p_kelpline")
    terms = {"date": "2026-11-14", "dive_type": "boat", "site": "Lovers Point", "gear_included": False}
    alone, pooled = sheets([kelp])[0].price(terms, 1), sheets([kelp], pool=True)[0].price(terms, 1)
    assert alone == 199 and pooled == 154                   # rides with the 3 already booked: 4-5 tier
    off_day = dict(terms, date="2026-11-08")
    assert sheets([kelp], pool=True)[0].price(off_day, 1) == 199    # no open group that day
    q = quote_for(kelp, terms, 1, 1, binding=True, pool=True)
    assert q.price_per_person == 154 and q.solo_price_per_person == 199
    assert any("joins a booked group of 3" in i for i in q.includes)
    assert ProviderSheet("x", "x", {}, ["d"], [{"min": 1, "max": 2, "pricePerPerson": 5}],
                         open_groups={"d": 9}, pool=True).pooled_size({"date": "d"}, 1) == 2   # capped at top tier


@pytest.mark.parametrize("activity", ["scuba", "skydiving", "kayaking"])
def test_solo_traveller_reaches_a_committed_booking(client, activity):
    c = client
    intent = publish(c, GOALS[activity])
    r = c.post("/v1/deals", json={"intentId": intent["id"], "solo": True}, headers=h(c, "u_kevin"))
    assert r.status_code == 200, r.text
    deal = r.json()
    assert deal["solo"] and deal["groupMin"] == 1 and deal["title"].endswith("solo")
    snap = settle(c, deal["id"])                             # negotiation starts by itself
    assert snap["deal"]["status"] == "AWAITING_APPROVAL", snap["deal"]["conflicts"]
    assert [m["userId"] for m in snap["members"]] == ["u_kevin"]
    chosen = next(q for q in snap["quotes"] if q["id"] == snap["deal"]["chosenQuoteId"])
    assert chosen["groupSize"] == 1 and chosen["binding"]
    assert chosen["pricePerPerson"] <= chosen["soloPricePerPerson"]
    assert any(m["type"] == "QuoteMsg" and "Solo traveller welcome" in m["summary"] for m in snap["agentMessages"])
    assert snap["deal"]["nudge"] is None
    plan = snap["proposals"][-1]
    c.post(f"/v1/deals/{deal['id']}/approvals",
           json={"proposalVersion": plan["version"], "quoteId": chosen["id"], "decision": "approve", "autoCommit": True},
           headers=h(c, "u_kevin"))
    done = wait_for(c, deal["id"], "u_kevin", {"COMMITTED"})
    assert [x["userId"] for x in done["commitments"] if x["state"] == "committed"] == ["u_kevin"]


def test_scuba_solo_agent_finds_an_open_group_rate(client):
    c = client
    intent = publish(c, GOALS["scuba"])
    deal = c.post("/v1/deals", json={"intentId": intent["id"], "solo": True}, headers=h(c, "u_kevin")).json()
    snap = settle(c, deal["id"])
    chosen = next(q for q in snap["quotes"] if q["id"] == snap["deal"]["chosenQuoteId"])
    assert chosen["pricePerPerson"] < chosen["soloPricePerPerson"]          # better than booking alone
    assert any("joins a booked group" in i for i in chosen["includes"])


def test_solo_refuses_extra_members(client):
    c = client
    intent = publish(c, GOALS["scuba"])
    r = c.post("/v1/deals", json={"intentId": intent["id"], "solo": True, "candidateIntentIds": ["i_x"]},
               headers=h(c, "u_kevin"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "SOLO_WITH_OTHERS"
