"""Hold-until-trip payments and fraud reports: Parley holds the money, the vendor is paid only after
the trip, and vendors reported by people on two different trips are frozen and everyone is refunded."""
import asyncio
import contextlib
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_flow import h
from tests.integration.test_priorities_api import WiderFinder

TODAY = "2026-10-24"


@pytest.fixture()
def client():
    from rally.core import Settings
    from rally.discovery import VendorFinder
    from rally.main import _buckets, app, rally
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.personas = c.get("/v1/demo/personas").json()
        c.tokens = {p["id"]: p["token"] for p in c.personas}
        c.rally, c.buckets = rally, _buckets
        yield c
    rally.s.demo_today = TODAY
    rally.finder = VendorFinder(Settings())


@contextlib.contextmanager
def clock(c, day: str):
    """Move Parley's 'today' (after trips are booked: the compiler reads it too)."""
    c.rally.s.demo_today = day
    try:
        yield
    finally:
        c.rally.s.demo_today = TODAY


def snap(c, deal_id, who):
    return c.get(f"/v1/deals/{deal_id}/snapshot", headers=h(c, who)).json()


def until(c, deal_id, who, statuses, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        s = snap(c, deal_id, who)
        if s["deal"]["status"] in statuses:
            return s
        if s["deal"]["vendorReview"]:
            staff = next(p["id"] for p in c.personas if p.get("providerId") == s["deal"]["vendorReview"]["providerId"])
            c.post(f"/v1/vendor/requests/{deal_id}/quote", json={"action": "approve"}, headers=h(c, staff))
        time.sleep(0.05)
    raise AssertionError(f"{deal_id} never reached {statuses}; last {s['deal']['status']}")


def staff_of(c, provider_id):
    return next(p["id"] for p in c.personas if p.get("providerId") == provider_id)


def quoted_trip(c, who):
    """A solo scuba trip with a quote waiting for approval."""
    c.buckets.clear()
    deal_id = c.post("/v1/demo/launch", json={"scenario": "solo"}, headers=h(c, who)).json()["dealId"]
    return until(c, deal_id, who, {"AWAITING_APPROVAL"})


def booked_trip(c, who="u_kevin", confirm=True):
    """Approved and committed by the traveller; the vendor confirms the booking."""
    s = quoted_trip(c, who)
    d = s["deal"]
    r = c.post(f"/v1/deals/{d['id']}/approvals", headers=h(c, who),
               json={"proposalVersion": d["currentProposalVersion"], "quoteId": d["chosenQuoteId"], "autoCommit": True})
    assert r.status_code == 200, r.text
    s = until(c, d["id"], who, {"COMMITTED"})
    vendor = s["deal"]["escrow"]["providerId"]
    if confirm:
        assert c.post(f"/v1/vendor/requests/{d['id']}/booking", headers=h(c, staff_of(c, vendor))).status_code == 200
    return snap(c, d["id"], who)


def report(c, who, s, reason="They never showed up and stopped answering."):
    return c.post(f"/v1/vendors/{s['deal']['escrow']['providerId']}/reports", headers=h(c, who),
                  json={"dealId": s["deal"]["id"], "reason": reason})


def test_money_is_held_until_after_the_trip(client):
    s = booked_trip(client)
    e = s["deal"]["escrow"]
    trip = s["proposals"][-1]["terms"]["date"]
    assert e["status"] == "holding" and e["amount"] == s["commitments"][0]["amount"]
    assert e["releaseAfter"] == (date.fromisoformat(trip) + timedelta(days=2)).isoformat()
    assert any(ev["type"] == "escrow.holding" for ev in s["events"])
    asyncio.run(client.rally.release_due())                       # today is before the trip: nothing paid
    assert snap(client, s["deal"]["id"], "u_kevin")["deal"]["escrow"]["status"] == "holding"


def test_the_vendor_is_paid_once_the_traveller_confirms_the_trip(client):
    c = client
    s = booked_trip(c)
    d, trip = s["deal"]["id"], s["proposals"][-1]["terms"]["date"]
    r = c.post(f"/v1/deals/{d}/trip-happened", headers=h(c, "u_kevin"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "TRIP_NOT_YET"
    with clock(c, trip):
        assert c.post(f"/v1/deals/{d}/trip-happened", headers=h(c, "u_kevin")).json()["status"] == "released"
    assert any(ev["type"] == "escrow.released" for ev in snap(c, d, "u_kevin")["events"])


def test_unreported_trips_pay_out_when_the_dispute_window_closes(client):
    c = client
    s = booked_trip(c)
    with clock(c, s["deal"]["escrow"]["releaseAfter"]):
        assert asyncio.run(c.rally.release_due()) == [s["deal"]["id"]]


def test_no_payout_for_a_booking_the_vendor_never_confirmed(client):
    c = client
    s = booked_trip(c, confirm=False)
    with clock(c, "2027-06-01"):
        assert asyncio.run(c.rally.release_due()) == []
    assert snap(c, s["deal"]["id"], "u_kevin")["deal"]["escrow"]["status"] == "holding"


def test_a_report_holds_that_trips_payout_but_one_report_freezes_nobody(client):
    c = client
    s = booked_trip(c)
    r = report(c, "u_kevin", s)
    assert r.status_code == 200 and not r.json()["vendorFrozen"] and r.json()["escrow"]["status"] == "disputed"
    with clock(c, "2027-06-01"):
        assert asyncio.run(c.rally.release_due()) == []          # disputed money is never paid out
    other = booked_trip(c, "u_ana")                               # the vendor still gets new customers
    assert other["deal"]["escrow"]["providerId"] == s["deal"]["escrow"]["providerId"]


def test_only_people_who_booked_and_paid_can_report(client):
    c = client
    s = booked_trip(c)
    assert report(c, "u_ana", s).status_code == 403                    # not a member of that trip
    assert report(c, "u_kevin", s, reason="bad").status_code == 422    # say what went wrong
    q = quoted_trip(c, "u_maya")                                       # quoted, not paid yet
    r = c.post(f"/v1/vendors/{q['quotes'][0]['providerId']}/reports", headers=h(c, "u_maya"),
               json={"dealId": q["deal"]["id"], "reason": "Seems shady to me."})
    assert r.status_code == 409


def test_the_same_person_reporting_twice_does_not_freeze_a_vendor(client):
    c = client
    first, second = booked_trip(c), booked_trip(c)
    report(c, "u_kevin", first)
    assert not report(c, "u_kevin", second).json()["vendorFrozen"]


def test_reports_from_two_trips_freeze_the_vendor_refund_everyone_and_stop_all_contact(client):
    c = client
    kevin, ana = booked_trip(c), booked_trip(c, "u_ana")
    vendor = kevin["deal"]["escrow"]["providerId"]
    waiting = quoted_trip(c, "u_maya")                                 # someone about to book it
    assert waiting["deal"]["chosenQuoteId"] and waiting["quotes"][0]["providerId"] == vendor

    report(c, "u_kevin", kevin)
    assert report(c, "u_ana", ana, reason="Took the deposit, no boat, no reply.").json()["vendorFrozen"]

    for who, s in (("u_kevin", kevin), ("u_ana", ana)):
        after = snap(c, s["deal"]["id"], who)
        assert after["deal"]["escrow"]["status"] == "refunded"
        assert all(x["state"] == "refunded" for x in after["commitments"])
    assert snap(c, waiting["deal"]["id"], "u_maya")["deal"]["status"] == "CANCELLED"

    staff = staff_of(c, vendor)
    r = c.post(f"/v1/vendor/requests/{kevin['deal']['id']}/booking", headers=h(c, staff))
    assert r.status_code == 403 and r.json()["error"]["code"] == "VENDOR_FROZEN"
    assert c.get("/v1/vendor/dashboard", headers=h(c, staff)).json()["frozen"]

    fresh = quoted_trip(c, "u_kai")                                    # a new trip never contacts it
    address = c.rally.provider(vendor)["agentAddress"]
    assert all(q["providerId"] != vendor for q in fresh["quotes"])
    assert all(address not in (m["toId"], m["fromId"]) for m in fresh["agentMessages"])


def test_vendors_booked_on_their_own_website_are_never_held(client):
    c = client
    c.rally.finder = WiderFinder()
    c.buckets.clear()
    g = c.post("/v1/goals:compile", json={"text": "Rock climbing in Yosemite next month under $400, I'm a beginner"},
               headers=h(c, "u_kevin")).json()
    g = c.patch(f"/v1/goals/{g['id']}", json={"groupMax": 1, "groupMin": 1}, headers=h(c, "u_kevin")).json()
    it = c.post("/v1/intents", json={"goalId": g["id"], "privatePrefs": g["suggestedPrefs"]}, headers=h(c, "u_kevin")).json()
    d = c.post("/v1/deals", json={"intentId": it["id"], "solo": True}, headers=h(c, "u_kevin")).json()["id"]
    s = until(c, d, "u_kevin", {"AWAITING_APPROVAL"})
    c.post(f"/v1/deals/{d}/approvals", headers=h(c, "u_kevin"),
           json={"proposalVersion": s["deal"]["currentProposalVersion"], "quoteId": s["deal"]["chosenQuoteId"]})
    s = until(c, d, "u_kevin", {"COMMITTED"})
    assert s["deal"]["escrow"] is None
    none = next(ev["summary"] for ev in s["events"] if ev["type"] == "escrow.none")
    assert "can't hold this money" in none and "never through a link someone sends you" in none
