# Agents

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Rally runs 27 uAgents. Every identity comes from `AGENT_SEED_PREFIX`, so the API and the agents process derive the same addresses without asking the network.

| Agent | Count | Where it runs | What it does |
|---|---|---|---|
| Group mediator | 1 | inside the API (FastAPI lifespan) | Sends `PlanSpaceWire` / `ProposalWire`, takes `ResponseWire`; the only agent that writes through `service.py` |
| Personal agents | 20 (one per person) | `agents/run_agents.py` | Hold their owner's private prefs per goal; answer with accept, one change request, or a hard no |
| Provider agents | 6 (one per vendor) | `agents/run_agents.py` | Answer `QuoteRequestWire` from `data/fixtures/providers.json` |

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

## Addresses

Generated with `python agents/connect_agentverse.py --table` using the team's private `AGENT_SEED_PREFIX`. Not filled in yet.

## Not done yet

- Provider agents run and answer `QuoteRequestWire`, but the API still prices quotes from its own copy of the vendor sheets (so vendor edits in the portal apply); the price-sheet request is not yet sent over the network.
- Invites and joins (`InviteMsg` / `JoinMsg`) are still decided in the API.
