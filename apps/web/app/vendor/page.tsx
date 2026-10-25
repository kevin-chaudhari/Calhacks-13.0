"use client";

import Link from "next/link";
import { Bot, ChevronRight, MessageSquare, Settings2 } from "lucide-react";
import { useState } from "react";
import { money, termValue, orderedTerms } from "@/lib/format";
import { usePersona, useVendorApi } from "@/lib/persona";
import type { VendorDashboard } from "@/lib/types";
import { useVendorDashboard } from "@/lib/useVendor";
import { ButtonLink, Callout, Card, CardHeader, Chip, PageTitle, Skeleton } from "@/components/ui/primitives";
import { STAGE, StagePill, Stat } from "@/components/rally/vendor";

export default function VendorHome() {
  const { vendor } = usePersona();
  const vapi = useVendorApi();
  const { data, error, refresh } = useVendorDashboard<VendorDashboard>(1500);
  const [saving, setSaving] = useState(false);

  if (error && !data) return <Callout tone="danger" title="Vendor portal unavailable">{error}</Callout>;
  if (!data || !vendor)
    return (
      <div className="space-y-4">
        <Skeleton className="h-16" />
        <Skeleton className="h-64" />
      </div>
    );

  const p = data.provider;
  const reqs = [...data.requests].sort((a, b) => STAGE[a.stage].order - STAGE[b.stage].order || b.updatedAt - a.updatedAt);

  async function toggleAuto() {
    setSaving(true);
    try {
      await vapi("/v1/vendor/provider", { method: "PATCH", body: { autoQuote: !p.autoQuote } });
      refresh();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageTitle eyebrow={`Vendor portal · ${data.staff.name}, ${data.staff.title}`} title={p.name}>
        Groups that want what you offer, found and organised by their agents. Your Parley agent answers price questions
        instantly; you approve quotes, talk to the group and confirm bookings.
      </PageTitle>

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Quotes to review" value={data.stages.needs_review ?? 0} />
        <Stat label="Bookings to confirm" value={data.stages.confirm_booking ?? 0} />
        <Stat label="Quotes out" value={data.stages.quote_sent ?? 0} />
        <Stat label="People booked" value={data.peopleBooked} />
        <Stat label="Committed revenue" value={money(data.committedRevenue)} hint="Simulated ledger, no money moved" />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader title="Group requests" meta={`${reqs.length} ${reqs.length === 1 ? "group" : "groups"} contacted your agent`} />
          {reqs.length === 0 ? (
            <div className="px-5 py-12 text-center text-[13px] text-muted">
              No groups yet. When customers looking for {p.activity.replace(/_/g, " ")} start negotiating, your agent sends them
              your price sheet and the group appears here.
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {reqs.map((r) => (
                <li key={r.id}>
                  <Link href={`/vendor/requests/${r.id}`} className="flex items-center gap-4 px-5 py-3.5 hover:bg-surface-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{r.title}</span>
                        <StagePill stage={r.stage} />
                        {r.chatCount > 0 && <span className="inline-flex items-center gap-1 text-[12px] text-muted"><MessageSquare size={12} /> {r.chatCount}</span>}
                      </div>
                      <div className="num mt-0.5 truncate text-[13px] text-muted">
                        {r.groupSize} people · {orderedTerms(r.terms).map(([k, v]) => termValue(k, v)).join(" · ") || "plan not set yet"}
                      </div>
                    </div>
                    <div className="num text-right">
                      {r.pricePerPerson != null ? (
                        <><div className="font-semibold">{money(r.pricePerPerson)} pp</div><div className="text-[12px] text-muted">{money(r.total ?? 0)} total</div></>
                      ) : r.draftPricePerPerson != null ? (
                        <><div className="font-semibold text-warn">{money(r.draftPricePerPerson)} pp</div><div className="text-[12px] text-muted">draft</div></>
                      ) : (
                        <div className="text-[12px] text-muted">round {r.round}</div>
                      )}
                    </div>
                    <ChevronRight size={16} className="text-muted" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-4">
          <Card className="p-5">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-muted"><Bot size={14} /> Your Parley agent</div>
            <div className="mt-2 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-accent" />
              <span className="font-medium">Online</span>
              <Chip>{data.agent.transport}</Chip>
            </div>
            <div className="mt-1 truncate font-mono text-[11px] text-muted">{data.agent.address}</div>
            <label className="mt-4 flex items-start gap-3">
              <input type="checkbox" checked={p.autoQuote} onChange={toggleAuto} disabled={saving} className="mt-1 accent-[var(--accent)]" />
              <span>
                <span className="block text-[13px] font-medium">Send binding quotes automatically</span>
                <span className="text-[12px] text-muted">Off: your agent drafts each quote and waits for a person here to approve it.</span>
              </span>
            </label>
            <ButtonLink href="/vendor/pricing" variant="secondary" className="mt-4 w-full"><Settings2 size={14} /> Agent & pricing rules</ButtonLink>
          </Card>
          <Callout tone="neutral" title="What your agent does on its own">
            Answers price-sheet requests from the mediator, computes group-tier prices for any plan, and drafts binding quotes.
            It never confirms a booking; a person does that here.
          </Callout>
        </div>
      </div>
    </>
  );
}
