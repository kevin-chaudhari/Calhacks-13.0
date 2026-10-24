"""FastAPI application: commands in, state out (plan section 12).

Run: uvicorn rally.main:app --reload --port 8000   (see Makefile: make api)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from rally_contracts import ApprovalRequest

from .core import ApiError, Settings, verify_persona
from .service import Rally
from .store import ConvexMirror, MemoryStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
settings = Settings()
mirror = ConvexMirror(settings.convex_url, settings.convex_server_key) \
    if settings.store == "convex" and settings.convex_url else None
rally = Rally(settings, MemoryStore(mirror))



@asynccontextmanager
async def lifespan(_: FastAPI):
    resumed = rally.resume()          # restart recovery: mediators, invites and quote requests in flight
    if rally.restored:
        logging.getLogger("rally").info("restored from Convex: %s; resumed %s", rally.restored, resumed)
    yield
    if mirror:
        mirror.close()


app = FastAPI(title="Rally API", version="0.1.0", lifespan=lifespan,
              description="Commands for the Rally group-deal engine. The UI reads state from Convex "
                          "(or GET /v1/deals/{id}/snapshot in local dev).")
rally.rail.install(app, rally)          # x402: payment middleware + POST /v1/x402/deposits/{deal}/{user}
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    return JSONResponse(exc.body(), status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    fields = {".".join(str(p) for p in e["loc"][1:]): e["msg"] for e in exc.errors()}
    return JSONResponse({"error": {"code": "VALIDATION", "message": "Request is invalid.",
                                   "retryable": False, "fields": fields}}, status_code=422)


# --------------------------------------------------------------- auth & limits

_buckets: dict[str, list[float]] = defaultdict(list)


def user(authorization: str = Header(default="")) -> str:
    uid = verify_persona(authorization.removeprefix("Bearer ").strip(), settings.secret)
    if not uid or uid not in rally.personas:
        raise ApiError(401, "UNAUTHENTICATED", "Pick a demo identity first.")
    return uid


def limited(uid: str, kind: str, per_min: int) -> None:
    now = time.time()
    b = [t for t in _buckets[f"{uid}:{kind}"] if now - t < 60]
    if len(b) >= per_min:
        raise ApiError(429, "RATE_LIMITED", "Slow down a little.", retryable=True)
    b.append(now)
    _buckets[f"{uid}:{kind}"] = b


def idempotent(uid: str, route: str, key: str | None, fn):
    """Same Idempotency-Key + persona + route returns the first response."""
    if not key:
        return fn()
    k = f"{uid}:{route}:{key}"
    if k not in rally.store.idempotency:
        rally.store.idempotency[k] = fn()
    return rally.store.idempotency[k]


async def aidempotent(uid: str, route: str, key: str | None, coro_fn):
    if not key:
        return await coro_fn()
    k = f"{uid}:{route}:{key}"
    if k not in rally.store.idempotency:
        rally.store.idempotency[k] = await coro_fn()
    return rally.store.idempotency[k]


# --------------------------------------------------------------------- bodies

class CompileBody(BaseModel):
    text: str
    timezone: str = "America/Los_Angeles"


class PublishBody(BaseModel):
    goalId: str
    privatePrefs: dict[str, Any]


class MatchBody(BaseModel):
    limit: int = 20


class DealBody(BaseModel):
    intentId: str
    candidateIntentIds: list[str]


class CommitBody(BaseModel):
    proposalVersion: int


class LeaveBody(BaseModel):
    reason: str | None = None


class ResetBody(BaseModel):
    scenario: str = "scuba"


# --------------------------------------------------------------------- routes

@app.get("/v1/health")
def health():
    return {"ok": True, "adapters": rally.provenance(),
            "convex": mirror.stats() if mirror else {"enabled": False},
            "restored": rally.restored,
            "payments": rally.rail.status(),
            "agents": {"personal": len(rally.agent_prefs), "providers": len(rally.providers)}}


@app.get("/v1/demo/personas")
def personas():
    if not settings.allow_demo_routes:
        raise ApiError(403, "DISABLED", "Demo routes are disabled.")
    return [p.wire() for p in rally.personas.values()]


@app.post("/v1/demo/reset")
def reset(body: ResetBody):
    if not settings.allow_demo_routes:
        raise ApiError(403, "DISABLED", "Demo routes are disabled.")
    if body.scenario != "scuba":
        raise ApiError(400, "UNKNOWN_SCENARIO", "Only the scuba scenario is seeded.")
    rally.seed()
    _buckets.clear()                  # a fresh rehearsal starts with fresh rate limits
    return {"ok": True, "intents": len(rally.store.intents)}


@app.post("/v1/goals:compile")
def compile_goal(body: CompileBody, uid: str = Depends(user), idempotency_key: str | None = Header(default=None)):
    limited(uid, "compile", 10)
    return idempotent(uid, "compile", idempotency_key, lambda: rally.compile_goal(uid, body.text))


@app.get("/v1/goals")
def my_goals(uid: str = Depends(user)):
    return rally.list_goals(uid)


@app.get("/v1/goals/{goal_id}")
def get_goal(goal_id: str, uid: str = Depends(user)):
    return rally.get_goal(uid, goal_id)


@app.patch("/v1/goals/{goal_id}")
def patch_goal(goal_id: str, body: dict[str, Any], uid: str = Depends(user)):
    limited(uid, "cmd", 30)
    return rally.patch_goal(uid, goal_id, body)


@app.post("/v1/intents")
def publish(body: PublishBody, uid: str = Depends(user), idempotency_key: str | None = Header(default=None)):
    limited(uid, "cmd", 30)
    return idempotent(uid, "publish", idempotency_key,
                      lambda: rally.publish_intent(uid, body.goalId, body.privatePrefs))


@app.get("/v1/intents/{intent_id}")
def get_intent(intent_id: str, uid: str = Depends(user)):
    return rally.get_intent(intent_id)


@app.post("/v1/intents/{intent_id}/matches")
def matches(intent_id: str, body: MatchBody | None = None, uid: str = Depends(user)):
    limited(uid, "cmd", 30)
    return rally.run_matches(uid, intent_id, (body or MatchBody()).limit)


@app.get("/v1/intents/{intent_id}/matches")
def get_matches(intent_id: str, uid: str = Depends(user)):
    m = rally.store.matches.get(intent_id)
    if not m:
        raise ApiError(404, "NOT_FOUND", "Matching has not run for this intent.")
    return m


@app.post("/v1/deals")
async def create_deal(body: DealBody, uid: str = Depends(user), idempotency_key: str | None = Header(default=None)):
    limited(uid, "cmd", 30)
    return await aidempotent(uid, "deal", idempotency_key,
                             lambda: rally.create_deal(uid, body.intentId, body.candidateIntentIds))


@app.get("/v1/deals")
def my_deals(uid: str = Depends(user)):
    return rally.list_deals(uid)


@app.get("/v1/deals/{deal_id}")
def get_deal(deal_id: str, uid: str = Depends(user)):
    rally._member(deal_id, uid, active_only=False)
    return rally._deal(deal_id).wire()


@app.get("/v1/deals/{deal_id}/snapshot")
def snapshot(deal_id: str, uid: str = Depends(user)):
    """Dev read path (STORE=memory). In Convex mode the UI subscribes to the same document."""
    rally._member(deal_id, uid, active_only=False)
    return rally.snapshot(deal_id)


@app.post("/v1/deals/{deal_id}/join")
async def join(deal_id: str, uid: str = Depends(user)):
    return await rally.join(uid, deal_id)


@app.post("/v1/deals/{deal_id}/negotiate", status_code=202)
async def negotiate(deal_id: str, uid: str = Depends(user)):
    return await rally.negotiate(uid, deal_id)


@app.get("/v1/deals/{deal_id}/rounds")
def rounds(deal_id: str, uid: str = Depends(user)):
    rally._member(deal_id, uid, active_only=False)
    return [r.wire() for r in rally.store.rounds[deal_id]]


@app.post("/v1/deals/{deal_id}/proposals")
def relax(deal_id: str, uid: str = Depends(user)):
    raise ApiError(501, "NOT_IMPLEMENTED", "Relaxing a term after NO_AGREEMENT is planned (plan 12.1) "
                                           "but not in this build. Leave the group or start a new goal.")


@app.post("/v1/deals/{deal_id}/approvals")
async def approve(deal_id: str, body: ApprovalRequest, uid: str = Depends(user)):
    limited(uid, "cmd", 30)
    return await rally.approve(uid, deal_id, body.proposal_version, body.quote_id, body.decision, body.auto_commit)


@app.post("/v1/deals/{deal_id}/commitments")
async def commit(deal_id: str, body: CommitBody, uid: str = Depends(user)):
    return await rally.commit(uid, deal_id, body.proposalVersion)


@app.post("/v1/deals/{deal_id}/leave")
async def leave(deal_id: str, body: LeaveBody | None = None, uid: str = Depends(user)):
    return await rally.leave(uid, deal_id, (body or LeaveBody()).reason)


@app.get("/v1/deals/{deal_id}/events")
def events(deal_id: str, afterSeq: int = 0, uid: str = Depends(user)):
    rally._member(deal_id, uid, active_only=False)
    return [e.wire() for e in rally.store.events[deal_id] if e.seq > afterSeq]


@app.get("/v1/providers")
def providers(activity: str | None = None):
    return [p for p in rally.providers if not activity or p["activity"] == activity]


@app.get("/v1/diagnostics")
def diagnostics(uid: str = Depends(user)):
    return rally.diagnostics()


@app.post("/v1/demo/act-as/{persona_id}/approve/{deal_id}")
async def demo_approve_for(persona_id: str, deal_id: str, body: ApprovalRequest, uid: str = Depends(user)):
    """A human clicks 'approve' on behalf of a seeded demo persona. Refused for real teammates."""
    if not settings.allow_demo_routes:
        raise ApiError(403, "DISABLED", "Demo routes are disabled.")
    if not rally.persona(persona_id).is_demo_persona:
        raise ApiError(403, "NOT_DEMO_PERSONA", "Only seeded demo personas can be approved on someone's behalf.")
    rally._member(deal_id, uid)
    return await rally.approve(persona_id, deal_id, body.proposal_version, body.quote_id, body.decision,
                               body.auto_commit)


# ------------------------------------------------------------- chat & voice

class MessageBody(BaseModel):
    text: str
    lang: str = "en-US"
    viaVoice: bool = False


class TranslateBody(BaseModel):
    text: str
    source: str = ""
    target: str


@app.post("/v1/deals/{deal_id}/messages")
async def post_message(deal_id: str, body: MessageBody, uid: str = Depends(user)):
    limited(uid, "chat", 40)
    return await rally.post_message(uid, deal_id, body.text, body.lang, body.viaVoice)


@app.post("/v1/translate")
def translate(body: TranslateBody, uid: str = Depends(user)):
    limited(uid, "translate", 30)
    return rally.translate(body.text, body.source, body.target)


# ------------------------------------------------------------------ vendors

class VendorQuoteBody(BaseModel):
    action: str = "approve"                  # approve | decline
    pricePerPerson: float | None = None      # may only lower the agent's draft
    note: str | None = None


@app.get("/v1/vendor/dashboard")
def vendor_dashboard(uid: str = Depends(user)):
    return rally.vendor_dashboard(uid)


@app.get("/v1/vendor/requests")
def vendor_requests(uid: str = Depends(user)):
    return rally.vendor_requests(uid)


@app.get("/v1/vendor/requests/{deal_id}")
def vendor_request(deal_id: str, uid: str = Depends(user)):
    return rally.vendor_request(uid, deal_id)


@app.post("/v1/vendor/requests/{deal_id}/quote")
async def vendor_quote(deal_id: str, body: VendorQuoteBody, uid: str = Depends(user)):
    if body.action not in {"approve", "decline"}:
        raise ApiError(422, "BAD_ACTION", "action must be approve or decline")
    return await rally.vendor_quote(uid, deal_id, body.action, body.pricePerPerson, body.note)


@app.post("/v1/vendor/requests/{deal_id}/booking")
async def vendor_booking(deal_id: str, uid: str = Depends(user)):
    return await rally.vendor_booking(uid, deal_id)


@app.patch("/v1/vendor/provider")
def vendor_update(body: dict[str, Any], uid: str = Depends(user)):
    return rally.vendor_update(uid, body)


# ------------------------------------------------------- platform: demo control room

class LaunchBody(BaseModel):
    scenario: str = "scuba"
    autoNegotiate: bool = True


@app.get("/v1/metrics")
def metrics():
    """Live numbers for the control room and the pitch. Computed from current state, never estimated."""
    return rally.metrics()


@app.post("/v1/demo/launch")
async def launch(body: LaunchBody, uid: str = Depends(user)):
    """One click from nothing to a live group room, for repeated expo demos."""
    if not settings.allow_demo_routes:
        raise ApiError(403, "DISABLED", "Demo routes are disabled.")
    limited(uid, "cmd", 30)
    return await rally.launch(body.scenario, organizer=uid, auto_negotiate=body.autoNegotiate)


@app.get("/v1/demo/seats/{deal_id}")
def seats(deal_id: str, uid: str = Depends(user)):
    """QR links that put a judge's phone in a member's or the vendor's seat (demo identities only)."""
    if not settings.allow_demo_routes:
        raise ApiError(403, "DISABLED", "Demo routes are disabled.")
    return rally.seats(uid, deal_id, settings.web_url)
