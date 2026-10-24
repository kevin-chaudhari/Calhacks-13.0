"""Canonical intent (plan section 13.2). Owner: B. Consumers: A, C, D."""

from datetime import date
from enum import Enum
from typing import Any

from pydantic import Field

from .base import RallyModel


class Shape(str, Enum):
    pair = "pair"
    group = "group"
    group_provider = "group_provider"


class Kind(str, Enum):
    hard = "hard"          # "Must have"
    prefer = "prefer"      # "Prefer"
    unknown = "unknown"    # "Needs your input"
    provider = "provider"  # "Provider decides"


class Source(str, Enum):
    stated = "stated"
    inferred = "inferred"
    default = "default"


class Money(RallyModel):
    amount: float = Field(gt=0)
    currency: str = "USD"


class Place(RallyModel):
    label: str
    lat: float | None = None
    lng: float | None = None


class Condition(RallyModel):
    key: str            # canonical term, e.g. "certification", "date", "price_per_person"
    kind: Kind
    op: str             # eq | in | gte | lte | between | near
    value: Any = None
    source: Source = Source.stated
    label: str = ""     # human sentence for the review page


class TermSpec(RallyModel):
    """A negotiable term and its public option grid."""
    key: str
    type: str           # numeric | categorical | date | boolean
    options: list[Any] = []
    label: str = ""


class MissingField(RallyModel):
    field: str
    question: str
    suggestions: list[Any] = []


class IntentDraft(RallyModel):
    activity: str
    category: str
    tags: list[str] = []
    template_id: str
    shape: Shape
    location: Place | None = None
    radius_km: float | None = None
    date_from: date | None = None
    date_to: date | None = None
    budget_max: Money | None = None
    group_min: int | None = Field(default=None, ge=1, le=8)
    group_max: int | None = Field(default=None, ge=1, le=8)
    conditions: list[Condition] = []
    negotiable_terms: list[TermSpec] = []
    missing: list[MissingField] = []
    confidence: float = Field(default=0.5, ge=0, le=1)
    limited_support: bool = False


class PrivatePrefs(RallyModel):
    """Never sent to Convex, the mediator, or any other member. Lives with the personal agent."""
    weights: dict[str, float]                     # sums to 1 over negotiable terms
    ranges: dict[str, list[Any]] = {}             # acceptable values per categorical/date term
    best: dict[str, Any] = {}                     # most-preferred value per term
    price_worst: float | None = None              # price at which price score hits 0
    reservation: float = 0.35                     # lowest acceptable score at the last round
    patience: float = 1.0                         # beta in the concession curve


class PublicIntent(RallyModel):
    """What the matcher, mediator and UI may see. No private preferences."""
    id: str
    goal_id: str
    user_id: str
    version: int = 1
    text: str
    draft: IntentDraft
    prefs_hash: str = ""
    status: str = "open"                          # open | in_deal | closed
    is_demo_persona: bool = False
    created_at: int = 0


CERT_LEVELS = ["none", "open_water", "advanced", "rescue", "divemaster"]
