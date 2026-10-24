"""Group-size nudge from the provider agent, and accepting it."""
import time

import pytest
from test_api_flow import GOAL, client, h, settle  # noqa: F401  (client is a fixture)


@pytest.fixture(autouse=True)
def _no_rate_limit():
    from rally.main import _buckets
    _buckets.clear()                          # these tests compile Kevin's goal more than 10 times a minute

FIVE_IS_CHEAPER = [{"min": 1, "max": 4, "pricePerPerson": 200}, {"min": 5, "max": 8, "pricePerPerson": 170}]


def four_person_deal(c):
    for staff in ("v_lena", "v_marcus"):                  # both scuba vendors: 5 people get a cheaper tier
        assert c.patch("/v1/vendor/provider", json={"tiers": FIVE_IS_CHEAPER}, headers=h(c, staff)).status_code == 200
    goal = c.post("/v1/goals:compile", json={"text": GOAL}, headers=h(c, "u_kevin")).json()
    goal = c.patch(f"/v1/goals/{goal['id']}", json={"groupMax": 5}, headers=h(c, "u_kevin")).json()
    intent = c.post("/v1/intents", json={"goalId": goal["id"], "privatePrefs": goal["suggestedPrefs"]},
                    headers=h(c, "u_kevin")).json()
    m = c.post(f"/v1/intents/{intent['id']}/matches", json={}, headers=h(c, "u_kevin")).json()
    three = m["selectedIntentIds"][:3]                    # Kevin + 3 = 4 people; more matches are free
    deal_id = c.post("/v1/deals", json={"intentId": intent["id"], "candidateIntentIds": three},
                     headers=h(c, "u_kevin")).json()["id"]
    end = time.time() + 5
    while time.time() < end and not all(
            x["state"] == "joined" for x in c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()["members"]):
        time.sleep(0.05)
    assert c.post(f"/v1/deals/{deal_id}/negotiate", headers=h(c, "u_kevin")).status_code == 202
    return deal_id, settle(c, deal_id)


def test_provider_agent_nudges_when_one_more_person_is_cheaper(client):
    c = client
    deal_id, snap = four_person_deal(c)
    assert snap["deal"]["status"] == "AWAITING_APPROVAL"
    quote = next(q for q in snap["quotes"] if q["id"] == snap["deal"]["chosenQuoteId"])
    assert quote["groupSize"] == 4
    nudge = snap["deal"]["nudge"]
    # same plan, same provider, same add-ons: only the tier base changes (200 -> 170)
    assert nudge == {"providerId": quote["providerId"], "extraPeople": 1,
                     "newPricePerPerson": quote["pricePerPerson"] - 30, "savingPerPerson": 30}
    msg = next(m for m in snap["agentMessages"] if m["type"] == "NudgeMsg")
    assert msg["fromKind"] == "provider" and "saves $30" in msg["summary"]


def test_accepting_the_nudge_invites_the_next_match_and_renegotiates(client):
    c = client
    deal_id, snap = four_person_deal(c)
    assert c.post(f"/v1/deals/{deal_id}/nudge/accept", headers=h(c, "u_ana")).status_code == 403   # organizer only
    c.post(f"/v1/deals/{deal_id}/approvals", headers=h(c, "u_kevin"),
           json={"proposalVersion": snap["deal"]["currentProposalVersion"], "quoteId": snap["deal"]["chosenQuoteId"]})
    r = c.post(f"/v1/deals/{deal_id}/nudge/accept", headers=h(c, "u_kevin"))
    assert r.status_code == 200, r.text
    time.sleep(0.2)
    snap2 = settle(c, deal_id)
    assert snap2["deal"]["status"] == "AWAITING_APPROVAL"
    assert sum(m["state"] == "joined" for m in snap2["members"]) == 5
    assert r.json()["invitedUserId"] in {m["userId"] for m in snap2["members"]}
    assert all(a["void"] for a in snap2["approvals"])
    quote = next(q for q in snap2["quotes"] if q["id"] == snap2["deal"]["chosenQuoteId"])
    assert quote["groupSize"] == 5 and snap2["deal"]["nudge"] is None    # 6 would exceed groupMax
    again = c.post(f"/v1/deals/{deal_id}/nudge/accept", headers=h(c, "u_kevin"))
    assert again.status_code == 409 and again.json()["error"]["code"] == "NO_NUDGE"


def test_leaving_mid_negotiation_restarts_with_a_replacement(client, monkeypatch):
    from rally.main import rally
    c = client
    monkeypatch.setattr(rally.s, "round_delay_s", 0.3)       # slow rounds so a member can leave mid-negotiation
    goal = c.post("/v1/goals:compile", json={"text": GOAL}, headers=h(c, "u_kevin")).json()
    goal = c.patch(f"/v1/goals/{goal['id']}", json={"groupMax": 5}, headers=h(c, "u_kevin")).json()
    intent = c.post("/v1/intents", json={"goalId": goal["id"], "privatePrefs": goal["suggestedPrefs"]},
                    headers=h(c, "u_kevin")).json()
    m = c.post(f"/v1/intents/{intent['id']}/matches", json={}, headers=h(c, "u_kevin")).json()
    deal_id = c.post("/v1/deals", json={"intentId": intent["id"], "candidateIntentIds": m["selectedIntentIds"]},
                     headers=h(c, "u_kevin")).json()["id"]
    end = time.time() + 5
    while time.time() < end and not all(
            x["state"] == "joined" for x in c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()["members"]):
        time.sleep(0.05)
    c.post(f"/v1/deals/{deal_id}/negotiate", headers=h(c, "u_kevin"))
    time.sleep(0.4)
    assert c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()["deal"]["status"] == "NEGOTIATING"
    member = next(x for x in m["matches"] if x["selected"])["userId"]
    assert c.post(f"/v1/deals/{deal_id}/leave", json={"reason": "sick"}, headers=h(c, member)).status_code == 200
    end = time.time() + 30
    while time.time() < end:
        snap = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
        if snap["deal"]["status"] in {"AWAITING_APPROVAL", "NO_AGREEMENT", "FAILED"}:
            break
        if snap["deal"]["vendorReview"]:
            c.post(f"/v1/vendor/requests/{deal_id}/quote", json={"action": "approve"},
                   headers=h(c, {"p_ottercove": "v_marcus", "p_kelpline": "v_lena"}[snap["deal"]["vendorReview"]["providerId"]]))
        time.sleep(0.1)
    assert snap["deal"]["status"] == "AWAITING_APPROVAL", snap["deal"]["status"]
    assert [r["leftUserId"] for r in snap["deal"]["replacements"]] == [member]
    assert sum(x["state"] == "joined" for x in snap["members"]) == 5
    q = next(q for q in snap["quotes"] if q["id"] == snap["deal"]["chosenQuoteId"])
    assert q["groupSize"] == 5
