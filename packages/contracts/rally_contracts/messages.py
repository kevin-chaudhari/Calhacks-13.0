"""Agent protocol messages (plan section 15.4). Owner: A.

These are plain Pydantic models so the in-process simulator, the uAgents
transport and the tests all share one definition. agents/ wraps them in
uagents.Model subclasses with identical fields.
"""

from typing import Literal

from .base import RallyModel

TermValue = str | int | float | bool


class ProposalMsg(RallyModel):
    msg_id: str
    deal_id: str
    proposal_version: int
    round: int
    terms: dict[str, TermValue]
    provider_id: str
    price_per_person: float
    currency: str = "USD"
    respond_by: int                      # epoch ms


ResponseKind = Literal["accept", "change_request", "reject_hard", "withdraw"]


class ResponseMsg(RallyModel):
    msg_id: str
    deal_id: str
    proposal_version: int
    member_id: str
    kind: ResponseKind
    term: str | None = None              # the one term a member reveals
    preferred: TermValue | None = None   # a public option, never a weight


class Tier(RallyModel):
    min: int
    max: int
    price_per_person: float
    includes: list[str] = []


class QuoteRequestMsg(RallyModel):
    msg_id: str
    deal_id: str
    activity: str
    date_from: str
    date_to: str
    group_size: int
    options: dict[str, list[TermValue]] = {}


class QuoteMsg(RallyModel):
    msg_id: str
    deal_id: str
    provider_id: str
    tiers: list[Tier]
    available_dates: list[str] = []
    sites: list[str] = []
    dive_types: list[str] = []
    gear_rental_per_person: float = 0.0
    expires_at: int
    terms_url: str | None = None
    provenance: Literal["live", "cached", "simulated"] = "simulated"


class FinalAgreementMsg(RallyModel):
    msg_id: str
    deal_id: str
    proposal_version: int
    quote_id: str
    status: Literal["agreed", "confirmed", "cancelled"]
