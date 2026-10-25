"""Social layer: a feed of open plans, trips and posts for every activity; profiles; follows; likes;
comments; and "I'm in too" (join someone's plan in one tap). Owner: platform (Kevin).

What's public here is exactly what was already public: a published intent (activity, place, dates,
budget cap, group size) and a trip's public summary. Private preferences never appear; trip cards
show first names of people who went, plan, vendor and price per person.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from rally_contracts import Persona

from . import catalog
from . import compiler as compiler_mod
from .core import FIXTURES, ApiError, sign_persona
from .store import now_ms

if TYPE_CHECKING:
    from .service import Rally

HOUR = 3_600_000


class Social:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.profiles: dict[str, dict] = {}          # user -> {bio, interests}
        self.posts: dict[str, dict] = {}
        self.likes: dict[str, set[str]] = {}         # item id -> users
        self.base_likes: dict[str, int] = {}         # seeded counts for demo posts
        self.comments: dict[str, list[dict]] = {}
        self.follows: dict[str, set[str]] = {}       # user -> who they follow


# ------------------------------------------------------------------ seeding

def load_people(app: "Rally") -> dict:
    """Community people and profiles; on every boot, so a Convex restore finds their plans' owners."""
    doc = json.loads((FIXTURES / "community.json").read_text(encoding="utf-8"))
    app.social.reset()
    for p in doc["people"]:
        persona = Persona(id=p["id"], name=p["name"], initials=p["initials"], is_demo_persona=True,
                          home_area=p["homeArea"], role="customer", agent_address=f"agent1q-{p['id'][2:]}")
        persona.token = sign_persona(persona.id, app.s.secret)
        app.personas[persona.id] = persona
        app.social.profiles[p["id"]] = {"bio": p["bio"], "interests": p["interests"], "community": True}
    return doc


def seed_community(app: "Rally") -> None:
    """Demo people across many activities and places, their open plans (compiled by the real compiler)
    and trip recaps. Their personal agents get neutral starting preferences for each plan."""
    from rally_contracts import PublicIntent

    from .service import prefs_hash
    doc = load_people(app)
    soc = app.social
    base = now_ms() - 10 * 60_000                    # interleave with recaps so the feed opens varied
    for i, plan in enumerate(doc["plans"]):
        res = compiler_mod.compile_goal(plan["text"], app.s.demo_today, "template")
        draft = res.draft
        draft.group_max = plan["groupMax"]
        draft.group_min = 1 if plan["groupMax"] == 1 else 2
        draft.missing = [m for m in draft.missing if m.field not in {"groupMax", "budgetMax"}]
        iid = f"i_c{i:02d}_{plan['userId'][2:]}"
        prefs = app._neutral_prefs(draft)
        best = prefs["best"]
        for t in draft.negotiable_terms:             # people differ: rotate favourites by person
            if t.options and t.type != "date" and t.key in best:
                best[t.key] = t.options[(i + len(plan["userId"])) % len(t.options)]
        app.agent_prefs[iid] = prefs
        intent = PublicIntent(id=iid, goal_id=f"g_c{i:02d}", user_id=plan["userId"], text=plan["text"],
                              draft=draft, status="open", created_at=base - ((i * 7) % len(doc["plans"])) * 23 * 60_000,
                              is_demo_persona=True, prefs_hash=prefs_hash(prefs))
        app.store.intents[iid] = intent
        app.store.publish_row("intents", iid, intent.wire(), [])
    for k, p in enumerate(doc["posts"]):
        pid = f"post_seed_{k}"
        soc.posts[pid] = {"id": pid, "userId": p["userId"], "text": p["text"], "activity": p["activity"],
                          "place": p["place"], "dealId": None, "at": now_ms() - p["hoursAgo"] * HOUR}
        soc.base_likes[pid] = p["likes"]
        soc.comments[pid] = [{"id": f"cm_{k}_{j}", "userId": doc["people"][(k + j + 1) % len(doc["people"])]["id"],
                              "text": t, "at": now_ms() - (p["hoursAgo"] - j - 1) * HOUR}
                             for j, t in enumerate(["Count me in next time!", "Which shop did you use?",
                                                    "This is awesome.", "Saving this."][:p["comments"]])]
    # a few follows so "Following" isn't empty
    for a, b in (("u_kevin", "c_lena"), ("u_kevin", "c_marco"), ("u_kevin", "c_sofia"), ("c_lena", "u_kevin"),
                 ("c_ben", "u_kevin"), ("u_ana", "c_leo")):
        soc.follows.setdefault(a, set()).add(b)


