"""What each personal agent learns about vendors across its owner's trips.

After every quote round, each vendor's price is compared with the median of the other vendors'
prices for the same plan (the market for that trip). The agent keeps one ratio per vendor per trip
and estimates the vendor's typical premium with shrinkage towards the market, so a single expensive
quote never condemns a vendor: a vendor 30% over the market is avoided after 3 trips, one 20% over
after 7, one 10% over never. A vendor is avoided only when it is also above the market on most of those
trips. Avoided vendors are never contacted again for that person's trips.

Stores public facts about vendors only (prices they quoted), never the owner's private preferences.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

MIN_TRIPS = 3             # never judge a vendor on fewer trips
PREMIUM = 0.15            # avoid when the estimated premium over the market is at least 15%
CONSISTENCY = 0.75        # ...and the vendor was above the market on at least 3 of every 4 trips
PRIOR = 2.0               # shrinkage: as if every vendor had already quoted at market price twice


class VendorMemory:
    def __init__(self, path: Path | None = None):
        self.path = path                    # None: remembered for this process only
        self.ratios: dict[str, dict[str, dict[str, float]]] = {}   # user -> vendor -> deal -> price / market
        self.names: dict[str, str] = {}
        if path:
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                self.ratios, self.names = doc.get("ratios", {}), doc.get("names", {})
            except (OSError, ValueError):
                pass

    def reset(self) -> None:
        self.ratios, self.names = {}, {}
        self._save()

    def observe(self, user_ids: list[str], deal_id: str, plans: list[list[tuple[str, str, float]]]) -> None:
        """One trip's price sheets. plans: for each plan (same terms, same group size), the
        (vendor id, name, price per person) of every vendor that can serve exactly that plan.
        A vendor's ratio for the trip is its median price / market over the plans it shares with
        others. Seeing the same trip again replaces its ratios."""
        per_vendor: dict[str, list[float]] = {}
        for quotes in plans:
            priced = [(vid, name, p) for vid, name, p in quotes if p and p > 0 and math.isfinite(p)]
            if len(priced) < 2:
                continue                    # nobody to compare against on this plan
            for vid, name, p in priced:
                market = statistics.median(q for other, _, q in priced if other != vid)
                per_vendor.setdefault(vid, []).append(p / market)
                self.names[vid] = name
        if not per_vendor:
            return
        for vid, ratios in per_vendor.items():
            for u in user_ids:
                self.ratios.setdefault(u, {}).setdefault(vid, {})[deal_id] = round(statistics.median(ratios), 4)
        self._save()

    def verdict(self, user_id: str, vendor_id: str) -> dict | None:
        ratios = list(self.ratios.get(user_id, {}).get(vendor_id, {}).values())
        if not ratios:
            return None
        n = len(ratios)
        premium = math.exp(sum(math.log(r) for r in ratios) / (n + PRIOR)) - 1
        above = sum(r > 1 for r in ratios) / n
        return {"vendorId": vendor_id, "name": self.names.get(vendor_id, vendor_id), "trips": n,
                "premium": round(premium, 3), "aboveMarketShare": round(above, 2),
                "avoid": n >= MIN_TRIPS and premium >= PREMIUM and above >= CONSISTENCY}

    def known(self, user_id: str) -> list[dict]:
        out = [self.verdict(user_id, v) for v in self.ratios.get(user_id, {})]
        return sorted((v for v in out if v), key=lambda v: (-v["avoid"], -v["premium"]))

    def avoids(self, user_id: str, vendor_id: str) -> bool:
        v = self.verdict(user_id, vendor_id)
        return bool(v and v["avoid"])

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"ratios": self.ratios, "names": self.names}), encoding="utf-8")
        tmp.replace(self.path)
