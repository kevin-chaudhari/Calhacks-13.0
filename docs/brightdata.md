# Bright Data: real vendors, real deals, live gear prices

When a plan says "Bring your own" gear (or an activity always needs something, like a dry bag),
every member sees **What you'll bring**: each item with the lowest real price found, the store, a
link, and the rent-or-buy comparison against the shops' rental price. Endpoints:

- `GET /v1/deals/{dealId}/gear` for the member's current plan
- `GET /v1/gear/{activity}?gear_included=false` before a group exists

The item list lives in `data/fixtures/gear.json` (add activities or items there).

## Real vendors for any activity (the main use)

For any goal ("rock climbing in Yosemite", "pottery class in Brooklyn"), Parley:

1. runs a **SERP API** Google search ("rock climbing guide near Yosemite Valley, CA", `brd_json=1`). The parsed
   `snack_pack` is the local map pack: each business's name, website, phone, rating, review count, address and
   Maps link. A second search finds web deals (Groupon, Viator and others) whose snippet states a price;
2. reads each vendor's own website through the **Web Unlocker** (`data_format: "markdown"`);
3. extracts the offers on that page with **Gemini** (structured output), or with rules when no Gemini key is set;
4. **keeps an offer only if its price appears in a sentence that exists verbatim on that page.** Invented or
   misread numbers are dropped (counted in `/v1/health` → `discovery.droppedUnverified`);
5. turns the offers into a price table per party size and format (a "$720 per group of 4" package becomes
   $180 each for four), which the agents negotiate over. Quotes from these vendors are labelled
   "Listed price, not a quote", carry the source sentence, and end with "Book on their website".

Vendors with no readable price are listed ("price not listed") but never priced. Results are cached per
activity + place for 24 hours (`data/runtime/discovery_cache.json`). `GET /v1/discover?q=surf+lessons+in+Santa+Cruz`
returns all of it; the **Find deals** page shows it.

Credits per new activity + place: 2 SERP requests + up to 6 Web Unlocker requests (+ up to 6 Gemini calls).

## Setup

1. **Bright Data account.** Sign up at brightdata.com with the hackathon credit code.
2. **SERP API zone.** Control panel → Proxies & Scraping → Add → **SERP API**. Give it a name
   (e.g. `serp_rally`) and create it. The zone name is `BRIGHTDATA_SERP_ZONE`.
3. **Web Unlocker zone.** Control panel → Proxies & Scraping → Add → **Web Unlocker API**, name it
   (e.g. `unlocker_rally`). That's `BRIGHTDATA_UNLOCKER_ZONE`. Without it, prices come only from search snippets.
4. **API key.** Control panel → Account settings → API key → copy. That's `BRIGHTDATA_API_KEY`.
5. **Optional, Walmart only:** Web Scrapers → Scraper Library → Walmart → the "discover by keyword"
   products scraper → copy its dataset id (`gd_…`) into `BRIGHTDATA_WALMART_DATASET_ID`.
6. In `.env` (the repo root file the API reads, never committed):
   ```
   BRIGHTDATA_API_KEY=...
   BRIGHTDATA_SERP_ZONE=serp_rally
   BRIGHTDATA_UNLOCKER_ZONE=unlocker_rally
   VENDOR_DISCOVERY=brightdata
   GEAR_PRICES=brightdata
   GEMINI_API_KEY=...                  # reads vendor pages precisely; rules are used without it
   BRIGHTDATA_WALMART_DATASET_ID=     # optional
   ```
7. Restart the API. `/v1/health` → `"discovery": {"mode": "brightdata", "pages": true, "extractor": "gemini"}`.
8. Test: open **Find deals** and search "surf lessons in Santa Cruz", or
   `curl -H "Authorization: Bearer <persona token>" "localhost:8000/v1/discover?q=surf+lessons+in+Santa+Cruz"`

## Credits

One search per item, cached 12 hours in `data/runtime/gear_cache.json`, so a full scuba list costs
about 8 SERP requests once (16 if Google answers the classic shopping URL empty and we retry the
newer one). Delete the cache file to force fresh prices before judging.

## If something is wrong

- `lastError` in `/v1/health` → `gear` shows Bright Data's message (401 = key, 404 = zone name).
- Items that fail fall back to a labelled typical price; the page never shows a fake "live" price.
