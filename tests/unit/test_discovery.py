"""Vendor discovery for any activity: Bright Data SERP (local pack) + Web Unlocker pages + offer
extraction with a verbatim-evidence check. Bright Data is mocked at the HTTP layer with its documented
parsed-JSON shape; the 'model' is a fake that also tries to slip in an invented price."""
import asyncio
import json

import httpx
import pytest

from rally import discovery as dv
from rally.core import Settings

SERP_MAIN = {
    "general": {"query": "rock climbing guide near Yosemite Valley, CA"},
    "snack_pack": [
        {"name": "Yosemite Mountaineering School", "site": "https://ymsclimb.example", "address": "Yosemite Village, CA",
         "phone": "+1 209-555-0101", "rating": 4.8, "reviews_cnt": 412, "maps_link": "https://maps.google.com/?cid=1"},
        {"name": "Granite Guides", "site": "https://graniteguides.example", "address": "El Portal, CA",
         "rating": 4.6, "reviews_cnt": 88, "maps_link": "https://maps.google.com/?cid=2"},
        {"name": "Valley Crag Co.", "link": "https://www.yelp.com/biz/valley-crag", "rating": 4.1, "reviews_cnt": 12},
    ],
    "organic": [
        {"title": "Tuolumne Climbing Collective | Guided climbs", "link": "https://tuolumne.example",
         "description": "Intro to granite: $145 per person, half day."},
        {"title": "Best climbing in Yosemite - Tripadvisor", "link": "https://www.tripadvisor.com/x"},
    ],
}
SERP_DEALS = {"organic": [
    {"title": "Yosemite climbing lesson - $119 (40% off)", "link": "https://www.groupon.com/deals/yosemite-climb",
     "description": "Half-day intro climbing class for one."},
    {"title": "Climbing gear sale", "link": "https://shop.example/sale", "description": "No prices here"},
]}
PAGES = {
    "ymsclimb.example": """# Yosemite Mountaineering School
## Rates
Go Climb a Rock (beginner group class): $172 per person, 7 hours.
Private guided climb for one: $395 per person.
Private guiding for groups: $720 per group, up to 4 people.
Gift cards available from $50.""",
    "graniteguides.example": "Granite Guides. Call us for rates. Book online.",
}


def handler(log):
    def h(req: httpx.Request):
        body = json.loads(req.content)
        log.append(body)
        if "google.com/search" in body["url"]:
            assert "brd_json=1" in body["url"] and body["zone"] == "serp_z"
            return httpx.Response(200, json=SERP_DEALS if "deal" in body["url"] else SERP_MAIN)
        assert body["zone"] == "unl_z" and body["data_format"] == "markdown"
        host = dv._domain(body["url"])
        return httpx.Response(200, text=PAGES.get(host, "nothing"))
    return h


def fake_model(page, vendor, activity):
    if "Mountaineering" not in vendor:
        return []
    return [
        {"title": "Go Climb a Rock", "price": 172, "unit": "per_person", "format": "group",
         "evidence": "Go Climb a Rock (beginner group class): $172 per person, 7 hours."},
        {"title": "Private guided climb", "price": 395, "unit": "per_person", "format": "private",
         "evidence": "Private guided climb for one: $395 per person."},
        {"title": "Private group guiding", "price": 720, "unit": "per_group", "group_max": 4, "format": "private",
         "evidence": "Private guiding for groups: $720 per group, up to 4 people."},
        {"title": "Sunset climb", "price": 99, "unit": "per_person",                   # invented: not on the page
         "evidence": "Sunset climb special $99 per person"},
        {"title": "Go Climb a Rock", "price": 17, "unit": "per_person",                # misread number
         "evidence": "Go Climb a Rock (beginner group class): $172 per person, 7 hours."},
    ]


