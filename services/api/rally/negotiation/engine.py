"""Pure negotiation library: plan space, pricing, member scoring, concession.

No I/O, no LLM. Both the mediator and every personal agent import this.

NOTE: the plan (section 15.7) says to port utility() and all_bundles() from the
Rendezvous prototype. That code was not available when this file was written, so
these are fresh implementations of the same ideas (weighted additive utility,
bundle enumeration, time-based concession). Person A should diff against
rendezvous/negotiation.py and keep whichever is better tested.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date
from typing import Any

VIOLATES = "VIOLATES"


# ---------------------------------------------------------------- plan space

@dataclass(frozen=True)
class Plan:
    terms: tuple[tuple[str, Any], ...]     # sorted (key, value) pairs, hashable
    provider_id: str
    price_per_person: float

    @property
    def t(self) -> dict[str, Any]:
        return dict(self.terms)

    @property
    def id(self) -> str:
        """Canonical id, used for deterministic tie-breaking and the tabu set."""
        return self.provider_id + "|" + "|".join(f"{k}={v}" for k, v in self.terms)

    def get(self, key: str) -> Any:
        if key == "price_per_person":
            return self.price_per_person
        return self.t.get(key)


def _vkey(v: Any) -> str:
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


@dataclass
class ProviderSheet:
    """A provider's deterministic price rules (fixture or vendor-edited, served by its provider agent).

    offers:    for each term, the values this provider can deliver (terms it does not list are unconstrained)
    modifiers: per-person price deltas by term value, e.g. {"dive_type": {"shore": -40}}
    """
    id: str
    name: str
    offers: dict[str, list[Any]]
    available_dates: list[str]
    tiers: list[dict]                      # {min, max, pricePerPerson, includes}
    modifiers: dict[str, dict[str, float]] = field(default_factory=dict)
    provenance: str = "simulated"
    open_groups: dict[str, int] = field(default_factory=dict)   # date -> people already booked on that trip
    pool: bool = False                     # solo mode: price a traveller as joining that date's open group
    format_tiers: dict[str, list[dict]] = field(default_factory=dict)   # web vendors: exact table per format

    def pooled_size(self, terms: dict[str, Any], group_size: int) -> int:
        """Group size the shop prices at: in solo mode, a traveller joining an existing trip counts with it."""
        if not self.pool:
            return group_size
        joined = group_size + self.open_groups.get(str(terms.get("date")), 0)
        top = max((t["max"] for t in self.tiers), default=group_size)
        return min(joined, top)

    def tier_for(self, group_size: int) -> dict | None:
        for tier in self.tiers:
            if tier["min"] <= group_size <= tier["max"]:
                return tier
        return None

    def price(self, terms: dict[str, Any], group_size: int) -> float | None:
        """Per-person price for this plan, or None if the provider cannot serve it."""
        if "date" in terms and terms["date"] not in self.available_dates:
            return None
        for key, value in terms.items():
            if key in self.offers and value not in self.offers[key]:
                return None
        size = self.pooled_size(terms, group_size)
        table = self.format_tiers.get(str(terms.get("format"))) if self.format_tiers else None
        tier = next((t for t in table if t["min"] <= size <= t["max"]), None) if table else self.tier_for(size)
        if tier is None:
            return None
        price = float(tier["pricePerPerson"])
        for key, value in terms.items():
            price += float(self.modifiers.get(key, {}).get(_vkey(value), 0))
        return round(price, 2)


@dataclass
class PublicConstraints:
    """Hard constraints every plan must satisfy. Public by construction."""
    date_from: str | None = None
    date_to: str | None = None
    budget_max: float | None = None
    exclusions: set[tuple[str, Any]] = field(default_factory=set)  # learned from reject_hard

    def violated_by(self, plan: Plan) -> str | None:
        d = plan.get("date")
        if d is not None and self.date_from and d < self.date_from:
            return "date"
        if d is not None and self.date_to and d > self.date_to:
            return "date"
        if self.budget_max is not None and plan.price_per_person > self.budget_max:
            return "price_per_person"
        for key, value in self.exclusions:
            if plan.get(key) == value:
                return key
        return None


def enumerate_plans(options: dict[str, list[Any]], providers: list[ProviderSheet],
                    group_size: int) -> list[Plan]:
    """Every (terms x provider) combination a provider can actually serve."""
    keys = sorted(options)
    plans: list[Plan] = []
    for combo in itertools.product(*(options[k] for k in keys)):
        terms = dict(zip(keys, combo))
        for prov in providers:
            price = prov.price(terms, group_size)
            if price is not None:
                plans.append(Plan(tuple(sorted(terms.items())), prov.id, price))
    plans.sort(key=lambda p: (p.price_per_person, p.id))
    return plans


def feasible(plans: list[Plan], constraints: dict[str, PublicConstraints]) -> list[Plan]:
    """The feasible set F: plans that violate no member's known hard constraint."""
    return [p for p in plans if all(c.violated_by(p) is None for c in constraints.values())]


