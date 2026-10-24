"""Configuration flags, demo identity tokens and the single error shape."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "data" / "fixtures"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


@dataclass
class Settings:
    compiler: str = field(default_factory=lambda: _env("COMPILER", "template"))      # gemini | template
    ranker: str = field(default_factory=lambda: _env("RANKER", "local"))             # moss | local
    transport: str = field(default_factory=lambda: _env("TRANSPORT", "inproc"))      # agentverse | bureau | inproc
    providers: str = field(default_factory=lambda: _env("PROVIDERS", "seeded"))      # agents | seeded
    payments: str = field(default_factory=lambda: _env("PAYMENTS", "simulated"))     # x402_testnet | simulated
    store: str = field(default_factory=lambda: _env("STORE", "memory"))              # convex | memory
    demo_today: str = field(default_factory=lambda: _env("DEMO_TODAY", "2026-10-24"))
    round_delay_s: float = field(default_factory=lambda: float(_env("DEMO_ROUND_DELAY_MS", "1400")) / 1000)
    max_rounds: int = field(default_factory=lambda: int(_env("MAX_ROUNDS", "5")))
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL", "gemini-2.5-flash"))
    convex_url: str = field(default_factory=lambda: os.environ.get("CONVEX_URL", ""))
    convex_server_key: str = field(default_factory=lambda: os.environ.get("RALLY_SERVER_KEY", ""))
    secret: str = field(default_factory=lambda: _env("RALLY_SECRET", "dev-only-not-secret"))
    allow_demo_routes: bool = field(default_factory=lambda: _env("ALLOW_DEMO_ROUTES", "1") == "1")
    cors_origins: list[str] = field(default_factory=lambda: _env(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","))

    def __post_init__(self) -> None:
        if self.payments not in {"simulated", "x402_testnet"}:
            raise RuntimeError(f"PAYMENTS={self.payments!r} refused: only simulated or x402_testnet are allowed.")


class ApiError(Exception):
    """Rendered as {"error": {code, message, retryable, fields?}} with the given HTTP status."""

    def __init__(self, status: int, code: str, message: str, retryable: bool = False,
                 fields: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.retryable, self.fields = retryable, fields

    def body(self) -> dict:
        err = {"code": self.code, "message": self.message, "retryable": self.retryable}
        if self.fields:
            err["fields"] = self.fields
        return {"error": err}


def sign_persona(user_id: str, secret: str) -> str:
    """Demo identity token: '<userId>.<hmac>'. Labelled 'Demo identity' in the UI. Not real auth."""
    sig = hmac.new(secret.encode(), user_id.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{user_id}.{sig}"


def verify_persona(token: str, secret: str) -> str | None:
    if not token or "." not in token:
        return None
    user_id = token.rsplit(".", 1)[0]
    return user_id if hmac.compare_digest(sign_persona(user_id, secret), token) else None
