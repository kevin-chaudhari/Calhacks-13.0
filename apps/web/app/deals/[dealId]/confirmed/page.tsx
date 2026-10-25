"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CircleCheck, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { money, orderedTerms, TERM_LABELS, termValue, time } from "@/lib/format";
import type { DealSnapshot } from "@/lib/types";
import { useDealSnapshot } from "@/lib/useDeal";
import { Avatar, Button, Callout, Card, CardHeader, Chip, Skeleton } from "@/components/ui/primitives";
import { ProvenanceBadge } from "@/components/rally/shell";
import { CalendarAndShare, DepositStatus, NegotiationReplay, ReplacementNotes } from "@/components/rally/platform";

function YourMoney({ snap }: { snap: DealSnapshot }) {
  const d = snap.deal;
  const e = d.escrow;
  const quote = snap.quotes.find((q) => q.id === d.chosenQuoteId);
  const [busy, setBusy] = useState<"trip" | "report" | null>(null);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState<{ tone: "danger" | "neutral"; text: string } | null>(null);

  async function act(kind: "trip" | "report") {
    if (!e) return;
    setBusy(kind);
    setNote(null);
    try {
      if (kind === "trip") await api(`/v1/deals/${d.id}/trip-happened`, { method: "POST" });
      else {
        const r = await api<{ vendorFrozen: boolean }>(`/v1/vendors/${e.providerId}/reports`, { body: { dealId: d.id, reason } });
        setReason("");
        setNote({ tone: "neutral", text: r.vendorFrozen ? `${e.providerName} is now frozen: nobody pays it, and everyone it owed is refunded.` : "Thanks. The payout for this trip is on hold." });
      }
    } catch (err) {
      setNote({ tone: "danger", text: err instanceof ApiError ? err.message : "That didn't work." });
    } finally {
      setBusy(null);
    }
  }

  if (!e) {
    if (quote?.provenance !== "cached") return null;
    return (
      <Callout tone="warn" title="Parley can't hold this payment">
        {quote.providerName} is booked on its own website, so you pay them directly. Pay only on their site itself, never through a link someone sends you.
      </Callout>
    );
  }
  const text = {
    holding: `Parley is holding ${money(e.amount)}. ${e.providerName} is paid only after the trip${e.releaseAfter ? `, from ${e.releaseAfter} if nobody reports a problem` : ""}.`,
    disputed: `The payout to ${e.providerName} is on hold: ${e.reason ?? "a problem was reported"}.`,
    released: `Paid to ${e.providerName} after the trip.`,
    refunded: `Refunded: ${e.reason ?? "the vendor was frozen"}. ${e.providerName} was never paid.`,
  }[e.status];
  return (
    <Card className="mb-6">
      <CardHeader icon={<ShieldCheck size={16} />} title="Your money" meta={<Chip tone={e.status === "refunded" || e.status === "disputed" ? "warn" : "accent"}>{e.status}</Chip>} />
      <div className="space-y-3 px-5 py-4 text-[13px]">
        <p>{text} Parley never asks you to pay anywhere else.</p>
        {e.status === "holding" && (
          <Button variant="secondary" onClick={() => act("trip")} disabled={!!busy}>{busy === "trip" ? "Saving…" : "The trip happened"}</Button>
        )}
        {e.status !== "refunded" && (
          <div className="flex flex-col gap-2 border-t border-line pt-3">
            <label htmlFor="report" className="font-medium">Something wrong with {e.providerName}?</label>
            <textarea
              id="report" value={reason} onChange={(ev) => setReason(ev.target.value)} rows={2} maxLength={500}
              placeholder="What happened? For example: no-show, asked to pay outside Parley"
              className="rounded-[6px] border border-line bg-surface px-2 py-1.5"
            />
            <Button variant="danger" onClick={() => act("report")} disabled={!!busy || reason.trim().length < 5}>
              {busy === "report" ? "Reporting…" : "Report this vendor"}
            </Button>
          </div>
        )}
        {note && <Callout tone={note.tone} title={note.text} />}
      </div>
    </Card>
  );
}

