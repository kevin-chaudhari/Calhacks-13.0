"""HuddleUp concierge conversation logic with a fake HuddleUp API (no network, no uagents)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agents"))

from concierge import Concierge, parse_answer  # noqa: E402

DRAFT = {"activity": "scuba_diving", "location": {"label": "Monterey, CA"}, "dateFrom": "2026-11-01",
         "dateTo": "2026-11-30", "budgetMax": {"amount": 300.0}, "groupMax": None,
         "conditions": [{"key": "certification", "value": "open_water"}]}


class FakeAPI:
    def __init__(self, end_status="AWAITING_APPROVAL"):
        self.calls, self.end_status = [], end_status
        self.patch = {}

    async def login(self, persona):
        self.calls.append(("login", persona))

    async def reset(self):
        self.calls.append(("reset",))

    def _goal(self):
        draft = {**DRAFT, "groupMax": self.patch.get("groupMax")}
        draft["missing"] = [] if draft["groupMax"] else [
            {"field": "groupMax", "question": "How many people at most, including you?", "suggestions": [4, 5, 6]}]
        return {"id": "g1", "draft": draft, "compiledBy": "template", "suggestedPrefs": {"weights": {}}}

    async def compile(self, persona, text):
        self.calls.append(("compile", text))
        self.patch = {}
        return self._goal()

    async def patch_goal(self, persona, goal_id, patch):
        self.calls.append(("patch", patch))
        self.patch.update(patch)
        return self._goal()

    async def publish(self, persona, goal_id, prefs):
        return {"id": "i1"}

    async def matches(self, persona, intent_id):
        return {"selectedIntentIds": ["i_ana", "i_kai"],
                "matches": [{"name": "Ana", "selected": True}, {"name": "Kai", "selected": True}],
                "rejections": [{"name": "Theo", "reason": "Budget $80 is below any available option (from $95)"}]}

    async def create_deal(self, persona, intent_id, candidates):
        self.calls.append(("deal", candidates))
        return {"id": "d_abc"}

    async def negotiate(self, persona, deal_id):
        self.calls.append(("negotiate", deal_id))

    async def snapshot(self, persona, deal_id):
        members = [{"state": "joined"}] * 3
        return {"deal": {"status": self.end_status, "chosenQuoteId": "q1", "conflicts": ["Kai needs a different date"],
                         "vendorReview": None},
                "members": members, "rounds": [{}, {}, {}, {}],
                "proposals": [{"version": 4, "terms": {"date": "2026-11-15", "dive_type": "boat",
                                                       "gear_included": True, "site": "Point Lobos"},
                               "providerId": "p_ottercove", "pricePerPerson": 190.0}],
                "quotes": [{"id": "q1", "pricePerPerson": 182.0}],
                "providerNames": {"p_ottercove": "Otter Cove Dive Co."}}


def chat(concierge, sender, text):
    out = []

    async def say(t):
        out.append(t)
    asyncio.run(concierge.handle(sender, text, say))
    return out


def make(api):
    return Concierge(api, "https://rally.example", ["u_kevin"], timeout_s=5, poll_s=0)


def test_asks_the_missing_question_then_replies_in_three_messages():
    api = FakeAPI()
    c = make(api)
    first = chat(c, "asi1", "Scuba in Monterey next month under $300, I'm Open Water.")
    assert first == ["How many people at most, including you? (for example 4, 5, 6)"]
    replies = chat(c, "asi1", "5 of us")
    assert ("patch", {"groupMax": 5}) in api.calls
    assert len(replies) == 3
    assert replies[0].startswith("Here's what I understood: Scuba diving, near Monterey, CA, Nov 1–Nov 30, "
                                 "up to $300 per person, group of up to 5, Open Water certified")
    assert "Ana, Kai" in replies[1] and "Theo (Budget $80 is below" in replies[1]
    assert "plan v4 in 4 rounds" in replies[2] and "Point Lobos" in replies[2] and "boat dive" in replies[2]
    assert "Otter Cove Dive Co., $182 per person" in replies[2]              # the binding quote's price
    assert replies[2].endswith("https://rally.example/deals/d_abc")
    # the follow-up was folded into the goal text, and the session ends after the plan
    assert api.calls[0] == ("login", "u_kevin")
    assert ("compile", "Scuba in Monterey next month under $300, I'm Open Water.. 5 of us") in api.calls
    assert "asi1" not in c.sessions


def test_no_agreement_names_the_conflict():
    c = make(FakeAPI(end_status="NO_AGREEMENT"))
    chat(c, "asi1", "Scuba in Monterey")
    replies = chat(c, "asi1", "4")
    assert "couldn't agree" in replies[-1] and "Kai needs a different date" in replies[-1]


def test_senders_keep_separate_state_and_map_to_personas_in_order():
    c = Concierge(FakeAPI(), "https://x", ["u_kevin", "u_ana"], timeout_s=5, poll_s=0)
    chat(c, "first", "Scuba in Monterey")
    chat(c, "second", "Scuba in Monterey")
    assert c.sessions["first"].persona == "u_kevin" and c.sessions["second"].persona == "u_ana"
    assert c.sessions["first"].asking == "groupMax"


def test_api_errors_become_a_chat_reply():
    from concierge import ApiFailure

    class Broken(FakeAPI):
        async def compile(self, persona, text):
            raise ApiFailure("Tell HuddleUp what you want to do. (EMPTY_GOAL)")
    replies = chat(make(Broken()), "asi1", "hm")
    assert replies == ["HuddleUp couldn't do that: Tell HuddleUp what you want to do. (EMPTY_GOAL). "
                       "Try rephrasing, or say 'start over'."]


def test_parse_answer():
    assert parse_answer("groupMax", "we're 5") == {"groupMax": 5}
    assert parse_answer("groupMax", "about 20") == {}
    assert parse_answer("budgetMax", "$250 tops") == {"budgetMax": 250.0}
    assert parse_answer("certification", "I'm Advanced Open Water") == {"certification": "advanced"}
    assert parse_answer("dates", "mid November") == {}


def test_reset_each_goal_resets_once_per_new_goal_not_on_follow_ups():
    api = FakeAPI()
    c = Concierge(api, "https://x", ["u_kevin"], timeout_s=5, poll_s=0, reset_each_goal=True)
    chat(c, "asi1", "Scuba in Monterey")
    chat(c, "asi1", "5")
    assert api.calls.count(("reset",)) == 1
