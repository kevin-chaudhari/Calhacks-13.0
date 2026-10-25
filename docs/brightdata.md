# Bright Data: live gear prices

When a plan says "Bring your own" gear (or an activity always needs something, like a dry bag),
every member sees **What you'll bring**: each item with the lowest real price found, the store, a
link, and the rent-or-buy comparison against the shops' rental price. Endpoints:

- `GET /v1/deals/{dealId}/gear` for the member's current plan
- `GET /v1/gear/{activity}?gear_included=false` before a group exists

The item list lives in `data/fixtures/gear.json` (add activities or items there).

## Setup

1. **Bright Data account.** Sign up at brightdata.com with the hackathon credit code.
2. **SERP API zone.** Control panel → Proxies & Scraping → Add → **SERP API**. Give it a name
   (e.g. `serp_rally`) and create it. The zone name is `BRIGHTDATA_SERP_ZONE`.
3. **API key.** Control panel → Account settings → API key → copy. That's `BRIGHTDATA_API_KEY`.
4. **Optional, Walmart only:** Web Scrapers → Scraper Library → Walmart → the "discover by keyword"
   products scraper → copy its dataset id (`gd_…`) into `BRIGHTDATA_WALMART_DATASET_ID`.
5. In `.env` (the repo root file the API reads, never committed):
   ```
   GEAR_PRICES=brightdata
   BRIGHTDATA_API_KEY=...
   BRIGHTDATA_SERP_ZONE=serp_rally
   BRIGHTDATA_WALMART_DATASET_ID=     # optional
   ```
6. Restart the API. `/v1/health` → `"gear": {"mode": "brightdata", "serp": true, ...}`, and the
   control room shows the Bright Data light green.
7. Test one search: open a group room, or
   `curl -H "Authorization: Bearer <persona token>" localhost:8000/v1/gear/scuba_diving?gear_included=false`

## Credits

One search per item, cached 12 hours in `data/runtime/gear_cache.json`, so a full scuba list costs
about 8 SERP requests once (16 if Google answers the classic shopping URL empty and we retry the
newer one). Delete the cache file to force fresh prices before judging.

## If something is wrong

- `lastError` in `/v1/health` → `gear` shows Bright Data's message (401 = key, 404 = zone name).
- Items that fail fall back to a labelled typical price; the page never shows a fake "live" price.