# ------------------------------------------------------------ member scoring

def _days(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def term_score(key: str, value: Any, prefs: dict, price_lo: float, price_hi: float) -> float | str:
    """s_{m,t}(value) in [0,1], or VIOLATES if outside the member's acceptable range
    or a must-have term that the plan doesn't cover."""
    s = _raw_score(key, value, prefs, price_lo, price_hi)
    if s != VIOLATES and priority(prefs, key) == "must" and float(s) < GOOD:
        return VIOLATES
    return s


def _raw_score(key: str, value: Any, prefs: dict, price_lo: float, price_hi: float) -> float | str:
    ranges: dict = prefs.get("ranges", {})
    best: dict = prefs.get("best", {})
    if key in ranges and value not in ranges[key]:
        return VIOLATES
    if key == "price_per_person":
        worst = prefs.get("price_worst") or price_hi
        if value > worst:
            return VIOLATES
        if worst <= price_lo:
            return 1.0
        return max(0.0, min(1.0, (worst - value) / (worst - price_lo)))
    if key not in best:
        return 0.5                         # no stated preference: neutral
    if key == "date":
        return max(0.0, 1.0 - _days(value, best[key]) / 14.0)
    if isinstance(best[key], bool):
        return 1.0 if value == best[key] else 0.0
    return 1.0 if value == best[key] else 0.35


GOOD = 0.75                                # a term at or above this score counts as covered


def priority(prefs: dict, key: str) -> str:
    """must | high | nice. Price is never ranked: the budget already caps it as a must-have."""
    if key == "price_per_person" or key not in prefs.get("best", {}):
        return "nice"                      # nothing to cover without a stated favourite
    return prefs.get("priorities", {}).get(key, "nice")


def uncovered_high(plan: Plan, prefs: dict, price_lo: float, price_hi: float) -> list[str]:
    """Top-priority terms this plan doesn't cover, most important (highest weight) first."""
    weights = prefs.get("weights", {})
    out = []
    for k in prefs.get("best", {}):
        if priority(prefs, k) == "high":
            s = _raw_score(k, plan.get(k), prefs, price_lo, price_hi)
            if s == VIOLATES or float(s) < GOOD:
                out.append(k)
    return sorted(out, key=lambda k: (-weights.get(k, 0.0), k))


def utility(plan: Plan, prefs: dict, price_lo: float, price_hi: float) -> tuple[float, str | None]:
    """u_m(p) = sum_t w_t * s_t(p_t). Returns (score, violated_term). Hard check first."""
    total = 0.0
    weights: dict[str, float] = prefs["weights"]
    musts = [k for k in prefs.get("best", {}) if priority(prefs, k) == "must"]
    for key in dict.fromkeys([*weights, *prefs.get("ranges", {}), *musts]):
        s = term_score(key, plan.get(key), prefs, price_lo, price_hi)
        if s == VIOLATES:
            return 0.0, key
        total += weights.get(key, 0.0) * float(s)
    return round(total, 6), None


def threshold(u_star: float, reservation: float, round_no: int, rounds: int, patience: float) -> float:
    """tau_m(r) = u* - (u* - rho) * (r/R)^(1/beta): the Rendezvous concession curve."""
    frac = min(1.0, round_no / max(1, rounds))
    return u_star - (u_star - reservation) * frac ** (1.0 / max(0.05, patience))
