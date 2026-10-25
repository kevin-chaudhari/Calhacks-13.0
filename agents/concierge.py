"""Parley concierge: type a group-trip goal in ASI:One, get back a negotiated group plan.

    python agents/concierge.py     # mailbox agent; needs the API (and, for TRANSPORT=agentverse, run_agents.py)

Chat Protocol (ChatMessage / ChatAcknowledgement) with a published manifest, so ASI:One can
discover and route to it. On each message it drives the Parley API over HTTP:
compile -> (ask a missing question) -> publish -> matches -> deal -> negotiate -> poll the snapshot,
and replies in three short messages: what Parley understood, who matched, and the agreed plan
with a link to the live group room.

People already in a deal are not matched again, so a second chat finds nobody until the demo board
is reset; CONCIERGE_RESET_EACH_GOAL=1 resets it before every new goal (it also ends earlier rooms).

Identity: ASI:One senders map to Parley demo personas from CONCIERGE_PERSONAS (default u_kevin),
in order of first contact; with one persona, every sender acts as Kevin.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/contracts"), str(ROOT / "services/api")]

Say = Callable[[str], Awaitable[None]]
DONE = {"AWAITING_APPROVAL", "NO_AGREEMENT", "COMMITTED", "CANCELLED", "FAILED"}
CERTS = [("divemaster", "divemaster"), ("rescue", "rescue"), ("advanced", "advanced"),
         ("open water", "open_water"), ("openwater", "open_water"), ("not certified", "none"), ("none", "none")]


class ApiFailure(Exception):
    pass


class RallyAPI:
    """The Parley HTTP API, as the concierge uses it. Replace with a fake in tests."""

    def __init__(self, base_url: str, transport=None):
        import httpx
        self.http = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=30, transport=transport)
        self.tokens: dict[str, str] = {}

    async def _call(self, method: str, path: str, persona: str | None = None, json: Any = None) -> Any:
        headers = {"Authorization": f"Bearer {self.tokens[persona]}"} if persona else {}
        r = await self.http.request(method, path, json=json, headers=headers)
        if r.status_code >= 400:
            try:
                err = r.json()["error"]
                raise ApiFailure(f"{err['message']} ({err['code']})")
            except (ValueError, KeyError):
                raise ApiFailure(f"HTTP {r.status_code} on {path}") from None
        return r.json()

    async def login(self, persona: str) -> None:
        if persona not in self.tokens:
            for p in await self._call("GET", "/v1/demo/personas"):
                self.tokens[p["id"]] = p["token"]
        if persona not in self.tokens:
            raise ApiFailure(f"unknown persona {persona}")

    async def reset(self):
        await self._call("POST", "/v1/demo/reset", json={"scenario": "scuba"})

    async def compile(self, persona, text):
        return await self._call("POST", "/v1/goals:compile", persona, {"text": text})

    async def patch_goal(self, persona, goal_id, patch):
        return await self._call("PATCH", f"/v1/goals/{goal_id}", persona, patch)

    async def publish(self, persona, goal_id, prefs):
        return await self._call("POST", "/v1/intents", persona, {"goalId": goal_id, "privatePrefs": prefs})

    async def matches(self, persona, intent_id):
        return await self._call("POST", f"/v1/intents/{intent_id}/matches", persona, {})

    async def create_deal(self, persona, intent_id, candidates):
        return await self._call("POST", "/v1/deals", persona, {"intentId": intent_id, "candidateIntentIds": candidates})

    async def negotiate(self, persona, deal_id):
        return await self._call("POST", f"/v1/deals/{deal_id}/negotiate", persona)

    async def snapshot(self, persona, deal_id):
        return await self._call("GET", f"/v1/deals/{deal_id}/snapshot", persona)


# ----------------------------------------------------------------- formatting

def _day(iso: str | None) -> str:
    if not iso:
        return "?"
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def _value(key: str, v: Any) -> str:
    if isinstance(v, bool):
        return key.replace("_included", "").replace("_", " ") + (" included" if v else " not included")
    if key == "date":
        return _day(v)
    if key == "dive_type":
        return f"{v} dive"
    return str(v)


def understood(draft: dict, compiled_by: str) -> str:
    parts = [draft.get("activity", "activity").replace("_", " ").capitalize()]
    if draft.get("location"):
        parts.append(f"near {draft['location']['label']}")
    if draft.get("dateFrom"):
        parts.append(f"{_day(draft['dateFrom'])}–{_day(draft.get('dateTo'))}")
    if draft.get("budgetMax"):
        parts.append(f"up to ${draft['budgetMax']['amount']:.0f} per person")
    if draft.get("groupMax"):
        parts.append(f"group of up to {draft['groupMax']}")
    cert = next((c["value"] for c in draft.get("conditions", []) if c.get("key") == "certification" and c.get("value")),
                None)
    if cert:
        parts.append(f"{cert.replace('_', ' ').title()} certified")
    how = "Gemini" if compiled_by == "gemini" else "Parley's offline compiler"
    return f"Here's what I understood: {', '.join(parts)}. (Compiled by {how}.)"


def matched(m: dict) -> str:
    chosen = [x["name"] for x in m["matches"] if x["selected"]]
    lines = [f"Found {len(chosen)} {'person' if len(chosen) == 1 else 'people'} who fit: {', '.join(chosen)}."]
    if m["rejections"]:
        lines.append("Not a fit: " + "; ".join(f"{r['name']} ({r['reason']})" for r in m["rejections"]) + ".")
    lines.append("Their agents are negotiating one shared plan now…")
    return " ".join(lines)


def plan_reply(snap: dict, link: str) -> str:
    deal, props = snap["deal"], snap["proposals"]
    names = snap.get("providerNames", {})
    if deal["status"] == "NO_AGREEMENT":
        why = "; ".join(deal.get("conflicts") or []) or "no plan fit everyone"
        return f"The agents couldn't agree on one plan: {why}. See the details in the group room: {link}"
    if not props:
        return f"Still negotiating. Follow it live in the group room: {link}"
    p = props[-1]
    terms = ", ".join(_value(k, v) for k, v in p["terms"].items())
    quote = next((q for q in snap.get("quotes", []) if q["id"] == deal.get("chosenQuoteId")), None)
    price = quote["pricePerPerson"] if quote else p["pricePerPerson"]
    rounds = len(snap.get("rounds", []))
    people = sum(1 for m in snap["members"] if m["state"] == "joined")
    head = (f"Agreed! All {people} agents accepted plan v{p['version']} in {rounds} round{'s' if rounds != 1 else ''}: "
            f"{terms} with {names.get(p['providerId'], p['providerId'])}, ${price:.0f} per person")
    if deal["status"] == "AWAITING_APPROVAL":
        return f"{head} (simulated quote). Everyone approves in the group room: {link}"
    if deal.get("vendorReview"):
        staff = deal["vendorReview"].get("staffName", "their staff")
        return f"{head}, pending {staff}'s review of the quote. Follow it live: {link}"
    return f"{head}. Group room: {link}"


def parse_answer(field_: str, text: str) -> dict:
    """Structured PATCH for an answer to the compiler's question, when the text clearly gives one."""
    low = text.lower()
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))]
    if field_ in {"groupMax", "groupMin"} and nums and 1 <= nums[0] <= 8 and nums[0].is_integer():
        return {field_: int(nums[0])}
    if field_ == "budgetMax" and nums:
        return {"budgetMax": nums[0]}
    if field_ == "certification":
        for word, level in CERTS:
            if word in low:
                return {"certification": level}
    return {}


