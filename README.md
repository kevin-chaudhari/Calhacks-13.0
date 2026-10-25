# Parley

**Say where you want to go. Your AI agent finds people to go with and bargains with the shops for you.**

Built at **Cal Hacks 13.0** by Kevin (website, payments, hosting), Parikshit (AI agents and Fetch.ai) and Dev (AI, search and data).

---

## The simple version

Imagine you want to go scuba diving. Doing it alone is expensive, and finding other divers who want the
same trip, on the same day, at the same price, is a lot of work. Then somebody still has to call the dive
shops and haggle.

**Parley does all of that for you.**

1. **You type one sentence**, like *"Scuba diving in Monterey next month, under $300. I'm certified."*
2. **Your own AI helper (your "agent") reads it** and turns it into a clear plan: what, where, when and how much.
3. **It finds people who want the same trip.** Or, if you'd rather go alone, it hunts for a boat that's already going so you can hop on at the cheaper group price.
4. **The agents talk it out.** Everyone's agent, plus a go-between agent, agree on one plan. The dive shops have agents too, and they offer prices.
5. **You say yes (or no).** Nothing is booked and no money moves until every real person approves the exact plan and price.

Think of it like a group chat where helpful robots do the planning and haggling, and the humans just make the final call.

### Two promises

- **Your secrets stay secret.** You can tell your agent things like *"I really care about a morning dive"*. Your agent uses that to argue for you, but never shows it to anyone else.
- **Robots suggest, people decide.** An agent can never approve, pay or book anything. Only a person clicking a button can.

## How it works (picture version)

```
  You: "Scuba in Monterey under $300"
           │
           ▼
  1. Your agent turns it into a plan      (what, where, when, budget, must-haves)
           │
           ▼
  2. It finds people who fit  ──────────  or nobody? You go solo, and your agent
           │                              looks for a boat that's already going
           ▼
  3. The agents negotiate                 (a go-between agent proposes a plan,
           │                               each person's agent says yes or "change this")
           ▼
  4. The shop's agent sends a real price  (shop staff can check it, or offer a discount)
           │
           ▼
  5. Every person approves  ──►  deposit (pretend money or test money)  ──►  shop confirms  ──►  you're going!
```

## Words you'll see

| Word | What it means |
|---|---|
| **Agent** | A small AI helper that works for one person or one shop. Yours knows what you want and argues for you. |
| **Mediator** | The go-between agent. It suggests one plan for the whole group and improves it round by round. |
| **Goal** | The sentence you typed. |
| **Must-have** (hard condition) | Something you won't give up, like "under $300" or "I'm certified". Agents never trade these away. |
| **Private preference** | Something you'd *like*, like a morning time slot. Only your agent knows it. |
| **Vendor** / **shop** | The business running the trip, like a dive shop. It has its own agent and its own staff page. |
| **Quote** | A shop's price offer for the exact plan. |
| **Solo mode** | Going alone. Your agent bargains for you and tries to slot you into a group that's already booked. |
| **Simulated** | Pretend. Anything pretend says so right on the screen. |

## Try it yourself

You need **Python** (version 3.11, 3.12 or 3.13) and **Node.js** (version 20 or newer). Works on Windows, Mac and Linux.

**Step 1. Install everything** (only needed once):

```bash
python scripts/rally.py setup
```

**Step 2. Start the app:**

```bash
python scripts/rally.py dev
```

**Step 3. Open http://localhost:3000 in your browser.** That's it!

### What to click

- **Go with others:** pick **With others**, tap **Scuba in Monterey**, then **Find my people**. Check the details, tap the people you want, and start the group. Use the name menu at the top right to switch to another person and approve as them.
- **Go alone:** pick **Just me**, tap **Scuba in Monterey**, then **Find my deal**. Your agent bargains with the dive shops and finds a boat that's already going.

### Finding your way around

| Where | What's there |
|---|---|
| **Plan a trip** (home) | Type a goal, see your trips and goals |
| **Trip page** | The next step is always at the top. Tabs: **Plan**, **Chat**, **Agent talk** (every message between agents) and **Replay** (step through how the deal changed) |
| **Agents** | Every agent and every message, live |
| **For shops** | What a dive shop sees: requests, quotes to approve, price rules |
| **Demo** | One-click demos, live numbers, and QR codes for phones |

