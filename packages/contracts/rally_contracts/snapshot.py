"""What the UI reads. One shape, whether it comes from Convex or the dev API.

Built only by the API (services/api/rally/service.py::snapshot). Contains no
private preferences, weights, reservation values or scores.
"""

from typing import Any

from .base import RallyModel
from .commitment import Approval, Commitment
from typing import Literal

from .deal import Deal, DealEvent, Member, Proposal, Quote, Round

AgentKind = Literal["mediator", "personal", "provider", "staff", "system"]


class AgentMessage(RallyModel):
    """One message on the agent wire (or a provider agent's hand-off to its human staff).

    payload holds only public fields: plan terms, versions, response kinds, the one term a
    member named, prices. Never weights, reservation values or scores.
    """
    seq: int
    at: int
    from_id: str
    from_label: str
    from_kind: AgentKind
    to_id: str
    to_label: str
    to_kind: AgentKind
    type: str                    # ProposalMsg | ResponseMsg | InviteMsg | QuoteRequestMsg | QuoteMsg | ...
    summary: str
    payload: dict[str, Any] = {}
    latency_ms: float | None = None


class ChatMessage(RallyModel):
    """Human conversation between group members and the vendor's staff."""
    id: str
    seq: int
    at: int
    author_id: str
    author_name: str
    author_role: Literal["member", "vendor"]
    author_title: str = ""
    text: str
    lang: str = "en-US"
    via_voice: bool = False


class DealSnapshot(RallyModel):
    deal: Deal
    members: list[Member]
    proposals: list[Proposal]
    rounds: list[Round]
    quotes: list[Quote]
    approvals: list[Approval]
    commitments: list[Commitment]
    events: list[DealEvent]
    provenance: dict[str, Any]              # adapter modes, so badges never lie
    provider_names: dict[str, str] = {}
    agent_messages: list[AgentMessage] = []
    chat: list[ChatMessage] = []
    term_labels: dict[str, str] = {}


class Persona(RallyModel):
    id: str
    name: str
    initials: str
    is_demo_persona: bool
    is_teammate: bool = False
    home_area: str = ""
    role: Literal["customer", "vendor"] = "customer"
    provider_id: str | None = None
    title: str = ""
    agent_address: str = ""
    token: str = ""