@pytest.fixture()
def settings(monkeypatch, tmp_path):
    monkeypatch.setenv("RALLY_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "k")
    monkeypatch.setenv("BRIGHTDATA_SERP_ZONE", "serp_z")
    monkeypatch.setenv("BRIGHTDATA_UNLOCKER_ZONE", "unl_z")
    return Settings()


PLACE = {"label": "Yosemite Valley, CA", "lat": 37.7456, "lng": -119.5936}


def test_finds_real_vendors_and_only_verified_prices(settings):
    log = []
    f = dv.VendorFinder(settings, transport=httpx.MockTransport(handler(log)), llm=fake_model)
    out = asyncio.run(f.find("rock_climbing", PLACE, ("2026-11-01", "2026-11-30")))
    names = [v["name"] for v in out["vendors"]]
    assert names[0] == "Yosemite Mountaineering School"                       # priced + best rated first
    assert "Valley Crag Co." in names and "Tuolumne Climbing Collective" in names
    yms = out["vendors"][0]
    assert sorted(o["price"] for o in yms["listedOffers"]) == [172, 395, 720]  # $99 and $17 rejected
    assert f.dropped_unverified == 2
    assert all(o["evidence"] in PAGES["ymsclimb.example"] for o in yms["listedOffers"])
    assert yms["provenance"] == "cached" and yms["source"] == "web" and yms["phone"] == "+1 209-555-0101"
    assert yms["rating"] == 4.8 and yms["reviews"] == 412 and len(yms["availableDates"]) == 30
    assert yms["tiers"][0] == {"min": 1, "max": 20, "pricePerPerson": 172.0, "includes": []}
    priv = {(t["min"], t["max"]): t["pricePerPerson"] for t in yms["formatTiers"]["Private lesson"]}
    assert priv[(1, 1)] == 395.0 and priv[(2, 2)] == 360.0 and priv[(4, 4)] == 180.0   # $720 / party of 4
    assert yms["formatTiers"]["Group lesson"][0]["pricePerPerson"] == 172.0
    from rally.providers import sheets
    sheet = sheets([yms])[0]
    terms = {"date": "2026-11-07", "format": "Private lesson"}
    assert sheet.price(terms, 1) == 395.0 and sheet.price(terms, 4) == 180.0 and sheet.price(terms, 5) == 395.0
    granite = next(v for v in out["vendors"] if v["name"] == "Granite Guides")
    assert granite["priced"] is False and granite["tiers"] == []              # "call us": shown, never priced
    tuol = next(v for v in out["vendors"] if v["name"] == "Tuolumne Climbing Collective")
    assert tuol["tiers"][0]["pricePerPerson"] == 145.0                         # from the search snippet
    assert out["deals"] == [{"title": "Yosemite climbing lesson - $119 (40% off)",
                             "link": "https://www.groupon.com/deals/yosemite-climb", "source": "groupon.com",
                             "price": 119.0, "snippet": "Half-day intro climbing class for one."}]
    # cached: a second search costs nothing
    calls = len(log)
    asyncio.run(dv.VendorFinder(settings, transport=httpx.MockTransport(handler(log)), llm=fake_model)
                .find("rock_climbing", PLACE))
    assert len(log) == calls


def test_rules_extractor_without_a_model(settings):
    f = dv.VendorFinder(settings, transport=httpx.MockTransport(handler([])), llm=None)
    f.llm, f.extractor = None, "rules"
    out = asyncio.run(f.find("rock_climbing", PLACE))
    yms = next(v for v in out["vendors"] if v["name"] == "Yosemite Mountaineering School")
    prices = sorted(o["price"] for o in yms["listedOffers"])
    assert prices == [172, 395, 720]                                          # gift card line skipped
    grp = next(o for o in yms["listedOffers"] if o["price"] == 720)
    assert grp["unit"] == "per_group" and grp["group_max"] == 4


def test_off_without_keys_and_no_network(monkeypatch, tmp_path):
    monkeypatch.setenv("RALLY_RUNTIME_DIR", str(tmp_path))
    for k in ("BRIGHTDATA_API_KEY", "BRIGHTDATA_SERP_ZONE"):
        monkeypatch.delenv(k, raising=False)

    def boom(_):
        raise AssertionError("no network without keys")
    out = asyncio.run(dv.VendorFinder(Settings(), transport=httpx.MockTransport(boom)).find("surfing", PLACE))
    assert out["mode"] == "off" and out["vendors"] == []


@pytest.mark.parametrize("offer,ok", [
    ({"price": 89, "evidence": "Lessons from $189 per person"}, False),       # 89 inside 189
    ({"price": 189, "evidence": "Lessons from $189 per person"}, True),
    ({"price": 1299.5, "evidence": "Full day $1,299.50"}, True),
    ({"price": 45, "evidence": "short"}, False),
])
def test_evidence_must_state_the_exact_price(offer, ok):
    page = "Lessons from $189 per person. Full day $1,299.50 for the boat."
    assert dv.verify_offer(offer, page) is ok


def test_per_group_packages_price_per_person_by_party_size():
    o = {"price": 720, "unit": "per_group", "group_max": 4}
    assert [dv.per_person(o, n) for n in (1, 2, 4, 5)] == [720.0, 360.0, 180.0, None]
