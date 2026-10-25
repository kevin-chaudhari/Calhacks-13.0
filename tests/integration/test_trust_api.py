"""Vendors found on the web are classified before anyone talks to them: a suspected fraud is never
contacted, an unverified vendor is flagged, and every level comes with its reasons."""
import json
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from rally.core import Settings
from rally.discovery import VendorFinder
from tests.integration.test_api_flow import h, settle
from tests.integration.test_any_activity import GOAL, publish

SERP = {"snack_pack": [
    {"name": "Yosemite Mountaineering School", "site": "https://ymsclimb.example", "address": "Yosemite Village, CA",
     "phone": "+1 209-555-0101", "rating": 4.8, "reviews_cnt": 412, "maps_link": "https://maps.google.com/?cid=1"},
    {"name": "Granite Guides", "site": "https://graniteguides.example", "address": "El Portal, CA",
     "rating": 4.6, "reviews_cnt": 88, "maps_link": "https://maps.google.com/?cid=2"},
], "organic": [
    {"title": "Valley Crag Co. | Climbing", "link": "https://valleycrag.example"},
    {"title": "Cheap Climbs Now | Best deals", "link": "https://cheapclimbsnow.example"},
]}
PAGES = {
    "ymsclimb.example": "Go Climb a Rock: $172 per person, 7 hours. Cancellation: full refund up to 48 hours before.",
    "graniteguides.example": "Beginner climb: $160 per person, half day.",
    "valleycrag.example": "Intro climb: $150 per person.",
    "cheapclimbsnow.example": "Guided climb: $60 per person. Payment by Zelle or wire transfer only.",
}
AGE_DAYS = {"ymsclimb.example": 4000, "graniteguides.example": 1500, "cheapclimbsnow.example": 20}
SCAM = "Cheap Climbs Now"


def handler(seen: list):
    def h(req: httpx.Request):
        if req.method == "GET":                                     # RDAP: domain registration date
            seen.append(req)
            domain = req.url.path.rsplit("/", 1)[-1]
            if domain not in AGE_DAYS:
                return httpx.Response(404)
            born = (date.today() - timedelta(days=AGE_DAYS[domain])).isoformat() + "T00:00:00Z"
            return httpx.Response(200, json={"events": [{"eventAction": "registration", "eventDate": born}]})
        body = json.loads(req.content)
        if "google.com/search" in body["url"]:
            return httpx.Response(200, json=SERP if "deal" not in body["url"] else {})
        return httpx.Response(200, text=PAGES.get(httpx.URL(body["url"]).host, ""))
    return h


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from rally.main import app, rally
    monkeypatch.setenv("RALLY_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "secret-key")
    monkeypatch.setenv("BRIGHTDATA_SERP_ZONE", "serp_z")
    monkeypatch.setenv("BRIGHTDATA_UNLOCKER_ZONE", "unl_z")
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.rdap = []
        rally.finder = VendorFinder(Settings(), transport=httpx.MockTransport(handler(c.rdap)))
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        c.rally = rally
        yield c
    rally.finder = VendorFinder(Settings())


def test_discover_labels_every_vendor_with_its_reasons(client):
    d = client.get("/v1/discover", params={"q": "rock climbing in Yosemite"}, headers=h(client, "u_kevin")).json()
    levels = {v["name"]: v["trust"]["level"] for v in d["vendors"]}
    assert levels == {"Yosemite Mountaineering School": "verified", "Granite Guides": "verified",
                      "Valley Crag Co.": "unverified", SCAM: "suspected_fraud"}
    record = next(v for v in d["vendors"] if v["name"] == SCAM)
    assert record["priced"] and record["tiers"][0]["pricePerPerson"] == 60     # the cheapest offer by far
    scam = record["trust"]
    assert {"asks to be paid in a way that can't be traced or refunded",
            "website only 20 days old and no map listing"} <= set(scam["reasons"])
    assert next(s for s in scam["signals"] if s["kind"] == "payment")["evidence"] == \
        "Payment by Zelle or wire transfer only."
    assert client.rdap and all("authorization" not in r.headers for r in client.rdap)   # key stays with Bright Data


def test_a_suspected_fraud_is_never_contacted_even_when_cheapest(client):
    c = client
    intent = publish(c, GOAL)
    deal = c.post("/v1/deals", json={"intentId": intent["id"], "solo": True}, headers=h(c, "u_kevin")).json()
    snap = settle(c, deal["id"])
    assert snap["deal"]["status"] == "AWAITING_APPROVAL", snap["deal"]["conflicts"]
    scam_id = next(p["id"] for p in c.rally.providers if p["name"] == SCAM)
    assert all(scam_id not in (m["toId"], m["fromId"]) and SCAM not in m["summary"]
               for m in snap["agentMessages"] if m["type"] != "VendorResults")
    assert all(q["providerId"] != scam_id for q in snap["quotes"])
    events = {e["type"]: e["summary"] for e in snap["events"]}
    assert events["vendor.fraud"].startswith(f"Not contacting {SCAM}: suspected fraud (")
    assert events["vendor.unverified"].startswith("Valley Crag Co. is unverified: no Google Maps listing")
