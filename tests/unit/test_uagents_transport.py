"""UAgentsTransport without a network: a fake send() plays the personal agents."""
import asyncio
import json

import pytest

pytest.importorskip("uagents")

from rally.negotiation.engine import Plan  # noqa: E402
from rally.negotiation.mediator import Mediator  # noqa: E402
from rally.negotiation.personal import PersonalAgentBrain  # noqa: E402
from rally.negotiation.transport import UAgentsTransport  # noqa: E402
from rally.negotiation.wire import PlanSpaceWire, PrefsWire, ProposalWire, ResponseWire  # noqa: E402
from rally_contracts import ProposalMsg  # noqa: E402

PREFS = {"weights": {"site": 1.0}, "best": {"site": "B"}}
PLANS = [Plan((("site", "A"),), "p1", 100.0), Plan((("site", "B"),), "p1", 120.0)]


class FakeNet:
    """Each address is an agent; replies are delivered back like the mediator agent's handler would."""

    def __init__(self, members, silent=(), spoof_as=None):
        self.addr = {m: f"agent1q{m}" for m in members}
        self.prefs: dict[str, dict] = {}
        self.brains: dict[str, PersonalAgentBrain] = {}
        self.silent, self.spoof_as = set(silent), spoof_as
        self.transport: UAgentsTransport | None = None

    async def send(self, address, msg):
        m = next(u for u, a in self.addr.items() if a == address)
        if isinstance(msg, PrefsWire):
            self.prefs[m] = json.loads(msg.prefs_json)
        elif isinstance(msg, PlanSpaceWire):
            self.brains[m] = PersonalAgentBrain(m, self.prefs.get(m, PREFS), msg.rounds)
            self.brains[m].set_plan_space([Plan(tuple(sorted(t.items())), p, x) for t, p, x in json.loads(msg.plans_json)])
        elif isinstance(msg, ProposalWire) and m not in self.silent:
            r = self.brains[m].respond(ProposalMsg(msg_id=msg.msg_id, deal_id=msg.deal_id,
                                                   proposal_version=msg.proposal_version, round=msg.round,
                                                   terms=json.loads(msg.terms_json), provider_id=msg.provider_id,
                                                   price_per_person=msg.price_per_person, respond_by=msg.respond_by))
            sender = self.addr[self.spoof_as] if self.spoof_as and m != self.spoof_as else address
            wire = ResponseWire(msg_id=r.msg_id, deal_id=r.deal_id, proposal_version=r.proposal_version,
                                member_id=r.member_id, kind=r.kind, term=r.term, preferred_json=json.dumps(r.preferred))
            asyncio.get_running_loop().call_soon(self.transport.deliver, sender, wire)

    def make(self, **kw):
        self.transport = UAgentsTransport("d1", self.send, self.addr, {m: f"i_{m}" for m in self.addr}, **kw)
        return self.transport


class _Hooks:
    async def proposal(self, *a): ...
    async def responses(self, *a): ...
    async def note(self, *a): ...
    async def member_state(self, *a): ...


def test_mediator_agrees_over_the_transport_and_records_latency():
    net = FakeNet(["a", "b"])
    t = net.make()
    res = asyncio.run(Mediator("d1", PLANS, {}, t, _Hooks(), timeout_s=2).run(["a", "b"]))
    assert res.agreed and res.plan.t == {"site": "B"}
    assert set(t.latency_ms) == {"a", "b"} and all(v >= 0 for v in t.latency_ms.values())


def test_live_prefs_reach_the_owners_agent_before_the_plan_space():
    net = FakeNet(["a", "b"])
    t = net.make(live_prefs={"a": {"weights": {"site": 1.0}, "best": {"site": "A"}}})
    asyncio.run(t.set_plan_space(["a", "b"], PLANS))
    assert net.prefs == {"a": {"weights": {"site": 1.0}, "best": {"site": "A"}}}


def test_silent_and_spoofed_members_count_as_no_answer():
    net = FakeNet(["a", "b", "c"], silent={"c"}, spoof_as="a")
    t = net.make()

    async def go():
        await t.set_plan_space(["a", "b", "c"], PLANS)
        msg = ProposalMsg(msg_id="m1", deal_id="d1", proposal_version=1, round=1, terms={"site": "B"},
                          provider_id="p1", price_per_person=120.0, respond_by=0)
        return await t.gather(msg, ["a", "b", "c"], timeout_s=0.3)

    out = asyncio.run(go())
    assert out["a"] is not None and out["a"].kind == "accept"
    assert out["b"] is None                       # b's reply arrived from a's address: dropped
    assert out["c"] is None                       # c never answered: timeout
    assert t.dropped == [{"memberId": "b", "sender": "agent1qa", "problem": "sender does not own member"}]


def test_withdrawn_member_answers_withdraw_without_a_network_hop():
    net = FakeNet(["a", "b"])
    t = net.make()
    t.withdrawn.add("b")
    asyncio.run(t.set_plan_space(["a", "b"], PLANS))
    msg = ProposalMsg(msg_id="m1", deal_id="d1", proposal_version=1, round=1, terms={"site": "B"},
                      provider_id="p1", price_per_person=120.0, respond_by=0)
    out = asyncio.run(t.gather(msg, ["a", "b"], timeout_s=0.5))
    assert out["b"].kind == "withdraw" and out["a"].kind == "accept"
