"""Convex as the system of record: background mirror, access lists, restart recovery.

FakeConvex mirrors convex/rally.ts (tested itself with convex-test in convex/rally.test.ts) and the
Python client's encoding: every int arrives as a float, as the real `convex` package sends it.
"""
import asyncio
import json

import pytest

from rally.core import Settings
from rally.service import Rally
from rally.store import ConvexMirror, MemoryStore

KEY = "server-key"
GOAL = "I want to go scuba diving in Monterey next month for under $300. I am Open Water certified."


def floats(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return float(v)
    if isinstance(v, dict):
        return {k: floats(x) for k, x in v.items()}
    if isinstance(v, list):
        return [floats(x) for x in v]
    return v


class FakeConvex:
    def __init__(self):
        self.snapshots: dict[str, dict] = {}
        self.rows: dict[tuple[str, str], dict] = {}
        self.calls = 0
        self.fail_next = 0

    def mutation(self, name, args):
        self.calls += 1
        if self.fail_next:
            self.fail_next -= 1
            raise RuntimeError("network blip")
        assert args.pop("serverKey") == KEY
        args = floats(json.loads(json.dumps(args)))
        if name == "rally:putMany":
            for s in args["snapshots"]:
                self.snapshots[s["dealId"]] = s
            for r in args["rows"]:
                self.rows[(r["table"], r["rid"])] = r
        elif name == "rally:resetAll":
            self.snapshots.clear()
            self.rows.clear()
        else:
            raise AssertionError(name)

    def query(self, name, args):
        assert name == "rally:dumpAll" and args["serverKey"] == KEY
        return {"snapshots": list(self.snapshots.values()), "rows": list(self.rows.values())}


def boot(fake, tmp_path, monkeypatch):
    monkeypatch.setenv("STORE", "convex")
    monkeypatch.setenv("DEMO_ROUND_DELAY_MS", "30")
    monkeypatch.setenv("RALLY_RUNTIME_DIR", str(tmp_path))
    mirror = ConvexMirror("http://fake", KEY, client=fake, flush_interval_s=0.001)
    rally = Rally(Settings(), MemoryStore(mirror))
    assert rally.vault.path == tmp_path / "agent_prefs.json"
    return rally, mirror


async def until(pred, timeout=8.0):
    end = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < end:
        if pred():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out")


def test_mirror_coalesces_and_retries():
    fake = FakeConvex()
    m = ConvexMirror("http://fake", KEY, client=fake, flush_interval_s=0.02)
    fake.fail_next = 1
    for v in range(20):
        m.put_snapshot("d1", {"v": v}, ["u_kevin"])
    m.put_row("goals", "g1", {"text": "x"}, ["u_kevin"])
    assert m.flush(10)
    assert fake.snapshots["d1"]["snapshot"] == {"v": 19.0}        # latest value wins, ints arrive as floats
    assert fake.rows[("goals", "g1")]["access"] == ["u_kevin"]
    assert m.errors == 1 and fake.calls <= 4                      # one blip, retried; 20 snapshots not 20 writes
    m.close()


def test_restart_mid_negotiation_resumes_and_keeps_history(tmp_path, monkeypatch):
    fake = FakeConvex()

    async def first_life():
        rally, mirror = boot(fake, tmp_path, monkeypatch)
        rally.resume()
        g = rally.compile_goal("u_kevin", GOAL)
        g = rally.patch_goal("u_kevin", g["id"], {"groupMax": 5})
        intent = rally.publish_intent("u_kevin", g["id"], g["suggestedPrefs"])
        m = rally.run_matches("u_kevin", intent["id"])
        deal = await rally.create_deal("u_kevin", intent["id"], m["selectedIntentIds"])
        await until(lambda: all(x.state == "joined" for x in rally.store.members[deal["id"]]))
        await rally.negotiate("u_kevin", deal["id"])
        await until(lambda: len(rally.store.rounds[deal["id"]]) >= 2)       # crash during round 2
        for t in rally.tasks.values():
            t.cancel()
        assert mirror.flush(10)
        mirror.close()
        return deal["id"], intent["id"], g["id"], len(rally.store.events[deal["id"]])

    deal_id, intent_id, goal_id, events_before = asyncio.run(first_life())
    stored = json.dumps(list(fake.snapshots.values()) + list(fake.rows.values()))
    for secret in ("weights", "reservation", "priceWorst", "patience"):
        assert secret not in stored                                  # private prefs never reach Convex

    async def second_life():
        rally, mirror = boot(fake, tmp_path, monkeypatch)
        assert rally.restored["deals"] == 1 and rally.restored["goals"] >= 1
        assert len(rally.store.events[deal_id]) == events_before    # history survived
        assert intent_id in rally.agent_prefs                       # Kevin's agent remembers him
        assert rally.resume() == [deal_id]
        await until(lambda: rally.store.deals[deal_id].vendor_review is not None
                    or rally.store.deals[deal_id].status in ("AWAITING_APPROVAL", "NO_AGREEMENT"))
        d = rally.store.deals[deal_id]
        seqs = [e.seq for e in rally.store.events[deal_id]]
        assert seqs == list(range(1, len(seqs) + 1))
        assert any(e.type == "deal.resumed" for e in rally.store.events[deal_id])
        versions = [p.version for p in rally.store.proposals[deal_id]]
        assert versions == sorted(set(versions))                    # numbering continued, no duplicates
        assert rally.get_goal("u_kevin", goal_id)["status"] == "published"
        mirror.flush(10)
        snap = fake.snapshots[deal_id]
        assert "u_kevin" in snap["access"] and "u_luis" not in snap["access"]
        if d.vendor_review:                                         # quoting vendor's staff can read it
            assert "v_marcus" in snap["access"]
            assert ("vendor", f"p_ottercove:{deal_id}") in fake.rows
            assert fake.rows[("vendor", f"p_ottercove:{deal_id}")]["access"] == ["v_marcus"]
        assert fake.rows[("goals", goal_id)]["access"] == ["u_kevin"]
        for t in rally.tasks.values():
            t.cancel()
        mirror.close()

    asyncio.run(second_life())


def test_reset_wipes_convex_then_reseeds(tmp_path, monkeypatch):
    fake = FakeConvex()
    rally, mirror = boot(fake, tmp_path, monkeypatch)
    mirror.flush(10)
    assert rally.restored is None and ("intents", "i_ana") in fake.rows
    assert fake.rows[("vendor", "p_ottercove:dashboard")]["access"] == ["v_marcus"]   # vendor screens never start empty
    fake.rows[("goals", "g_stale")] = {"table": "goals", "rid": "g_stale", "doc": {}, "access": []}
    rally.seed()
    mirror.flush(10)
    assert ("goals", "g_stale") not in fake.rows and ("intents", "i_ana") in fake.rows
    mirror.close()


@pytest.mark.parametrize("bad", [None, {"snapshots": [], "rows": []}])
def test_empty_or_unreachable_convex_falls_back_to_seed(tmp_path, monkeypatch, bad):
    fake = FakeConvex()
    fake.query = lambda name, args: (_ for _ in ()).throw(RuntimeError("down")) if bad is None else bad
    rally, mirror = boot(fake, tmp_path, monkeypatch)
    assert rally.restored is None and "i_ana" in rally.store.intents
    mirror.close()
