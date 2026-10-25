"""Control room endpoints: one-click scenarios, seat links, live metrics."""
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from rally.main import app
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        yield c


def h(c, who):
    return {"Authorization": f"Bearer {c.tokens[who]}"}


def snapshot_until(c, deal_id, pred, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        s = c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, "u_kevin")).json()
        if pred(s):
            return s
        time.sleep(0.05)
    raise AssertionError(s["deal"]["status"])


@pytest.mark.parametrize("scenario", ["scuba", "skydiving", "kayaking", "solo"])
def test_one_click_launch_reaches_an_agreed_plan(client, scenario):
    c = client
    r = c.post("/v1/demo/launch", json={"scenario": scenario}, headers=h(c, "u_kevin"))
    assert r.status_code == 200, r.text
    d = r.json()["dealId"]
    s = snapshot_until(c, d, lambda s: s["deal"]["status"] in ("AWAITING_APPROVAL", "NO_AGREEMENT")
                       or s["deal"]["vendorReview"])
    assert s["deal"]["status"] != "NO_AGREEMENT"
    assert s["deal"]["negotiationMs"] is not None and s["deal"]["negotiationMs"] >= 0
    m = c.get("/v1/metrics").json()
    assert m["agreed"] == 1 and m["hardConstraintViolations"] == 0 and m["proposalsChecked"] > 0
    assert m["agentMessages"] == len(s["agentMessages"]) and m["meanRounds"] >= 1


def test_seat_links_cover_every_member_and_the_quoting_vendor(client):
    c = client
    d = c.post("/v1/demo/launch", json={"scenario": "scuba"}, headers=h(c, "u_kevin")).json()["dealId"]
    snapshot_until(c, d, lambda s: s["deal"]["vendorReview"] is not None)
    seats = c.get(f"/v1/demo/seats/{d}", headers=h(c, "u_kevin")).json()
    names = {x["name"]: x for x in seats}
    assert {"Kevin", "Ana", "Ravi", "Maya", "Kai", "Marcus Bell"} <= set(names)
    assert names["Ana"]["url"].endswith(f"/join?d={d}&t={c.tokens['u_ana']}")
    assert names["Marcus Bell"]["role"] == "vendor" and "&v=v_marcus" in names["Marcus Bell"]["url"]
    assert c.get(f"/v1/demo/seats/{d}", headers=h(c, "u_ana")).status_code == 403


def test_unknown_scenario_is_refused(client):
    r = client.post("/v1/demo/launch", json={"scenario": "moon"}, headers=h(client, "u_kevin"))
    assert r.status_code == 400 and r.json()["error"]["code"] == "UNKNOWN_SCENARIO"


def test_gear_for_the_agreed_plan_includes_the_rent_or_buy_comparison(client):
    c = client
    d = c.post("/v1/demo/launch", json={"scenario": "scuba"}, headers=h(c, "u_kevin")).json()["dealId"]
    snapshot_until(c, d, lambda s: s["deal"]["vendorReview"] is not None)
    r = c.get(f"/v1/deals/{d}/gear", headers=h(c, "u_ana"))
    assert r.status_code == 200, r.text
    gear = r.json()
    assert gear["activity"] == "scuba_diving" and gear["mode"] == "estimate" and gear["items"]
    assert gear["rentals"] and gear["rentals"][0]["term"] == "gear_included"
    assert c.get(f"/v1/deals/{d}/gear", headers=h(c, "u_jordan") if "u_jordan" in c.tokens else {}).status_code in (401, 403)
    byo = c.get("/v1/gear/scuba_diving?gear_included=false", headers=h(c, "u_kevin")).json()
    assert {"bcd", "regulator"} <= {i["key"] for i in byo["items"]}
    assert c.get("/v1/gear/curling", headers=h(c, "u_kevin")).status_code == 404
    assert c.get("/v1/health").json()["gear"]["mode"] == "estimate"
