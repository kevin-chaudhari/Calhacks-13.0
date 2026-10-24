"""Rally's agent network: one deterministic identity, port and name per agent.

The API (mediator) and agents/run_agents.py (personal + provider agents) both build the
directory from the same fixtures and AGENT_SEED_PREFIX, so every process knows every
address without asking the network.

AGENT_NETWORK=mailbox  Agentverse mailboxes; addresses resolve through the Almanac (venue / demo).
AGENT_NETWORK=local    plain HTTP on AGENT_HOST, static resolver; no Fetch.ai account needed (tests).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ..core import FIXTURES

AGENTS_DIR = Path(__file__).resolve().parents[4] / "agents"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


DEV_PREFIX = "rally dev agents"


def seed_prefix() -> str:
    """Seeds are private keys: anyone who knows the prefix can impersonate every Rally agent."""
    return _env("AGENT_SEED_PREFIX", DEV_PREFIX)


def network_mode() -> str:
    return _env("AGENT_NETWORK", "mailbox")      # mailbox | local


def host() -> str:
    return _env("AGENT_HOST", "127.0.0.1")


def base_port() -> int:
    return int(_env("AGENT_BASE_PORT", "8100"))


@dataclass(frozen=True)
class AgentSpec:
    key: str             # "mediator", "personal:u_ana", "provider:p_kelpline", "concierge"
    kind: str            # mediator | personal | provider | concierge
    owner: str           # user id, provider id, or "" for Rally's own agents
    name: str            # Agentverse display name
    description: str
    port: int

    @property
    def seed(self) -> str:
        return f"{seed_prefix()} {self.key}"

    @property
    def address(self) -> str:
        from uagents_core.identity import Identity
        return Identity.from_seed(self.seed, 0).address

    @property
    def endpoint(self) -> str:
        return f"http://{host()}:{self.port}/submit"


def directory() -> list[AgentSpec]:
    """Every Rally agent, in a fixed order (ports follow this order)."""
    personas = json.loads((FIXTURES / "personas.json").read_text(encoding="utf-8"))["personas"]
    providers = json.loads((FIXTURES / "providers.json").read_text(encoding="utf-8"))["providers"]
    port = base_port()
    out = [AgentSpec("mediator", "mediator", "", "Rally · group mediator",
                     "Negotiates one shared plan for a group of personal agents in bounded rounds. "
                     "Never sees anyone's private preferences.", port)]
    for p in personas:
        if p["role"] != "customer":
            continue
        port += 1
        out.append(AgentSpec(f"personal:{p['id']}", "personal", p["id"], f"Rally · {p['name']}'s agent",
                             f"{p['name']}'s personal Rally agent. Holds {p['name']}'s private trip preferences "
                             "and answers the mediator's proposals with accept, one change request, or a hard no.",
                             port))
    for p in providers:
        port += 1
        out.append(AgentSpec(f"provider:{p['id']}", "provider", p["id"], f"Rally · {p['name']}",
                             f"Provider agent for {p['name']} ({p['location']['label']}). Answers group quote "
                             "requests from its price tiers.", port))
    out.append(AgentSpec("concierge", "concierge", "", "Rally concierge",
                         "Group trips: tell Rally a goal (scuba, skydiving, kayaking) and it finds people, "
                         "negotiates one shared plan with vendors and gets the group discount.", port + 1))
    return out


def by_key() -> dict[str, AgentSpec]:
    return {s.key: s for s in directory()}


def address_of(key: str) -> str:
    return by_key()[key].address


def start_in_loop(agent) -> list:
    """Run an agent inside an already-running loop (the API's) and return its tasks.

    Agent.run_async() cancels every task on the loop when it stops, which would take uvicorn
    down with it; this starts the same pieces and lets the caller cancel only the agent's own.
    """
    import asyncio

    before = asyncio.all_tasks()
    agent.setup()
    coros = []
    if not (agent._use_mailbox and not agent._rest_handlers):
        coros.append(agent.start_server())
    if agent.mailbox_client is not None:
        coros.append(agent.mailbox_client.run())
    started = [asyncio.create_task(c) for c in coros]
    return started + list(asyncio.all_tasks() - before - set(started))


def make_agent(spec: AgentSpec, loop=None):
    """A uAgents Agent for this spec, configured for AGENT_NETWORK."""
    from uagents import Agent

    readme = AGENTS_DIR / "readmes" / f"{spec.kind}.md"
    common = dict(name=spec.name, seed=spec.seed, port=spec.port, loop=loop, description=spec.description,
                  log_level=_env("AGENT_LOG_LEVEL", "WARNING"))
    if network_mode() == "local":
        from uagents.resolver import RulesBasedResolver
        rules = {s.address: s.endpoint for s in directory()}
        return Agent(**common, endpoint=None, resolve=RulesBasedResolver(rules), enable_agent_inspector=False)
    if seed_prefix() == DEV_PREFIX or seed_prefix().startswith("PASTE_"):
        raise RuntimeError("AGENT_NETWORK=mailbox needs a private AGENT_SEED_PREFIX in .env; the default is public.")
    return Agent(**common, mailbox=True, publish_agent_details=True,
                 readme_path=str(readme) if readme.exists() else None)
