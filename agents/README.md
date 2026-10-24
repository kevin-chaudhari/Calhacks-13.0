# Agents

`bureau_demo.py` runs the scuba negotiation over **real uAgents messages**: five personal agents (each holds only its owner's private preferences) and one mediator agent, in a local Bureau. The mediator is the same `Mediator` class the API uses, behind a `UAgentsTransport`. It also drops a response whose sender address does not own the member id it claims.

```bash
pip install uagents          # tested with uagents 0.26.1
python agents/bureau_demo.py
```

Verified in the build sandbox: agreement on plan v4 in 4 rounds, about 1 ms per hop on one machine. Venue-network latency will differ.

Not verified yet:
- Agentverse mailbox registration (the sandbox could not reach Fetch.ai's network; uAgents logged "Ledger unavailable", which is harmless for a local Bureau).
- Running the mediator agent inside the FastAPI process (`TRANSPORT=bureau`). Plan: move `UAgentsTransport` into `services/api/rally/negotiation/transport.py` and start the mediator agent on API startup.
- Personal agents on teammates' laptops (needs mailboxes or reachable endpoints).

`protocol.py` mirrors `packages/contracts/rally_contracts/messages.py`; terms travel as JSON strings and are decoded into the shared contract before any logic runs.
