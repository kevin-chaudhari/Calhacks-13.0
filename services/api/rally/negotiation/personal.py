"""Personal agent decision logic (plan section 15.3).

Used by the in-process simulator AND by agents/personal/agent.py (uAgents), so
simulated and real agents answer identically. Private preferences never leave
this object: responses carry one word, at most one term, and a public option.
"""

from __future__ import annotations

import uuid
from typing import Any

from rally_contracts import ProposalMsg, ResponseMsg

from .engine import VIOLATES, Plan, term_score, threshold, utility


class PersonalAgentBrain:
    def __init__(self, member_id: str, prefs: dict, rounds: int = 5):
        self.member_id = member_id
        self.prefs = prefs                  # PrivatePrefs as a dict; never serialized out
        self.rounds = rounds
        self.space: list[Plan] = []
        self.price_lo = 0.0
        self.price_hi = 1.0
        self.u_star = 1.0

    def set_plan_space(self, plans: list[Plan]) -> None:
        """The plan space is public; the agent uses it to compute its best achievable score."""
        self.space = plans
        prices = [p.price_per_person for p in plans] or [0.0, 1.0]
        self.price_lo, self.price_hi = min(prices), max(prices)
        scores = [utility(p, self.prefs, self.price_lo, self.price_hi) for p in plans]
        ok = [u for u, v in scores if v is None]
        self.u_star = max(ok) if ok else 0.0

    def _plan_from(self, msg: ProposalMsg) -> Plan:
        return Plan(tuple(sorted(msg.terms.items())), msg.provider_id, msg.price_per_person)

    def respond(self, msg: ProposalMsg) -> ResponseMsg:
        plan = self._plan_from(msg)
        u, violated = utility(plan, self.prefs, self.price_lo, self.price_hi)
        base = dict(msg_id=str(uuid.uuid4()), deal_id=msg.deal_id,
                    proposal_version=msg.proposal_version, member_id=self.member_id)
        if violated:
            return ResponseMsg(**base, kind="reject_hard", term=violated,
                               preferred=self._json(plan.get(violated)))
        tau = threshold(self.u_star, self.prefs.get("reservation", 0.35), msg.round,
                        self.rounds, self.prefs.get("patience", 1.0))
        if u >= tau - 1e-9:
            return ResponseMsg(**base, kind="accept")
        term = self._worst_term(plan)
        return ResponseMsg(**base, kind="change_request", term=term,
                           preferred=self._json(self._preferred(term, plan)))

    # -- helpers ---------------------------------------------------------

    def _worst_term(self, plan: Plan) -> str:
        """Term with the largest weighted loss w * (1 - s). Ties: alphabetical."""
        losses = []
        for key, w in self.prefs["weights"].items():
            s = term_score(key, plan.get(key), self.prefs, self.price_lo, self.price_hi)
            s = 0.0 if s == VIOLATES else float(s)
            losses.append((-(w * (1 - s)), key))
        losses.sort()
        return losses[0][1]

    def _preferred(self, term: str, plan: Plan) -> Any:
        """The public option for `term` this member scores highest (among plans in the space)."""
        if term == "price_per_person":
            return self.price_lo
        values = sorted({p.get(term) for p in self.space}, key=str)
        best_v, best_s = plan.get(term), -1.0
        for v in values:
            s = term_score(term, v, self.prefs, self.price_lo, self.price_hi)
            if s != VIOLATES and float(s) > best_s:
                best_v, best_s = v, float(s)
        return best_v

    @staticmethod
    def _json(v: Any) -> Any:
        return v if isinstance(v, (str, int, float, bool)) or v is None else str(v)
