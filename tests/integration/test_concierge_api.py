"""The concierge drives the real HuddleUp API (in-process over ASGI) from a chat goal to an agreed plan."""
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agents"))

from concierge import Concierge, RallyAPI  # noqa: E402


def test_chat_goal_reaches_a_negotiated_plan_with_a_room_link():
    from rally.main import _buckets, app
    _buckets.clear()

    async def go():
        api = RallyAPI("http://rally", transport=httpx.ASGITransport(app=app))
        await api._call("POST", "/v1/demo/reset", json={"scenario": "scuba"})
        c = Concierge(api, "https://rally.example", ["u_kevin"], timeout_s=20, poll_s=0.05)
        out = []

        async def say(t):
            out.append(t)
        await c.handle("asi1", "I want to go scuba diving in Monterey next month for under $300. "
                               "I am Open Water certified.", say)
        asked = list(out)
        await c.handle("asi1", "5", say)
        return asked, out[len(asked):], api

    asked, replies, api = asyncio.run(go())
    assert asked == ["How many people at most, including you? (for example 4, 5, 6)"]
    assert len(replies) == 3, replies
    assert "Monterey" in replies[0] and "$300" in replies[0] and "group of up to 5" in replies[0]
    assert "Found 4 people" in replies[1] and "Theo (" in replies[1]
    # Otter Cove's staff reviews quotes by hand, so the agents agree and the quote waits for Marcus
    assert "Agreed! All 5 agents accepted plan v4" in replies[2], replies[2]
    assert "Marcus" in replies[2] and "/deals/d_" in replies[2]
