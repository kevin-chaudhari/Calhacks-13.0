"""End-to-end over HTTP: goal -> intent -> matches -> deal -> negotiation -> quote -> approvals -> commitment."""
import time

import pytest
from fastapi.testclient import TestClient

GOAL = "I want to go scuba diving in Monterey next month for under $300. I am Open Water certified."


@pytest.fixture()
def client():
    from rally.main import app, rally
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        yield c


def h(c, who, key=None):
    hdr = {"Authorization": f"Bearer {c.tokens[who]}"}
    if key:
        hdr["Idempotency-Key"] = key
    return hdr


def wait_for(c, deal_id, who, statuses, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        snap = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, who)).json()
        if snap["deal"]["status"] in statuses:
            return snap
        time.sleep(0.05)
    raise AssertionError(f"deal never reached {statuses}; last {snap['deal']['status']}")


def settle(c, deal_id):
    """Wait for the mediator; if the chosen vendor reviews quotes by hand, approve as their staff."""
    end = time.time() + 10
    while time.time() < end:
        snap = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
        if snap["deal"]["status"] in {"AWAITING_APPROVAL", "NO_AGREEMENT"}:
            return snap
        if snap["deal"]["vendorReview"]:
            staff = next(p for p in c.get("/v1/demo/personas").json()
                         if p.get("providerId") == snap["deal"]["vendorReview"]["providerId"])
            c.post(f"/v1/vendor/requests/{deal_id}/quote", json={"action": "approve"}, headers=h(c, staff["id"]))
        time.sleep(0.05)
    raise AssertionError("deal did not settle")


def run_to_approval(c):
    goal = c.post("/v1/goals:compile", json={"text": GOAL}, headers=h(c, "u_kevin", "k1")).json()
    assert goal["status"] == "needs_input"
    assert [m["field"] for m in goal["draft"]["missing"]] == ["groupMax"]
    # never invented: budget and dates come from the sentence
    assert goal["draft"]["budgetMax"]["amount"] == 300
    goal = c.patch(f"/v1/goals/{goal['id']}", json={"groupMax": 5}, headers=h(c, "u_kevin")).json()
    assert goal["status"] == "ready"
    intent = c.post("/v1/intents", json={"goalId": goal["id"], "privatePrefs": goal["suggestedPrefs"]},
                    headers=h(c, "u_kevin", "p1")).json()
    assert "weights" not in str(intent)            # private prefs never echo back
    m = c.post(f"/v1/intents/{intent['id']}/matches", json={}, headers=h(c, "u_kevin")).json()
    reasons = {r["name"]: r["failedConstraint"] for r in m["rejections"]}
    assert reasons == {"Luis": "date", "Sam": "certification", "Priya": "distance", "Theo": "budget",
                       "Noor": "certification"}
    assert len(m["selectedIntentIds"]) == 4
    deal = c.post("/v1/deals", json={"intentId": intent["id"], "candidateIntentIds": m["selectedIntentIds"]},
                  headers=h(c, "u_kevin", "d1")).json()
    deal_id = deal["id"]
    end = time.time() + 5
    while time.time() < end:
        snap = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
        if all(mm["state"] == "joined" for mm in snap["members"]):
            break
        time.sleep(0.05)
    r = c.post(f"/v1/deals/{deal_id}/negotiate", headers=h(c, "u_kevin"))
    assert r.status_code == 202
    end = time.time() + 10
    while time.time() < end:
        snap = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
        if snap["deal"]["status"] in {"AWAITING_APPROVAL", "NO_AGREEMENT"} or snap["deal"]["vendorReview"]:
            break
        time.sleep(0.05)
    # Otter Cove's agent drafts the quote; their staff (Marcus) approves it in the vendor portal
    assert snap["deal"]["vendorReview"]["providerId"] == "p_ottercove"
    reqs = c.get("/v1/vendor/requests", headers=h(c, "v_marcus")).json()
    assert [r["stage"] for r in reqs if r["id"] == deal_id] == ["needs_review"]
    assert c.post(f"/v1/vendor/requests/{deal_id}/quote", json={"pricePerPerson": 999},
                  headers=h(c, "v_marcus")).status_code == 422          # may lower, never raise
    assert c.post(f"/v1/vendor/requests/{deal_id}/quote", json={"action": "approve"},
                  headers=h(c, "v_lena")).status_code == 409            # another vendor can't approve
    r = c.post(f"/v1/vendor/requests/{deal_id}/quote", json={"action": "approve"}, headers=h(c, "v_marcus"))
    assert r.status_code == 200, r.text
    snap = wait_for(c, deal_id, "u_kevin", {"AWAITING_APPROVAL", "NO_AGREEMENT"})
    return deal_id, snap


