"""Agent transports. The mediator only sees the Transport protocol.

InProcTransport  - personal agents run as objects in this process (TRANSPORT=inproc).
                   Same message models and the same PersonalAgentBrain as real agents.
UAgentsTransport - personal agents are real uAgents (agents/run_agents.py or a local Bureau);
                   the mediator agent sends ProposalWire and awaits ResponseWire (TRANSPORT=agentverse).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

from rally_contracts import ProposalMsg, ResponseMsg

from .engine import Plan
from .personal import PersonalAgentBrain


class InProcTransport:
    mode = "inproc"

    def __init__(self, brains: dict[str, PersonalAgentBrain], latency_s: float = 0.0,
                 offline: set[str] | None = None):
        self.brains = brains
        self.latency_s = latency_s
        self.offline = offline or set()          # fault injection: these members never answer
        self.withdrawn: set[str] = set()         # owner left the group: agent answers "withdraw"
        self.log: list[dict] = []

    async def set_plan_space(self, member_ids: list[str], plans: list[Plan]) -> None:
        for m in member_ids:
            if m in self.brains:
                self.brains[m].set_plan_space(plans)

    async def gather(self, msg: ProposalMsg, member_ids: list[str],
                     timeout_s: float) -> dict[str, ResponseMsg | None]:
        async def one(m: str) -> tuple[str, ResponseMsg | None]:
            if m in self.offline or m not in self.brains:
                return m, None
            if self.latency_s:
                await asyncio.sleep(self.latency_s)
            if m in self.withdrawn:
                return m, ResponseMsg(msg_id=f"w-{msg.msg_id}-{m}", deal_id=msg.deal_id,
                                      proposal_version=msg.proposal_version, member_id=m, kind="withdraw")
            resp = self.brains[m].respond(msg)
            self.log.append({"to": m, "type": "ProposalMsg", "version": msg.proposal_version,
                             "reply": resp.kind})
            return m, resp

        pairs = await asyncio.gather(*(one(m) for m in member_ids))
        return dict(pairs)


log = logging.getLogger("rally.transport")
Send = Callable[[str, Any], Awaitable[None]]


class UAgentsTransport:
    """Same interface as InProcTransport, over real uAgents messages.

    send(address, wire_msg) is the mediator agent's ctx.send. Responses come back through
    deliver(), which the mediator agent's ResponseWire handler calls. A response counts only
    if its sender address owns the member id it claims; anything else is dropped.
    """

    def __init__(self, deal_id: str, send: Send, addresses: dict[str, str], intents: dict[str, str] | None = None,
                 rounds: int = 5, live_prefs: dict[str, dict] | None = None, mode: str = "agentverse"):
        self.deal_id = deal_id
        self.send = send
        self.addresses = addresses               # member id -> personal agent address
        self.intents = intents or {}             # member id -> intent id
        self.rounds = rounds
        self.live_prefs = live_prefs or {}       # member id -> prefs for goals typed live (not in fixtures)
        self.mode = mode
        self.withdrawn: set[str] = set()         # owner left via the app: answer "withdraw" for them
        self.offline: set[str] = set()
        self.waiting: dict[tuple[str, int], asyncio.Future] = {}
        self.sent_at: dict[tuple[str, int], float] = {}
        self.latency_ms: dict[str, float] = {}   # member id -> last round-trip, for AgentMessage.latency_ms
        self.hops: list[float] = []
        self.dropped: list[dict] = []

    async def set_plan_space(self, member_ids: list[str], plans: list[Plan]) -> None:
        from .wire import PlanSpaceWire, PrefsWire

        payload = json.dumps([[p.t, p.provider_id, p.price_per_person] for p in plans])
        for m in member_ids:
            if m not in self.addresses:
                continue
            if m in self.live_prefs:
                await self.send(self.addresses[m], PrefsWire(member_id=m, intent_id=self.intents.get(m, ""),
                                                             prefs_json=json.dumps(self.live_prefs[m])))
            await self.send(self.addresses[m], PlanSpaceWire(deal_id=self.deal_id, plans_json=payload, member_id=m,
                                                             intent_id=self.intents.get(m, ""), rounds=self.rounds))

    async def gather(self, msg: ProposalMsg, member_ids: list[str],
                     timeout_s: float) -> dict[str, ResponseMsg | None]:
        from .wire import ProposalWire

        loop = asyncio.get_running_loop()
        out: dict[str, ResponseMsg | None] = {}
        futs: dict[str, asyncio.Future] = {}
        wire = ProposalWire(msg_id=msg.msg_id, deal_id=msg.deal_id, proposal_version=msg.proposal_version,
                            round=msg.round, terms_json=json.dumps(msg.terms), provider_id=msg.provider_id,
                            price_per_person=msg.price_per_person, currency=msg.currency, respond_by=msg.respond_by)
        for m in member_ids:
            if m in self.withdrawn:
                out[m] = ResponseMsg(msg_id=f"w-{msg.msg_id}-{m}", deal_id=msg.deal_id,
                                     proposal_version=msg.proposal_version, member_id=m, kind="withdraw")
                continue
            if m in self.offline or m not in self.addresses:
                out[m] = None
                continue
            key = (m, msg.proposal_version)
            futs[m] = self.waiting[key] = loop.create_future()
            self.sent_at[key] = time.perf_counter()
            await self.send(self.addresses[m], wire)
        if futs:
            await asyncio.wait(futs.values(), timeout=timeout_s)
        for m, f in futs.items():
            self.waiting.pop((m, msg.proposal_version), None)
            out[m] = f.result() if f.done() and not f.cancelled() else None
            if out[m] is None:
                f.cancel()
        return out

    def deliver(self, sender: str, w: Any) -> bool:
        """Called with each ResponseWire the mediator agent receives. Returns True if accepted."""
        if self.addresses.get(w.member_id) != sender:
            self.dropped.append({"memberId": w.member_id, "sender": sender, "problem": "sender does not own member"})
            log.warning("dropped response: %s… does not own %s", sender[:20], w.member_id)
            return False
        key = (w.member_id, w.proposal_version)
        f = self.waiting.get(key)
        if f is None or f.done():
            return False                         # late or duplicate: the mediator already moved on
        ms = round((time.perf_counter() - self.sent_at.pop(key)) * 1000, 1)
        self.latency_ms[w.member_id] = ms
        self.hops.append(ms)
        f.set_result(ResponseMsg(msg_id=w.msg_id, deal_id=w.deal_id, proposal_version=w.proposal_version,
                                 member_id=w.member_id, kind=w.kind, term=w.term,
                                 preferred=json.loads(w.preferred_json) if w.preferred_json else None))
        return True
