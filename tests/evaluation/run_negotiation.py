"""Negotiation evaluation (plan 20.2). Usage: make eval  (or python tests/evaluation/run_negotiation.py)

Generates N random groups whose public hard constraints admit at least one plan with known private preferences, runs the real mediator,
and compares against an oracle that sees everyone's preferences (the mediator never does).
Writes tests/evaluation/results/negotiation.json. Every number is measured, not estimated.
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/contracts"), str(ROOT / "services/api"), str(ROOT / "tests/unit")]

from rally.negotiation.engine import enumerate_plans, feasible, utility  # noqa: E402
from test_mediator import OPTIONS, PROVIDERS, run_scenario  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50


def main():
    rows = []
    for seed in range(N):
        n = 2 + seed % 5
        res, rec, prefs, cons = run_scenario(seed, n, require_feasible=True)
        plans = enumerate_plans(OPTIONS, PROVIDERS, n)
        F = feasible(plans, cons)
        prices = [p.price_per_person for p in plans] or [0, 1]
        lo, hi = min(prices), max(prices)

        def ok(p, m):
            u, v = utility(p, prefs[m], lo, hi)
            return v is None and u >= prefs[m]["reservation"]
        unanimous_exists = any(all(ok(p, m) for m in prefs) for p in F)
        violations = sum(1 for p, a in zip(rec.sent, rec.attempts)
                         if a == 1 and any(c.violated_by(p) for c in cons.values()))
        quality = None
        if res.agreed:
            active = res.active
            def total(p):
                vals = [utility(p, prefs[m], lo, hi) for m in active]
                return None if any(v for _, v in vals) else sum(u for u, _ in vals)
            best = max((t for t in (total(p) for p in F) if t is not None), default=None)
            got = total(res.plan)
            quality = round(got / best, 4) if best and got is not None else None
        rows.append({"seed": seed, "members": n, "agreed": res.agreed, "fullGroup": res.agreed and len(res.active) == n,
                     "unanimousPlanExists": unanimous_exists, "rounds": res.rounds_used,
                     "removed": len(res.removed), "violations": violations, "quality": quality})
    feas = [r for r in rows if r["unanimousPlanExists"]]
    summary = {
        "scenarios": N,
        "hardConstraintViolations": sum(r["violations"] for r in rows),
        "agreementRate": round(sum(r["agreed"] for r in rows) / N, 3),
        "fullGroupAgreementWhereUnanimousPlanExists": round(sum(r["fullGroup"] for r in feas) / len(feas), 3) if feas else None,
        "scenariosWithUnanimousPlan": len(feas),
        "meanRounds": round(statistics.mean(r["rounds"] for r in rows), 2),
        "maxRounds": max(r["rounds"] for r in rows),
        "meanPlanQualityVsOracle": round(statistics.mean(q for r in rows if (q := r["quality"]) is not None), 3),
    }
    out = ROOT / "tests/evaluation/results"
    out.mkdir(exist_ok=True)
    (out / "negotiation.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
