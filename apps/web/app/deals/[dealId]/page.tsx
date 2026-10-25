"use client";

import { useParams } from "next/navigation";
import { Bot, ClipboardList, History, MessagesSquare, Play, QrCode, Receipt, Users } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { money } from "@/lib/format";
import { usePersona } from "@/lib/persona";
import { useDealSnapshot } from "@/lib/useDeal";
import { Button, Callout, Card, CardHeader, Skeleton, Tabs, cx } from "@/components/ui/primitives";
import { ActivityFeed, DealHeader, MemberRail, NextStepBar, PlanCard, QuoteMini, RoundTimeline } from "@/components/rally/room";
import { AgentConversation, WorkflowStepper } from "@/components/rally/agents";
import { ChatPanel } from "@/components/rally/chat";
import { GearCard } from "@/components/rally/gear";
import { ExplanationCard, NegotiationReplay, NudgeCard, ReplacementNotes, SeatsPanel } from "@/components/rally/platform";

type Tab = "plan" | "chat" | "agents" | "replay" | "people";

export default function GroupRoom() {
  const { dealId } = useParams<{ dealId: string }>();
  const { me } = usePersona();
  const { snap, error } = useDealSnapshot(dealId);
  const [tab, setTab] = useState<Tab>("plan");
  const [cmdErr, setCmdErr] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [seats, setSeats] = useState(false);

  if (error && !snap) return <Callout tone="danger" title="Can't open this trip">{error}</Callout>;
  if (!snap)
    return (
      <div className="space-y-5">
        <Skeleton className="h-16" />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <Skeleton className="h-[520px]" />
          <Skeleton className="h-[420px]" />
        </div>
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
  // On wide screens the sidebar is always visible, so "People" only exists as a tab on phones.
  const main: Exclude<Tab, "people"> = tab === "people" ? "plan" : tab;

  async function sendChat(text: string, lang: string, viaVoice: boolean) {
    await api(`/v1/deals/${dealId}/messages`, { body: { text, lang, viaVoice } });
  }

  return (
    <>
      <DealHeader
        snap={snap}
        action={isOrganizer && (
          <Button variant="secondary" onClick={() => setSeats(!seats)}><QrCode size={15} /> {seats ? "Hide phone seats" : "Phone seats"}</Button>
        )}
      />
      {error && <div className="mb-4"><Callout tone="warn" title="Reconnecting…">{error}</Callout></div>}
      <div className="mb-6 space-y-3">
        <WorkflowStepper deal={snap.deal} reviewBy={review?.staffName ?? null} />
        <NextStepBar snap={snap} meId={me?.id} />
        {snap.deal.status === "GROUP_FORMING" && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-line bg-surface px-5 py-4 shadow-card">
            <div>
              <div className="font-semibold">{joined} of {snap.members.length} agents have joined</div>
              <div className="text-[13px] text-muted">Next, a go-between agent sends one shared plan to everyone&apos;s agent and improves it round by round.</div>
            </div>
            {isOrganizer ? (
              <Button onClick={start} disabled={starting || joined < snap.deal.groupMin || pendingInvites > 0}>
                <Play size={15} /> {starting ? "Starting…" : pendingInvites > 0 ? `Waiting for ${pendingInvites} agent${pendingInvites > 1 ? "s" : ""}…` : "Start negotiation"}
              </Button>
            ) : (
              <span className="text-[13px] text-muted">Waiting for the organizer to start.</span>
            )}
          </div>
        )}
        {cmdErr && <Callout tone="danger" title="Not started">{cmdErr}</Callout>}
        {snap.deal.solo && (
          <div className="flex items-start gap-3 rounded-[16px] border border-buoy/40 bg-buoy-soft px-5 py-4 text-[14px]">
            <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-buoy" aria-hidden />
            <div>
              <div className="font-semibold">
                {["GROUP_FORMING", "NEGOTIATING", "PROVIDER_QUOTES_PENDING"].includes(snap.deal.status)
                  ? "Your agent is bargaining with the shops' agents for you"
                  : "Your agent bargained with the shops' agents for you"}
              </div>
              <div className="text-[13px] text-ink/75">
                {(() => {
                  const ride = chosen?.includes.find((i) => i.startsWith("joins a booked group"));
                  return chosen && ride
                    ? `${chosen.providerName} has a trip already running that day, so you ${ride.replace("joins", "join")}: ${money(chosen.pricePerPerson)} instead of ${money(chosen.soloPricePerPerson)} booking alone.`
                    : "It asks each shop for its prices and any trips already running that you can join at the group price, then shows you the best plan.";
                })()}
              </div>
            </div>
          </div>
        )}
        <NudgeCard snap={snap} meId={me?.id} />
        {seats && isOrganizer && <SeatsPanel dealId={dealId} />}
      </div>

      <Tabs<Tab>
        label="Trip sections"
        value={tab}
        onChange={setTab}
        className="mb-5 w-fit max-w-full"
        items={[
          { key: "plan", label: "Plan", icon: <ClipboardList size={16} /> },
          { key: "people", label: "People", icon: <Users size={16} />, count: joined, className: "lg:hidden" },
          { key: "chat", label: "Chat", icon: <MessagesSquare size={16} />, count: snap.chat.length },
          { key: "agents", label: "Agent talk", icon: <Bot size={16} />, count: snap.agentMessages.length },
          { key: "replay", label: "Replay", icon: <History size={16} /> },
        ]}
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className={cx("min-w-0 space-y-5", tab === "people" && "hidden lg:block")} role="tabpanel">
          {main === "plan" && (
            <>
              {isMember && <ExplanationCard dealId={dealId} version={snap.deal.currentProposalVersion ?? 0} />}
              <PlanCard snap={snap} providerName={providerName} />
              <RoundTimeline snap={snap} />
              {isMember && <GearCard dealId={dealId} version={snap.deal.currentProposalVersion ?? 0} />}
            </>
          )}
          {main === "chat" && (
            <ChatPanel
              title={vendorName ? `Group chat with ${vendorName}` : "Group chat"}
              meta={vendorName ? "Members and the shop's staff. Speak or type in any language." : "The shop joins once their agent sends a quote."}
              messages={snap.chat}
              meId={me?.id}
              canSend={isMember}
              disabledReason="Only group members can post here."
              onSend={sendChat}
            />
          )}
          {main === "agents" && <AgentConversation messages={snap.agentMessages} />}
          {main === "replay" && (
            snap.proposals.length ? <NegotiationReplay snap={snap} /> : (
              <Callout tone="neutral" title="Nothing to replay yet">Once the agents trade plans, you can step through every version here.</Callout>
            )
          )}
        </div>

        <aside className={cx("space-y-5", tab !== "people" && "hidden lg:block")}>
          <MemberRail snap={snap} />
          {(snap.deal.replacements?.length ?? 0) > 0 && (
            <div className="rounded-[16px] border border-line bg-surface px-4 py-3 shadow-card"><ReplacementNotes snap={snap} /></div>
          )}
          {snap.quotes.length > 0 && (
            <Card>
              <CardHeader icon={<Receipt size={15} />} title="Shop quotes" meta="Same plan, for a group this size" />
              <div className="space-y-2 p-3">
                {snap.quotes.map((q) => <QuoteMini key={q.id} q={q} chosen={q.id === snap.deal.chosenQuoteId} />)}
              </div>
            </Card>
          )}
          <ActivityFeed events={snap.events} />
        </aside>
      </div>
    </>
  );
}
