"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { CalendarCheck, Check, Send, X } from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { money, orderedTerms, TERM_LABELS, termValue, time } from "@/lib/format";
import { usePersona, useVendorApi } from "@/lib/persona";
import type { VendorRequest } from "@/lib/types";
import { useVendorRequest } from "@/lib/useVendor";
import { Avatar, Button, Callout, Card, CardHeader, Chip, Skeleton } from "@/components/ui/primitives";
import { AgentConversation, WorkflowStepper } from "@/components/rally/agents";
import { ChatPanel } from "@/components/rally/chat";
import { ProvenanceBadge } from "@/components/rally/shell";
import { StagePill } from "@/components/rally/vendor";

function ReviewPanel({ req, onDone }: { req: VendorRequest; onDone: () => void }) {
  const vapi = useVendorApi();
  const draft = req.review!.draft;
  const [price, setPrice] = useState(String(draft.pricePerPerson));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"approve" | "decline" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const n = draft.groupSize;
  const p = Number(price);
  const invalid = !(p > 0) || p > draft.pricePerPerson;

  async function act(action: "approve" | "decline") {
    setBusy(action);
    setErr(null);
    try {
      await vapi(`/v1/vendor/requests/${req.deal.id}/quote`, {
        body: action === "approve"
          ? { action, pricePerPerson: p !== draft.pricePerPerson ? p : null, note: note || null }
          : { action, note: note || "not available for this plan" },
      });
      onDone();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't send.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="border-warn/50">
      <CardHeader title="Your agent drafted a quote" meta={`Plan v${req.review!.version} · waiting since ${time(req.review!.since)}`} />
      <div className="grid gap-5 p-5 sm:grid-cols-2">
        <div>
          <div className="text-[12px] text-muted">Agent&apos;s price from your rules</div>
          <div className="num text-[28px] font-semibold leading-[34px]">{money(draft.pricePerPerson)} <span className="text-[14px] font-normal text-muted">pp</span></div>
          <div className="num text-[13px] text-muted">{money(draft.total)} for {n} people · solo price {money(draft.soloPricePerPerson)}</div>
          <div className="mt-3 flex flex-wrap gap-1.5">{draft.includes.map((i) => <Chip key={i}>{i}</Chip>)}</div>
        </div>
        <div className="space-y-3">
          <label className="block">
            <span className="text-[13px] font-medium">Price per person to send</span>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-muted">$</span>
              <input type="number" inputMode="decimal" min={1} max={draft.pricePerPerson} value={price} onChange={(e) => setPrice(e.target.value)}
                className="num h-9 w-28 rounded-[6px] border border-line bg-surface px-2 text-[14px]" aria-describedby="price-help" />
              <span className="num text-[13px] text-muted">= {money((p || 0) * n)} total</span>
            </div>
            <span id="price-help" className="text-[12px] text-muted">You can offer a discount, never a higher price than the group agreed to.</span>
          </label>
          <label className="block">
            <span className="text-[13px] font-medium">Note to the group (optional)</span>
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder="e.g. Meet at the shop at 7:30"
              className="mt-1 h-9 w-full rounded-[6px] border border-line bg-surface px-2 text-[14px]" />
          </label>
        </div>
      </div>
      {err && <div className="px-5 pb-3"><Callout tone="danger" title="Not sent">{err}</Callout></div>}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">
        <Button variant="danger" onClick={() => act("decline")} disabled={!!busy}><X size={14} /> {busy === "decline" ? "Declining…" : "Decline"}</Button>
        <Button onClick={() => act("approve")} disabled={!!busy || invalid}><Send size={14} /> {busy === "approve" ? "Sending…" : "Approve and send quote"}</Button>
      </div>
    </Card>
  );
}

export default function VendorRequestPage() {
  const { dealId } = useParams<{ dealId: string }>();
  const { vendor } = usePersona();
  const vapi = useVendorApi();
  const { data: req, error, refresh } = useVendorRequest<VendorRequest>(dealId);
  const [bookErr, setBookErr] = useState<string | null>(null);
  const [booking, setBooking] = useState(false);

  if (error && !req) return <Callout tone="danger" title="Can't open this request">{error}</Callout>;
  if (!req) return <Skeleton className="h-96" />;

  const plan = req.proposals[req.proposals.length - 1];
  const quote = req.quotes.find((q) => q.binding);
  const active = req.members.filter((m) => m.state === "joined");

  async function confirmBooking() {
    setBooking(true);
    setBookErr(null);
    try {
      await vapi(`/v1/vendor/requests/${dealId}/booking`, { body: {} });
      refresh();
    } catch (e) {
      setBookErr(e instanceof ApiError ? e.message : "Couldn't confirm.");
    } finally {
      setBooking(false);
    }
  }

  async function sendChat(text: string, lang: string, viaVoice: boolean) {
    await vapi(`/v1/deals/${dealId}/messages`, { body: { text, lang, viaVoice } });
    refresh();
  }

  return (
    <>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[13px] text-muted"><Link href="/vendor" className="hover:text-ink">Requests</Link> / {req.deal.id}</div>
          <h1 className="mt-1 text-[28px] font-semibold leading-[34px] tracking-[-0.01em]">{req.deal.title}</h1>
        </div>
        <div className="flex items-center gap-2">
          <StagePill stage={req.stage} />
          <Chip>{active.length} people</Chip>
        </div>
      </div>
      <div className="mb-5"><WorkflowStepper deal={req.deal} reviewBy={req.review ? req.staff.name : null} /></div>

      <div className="mb-6 space-y-3">
        {req.stage === "needs_review" && req.review && <ReviewPanel req={req} onDone={refresh} />}
        {req.stage === "negotiating" && (
          <Callout tone="neutral" title="The group's agents are still negotiating">
            Your agent sent its price sheet. If the group picks a plan only you can serve, it will ask you for a binding quote.
          </Callout>
        )}
        {req.stage === "quote_sent" && quote && (
          <Callout tone="accent" title={`Quote sent: ${money(quote.pricePerPerson)} per person`}>
            Waiting for every member to approve plan v{quote.proposalVersion}. Expires {time(quote.expiresAt)}.
          </Callout>
        )}
        {req.stage === "confirm_booking" && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-warn/50 bg-warn-soft px-5 py-3">
            <div>
              <div className="font-semibold text-warn">Everyone approved and committed.</div>
              <div className="text-[13px] text-ink/80">Reserve the slot in your own system, then confirm here so the group knows it&apos;s booked.</div>
            </div>
            <Button onClick={confirmBooking} disabled={booking}><CalendarCheck size={15} /> {booking ? "Confirming…" : "Confirm booking"}</Button>
          </div>
        )}
        {bookErr && <Callout tone="danger" title="Not confirmed">{bookErr}</Callout>}
        {req.stage === "booked" && <Callout tone="accent" title="Booked">You confirmed this booking. The group sees it on their confirmation page.</Callout>}
        {req.stage === "lost" && <Callout tone="neutral" title="The group chose another vendor">Their agreed plan was better served elsewhere. Nothing to do.</Callout>}
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader title={plan ? `Group plan v${plan.version}` : "Group plan"} meta={plan ? (req.deal.status === "NEGOTIATING" ? "Still being negotiated" : "Agreed by every member's agent") : "Not proposed yet"} />
            {plan ? (
              <dl className="divide-y divide-line">
                {orderedTerms(plan.terms).map(([k, v]) => (
                  <div key={k} className="grid grid-cols-[140px_1fr] px-5 py-2.5">
                    <dt className="text-[13px] text-muted">{TERM_LABELS[k] ?? req.termLabels[k] ?? k}</dt>
                    <dd className="font-medium">{termValue(k, v)}</dd>
                  </div>
                ))}
                <div className="grid grid-cols-[140px_1fr] px-5 py-2.5">
                  <dt className="text-[13px] text-muted">Group</dt>
                  <dd className="flex flex-wrap items-center gap-2">
                    {active.map((m) => (
                      <span key={m.name} className="inline-flex items-center gap-1.5 text-[13px]"><Avatar initials={m.initials} size={22} /> {m.name}</span>
                    ))}
                  </dd>
                </div>
                {quote && (
                  <div className="grid grid-cols-[140px_1fr] px-5 py-2.5">
                    <dt className="text-[13px] text-muted">Your quote</dt>
                    <dd className="num flex items-center gap-2 font-medium">{money(quote.pricePerPerson)} pp · {money(quote.total)} <ProvenanceBadge kind={quote.provenance} /></dd>
                  </div>
                )}
              </dl>
            ) : (
              <div className="px-5 py-8 text-center text-[13px] text-muted">The mediator hasn&apos;t proposed a plan yet.</div>
            )}
          </Card>
          <Card>
            <CardHeader title="How the group got here" meta="Negotiation rounds run by the group's mediator" />
            <ol className="divide-y divide-line">
              {req.negotiation.map((e) => (
                <li key={e.seq} className="flex gap-3 px-5 py-2 text-[13px]">
                  <span className="num w-20 shrink-0 font-mono text-[11px] text-muted">{time(e.at)}</span>
                  <span>{e.summary}</span>
                </li>
              ))}
            </ol>
          </Card>
        </div>
        <div className="space-y-6">
          <ChatPanel
            title="Talk to the group"
            meta={req.canChat ? "Speak or type in your language; members can translate and listen." : "Chat opens when your agent sends this group a quote."}
            messages={req.chat}
            meId={vendor?.id}
            canSend={req.canChat}
            disabledReason="Chat opens when your agent quotes this group."
            onSend={sendChat}
            token={vendor?.token}
          />
          <AgentConversation messages={req.agentMessages} title="Your agent's conversation" maxHeight={420} />
        </div>
      </div>
      <p className="mt-6 flex items-center gap-1.5 text-[12px] text-muted"><Check size={12} /> You see the group&apos;s public plan and first names only. Their private preferences never leave their own agents.</p>
    </>
  );
}
