"use client";

import { useParams } from "next/navigation";
import { Play, QrCode } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { money } from "@/lib/format";
import { usePersona } from "@/lib/persona";
import { useDealSnapshot } from "@/lib/useDeal";
import { Button, Callout, Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { ActivityFeed, DealHeader, MemberRail, NextStepBar, PlanCard, QuoteMini, RoundTimeline } from "@/components/rally/room";
import { AgentConversation, WorkflowStepper } from "@/components/rally/agents";
import { ChatPanel } from "@/components/rally/chat";
import { cx } from "@/components/ui/primitives";
import { GearCard } from "@/components/rally/gear";
import { ExplanationCard, NegotiationReplay, NudgeCard, ReplacementNotes, SeatsPanel } from "@/components/rally/platform";

export default function GroupRoom() {
  const { dealId } = useParams<{ dealId: string }>();
  const { me } = usePersona();
  const { snap, error } = useDealSnapshot(dealId);
  const [tab, setTab] = useState<"plan" | "members" | "activity">("plan");
  const [cmdErr, setCmdErr] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [seats, setSeats] = useState(false);

  if (error && !snap) return <Callout tone="danger" title="Can't open this group">{error}</Callout>;
  if (!snap)
    return (
      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)_340px]">
        <Skeleton className="h-[420px]" />
        <Skeleton className="h-[520px]" />
        <Skeleton className="h-[420px]" />
      </div>
    );

  const providerName = (id: string) => snap.providerNames[id] ?? id;
  const joined = snap.members.filter((m) => m.state === "joined").length;
  const pendingInvites = snap.members.filter((m) => m.state === "invited").length;
  const isOrganizer = me?.id === snap.deal.createdBy;

  async function start() {
    setStarting(true);
    setCmdErr(null);
    try {
      await api(`/v1/deals/${dealId}/negotiate`, { body: {} });
    } catch (e) {
      setCmdErr(e instanceof ApiError ? e.message : "Couldn't start.");
    } finally {
      setStarting(false);
    }
  }

  const review = snap.deal.vendorReview as { staffName?: string; providerName?: string } | null;
  const chosen = snap.quotes.find((q) => q.id === snap.deal.chosenQuoteId);
  const vendorName = review?.providerName ?? chosen?.providerName;
  const isMember = snap.members.some((m) => m.userId === me?.id);

  async function sendChat(text: string, lang: string, viaVoice: boolean) {
    await api(`/v1/deals/${dealId}/messages`, { body: { text, lang, viaVoice } });
  }

  const tabs = (
    <div className="mb-4 flex gap-1 rounded-[8px] border border-line bg-surface p-1 lg:hidden" role="tablist">
      {(["plan", "members", "activity"] as const).map((t) => (
        <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={cx("flex-1 rounded-[6px] py-1.5 text-[13px] font-medium capitalize", tab === t ? "bg-surface-2 text-ink" : "text-muted")}>
          {t}
        </button>
      ))}
    </div>
  );

  return (
    <>
      <DealHeader snap={snap} />
      {error && <div className="mb-4"><Callout tone="warn" title="Reconnecting…">{error}</Callout></div>}
      <div className="mb-5 space-y-3">
        <WorkflowStepper deal={snap.deal} reviewBy={review?.staffName ?? null} />
        <NextStepBar snap={snap} meId={me?.id} />
        {snap.deal.status === "GROUP_FORMING" && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-line bg-surface px-5 py-3">
            <div>
              <div className="font-semibold">{joined} of {snap.members.length} agents have joined</div>
              <div className="text-[13px] text-muted">The mediator will send one shared plan to every agent and revise it round by round.</div>
            </div>
            {isOrganizer ? (
              <Button onClick={start} disabled={starting || joined < snap.deal.groupMin || pendingInvites > 0}>
                <Play size={14} /> {starting ? "Starting…" : pendingInvites > 0 ? `Waiting for ${pendingInvites} agent${pendingInvites > 1 ? "s" : ""}…` : "Start negotiation"}
              </Button>
            ) : (
              <span className="text-[13px] text-muted">Waiting for the organizer to start.</span>
            )}
          </div>
        )}
        {cmdErr && <Callout tone="danger" title="Not started">{cmdErr}</Callout>}
        {snap.deal.solo && (
          <div className="flex items-start gap-3 rounded-[12px] border border-line bg-buoy-soft px-5 py-3 text-[14px]">
            <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-buoy" aria-hidden />
            <div>
              <div className="font-semibold">
                {["GROUP_FORMING", "NEGOTIATING", "PROVIDER_QUOTES_PENDING"].includes(snap.deal.status)
                  ? "Your agent is negotiating on its own with the shops' agents"
                  : "Your agent negotiated this on its own with the shops' agents"}
              </div>
              <div className="text-[13px] text-ink/75">
                {(() => {
                  const q = snap.quotes.find((x) => x.id === snap.deal.chosenQuoteId);
                  const ride = q?.includes.find((i) => i.startsWith("joins a booked group"));
                  return q && ride
                    ? `${q.providerName} has a trip already running that day, so you ${ride.replace("joins", "join")}: ${money(q.pricePerPerson)} instead of ${money(q.soloPricePerPerson)} booking alone.`
                    : "It asks each shop for its price sheet and any trips already running that you can join at the group rate, then proposes the best plan to you.";
                })()}
              </div>
            </div>
          </div>
        )}
        <NudgeCard snap={snap} meId={me?.id} />
        {isOrganizer && (
          <div className="flex justify-end">
            <Button variant="secondary" onClick={() => setSeats(!seats)}><QrCode size={14} /> {seats ? "Hide phone seats" : "Phone seats"}</Button>
          </div>
        )}
        {seats && isOrganizer && <SeatsPanel dealId={dealId} />}
      </div>
      {tabs}
      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)_340px]">
        <div className={cx(tab !== "members" && "hidden lg:block")}>
          <MemberRail snap={snap} />
          {(snap.deal.replacements?.length ?? 0) > 0 && (
            <div className="mt-3 rounded-[10px] border border-line bg-surface px-4 py-3"><ReplacementNotes snap={snap} /></div>
          )}
        </div>
        <div className={cx("space-y-4", tab !== "plan" && "hidden lg:block")}>
          {isMember && <ExplanationCard dealId={dealId} version={snap.deal.currentProposalVersion ?? 0} />}
          <PlanCard snap={snap} providerName={providerName} />
          <RoundTimeline snap={snap} />
          {isMember && <GearCard dealId={dealId} version={snap.deal.currentProposalVersion ?? 0} />}
          <NegotiationReplay snap={snap} />
        </div>
        <div className={cx("space-y-4", tab !== "activity" && "hidden lg:block")}>
          {snap.quotes.length > 0 && (
            <Card>
              <CardHeader title="Provider quotes" meta="Same plan, group of the current size" />
              <div className="space-y-2 p-3">
                {snap.quotes.map((q) => <QuoteMini key={q.id} q={q} chosen={q.id === snap.deal.chosenQuoteId} />)}
              </div>
            </Card>
          )}
          <ActivityFeed events={snap.events} />
        </div>
      </div>
      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <AgentConversation messages={snap.agentMessages} />
        <ChatPanel
          title={vendorName ? `Group chat with ${vendorName}` : "Group chat"}
          meta={vendorName ? "Members and the vendor's staff. Speak or type in any language." : "The vendor joins once their agent sends a quote."}
          messages={snap.chat}
          meId={me?.id}
          canSend={isMember}
          disabledReason="Only group members can post here."
          onSend={sendChat}
        />
      </div>
    </>
  );
}
