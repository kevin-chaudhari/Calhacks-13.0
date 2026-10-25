"""Hold-until-trip payments and fraud reports. Owner: platform.

Parley holds everything the members committed for a trip booked through it. The vendor is paid only
after the trip: once it has confirmed the booking, and either every member says the trip happened or
DISPUTE_DAYS have passed since the trip date with no report.

Only someone who booked and paid a vendor can report it. A report freezes that trip's payout. Reports
from FREEZE_AFTER different trips freeze the vendor everywhere: every payout it was still owed is
refunded to the members, its open deals are cancelled, and no agent contacts it again. One report
can't freeze a vendor, so a competitor can't take a shop down with a single fake complaint.

Vendors found on the web are booked and paid on their own website, so Parley never holds that
money; the trip page says so instead.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import TYPE_CHECKING

from rally_contracts import DealStatus, Escrow

from .core import ApiError
from .store import now_ms

if TYPE_CHECKING:
    from .service import Rally

S = DealStatus
DISPUTE_DAYS = 2           # members can report a problem this long after the trip before the vendor is paid
FREEZE_AFTER = 2           # reports from this many different trips freeze a vendor everywhere
OPEN = {S.PROVIDER_QUOTES_PENDING, S.AWAITING_APPROVAL, S.COMMITMENT_PENDING}


def _today(app: "Rally") -> date:
    return date.fromisoformat(app.s.demo_today)


def _chosen(app: "Rally", deal_id: str):
    deal = app.store.deals[deal_id]
    return next((q for q in app.store.quotes[deal_id] if q.id == deal.chosen_quote_id), None)


def _sim(app: "Rally", deal_id: str) -> str:
    return " (simulated, no money moved)" if app.store.deals[deal_id].payments_mode == "simulated" else ""


def open_escrow(app: "Rally", deal_id: str) -> None:
    """Everyone committed: Parley holds the money. Call inside the deal lock."""
    deal = app.store.deals[deal_id]
    quote = _chosen(app, deal_id)
    if quote is None or deal.escrow is not None:
        return
    if quote.provenance == "cached":
        site = (quote.source_url or "").split("//")[-1].split("/")[0] or "its website"
        app.store.append_event(deal_id, "escrow.none", "commitments",
                               f"{quote.provider_name} is booked on its own website, so Parley can't hold this "
                               f"money. Pay only on {site} itself, never through a link someone sends you")
        return
    held = round(sum(c.amount for c in app.store.commitments[deal_id] if c.state == "committed"), 2)
    props = app.store.proposals[deal_id]
    trip = props[-1].terms.get("date") if props else None
    after = (date.fromisoformat(str(trip)) + timedelta(days=DISPUTE_DAYS)).isoformat() if trip else None
    deal.escrow = Escrow(status="holding", amount=held, provider_id=quote.provider_id,
                         provider_name=quote.provider_name, trip_date=trip, release_after=after, at=now_ms())
    app.store.append_event(deal_id, "escrow.holding", "commitments",
                           f"Parley is holding ${held:.0f}{_sim(app, deal_id)}. {quote.provider_name} is paid only "
                           f"after the trip" + (f", from {after} if nobody reports a problem" if after else ""),
                           {"amount": held, "releaseAfter": after})


def _try_release(app: "Rally", deal_id: str) -> bool:
    """Pay the vendor if the trip is over and nothing is wrong. Call inside the deal lock."""
    deal = app.store.deals[deal_id]
    e = deal.escrow
    if e is None or e.status != "holding" or e.provider_id in app.frozen:
        return False
    if deal.booking_status != "confirmed_by_provider":
        return False                                    # never pay for a booking the vendor didn't confirm
    active = {m.user_id for m in app._active(deal_id)}
    window_over = e.release_after is not None and _today(app) >= date.fromisoformat(e.release_after)
    if not (window_over or (active and active <= set(e.confirmed_by))):
        return False
    e.status, e.at = "released", now_ms()
    why = "everyone said the trip happened" if not window_over else "nobody reported a problem after the trip"
    app.store.append_event(deal_id, "escrow.released", "commitments",
                           f"Paid {e.provider_name} ${e.amount:.0f}{_sim(app, deal_id)}: {why}", {"amount": e.amount})
    return True


async def release_due(app: "Rally") -> list[str]:
    """Pay out every trip whose dispute window has closed. Runs periodically and after each change."""
    paid = []
    for deal_id in [d.id for d in app.store.deals.values() if d.escrow and d.escrow.status == "holding"]:
        async with app.store.locks[deal_id]:
            if _try_release(app, deal_id):
                app.publish(deal_id)
                paid.append(deal_id)
    return paid


async def confirm_trip(app: "Rally", user_id: str, deal_id: str) -> dict:
    """A member says the trip happened. When everyone has, the vendor is paid without waiting."""
    async with app.store.locks[deal_id]:
        deal = app._deal(deal_id)
        member = app._member(deal_id, user_id)
        e = deal.escrow
        if e is None or e.status != "holding":
            raise ApiError(409, "NOT_HOLDING", "Parley isn't holding a payment for this trip.")
        if e.trip_date and _today(app) < date.fromisoformat(str(e.trip_date)):
            raise ApiError(409, "TRIP_NOT_YET", f"You can confirm the trip from {e.trip_date}.")
        if user_id not in e.confirmed_by:
            e.confirmed_by.append(user_id)
            app.store.append_event(deal_id, "trip.confirmed", user_id, f"{member.name} says the trip happened")
        _try_release(app, deal_id)
        app.publish(deal_id)
        return e.wire()


async def report_vendor(app: "Rally", user_id: str, provider_id: str, deal_id: str, reason: str) -> dict:
    reason = (reason or "").strip()
    if not 5 <= len(reason) <= 500:
        raise ApiError(422, "BAD_REASON", "Say what went wrong in 5 to 500 characters.", fields={"reason": "required"})
    async with app.store.locks[deal_id]:
        deal = app._deal(deal_id)
        member = app._member(deal_id, user_id)
        quote = _chosen(app, deal_id)
        if deal.status != S.COMMITTED or quote is None or quote.provider_id != provider_id:
            raise ApiError(409, "NOT_YOUR_VENDOR", "You can report a vendor you booked and paid on Parley.")
        mine = next((r for r in app.reports.get(provider_id, []) if r["userId"] == user_id), None)
        if mine is None:
            mine = {"id": f"r_{uuid.uuid4().hex[:8]}", "providerId": provider_id, "dealId": deal_id,
                    "userId": user_id, "reason": reason, "at": now_ms()}
            app.reports.setdefault(provider_id, []).append(mine)
            app.store.publish_row("vendor_reports", provider_id, {"reports": app.reports[provider_id]},
                                  sorted({r["userId"] for r in app.reports[provider_id]}))
            app.store.append_event(deal_id, "vendor.reported", user_id,
                                   f"{member.name} reported {quote.provider_name}: {reason}")
        e = deal.escrow
        if e is not None and e.status == "holding":
            e.status, e.reason, e.at = "disputed", f"{member.name} reported a problem", now_ms()
            app.store.append_event(deal_id, "escrow.disputed", "commitments",
                                   f"Payout to {quote.provider_name} is on hold: {member.name} reported a problem")
        app.publish(deal_id)
    trips = {r["dealId"] for r in app.reports[provider_id]}
    if len(trips) >= FREEZE_AFTER and provider_id not in app.frozen:
        await freeze_vendor(app, provider_id, f"reported by people on {len(trips)} different trips")
    return {"report": mine, "vendorFrozen": provider_id in app.frozen,
            "escrow": deal.escrow.wire() if deal.escrow else None}


def _refund_committed(app: "Rally", deal_id: str, why: str) -> None:
    for c in app.store.commitments[deal_id]:
        if c.state == "committed":
            c.state = "refunded"
            app.store.append_event(
                deal_id, "commitment.refunded", c.user_id,
                f"Refunded ${c.amount:.0f} to {app.personas[c.user_id].name} ({why})" if c.method == "simulated" else
                f"Refund owed to {app.personas[c.user_id].name} ({why}): x402 has no automatic refunds, so "
                f"Parley's testnet wallet sends it back separately")
        elif c.state == "pending":
            c.state = "cancelled"


async def freeze_vendor(app: "Rally", provider_id: str, why: str) -> None:
    """Stop all money and all contact with a vendor: refund what it was owed, cancel its open deals."""
    app.frozen[provider_id] = {"providerId": provider_id, "reason": why, "at": now_ms()}
    app.store.publish_row("vendor_reports", f"{provider_id}:frozen", app.frozen[provider_id], [])
    name = next((p["name"] for p in app.providers if p["id"] == provider_id), provider_id)
    for deal_id in list(app.store.deals):
        async with app.store.locks[deal_id]:
            deal = app.store.deals[deal_id]
            quote = _chosen(app, deal_id)
            ours = (quote is not None and quote.provider_id == provider_id) or \
                (deal.vendor_review or {}).get("providerId") == provider_id
            if not ours:
                continue
            e = deal.escrow
            if e is not None and e.status in {"holding", "disputed"}:
                e.status, e.reason, e.at = "refunded", f"{name} was frozen: {why}", now_ms()
                _refund_committed(app, deal_id, f"{name} was frozen after fraud reports")
                app.store.append_event(deal_id, "escrow.refunded", "commitments",
                                       f"{name} was frozen after fraud reports ({why}). It was never paid, "
                                       f"and everyone's money is refunded")
            elif DealStatus(deal.status) in OPEN:
                _refund_committed(app, deal_id, f"{name} was frozen after fraud reports")
                deal.vendor_review = None
                app.store.transition(deal_id, OPEN, S.CANCELLED, "mediator",
                                     f"Cancelled: {name} was frozen after fraud reports ({why}). Nothing was paid "
                                     f"to it. Start a new goal to find another vendor")
            else:
                continue
            app.publish(deal_id)


def install(rally_cls) -> None:
    for fn in (open_escrow, _try_release, release_due, confirm_trip, report_vendor, freeze_vendor):
        setattr(rally_cls, fn.__name__, fn)
