"""uAgents wire models. Field-for-field mirrors of packages/contracts/rally_contracts/messages.py.

Terms travel as a JSON string so the uAgents schema digest stays simple and stable;
both sides decode it into the shared Pydantic contract before any logic runs.
"""
from uagents import Model


class ProposalWire(Model):
    msg_id: str
    deal_id: str
    proposal_version: int
    round: int
    terms_json: str
    provider_id: str
    price_per_person: float
    currency: str
    respond_by: int


class PlanSpaceWire(Model):
    deal_id: str
    plans_json: str          # public plan space: [[terms, provider_id, price], ...]


class ResponseWire(Model):
    msg_id: str
    deal_id: str
    proposal_version: int
    member_id: str
    kind: str
    term: str | None = None
    preferred_json: str | None = None
