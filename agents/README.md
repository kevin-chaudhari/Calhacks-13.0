# Agents

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Rally runs 27 uAgents. Every identity comes from `AGENT_SEED_PREFIX`, so the API and the agents process derive the same addresses without asking the network.

| Agent | Count | Where it runs | What it does |
|---|---|---|---|
| Group mediator | 1 | inside the API (FastAPI lifespan) | Sends `PlanSpaceWire` / `ProposalWire`, takes `ResponseWire`; the only agent that writes through `service.py` |
| Personal agents | 20 (one per person) | `agents/run_agents.py` | Hold their owner's private prefs per goal; answer with accept, one change request, or a hard no |
| Provider agents | 6 (one per vendor) | `agents/run_agents.py` | Answer `QuoteRequestWire` from `data/fixtures/providers.json` |

| Rally concierge | 1 | `agents/concierge.py` | Chat Protocol agent for ASI:One: a typed goal becomes a negotiated group plan with a room link |

Shared code: `services/api/rally/negotiation/` has `wire.py` (message models), `network.py` (seeds, ports, agent factory) and `transport.py` (`UAgentsTransport`, same interface as `InProcTransport`).

## Run it over the network

```bash
pip install uagents uagents-core        # tested with uagents 0.26.1

# Local, no Fetch.ai account: real uAgents messages over HTTP on localhost
AGENT_NETWORK=local python agents/run_agents.py                     # terminal 1
TRANSPORT=agentverse AGENT_NETWORK=local python scripts/rally.py dev # terminal 2
TRANSPORT=agentverse AGENT_NETWORK=local python -m pytest tests/integration/test_transport_agentverse.py

# Agentverse mailboxes (set a private AGENT_SEED_PREFIX and AGENTVERSE_API_KEY in .env first)
python agents/run_agents.py                                         # terminal 1
TRANSPORT=agentverse python scripts/rally.py dev                    # terminal 2
python agents/connect_agentverse.py                                 # once: registers all 27 mailboxes
```

With `TRANSPORT=agentverse` the UI badge reads "Agents: agentverse" only once the mediator agent is actually up; if it fails to start, the API stays in-process and says "inproc".

Goals typed live in the app (not in the fixtures) reach their owner's agent as one `PrefsWire` from the API, which received them from the owner's browser, just before the plan space. The mediator logic never reads them.

`bureau_demo.py` runs the same negotiation in a single local Bureau, using the same `UAgentsTransport`:

```bash
python agents/bureau_demo.py     # agreed on v4 in 4 rounds, ~1 ms per hop on one machine
```

## Rally on ASI:One (concierge)

`agents/concierge.py` speaks the Chat Protocol (`ChatMessage` / `ChatAcknowledgement`, manifest published) through an Agentverse mailbox, so ASI:One can route a goal to it. For each goal it calls the Rally API (compile → answer a missing question → publish → matches → deal → negotiate → poll the snapshot) and replies in three messages: what Rally understood, who matched and who didn't (with reasons), and the agreed plan with the price per person and a link to `RALLY_WEB_URL/deals/<id>`.

```bash
python agents/concierge.py        # needs RALLY_API_URL, RALLY_WEB_URL; mailbox via connect_agentverse.py
```

```
You:   Scuba in Monterey next month under $300, I'm Open Water.
Rally: How many people at most, including you? (for example 4, 5, 6)
You:   5
Rally: Here's what I understood: Scuba diving, near Monterey, CA, Nov 1–Nov 30, up to $300 per person, ...
Rally: Found 4 people who fit: Ana, Maya, Kai, Eli. Not a fit: Luis (Only free Dec 19–Dec 31); ...
Rally: Agreed! All 5 agents accepted plan v3 in 3 rounds: Nov 21, boat dive, gear included, Lovers Point
       with Kelp Line Divers, $199 per person (simulated quote). Everyone approves in the group room: <link>
```

**Identity (demo):** ASI:One senders map to `CONCIERGE_PERSONAS` in order of first contact. By default that is only `u_kevin`, so **the first sender (and every sender) acts as Kevin**. Say "start over" to drop a half-finished goal.

**Repeat runs:** people already in a deal aren't matched again, so a second chat finds nobody until the board is reset. Set `CONCIERGE_RESET_EACH_GOAL=1` for judging; it resets the scuba scenario before each new goal (earlier rooms end).

Tests: `tests/unit/test_concierge.py` (fake API: the three replies, the follow-up question, errors) and `tests/integration/test_concierge_api.py` (the real API in-process).

## Addresses

Generated with `python agents/connect_agentverse.py --table` using the team's private `AGENT_SEED_PREFIX`. Not filled in yet.

## Not done yet

- Provider agents run and answer `QuoteRequestWire`, but the API still prices quotes from its own copy of the vendor sheets (so vendor edits in the portal apply); the price-sheet request is not yet sent over the network.
- Invites and joins (`InviteMsg` / `JoinMsg`) are still decided in the API.
