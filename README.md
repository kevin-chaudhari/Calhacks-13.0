# Rally

Your agents find your people, agree on the plan, and turn shared goals into group deals.

This is the **first working vertical slice** from the Rally Engineering Master Plan (section 26.2): the scuba goal goes from a sentence to a simulated commitment in the browser, with every step visible live in the group room.

```
sentence → compiled intent → you review → hard-filter matching → group of 5
→ mediator negotiates one shared plan (bounded rounds, private prefs stay private)
→ provider quote → every member approves the exact version → simulated commitment
```

## Run it

Needs Python 3.11 to 3.13 and Node 20+. Works on Windows, macOS and Linux.

```bash
python scripts/rally.py setup     # pip install -r requirements.txt + npm install
python scripts/rally.py dev       # API on :8000, web on :3000
```

Open http://localhost:3000, click **Scuba trip in Monterey**, then **Find my people**. Answer "5" for group size, publish, start the group, start negotiation, approve. Switch identity in the header to approve as Ana and Ravi (teammates do this from their own laptops); use **Approve as demo** for the two seeded personas.

**On stage:** open http://localhost:3000/demo (the control room). It shows which sponsor adapters are live, launches a whole scenario in one click (scuba, skydiving, kayaking), measures results live (hard-constraint violations, agent messages, time to agreement, savings), and the group room's **Phone seats** button gives every member and the vendor's staff a QR code so judges act from their own phones.

`python scripts/rally.py reset` restores the scenario between rehearsals. (`make dev`, `make test`, etc. do the same on macOS/Linux.)

## Two sides: customers and vendors

Rally now runs end to end from both sides, for **scuba diving, skydiving and sea kayaking**.

| Customer app (`/`) | Vendor portal (`/vendor`) |
|---|---|
| Type a goal, review it, publish, match, start a group | Six fictional vendors, each with staff and a Rally provider agent |
| Group room: 7-step workflow, live plan, rounds, quotes | Requests list with stages: negotiating → quote to review → quote sent → confirm booking → booked |
| **Agent conversation**: every message between the mediator, each person's agent and the vendor's agent (Invite, Join, Proposal, Response, QuoteRequest, Quote, Review, FinalAgreement), with payloads | Review the agent's drafted quote, offer a discount (never a higher price), approve or decline |
| Group chat with the vendor's staff | Same chat from the vendor side |
| Approve, commit, see the vendor's booking confirmation | Confirm the booking; edit pricing tiers, option modifiers, dates and auto-quote |

**Voice and translation (both sides, emphasised on the vendor side):** the mic button dictates messages (speech to text), "Listen" reads any message aloud (text to speech), and messages in another language can be translated into yours, automatically or on demand. Pick your language in the chat header (English, Spanish, Hindi, Chinese, French, Japanese, Portuguese).
- Speech to text uses the browser's Web Speech API: Chrome or Edge, with a network connection.
- Text to speech uses `speechSynthesis`: all modern browsers.
- Translation uses Chrome's on-device Translator API (Chrome 138+); otherwise the API's `/v1/translate` with `GEMINI_API_KEY`. With neither, the chat says translation isn't available rather than faking it.

Vendors with `autoQuote: false` (Otter Cove Dive Co., Redwood Skydive Co., Stillwater Kayak Tours) make the group wait for a person to approve the quote, which is the step that shows the two sides talking. The scuba run ends with Otter Cove, the skydiving run with Redwood, and kayaking with Harbor Paddle Co. (automatic).

**Two-laptop demo:** open `/` on one laptop (customer, switch identity in the header to approve as Ana and Ravi) and `/vendor` on the other (staff, pick Marcus Bell for scuba, Ken Watanabe for skydiving). `node tests/e2e/two_sided_walk.js` runs exactly that in two browser contexts.

## What is real and what is simulated

The UI labels every simulated thing on screen; this table is the same information for the team.

