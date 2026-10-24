"""Agent transports. The mediator only sees the Transport protocol.

InProcTransport  - personal agents run as objects in this process (TRANSPORT=inproc).
                   Same message models and the same PersonalAgentBrain as real agents.
UAgentsTransport - not implemented in this PR; see agents/README.md for the plan.
"""

from __future__ import annotations

import asyncio

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
