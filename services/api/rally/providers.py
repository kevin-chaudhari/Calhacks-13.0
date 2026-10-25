"""Provider price sheets and quotes (plan section 16).

PROVIDERS=seeded: deterministic tier tables from data/fixtures/providers.json,
always labelled provenance="simulated". Apify "listed price" records (P2) would
enter as provenance="cached" and are never selectable as the binding quote.
"""

from __future__ import annotations

import json
import uuid

from rally_contracts import Quote

from .core import FIXTURES
from .negotiation.engine import Plan, ProviderSheet
from .store import now_ms

QUOTE_TTL_MS = 30 * 60 * 1000


def load_providers() -> list[dict]:
    return json.loads((FIXTURES / "providers.json").read_text(encoding="utf-8"))["providers"]


def sheets(providers: list[dict], pool: bool = False) -> list[ProviderSheet]:
    return [ProviderSheet(id=p["id"], name=p["name"], offers=p["offers"], available_dates=p["availableDates"],
                          tiers=p["tiers"], modifiers=p.get("modifiers", {}),
                          provenance=p.get("provenance", "simulated"), open_groups=p.get("openGroups", {}),
                          pool=pool) for p in providers]


def open_group_seats(provider: dict, plan_terms: dict) -> int:
    return int(provider.get("openGroups", {}).get(str(plan_terms.get("date")), 0))


def quote_for(provider: dict, plan_terms: dict, group_size: int, version: int, binding: bool,
              pool: bool = False) -> Quote:
    sheet = sheets([provider], pool)[0]
    price = sheet.price(plan_terms, group_size)
    solo = sheets([provider])[0].price(plan_terms, 1)     # baseline: booking alone, never pooled
    tier = sheet.tier_for(sheet.pooled_size(plan_terms, group_size)) or {}
    includes = list(tier.get("includes", []))
    joined = open_group_seats(provider, plan_terms) if pool else 0
    if joined and price is not None:
        includes.append(f"joins a booked group of {joined} (group rate)")
    for key, value in plan_terms.items():           # paid add-ons the group chose
        if value is True and provider.get("modifiers", {}).get(key, {}).get("true", 0) > 0:
            includes.append(key.replace("_included", "").replace("_", " ") + " (add-on)")
    available = price is not None
    t = now_ms()
    return Quote(
        id=f"q_{uuid.uuid4().hex[:8]}", provider_id=provider["id"], provider_name=provider["name"],
        proposal_version=version, group_size=group_size,
        price_per_person=price or 0.0, solo_price_per_person=solo or 0.0,
        total=round((price or 0.0) * group_size, 2), currency="USD", includes=includes,
        available=available, binding=binding and available, provenance=provider.get("provenance", "simulated"),
        expires_at=t + QUOTE_TTL_MS, tiers=provider["tiers"], source_url=provider.get("url"),
        last_verified_at=t,
    )


def baseline_valid(q: Quote) -> bool:
    """Savings are shown only against the same provider's single-person price for the same plan."""
    return q.available and q.solo_price_per_person > 0 and q.solo_price_per_person >= q.price_per_person


def rank_quotes(quotes: list[Quote], wanted: set[str]) -> list[Quote]:
    """Tie-break: lower price, more wanted inclusions, fresher, provider id (plan 16.3)."""
    return sorted(quotes, key=lambda q: (not q.available, q.price_per_person,
                                         -len(wanted & set(q.includes)), -q.last_verified_at, q.provider_id))


def plan_terms(plan: Plan) -> dict:
    return plan.t
