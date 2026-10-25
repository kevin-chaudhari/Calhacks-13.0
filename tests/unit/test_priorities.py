"""Priorities: must-haves are never traded, top priorities are covered before the agent accepts
anything, and only nice-to-haves are conceded round by round."""
import asyncio

from rally_contracts import ProposalMsg

from rally.negotiation.engine import Plan, PublicConstraints, enumerate_plans
from rally.negotiation.mediator import Mediator
from rally.negotiation.personal import PersonalAgentBrain
from rally.negotiation.transport import InProcTransport
from tests.unit.test_mediator import DATES, OPTIONS, PROVIDERS, Recorder

BASE = {
    "weights": {"price_per_person": 0.4, "date": 0.3, "site": 0.2, "gear_included": 0.1},
    "best": {"date": "2026-11-14", "site": "Lovers Point", "gear_included": True},
    "price_worst": 300, "reservation": 0.35, "patience": 1.0,
}
IDEAL = dict(date="2026-11-14", site="Lovers Point", gear_included=True)
CHEAP_WRONG_SITE = dict(date="2026-11-14", site="Point Lobos", gear_included=True)
CHEAP_NO_GEAR = dict(date="2026-11-14", site="Lovers Point", gear_included=False)


def plan(price: float, **terms) -> Plan:
    return Plan(tuple(sorted(terms.items())), "p_test", price)


def brain(**priorities) -> PersonalAgentBrain:
    b = PersonalAgentBrain("u_test", {**BASE, "priorities": priorities}, rounds=5)
    b.set_plan_space([plan(100, **CHEAP_WRONG_SITE), plan(100, **CHEAP_NO_GEAR), plan(240, **IDEAL)])
    return b


def ask(b: PersonalAgentBrain, p: Plan, round_no: int):
    return b.respond(ProposalMsg(msg_id="m", deal_id="d", proposal_version=round_no, round=round_no,
                                 terms=p.t, provider_id=p.provider_id, price_per_person=p.price_per_person,
                                 respond_by=0))


def test_without_priorities_the_agent_settles_for_a_cheaper_plan_by_the_last_round():
    r = ask(brain(), plan(100, **CHEAP_WRONG_SITE), 5)
    assert r.kind == "accept"                       # the old behaviour, still the default


def test_top_priority_is_never_conceded_even_in_the_last_round():
    b = brain(site="high")
    for rnd in range(1, 6):
        r = ask(b, plan(100, **CHEAP_WRONG_SITE), rnd)
        assert (r.kind, r.term, r.preferred) == ("change_request", "site", "Lovers Point")
    assert ask(b, plan(240, **IDEAL), 5).kind == "accept"


def test_must_have_is_a_hard_limit_however_cheap():
    r = ask(brain(gear_included="must"), plan(100, **CHEAP_NO_GEAR), 5)
    assert (r.kind, r.term) == ("reject_hard", "gear_included")


def test_a_near_date_still_covers_a_top_priority_date():
    b = brain(date="high")
    assert ask(b, plan(100, **{**IDEAL, "date": "2026-11-15"}), 5).kind == "accept"      # 1 day off
    assert ask(b, plan(100, **{**IDEAL, "date": "2026-11-22"}), 5).term == "date"        # 8 days off


def test_ranking_needs_a_favourite():
    b = PersonalAgentBrain("u", {**BASE, "best": {}, "priorities": {"site": "must"}})
    b.set_plan_space([plan(100, **CHEAP_WRONG_SITE)])
    assert ask(b, plan(100, **CHEAP_WRONG_SITE), 5).kind == "accept"   # nothing to hold out for


def _group(prefs: dict[str, dict], providers=PROVIDERS):
    members = list(prefs)
    plans = enumerate_plans(OPTIONS, providers, len(members))
    brains = {m: PersonalAgentBrain(m, p, 5) for m, p in prefs.items()}
    cons = {m: PublicConstraints(DATES[0], DATES[-1], None) for m in members}
    med = Mediator("d", plans, cons, InProcTransport(brains), Recorder(), rounds=5, restarts=0, group_min=2)
    return asyncio.run(med.run(members))


def _diver(**extra) -> dict:
    return {"weights": {"price_per_person": 0.7, "dive_type": 0.1, "site": 0.1, "date": 0.1},
            "best": {"dive_type": "shore", "site": "A", "date": "2026-11-14"}, "price_worst": 400,
            "reservation": 0.2, "patience": 1.0, **extra}


def test_group_plan_covers_a_members_top_priority_over_a_cheaper_plan():
    boat = _diver(best={"dive_type": "boat", "site": "A", "date": "2026-11-14"}, priorities={"dive_type": "high"})
    res = _group({"m0": _diver(), "m1": boat})
    assert res.agreed and res.plan.get("dive_type") == "boat"
    assert any(p.get("dive_type") == "shore" and p.price_per_person < res.plan.price_per_person
               for p in enumerate_plans(OPTIONS, PROVIDERS, 2))     # a cheaper plan existed and was refused


def test_no_vendor_covers_a_must_have_so_there_is_no_deal():
    gear_only = [s for s in PROVIDERS if s.id == "p2"]                  # p2 always includes gear
    picky = _diver(best={"gear_included": False}, priorities={"gear_included": "must"})
    res = _group({"m0": _diver(), "m1": picky}, providers=gear_only)
    assert not res.agreed
