"""Activity catalog (data/fixtures/activities.json): canonical vocabulary per activity."""

from __future__ import annotations

import json
from functools import lru_cache

from .core import FIXTURES


@lru_cache(maxsize=1)
def activities() -> dict[str, dict]:
    return json.loads((FIXTURES / "activities.json").read_text(encoding="utf-8"))["activities"]


def canonical(activity: str) -> str:
    """Map synonyms (boat_dive, tandem_skydive, ...) to the catalog key; unknown activities map to themselves."""
    for key, info in activities().items():
        if activity == key or activity in info.get("synonyms", []):
            return key
    return activity


def info(activity: str) -> dict | None:
    return activities().get(canonical(activity))


def label(activity: str) -> str:
    i = info(activity)
    return i["label"] if i else activity.replace("_", " ").capitalize()