# ------------------------------------------------------------------ feed

def _person(app: "Rally", uid: str) -> dict:
    p = app.personas.get(uid)
    return {"id": uid, "name": p.name if p else uid, "initials": p.initials if p else "?",
            "homeArea": p.home_area if p else ""}


def _engagement(app: "Rally", item_id: str, me: str) -> dict:
    soc = app.social
    likers = soc.likes.get(item_id, set())
    return {"likes": soc.base_likes.get(item_id, 0) + len(likers), "likedByMe": me in likers,
            "comments": len(soc.comments.get(item_id, []))}


def _plan_item(app: "Rally", it, me: str) -> dict:
    d = it.draft
    return {"type": "plan", "id": it.id, "at": it.created_at, "user": _person(app, it.user_id),
            "activity": catalog.canonical(d.activity), "activityLabel": catalog.label(d.activity),
            "category": (catalog.info(d.activity) or {}).get("category", "other"),
            "place": d.location.label if d.location else None, "text": it.text,
            "dateFrom": d.date_from.isoformat() if d.date_from else None,
            "dateTo": d.date_to.isoformat() if d.date_to else None,
            "budget": d.budget_max.amount if d.budget_max else None, "groupMax": d.group_max,
            "mine": it.user_id == me, "joinable": it.user_id != me and it.status == "open",
            **_engagement(app, it.id, me)}


def _trip_item(app: "Rally", deal, me: str) -> dict | None:
    props = app.store.proposals.get(deal.id) or []
    quote = next((q for q in app.store.quotes.get(deal.id, []) if q.id == deal.chosen_quote_id), None)
    if not props or quote is None:
        return None
    members = [m for m in app.store.members[deal.id] if m.state == "joined"]
    place = app._deal_place(deal.id)
    return {"type": "trip", "id": deal.id, "at": deal.created_at, "user": _person(app, deal.created_by),
            "activity": deal.activity, "activityLabel": deal.activity_label,
            "category": (catalog.info(deal.activity) or {}).get("category", "other"),
            "place": place.label if place else None, "title": deal.title, "solo": deal.solo,
            "people": [_person(app, m.user_id)["name"].split()[0] for m in members],
            "date": props[-1].terms.get("date"), "vendor": quote.provider_name,
            "pricePerPerson": quote.price_per_person, "listed": quote.provenance == "cached",
            "status": deal.status, "member": any(m.user_id == me for m in members),
            **_engagement(app, deal.id, me)}


def _post_item(app: "Rally", p: dict, me: str) -> dict:
    return {"type": "post", "id": p["id"], "at": p["at"], "user": _person(app, p["userId"]), "text": p["text"],
            "activity": p.get("activity"), "activityLabel": catalog.label(p["activity"]) if p.get("activity") else None,
            "category": (catalog.info(p.get("activity") or "") or {}).get("category", "other"),
            "place": p.get("place"), "dealId": p.get("dealId"), **_engagement(app, p["id"], me)}


