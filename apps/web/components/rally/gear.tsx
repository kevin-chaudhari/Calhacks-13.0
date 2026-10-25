"use client";

// "What you'll bring": the gear a member needs for the current plan, with real store prices from
// Bright Data (Google Shopping via the SERP API, and Walmart via the Web Scraper API) when enabled.
// Without credentials it shows typical prices, labelled as such.

import { ChevronDown, ExternalLink, ShoppingBag } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { money } from "@/lib/format";
import { Card, CardHeader, Chip, Skeleton, cx } from "@/components/ui/primitives";

interface Offer { title: string; price: number; shop: string | null; link: string; rating: number | null; source: string }
interface Item {
  key: string; label: string; why: string | null; status: "needed" | "maybe"; optional: boolean;
  offers: Offer[]; price: number | null; median: number | null; provenance: "live" | "estimate";
  searchUrl: string; error: string | null;
}
interface Rental { term: string; providerId: string; providerName: string; pricePerPerson: number; chosen: boolean; includedInPlan: boolean }
export interface GearList {
  activity: string; mode: "brightdata" | "estimate"; items: Item[]; totalRequired: number;
  liveCount: number; fetchedAt: number; rentals?: Rental[]; planVersion?: number;
}

const SOURCE: Record<string, string> = { google_shopping: "Google Shopping", walmart: "Walmart" };

