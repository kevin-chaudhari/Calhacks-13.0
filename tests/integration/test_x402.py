"""x402 testnet deposits, end to end over real HTTP 402 with real EIP-3009 signatures.

Only the facilitator is stood in (it would settle on Base Sepolia over the network): FakeFacilitator
checks what a facilitator checks first (payer, payTo, amount, asset, network) and returns a tx hash.
"""
import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from rally.core import Settings
from rally.payments import X402TestnetRail
from rally.service import Rally
from rally.store import MemoryStore

pytest.importorskip("x402")                      # pip install "x402[fastapi,httpx,evm]==2.24.0"
from eth_account import Account  # noqa: E402
from x402.schemas import SettleResponse, SupportedKind, SupportedResponse, VerifyResponse  # noqa: E402

NET = "eip155:84532"
BASE_SEPOLIA_USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
GOAL = "I want to go scuba diving in Monterey next month for under $300. I am Open Water certified."
MEMBERS = ["u_kevin", "u_ana", "u_ravi", "u_maya", "u_kai"]


class FakeFacilitator:
    def __init__(self, pay_to):
        self.pay_to = pay_to
        self.settled: list[dict] = []

    def get_supported(self):
        return SupportedResponse(kinds=[SupportedKind(x402_version=2, scheme="exact", network=NET)])

    async def verify(self, payload, req):
        auth = payload.payload["authorization"]
        ok = (auth["to"] == self.pay_to == req.pay_to and auth["value"] == req.amount
              and req.asset == BASE_SEPOLIA_USDC and req.network == NET and payload.payload.get("signature"))
        return VerifyResponse(is_valid=bool(ok), payer=auth["from"], invalid_reason=None if ok else "mismatch")

    async def settle(self, payload, req):
        auth = payload.payload["authorization"]
        tx = "0x" + f"{len(self.settled) + 1:064x}"
        self.settled.append({"from": auth["from"], "to": auth["to"], "value": auth["value"], "tx": tx})
        return SettleResponse(success=True, transaction=tx, network=NET, payer=auth["from"], amount=req.amount)


@pytest.fixture()
def x402_rally(monkeypatch):
    wallets = {u: Account.create() for u in MEMBERS}
    pay_to = Account.create().address
    monkeypatch.setenv("PAYMENTS", "x402_testnet")
    monkeypatch.setenv("X402_PAY_TO", pay_to)
    monkeypatch.setenv("X402_PAYER_KEYS", json.dumps({u: a.key.hex() for u, a in wallets.items() if u != "u_kai"}))
    monkeypatch.setenv("DEMO_ROUND_DELAY_MS", "0")
    settings = Settings()
    fac = FakeFacilitator(pay_to)
    rally = Rally(settings, MemoryStore())
    rally.rail = X402TestnetRail(settings, facilitator=fac)
    app = FastAPI()
    rally.rail.install(app, rally)
    rally.rail.transport = httpx.ASGITransport(app=app)
    return rally, fac, wallets, app


async def until(pred, timeout=10.0):
    end = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < end:
        if pred():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out")


async def to_approval(rally):
    g = rally.compile_goal("u_kevin", GOAL)
    g = rally.patch_goal("u_kevin", g["id"], {"groupMax": 5})
    intent = rally.publish_intent("u_kevin", g["id"], g["suggestedPrefs"])
    m = rally.run_matches("u_kevin", intent["id"])
    deal = await rally.create_deal("u_kevin", intent["id"], m["selectedIntentIds"])
    d = deal["id"]
    await until(lambda: all(x.state == "joined" for x in rally.store.members[d]))
    await rally.negotiate("u_kevin", d)
    await until(lambda: rally.store.deals[d].vendor_review is not None)
    await rally.vendor_quote("v_marcus", d, "approve", None, None)
    return d


def test_every_member_pays_a_real_x402_deposit(x402_rally):
    rally, fac, wallets, _ = x402_rally

    async def run():
        d = await to_approval(rally)
        deal = rally.store.deals[d]
        for u in ["u_kevin", "u_ana", "u_ravi", "u_maya"]:
            await rally.approve(u, d, deal.current_proposal_version, deal.chosen_quote_id, "approve", True)
        assert rally.store.deals[d].status == "AWAITING_APPROVAL"       # nobody paid before unanimity
        assert fac.settled == []
        await rally.approve("u_kai", d, deal.current_proposal_version, deal.chosen_quote_id, "approve", True)
        await until(lambda: sum(c.state == "committed" for c in rally.store.commitments[d]) == 4
                    and not rally.paying)
        return d

    d = asyncio.run(run())
    rows = {c.user_id: c for c in rally.store.commitments[d]}
    # four wallets paid 0.01 test USDC (10000 atomic units) to Rally's address, each with its own tx
    assert sorted(s["from"] for s in fac.settled) == sorted(wallets[u].address for u in ["u_kevin", "u_ana", "u_ravi", "u_maya"])
    assert {s["value"] for s in fac.settled} == {"10000"} and {s["to"] for s in fac.settled} == {fac.pay_to}
    for u in ["u_kevin", "u_ana", "u_ravi", "u_maya"]:
        assert rows[u].method == "x402_testnet" and rows[u].network == "base-sepolia"
        assert rows[u].explorer_url == f"https://sepolia.basescan.org/tx/{rows[u].tx_ref}"
    # Kai has no testnet wallet: his deposit fails visibly and the deal waits instead of pretending
    assert rows["u_kai"].state == "pending" and rally.store.deals[d].status == "COMMITMENT_PENDING"
    assert any(e.type == "commitment.failed" and "No testnet wallet" in e.summary for e in rally.store.events[d])


def test_paid_route_refuses_a_deposit_with_nothing_pending_and_does_not_settle(x402_rally):
    rally, fac, _, app = x402_rally

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://rally") as h:
            unpaid = await h.post("/v1/x402/deposits/d_nope/u_kevin")
        assert unpaid.status_code == 402 and "payment-required" in unpaid.headers
        with pytest.raises(Exception, match="409|NO_PENDING_COMMITMENT"):
            await rally.rail.commit("d_nope", "u_kevin")

    asyncio.run(run())
    assert fac.settled == []


@pytest.mark.parametrize("network", ["base", "eip155:8453", "ethereum", "solana"])
def test_mainnet_and_unknown_networks_are_refused(monkeypatch, network):
    monkeypatch.setenv("PAYMENTS", "x402_testnet")
    monkeypatch.setenv("X402_NETWORK", network)
    monkeypatch.setenv("X402_PAY_TO", Account.create().address)
    with pytest.raises(RuntimeError, match="testnet only"):
        X402TestnetRail(Settings())
