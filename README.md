# Parley

**Tell your agent where you want to go. It finds the people, or goes it alone with you, and negotiates the deal with the shops' agents.**

Parley turns a sentence like *"Scuba diving in Monterey next month, under $300, I'm Open Water certified"* into a booked adventure. Each person has a personal AI agent that holds their private preferences. The agents find compatible people, agree on one plan without revealing anyone's preferences, and negotiate price with vendor agents that represent real shops. Nothing is booked or paid until every human approves the exact plan and quote.

Built at **Cal Hacks 13.0** by Kevin (platform, frontend, payments, deployment), Parikshit (agents and Fetch.ai) and Dev (AI, search and data).

```
"Scuba in Monterey under $300"
        │  compile (Gemini or offline template)          you review: hard conditions vs. preferences
        ▼
   public intent ──► matching (hard filters, Moss ranking) ──► people who fit
        │                                                         │
        │  nobody fits, or "Just me"                              │  "With others"
        ▼                                                         ▼
   SOLO: your agent ⇄ every shop's agent              GROUP: mediator ⇄ each person's agent
   (price sheets + trips already running)             (bounded rounds, private prefs stay private)
        └──────────────────────┬──────────────────────────────────┘
                               ▼
              binding quote from the vendor's agent (staff can review and discount)
                               ▼
        every human approves the exact version ─► deposit (simulated or x402 testnet)
                               ▼
              vendor staff confirm the booking ─► calendar invite, share card
```

## Contents

1. [Why it's different](#why-its-different)
2. [Run it in two minutes](#run-it-in-two-minutes)
3. [Demo script for judges](#demo-script-for-judges)
4. [Features](#features)
5. [Sponsor technology](#sponsor-technology)
6. [What is real and what is simulated](#what-is-real-and-what-is-simulated)
7. [Configuration](#configuration)
8. [Architecture](#architecture)
9. [API reference](#api-reference)
10. [Tests and measured results](#tests-and-measured-results)
11. [Deploying](#deploying)
12. [Privacy and safety rules](#privacy-and-safety-rules)
13. [Troubleshooting](#troubleshooting)
14. [Project layout and owners](#project-layout-and-owners)

## Why it's different

- **Agents negotiate, people decide.** Agents propose and counter-propose; only a human click approves, commits or books.
- **Private preferences never leave your agent.** The mediator sees accept, "change this term" or "can't do this". It never sees weights or ideal values. That rule is enforced by tests on every snapshot.
- **Groups or solo.** With others, a mediator gets everyone's agent to one plan. Alone, your agent negotiates with every shop directly and hunts for **trips already running that you can join at the group rate**, the main lever a solo traveller actually has.
- **Both sides are real.** Vendors have their own portal, their own agent with editable price rules, and staff who can review a quote, offer a discount (never a higher price) and confirm the booking.
- **Honest labels.** Anything simulated says so on screen: "Simulated", "Listed price, not a quote", "Typical price, not live", "Testnet".

## Run it in two minutes

Needs **Python 3.11 to 3.13** and **Node 20+**. Works on Windows, macOS and Linux.

```bash
python scripts/rally.py setup     # pip install -r requirements.txt + npm install
python scripts/rally.py dev       # API on http://localhost:8000, web on http://localhost:3000
```

Open http://localhost:3000.

- **With others:** pick *Scuba in Monterey*, then **Find my people**. Answer 5 for group size, publish, start the group and approve. Switch identity in the header to approve as other people.
- **Just me:** choose *Just me*, pick *Scuba in Monterey*, then **Find my deal**. Publish, then **Go solo**. Your agent negotiates with the dive shops and finds a boat that's already going.

`python scripts/rally.py reset` restores the scenario between rehearsals. Copy `.env.example` to `.env` to turn on sponsor integrations (see [Configuration](#configuration)). The API reads `.env` itself.

## Demo script for judges

Open **http://localhost:3000/demo**, the control room, on the projector.

1. **Lights.** Each sponsor's integration shows live (teal) or fallback (amber). Nothing pretends to be live.
2. **Launch scuba.** One click compiles the goal, matches five divers, invites their agents and starts the negotiation. The room fills as agents join.
3. **Phone seats.** In the group room, **Phone seats** shows a QR code per member and for the vendor's staff. A judge scans one and approves or asks for a change as that person, live on both screens.
4. **Vendor review.** Another judge takes the vendor seat and approves the binding quote in the vendor portal, or offers a discount.
5. **Approve and commit.** Everyone approves; deposits commit; add the trip to a calendar or share it.
6. **Replay.** Scrub through every plan version: what was proposed, how each agent answered, why the next version changed.
7. **Solo diver.** Launch the solo scenario. Nobody to go with, yet the agent joins Kelp Line's already-booked Nov 14 boat and pays the 4-to-5-person rate instead of the solo rate.
8. **Point at the numbers:** zero hard-constraint violations, agent messages, time to agreement, group savings. They are all measured live, never estimated.

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
