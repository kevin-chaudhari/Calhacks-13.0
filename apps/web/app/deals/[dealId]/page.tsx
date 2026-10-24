"use client";

import { useParams } from "next/navigation";
import { Play } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useDealSnapshot } from "@/lib/useDeal";
import { Button, Callout, Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { ActivityFeed, DealHeader, MemberRail, NextStepBar, PlanCard, QuoteMini, RoundTimeline } from "@/components/rally/room";
import { AgentConversation, WorkflowStepper } from "@/components/rally/agents";
import { ChatPanel } from "@/components/rally/chat";
import { cx } from "@/components/ui/primitives";

export default function GroupRoom() {
  const { dealId } = useParams<{ dealId: string }>();
  const { me } = usePersona();
  const { snap, error } = useDealSnapshot(dealId);
  const [tab, setTab] = useState<"plan" | "members" | "activity">("plan");
  const [cmdErr, setCmdErr] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

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
      </div>
      {tabs}
      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)_340px]">
        <div className={cx(tab !== "members" && "hidden lg:block")}>
          <MemberRail snap={snap} />
        </div>
        <div className={cx("space-y-4", tab !== "plan" && "hidden lg:block")}>
          <PlanCard snap={snap} providerName={providerName} />
          <RoundTimeline snap={snap} />
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
