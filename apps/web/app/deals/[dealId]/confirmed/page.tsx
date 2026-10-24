"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { CircleCheck } from "lucide-react";
import { money, orderedTerms, TERM_LABELS, termValue, time } from "@/lib/format";
import { useDealSnapshot } from "@/lib/useDeal";
import { Avatar, Callout, Card, CardHeader, Chip, Skeleton } from "@/components/ui/primitives";
import { ProvenanceBadge } from "@/components/rally/shell";
import { CalendarAndShare, DepositStatus, NegotiationReplay, ReplacementNotes } from "@/components/rally/platform";

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
      <div className="mb-8 flex items-start gap-4">
        <CircleCheck size={36} strokeWidth={1.5} className="shrink-0 text-accent" />
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[28px] font-semibold leading-[34px] tracking-[-0.01em]">Committed</h1>
            <Chip tone="sim">{sim ? "Simulated, no money moved" : "x402 testnet deposits, Base Sepolia"}</Chip>
            {d.bookingStatus === "not_booked" ? <Chip tone="warn">Booking: waiting for the vendor</Chip> : <Chip tone="accent">Booked by {d.bookedBy}</Chip>}
          </div>
          <p className="mt-2 text-muted">
            {committed.length} people committed to plan v{d.currentProposalVersion} after {roundsUsed} negotiation round{roundsUsed === 1 ? "" : "s"}.
            {" "}{d.bookingStatus === "not_booked" ? <>Next: {quote?.providerName ?? "the provider"} confirms the booking from their vendor portal.</> : <>{quote?.providerName} confirmed the booking. See you on the water.</>}
          </p>
          <div className="mt-4"><CalendarAndShare snap={snap} /></div>
        </div>
      </div>

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
