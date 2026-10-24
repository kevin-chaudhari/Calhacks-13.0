"""uAgents wire models. Field-for-field mirrors of packages/contracts/rally_contracts/messages.py.

Terms travel as a JSON string so the uAgents schema digest stays simple and stable;
both sides decode it into the shared Pydantic contract before any logic runs.
Imports uagents, so only load this module when TRANSPORT=agentverse (or from agents/).
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
    member_id: str = ""
    intent_id: str = ""      # which of the owner's goals this deal is for
    rounds: int = 5


class ResponseWire(Model):
    msg_id: str
    deal_id: str
    proposal_version: int
    member_id: str
    kind: str
    term: str | None = None
    preferred_json: str | None = None


class PrefsWire(Model):
    """Hands a goal typed live in the app to its owner's agent. Only the API agent may send it."""
    member_id: str
    intent_id: str
    prefs_json: str


class QuoteRequestWire(Model):
    msg_id: str
    deal_id: str
    activity: str
    group_size: int
    terms_json: str = ""     # empty: price sheet; set: binding quote for these terms


class QuoteWire(Model):
    msg_id: str
    deal_id: str
    provider_id: str
    tiers_json: str
    available_dates: list[str] = []
    offers_json: str = "{}"
    price_per_person: float | None = None    # set for a binding quote request
    provenance: str = "simulated"
