import json

from rally.negotiation.engine import Plan
from rally.negotiation.personal import PersonalAgentBrain

PREFS = {
    "weights": {"price_per_person": 0.4, "date": 0.3, "site": 0.2, "gear_included": 0.1},
    "best": {"date": "2026-11-14", "site": "Lovers Point", "gear_included": True},
    "price_worst": 300,
}


def plan(price: float, **terms) -> Plan:
    return Plan(tuple(sorted(terms.items())), "p_test", price)


def brain() -> PersonalAgentBrain:
    b = PersonalAgentBrain("u_test", PREFS)
    b.set_plan_space([plan(100, date="2026-11-14", site="Lovers Point", gear_included=True),
                      plan(250, date="2026-11-22", site="Point Lobos", gear_included=False)])
    return b


def test_explain_buckets_each_term_by_fit():
    p = plan(180, date="2026-11-15", site="Point Lobos", gear_included=True)
    out = brain().explain(p)
    # price (300-180)/(300-100) = 0.6 -> ok; date 1 day off -> 0.93 good; other site -> 0.35 compromise
    assert out == [
        {"term": "price_per_person", "value": 180, "fit": "ok"},
        {"term": "date", "value": "2026-11-15", "fit": "good"},
        {"term": "site", "value": "Point Lobos", "fit": "compromise"},
        {"term": "gear_included", "value": True, "fit": "good"},
    ]


def test_explain_never_reveals_weights_or_scores():
    text = json.dumps(brain().explain(plan(180, date="2026-11-15", site="Point Lobos", gear_included=True)))
    assert "0.4" not in text and "weight" not in text and "score" not in text
