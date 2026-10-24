"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Check } from "lucide-react";
import { money, termValue, time } from "@/lib/format";
import { useDealSnapshot } from "@/lib/useDeal";
import { Callout, Card, Chip, PageTitle, Skeleton, cx } from "@/components/ui/primitives";
import { ProvenanceBadge } from "@/components/rally/shell";

export default function Providers() {
  const { dealId } = useParams<{ dealId: string }>();
  const { snap, error } = useDealSnapshot(dealId);
  if (error && !snap) return <Callout tone="danger" title="Can't load quotes">{error}</Callout>;
  if (!snap) return <Skeleton className="h-96" />;
  const quotes = snap.quotes;
  const chosen = quotes.find((q) => q.id === snap.deal.chosenQuoteId);
  const plan = snap.proposals[snap.proposals.length - 1];
  const size = chosen?.groupSize ?? snap.members.filter((m) => m.state === "joined").length;

  return (
    <>
      <PageTitle eyebrow={<Link href={`/deals/${dealId}`} className="hover:text-ink">← Group room</Link>} title="Provider comparison">
        Quotes for the plan your group agreed. Savings are only shown against the same provider&apos;s single-person price for the same plan.
      </PageTitle>
      {quotes.length === 0 && <Callout tone="neutral" title="No quotes yet">Quotes are requested once every agent accepts a plan.</Callout>}
      {chosen && plan && (
        <div className="mb-5 rounded-[10px] border border-accent bg-accent-soft px-5 py-3 text-[13px]">
          <span className="font-semibold text-accent">Selected: {chosen.providerName}.</span>{" "}
          Lowest per-person price for {termValue("dive_type", plan.terms.dive_type)} at {String(plan.terms.site)} on {termValue("date", plan.terms.date)}
          {plan.terms.gear_included ? " with gear included" : ""}.
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {quotes.map((q) => {
          const isChosen = q.id === chosen?.id;
          const expired = q.expiresAt < Date.now();
          const saving = q.soloPricePerPerson - q.pricePerPerson;
          return (
            <Card key={q.id} className={cx("p-5", isChosen && "border-accent", (!q.available || expired) && "opacity-60")}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-[17px] font-semibold">
                    {q.providerName}
                    {isChosen && <Chip tone="accent"><Check size={12} /> Selected</Chip>}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <ProvenanceBadge kind={q.provenance} />
                    <Chip>{q.binding ? "Agent quote (binding)" : q.available ? "Price sheet" : "Unavailable"}</Chip>
                    {expired && <Chip tone="danger">Expired</Chip>}
                  </div>
                </div>
                {q.available && (
                  <div className="text-right">
                    <div className="num text-[28px] font-semibold leading-[34px]">{money(q.pricePerPerson)}</div>
                    <div className="num text-[12px] text-muted">per person · {money(q.total)} for {q.groupSize}</div>
                  </div>
                )}
              </div>
              {q.available && saving > 0 && (
                <div className="num mt-3 text-[13px]">
                  <span className="font-medium text-accent">{money(saving)} less per person</span>{" "}
                  <span className="text-muted">than this shop&apos;s solo price ({money(q.soloPricePerPerson)}) for the same plan.</span>
                </div>
              )}
              <table className="num mt-4 w-full text-[13px]">
                <caption className="sr-only">Group-size price tiers</caption>
                <thead>
                  <tr className="text-left text-muted"><th className="pb-1 font-normal">Group size</th><th className="pb-1 font-normal">Base price pp</th></tr>
                </thead>
                <tbody>
                  {(q.tiers as { min: number; max: number; pricePerPerson: number }[]).map((t) => (
                    <tr key={t.min} className={cx("border-t border-line", t.min <= size && size <= t.max && "font-semibold text-accent")}>
                      <td className="py-1">{t.min === t.max ? t.min : `${t.min}–${t.max}`}</td>
                      <td className="py-1">{money(t.pricePerPerson)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {q.includes.map((i) => <Chip key={i}>{i}</Chip>)}
              </div>
              <div className="mt-3 font-mono text-[11px] text-muted">
                verified {time(q.lastVerifiedAt)} · expires {time(q.expiresAt)}
                {q.sourceUrl && <> · <a className="underline" href={q.sourceUrl}>source</a></>}
              </div>
            </Card>
          );
        })}
      </div>
      <p className="mt-6 text-[12px] text-muted">
        Providers in this demo are fictional, with fixture price tables. A quote is never a reservation; the booking is made with the provider after everyone commits.
      </p>
    </>
  );
}
