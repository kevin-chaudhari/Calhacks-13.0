"""Group mediator: bounded single-negotiating-text loop (plan sections 15.5, 15.6).

Guarantees, each covered by tests/unit/test_mediator.py:
  * every proposal sent is drawn from F, so it satisfies every known hard constraint;
  * it returns within rounds * (restarts + 1) rounds;
  * it never reports agreement unless every active member accepted that exact version.
It does NOT guarantee the best possible plan.

Agent messages are inputs: each response is validated (deal, version, member,
known term, unseen msg id) before it can influence anything.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from rally_contracts import ProposalMsg, ResponseMsg

from .engine import Plan, PublicConstraints, feasible

PRICE = "price_per_person"
PRICE_FLEX = {"provider", "gear_included", "dive_type"}   # what a price request may change


class Transport(Protocol):
    async def set_plan_space(self, member_ids: list[str], plans: list[Plan]) -> None: ...
    async def gather(self, msg: ProposalMsg, member_ids: list[str],
                     timeout_s: float) -> dict[str, ResponseMsg | None]: ...


class Hooks(Protocol):
    async def proposal(self, plan: Plan, version: int, round_no: int, attempt: int,
                       rationale: list[str], changed: list[str]) -> None: ...
    async def responses(self, version: int, round_no: int, attempt: int,
                        responses: dict[str, ResponseMsg | None], outcome: str,
                        accepted: int, active: int) -> None: ...
    async def note(self, type_: str, summary: str, payload: dict[str, Any]) -> None: ...
    async def member_state(self, member_id: str, state: str, reason: str | None) -> None: ...


@dataclass
class MediationResult:
    agreed: bool
    plan: Plan | None
    version: int
    rounds_used: int
    active: list[str]
    removed: dict[str, str] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    conflicts_by_member: dict[str, str] = field(default_factory=dict)


def changed_terms(p: Plan, q: Plan) -> set[str]:
    a, b = p.t, q.t
    out = {k for k in a if a[k] != b.get(k)}
    if p.provider_id != q.provider_id:
        out.add("provider")
    return out


class Mediator:
    def __init__(self, deal_id: str, plans: list[Plan], constraints: dict[str, PublicConstraints],
                 transport: Transport, hooks: Hooks, *, rounds: int = 5, restarts: int = 1,
                 group_min: int = 2, timeout_s: float = 20.0, term_keys: set[str] | None = None,
                 names: dict[str, str] | None = None, replan=None):
        self.deal_id = deal_id
        self.all_plans = plans
        self.constraints = constraints
        self.transport = transport
        self.hooks = hooks
        self.rounds = rounds
        self.restarts = restarts
        self.group_min = group_min
        self.timeout_s = timeout_s
        self.term_keys = set(term_keys or (plans[0].t if plans else ())) | {PRICE}
        self.names = names or {}
        self.replan = replan                    # callable(active_ids) -> plans, for a new group size
        self.version = 0
        self.seen_msg_ids: set[str] = set()
        self.rounds_used = 0
        self.rejected: list[dict] = []          # invalid agent messages, for the audit log

    # ------------------------------------------------------------- public

    async def run(self, members: list[str]) -> MediationResult:
        active = list(members)
        removed: dict[str, str] = {}
        attempt = 1
        while True:
            result = await self._attempt(active, attempt)
            result.removed.update(removed)
            if result.agreed or attempt > self.restarts or len(active) - 1 < self.group_min:
                return result
            drop = self._choose_removal(result, active)
            if drop is None:
                return result
            reason = result.conflicts_by_member.get(drop, "no plan fit their constraints")
            removed[drop] = reason
            active = [m for m in active if m != drop]
            self.constraints.pop(drop, None)
            if self.replan:
                self.all_plans = self.replan(active)
            await self.hooks.member_state(drop, "removed", reason)
            await self.hooks.note("member_removed",
                                  f"Removed {self.names.get(drop, drop)} so the rest can agree: {reason}",
                                  {"memberId": drop, "reason": reason})
            attempt += 1

    # ------------------------------------------------------------ attempt

    async def _attempt(self, active: list[str], attempt: int) -> MediationResult:
        F = feasible(self.all_plans, {m: self.constraints[m] for m in active if m in self.constraints})
        if not F:
            return MediationResult(False, None, self.version, self.rounds_used, active,
                                   conflicts=["No plan satisfies every member's hard constraints."])
        await self.transport.set_plan_space(active, F)
        p = F[0]                                    # lowest price, then canonical id
        rationale = ["Opening plan: the lowest-priced option that fits everyone's hard constraints."]
        changed: list[str] = []
        tabu: set[str] = set()
        history: list[tuple[Plan, int, dict[str, str]]] = []
        last_requests: dict[str, str] = {}

        for r in range(1, self.rounds + 1):
            assert all(self.constraints[m].violated_by(p) is None for m in active if m in self.constraints), \
                "mediator tried to send a plan that violates a hard constraint"
            self.version += 1
            self.rounds_used += 1
            await self.hooks.proposal(p, self.version, r, attempt, rationale, changed)
            msg = ProposalMsg(msg_id=str(uuid.uuid4()), deal_id=self.deal_id,
                              proposal_version=self.version, round=r, terms=p.t,
                              provider_id=p.provider_id, price_per_person=p.price_per_person,
                              respond_by=int((time.time() + self.timeout_s) * 1000))
            raw = await self.transport.gather(msg, active, self.timeout_s)
            responses = {m: self._validate(raw.get(m), m) for m in active}

            # silent members drop out of the active set
            for m, resp in responses.items():
                if resp is None:
                    await self.hooks.member_state(m, "unresponsive", "did not answer in time")
            active = [m for m in active if responses[m] is not None
                      and responses[m].kind != "withdraw"]
            for m, resp in responses.items():
                if resp is not None and resp.kind == "withdraw":
                    await self.hooks.member_state(m, "withdrawn", "left the group")

            accepted = [m for m in active if responses[m].kind == "accept"]
            requests: list[tuple[str, str, Any, str]] = []      # (member, term, preferred, kind)
            for m in active:
                resp = responses[m]
                if resp.kind == "reject_hard" and resp.term:
                    # the member revealed one private hard limit: exclude that value from now on
                    self.constraints.setdefault(m, PublicConstraints()).exclusions.add((resp.term, p.get(resp.term)))
                    requests.append((m, resp.term, None, "reject_hard"))
                elif resp.kind == "change_request" and resp.term:
                    requests.append((m, resp.term, resp.preferred, "change_request"))
            last_requests = {m: t for m, t, _, _ in requests}

            if len(accepted) == len(active) and len(active) >= self.group_min:
                await self.hooks.responses(self.version, r, attempt, responses, "all_accept",
                                           len(accepted), len(active))
                return MediationResult(True, p, self.version, self.rounds_used, active)
            if len(active) < self.group_min:
                await self.hooks.responses(self.version, r, attempt, responses, "stalled",
                                           len(accepted), len(active))
                break

            history.append((p, len(accepted), dict(last_requests)))
            F = feasible(self.all_plans, {m: self.constraints[m] for m in active if m in self.constraints})
            q, why = self._next_plan(p, F, requests, tabu)
            if q is None:
                await self.hooks.responses(self.version, r, attempt, responses, "stalled",
                                           len(accepted), len(active))
                await self.hooks.note("stalled", why, {})
                break
            await self.hooks.responses(self.version, r, attempt, responses,
                                       "revised" if r < self.rounds else "exhausted",
                                       len(accepted), len(active))
            tabu.add(p.id)
            changed = sorted(changed_terms(p, q))
            rationale = why_lines(p, q, requests, self.names)
            p = q

        # no unanimity in this attempt
        feasible_hist = [(pl, n, req) for pl, n, req in history
                         if all(self.constraints[m].violated_by(pl) is None for m in active if m in self.constraints)]
        best = max(feasible_hist, key=lambda h: (h[1], -h[0].price_per_person), default=None)
        conflicts_by_member = dict(best[2]) if best else dict(last_requests)
        conflicts = [f"{self.names.get(m, m)} needs a different {t.replace('_', ' ')}"
                     for m, t in sorted(conflicts_by_member.items())]
        return MediationResult(False, best[0] if best else None, self.version, self.rounds_used,
                               active, conflicts=conflicts,
                               conflicts_by_member={m: f"needs a different {t.replace('_', ' ')}"
                                                    for m, t in conflicts_by_member.items()})

    # ------------------------------------------------------------ helpers

    def _validate(self, resp: ResponseMsg | None, member_id: str) -> ResponseMsg | None:
        """Reject stale, duplicate, spoofed or malformed responses (they count as silence)."""
        if resp is None:
            return None
        problems = []
        if resp.deal_id != self.deal_id:
            problems.append("wrong deal")
        if resp.proposal_version != self.version:
            problems.append("stale version")
        if resp.member_id != member_id:
            problems.append("sender mismatch")
        if resp.msg_id in self.seen_msg_ids:
            problems.append("duplicate msgId")
        if resp.term is not None and resp.term not in self.term_keys:
            problems.append(f"unknown term {resp.term!r}")
        if problems:
            self.rejected.append({"memberId": member_id, "problems": problems})
            return None
        self.seen_msg_ids.add(resp.msg_id)
        return resp

    def _next_plan(self, p: Plan, F: list[Plan], requests, tabu: set[str]) -> tuple[Plan | None, str]:
        if not requests:
            return None, "No member asked for a specific change; nothing to revise."
        allowed: set[str] = set()
        for _, term, _, _ in requests:
            allowed |= PRICE_FLEX if term == PRICE else {term}
        allowed.add("provider")                     # a provider can always be swapped
        p_feasible = any(q.id == p.id for q in F)

        def satisfied(q: Plan) -> int:
            n = 0
            for _, term, pref, kind in requests:
                if kind == "reject_hard":
                    n += q.get(term) != p.get(term)
                elif term == PRICE:
                    n += q.price_per_person < p.price_per_person
                else:
                    n += q.get(term) == pref
            return n

        untried = [q for q in F if q.id not in tabu and q.id != p.id]
        strict = [q for q in untried if changed_terms(p, q) <= allowed or not p_feasible]
        # Prefer plans that change only requested terms; if none exists, allow extra changes
        # (each unrequested change costs 1.5) rather than stalling. Still drawn only from F.
        pool = strict or untried
        if not pool:
            return None, "Stalled: every feasible plan has already been tried."

        def cost(q: Plan) -> float:
            extra = changed_terms(p, q) - allowed
            return (len(changed_terms(p, q) - {"provider"}) + 1.5 * len(extra)
                    + 0.25 * (q.provider_id != p.provider_id))

        scored = [(2 * satisfied(q) - cost(q), -q.price_per_person, q) for q in pool]
        scored = [s for s in scored if satisfied(s[2]) > 0 or not p_feasible]
        if not scored:
            return None, "Stalled: no plan satisfies any outstanding request without breaking a hard constraint."
        scored.sort(key=lambda s: (-s[0], -s[1], s[2].id))
        return scored[0][2], ""

    def _choose_removal(self, result: MediationResult, active: list[str]) -> str | None:
        """Fair removal: someone whose request blocked the best plan; ties go to the newest member."""
        blockers = [m for m in active if m in result.conflicts_by_member]
        if not blockers:
            return None
        organizer = active[0]
        blockers = [m for m in blockers if m != organizer] or blockers
        return blockers[-1]


def _fmt(v: Any) -> str:
    return {True: "yes", False: "no"}.get(v, str(v)) if isinstance(v, bool) else str(v)


def why_lines(p: Plan, q: Plan, requests, names: dict[str, str]) -> list[str]:
    lines = []
    for term in sorted(changed_terms(p, q)):
        if term == "provider":
            lines.append(f"Provider: {names.get(p.provider_id, p.provider_id)} → "
                         f"{names.get(q.provider_id, q.provider_id)}, the one that offers this combination.")
            continue
        who = [names.get(m, m) for m, t, _, _ in requests if t == term]
        by = f" · requested by {len(who)} member{'s' if len(who) != 1 else ''}" if who else ""
        lines.append(f"{term.replace('_', ' ').capitalize()}: {_fmt(p.get(term))} → {_fmt(q.get(term))}{by}")
    if q.price_per_person != p.price_per_person:
        lines.append(f"Price per person: ${p.price_per_person:.0f} → ${q.price_per_person:.0f}")
    return lines
