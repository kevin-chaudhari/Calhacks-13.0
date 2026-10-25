"""Matching (plan section 14): a hard filter that can only reject, then a ranker that can only reorder.

Semantic similarity never admits a candidate who failed a hard constraint.
Ranker: RANKER=local is a TF-IDF cosine implemented here. RANKER=moss is not
implemented in this PR (Moss SDK not verified); it falls back to local and the
result records ranker="local" so the UI label stays honest.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from rally_contracts import CERT_LEVELS, PublicIntent

from . import catalog

WEIGHTS = {"semantic": 0.45, "date": 0.25, "proximity": 0.15, "pref": 0.15}


def _md(d) -> str:
    """'Nov 7' (strftime %-d is not supported on Windows)."""
    return f"{d:%b} {d.day}"


@dataclass
class Candidate:
    intent: PublicIntent
    eligible: bool
    failed_constraint: str | None = None
    reason: str = ""
    score: float = 0.0
    components: dict | None = None


def haversine_km(a, b) -> float:
    if a is None or b is None or a.lat is None or b.lat is None:
        return 0.0
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _area(label: str) -> str:
    return label.split(",")[0].strip().casefold()


def _same_area(a, b) -> bool:
    """With coordinates on both sides distance decides; without them only the same named place counts
    (before this, a missing coordinate meant 0 km and everyone matched everywhere)."""
    if a is None or b is None:
        return True                                   # no place on one side: the date/budget filters decide
    if a.lat is not None and b.lat is not None:
        return True
    return _area(a.label) == _area(b.label)


def _cert(intent: PublicIntent, key: str = "certification") -> str | None:
    for c in intent.draft.conditions:
        if c.key == key and c.value is not None:
            return str(c.value)
    return None


def _rank(level: str | None) -> int:
    return CERT_LEVELS.index(level) if level in CERT_LEVELS else -1


def overlap_days(a: PublicIntent, b: PublicIntent) -> int:
    da, db = a.draft, b.draft
    if not (da.date_from and da.date_to and db.date_from and db.date_to):
        return 0
    lo, hi = max(da.date_from, db.date_from), min(da.date_to, db.date_to)
    return max(0, (hi - lo).days + 1)


def hard_filter(seeker: PublicIntent, cand: PublicIntent) -> tuple[str | None, str]:
    """Returns (failed_constraint, human sentence) or (None, '')."""
    s, c = seeker.draft, cand.draft
    name = cand.user_id
    if catalog.canonical(s.activity) != catalog.canonical(c.activity):
        return "activity", f"Wants {c.activity.replace('_', ' ')}"
    if overlap_days(seeker, cand) < 1:
        when = f"{_md(c.date_from)}–{_md(c.date_to)}" if c.date_from else "no dates set"
        return "date", f"Only free {when}"
    if not _same_area(s.location, c.location):
        return "distance", f"Somewhere else ({c.location.label if c.location else 'no place set'})"
    dist = haversine_km(s.location, c.location)
    limit = min(s.radius_km or 1e9, c.radius_km or 1e9)
    if dist > limit:
        return "distance", f"{dist:,.0f} km away ({c.location.label if c.location else 'unknown'})"
    act = catalog.info(s.activity) or {}
    floor = act.get("minPlausiblePrice")
    if floor and c.budget_max and c.budget_max.amount < floor:
        return "budget", f"Budget ${c.budget_max.amount:,.0f} is below any available option (from ${floor:,.0f})"
    if floor and s.budget_max and s.budget_max.amount < floor:
        return "budget", "Your budget is below any available option"
    need = act.get("minCertification")
    if need and _rank(_cert(cand)) < _rank(need):
        return "certification", "Not certified yet; guided dives need Open Water"
    for a, b in ((seeker, cand), (cand, seeker)):
        req = _cert(a, "partner_certification")
        if req and _rank(_cert(b)) < _rank(req):
            who = "They require" if a is cand else "You require"
            return "certification", f"{who} partners at {req.replace('_', ' ').title()} or above"
    _ = name
    return None, ""


# ------------------------------------------------------------------ ranking

def _tokens(intent: PublicIntent) -> list[str]:
    d = intent.draft
    text = " ".join([intent.text, d.activity, " ".join(d.tags), d.location.label if d.location else ""])
    return re.findall(r"[a-z]{3,}", text.lower())


class LocalRanker:
    mode = "local"

    def rank(self, seeker: PublicIntent, pool: list[PublicIntent]) -> dict[str, float]:
        docs = [_tokens(seeker)] + [_tokens(p) for p in pool]
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)

        def vec(tokens):
            tf = Counter(tokens)
            return {t: (1 + math.log(f)) * math.log(1 + n / df[t]) for t, f in tf.items()}

        sv = vec(docs[0])
        out = {}
        for p, toks in zip(pool, docs[1:]):
            pv = vec(toks)
            dot = sum(sv.get(t, 0) * w for t, w in pv.items())
            norm = math.sqrt(sum(w * w for w in sv.values())) * math.sqrt(sum(w * w for w in pv.values()))
            out[p.id] = dot / norm if norm else 0.0
        return out


def match(seeker: PublicIntent, board: list[PublicIntent], ranker=None) -> tuple[list[Candidate], str]:
    ranker = ranker or LocalRanker()
    pool = [c for c in board if c.id != seeker.id and c.user_id != seeker.user_id and c.status == "open"
            and c.draft.category == seeker.draft.category
            and catalog.canonical(c.draft.activity) == catalog.canonical(seeker.draft.activity)]
    results: list[Candidate] = []
    survivors: list[PublicIntent] = []
    for c in pool:
        failed, why = hard_filter(seeker, c)
        if failed:
            results.append(Candidate(c, False, failed, why))
        else:
            survivors.append(c)
    sem = ranker.rank(seeker, survivors) if survivors else {}
    s = seeker.draft
    for c in survivors:
        d = c.draft
        span = min((s.date_to - s.date_from).days + 1, (d.date_to - d.date_from).days + 1)
        date_c = overlap_days(seeker, c) / span if span else 0
        limit = min(s.radius_km or 1e9, d.radius_km or 1e9)
        prox = 1 - haversine_km(s.location, d.location) / limit if limit < 1e9 else 1.0
        pref = (min(s.budget_max.amount, d.budget_max.amount) / max(s.budget_max.amount, d.budget_max.amount)
                if s.budget_max and d.budget_max else 0.5)
        comp = {"semantic": round(sem.get(c.id, 0.0), 3), "date": round(date_c, 3),
                "proximity": round(max(0.0, prox), 3), "pref": round(pref, 3)}
        score = sum(WEIGHTS[k] * v for k, v in comp.items())
        lo, hi = max(s.date_from, d.date_from), min(s.date_to, d.date_to)
        reason = f"{_md(lo)}–{_md(hi)} overlap · {haversine_km(s.location, d.location):.0f} km"
        cert = _cert(c)
        if cert:
            reason += f" · {cert.replace('_', ' ').title()}"
        results.append(Candidate(c, True, None, reason, round(score, 4), comp))
    # deterministic order: eligible by score desc, then earlier createdAt, then id
    results.sort(key=lambda r: (not r.eligible, -r.score, r.intent.created_at, r.intent.id))
    return results, getattr(ranker, "mode", "local")


def pick_group(seeker: PublicIntent, ranked: list[Candidate], group_max: int) -> list[Candidate]:
    """Top group_max-1 eligible candidates that share at least one common day with everyone."""
    chosen: list[Candidate] = []
    for cand in [r for r in ranked if r.eligible]:
        trial = chosen + [cand]
        lo = max([seeker.draft.date_from] + [t.intent.draft.date_from for t in trial])
        hi = min([seeker.draft.date_to] + [t.intent.draft.date_to for t in trial])
        if lo <= hi:
            chosen = trial
        if len(chosen) >= group_max - 1:
            break
    return chosen


def common_window(intents: list[PublicIntent]) -> tuple[date, date] | None:
    lo = max(i.draft.date_from for i in intents)
    hi = min(i.draft.date_to for i in intents)
    return (lo, hi) if lo <= hi else None