| Part | Status in this build | Label in the UI |
|---|---|---|
| Goal compiler | Rule-based template compiler (scuba, ski, tennis, carpool, group buy, generic). Gemini adapter written, **not yet run against the API** | "Compiled offline" |
| Matching | Real hard filters with reasons; local TF-IDF ranker. Moss adapter **not written** | "Ranked locally" |
| Negotiation | Real mediator + personal-agent logic. In the API, agents run in-process (`TRANSPORT=inproc`). `agents/bureau_demo.py` runs the same logic over **real uAgents messages** in a local Bureau | "Agents: inproc" |
| Providers | Six fictional vendors (2 per activity) with fixture price rules that staff can edit; provider agents run in-process | "Simulated" |
| Commitment | Simulated ledger by default. `PAYMENTS=x402_testnet`: each member's agent pays a real x402 deposit in test USDC on Base Sepolia (tested end to end with real EIP-3009 signatures against a stand-in facilitator; **not yet run against x402.org with funded wallets**). Mainnet refused | "Simulated, no money moved" / "Testnet deposit" + explorer link |
| State | `STORE=convex`: batched write-through, membership-checked browser reads, vendor portal live, restart recovery (groups resume mid-negotiation). Verified with convex-test and a fake client; **not yet run against a deployment** | Control room light |
| Identity | Demo personas with HMAC tokens | "Demo identity" |

## Measured results (reproducible, nothing estimated)

`python scripts/rally.py eval` runs the real mediator on 50 generated groups (2 to 6 people, random private preferences, public constraints that admit at least one plan) and compares against an oracle that sees everyone's preferences. Latest run, committed in `tests/evaluation/results/negotiation.json`:

| Metric | Result |
|---|---|
| Hard-constraint violations in proposals sent | **0** |
| Agreement rate (any group size ≥ 2) | 56% |
| Full-group agreement where a unanimous plan exists | 66.7% (16 of 24) |
| Mean / max rounds | 3.2 / 10 |
| Agreed plan's total member score vs oracle best | 97.1% |

Full-group agreement is the number to improve next (Person A). The scuba demo scenario converges in 4 rounds, both in-process and over uAgents.

Tests: `python scripts/rally.py test` runs 131 tests, including the vendor review, discount limits, booking confirmation, vendor/customer chat permissions and all three activities, plus Hypothesis property tests that the mediator never sends a plan violating a known hard constraint and always terminates, every allowed and forbidden state transition, version-bound idempotent approvals, private-preference leak checks on every snapshot, and an HTTP end-to-end run of the whole scuba path. `tests/e2e/two_sided_walk.js` drives the whole path in a real browser as a customer and a vendor at once, and screenshots each screen.

## Layout

```
apps/web/                 Next.js 15 app: 8 pages, design tokens from plan 8.1
services/api/rally/       FastAPI: compiler, matching, negotiation/, providers, service (orchestrator), store
packages/contracts/       Pydantic models = source of truth; gen_ts.py → ts/index.ts (camelCase on the wire)
agents/                   uAgents wire models + bureau_demo.py (real agent messaging, local)
convex/                   schema + server-key-guarded write mutations + snapshot query
data/fixtures/            personas, 10 seeded intents (5 fit, 5 rejected with reasons), private prefs, providers, recorded deal snapshot
tests/                    unit, integration, evaluation, e2e
docs/decisions.md         deviations from the master plan and why
```

The browser sends commands to FastAPI and reads state from one `DealSnapshot` document: from Convex when `NEXT_PUBLIC_CONVEX_URL` is set, otherwise by polling `GET /v1/deals/{id}/snapshot`. Same shape either way, built by one function.

## Next steps by owner

- **A (agents):** wire a `UAgentsTransport` into the API (lift it from `agents/bureau_demo.py`), then Agentverse mailboxes from the venue network. Raise full-group agreement on the eval.
- **B (AI):** set `GEMINI_API_KEY`, `COMPILER=gemini`, confirm the model id and run the 30-goal eval set (not written yet). Moss adapter behind `RANKER=moss`.
- **C (data/infra):** `npx convex dev`, set `RALLY_SERVER_KEY` in Convex and `.env`, run with `STORE=convex`, confirm the room updates live. Then Apify listed prices, then x402 testnet.
- **D (frontend):** polish on the live flow; second goal (tennis) end to end; demo video.

Deploying (Vultr + Caddy + Vercel + Convex): see `infra/DEPLOY.md`.

See `docs/decisions.md` for what this build changed from the plan.
