"""Gear list + Bright Data parsing. Live calls are mocked at the HTTP layer (httpx.MockTransport)."""
import asyncio
import json

import httpx
import pytest

from rally import gear as g
from rally.core import Settings


def test_price_parsing_handles_store_formats():
    assert g.parse_price("$1,299.99") == 1299.99
    assert g.parse_price("Now $24.97") == 24.97
    assert g.parse_price("$20 - $40") == 20.0
    assert g.parse_price(19.5) == 19.5
    assert g.parse_price({"value": 12}) == 12.0
    assert g.parse_price("Free") is None and g.parse_price(None) is None and g.parse_price(True) is None


def test_gear_needed_depends_on_the_plan():
    byo = {i["key"] for i in g.needed_items("scuba_diving", {"gear_included": False})}
    rented = {i["key"] for i in g.needed_items("scuba_diving", {"gear_included": True})}
    undecided = {i["key"]: i["status"] for i in g.needed_items("boat_dive", {})}       # synonym resolves
    assert {"wetsuit", "bcd", "regulator", "mask"} <= byo
    assert rented == {"defog"}                                                        # only always-items
    assert undecided["wetsuit"] == "maybe" and undecided["defog"] == "needed"


def test_pick_drops_accessories_and_duplicates():
    offers = [
        {"title": "Fin strap replacement", "price": 6.0, "shop": "Walmart", "link": "a"},
        {"title": "Cressi Pro Light fins", "price": 89.0, "shop": "REI", "link": "b"},
        {"title": "Cressi Pro Light fins", "price": 89.0, "shop": "REI", "link": "c"},
        {"title": "Mares Avanti fins", "price": 74.5, "shop": "Walmart", "link": "d"},
    ]
    picked = g.pick(offers, [25, 300])
    assert [o["price"] for o in picked] == [74.5, 89.0]


SERP = {"shopping": [
    {"title": "Seac 7mm Wetsuit", "price": "$229.00", "shop": "Walmart", "link": "https://walmart.com/ip/1", "rating": 4.4},
    {"title": "Wetsuit zipper pull", "price": "$3.99", "shop": "Amazon", "link": "https://amazon.com/x"},
    {"title": "Cressi Lontra 7mm", "price": "$184.95", "shop": "Leisure Pro", "link": "https://leisurepro.com/p"},
]}


def settings(monkeypatch, tmp_path, **env):
    monkeypatch.setenv("RALLY_RUNTIME_DIR", str(tmp_path))
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings()


def test_serp_prices_are_live_and_cached(monkeypatch, tmp_path):
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append(body)
        assert req.url == "https://api.brightdata.com/request"
        assert req.headers["authorization"] == "Bearer k_test" and body["zone"] == "serp_rally"
        assert "brd_json=1" in body["url"] and body["format"] == "raw"
        return httpx.Response(200, json=SERP)

    s = settings(monkeypatch, tmp_path, GEAR_PRICES="brightdata", BRIGHTDATA_API_KEY="k_test",
                 BRIGHTDATA_SERP_ZONE="serp_rally")
    p = g.GearPricer(s, transport=httpx.MockTransport(handler))
    out = asyncio.run(p.price("kayaking", {"wetsuit_included": False}))
    wetsuit = next(i for i in out["items"] if i["key"] == "wetsuit")
    assert out["mode"] == "brightdata" and wetsuit["provenance"] == "live"
    assert wetsuit["price"] == 184.95 and wetsuit["offers"][0]["shop"] == "Leisure Pro"
    assert all(o["price"] > 50 for o in wetsuit["offers"])               # the $3.99 zipper pull is gone
    calls = len(seen)
    asyncio.run(g.GearPricer(s, transport=httpx.MockTransport(handler)).price("kayaking", {"wetsuit_included": False}))
    assert len(seen) == calls                                            # second run served from the disk cache
    assert (tmp_path / "gear_cache.json").exists()


def test_walmart_dataset_polls_a_slow_snapshot(monkeypatch, tmp_path):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(g.asyncio, "sleep", lambda *_: real_sleep(0))
    polls = {"n": 0}

    def handler(req: httpx.Request):
        if req.url.path == "/datasets/v3/scrape":
            q = dict(req.url.params)
            assert q["dataset_id"] == "gd_walmart" and q["discover_by"] == "keyword"
            assert json.loads(req.content)["input"][0]["keyword"]
            return httpx.Response(202, json={"snapshot_id": "s_1"})
        if req.url.path == "/datasets/v3/progress/s_1":
            polls["n"] += 1
            return httpx.Response(200, json={"status": "ready" if polls["n"] > 1 else "running"})
        if req.url.path == "/datasets/v3/snapshot/s_1":
            return httpx.Response(200, json=[
                {"title": "Ozark Trail 10L Dry Bag", "final_price": 12.97, "url": "https://walmart.com/ip/9", "rating": 4.6},
                {"title": "broken row", "error": "blocked"},
            ])
        return httpx.Response(404)

    s = settings(monkeypatch, tmp_path, GEAR_PRICES="brightdata", BRIGHTDATA_API_KEY="k",
                 BRIGHTDATA_WALMART_DATASET_ID="gd_walmart")
    out = asyncio.run(g.GearPricer(s, transport=httpx.MockTransport(handler)).price("kayaking", {"wetsuit_included": True}))
    bag = next(i for i in out["items"] if i["key"] == "drybag")
    assert bag["provenance"] == "live" and bag["offers"][0] == {
        "title": "Ozark Trail 10L Dry Bag", "price": 12.97, "shop": "Walmart",
        "link": "https://walmart.com/ip/9", "rating": 4.6, "source": "walmart"}


def test_a_failing_source_falls_back_to_labelled_estimates(monkeypatch, tmp_path):
    s = settings(monkeypatch, tmp_path, GEAR_PRICES="brightdata", BRIGHTDATA_API_KEY="k", BRIGHTDATA_SERP_ZONE="z")
    p = g.GearPricer(s, transport=httpx.MockTransport(lambda r: httpx.Response(401, text="bad key")))
    out = asyncio.run(p.price("skydiving", {}))
    assert {i["provenance"] for i in out["items"]} == {"estimate"}
    assert all("401" in i["error"] for i in out["items"]) and p.status()["errors"] == len(out["items"])


@pytest.mark.parametrize("env", [{}, {"GEAR_PRICES": "brightdata"}, {"GEAR_PRICES": "brightdata", "BRIGHTDATA_API_KEY": "k"}])
def test_without_credentials_nothing_is_called(monkeypatch, tmp_path, env):
    def boom(_):
        raise AssertionError("no network without credentials")
    s = settings(monkeypatch, tmp_path, **env)
    out = asyncio.run(g.GearPricer(s, transport=httpx.MockTransport(boom)).price("scuba_diving", {"gear_included": False}))
    assert out["mode"] == "estimate" and out["liveCount"] == 0 and out["totalRequired"] > 1000
