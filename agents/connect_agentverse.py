"""Connect every running Rally agent to its Agentverse mailbox in one go, then print the address table.

    # .env: AGENTVERSE_API_KEY (agentverse.ai → Profile → API keys), AGENT_SEED_PREFIX (private)
    python agents/run_agents.py               # terminal 1: personal + provider agents
    python agents/concierge.py                # terminal 1b: the ASI:One concierge
    TRANSPORT=agentverse python scripts/rally.py api    # terminal 2: mediator agent inside the API
    python agents/connect_agentverse.py       # terminal 3: registers each agent, prints the README table
    python agents/connect_agentverse.py --table   # only print the table (no network)

Each agent exposes POST /connect on its local port; this sends the API key there, which is what
the Agentverse inspector's "Connect" button does, once per agent.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/contracts"), str(ROOT / "services/api")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # agent names contain "·"

from rally.negotiation import network  # noqa: E402

AGENTVERSE = "https://agentverse.ai/agents/details/{address}/profile"


def connect(spec: network.AgentSpec, token: str) -> str:
    req = urllib.request.Request(
        f"http://127.0.0.1:{spec.port}/connect",
        data=json.dumps({"user_token": token, "agent_type": "mailbox"}).encode(),
        headers={"Content-Type": "application/json", "x-uagents-address": spec.address})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
            return "ok" if body.get("success", True) else f"failed: {body}"
    except urllib.error.URLError as exc:
        return f"not reachable ({exc.reason}); is it running?"


def table(specs: list[network.AgentSpec]) -> str:
    rows = ["| Agent | Kind | Address | Agentverse |", "|---|---|---|---|"]
    rows += [f"| {s.name} | {s.kind} | `{s.address}` | [profile]({AGENTVERSE.format(address=s.address)}) |"
             for s in specs]
    return "\n".join(rows)


def main() -> int:
    specs = network.directory()
    if "--table" not in sys.argv:
        token = os.environ.get("AGENTVERSE_API_KEY", "").strip()
        if not token or token.startswith("PASTE_"):
            print("Set AGENTVERSE_API_KEY (agentverse.ai → Profile → API keys).")
            return 1
        failed = 0
        for s in specs:
            status = connect(s, token)
            failed += status != "ok"
            print(f"{status:<10} {s.name}")
        if failed:
            print(f"\n{failed} agent(s) not connected.")
    print("\n" + table(specs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
