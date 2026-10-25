"""Parley's personal and provider agents as real uAgents, in one process.

    python agents/run_agents.py                 # AGENT_NETWORK=mailbox (Agentverse), the default
    AGENT_NETWORK=local python agents/run_agents.py   # plain HTTP on localhost, no account needed

One personal agent per customer persona (holding that person's private prefs per goal,
from data/fixtures/private_prefs.json) and one provider agent per vendor (answering
QuoteRequestWire from data/fixtures/providers.json). Seeds come from AGENT_SEED_PREFIX, so
addresses are stable across restarts and match what the API computes. Agents only take
negotiation messages from the Parley mediator's address.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/contracts"), str(ROOT / "services/api")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # agent names contain "·"

from uagents import Agent, Context  # noqa: E402

from rally.negotiation import network  # noqa: E402
from rally.negotiation.engine import Plan  # noqa: E402
from rally.negotiation.personal import PersonalAgentBrain  # noqa: E402
from rally.negotiation.wire import (PlanSpaceWire, PrefsWire, ProposalWire, QuoteRequestWire,  # noqa: E402
                                    QuoteWire, ResponseWire)
from rally.providers import load_providers, sheets  # noqa: E402
from rally_contracts import PrivatePrefs, ProposalMsg  # noqa: E402

FIX = ROOT / "data/fixtures"


def fixture_prefs() -> dict[str, dict[str, dict]]:
    """user id -> intent id -> engine prefs, for every seeded intent."""
    raw = json.loads((FIX / "private_prefs.json").read_text(encoding="utf-8"))["prefs"]
    out: dict[str, dict[str, dict]] = {}
    for f in sorted(FIX.glob("intents_*.json")):
        for it in json.loads(f.read_text(encoding="utf-8"))["intents"]:
            if it["id"] in raw:
                out.setdefault(it["userId"], {})[it["id"]] = \
                    PrivatePrefs.model_validate(raw[it["id"]]).model_dump(by_alias=False)
    return out


def make_personal(spec: network.AgentSpec, prefs: dict[str, dict], mediator: str, loop) -> Agent:
    agent = network.make_agent(spec, loop)
    uid = spec.owner
    brains: dict[str, PersonalAgentBrain] = {}      # deal id -> brain; private prefs never leave this process

    @agent.on_message(model=PrefsWire)
    async def on_prefs(ctx: Context, sender: str, msg: PrefsWire):
        if sender != mediator or msg.member_id != uid:
            return
        prefs[msg.intent_id] = json.loads(msg.prefs_json)

    @agent.on_message(model=PlanSpaceWire)
    async def on_space(ctx: Context, sender: str, msg: PlanSpaceWire):
        if sender != mediator:
            return
        p = prefs.get(msg.intent_id)
        if p is None:
            ctx.logger.warning(f"no preferences for goal {msg.intent_id}; staying silent")
            brains.pop(msg.deal_id, None)
            return
        brain = PersonalAgentBrain(uid, p, msg.rounds)
        brain.set_plan_space([Plan(tuple(sorted(t.items())), pid, price) for t, pid, price in json.loads(msg.plans_json)])
        brains[msg.deal_id] = brain

    @agent.on_message(model=ProposalWire)
    async def on_proposal(ctx: Context, sender: str, msg: ProposalWire):
        brain = brains.get(msg.deal_id)
        if sender != mediator or brain is None:
            return
        resp = brain.respond(ProposalMsg(msg_id=msg.msg_id, deal_id=msg.deal_id, proposal_version=msg.proposal_version,
                                         round=msg.round, terms=json.loads(msg.terms_json), provider_id=msg.provider_id,
                                         price_per_person=msg.price_per_person, currency=msg.currency,
                                         respond_by=msg.respond_by))
        await ctx.send(sender, ResponseWire(msg_id=resp.msg_id, deal_id=resp.deal_id,
                                            proposal_version=resp.proposal_version, member_id=resp.member_id,
                                            kind=resp.kind, term=resp.term,
                                            preferred_json=json.dumps(resp.preferred)))
    return agent


def make_provider(spec: network.AgentSpec, provider: dict, loop) -> Agent:
    agent = network.make_agent(spec, loop)
    sheet = sheets([provider])[0]

    @agent.on_message(model=QuoteRequestWire)
    async def on_quote_request(ctx: Context, sender: str, msg: QuoteRequestWire):
        price = sheet.price(json.loads(msg.terms_json), msg.group_size) if msg.terms_json else None
        await ctx.send(sender, QuoteWire(msg_id=msg.msg_id, deal_id=msg.deal_id, provider_id=provider["id"],
                                         tiers_json=json.dumps(provider["tiers"]),
                                         available_dates=provider["availableDates"],
                                         offers_json=json.dumps(provider["offers"]), price_per_person=price,
                                         provenance=provider.get("provenance", "simulated")))
    return agent


async def main() -> None:
    loop = asyncio.get_running_loop()
    specs = network.directory()
    mediator = network.address_of("mediator")
    prefs = fixture_prefs()
    providers = {p["id"]: p for p in load_providers()}
    agents = []
    for s in specs:
        if s.kind == "personal":
            agents.append(make_personal(s, prefs.setdefault(s.owner, {}), mediator, loop))
        elif s.kind == "provider":
            agents.append(make_provider(s, providers[s.owner], loop))
    print(f"Parley agents ({network.network_mode()}), mediator {mediator}")
    for s in specs:
        if s.kind in {"personal", "provider"}:
            print(f"  {s.port}  {s.address}  {s.name}")
    sys.stdout.flush()
    await asyncio.gather(*(a.run_async() for a in agents))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
