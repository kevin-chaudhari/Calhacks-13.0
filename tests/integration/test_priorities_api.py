"""Priorities over HTTP: they are validated when the intent is published, and when no vendor found so
far satisfies them, the agents search wider and ask more vendors instead of settling."""
import pytest
from fastapi.testclient import TestClient

from rally.core import Settings
from rally.discovery import VendorFinder, _with_window, provider_record
from tests.integration.test_api_flow import GOAL as SCUBA, h, wait_for

GOAL = "Rock climbing in Yosemite next month under $400, I'm a beginner"
YOSEMITE = {"label": "Yosemite Valley, CA", "lat": 37.7456, "lng": -119.5936}


def shop(name: str, price: float, fmt: str) -> dict:
    site = f"https://{name.split()[0].lower()}.example"
    offer = {"title": f"{fmt} climb", "price": price, "unit": "per_person", "format": fmt, "includes": [],
             "evidence": f"{fmt.title()} climb: ${price:.0f} per person."}
    return provider_record("rock_climbing", YOSEMITE, {"name": name, "site": site}, [offer], None, site, 0)


class WiderFinder:
    """Bright Data stand-in: the first search reads 6 vendors and finds only a cheap group class;
    a wider search (12) also reaches a shop that teaches private lessons."""
    mode = "brightdata"

    def __init__(self):
        self.limits: list[int] = []

    def status(self) -> dict:
        return {"mode": self.mode}

    async def find(self, activity, place, window=None, limit=6, refresh=False):
        self.limits.append(limit)
        vendors = [shop("Granite Group Classes", 100, "group")]
        if limit >= 12:
            vendors.append(shop("Summit Private Guides", 250, "private"))
        return _with_window({"mode": "brightdata", "vendors": vendors, "deals": [], "query": "q", "errors": []},
                            window)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from rally.main import app, rally
    monkeypatch.setenv("RALLY_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        c.rally = rally
        yield c
    rally.finder = VendorFinder(Settings())


def goal(c, text=GOAL, size=1):
    g = c.post("/v1/goals:compile", json={"text": text}, headers=h(c, "u_kevin")).json()
    return c.patch(f"/v1/goals/{g['id']}", json={"groupMax": size, "groupMin": 1 if size == 1 else 2},
                   headers=h(c, "u_kevin")).json()


def publish(c, g, **changes):
    prefs = {**g["suggestedPrefs"], **changes}
    return c.post("/v1/intents", json={"goalId": g["id"], "privatePrefs": prefs}, headers=h(c, "u_kevin"))


@pytest.mark.parametrize("changes, field", [
    ({"priorities": {"price_per_person": "high"}}, "price_per_person"),       # the budget already caps price
    ({"priorities": {"stargazing": "must"}}, "stargazing"),                   # not a term of this goal
    ({"best": {"date": "next-tuesday"}}, "date"),                             # used to crash the whole group
])
def test_bad_priorities_are_refused_at_publish(client, changes, field):
    r = publish(client, goal(client, SCUBA, size=5), **changes)
    assert r.status_code == 422 and field in r.json()["error"]["fields"], r.text


def test_a_ranked_term_needs_a_favourite(client):
    g = goal(client, SCUBA, size=5)
    best = {k: v for k, v in g["suggestedPrefs"]["best"].items() if k != "site"}
    r = publish(client, g, best=best, priorities={"site": "high"})
    assert r.status_code == 422 and "site" in r.json()["error"]["fields"]


def test_without_priorities_the_cheapest_vendor_wins_from_the_first_search(client):
    client.rally.finder = finder = WiderFinder()
    intent = publish(client, goal(client)).json()
    deal = client.post("/v1/deals", json={"intentId": intent["id"], "solo": True}, headers=h(client, "u_kevin")).json()
    snap = wait_for(client, deal["id"], "u_kevin", {"AWAITING_APPROVAL", "NO_AGREEMENT"})
    chosen = next(q for q in snap["quotes"] if q["id"] == snap["deal"]["chosenQuoteId"])
    assert chosen["providerName"] == "Granite Group Classes" and finder.limits == [6]


def test_unsatisfied_must_have_makes_the_agents_ask_more_vendors(client):
    client.rally.finder = finder = WiderFinder()
    g = goal(client)
    intent = publish(client, g, best={**g["suggestedPrefs"]["best"], "format": "Private lesson"},
                     priorities={"format": "must"}).json()
    deal = client.post("/v1/deals", json={"intentId": intent["id"], "solo": True}, headers=h(client, "u_kevin")).json()
    snap = wait_for(client, deal["id"], "u_kevin", {"AWAITING_APPROVAL", "NO_AGREEMENT"})
    assert snap["deal"]["status"] == "AWAITING_APPROVAL", snap["deal"]["conflicts"]
    chosen = next(q for q in snap["quotes"] if q["id"] == snap["deal"]["chosenQuoteId"])
    assert (chosen["providerName"], chosen["pricePerPerson"]) == ("Summit Private Guides", 250.0)
    assert snap["proposals"][-1]["terms"]["format"] == "Private lesson"
    assert finder.limits == [6, 12]
    assert any(e["type"] == "vendors.more" for e in snap["events"])


class GroupOnlyFinder(WiderFinder):
    """Every shop in reach teaches group classes only; the wider search adds one more of them."""

    async def find(self, activity, place, window=None, limit=6, refresh=False):
        self.limits.append(limit)
        vendors = [shop("Granite Group Classes", 100, "group")]
        if limit >= 12:
            vendors.append(shop("Valley Group Climbs", 120, "group"))
        return _with_window({"mode": "brightdata", "vendors": vendors, "deals": [], "query": "q", "errors": []},
                            window)


def test_search_stops_when_a_wider_search_finds_nobody_new(client):
    client.rally.finder = finder = GroupOnlyFinder()
    g = goal(client)
    intent = publish(client, g, best={**g["suggestedPrefs"]["best"], "format": "Private lesson"},
                     priorities={"format": "must"}).json()
    deal = client.post("/v1/deals", json={"intentId": intent["id"], "solo": True}, headers=h(client, "u_kevin")).json()
    snap = wait_for(client, deal["id"], "u_kevin", {"AWAITING_APPROVAL", "NO_AGREEMENT"})
    assert snap["deal"]["status"] == "NO_AGREEMENT"          # never settles for a group class
    assert finder.limits == [6, 12, 20]            # 12 found a new shop; 20 found nobody new, so it stopped
    assert not snap["quotes"]