# -------------------------------------------------------------------- logic

@dataclass
class Session:
    sender: str
    persona: str
    text: str = ""
    patch: dict = field(default_factory=dict)
    asking: str | None = None
    busy: bool = False


class Concierge:
    def __init__(self, api, web_url: str, personas: list[str], timeout_s: float = 120.0, poll_s: float = 0.5,
                 reset_each_goal: bool = False):
        self.api, self.web_url = api, web_url.rstrip("/")
        self.reset_each_goal = reset_each_goal        # judging: every new chat goal gets a fresh demo board
        self.personas = personas or ["u_kevin"]
        self.timeout_s, self.poll_s = timeout_s, poll_s
        self.sessions: dict[str, Session] = {}
        self.seen: list[str] = []                      # senders in order of first contact

    def persona_for(self, sender: str) -> str:
        if sender not in self.seen:
            self.seen.append(sender)
        return self.personas[(self.seen.index(sender)) % len(self.personas)]

    async def handle(self, sender: str, text: str, say: Say) -> None:
        text = text.strip()
        if not text:
            return
        s = self.sessions.get(sender)
        if s is None or text.lower() in {"start over", "reset", "new goal"}:
            s = self.sessions[sender] = Session(sender, self.persona_for(sender))
            if text.lower() in {"start over", "reset", "new goal"}:
                await say("Starting fresh. What would you like to do, and with whom?")
                return
        if s.busy:
            await say("Still working on your last goal; I'll message you when the plan is ready.")
            return
        s.busy = True
        try:
            await self._step(s, text, say)
        except ApiFailure as exc:
            await say(f"Parley couldn't do that: {exc}. Try rephrasing, or say 'start over'.")
            s.text, s.patch, s.asking = "", {}, None
        except Exception as exc:  # noqa: BLE001 - the chat must always answer
            await say(f"Something went wrong on Parley's side ({type(exc).__name__}). Say 'start over' to retry.")
            s.text, s.patch, s.asking = "", {}, None
        finally:
            s.busy = False

    async def _step(self, s: Session, text: str, say: Say) -> None:
        await self.api.login(s.persona)
        if s.asking:
            s.patch.update(parse_answer(s.asking, text))
            s.text = f"{s.text}. {text}"
        else:
            s.text, s.patch = text, {}
            if self.reset_each_goal:
                await self.api.reset()
        goal = await self.api.compile(s.persona, s.text)
        if s.patch:
            goal = await self.api.patch_goal(s.persona, goal["id"], s.patch)
        missing = goal["draft"].get("missing") or []
        if missing:
            q = missing[0]
            s.asking = q["field"]
            hint = f" (for example {', '.join(str(x) for x in q['suggestions'][:3])})" if q.get("suggestions") else ""
            await say(f"{q['question']}{hint}")
            return
        s.asking = None
        await say(understood(goal["draft"], goal.get("compiledBy", "template")))
        await self._run(s, goal, say)
        self.sessions.pop(s.sender, None)                  # the next message starts a new goal

    async def _run(self, s: Session, goal: dict, say: Say) -> None:
        intent = await self.api.publish(s.persona, goal["id"], goal["suggestedPrefs"])
        m = await self.api.matches(s.persona, intent["id"])
        if not m["selectedIntentIds"]:
            reasons = "; ".join(f"{r['name']} ({r['reason']})" for r in m["rejections"][:5])
            await say("I couldn't find anyone who fits yet." + (f" Closest: {reasons}." if reasons else ""))
            return
        await say(matched(m))
        deal = await self.api.create_deal(s.persona, intent["id"], m["selectedIntentIds"])
        link = f"{self.web_url}/deals/{deal['id']}"
        end = time.monotonic() + 15
        while time.monotonic() < end:                       # invited agents join within seconds
            snap = await self.api.snapshot(s.persona, deal["id"])
            if all(x["state"] != "invited" for x in snap["members"]):
                break
            await asyncio.sleep(self.poll_s)
        await self.api.negotiate(s.persona, deal["id"])
        end = time.monotonic() + self.timeout_s
        while True:
            snap = await self.api.snapshot(s.persona, deal["id"])
            if snap["deal"]["status"] in DONE or snap["deal"].get("vendorReview") or time.monotonic() > end:
                break
            await asyncio.sleep(self.poll_s)
        await say(plan_reply(snap, link))


