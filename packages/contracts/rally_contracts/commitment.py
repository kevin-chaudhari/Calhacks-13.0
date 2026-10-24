"""Approvals and commitments (plan section 17). Owner: C."""

from typing import Literal

from .base import RallyModel


class ApprovalRequest(RallyModel):
    proposal_version: int
    quote_id: str
    decision: Literal["approve", "decline"] = "approve"
    auto_commit: bool = True


class Approval(RallyModel):
    id: str
    deal_id: str
    user_id: str
    proposal_version: int
    quote_id: str
    decision: Literal["approve", "decline"]
    idempotency_key: str
    void: bool = False
    at: int


class Commitment(RallyModel):
    id: str
    deal_id: str
    user_id: str
    proposal_version: int
    amount: float
    currency: str = "USD"
    state: Literal["pending", "committed", "cancelled", "refunded"] = "pending"
    method: Literal["simulated", "x402_testnet"] = "simulated"
    tx_ref: str | None = None
    explorer_url: str | None = None            # x402 testnet: link to the settled transaction
    network: str | None = None                  # e.g. "base-sepolia"; None when simulated
    idempotency_key: str
    at: int