def feed(app: "Rally", me: str, scope: str = "all", activity: str = "", category: str = "", limit: int = 60) -> dict:
    items: list[dict] = []
    for it in app.store.intents.values():
        if it.status == "open":
            items.append(_plan_item(app, it, me))
    for deal in app.store.deals.values():
        if deal.status in {"COMMITTED", "AWAITING_APPROVAL", "COMMITMENT_PENDING"}:
            t = _trip_item(app, deal, me)
            if t:
                items.append(t)
    items += [_post_item(app, p, me) for p in app.social.posts.values()]
    if scope == "following":
        follow = app.social.follows.get(me, set())
        items = [i for i in items if i["user"]["id"] in follow]
    if activity:
        a = app.resolve_activity_place(activity=activity)[0]
        items = [i for i in items if i.get("activity") == a]
    if category:
        items = [i for i in items if i.get("category") == category]
    items.sort(key=lambda i: -i["at"])
    counts: dict[str, int] = {}
    for it in app.store.intents.values():
        if it.status == "open":
            k = catalog.canonical(it.draft.activity)
            counts[k] = counts.get(k, 0) + 1
    trending = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
    return {"items": items[:limit], "trending": [{"activity": k, "label": catalog.label(k), "openPlans": n}
                                                  for k, n in trending]}


# ------------------------------------------------------------------ actions

def _item_exists(app: "Rally", item_id: str) -> bool:
    return item_id in app.store.intents or item_id in app.store.deals or item_id in app.social.posts


def toggle_like(app: "Rally", me: str, item_id: str) -> dict:
    if not _item_exists(app, item_id):
        raise ApiError(404, "NOT_FOUND", "That post is gone.")
    s = app.social.likes.setdefault(item_id, set())
    s.symmetric_difference_update({me})
    return _engagement(app, item_id, me)


def comments(app: "Rally", item_id: str) -> list[dict]:
    return [{**c, "user": _person(app, c["userId"])} for c in app.social.comments.get(item_id, [])]


def add_comment(app: "Rally", me: str, item_id: str, text: str) -> list[dict]:
    text = (text or "").strip()
    if not text:
        raise ApiError(422, "EMPTY", "Write something first.")
    if len(text) > 500:
        raise ApiError(422, "TOO_LONG", "Keep comments under 500 characters.")
    if not _item_exists(app, item_id):
        raise ApiError(404, "NOT_FOUND", "That post is gone.")
    app.social.comments.setdefault(item_id, []).append(
        {"id": f"cm_{uuid.uuid4().hex[:8]}", "userId": me, "text": text, "at": now_ms()})
    return comments(app, item_id)


def create_post(app: "Rally", me: str, text: str, activity: str = "", place: str = "", deal_id: str = "") -> dict:
    text = (text or "").strip()
    if not text or len(text) > 1000:
        raise ApiError(422, "BAD_POST", "Posts need 1 to 1,000 characters.")
    if deal_id:
        app._member(deal_id, me, active_only=False)       # recaps only from people who went
        deal = app._deal(deal_id)
        activity = activity or deal.activity
        place = place or (app._deal_place(deal_id).label if app._deal_place(deal_id) else "")
    pid = f"post_{uuid.uuid4().hex[:8]}"
    post = {"id": pid, "userId": me, "text": text, "activity": catalog.canonical(activity) if activity else None,
            "place": place or None, "dealId": deal_id or None, "at": now_ms()}
    app.social.posts[pid] = post
    app.store.publish_row("posts", pid, post, [])
    return _post_item(app, post, me)


def toggle_follow(app: "Rally", me: str, uid: str) -> dict:
    if uid not in app.personas or uid == me:
        raise ApiError(422, "BAD_FOLLOW", "You can't follow that account.")
    s = app.social.follows.setdefault(me, set())
    s.symmetric_difference_update({uid})
    return {"following": uid in s, "followers": sum(uid in f for f in app.social.follows.values())}


