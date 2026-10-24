"""uAgents wire models. They live in services/api/rally/negotiation/wire.py so the API's
mediator agent and these agents share one definition (and one schema digest)."""
from rally.negotiation.wire import (PlanSpaceWire, PrefsWire, ProposalWire, QuoteRequestWire,  # noqa: F401
                                    QuoteWire, ResponseWire)
