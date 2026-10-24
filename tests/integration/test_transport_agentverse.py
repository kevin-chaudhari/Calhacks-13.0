"""The scuba deal over real uAgents messages: mediator in the API, personal agents in another process.

    TRANSPORT=agentverse AGENT_NETWORK=local python -m pytest tests/integration/test_transport_agentverse.py
    TRANSPORT=agentverse python -m pytest tests/integration/test_transport_agentverse.py   # agents already
                                                                     # running with mailboxes on Agentverse

Run this file on its own: TRANSPORT is read once per process. Skipped unless TRANSPORT=agentverse.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("TRANSPORT") != "agentverse",
                                reason="set TRANSPORT=agentverse to run over the agent network")

ROOT = Path(__file__).resolve().parents[2]


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="module")
def agents():
    from rally.negotiation import network
    if network.network_mode() != "local":
        yield None                                   # mailbox: agents/run_agents.py is already running
        return
    # the child would otherwise read .env (pytest doesn't): pin it to the seeds this process derives addresses from
    env = {**os.environ, "AGENT_SEED_PREFIX": network.seed_prefix(), "AGENT_NETWORK": "local"}
    proc = subprocess.Popen([sys.executable, str(ROOT / "agents/run_agents.py")], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ports = [s.port for s in network.directory() if s.kind in {"personal", "provider"}]
    end = time.time() + 60
    while not all(_port_open(p) for p in ports):
        assert proc.poll() is None, "run_agents.py exited"
        assert time.time() < end, "agents did not start"
        time.sleep(0.3)
    yield proc
    proc.terminate()
    proc.wait(10)


@pytest.fixture()
def client(agents):
    from fastapi.testclient import TestClient

    from rally.main import app
    with TestClient(app) as c:
        c.post("/v1/demo/reset", json={"scenario": "scuba"})
        c.tokens = {p["id"]: p["token"] for p in c.get("/v1/demo/personas").json()}
        yield c


def test_scuba_reaches_v4_in_4_rounds_over_the_network(client):
    from test_api_flow import run_to_approval

    from rally.negotiation import network

    c = client
    assert c.get("/v1/health").json()["adapters"]["transport"] == "agentverse"
    deal_id, snap = run_to_approval(c)
    assert snap["deal"]["status"] == "AWAITING_APPROVAL"
    assert snap["deal"]["currentProposalVersion"] == 4
    assert len(snap["rounds"]) == 4
    assert snap["provenance"]["transport"] == "agentverse"

    specs = network.by_key()
    for m in snap["members"]:
        assert m["agentAddress"] == specs[f"personal:{m['userId']}"].address
    replies = [m for m in snap["agentMessages"] if m["type"] == "ResponseMsg"]
    assert replies and all(m["latencyMs"] is not None and m["latencyMs"] > 0 for m in replies)
    proposals = [m for m in snap["agentMessages"] if m["type"] == "ProposalMsg"]
    assert all(m["fromId"] == specs["mediator"].address for m in proposals)
