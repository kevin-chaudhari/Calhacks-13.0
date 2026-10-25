"""Payment rails for member commitments (plan section 17). Owner: platform (Kevin).

PAYMENTS=simulated     the ledger records a commitment; no money moves (default).
PAYMENTS=x402_testnet  each member's commitment is backed by a real x402 payment of a small test-USDC
                       deposit on Base Sepolia:

    member clicks Commit (or auto-commit after the last approval)
      -> the member's personal agent (holding a testnet wallet) POSTs /v1/x402/deposits/{deal}/{user}
      -> HuddleUp answers 402 Payment Required with the price, asset and payTo address
      -> the agent signs an EIP-3009 transferWithAuthorization and retries with PAYMENT-SIGNATURE
      -> the x402 facilitator verifies, the handler checks a commitment is actually pending,
         the facilitator settles on-chain, and the PAYMENT-RESPONSE header carries the tx hash
      -> the ledger row is marked committed with txRef + a Base Sepolia explorer link

Facts that shape the UI copy (x402 docs, verified Oct 2026): settlement is a plain transfer, not
escrow; a refund is a separate transfer the payTo wallet must send. Mainnet networks are refused at
startup. A human click is the only authorization: agents never pay on their own.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

    from .core import Settings

log = logging.getLogger("rally.payments")

TESTNETS = {"base-sepolia": "eip155:84532"}
REFUSED = {"base", "eip155:8453", "ethereum", "eip155:1", "polygon", "eip155:137", "avalanche", "eip155:43114"}
EXPLORERS = {"eip155:84532": "https://sepolia.basescan.org/tx/"}
DEPOSIT_ROUTE = "/v1/x402/deposits"


class PaymentError(Exception):
    pass


@dataclass
class CommitResult:
    tx_ref: str
    explorer_url: str | None = None
    network: str | None = None
    payer: str | None = None


class SimulatedRail:
    mode = "simulated"
    label = "Simulated, no money moved"

    async def commit(self, deal_id: str, user_id: str) -> CommitResult:
        return CommitResult(tx_ref=f"sim_{uuid.uuid4().hex[:12]}")

    def install(self, app: "FastAPI", rally: Any) -> None:  # nothing to mount
        return None

    def status(self) -> dict:
        return {"mode": self.mode}


class X402TestnetRail:
    """Real x402 over HTTP: server middleware on our own deposit route + a paying client per persona."""

    mode = "x402_testnet"

    def __init__(self, settings: "Settings", facilitator: Any = None, transport: Any = None):
        from x402 import x402ResourceServer
        from x402.http import FacilitatorConfig, HTTPFacilitatorClient
        from x402.mechanisms.evm.exact import register_exact_evm_server

        net = settings.x402_network.strip().lower()
        if net in REFUSED or net not in TESTNETS:
            raise RuntimeError(f"X402_NETWORK={settings.x402_network!r} refused: testnet only "
                               f"({', '.join(TESTNETS)}).")
        if not settings.x402_pay_to:
            raise RuntimeError("PAYMENTS=x402_testnet needs X402_PAY_TO (HuddleUp's testnet receiving address).")
        self.network_name = net
        self.network = TESTNETS[net]
        self.pay_to = settings.x402_pay_to
        self.price_usd = settings.x402_deposit_usd
        self.base_url = settings.api_self_url
        self.transport = transport                      # tests: httpx.ASGITransport(app)
        try:
            self.keys: dict[str, str] = json.loads(settings.x402_payer_keys or "{}")
        except ValueError as exc:
            raise RuntimeError("X402_PAYER_KEYS must be JSON: {\"u_kevin\": \"0x…\"}") from exc
        self.facilitator = facilitator or HTTPFacilitatorClient(FacilitatorConfig(url=settings.x402_facilitator_url))
        self.server = x402ResourceServer(self.facilitator)
        register_exact_evm_server(self.server, self.network)
        self.label = f"Testnet deposit, {self.price_usd} test USDC on Base Sepolia"
        self.settled = 0
        self.failures = 0

    # -------------------------------------------------------------- server side

    def routes(self) -> dict:
        return {f"POST {DEPOSIT_ROUTE}/*": {
            "accepts": {"scheme": "exact", "payTo": self.pay_to, "price": f"${self.price_usd}",
                        "network": self.network},
            "description": "HuddleUp group-trip deposit (testnet)",
        }}

    def install(self, app: "FastAPI", rally: Any) -> None:
        from x402.http.middleware.fastapi import PaymentMiddlewareASGI

        app.add_middleware(PaymentMiddlewareASGI, routes=self.routes(), server=self.server)

        from fastapi.responses import JSONResponse

        from .core import ApiError

        @app.post(DEPOSIT_ROUTE + "/{deal_id}/{user_id}")
        async def x402_deposit(deal_id: str, user_id: str):
            # Runs only after the facilitator verified the payment; a non-2xx here cancels settlement,
            # so money moves only for a commitment that is actually pending.
            try:
                return rally.deposit_check(deal_id, user_id)
            except ApiError as err:
                return JSONResponse(err.body(), status_code=err.status)

    # -------------------------------------------------------------- client side

    def payer_address(self, user_id: str) -> str | None:
        key = self.keys.get(user_id)
        if not key:
            return None
        from eth_account import Account
        return Account.from_key(key).address

    async def commit(self, deal_id: str, user_id: str) -> CommitResult:
        import httpx
        from eth_account import Account
        from x402 import x402Client
        from x402.http.clients.httpx import x402AsyncTransport
        from x402.http.utils import decode_payment_response_header
        from x402.mechanisms.evm.exact import register_exact_evm_client
        from x402.mechanisms.evm.signers import EthAccountSigner

        key = self.keys.get(user_id)
        if not key:
            self.failures += 1
            raise PaymentError(f"No testnet wallet configured for {user_id} (X402_PAYER_KEYS).")
        client = x402Client()
        register_exact_evm_client(client, EthAccountSigner(Account.from_key(key)), networks=self.network)
        transport = x402AsyncTransport(client, transport=self.transport)
        async with httpx.AsyncClient(transport=transport, base_url=self.base_url, timeout=90) as http:
            resp = await http.post(f"{DEPOSIT_ROUTE}/{deal_id}/{user_id}")
        header = resp.headers.get("payment-response")
        if resp.status_code != 200 or not header:
            self.failures += 1
            detail = resp.text[:200] if resp.status_code != 200 else "no settlement header"
            raise PaymentError(f"x402 deposit failed ({resp.status_code}): {detail}")
        settle = decode_payment_response_header(header)
        if not settle.success:
            self.failures += 1
            raise PaymentError(f"x402 settlement failed: {settle.error_message or settle.error_reason}")
        self.settled += 1
        return CommitResult(tx_ref=settle.transaction, network=self.network_name, payer=settle.payer,
                            explorer_url=EXPLORERS.get(self.network, "") + settle.transaction)

    def status(self) -> dict:
        return {"mode": self.mode, "network": self.network_name, "payTo": self.pay_to,
                "depositUsd": self.price_usd, "wallets": sorted(self.keys), "settled": self.settled,
                "failures": self.failures}


def make_rail(settings: "Settings"):
    return X402TestnetRail(settings) if settings.payments == "x402_testnet" else SimulatedRail()
