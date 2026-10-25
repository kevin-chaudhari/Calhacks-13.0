"""Gear a member has to bring, priced from real stores via Bright Data. Owner: platform (Kevin).

GEAR_PRICES=brightdata   live prices. Two Bright Data products, use either or both:
  * SERP API (BRIGHTDATA_SERP_ZONE): one Google Shopping search per item, parsed to JSON by Bright
    Data (brd_json=1). Covers Walmart, REI, Amazon, Target, dive shops, ... in one call.
      POST https://api.brightdata.com/request  {"zone", "url", "format": "raw"}
  * Web Scraper API, Walmart (BRIGHTDATA_WALMART_DATASET_ID): Walmart products discovered by keyword.
      POST https://api.brightdata.com/datasets/v3/scrape?dataset_id=…&type=discover_new&discover_by=keyword
    A sync scrape that runs past ~1 minute answers 202 + snapshot_id; we poll briefly, then give up
    rather than hold a request open.
GEAR_PRICES=estimate     typical prices from data/fixtures/gear.json, labelled "Typical price, not live".

Results are cached per search (memory + data/runtime/gear_cache.json, 12 h) so a rehearsal doesn't
burn credits. Nothing about the member is sent: the search text is the item, never a name or preference.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import statistics
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

from .catalog import canonical
from .core import FIXTURES

if TYPE_CHECKING:
    from .core import Settings

log = logging.getLogger("rally.gear")

API = os.environ.get("BRIGHTDATA_API_BASE", "https://api.brightdata.com").rstrip("/")   # override only for local mocks
CACHE_TTL_S = 12 * 3600
_PRICE = re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)")


def load_catalog() -> dict[str, list[dict]]:
    return json.loads((FIXTURES / "gear.json").read_text())["activities"]


def parse_price(value: Any) -> float | None:
    """'$1,299.99' -> 1299.99; 'Now $24.97' -> 24.97; '$20 - $40' -> 20.0; 19.5 -> 19.5."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value > 0 else None
    if isinstance(value, dict):                       # {"value": 24.97} or {"amount": ...}
        for k in ("value", "amount", "price", "final_price"):
            if k in value:
                return parse_price(value[k])
        return None
    if not isinstance(value, str):
        return None
    m = _PRICE.search(value.replace(" ", " "))
    if not m:
        return None
    p = float(m.group(1).replace(",", ""))
    return p if p > 0 else None


def needed_items(activity: str, terms: dict) -> list[dict]:
    """Items the member brings for this plan. An item tied to a term is needed when the plan sets that
    term to False (the shop doesn't provide it). If the plan hasn't decided yet, it's listed as 'maybe'."""
    out = []
    for item in load_catalog().get(canonical(activity), []):
        term = item.get("neededWhen")
        if term is None:
            out.append({**item, "status": "needed"})
        elif terms.get(term) is False:
            out.append({**item, "status": "needed"})
        elif term not in terms:
            out.append({**item, "status": "maybe"})
    return out


def _offer(title: Any, price: Any, shop: Any, link: Any, source: str, rating: Any = None) -> dict | None:
    p = parse_price(price)
    if p is None or not title or not link:
        return None
    return {"title": str(title)[:140], "price": round(p, 2), "shop": str(shop or "").strip() or None,
            "link": str(link), "rating": rating if isinstance(rating, (int, float)) else None, "source": source}


def parse_serp(payload: Any) -> list[dict]:
    """Google Shopping results parsed by Bright Data (brd_json=1). Field names per Bright Data's docs:
    shopping[].title / price / shop / link / rating; older layouts used shopping_results / source."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return []
    if not isinstance(payload, dict):
        return []
    rows = payload.get("shopping") or payload.get("shopping_results") or []
    if not rows:                                       # some layouts put shopping ads under "organic"
        rows = [r for r in payload.get("organic", []) if isinstance(r, dict) and r.get("price")]
    offers = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        o = _offer(r.get("title"), r.get("price") or r.get("extracted_price"),
                   r.get("shop") or r.get("source") or r.get("merchant"),
                   r.get("link") or r.get("product_link") or r.get("url"), "google_shopping", r.get("rating"))
        if o:
            offers.append(o)
    return offers


def parse_walmart(records: Any) -> list[dict]:
    """Bright Data Walmart scraper records. Field names vary by scraper version, so we read the common ones."""
    if isinstance(records, dict):
        records = records.get("data") or records.get("results") or [records]
    offers = []
    for r in records or []:
        if not isinstance(r, dict) or r.get("error"):
            continue
        o = _offer(r.get("title") or r.get("product_name") or r.get("name"),
                   r.get("final_price") or r.get("price") or r.get("initial_price"),
                   r.get("seller_name") or r.get("seller") or "Walmart",
                   r.get("url") or r.get("product_url"), "walmart", r.get("rating"))
        if o:
            offers.append(o)
    return offers


def pick(offers: list[dict], price_range: list[float] | None, n: int = 3) -> list[dict]:
    """Drop accessories/bulk listings outside the item's plausible range, de-duplicate, cheapest first."""
    lo, hi = (price_range or [0, 1e9])[:2]
    seen, kept = set(), []
    for o in sorted(offers, key=lambda o: o["price"]):
        key = (o["title"].lower()[:60], o["shop"])
        if lo <= o["price"] <= hi and key not in seen:
            seen.add(key)
            kept.append(o)
    return kept[:n]


