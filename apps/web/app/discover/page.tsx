"use client";

// Find real deals: vendors for any activity near any place, with every price traced to its source.

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ExternalLink, MapPin, Phone, Search, Star, Tag } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { ago, money, UNIT_LABEL } from "@/lib/format";
import { usePersona } from "@/lib/persona";
import { Button, Callout, Card, Chip, Skeleton, cx } from "@/components/ui/primitives";

interface ListedOffer { title: string; price: number; unit: string; group_max: number | null; format: string | null; duration: string | null; evidence: string; sourceUrl: string | null }
interface Vendor {
  id: string; name: string; url: string | null; mapsLink: string | null; phone: string | null; rating: number | null; reviews: number | null;
  location: { label: string }; hours: string | null; priceLevel: string | null; listedOffers: ListedOffer[]; priced: boolean; fetchedAt: number;
}
interface Deal { title: string; link: string; source: string; price: number; snippet: string }
interface Result {
  mode: "brightdata" | "off"; activity: string; activityLabel: string; place: string; vendors: Vendor[]; deals: Deal[];
  seeded: { id: string; name: string; fromPrice: number; location: { label: string } }[]; fetchedAt: number; extractor: string; errors: string[];
}

const SUGGEST = ["surf lessons in Santa Cruz", "rock climbing in Yosemite", "hot air balloon in Napa", "pottery class in Brooklyn",
  "escape room in San Francisco", "kayaking near Stony Brook", "whale watching in Monterey", "golf in Palo Alto"];

const host = (u: string | null) => (u ? u.split("//")[1]?.split("/")[0]?.replace(/^www\./, "") ?? u : "");