function ago(ms: number) {
  const s = Math.max(0, Math.round((Date.now() - ms) / 1000));
  return s < 60 ? "just now" : s < 3600 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`;
}

function ItemRow({ item }: { item: Item }) {
  const [open, setOpen] = useState(false);
  const best = item.offers[0];
  const live = item.provenance === "live";
  return (
    <li className="px-5 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium">{item.label}</span>
            {item.optional && <Chip>optional</Chip>}
            {item.status === "maybe" && <Chip tone="warn" title="The group hasn't decided whether the shop provides this yet">if not rented</Chip>}
          </div>
          {item.why && <div className="text-[12px] text-muted">{item.why}</div>}
          {live && best ? (
            <a href={best.link} target="_blank" rel="noreferrer" className="mt-0.5 inline-flex max-w-full items-center gap-1 text-[12px] text-muted hover:text-ink">
              <span className="truncate">{best.title}</span>{best.shop && <span className="shrink-0">· {best.shop}</span>}
              <ExternalLink size={11} className="shrink-0" />
            </a>
          ) : (
            <a href={item.searchUrl} target="_blank" rel="noreferrer" className="mt-0.5 inline-flex items-center gap-1 text-[12px] text-muted underline">
              compare prices <ExternalLink size={11} />
            </a>
          )}
        </div>
        <div className="shrink-0 text-right">
          {item.price != null ? (
            <div className={cx("num font-semibold", !live && "text-muted")}>{live ? "" : "~"}{money(item.price)}</div>
          ) : (
            <div className="text-[12px] text-muted">no price</div>
          )}
          <div className="text-[11px] text-muted">{live ? "lowest found" : "typical"}</div>
          {live && item.offers.length > 1 && (
            <button onClick={() => setOpen(!open)} className="mt-0.5 inline-flex items-center gap-0.5 text-[11px] text-accent" aria-expanded={open}>
              {item.offers.length - 1} more <ChevronDown size={11} className={cx("transition-transform", open && "rotate-180")} />
            </button>
          )}
        </div>
      </div>
      {open && (
        <ul className="mt-2 space-y-1 border-l-2 border-line pl-3">
          {item.offers.slice(1).map((o) => (
            <li key={o.link} className="flex items-center justify-between gap-3 text-[12px]">
              <a href={o.link} target="_blank" rel="noreferrer" className="min-w-0 truncate text-muted hover:text-ink">
                {o.title}{o.shop && ` · ${o.shop}`}
              </a>
              <span className="num shrink-0">{money(o.price)}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function GearView({ gear }: { gear: GearList }) {
  const live = gear.liveCount > 0;
  const rentals = gear.rentals ?? [];
  const included = rentals.some((r) => r.includedInPlan);
  const required = gear.items.filter((i) => i.status === "needed");
  const maybe = gear.items.filter((i) => i.status === "maybe");
  const sources = Array.from(new Set(gear.items.flatMap((i) => i.offers.map((o) => SOURCE[o.source] ?? o.source))));
  const paidRental = rentals.filter((r) => r.pricePerPerson > 0).sort((a, b) => a.pricePerPerson - b.pricePerPerson)[0];
  const freeRental = rentals.find((r) => r.pricePerPerson === 0);
  const needsGear = required.some((i) => !i.optional) || maybe.length > 0;
  return (
    <Card>
      <CardHeader
        title={<span className="flex items-center gap-1.5"><ShoppingBag size={13} /> What you&apos;ll bring</span>}
        meta={live ? `Live store prices · ${ago(gear.fetchedAt)}` : "Typical prices, not live"}
        action={live
          ? <Chip tone="accent" title={`Prices from ${sources.join(" and ")}, collected by Bright Data`}>Bright Data</Chip>
          : <Chip tone="sim" title="Set GEAR_PRICES=brightdata with a Bright Data API key for live prices">Estimate</Chip>}
      />
      {included && (
        <div className="border-b border-line bg-accent-soft/60 px-5 py-2.5 text-[13px]">
          The plan includes the shop&apos;s gear, so you only need what&apos;s listed here.
        </div>
      )}
      {required.length + maybe.length === 0 ? (
        <div className="px-5 py-4 text-[13px] text-muted">Nothing to bring for this plan.</div>
      ) : (
        <ul className="divide-y divide-line">
          {[...required, ...maybe].map((i) => <ItemRow key={i.key} item={i} />)}
        </ul>
      )}
      <div className="space-y-1 border-t border-line bg-surface-2/60 px-5 py-3 text-[13px]">
        {gear.totalRequired > 0 && (
          <div className="flex justify-between gap-3">
            <span className="text-muted">Buying everything required</span>
            <span className="num font-semibold">{live ? "" : "~"}{money(gear.totalRequired)}</span>
          </div>
        )}
        {rentals.length > 0 && (
          <div className="text-[12px] text-muted">
            {rentals.map((r, idx) => (
              <span key={r.providerId + r.term}>
                {idx > 0 && " · "}
                {r.providerName}{r.chosen && " (your shop)"}: {r.pricePerPerson > 0 ? `rents it for ${money(r.pricePerPerson)} per person` : "includes it in the price"}
              </span>
            ))}
            {needsGear && !included && freeRental && (
              <span className="block pt-0.5 text-ink">{freeRental.providerName} includes the gear, which saves buying {money(gear.totalRequired)} of it.</span>
            )}
            {needsGear && !included && !freeRental && paidRental && gear.totalRequired > paidRental.pricePerPerson && (
              <span className="block pt-0.5 text-ink">
                Renting from {paidRental.providerName} costs {money(paidRental.pricePerPerson)} a trip; buying pays off after about {Math.ceil(gear.totalRequired / paidRental.pricePerPerson)} trips.
              </span>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

/** Loads the member's gear list for a deal and refreshes when the plan version changes. */
export function GearCard({ dealId, version }: { dealId: string; version: number }) {
  const [gear, setGear] = useState<GearList | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (version < 1) return;
    let alive = true;
    api<GearList>(`/v1/deals/${dealId}/gear`)
      .then((g) => alive && (setGear(g), setErr(null)))
      .catch((e) => alive && setErr(e instanceof ApiError ? e.message : "Couldn't load gear."));
    return () => {
      alive = false;
    };
  }, [dealId, version]);
  if (version < 1) return null;
  if (err) return null;                                   // gear is a helper; never block the plan
  if (!gear)
    return (
      <Card>
        <CardHeader title="What you'll bring" meta="Checking store prices…" />
        <div className="space-y-2 p-4"><Skeleton className="h-8" /><Skeleton className="h-8" /></div>
      </Card>
    );
  return <GearView gear={gear} />;
}