def profile(app: "Rally", me: str, uid: str) -> dict:
    p = app.personas.get(uid)
    if p is None or p.role != "customer":
        raise ApiError(404, "NOT_FOUND", "No such person.")
    prof = app.social.profiles.get(uid, {})
    plans = [_plan_item(app, it, me) for it in app.store.intents.values() if it.user_id == uid and it.status == "open"]
    trips = [t for t in (_trip_item(app, d, me) for d in app.store.deals.values()
                         if any(m.user_id == uid and m.state == "joined" for m in app.store.members[d.id]))
             if t and t["status"] == "COMMITTED"]
    posts = [_post_item(app, x, me) for x in app.social.posts.values() if x["userId"] == uid]
    interests = prof.get("interests") or sorted({x["activity"] for x in plans + trips + posts if x.get("activity")})
    return {"id": uid, "name": p.name, "initials": p.initials, "homeArea": p.home_area,
            "bio": prof.get("bio", ""), "community": bool(prof.get("community")),
            "interests": [{"activity": a, "label": catalog.label(a)} for a in interests],
            "followers": sum(uid in f for f in app.social.follows.values()),
            "following": len(app.social.follows.get(uid, set())),
            "followedByMe": uid in app.social.follows.get(me, set()), "isMe": uid == me,
            "plans": sorted(plans, key=lambda x: -x["at"]), "trips": sorted(trips, key=lambda x: -x["at"]),
            "posts": sorted(posts, key=lambda x: -x["at"])}


def people(app: "Rally", me: str, q: str = "") -> list[dict]:
    q = q.casefold().strip()
    out = []
    for uid, p in app.personas.items():
        if p.role != "customer" or uid == me:
            continue
        prof = app.social.profiles.get(uid, {})
        interests = prof.get("interests", [])
        hay = " ".join([p.name, p.home_area, *[catalog.label(a) for a in interests]]).casefold()
        if q and q not in hay:
            continue
        out.append({**_person(app, uid), "interests": [catalog.label(a) for a in interests][:3],
                    "followedByMe": uid in app.social.follows.get(me, set())})
    return out[:40]


def join_plan(app: "Rally", me: str, intent_id: str) -> dict:
    """'I'm in too': publish the same public plan as mine (same activity, place, dates, budget cap) with my
    agent's neutral preferences, run matching, and pre-select the person whose plan it was."""
    src = app.store.intents.get(intent_id)
    if src is None or src.status != "open":
        raise ApiError(404, "NOT_FOUND", "That plan isn't open any more.")
    if src.user_id == me:
        raise ApiError(422, "OWN_PLAN", "That's your own plan.")
    draft = src.draft.model_copy(deep=True)
    draft.missing = []
    goal_id = f"g_{uuid.uuid4().hex[:8]}"
    name = app.personas[src.user_id].name.split()[0]
    goal = {"id": goal_id, "userId": me, "text": f"Joining {name}: {src.text}", "status": "ready",
            "compiledBy": "join", "warnings": [], "draft": draft.wire(), "createdAt": now_ms(),
            "suggestedPrefs": app._neutral_prefs(draft), "_extracted": None}
    app.store.goals[goal_id] = goal
    app.store.publish_row("goals", goal_id, app._stored_goal(goal), [me])
    intent = app.publish_intent(me, goal_id, goal["suggestedPrefs"])
    m = app.run_matches(me, intent["id"])
    if intent_id not in m["selectedIntentIds"] and any(c["intentId"] == intent_id for c in m["matches"]):
        m["selectedIntentIds"] = [intent_id, *m["selectedIntentIds"]][: max(1, (draft.group_max or 2) - 1)]
        app.store.matches[intent["id"]] = m
    return {"goalId": goal_id, "intentId": intent["id"], "withUserId": src.user_id}


def install(rally_cls) -> None:
    for fn in (feed, toggle_like, comments, add_comment, create_post, toggle_follow, profile, people, join_plan):
        setattr(rally_cls, f"social_{fn.__name__}", fn)
    setattr(rally_cls, "seed_community", seed_community)
    setattr(rally_cls, "load_community_people", load_people)


_ = Any