function VendorCard({ v, cheapest }: { v: Vendor; cheapest: boolean }) {
  const offers = [...v.listedOffers].sort((a, b) => a.price - b.price);
  return (
    <Card className={cx(cheapest && "border-ink")}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[18px] font-semibold leading-6">{v.name}</h2>
            {cheapest && <Chip tone="buoy">Lowest listed price</Chip>}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
            {v.rating != null && (
              <span className="inline-flex items-center gap-1 text-ink"><Star size={13} className="fill-buoy text-buoy" /> {v.rating.toFixed(1)}
                {v.reviews != null && <span className="text-muted">({v.reviews.toLocaleString()})</span>}</span>
            )}
            {v.location.label && <span className="inline-flex items-center gap-1"><MapPin size={13} /> {v.location.label}</span>}
            {v.hours && <span>{v.hours}</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {v.phone && <a href={`tel:${v.phone}`} className="inline-flex h-8 items-center gap-1 rounded-[8px] border border-line px-2.5 text-[13px]"><Phone size={13} /> Call</a>}
          {v.mapsLink && <a href={v.mapsLink} target="_blank" rel="noreferrer" className="inline-flex h-8 items-center gap-1 rounded-[8px] border border-line px-2.5 text-[13px]"><MapPin size={13} /> Map</a>}
          {v.url && <a href={v.url} target="_blank" rel="noreferrer" className="inline-flex h-8 items-center gap-1 rounded-[8px] border border-line px-2.5 text-[13px]">{host(v.url)} <ExternalLink size={12} /></a>}
        </div>
      </div>
      {offers.length ? (
        <ul className="mt-3 divide-y divide-line border-t border-line">
          {offers.map((o, i) => (
            <li key={i} className="grid gap-1 px-5 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-4">
              <div className="min-w-0">
                <div className="font-medium">{o.title}</div>
                <blockquote className="mt-1 border-l-2 border-buoy pl-2 text-[13px] leading-5 text-ink/80">
                  &ldquo;{o.evidence}&rdquo;{" "}
                  {o.sourceUrl && <a href={o.sourceUrl} target="_blank" rel="noreferrer" className="whitespace-nowrap text-muted underline">{host(o.sourceUrl)}</a>}
                </blockquote>
              </div>
              <div className="text-left sm:text-right">
                <div className="num display text-[22px] font-semibold leading-7">{money(o.price)}</div>
                <div className="text-[12px] text-muted">{UNIT_LABEL[o.unit] ?? o.unit}{o.group_max ? `, up to ${o.group_max}` : ""}</div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-3 border-t border-line px-5 py-3 text-[13px] text-muted">
          No price on their website. {v.phone ? "Call to ask, or" : "You can"} still add them to a plan; your agent asks for a quote.
        </div>
      )}
    </Card>
  );
}

function Discover() {
  const router = useRouter();
  const params = useSearchParams();
  const { me } = usePersona();
  const q0 = params.get("q") ?? "";
  const [q, setQ] = useState(q0);
  const [res, setRes] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!me || !q0) return;
    let alive = true;
    setBusy(true);
    setErr(null);
    setRes(null);
    api<Result>(`/v1/discover?q=${encodeURIComponent(q0)}`)
      .then((r) => alive && setRes(r))
      .catch((e) => alive && setErr(e instanceof ApiError ? e.message : "Search failed."))
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
  }, [q0, me]);

  const go = (text: string) => router.push(`/discover?q=${encodeURIComponent(text)}`);
  const priced = res?.vendors.filter((v) => v.priced) ?? [];
  const cheapestId = priced.length ? priced.reduce((a, b) => (Math.min(...a.listedOffers.map((o) => o.price)) <= Math.min(...b.listedOffers.map((o) => o.price)) ? a : b)).id : null;

  return (
    <>
      <h1 className="text-[34px] font-semibold leading-[40px] tracking-[-0.025em]">Find real deals</h1>
      <p className="mt-1 max-w-[62ch] text-muted">Any activity, anywhere. HuddleUp searches the web, reads each vendor&apos;s own site and shows only prices it can quote back to you.</p>
      <form onSubmit={(e) => (e.preventDefault(), q.trim() && go(q.trim()))} className="mt-6 flex max-w-2xl gap-2">
        <label htmlFor="q" className="sr-only">What and where</label>
        <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="surf lessons in Santa Cruz"
          className="h-12 flex-1 rounded-[12px] border border-line bg-surface px-4 text-[16px]" />
        <Button className="h-12 px-5" type="submit" disabled={!q.trim() || busy}><Search size={16} /> {busy ? "Searching…" : "Search"}</Button>
      </form>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {SUGGEST.map((s) => (
          <button key={s} onClick={() => (setQ(s), go(s))} className="rounded-full border border-line bg-surface px-3 py-1 text-[13px] text-muted hover:border-ink hover:text-ink">{s}</button>
        ))}
      </div>

      <div className="mt-8">
        {err && <Callout tone="danger" title="Couldn't search">{err}</Callout>}
        {busy && (
          <div className="space-y-3">
            <p className="text-[14px] text-muted">Searching the web and reading vendors&apos; price pages. The first search for a place takes up to a minute; after that it&apos;s instant.</p>
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-40" />)}
          </div>
        )}
        {res && (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-[22px] font-semibold">{res.activityLabel} near {res.place}</h2>
                {res.mode === "brightdata" && (
                  <span className="text-[12px] text-muted">
                    {res.vendors.length} vendors, {priced.length} with prices · read {ago(res.fetchedAt)} · Bright Data{res.extractor === "gemini" ? " + Gemini" : ""}
                  </span>
                )}
              </div>
              {res.mode === "off" && (
                <Callout tone="neutral" title="Live search is off">
                  Add your Bright Data key and SERP zone in <code>.env</code> (see docs/brightdata.md) to search real vendors. Demo shops for this activity are listed on the right if there are any.
                </Callout>
              )}
              {res.mode === "brightdata" && res.vendors.length === 0 && (
                <Callout tone="neutral" title="No vendors found">Try a nearby town or a more common name for the activity.</Callout>
              )}
              {res.vendors.map((v) => <VendorCard key={v.id} v={v} cheapest={v.id === cheapestId} />)}
              {res.errors.length > 0 && <p className="text-[12px] text-muted">{res.errors.length} vendor site{res.errors.length > 1 ? "s" : ""} couldn&apos;t be read and {res.errors.length > 1 ? "are" : "is"} shown without prices.</p>}
            </div>
            <aside className="space-y-4">
              <Card className="p-5">
                <div className="display text-[18px] font-semibold">Plan it with your agent</div>
                <p className="mt-1 text-[13px] text-muted">Your agent finds people who want the same trip, or goes solo, and negotiates using these prices.</p>
                <Link href={`/?q=${encodeURIComponent(q0)}`} className="mt-3 inline-flex h-10 w-full items-center justify-center rounded-[8px] bg-ink text-[13px] font-medium text-bg">Plan this trip</Link>
                <Link href={`/explore?activity=${res.activity}`} className="mt-2 block text-center text-[13px] text-muted underline">See who else wants to go</Link>
              </Card>
              {res.deals.length > 0 && (
                <div>
                  <h3 className="mb-2 flex items-center gap-1.5 text-[15px] font-semibold"><Tag size={14} /> Deals on the web</h3>
                  <ul className="space-y-2">
                    {res.deals.map((d) => (
                      <li key={d.link}>
                        <a href={d.link} target="_blank" rel="noreferrer" className="block rounded-[12px] border border-line bg-surface p-3 hover:border-ink">
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="num font-semibold">{money(d.price)}</span>
                            <span className="text-[12px] text-muted">{d.source}</span>
                          </div>
                          <div className="mt-0.5 line-clamp-2 text-[13px]">{d.title}</div>
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {res.seeded.length > 0 && (
                <div>
                  <h3 className="mb-2 text-[15px] font-semibold">HuddleUp demo shops</h3>
                  <ul className="space-y-2">
                    {res.seeded.map((s) => (
                      <li key={s.id} className="rounded-[12px] border border-line bg-surface p-3 text-[13px]">
                        <div className="font-medium">{s.name}</div>
                        <div className="text-muted">from {money(s.fromPrice)} · simulated prices</div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>
    </>
  );
}

export default function DiscoverPage() {
  return (
    <Suspense fallback={<Skeleton className="h-40" />}>
      <Discover />
    </Suspense>
  );
}
