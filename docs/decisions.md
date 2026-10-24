# Decisions and deviations in the first build

Each item says what the master plan said, what this build does, and when to revisit.

**D1. In-process working copy, Convex as mirror.** Plan 7: Convex is the system of record and FastAPI writes through internal mutations. This build keeps the authoritative copy in the single FastAPI process (per-deal asyncio lock, compare-and-set `transition()` that appends the event in the same step) and writes through to Convex when `STORE=convex`. Why: it let the whole flow run and be tested without a Convex deployment. Gap: no recovery from Convex after an API restart (`make reset` instead). Revisit once Convex is deployed.

**D2. Generic Convex tables plus a snapshot document.** Plan 11.3 has one typed table per entity. This build stores `rows {table, rid, doc}` and one `snapshots {dealId, snapshot}` per deal; the room subscribes to the snapshot. Why: one shape for both read paths, built by one function, so the UI cannot diverge. Revisit when per-entity queries are needed.

**D3. Server-key mutations instead of internal mutations + admin auth.** Plan 11.2 calls internal mutations with the deploy key from Python. This build uses public mutations that check `RALLY_SERVER_KEY`, because calling internal functions from the Python client was not verified. Convex reads are **not yet membership-checked**; fine for demo personas, required before anything else.

**D4. Negotiation engine written fresh.** Plan 15.7 ports `utility()` and `all_bundles()` from Rendezvous. That code was not available to this build (the CALHACKS folder was empty), so `negotiation/engine.py` reimplements weighted additive utility, plan enumeration and the concession curve. Person A should diff against `rendezvous/negotiation.py`.

**D5. Mediator revision rule.** Plan 15.5 scores candidates as `2·|requests satisfied| − |accepting members whose terms change|`. The mediator cannot see which terms an accepting member cares about, so this build uses `2·satisfied − terms changed` (provider swaps cost 0.25), prefers plans that change only requested terms, and only when none exists allows extra changes at a 1.5 penalty each. This raised full-group agreement on the eval from 46% to 67% with zero hard-constraint violations. Every candidate is still drawn from the feasible set F.

**D6. Personal agents answer from the plan space.** To compute u* (best achievable score), each agent receives the public plan space at the start of an attempt. The space is public by construction; no private data moves.

**D7. Approve-as-demo route.** `POST /v1/demo/act-as/{persona}/approve/{deal}` lets a human click approve for a seeded persona. It refuses real teammates and is disabled with `ALLOW_DEMO_ROUTES=0`. Agents never approve.

**D8. Not implemented yet, returning honest errors.** `POST /v1/deals/{id}/proposals` (relax a term) returns 501. `PAYMENTS=x402_testnet` returns 501 at commit time. Deal expiry has a deadline field but no scheduler.

**D9. Windows-friendly runner.** Plan 19.2 uses `make` and `pnpm`. The team lead is on Windows, so `scripts/rally.py` is the canonical runner and `npm` workspaces replace pnpm; the Makefile just calls the script.

**D10. Next.js 15.5.28, React 19.1.10.** Next 15.5.4 is affected by CVE-2025-66478; pinned to the latest patched 15.5 release.
