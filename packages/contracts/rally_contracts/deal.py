"""Deal lifecycle, members, proposals, rounds, quotes, events (plan sections 6, 11).

Owner: A (deal + status), C (approvals, commitments, events). Consumers: D.
"""

from enum import Enum
from typing import Any, Literal

from .base import RallyModel
from .intent import Shape

Provenance = Literal["live", "cached", "simulated"]


class DealStatus(str, Enum):
    GROUP_FORMING = "GROUP_FORMING"
    NEGOTIATING = "NEGOTIATING"
    PROVIDER_QUOTES_PENDING = "PROVIDER_QUOTES_PENDING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMMITMENT_PENDING = "COMMITMENT_PENDING"
    COMMITTED = "COMMITTED"
    NO_AGREEMENT = "NO_AGREEMENT"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


ACTIVE = {
    DealStatus.GROUP_FORMING,
    DealStatus.NEGOTIATING,
    DealStatus.PROVIDER_QUOTES_PENDING,
    DealStatus.AWAITING_APPROVAL,
    DealStatus.COMMITMENT_PENDING,
}

# Allowed edges. Anything else is rejected by state.transition().
TRANSITIONS: dict[DealStatus, set[DealStatus]] = {
    DealStatus.GROUP_FORMING: {DealStatus.NEGOTIATING},
    DealStatus.NEGOTIATING: {
        DealStatus.PROVIDER_QUOTES_PENDING,
        DealStatus.AWAITING_APPROVAL,      # pair shape skips quotes
        DealStatus.NO_AGREEMENT,
    },
    DealStatus.NO_AGREEMENT: {DealStatus.NEGOTIATING},          # organizer relaxes a term
    DealStatus.PROVIDER_QUOTES_PENDING: {DealStatus.AWAITING_APPROVAL, DealStatus.NO_AGREEMENT},
    DealStatus.AWAITING_APPROVAL: {DealStatus.COMMITMENT_PENDING, DealStatus.NEGOTIATING},
    DealStatus.COMMITMENT_PENDING: {DealStatus.COMMITTED, DealStatus.NEGOTIATING},
    DealStatus.COMMITTED: set(),
    DealStatus.EXPIRED: set(),
    DealStatus.CANCELLED: set(),
    DealStatus.FAILED: set(),
}
for _s in ACTIVE:
    TRANSITIONS[_s] |= {DealStatus.EXPIRED, DealStatus.CANCELLED, DealStatus.FAILED}
TRANSITIONS[DealStatus.NO_AGREEMENT] |= {DealStatus.CANCELLED, DealStatus.EXPIRED}

MemberState = Literal["invited", "joined", "unresponsive", "withdrawn", "removed"]
AgentStatus = Literal["idle", "thinking", "accepted", "change_request", "reject_hard",
                      "unresponsive", "withdrawn"]


class Member(RallyModel):
    user_id: str
    name: str
    initials: str
    intent_id: str
    role: Literal["organizer", "member"] = "member"
    state: MemberState = "invited"
    is_demo_persona: bool = False
    agent_address: str = ""
    agent_status: AgentStatus = "idle"
    agent_term: str | None = None          # term named in the latest change request
    removed_reason: str | None = None


class Proposal(RallyModel):
    version: int
    round: int
    terms: dict[str, Any]
    provider_id: str
    price_per_person: float
    currency: str = "USD"
    rationale: list[str] = []
    feasible: bool = True
    changed: list[str] = []                # term keys changed from the previous version


class RoundResponse(RallyModel):
    member_id: str
    kind: str
    term: str | None = None


class Round(RallyModel):
    number: int
    attempt: int = 1
    proposal_version: int
    responses: list[RoundResponse] = []
    outcome: Literal["pending", "all_accept", "revised", "stalled", "timeout", "exhausted"] = "pending"
    accepted: int = 0
    active: int = 0


class Quote(RallyModel):
    id: str
    provider_id: str
    provider_name: str
    proposal_version: int
    group_size: int
    price_per_person: float
    solo_price_per_person: float           # same provider, same plan, group of 1: the only valid baseline
    total: float
    currency: str = "USD"
    includes: list[str] = []
    available: bool = True
    binding: bool = False                  # a price sheet is not a binding quote
    provenance: Provenance = "simulated"
    expires_at: int
    tiers: list[dict] = []
    source_url: str | None = None
    last_verified_at: int = 0


class DealEvent(RallyModel):
    seq: int
    type: str
    actor: str
    summary: str
    payload: dict[str, Any] = {}
    at: int


class Nudge(RallyModel):
    """A provider agent's offer: this many more people moves the group to a cheaper tier."""
    provider_id: str
    provider_name: str = ""
    extra_people: int
    current_price_per_person: float
    new_price_per_person: float
    saving_per_person: float
    candidate_user_id: str | None = None      # next eligible person from the stored matches
    candidate_name: str | None = None
    at: int = 0
    status: Literal["open", "accepted", "dismissed", "expired"] = "open"


class Replacement(RallyModel):
    """A member left and the mediator invited the next eligible person in their place."""
    left_user_id: str
    left_name: str = ""
    invited_user_id: str
    invited_name: str = ""
    at: int


class Deal(RallyModel):
    id: str
    shape: Shape
    activity: str
    title: str
    status: DealStatus
    status_version: int = 0
    current_proposal_version: int = 0
    max_rounds: int = 5
    round: int = 0
    attempt: int = 1
    group_min: int = 2
    group_max: int = 8
    deadline_at: int
    term_space: list[dict] = []
    created_by: str
    created_at: int
    booking_status: Literal["not_booked", "booked_by_human", "confirmed_by_provider"] = "not_booked"
    conflicts: list[str] = []
    chosen_quote_id: str | None = None
    payments_mode: Literal["simulated", "x402_testnet"] = "simulated"
    activity_label: str = ""
    vendor_review: dict[str, Any] | None = None   # provider agent drafted a quote; staff must approve
    booked_by: str | None = None
    nudge: Nudge | None = None                  # owner: agents (Parikshit); UI: platform (Kevin)
    replacements: list[Replacement] = []        # owner: agents (Parikshit); UI: platform (Kevin)
    negotiation_ms: int | None = None           # wall time from negotiate to agreement, for live metrics
    solo: bool = False                          # one traveller; their agent negotiates with vendor agents directly