def test_full_scuba_path(client):
    c = client
    deal_id, snap = run_to_approval(c)
    assert snap["deal"]["status"] == "AWAITING_APPROVAL"
    final = snap["proposals"][-1]
    assert final["terms"]["dive_type"] == "boat"                 # Kai's revealed hard limit held
    assert final["pricePerPerson"] <= 220                        # Ravi's public budget cap held
    v = snap["deal"]["currentProposalVersion"]
    quote_id = snap["deal"]["chosenQuoteId"]
    # stale version is refused
    r = c.post(f"/v1/deals/{deal_id}/approvals", json={"proposalVersion": v - 1, "quoteId": quote_id},
               headers=h(c, "u_kevin"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "PROPOSAL_CHANGED"
    body = {"proposalVersion": v, "quoteId": quote_id, "decision": "approve", "autoCommit": True}
    a1 = c.post(f"/v1/deals/{deal_id}/approvals", json=body, headers=h(c, "u_kevin")).json()
    a2 = c.post(f"/v1/deals/{deal_id}/approvals", json=body, headers=h(c, "u_kevin")).json()
    assert a1["id"] == a2["id"]                                   # duplicate returns the first row
    for who in ["u_ana", "u_ravi"]:
        assert c.post(f"/v1/deals/{deal_id}/approvals", json=body, headers=h(c, who)).status_code == 200
    # a teammate cannot be approved on their behalf
    r = c.post(f"/v1/demo/act-as/u_ana/approve/{deal_id}", json=body, headers=h(c, "u_kevin"))
    assert r.status_code == 403
    for persona in ["u_maya", "u_kai"]:
        r = c.post(f"/v1/demo/act-as/{persona}/approve/{deal_id}", json=body, headers=h(c, "u_kevin"))
        assert r.status_code == 200, r.text
    snap = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
    assert snap["deal"]["status"] == "COMMITTED"
    assert snap["deal"]["bookingStatus"] == "not_booked"          # committing is not booking
    # the vendor confirms the booking; the agent wire shows every hop
    assert c.post(f"/v1/vendor/requests/{deal_id}/booking", headers=h(c, "v_marcus")).status_code == 200
    snap = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
    assert snap["deal"]["bookingStatus"] == "confirmed_by_provider"
    types = {m["type"] for m in snap["agentMessages"]}
    assert {"InviteMsg", "JoinMsg", "ProposalMsg", "ResponseMsg", "QuoteRequestMsg", "QuoteMsg",
            "ReviewRequest", "ReviewDecision", "FinalAgreementMsg"} <= types
    # people talk too: a member and the vendor's staff, with a voice-dictated message
    assert c.post(f"/v1/deals/{deal_id}/messages", json={"text": "Can we bring a GoPro?"},
                  headers=h(c, "u_ana")).status_code == 200
    r = c.post(f"/v1/deals/{deal_id}/messages", json={"text": "Sí, claro", "lang": "es-ES", "viaVoice": True},
               headers=h(c, "v_marcus"))
    assert r.status_code == 200 and r.json()["authorRole"] == "vendor"
    assert c.post(f"/v1/deals/{deal_id}/messages", json={"text": "hi"}, headers=h(c, "v_lena")).status_code == 403
    snap = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
    assert all(cm["method"] == "simulated" and cm["txRef"].startswith("sim_") for cm in snap["commitments"])
    seqs = [e["seq"] for e in snap["events"]]
    assert seqs == list(range(1, len(seqs) + 1))                  # gap-free audit log
    text = str(snap)
    for secret in ["weights", "reservation", "priceWorst", "patience"]:
        assert secret not in text                                 # no private preference leaks


def test_outsider_cannot_read_or_approve(client):
    c = client
    deal_id, snap = run_to_approval(c)
    assert c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_luis")).status_code == 403
    body = {"proposalVersion": snap["deal"]["currentProposalVersion"], "quoteId": snap["deal"]["chosenQuoteId"]}
    assert c.post(f"/v1/deals/{deal_id}/approvals", json=body, headers=h(c, "u_luis")).status_code == 403
    assert c.get("/v1/goals", headers={"Authorization": "Bearer u_kevin.forged"}).status_code == 401


def test_leaving_voids_approvals_and_renegotiates(client):
    c = client
    deal_id, snap = run_to_approval(c)
    body = {"proposalVersion": snap["deal"]["currentProposalVersion"], "quoteId": snap["deal"]["chosenQuoteId"]}
    c.post(f"/v1/deals/{deal_id}/approvals", json=body, headers=h(c, "u_kevin"))
    c.post(f"/v1/deals/{deal_id}/leave", json={"reason": "work trip"}, headers=h(c, "u_ana"))
    time.sleep(0.2)
    snap2 = settle(c, deal_id)
    assert snap2["deal"]["currentProposalVersion"] > body["proposalVersion"]
    assert all(a["void"] for a in snap2["approvals"])
    r = c.post(f"/v1/deals/{deal_id}/approvals", json=body, headers=h(c, "u_kevin"))
    assert r.status_code == 409
    # the mediator invited the next eligible match in Ana's place, so the group stays at 5
    active = [m for m in snap2["members"] if m["state"] == "joined"]
    assert len(active) == 5 and "u_ana" not in {m["userId"] for m in active}
    [rep] = snap2["deal"]["replacements"]
    newcomer = next(m for m in snap2["members"] if m["userId"] == rep["invitedUserId"])
    assert rep["leftUserId"] == "u_ana" and newcomer["state"] == "joined"
    assert rep["leftName"] == "Ana" and rep["invitedName"] == newcomer["name"]
    assert any(e["type"] == "member.replaced" and newcomer["name"] in e["summary"] for e in snap2["events"])


def test_compile_needs_input_and_publish_blocked(client):
    c = client
    g = c.post("/v1/goals:compile", json={"text": "I want to go diving soon"}, headers=h(c, "u_kevin")).json()
    fields = {m["field"] for m in g["draft"]["missing"]}
    assert {"location", "dates", "budgetMax", "certification"} <= fields
    assert g["draft"]["budgetMax"] is None and g["draft"]["dateFrom"] is None
    r = c.post("/v1/intents", json={"goalId": g["id"], "privatePrefs": g["suggestedPrefs"]}, headers=h(c, "u_kevin"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "NEEDS_INPUT"


@pytest.mark.parametrize("goal,vendor_auto", [
    ("I want to go skydiving near Santa Cruz next month for under $400, first jump.", None),
    ("Sea kayaking in Monterey next month, under $120 per person.", None),
])
def test_other_activities_reach_approval(client, goal, vendor_auto):
    c = client
    g = c.post("/v1/goals:compile", json={"text": goal}, headers=h(c, "u_kevin")).json()
    g = c.patch(f"/v1/goals/{g['id']}", json={"groupMax": 5}, headers=h(c, "u_kevin")).json()
    assert g["status"] == "ready", g["draft"]["missing"]
    intent = c.post("/v1/intents", json={"goalId": g["id"], "privatePrefs": g["suggestedPrefs"]},
                    headers=h(c, "u_kevin")).json()
    m = c.post(f"/v1/intents/{intent['id']}/matches", json={}, headers=h(c, "u_kevin")).json()
    assert len(m["selectedIntentIds"]) == 4
    assert len([r for r in m["rejections"] if not r["userId"].startswith("c_")]) == 3   # community people elsewhere are extra rejections
    deal = c.post("/v1/deals", json={"intentId": intent["id"], "candidateIntentIds": m["selectedIntentIds"]},
                  headers=h(c, "u_kevin")).json()
    time.sleep(0.3)
    assert c.post(f"/v1/deals/{deal['id']}/negotiate", headers=h(c, "u_kevin")).status_code == 202
    end = time.time() + 10
    while time.time() < end:
        snap = c.get(f"/v1/deals/{deal['id']}/snapshot", headers=h(c, "u_kevin")).json()
        if snap["deal"]["status"] in {"AWAITING_APPROVAL", "NO_AGREEMENT"} or snap["deal"]["vendorReview"]:
            break
        time.sleep(0.05)
    if snap["deal"]["vendorReview"]:
        staff = next(p for p in c.get("/v1/demo/personas").json()
                     if p.get("providerId") == snap["deal"]["vendorReview"]["providerId"])
        c.post(f"/v1/vendor/requests/{deal['id']}/quote", json={"action": "approve"}, headers=h(c, staff["id"]))
        snap = wait_for(c, deal["id"], "u_kevin", {"AWAITING_APPROVAL", "NO_AGREEMENT"})
    assert snap["deal"]["status"] == "AWAITING_APPROVAL", snap["deal"]["conflicts"]