class GearPricer:
    def __init__(self, settings: "Settings", transport: Any = None):
        self.s = settings
        self.transport = transport                       # tests: httpx.MockTransport
        self.key = settings.brightdata_api_key
        self.serp_zone = settings.brightdata_serp_zone
        self.walmart_dataset = settings.brightdata_walmart_dataset_id
        wanted = settings.gear_prices
        live = bool(self.key and (self.serp_zone or self.walmart_dataset))
        if wanted == "brightdata" and not live:
            log.warning("GEAR_PRICES=brightdata needs BRIGHTDATA_API_KEY and a SERP zone or Walmart dataset id; "
                        "using typical prices instead.")
        self.mode = "brightdata" if wanted == "brightdata" and live else "estimate"
        self.cache_path = Path(settings.runtime_dir) / "gear_cache.json"
        self.cache: dict[str, dict] = self._load_cache()
        self.calls = 0
        self.errors = 0
        self.last_error: str | None = None
        self._sem = asyncio.Semaphore(4)

    # --------------------------------------------------------------- cache

    def _load_cache(self) -> dict:
        try:
            return json.loads(self.cache_path.read_text())
        except (OSError, ValueError):
            return {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache))
        except OSError as exc:                            # best effort: a read-only disk only costs credits
            log.warning("gear cache not saved: %s", exc)

    # --------------------------------------------------------------- Bright Data calls

    def _client(self):
        import httpx
        return httpx.AsyncClient(transport=self.transport, timeout=70,
                                 headers={"Authorization": f"Bearer {self.key}"})

    async def _serp(self, http, query: str) -> list[dict]:
        offers: list[dict] = []
        # Google has moved Shopping between tbm=shop and udm=28; try the classic one, fall back once.
        for mode in ("tbm=shop", "udm=28"):
            url = f"https://www.google.com/search?q={quote_plus(query)}&{mode}&gl=us&hl=en&brd_json=1"
            r = await http.post(f"{API}/request", json={"zone": self.serp_zone, "url": url, "format": "raw"})
            self.calls += 1
            if r.status_code != 200:
                raise RuntimeError(f"SERP API {r.status_code}: {r.text[:160]}")
            offers = parse_serp(r.text)
            if offers:
                break
        return offers

    async def _walmart(self, http, query: str) -> list[dict]:
        params = {"dataset_id": self.walmart_dataset, "type": "discover_new", "discover_by": "keyword",
                  "format": "json", "include_errors": "true"}
        r = await http.post(f"{API}/datasets/v3/scrape", params=params,
                            json={"input": [{"keyword": query}], "limit_per_input": 8})
        self.calls += 1
        if r.status_code == 202:                          # ran past the sync window: poll briefly
            snap = r.json().get("snapshot_id")
            for _ in range(10):
                await asyncio.sleep(3)
                p = await http.get(f"{API}/datasets/v3/progress/{snap}")
                status = p.json().get("status")
                if status == "ready":
                    r = await http.get(f"{API}/datasets/v3/snapshot/{snap}", params={"format": "json"})
                    break
                if status == "failed":
                    raise RuntimeError("Walmart scrape failed")
            else:
                raise RuntimeError("Walmart scrape still running; try again in a minute")
        if r.status_code != 200:
            raise RuntimeError(f"Web Scraper API {r.status_code}: {r.text[:160]}")
        return parse_walmart(r.json())

    async def _search(self, http, item: dict) -> tuple[list[dict], str | None]:
        q = item["query"]
        hit = self.cache.get(q)
        if hit and time.time() - hit["at"] < CACHE_TTL_S:
            return hit["offers"], None
        offers: list[dict] = []
        errors = []
        async with self._sem:
            for name, fn, on in (("serp", self._serp, self.serp_zone), ("walmart", self._walmart, self.walmart_dataset)):
                if not on:
                    continue
                try:
                    offers += await fn(http, q)
                except Exception as exc:                  # one source failing must not hide the other
                    self.errors += 1
                    self.last_error = f"{name}: {exc}"
                    errors.append(self.last_error)
                    log.warning("bright data %s failed for %r: %s", name, q, exc)
        if offers:
            self.cache[q] = {"at": time.time(), "offers": offers}
        return offers, "; ".join(errors) or None

    # --------------------------------------------------------------- public

    async def price(self, activity: str, terms: dict) -> dict:
        items = needed_items(activity, terms)
        out = []
        if self.mode == "brightdata" and items:
            async with self._client() as http:
                results = await asyncio.gather(*(self._search(http, i) for i in items))
            self._save_cache()
        else:
            results = [([], None)] * len(items)
        for item, (offers, err) in zip(items, results):
            best = pick(offers, item.get("priceRange"))
            live = bool(best)
            out.append({
                "key": item["key"], "label": item["label"], "why": item.get("why"),
                "status": item["status"], "optional": bool(item.get("optional")),
                "offers": best,
                "price": best[0]["price"] if live else item.get("typicalUsd"),
                "median": round(statistics.median(o["price"] for o in best), 2) if live else None,
                "provenance": "live" if live else "estimate",
                "searchUrl": f"https://www.google.com/search?q={quote_plus(item['query'])}&tbm=shop",
                "error": err,
            })
        required = [i for i in out if i["status"] == "needed" and not i["optional"] and i["price"]]
        return {
            "activity": canonical(activity),
            "mode": self.mode,
            "items": out,
            "totalRequired": round(sum(i["price"] for i in required), 2),
            "liveCount": sum(i["provenance"] == "live" for i in out),
            "fetchedAt": int(time.time() * 1000),
        }

    def status(self) -> dict:
        return {"mode": self.mode, "serp": bool(self.serp_zone), "walmart": bool(self.walmart_dataset),
                "calls": self.calls, "errors": self.errors, "lastError": self.last_error,
                "cachedSearches": len(self.cache)}