export default function Confirmed() {
  const { dealId } = useParams<{ dealId: string }>();
  const { snap, error } = useDealSnapshot(dealId);
  if (error && !snap) return <Callout tone="danger" title="Can't load this deal">{error}</Callout>;
  if (!snap) return <Skeleton className="h-96" />;

  const d = snap.deal;
  const plan = snap.proposals[snap.proposals.length - 1];
  const quote = snap.quotes.find((q) => q.id === d.chosenQuoteId);
  const committed = snap.commitments.filter((c) => c.state === "committed");
  const removed = snap.members.filter((m) => m.state === "removed" || m.state === "withdrawn" || m.state === "unresponsive");
  const roundsUsed = snap.rounds.length;
  const sim = d.paymentsMode === "simulated";
  const names = Object.fromEntries(snap.members.map((m) => [m.userId, m]));

  if (d.status !== "COMMITTED") {
    return (
      <Callout tone="neutral" title="Not committed yet">
        This deal is {d.status.toLowerCase().replace(/_/g, " ")}. <Link className="underline" href={`/deals/${dealId}`}>Back to the group room</Link>
      </Callout>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="chart-field mb-8 flex items-start gap-4 rounded-[24px] border border-line p-6 shadow-card sm:p-8">
        <span className="inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink shadow-pop">
          <CircleCheck size={30} strokeWidth={2} />
        </span>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[30px] font-semibold leading-[36px] tracking-[-0.02em]">You&apos;re going!</h1>
            <Chip tone="sim">{sim ? "Simulated, no money moved" : "x402 testnet deposits, Base Sepolia"}</Chip>
            {quote?.provenance === "cached" ? <Chip tone="warn">Book with the shop</Chip>
              : d.bookingStatus === "not_booked" ? <Chip tone="warn">Booking: waiting for the vendor</Chip> : <Chip tone="accent">Booked by {d.bookedBy}</Chip>}
          </div>
          <p className="mt-2 text-muted">
            {committed.length} people committed to plan v{d.currentProposalVersion} after {roundsUsed} negotiation round{roundsUsed === 1 ? "" : "s"}.
            {" "}{quote?.provenance === "cached"
              ? <>{quote.providerName} isn&apos;t on Parley yet, so book on their website at the listed price; your plan, date and group size are below.</>
              : d.bookingStatus === "not_booked" ? <>Next: {quote?.providerName ?? "the provider"} confirms the booking from their vendor portal.</> : <>{quote?.providerName} confirmed the booking. Have a great trip.</>}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {quote?.provenance === "cached" && quote.sourceUrl && (
              <a href={quote.sourceUrl} target="_blank" rel="noreferrer" className="inline-flex h-9 items-center rounded-[8px] bg-ink px-4 text-[13px] font-medium text-bg">
                Book on {quote.sourceUrl.split("//")[1]?.split("/")[0]?.replace(/^www\./, "")}
              </a>
            )}
            <CalendarAndShare snap={snap} />
          </div>
        </div>
      </div>

      <YourMoney snap={snap} />

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader title="Plan" meta={quote && <span className="flex items-center gap-2">{quote.providerName} <ProvenanceBadge kind={quote.provenance} /></span>} />
          <dl className="divide-y divide-line">
            {plan && orderedTerms(plan.terms).map(([k, v]) => (
              <div key={k} className="grid grid-cols-[130px_1fr] px-5 py-2.5">
                <dt className="text-[13px] text-muted">{TERM_LABELS[k] ?? k}</dt>
                <dd className="font-medium">{termValue(k, v)}</dd>
              </div>
            ))}
          </dl>
        </Card>
        <Card>
          <CardHeader title="Per-person allocation" meta={quote && <span className="num">{money(quote.total)} total</span>} />
          <ul className="divide-y divide-line">
            {snap.commitments.map((c) => (
              <li key={c.id} className="flex items-center gap-3 px-5 py-2.5">
                <Avatar initials={names[c.userId]?.initials ?? "?"} demo={names[c.userId]?.isDemoPersona} size={28} />
                <span className="flex-1 font-medium">{names[c.userId]?.name}</span>
                <DepositStatus c={c} events={snap.events} name={names[c.userId]?.name ?? c.userId} />
                <span className="num font-semibold">{money(c.amount)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader title="Negotiation summary" />
        <div className="space-y-2 px-5 py-4 text-[13px]">
          <div className="num">{roundsUsed} rounds · {snap.proposals.length} plan versions · {snap.deal.attempt > 1 ? "one restart after a removal" : "no restarts"}</div>
          <ReplacementNotes snap={snap} />
          {removed.map((m) => (
            <div key={m.userId} className="text-muted">{m.name}: {m.removedReason ?? m.state}</div>
          ))}
          {quote && quote.soloPricePerPerson > quote.pricePerPerson && (
            <div className="num">
              Group price {money(quote.pricePerPerson)} vs {quote.providerName}&apos;s solo price {money(quote.soloPricePerPerson)} for the same plan (simulated quotes).
            </div>
          )}
        </div>
      </Card>

      <div className="mt-6"><NegotiationReplay snap={snap} /></div>

      <Card className="mt-6">
        <CardHeader title="Audit timeline" meta={`${snap.events.length} events, append-only`} />
        <ol className="max-h-[360px] divide-y divide-line overflow-y-auto">
          {snap.events.map((e) => (
            <li key={e.seq} className="grid grid-cols-[48px_86px_1fr] gap-2 px-5 py-2 text-[13px]">
              <span className="num font-mono text-muted">#{e.seq}</span>
              <span className="num font-mono text-[12px] text-muted">{time(e.at)}</span>
              <span>{e.summary}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
