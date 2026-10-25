"""Across trips, each agent learns which vendors always quote far above the others, and stops
contacting them: no request, nothing in that vendor's portal."""
import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_flow import h, settle

OTTER, OTTER_STAFF = "p_ottercove", "v_marcus"


@pytest.fixture()
def client():
    from rally.main import _buckets, app, rally
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        c.rally, c.buckets = rally, _buckets
        tiers = c.get("/v1/vendor/dashboard", headers=h(c, OTTER_STAFF)).json()["provider"]["tiers"]
        r = c.patch("/v1/vendor/provider", headers=h(c, OTTER_STAFF),
                    json={"tiers": [{**t, "pricePerPerson": round(t["pricePerPerson"] * 1.5)} for t in tiers]})
        assert r.status_code == 200, r.text
        yield c


def solo_trip(c) -> dict:
    c.buckets.clear()
    deal_id = c.post("/v1/demo/launch", json={"scenario": "solo"}, headers=h(c, "u_kevin")).json()["dealId"]
    return settle(c, deal_id)


def contacted(c, snap) -> bool:
    otter = c.rally.provider(OTTER)["agentAddress"]
    return any(m["toId"] == otter for m in snap["agentMessages"])


def test_an_always_expensive_vendor_is_dropped_after_three_trips(client):
    c = client
    for _ in range(3):
        snap = solo_trip(c)
        assert contacted(c, snap)                       # still asked while the agent is learning
    learned = {v["vendorId"]: v for v in c.get("/v1/agent/vendors", headers=h(c, "u_kevin")).json()}
    assert learned[OTTER]["avoid"] and learned[OTTER]["trips"] == 3 and learned[OTTER]["premium"] > 0.15
    assert not learned["p_kelpline"]["avoid"]

    snap = solo_trip(c)
    assert snap["deal"]["status"] == "AWAITING_APPROVAL"
    assert not contacted(c, snap)
    assert all(q["providerId"] != OTTER for q in snap["quotes"])
    skipped = [e["summary"] for e in snap["events"] if e["type"] == "vendor.skipped"]
    assert len(skipped) == 1 and skipped[0].startswith("Skipped Otter Cove Dive Co.: it quoted ")
    portal = c.get("/v1/vendor/requests", headers=h(c, OTTER_STAFF)).json()
    assert snap["deal"]["id"] not in {r["id"] for r in portal}     # the vendor never hears of it


def test_a_group_skips_a_vendor_only_when_most_members_learned_to(client):
    c = client
    for _ in range(3):
        solo_trip(c)                                    # only Kevin's agent has learned
    c.buckets.clear()
    deal_id = c.post("/v1/demo/launch", json={"scenario": "scuba"}, headers=h(c, "u_kevin")).json()["dealId"]
    snap = settle(c, deal_id)
    assert len([m for m in snap["members"] if m["state"] == "joined"]) > 2
    assert contacted(c, snap) and not any(e["type"] == "vendor.skipped" for e in snap["events"])


def test_demo_reset_forgets_what_agents_learned(client):
    c = client
    for _ in range(3):
        solo_trip(c)
    c.post("/v1/demo/reset", json={"scenario": "scuba"})
    assert c.get("/v1/agent/vendors", headers=h(c, "u_kevin")).json() == []
