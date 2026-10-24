"""Safety properties of the group mediator (plan 15.8)."""
import asyncio
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from rally.negotiation.engine import (Plan, ProviderSheet, PublicConstraints, enumerate_plans, feasible,
                                      utility)
from rally.negotiation.mediator import Mediator
from rally.negotiation.personal import PersonalAgentBrain
from rally.negotiation.transport import InProcTransport

SEED_FEASIBLE = 0
DATES = ["2026-11-07", "2026-11-08", "2026-11-14", "2026-11-15", "2026-11-21", "2026-11-22"]
SITES = ["A", "B", "C"]
OPTIONS = {"date": DATES, "site": SITES, "dive_type": ["shore", "boat"], "gear_included": [True, False]}
PROVIDERS = [
    ProviderSheet("p1", "P1", {"site": ["A", "B"], "dive_type": ["shore", "boat"]}, DATES,
                  [{"min": 1, "max": 3, "pricePerPerson": 180}, {"min": 4, "max": 8, "pricePerPerson": 150}],
                  modifiers={"dive_type": {"shore": -40}, "gear_included": {"true": 45}}),
    ProviderSheet("p2", "P2", {"site": ["B", "C"], "dive_type": ["boat"], "gear_included": [True]}, DATES[1:],
                  [{"min": 1, "max": 3, "pricePerPerson": 210, "includes": ["gear"]},
                   {"min": 4, "max": 8, "pricePerPerson": 175, "includes": ["gear"]}]),
]


class Recorder:
    def __init__(self):
        self.sent: list[Plan] = []
        self.attempts: list[int] = []
        self.rounds = 0

    async def proposal(self, plan, version, round_no, attempt, rationale, changed):
        self.sent.append(plan)
        self.attempts.append(attempt)

    async def responses(self, *a):
        self.rounds += 1

    async def note(self, *a):
        pass

    async def member_state(self, *a):
        pass


def random_member(rng: random.Random) -> tuple[dict, PublicConstraints]:
    keys = ["date", "site", "dive_type", "gear_included", "price_per_person"]
    w = [rng.random() + 0.01 for _ in keys]
    prefs = {"weights": {k: x / sum(w) for k, x in zip(keys, w)},
             "best": {"date": rng.choice(DATES), "site": rng.choice(SITES),
                      "dive_type": rng.choice(["shore", "boat"]), "gear_included": rng.random() < 0.5},
             "price_worst": rng.choice([160, 200, 260]), "reservation": rng.uniform(0.1, 0.6),
             "patience": rng.uniform(0.5, 2.0)}
    if rng.random() < 0.3:
        prefs["ranges"] = {"dive_type": [rng.choice(["shore", "boat"])]}      # private hard limit
    if rng.random() < 0.3:
        prefs.setdefault("ranges", {})["site"] = rng.sample(SITES, 2)
    lo = rng.randrange(0, 4)
    hi = rng.randrange(lo, 6)
    cons = PublicConstraints(DATES[lo], DATES[hi], rng.choice([None, 170, 220, 300]))
    return prefs, cons


def run_scenario(seed: int, n: int, offline: int = 0, require_feasible: bool = False):
    rng = random.Random(seed)
    members = [f"m{i}" for i in range(n)]
    plans = enumerate_plans(OPTIONS, PROVIDERS, n)
    for _ in range(200):                       # optionally resample until F is non-empty
        prefs, cons = {}, {}
        for m in members:
            prefs[m], cons[m] = random_member(rng)
        if not require_feasible or feasible(plans, cons):
            break
    brains = {m: PersonalAgentBrain(m, prefs[m], 5) for m in members}
    rec = Recorder()
    transport = InProcTransport(brains, offline=set(members[:offline]))
    med = Mediator("d", plans, {m: PublicConstraints(c.date_from, c.date_to, c.budget_max) for m, c in cons.items()},
                   transport, rec, rounds=5, restarts=1, group_min=2,
                   replan=lambda ids: enumerate_plans(OPTIONS, PROVIDERS, len(ids)))
    res = asyncio.run(med.run(members))
    return res, rec, prefs, cons


@settings(max_examples=150, deadline=None)
@given(seed=st.integers(0, 10_000), n=st.integers(2, 6))
def test_never_sends_a_plan_violating_public_hard_constraints(seed, n):
    res, rec, prefs, cons = run_scenario(seed, n)
    for plan, attempt in zip(rec.sent, rec.attempts):
        if attempt == 1:                      # before any removal, every member's constraints apply
            assert all(c.violated_by(plan) is None for c in cons.values())
    if res.agreed:
        for m in res.active:
            assert cons[m].violated_by(res.plan) is None
            _, violated = utility(res.plan, prefs[m], 0, 1000)
            assert violated is None or violated == "price_per_person" and res.plan.price_per_person <= (cons[m].budget_max or 1e9)


@settings(max_examples=150, deadline=None)
@given(seed=st.integers(0, 10_000), n=st.integers(2, 6))
def test_terminates_within_round_budget(seed, n):
    res, rec, *_ = run_scenario(seed, n)
    assert res.rounds_used <= 5 * (1 + 1)
    assert len(rec.sent) == res.rounds_used


@settings(max_examples=100, deadline=None)
@given(seed=st.integers(0, 10_000), n=st.integers(2, 6))
def test_agreement_means_every_active_member_accepted_final_version(seed, n):
    res, rec, prefs, cons = run_scenario(seed, n)
    if res.agreed:
        assert rec.sent[-1] == res.plan
        assert len(res.active) >= 2


def test_infeasible_group_returns_no_agreement_naming_conflict():
    plans = enumerate_plans(OPTIONS, PROVIDERS, 2)
    cons = {"weekend_a": PublicConstraints("2026-11-07", "2026-11-08"),
            "weekend_b": PublicConstraints("2026-11-21", "2026-11-22")}
    brains = {m: PersonalAgentBrain(m, {"weights": {"date": 1.0}}, 5) for m in cons}
    med = Mediator("d", plans, cons, InProcTransport(brains), Recorder(), group_min=2)
    res = asyncio.run(med.run(list(cons)))
    assert not res.agreed and res.plan is None
    assert "No plan satisfies" in res.conflicts[0]


def test_offline_member_is_dropped_from_the_active_set():
    res, rec, *_ = run_scenario(seed=SEED_FEASIBLE, n=4, offline=1)
    assert res.rounds_used >= 1
    assert "m0" not in res.active


def test_stale_spoofed_and_unknown_term_messages_are_ignored():
    from rally_contracts import ResponseMsg
    plans = enumerate_plans(OPTIONS, PROVIDERS, 2)
    med = Mediator("d", plans, {}, None, Recorder(), term_keys=set(OPTIONS))
    med.version = 3
    good = dict(msg_id="x", deal_id="d", proposal_version=3, member_id="a", kind="accept")
    assert med._validate(ResponseMsg(**good), "a") is not None
    assert med._validate(ResponseMsg(**good), "a") is None                         # duplicate msgId
    assert med._validate(ResponseMsg(**{**good, "msg_id": "y", "proposal_version": 2}), "a") is None
    assert med._validate(ResponseMsg(**{**good, "msg_id": "z", "member_id": "b"}), "a") is None
    assert med._validate(ResponseMsg(**{**good, "msg_id": "w", "kind": "change_request",
                                        "term": "budget_hack"}), "a") is None
    assert len(med.rejected) == 4
