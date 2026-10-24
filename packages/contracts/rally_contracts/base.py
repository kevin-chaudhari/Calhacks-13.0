"""Base model: snake_case in Python, camelCase on the wire and in Convex.

Every contract inherits from RallyModel so nothing is converted by hand anywhere.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class RallyModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        use_enum_values=True,
        json_schema_serialization_defaults_required=True,   # server always emits defaults
    )

    def wire(self) -> dict:
        """JSON-safe dict with camelCase keys (what the browser and Convex see)."""
        return self.model_dump(mode="json", by_alias=True)