Want to start fresh? Run `python scripts/rally.py reset`.

Everything works with no setup. To switch on the real sponsor services (Gemini, Convex, Bright Data and the rest), copy `.env.example` to `.env` and fill it in. See [Configuration](#configuration).

## Demo for judges

Open **http://localhost:3000/demo** on the big screen.

1. **The lights.** Each sponsor service shows **live** (teal) or **fallback** (amber). Nothing pretends.
2. **Launch scuba.** One click: the goal is read, five divers are matched, their agents join and start negotiating.
3. **Phone seats.** In the trip page, **Phone seats** shows a QR code for each person and for the shop's staff. A judge scans one and approves, or asks for a change, from their own phone.
4. **The shop.** Another judge takes the shop seat and approves the price, or offers a discount.
5. **Everyone approves.** Deposits go through; add the trip to a calendar or share it.
6. **Replay.** Step through every version of the plan and see why it changed.
7. **Solo diver.** Nobody to go with, yet the agent joins a boat that's already booked and pays the group price.
8. **The numbers:** zero broken must-haves, how many agent messages, time to agreement, money saved. All measured live.

---

# For developers

Everything below is the technical reference.

## Contents

1. [Why it's different](#why-its-different)
2. [Features](#features)
3. [Sponsor technology](#sponsor-technology)
4. [What is real and what is simulated](#what-is-real-and-what-is-simulated)
5. [Configuration](#configuration)
6. [Architecture](#architecture)
7. [API reference](#api-reference)
8. [Tests and measured results](#tests-and-measured-results)
9. [Deploying](#deploying)
10. [Privacy and safety rules](#privacy-and-safety-rules)
11. [Troubleshooting](#troubleshooting)
12. [Project layout and owners](#project-layout-and-owners)

## Why it's different

- **Agents negotiate, people decide.** Agents propose and counter-propose; only a human click approves, commits or books.
- **Private preferences never leave your agent.** The mediator sees accept, "change this term" or "can't do this". It never sees weights or ideal values. Tests enforce this on every snapshot.
- **Groups or solo.** With others, a mediator gets everyone's agent to one plan. Alone, your agent negotiates with every shop directly and hunts for **trips already running that you can join at the group rate**, the main lever a solo traveller actually has.
- **Both sides are real.** Vendors have their own portal, their own agent with editable price rules, and staff who can review a quote, offer a discount (never a higher price) and confirm the booking.
- **Honest labels.** Anything simulated says so on screen: "Simulated", "Listed price, not a quote", "Typical price, not live", "Testnet".

## Features

### For travellers (`/`)
| Feature | What it does |
|---|---|
| Goal compiler | One sentence becomes a structured intent: activity, place, dates, budget, certification, negotiable terms. Gemini when configured, an offline template otherwise. Asks when something is missing; never invents a budget or date. |
| Review | Hard conditions ("must have") vs. private preferences (sliders only your agent sees). |
| Matching | Hard filters with a reason for every rejection; ranking only reorders people who passed. |
| **Solo mode** | "Just me" on the home page, or **Go solo** when nobody fits. The agent negotiates with every shop's agent alone and prices you into trips already running (`openGroups`) at their group rate. |
| Group room | 7-step workflow, live plan with per-term agreement, round timeline, quotes, mediator activity, the full agent-to-agent conversation, and group chat with the vendor's staff. |
| Group-size nudge | A vendor's agent says "one more person drops everyone to $139". The organizer invites the next match in one click. |
| Auto-replace | If someone leaves, the next free match is invited so the group keeps its size. |
| Why this plan works for you | A private explanation of how the plan scores against your own preferences. *The card is built; it appears once Dev's `/explanation` endpoint lands.* |
| What you'll bring | Gear you need for the current plan, priced from real stores through **Bright Data**, with a rent-or-buy comparison against the shops' rental prices. |
| Approve and commit | Approval binds to the exact plan version and quote. Deposits are simulated or **x402 testnet** payments with explorer links and retry. |
| Confirmation | Calendar (.ics) download, share card, negotiation replay, append-only audit timeline. |
| Voice and translation | Dictate messages, hear them read aloud, auto-translate the chat (English, Spanish, Hindi, Chinese, French, Japanese, Portuguese). |
| Also on ASI:One | Type the same goal in ASI:One chat; the Parley concierge agent replies with the plan and a room link. |

### For vendors (`/vendor`)
| Feature | What it does |
|---|---|
| Requests | Every group or solo traveller that wants what you offer, by stage: negotiating, quote to review, quote sent, confirm booking, booked. |
| Quote review | Your agent drafts the binding quote; staff approve it, lower the price, or decline. |
| Agent and pricing | Edit group-size tiers, option modifiers, available dates and auto-quote. Your agent prices every plan from these rules. |
| Chat | The same chat as the travellers, with voice and translation. |

### For the stage (`/demo`)
Sponsor lights, one-click scenarios (scuba, skydiving, kayaking, **solo diver**), live metrics, phone seats and reset.

## Sponsor technology

| Sponsor | Used for | Where |
|---|---|---|
| **Fetch.ai** (uAgents, Agentverse, ASI:One) | Every person, vendor and the mediator is a uAgent; 8 registered on Agentverse; Chat Protocol concierge for ASI:One | `agents/`, `services/api/rally/negotiation/` (see `agents/README.md`) |
| **Google Gemini** | Goal compiler (written, behind `COMPILER=gemini`), chat translation fallback; private explanations planned | `services/api/rally/compiler.py` |
| **Moss** | Semantic ranking of matches and vendor search: **planned** (Dev); the local TF-IDF ranker runs until then | `services/api/rally/matching.py` |
| **Convex** | Live state for every screen, membership-checked reads, restart recovery | `convex/`, `services/api/rally/store.py` |
| **Coinbase x402** | Per-member deposits as real HTTP 402 payments in test USDC on Base Sepolia | `services/api/rally/payments.py` |
| **Bright Data** | Live store prices for the gear each person must bring (SERP API → Google Shopping; Walmart Web Scraper API) | `services/api/rally/gear.py`, `docs/brightdata.md` |
| **Apify** | Vendors' public listed prices, labelled "Listed price, not a quote": **planned** (Dev); the UI badge is ready | `services/api/rally/providers.py` |
| **Vultr** | API and agents host behind Caddy HTTPS | `infra/` |

## What is real and what is simulated

| Part | Status | Label in the UI |
|---|---|---|
| Goal compiler | Offline template compiler always works; Gemini behind `COMPILER=gemini` | "Compiled by Gemini" / "Compiled offline" |
| Matching | Real hard filters with reasons; local TF-IDF ranker. Moss adapter **not written yet** (`RANKER=moss` falls back to local and says so) | "Ranked locally" |
| Negotiation | Real mediator and personal-agent logic, in-process or over real uAgents (`TRANSPORT=agentverse`); measured over Agentverse mailboxes: same result as in-process | "Agents: agentverse" / "Agents: inproc" |
| Solo negotiation | Real: same mediator with one member; vendors' open trips priced from `openGroups` in the provider fixtures | "Solo", "joins a booked group of N (group rate)" |
| Vendors | Six fictional shops (two per activity) with editable fixture price rules | "Simulated" |
| Payments | Simulated ledger by default. `PAYMENTS=x402_testnet`: real x402 deposits in test USDC, verified end to end with real signatures against a stand-in facilitator; **not yet run against x402.org with funded wallets**. Mainnet refused at startup | "Simulated, no money moved" / "Testnet deposit" |
| State | In-memory by default; `STORE=convex` mirrors to Convex. Verified with convex-test and a fake client; **not yet run against a live deployment** | Control room light |
| Gear prices | `GEAR_PRICES=brightdata`: live; tested against mocked Bright Data responses, **not yet with a real key** | "Bright Data" / "Typical prices, not live" |
| Identity | Demo personas with HMAC-signed tokens, not real accounts | Identity switcher in the header |

## Configuration

Copy `.env.example` to `.env` in the project root (git-ignored; the API loads it at startup, real environment variables win). Every integration is off by default and falls back to a labelled offline mode, so the app always runs.

| Variable | Default | What it turns on | Owner |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Where the web app calls the API (put in `apps/web/.env.local`) | Kevin |
| `NEXT_PUBLIC_CONVEX_URL` | | Live reads from Convex instead of polling | Kevin |
| `STORE`, `CONVEX_URL`, `RALLY_SERVER_KEY` | `memory` | `convex`: system of record in Convex | Kevin |
| `PAYMENTS`, `X402_*` | `simulated` | `x402_testnet`: real testnet deposits (`python scripts/x402_wallets.py` makes wallets) | Kevin |
| `GEAR_PRICES`, `BRIGHTDATA_API_KEY`, `BRIGHTDATA_SERP_ZONE`, `BRIGHTDATA_WALMART_DATASET_ID` | `estimate` | `brightdata`: live gear prices (`docs/brightdata.md`) | Kevin |
| `COMPILER`, `GEMINI_API_KEY`, `GEMINI_MODEL` | `template` | `gemini`: Gemini goal compiler and chat translation | Dev |
| `RANKER`, `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY` | `local` | `moss`: semantic ranking (planned) | Dev |
| `PROVIDERS`, `APIFY_TOKEN` | `seeded` | `seeded+apify`: listed prices (planned) | Dev |
| `TRANSPORT`, `AGENT_NETWORK`, `AGENT_SEED_PREFIX`, `AGENTVERSE_API_KEY`, `AGENT_DIRECT` | `inproc` | `agentverse`: agents over real uAgents messaging | Parikshit |
| `RALLY_WEB_URL` | `http://localhost:3000` | Public web URL for QR seats and ASI:One links | all |
| `RALLY_SECRET` | dev value | Signs demo identity tokens; set a fresh one when deployed | all |
| `DEMO_ROUND_DELAY_MS` | `1400` | Pause between rounds so judges can watch | all |
| `ALLOW_DEMO_ROUTES` | `1` | Control room, seats, persona switcher; set `0` outside the demo | all |

## Architecture

```
 Browser (Next.js 15, React 19, Tailwind 4)
   │ commands (REST)                         ▲ live state: one DealSnapshot document
   ▼                                         │ (Convex subscription, or polling)
 FastAPI orchestrator (services/api/rally) ──┴─► Convex (mirror, token-checked reads)
   │  service.py: the only writer; state machine with allowed transitions
   │  compiler.py ─ Gemini / template      matching.py ─ hard filters + ranker (local; Moss planned)
   │  negotiation/ ─ mediator, personal-agent brain, engine (plan space, pricing, open groups)
   │  providers.py ─ vendor sheets, binding quotes      payments.py ─ simulated / x402 testnet
   │  gear.py ─ Bright Data prices
   ▼
 uAgents (agents/run_agents.py): 20 personal + 6 vendor agents; mediator inside the API;
 concierge.py on Agentverse for ASI:One
```

- **Contracts first.** `packages/contracts` (Pydantic) is the source of truth; `gen_ts.py` writes `ts/index.ts`, camelCase on the wire.
- **One snapshot.** Every screen renders from the same `DealSnapshot`, built by one function, whether it arrives from Convex or by polling.
- **Restart-safe.** With Convex on, a restarted API rebuilds its state and resumes negotiations, invites and quote requests (`deal.resumed` event).
- **Solo pricing.** `ProviderSheet.pool` prices a solo traveller as part of the group already booked on that date (`openGroups`), capped at the shop's largest tier. Groups are priced as before.

## API reference

All commands take `Authorization: Bearer <persona token>` (from `GET /v1/demo/personas`). Errors are always `{"error": {code, message, retryable, fields?}}`.

| Method and path | Purpose |
|---|---|
| `POST /v1/goals:compile`, `PATCH /v1/goals/{id}` | Sentence to intent; answer missing questions |
| `POST /v1/intents`, `POST /v1/intents/{id}/matches` | Publish (private prefs go to your agent only); find people |
| `POST /v1/deals` | Start a group `{intentId, candidateIntentIds}` or a solo trip `{intentId, solo: true}` |
| `POST /v1/deals/{id}/negotiate` | Start negotiation (solo trips start by themselves) |
| `GET /v1/deals/{id}/snapshot` | The whole deal, for members only |
| `POST /v1/deals/{id}/approvals`, `/commitments`, `/leave` | Approve a version, commit, leave |
| `POST /v1/deals/{id}/nudge/accept` | Invite one more person after a vendor's group-size offer |
| `GET /v1/deals/{id}/explanation` | Why this plan works for you (private). *Dev's branch; the UI hides the card until it exists* |
| `GET /v1/deals/{id}/gear`, `GET /v1/gear/{activity}` | What to bring, with live prices |
| `POST /v1/deals/{id}/messages` | Group chat |
| `GET /v1/vendor/requests`, `POST /v1/vendor/requests/{id}/quote` | Vendor portal: requests, approve or discount a quote |
| `GET /v1/providers/search?q=` | Vendor search. *Dev's branch; the search box hides itself until it exists* |
| `POST /v1/x402/deposits/{deal}/{user}` | x402-paid deposit route (testnet) |
| `GET /v1/health`, `GET /v1/metrics` | Adapter status; live measured metrics |
| `POST /v1/demo/launch`, `GET /v1/demo/seats/{id}`, `POST /v1/demo/reset` | Control room |

Interactive docs: http://localhost:8000/docs.

## Tests and measured results

```bash
python scripts/rally.py test            # all Python tests (unit, integration, property-based)
npm run test:convex                     # Convex functions with convex-test
./node_modules/.bin/tsc -p apps/web --noEmit
node tests/e2e/two_sided_walk.js        # real browser: a traveller and a vendor at once
```

The Python suite covers:
- the full scuba path over HTTP and solo trips for all three activities;
- open-group pricing and vendor review limits (may lower, never raise);
- private-preference leak checks on every snapshot;
- Hypothesis properties: the mediator never sends a plan that violates a known hard constraint, and always terminates;
- every allowed and forbidden state transition and version-bound idempotent approvals;
- x402 deposits with real signatures, Convex restore after a restart, Bright Data parsing and caching, the uAgents transport and the ASI:One concierge.

`python scripts/rally.py eval` runs the real mediator on 50 generated groups against an oracle that sees everyone's preferences (results in `tests/evaluation/results/negotiation.json`):

| Metric | Result |
|---|---|
| Hard-constraint violations in proposals sent | **0** |
| Agreed plan's total member score vs oracle best | 97.1% |
| Full-group agreement where a unanimous plan exists | 66.7% |
| Mean / max rounds | 3.2 / 10 |

## Deploying

Web on Vercel, API and agents on a Vultr VM behind Caddy (automatic HTTPS), live state in Convex. Step by step: `infra/DEPLOY.md`. Bright Data setup: `docs/brightdata.md`.

## Privacy and safety rules

- Private preferences stay with the owner's agent; they are never written to Convex or any snapshot.
- Hard conditions are never traded away; the mediator can't propose a plan that violates a known one.
- Agents never approve, pay or book; a person does, for an exact plan version and quote.
- Payments are testnet only; mainnet network names refuse to start.
- Secrets live in `.env` (git-ignored) and are never committed.
- Simulated data is always labelled as simulated.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Can't reach the Parley API" | Start it with `python scripts/rally.py dev`; check `NEXT_PUBLIC_API_URL` |
| "Nobody fits yet" | Expected when no one passes your hard conditions. Go solo, or widen dates, budget or distance |
| A sponsor light is amber | That integration's variables aren't set, or it failed; `GET /v1/health` shows the reason |
| Gear shows "Typical prices" | Set `GEAR_PRICES=brightdata`, `BRIGHTDATA_API_KEY` and `BRIGHTDATA_SERP_ZONE`; check `lastError` in health |
| QR seats open localhost on phones | Set `RALLY_WEB_URL` to the public web URL |
| 429 errors while rehearsing | Reset from the control room; it clears rate limits |

## Project layout and owners

```
apps/web/                 Next.js app: traveller app, vendor portal, control room   (Kevin)
services/api/rally/       FastAPI orchestrator, payments, store, gear, solo mode     (Kevin)
  compiler.py, matching.py                                                         (Dev)
  negotiation/            mediator, personal agents, uAgents transport              (Parikshit)
agents/                   uAgents runner, Agentverse registration, ASI:One concierge (Parikshit)
convex/                   schema and functions                                      (Kevin)
packages/contracts/       shared Pydantic models and generated TypeScript           (all)
data/fixtures/            personas, intents, private prefs, vendors, gear lists
infra/                    Docker, Caddy, systemd, Vultr cloud-init, Vercel          (Kevin)
docs/                     decisions, Bright Data setup, work docs
tests/                    unit, integration, evaluation, e2e
```

The Python package and some environment variables keep the internal name `rally` (for example `RALLY_SECRET`), so teammates' branches merge cleanly; everything people see says Parley.
