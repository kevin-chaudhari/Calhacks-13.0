"""Safety net: a deal can't stay stuck at NEGOTIATING. If its negotiation task stops without moving
the deal on (the rare stuck-after-leaving race), the housekeeping check restarts it; a deal that is
still negotiating is left alone."""
import asyncio
import contextlib
import time

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_flow import GOAL, h


@pytest.fixture()
def client():
    from rally.main import _buckets, app, rally
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        _buckets.clear()
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        c.rally = rally
        yield c


def negotiating_deal(c, monkeypatch) -> str:
    monkeypatch.setattr(c.rally.s, "round_delay_s", 0.3)       # slow rounds: negotiation is still running
    g = c.post("/v1/goals:compile", json={"text": GOAL}, headers=h(c, "u_kevin")).json()
    g = c.patch(f"/v1/goals/{g['id']}", json={"groupMax": 5}, headers=h(c, "u_kevin")).json()
    i = c.post("/v1/intents", json={"goalId": g["id"], "privatePrefs": g["suggestedPrefs"]}, headers=h(c, "u_kevin")).json()
    m = c.post(f"/v1/intents/{i['id']}/matches", json={}, headers=h(c, "u_kevin")).json()
    d = c.post("/v1/deals", json={"intentId": i["id"], "candidateIntentIds": m["selectedIntentIds"]},
               headers=h(c, "u_kevin")).json()["id"]
    end = time.time() + 5
    while time.time() < end and any(x["state"] == "invited" for x in status(c, d)["members"]):
        time.sleep(0.05)
    assert c.post(f"/v1/deals/{d}/negotiate", headers=h(c, "u_kevin")).status_code == 202
    return d


def status(c, d):
    return c.get(f"/v1/deals/{d}/snapshot", headers=h(c, "u_kevin")).json()


def kill_task(c, d):
    """What the race leaves behind: the deal's negotiation task gone, nothing started in its place."""
    async def kill():
        t = c.rally.tasks[d]
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
    c.portal.call(kill)


def settle(c, d, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        s = status(c, d)
        if s["deal"]["status"] in {"AWAITING_APPROVAL", "NO_AGREEMENT", "FAILED"}:
            return s
        if s["deal"]["vendorReview"]:
            staff = {"p_ottercove": "v_marcus", "p_kelpline": "v_lena"}[s["deal"]["vendorReview"]["providerId"]]
            c.post(f"/v1/vendor/requests/{d}/quote", json={"action": "approve"}, headers=h(c, staff))
        time.sleep(0.05)
    return s


def test_a_negotiation_whose_task_stopped_is_restarted(client, monkeypatch):
    c = client
    d = negotiating_deal(c, monkeypatch)
    kill_task(c, d)
    time.sleep(1.0)
    assert status(c, d)["deal"]["status"] == "NEGOTIATING"          # stuck, exactly like the bug
    assert c.portal.call(c.rally.revive_stalled) == [d]
    s = settle(c, d)
    assert s["deal"]["status"] == "AWAITING_APPROVAL", s["deal"]["status"]
    assert any(e["type"] == "deal.revived" for e in s["events"])


def test_a_negotiation_still_running_is_left_alone(client, monkeypatch):
    c = client
    d = negotiating_deal(c, monkeypatch)
    task = c.rally.tasks[d]
    assert c.portal.call(c.rally.revive_stalled) == []
    assert c.rally.tasks[d] is task                                    # no second mediator on the same deal
    assert settle(c, d)["deal"]["status"] == "AWAITING_APPROVAL"


def test_demo_reset_survives_tasks_left_from_a_closed_event_loop(client):
    held = {}

    async def start():
        held["t"] = asyncio.get_running_loop().create_task(asyncio.sleep(100))
        await asyncio.sleep(0)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(start())
    loop.close()                                   # its task is still pending, on a loop that's gone
    client.rally.tasks["d_old"] = held["t"]
    assert client.post("/v1/demo/reset", json={"scenario": "scuba"}).status_code == 200
    assert "d_old" not in client.rally.tasks