# -------------------------------------------------------------------- agent

def build_agent(concierge: Concierge, loop=None):
    from uagents import Context, Protocol
    from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, TextContent, chat_protocol_spec

    from rally.negotiation import network

    agent = network.make_agent(network.by_key()["concierge"], loop)
    chat = Protocol(spec=chat_protocol_spec)
    tasks: set[asyncio.Task] = set()

    @chat.on_message(ChatMessage)
    async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
        await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

        async def say(text: str) -> None:
            await ctx.send(sender, ChatMessage(content=[TextContent(text=text)]))

        t = asyncio.create_task(concierge.handle(sender, msg.text(), say))   # negotiation takes a while
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    @chat.on_message(ChatAcknowledgement)
    async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        pass

    agent.include(chat, publish_manifest=True)
    return agent


def from_env() -> Concierge:
    personas = [p.strip() for p in os.environ.get("CONCIERGE_PERSONAS", "u_kevin").split(",") if p.strip()]
    return Concierge(RallyAPI(os.environ.get("RALLY_API_URL", "http://localhost:8000")),
                     os.environ.get("RALLY_WEB_URL", "http://localhost:3000"), personas,
                     timeout_s=float(os.environ.get("CONCIERGE_TIMEOUT_S", "120")),
                     reset_each_goal=os.environ.get("CONCIERGE_RESET_EACH_GOAL", "0") == "1")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = build_agent(from_env())
    print(f"Parley concierge {a.address}")
    a.run()
