"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Check, Info, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { money, orderedTerms, TERM_LABELS, termValue } from "@/lib/format";
import { usePersona } from "@/lib/persona";
import { useDealSnapshot } from "@/lib/useDeal";
import { Avatar, Button, Callout, Card, CardHeader, Chip, PageTitle, Skeleton } from "@/components/ui/primitives";
import { ProvenanceBadge } from "@/components/rally/shell";

export default function Approve() {
  const { dealId } = useParams<{ dealId: string }>();
  const router = useRouter();
  const { me } = usePersona();
  const { snap, error } = useDealSnapshot(dealId);
  const [pending, setPending] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (snap?.deal.status === "COMMITTED") router.push(`/deals/${dealId}/confirmed`);
  }, [snap?.deal.status, dealId, router]);

  if (error && !snap) return <Callout tone="danger" title="Can't load this deal">{error}</Callout>;
  if (!snap) return <Skeleton className="h-96" />;

  const d = snap.deal;
  const v = d.currentProposalVersion;
  const plan = snap.proposals[snap.proposals.length - 1];
  const quote = snap.quotes.find((q) => q.id === d.chosenQuoteId);
  const active = snap.members.filter((m) => m.state === "joined");
  const approvedIds = new Set(snap.approvals.filter((a) => a.proposalVersion === v && a.decision === "approve" && !a.void).map((a) => a.userId));
  const iApproved = me ? approvedIds.has(me.id) : false;
  const iAmMember = active.some((m) => m.userId === me?.id);
  const expired = quote ? quote.expiresAt < Date.now() : false;
  const open = d.status === "AWAITING_APPROVAL";
  const disabledReason = !open
    ? `Approvals are closed (${d.status.toLowerCase().replace(/_/g, " ")}).`
    : !iAmMember ? "You're not an active member of this group."
    : expired ? "The quote expired. Refresh it from the group room."
    : iApproved ? "You approved this version."
    : null;
  const simulated = d.paymentsMode === "simulated";

  async function approve(asPersona?: string) {
    if (!quote) return;
    setPending(asPersona ?? "me");
    setErr(null);
    const body = { proposalVersion: v, quoteId: quote.id, decision: "approve", autoCommit: true };
    try {
      if (asPersona) await api(`/v1/demo/act-as/${asPersona}/approve/${dealId}`, { body });
      else await api(`/v1/deals/${dealId}/approvals`, { body });
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Approval failed.");
    } finally {
      setPending(null);
    }
  }

  async function leave() {
    try {
      await api(`/v1/deals/${dealId}/leave`, { body: { reason: "left from the approval page" } });
      router.push(`/deals/${dealId}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't leave.");
    }
  }

  return (
    <>
      <PageTitle eyebrow={<Link href={`/deals/${dealId}`} className="hover:text-ink">← Group room</Link>} title={`Approve plan v${v}`}>
        Your approval binds to this exact version and quote. If anything changes, approvals reset and everyone reviews again.
      </PageTitle>

      <div className="mb-5 flex items-start gap-3 rounded-[10px] border border-sim/30 bg-sim-soft px-5 py-3">
        <Info size={16} className="mt-0.5 shrink-0 text-sim" />
        <div className="text-[13px]">
          <span className="font-semibold text-sim">{simulated ? "Simulated commitment. No money moves." : "Testnet payment (Base Sepolia). No real funds."}</span>{" "}
          Committing records each member&apos;s share in an auditable ledger. It is not a booking; the provider still has to confirm.
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Final terms" meta={quote ? <span className="flex items-center gap-2">{quote.providerName} <ProvenanceBadge kind={quote.provenance} /></span> : undefined} />
            <dl className="divide-y divide-line">
              {plan && orderedTerms(plan.terms).map(([k, val]) => (
                <div key={k} className="grid grid-cols-[150px_1fr] px-5 py-3">
                  <dt className="text-[13px] text-muted">{TERM_LABELS[k] ?? k}</dt>
                  <dd className="font-medium">{termValue(k, val)}</dd>
                </div>
              ))}
            </dl>
          </Card>
          {quote && (
            <Card>
              <CardHeader title="Price breakdown" />
              <dl className="num divide-y divide-line">
                <div className="flex justify-between px-5 py-3"><dt className="text-muted">Per person</dt><dd className="font-semibold">{money(quote.pricePerPerson)}</dd></div>
                <div className="flex justify-between px-5 py-3"><dt className="text-muted">Group of {quote.groupSize}</dt><dd>{money(quote.total)}</dd></div>
                <div className="flex justify-between px-5 py-3"><dt className="text-muted">Fees</dt><dd>None</dd></div>
                <div className="flex justify-between px-5 py-3"><dt className="text-muted">Cancellation terms</dt><dd className="text-muted">Not provided by this provider</dd></div>
              </dl>
            </Card>
          )}
        </div>

        <div className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <Card>
            <CardHeader title="Approvals" meta={<span className="num">{approvedIds.size} of {active.length} approved</span>} />
            <ul className="divide-y divide-line">
              {active.map((m) => (
                <li key={m.userId} className="flex items-center gap-3 px-5 py-2.5">
                  <Avatar initials={m.initials} demo={m.isDemoPersona} size={28} />
                  <span className="flex-1 font-medium">{m.name}{m.userId === me?.id && <span className="ml-1 text-[12px] text-muted">(you)</span>}</span>
                  {approvedIds.has(m.userId) ? (
                    <Chip tone="accent"><Check size={12} /> Approved</Chip>
                  ) : m.isDemoPersona && open && iAmMember ? (
                    <button onClick={() => approve(m.userId)} disabled={!!pending} className="rounded-full border border-line px-2 py-0.5 text-[12px] text-muted hover:border-accent hover:text-ink">
                      {pending === m.userId ? "…" : `Approve for ${m.name}`}
                    </button>
                  ) : (
                    <Chip>Pending</Chip>
                  )}
                </li>
              ))}
            </ul>
          </Card>
          {err && <Callout tone="danger" title="Not approved">{err}</Callout>}
          <Button className="h-10 w-full" onClick={() => approve()} disabled={!!disabledReason || !!pending}>
            {pending === "me" ? "Sending…" : iApproved ? <><Check size={15} /> Approved v{v}</> : `Approve plan v${v}`}
          </Button>
          {disabledReason && !iApproved && <p className="text-[12px] text-muted">{disabledReason}</p>}
          <Button variant="danger" className="w-full" onClick={leave} disabled={!iAmMember || d.status === "COMMITTED"}>
            <LogOut size={14} /> Leave the group
          </Button>
          <p className="text-[12px] text-muted">
            Teammates approve from their own laptops. &ldquo;Approve for&rdquo; is a human click on behalf of a member who isn&apos;t at a laptop; agents never approve.
          </p>
        </div>
      </div>
    </>
  );
}
