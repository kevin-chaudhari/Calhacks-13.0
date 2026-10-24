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
  * On boot with STORE=convex, Rally.restore() rebuilds this working copy from Convex
    (rally:dumpAll) and Rally.resume() restarts mediators, invites and quote requests that
    were in flight, so Convex is the system of record (plan 7.4).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from collections import defaultdict
from pathlib import Path
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
        self.reset(remote=False)          # never wipe Convex on boot: Rally.restore() decides

    def reset(self, remote: bool = True) -> None:
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
        if self.mirror and remote:
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

    def publish(self, deal_id: str, snapshot: dict, access: list[str] | None = None) -> None:
        if self.mirror:
            self.mirror.put_snapshot(deal_id, snapshot, access)

    def publish_row(self, table: str, row_id: str, row: dict, access: list[str] | None = None) -> None:
        """access: user ids allowed to read it in Convex; [] = any signed-in persona."""
        if self.mirror:
            self.mirror.put_row(table, row_id, row, access)


class ConvexMirror:
    """Write-through to Convex (convex/rally.ts) from a background thread.

    * Writes never block a state transition: put_* records the latest value and returns.
    * Coalescing: ten rounds of snapshots for one deal become one write if they arrive within a flush.
    * Batching: one `rally:putMany` mutation per flush (one Convex transaction).
    * A failed flush is retried with backoff and counted in /v1/health; newer values are never overwritten
      by an older retry.
    * load() returns everything for restart recovery (`rally:dumpAll`).
    """

    MAX_BATCH = 24

    def __init__(self, url: str, server_key: str, client=None, flush_interval_s: float = 0.05):
        if client is None:
            from convex import ConvexClient  # imported lazily: optional dependency
            client = ConvexClient(url)
        self.client = client
        self.server_key = server_key
        self.flush_interval_s = flush_interval_s
        self.errors = 0
        self.writes = 0
        self.last_error: str | None = None
        self.last_flush_ms: float | None = None
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._idle = threading.Event()
        self._idle.set()
        self._snapshots: dict[str, tuple[dict, list[str]]] = {}
        self._rows: dict[tuple[str, str], tuple[dict, list[str]]] = {}
        self._stop = False
        self._thread = threading.Thread(target=self._run, name="convex-mirror", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------ producer side

    def put_snapshot(self, deal_id: str, snapshot: dict, access: list[str] | None = None) -> None:
        with self._lock:
            self._snapshots[deal_id] = (snapshot, access or [])
            self._idle.clear()
        self._wake.set()

    def put_row(self, table: str, row_id: str, row: dict, access: list[str] | None = None) -> None:
        with self._lock:
            self._rows[(table, row_id)] = (row, access or [])
            self._idle.clear()
        self._wake.set()

    def reset(self) -> None:
        """Synchronous: drop anything queued, then empty Convex."""
        with self._lock:
            self._snapshots.clear()
            self._rows.clear()
        self.flush()
        self._mutate("rally:resetAll", {})

    def load(self) -> dict | None:
        try:
            return self.client.query("rally:dumpAll", {"serverKey": self.server_key})
        except Exception as exc:  # noqa: BLE001
            self.errors += 1
            self.last_error = f"load: {str(exc)[:280]}"
            log.warning("convex load failed: %s", exc)
            return None

    def flush(self, timeout_s: float = 10.0) -> bool:
        """Block until everything queued so far is written (tests, shutdown, reset)."""
        self._wake.set()
        return self._idle.wait(timeout_s)

    def pending(self) -> int:
        with self._lock:
            return len(self._snapshots) + len(self._rows)

    def close(self) -> None:
        self.flush(5)
        self._stop = True
        self._wake.set()

    # ------------------------------------------------------------ writer thread

    def _mutate(self, name: str, args: dict) -> bool:
        try:
            self.client.mutation(name, {"serverKey": self.server_key, **args})
            self.writes += 1
            return True
        except Exception as exc:  # noqa: BLE001 - surfaced via health, never fatal
            self.errors += 1
            self.last_error = f"{name}: {str(exc)[:280]}"
            log.warning("convex write %s failed: %s", name, exc)
            return False

    def _run(self) -> None:
        backoff = 0.0
        while not self._stop:
            self._wake.wait(timeout=1.0)
            self._wake.clear()
            if backoff:
                time.sleep(backoff)
            time.sleep(self.flush_interval_s)          # let a burst of publishes coalesce
            with self._lock:
                snaps = list(self._snapshots.items())[: self.MAX_BATCH]
                rows = list(self._rows.items())[: self.MAX_BATCH]
                for k, _ in snaps:
                    self._snapshots.pop(k)
                for k, _ in rows:
                    self._rows.pop(k)
            if not snaps and not rows:
                self._idle.set()
                continue
            t0 = time.perf_counter()
            ok = self._mutate("rally:putMany", {
                "snapshots": [{"dealId": k, "snapshot": v, "access": a} for k, (v, a) in snaps],
                "rows": [{"table": t, "rid": r, "doc": v, "access": a} for (t, r), (v, a) in rows],
            })
            self.last_flush_ms = round((time.perf_counter() - t0) * 1000, 1)
            with self._lock:
                if not ok:                               # requeue unless a newer value arrived meanwhile
                    for k, v in snaps:
                        self._snapshots.setdefault(k, v)
                    for k, v in rows:
                        self._rows.setdefault(k, v)
                more = bool(self._snapshots or self._rows)
            backoff = 0.0 if ok else min(5.0, (backoff or 0.25) * 2)
            if more:
                self._wake.set()
            else:
                self._idle.set()

    def stats(self) -> dict:
        return {"enabled": True, "writes": self.writes, "errors": self.errors, "lastError": self.last_error,
                "lastFlushMs": self.last_flush_ms, "pending": self.pending()}


class AgentPrefsVault:
    """The personal agents' own storage, so a restart doesn't make an agent forget its owner.

    Lives on the API host only (data/runtime/, git-ignored, mode 0600). Never sent to Convex,
    the mediator, vendors or the browser. With Parikshit's TRANSPORT=agentverse this moves into
    each agent's process, as plan section 7.1 intends.
    """

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save(self, prefs: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(prefs), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
