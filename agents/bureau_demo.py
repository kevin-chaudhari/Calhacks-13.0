"""Real uAgents messaging for the scuba scenario, in a local Bureau (TRANSPORT=bureau).

    python agents/bureau_demo.py

Five personal agents (each holding only its owner's private preferences) and one
mediator agent. The mediator runs the SAME Mediator class the API uses, through a
UAgentsTransport that sends ProposalWire and awaits ResponseWire. Prints every hop
with latency. Agentverse mailbox registration is not attempted here (needs network
and an Agentverse account; see agents/README.md).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/contracts"), str(ROOT / "services/api"), str(ROOT / "agents")]

from uagents import Agent, Bureau, Context  # noqa: E402

from protocol import PlanSpaceWire, ProposalWire, ResponseWire  # noqa: E402
from rally.negotiation.engine import Plan, PublicConstraints, enumerate_plans  # noqa: E402
from rally.negotiation.mediator import Mediator  # noqa: E402
from rally.negotiation.personal import PersonalAgentBrain  # noqa: E402
from rally.providers import load_providers, sheets  # noqa: E402
from rally_contracts import PrivatePrefs, ProposalMsg, ResponseMsg  # noqa: E402

FIX = ROOT / "data/fixtures"
MEMBERS = ["u_kevin", "u_ana", "u_ravi", "u_maya", "u_kai"]
WINDOWS = {}
for it in json.loads((FIX / "intents_scuba.json").read_text(encoding="utf-8"))["intents"]:  # noqa: E501
    WINDOWS[it["userId"]] = (it["draft"]["dateFrom"], it["draft"]["dateTo"], it["draft"]["budgetMax"]["amount"])
WINDOWS["u_kevin"] = ("2026-11-01", "2026-11-30", 300)
_ALL = json.loads((FIX / "private_prefs.json").read_text(encoding="utf-8"))["prefs"]
PREFS = {u: PrivatePrefs.model_validate(_ALL["default:scuba_diving" if u == "u_kevin" else "i_" + u[2:]]).model_dump()
         for u in MEMBERS}
OPTIONS = {"date": ["2026-11-07", "2026-11-08", "2026-11-14", "2026-11-15", "2026-11-21", "2026-11-22"],
           "site": ["Breakwater Cove", "Lovers Point", "Point Lobos"], "dive_type": ["shore", "boat"],
           "gear_included": [True, False]}

bureau = Bureau(port=8010, endpoint=None)
personal: dict[str, Agent] = {}


def make_personal(uid: str) -> Agent:
    agent = Agent(name=f"rally-{uid}", seed=f"rally demo personal agent {uid} local only")
    brain = PersonalAgentBrain(uid, PREFS[uid], rounds=5)    # private prefs live only here

    @agent.on_message(model=PlanSpaceWire)
    async def on_space(ctx: Context, sender: str, msg: PlanSpaceWire):
        brain.set_plan_space([Plan(tuple(sorted(t.items())), p, price) for t, p, price in json.loads(msg.plans_json)])

    @agent.on_message(model=ProposalWire)
    async def on_proposal(ctx: Context, sender: str, msg: ProposalWire):
        resp = brain.respond(ProposalMsg(msg_id=msg.msg_id, deal_id=msg.deal_id, proposal_version=msg.proposal_version,
                                         round=msg.round, terms=json.loads(msg.terms_json), provider_id=msg.provider_id,
                                         price_per_person=msg.price_per_person, respond_by=msg.respond_by))
        await ctx.send(sender, ResponseWire(msg_id=resp.msg_id, deal_id=resp.deal_id,
                                            proposal_version=resp.proposal_version, member_id=resp.member_id,
                                            kind=resp.kind, term=resp.term,
                                            preferred_json=json.dumps(resp.preferred)))
    return agent


for uid in MEMBERS:
    personal[uid] = make_personal(uid)
    bureau.add(personal[uid])

mediator_agent = Agent(name="rally-mediator", seed="rally demo mediator agent local only")
bureau.add(mediator_agent)


class UAgentsTransport:
    mode = "bureau"

    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.waiting: dict[tuple[str, int], asyncio.Future] = {}
        self.hops: list[float] = []

    async def set_plan_space(self, member_ids, plans):
        payload = json.dumps([[p.t, p.provider_id, p.price_per_person] for p in plans])
        for m in member_ids:
            await self.ctx.send(personal[m].address, PlanSpaceWire(deal_id="d_bureau", plans_json=payload))

    async def gather(self, msg: ProposalMsg, member_ids, timeout_s):
        loop = asyncio.get_running_loop()
        sent_at = time.perf_counter()
        futs = {m: loop.create_future() for m in member_ids}
        for m, f in futs.items():
            self.waiting[(m, msg.proposal_version)] = f
            await self.ctx.send(personal[m].address, ProposalWire(
                msg_id=msg.msg_id, deal_id=msg.deal_id, proposal_version=msg.proposal_version, round=msg.round,
                terms_json=json.dumps(msg.terms), provider_id=msg.provider_id,
                price_per_person=msg.price_per_person, currency=msg.currency, respond_by=msg.respond_by))
        out = {}
        for m, f in futs.items():
            try:
                out[m] = await asyncio.wait_for(f, timeout_s)
                self.hops.append((time.perf_counter() - sent_at) * 1000)
            except asyncio.TimeoutError:
                out[m] = None
        return out

    def deliver(self, sender: str, w: ResponseWire):
        owner = next((u for u, a in personal.items() if a.address == sender), None)
        if owner is None or owner != w.member_id:
            print(f"  dropped message: sender {sender[:16]}… does not own member {w.member_id}")
            return
        f = self.waiting.pop((w.member_id, w.proposal_version), None)
        if f and not f.done():
            f.set_result(ResponseMsg(msg_id=w.msg_id, deal_id=w.deal_id, proposal_version=w.proposal_version,
                                     member_id=w.member_id, kind=w.kind, term=w.term,
                                     preferred=json.loads(w.preferred_json) if w.preferred_json else None))


class PrintHooks:
    async def proposal(self, plan, version, r, attempt, rationale, changed):
        print(f"v{version} round {r}: {plan.t} @ {plan.provider_id} ${plan.price_per_person:.0f}")

    async def responses(self, version, r, attempt, responses, outcome, accepted, active):
        print("   " + ", ".join(f"{m[2:]}={x.kind}{'(' + x.term + ')' if x and x.term else ''}" if x else f"{m[2:]}=timeout"
                              for m, x in responses.items()) + f"  -> {outcome} {accepted}/{active}")

    async def note(self, *a):
        print("   note:", a[1])

    async def member_state(self, m, state, reason):
        print(f"   {m}: {state} ({reason})")


transport: UAgentsTransport | None = None


@mediator_agent.on_message(model=ResponseWire)
async def on_response(ctx: Context, sender: str, msg: ResponseWire):
    transport.deliver(sender, msg)


@mediator_agent.on_event("startup")
async def start(ctx: Context):
    global transport
    transport = UAgentsTransport(ctx)

    async def run():
        await asyncio.sleep(1.0)
        plans = enumerate_plans(OPTIONS, sheets([p for p in load_providers() if p["activity"] == "scuba_diving"]), len(MEMBERS))
        cons = {m: PublicConstraints(*WINDOWS[m]) for m in MEMBERS}
        med = Mediator("d_bureau", plans, cons, transport, PrintHooks(), rounds=5, restarts=1, group_min=2,
                       timeout_s=10.0, term_keys=set(OPTIONS))
        t0 = time.perf_counter()
        res = await med.run(MEMBERS)
        hops = sorted(transport.hops)
        print(f"\nagreed={res.agreed} version={res.version} rounds={res.rounds_used} "
              f"wall={time.perf_counter() - t0:.2f}s  hop latency p50={hops[len(hops) // 2]:.1f}ms max={hops[-1]:.1f}ms "
              f"(local Bureau on one machine; venue-network latency will differ)")
        sys.stdout.flush()
        os._exit(0 if res.agreed else 1)          # stop the Bureau's servers immediately

    asyncio.ensure_future(run())


if __name__ == "__main__":
    bureau.run()
