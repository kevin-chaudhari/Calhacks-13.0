"""State store. FastAPI is the only writer (plan section 7).

Interim design for this PR, stated plainly:
  * MemoryStore holds the authoritative working copy inside the single FastAPI
    process; every write for a deal happens under that deal's asyncio lock, and
    status changes go through a compare-and-set transition() that appends the
    event in the same step, so state and events never diverge.
  * When STORE=convex, every change is also written through to Convex
    (ConvexMirror) as per-table rows plus a denormalised DealSnapshot document,
    which the browser subscribes to. The snapshot is built by the same code that
    serves GET /v1/deals/{id}/snapshot, so both read paths have one shape.
  * Not yet done: rebuilding the in-memory copy from Convex after a restart
    (plan 7.4 "resume from last round"). Until then, a restart needs make reset.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from rally_contracts import (TRANSITIONS, Approval, Commitment, Deal, DealEvent, DealStatus, Member,
                             Proposal, PublicIntent, Quote, Round)

log = logging.getLogger("rally.store")


def now_ms() -> int:
    return int(time.time() * 1000)


class TransitionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class MemoryStore:
    mode = "memory"

    def __init__(self, mirror: "ConvexMirror | None" = None):
        self.mirror = mirror
        self.reset()

    def reset(self) -> None:
        self.goals: dict[str, dict] = {}
        self.intents: dict[str, PublicIntent] = {}
        self.matches: dict[str, dict] = {}
        self.deals: dict[str, Deal] = {}
        self.members: dict[str, list[Member]] = defaultdict(list)
        self.proposals: dict[str, list[Proposal]] = defaultdict(list)
        self.rounds: dict[str, list[Round]] = defaultdict(list)
        self.quotes: dict[str, list[Quote]] = defaultdict(list)
        self.approvals: dict[str, list[Approval]] = defaultdict(list)
        self.commitments: dict[str, list[Commitment]] = defaultdict(list)
        self.events: dict[str, list[DealEvent]] = defaultdict(list)
        self.agent_messages: dict[str, list] = defaultdict(list)   # deal id -> AgentMessage[]
        self.chat: dict[str, list] = defaultdict(list)             # deal id -> ChatMessage[]
        self.idempotency: dict[str, Any] = {}
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        if self.mirror:
            self.mirror.reset()

    # ------------------------------------------------------------ events

    def append_event(self, deal_id: str, type_: str, actor: str, summary: str,
                     payload: dict | None = None) -> DealEvent:
        seq = len(self.events[deal_id]) + 1
        ev = DealEvent(seq=seq, type=type_, actor=actor, summary=summary,
                       payload=payload or {}, at=now_ms())
        self.events[deal_id].append(ev)
        return ev

    def transition(self, deal_id: str, expected: DealStatus | set[DealStatus], new: DealStatus,
                   actor: str, summary: str, payload: dict | None = None) -> Deal:
        """Compare-and-set on deal status; appends the event in the same step."""
        deal = self.deals.get(deal_id)
        if deal is None:
            raise TransitionError("NOT_FOUND", "Deal not found.")
        current = DealStatus(deal.status)
        allowed_from = expected if isinstance(expected, set) else {expected}
        if current not in allowed_from:
            raise TransitionError("WRONG_STATE",
                                  f"Deal is {current.value}, expected {', '.join(s.value for s in allowed_from)}.")
        if new not in TRANSITIONS[current]:
            raise TransitionError("ILLEGAL_TRANSITION", f"{current.value} → {new.value} is not allowed.")
        deal.status = new
        deal.status_version += 1
        self.append_event(deal_id, f"deal.{new.value.lower()}", actor, summary,
                          {"from": current.value, "to": new.value, **(payload or {})})
        return deal

    # ------------------------------------------------------------ mirror

    def publish(self, deal_id: str, snapshot: dict) -> None:
        if self.mirror:
            self.mirror.put_snapshot(deal_id, snapshot)

    def publish_row(self, table: str, row_id: str, row: dict) -> None:
        if self.mirror:
            self.mirror.put_row(table, row_id, row)


class ConvexMirror:
    """Write-through to Convex using server-key guarded mutations in convex/rally.ts.

    Uses the official `convex` Python client. Failures are logged and surfaced in
    /v1/health; they never block a state transition (plan 10, component 15).
    """

    def __init__(self, url: str, server_key: str):
        from convex import ConvexClient  # imported lazily: optional dependency
        self.client = ConvexClient(url)
        self.server_key = server_key
        self.errors = 0
        self.last_error: str | None = None

    def _call(self, name: str, args: dict) -> None:
        try:
            self.client.mutation(name, {"serverKey": self.server_key, **args})
        except Exception as exc:  # noqa: BLE001 - surfaced via health, never fatal
            self.errors += 1
            self.last_error = str(exc)[:300]
            log.warning("convex write %s failed: %s", name, exc)

    def reset(self) -> None:
        self._call("rally:resetAll", {})

    def put_snapshot(self, deal_id: str, snapshot: dict) -> None:
        self._call("rally:putSnapshot", {"dealId": deal_id, "snapshot": snapshot})

    def put_row(self, table: str, row_id: str, row: dict) -> None:
        self._call("rally:putRow", {"table": table, "rid": row_id, "doc": row})
