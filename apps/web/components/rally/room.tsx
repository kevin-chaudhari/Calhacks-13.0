"use client";

import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowRight, Bot, Check, ChevronLeft, ChevronRight, CircleDashed, Clock, LogOut, MessageSquareWarning, Receipt, ShieldX, UserMinus,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { day, money, orderedTerms, TERM_LABELS, termValue, time } from "@/lib/format";
import type { DealEvent, DealSnapshot, Member, Proposal, Quote } from "@/lib/types";
import { Avatar, ButtonLink, Card, CardHeader, Chip, cx } from "@/components/ui/primitives";
import { ProvenanceBadge, StatusPill } from "./shell";

const AGENT_STATUS: Record<string, { label: (m: Member) => string; tone: "accent" | "warn" | "danger" | "neutral" | "sim" }> = {
  accepted: { label: () => "Accepted", tone: "accent" },
  change_request: { label: (m) => `Wants a change: ${(m.agentTerm ?? "").replace(/_/g, " ")}`, tone: "warn" },
  reject_hard: { label: (m) => `Can't do this ${(m.agentTerm ?? "").replace(/_/g, " ")}`, tone: "danger" },
  thinking: { label: () => "Thinking…", tone: "neutral" },
  idle: { label: () => "Waiting", tone: "neutral" },
  unresponsive: { label: () => "Unresponsive", tone: "danger" },
  withdrawn: { label: () => "Left the group", tone: "neutral" },
};

export function MemberRail({ snap }: { snap: DealSnapshot }) {
  const active = snap.members.filter((m) => m.state === "joined");
  const accepted = active.filter((m) => m.agentStatus === "accepted").length;
  return (
    <Card>
      <CardHeader title="Members" meta={<span className="num">{active.length} in the group · {accepted} of {active.length} accepted</span>} />
      <ul className="divide-y divide-line">
        {snap.members.map((m) => {
          const gone = m.state !== "joined";
          const st =
            m.state === "invited" ? { label: "Invited", tone: "neutral" as const }
            : m.state === "removed" ? { label: "Removed", tone: "danger" as const }
            : m.state === "withdrawn" ? { label: "Left the group", tone: "neutral" as const }
            : m.state === "unresponsive" ? { label: "Unresponsive", tone: "danger" as const }
            : { label: (AGENT_STATUS[m.agentStatus] ?? AGENT_STATUS.idle).label(m), tone: (AGENT_STATUS[m.agentStatus] ?? AGENT_STATUS.idle).tone };
          return (
            <li key={m.userId} className={cx("group flex items-center gap-3 px-5 py-3", gone && "opacity-60")}>
              <Avatar initials={m.initials} demo={m.isDemoPersona} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="font-medium">{m.name}</span>
                  {m.role === "organizer" && <span className="text-[12px] text-muted">organizer</span>}
                </div>
                <motion.div key={st.label} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }} className="mt-1">
                  <Chip tone={st.tone}>{st.label}</Chip>
                </motion.div>
                {m.removedReason && gone && <div className="mt-1 text-[12px] text-muted">{m.removedReason}</div>}
                <div className="mt-1 hidden truncate font-mono text-[11px] text-muted group-hover:block">{m.agentAddress}</div>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function termState(key: string, snap: DealSnapshot, p: Proposal, isCurrent: boolean) {
  if (key === "price_per_person") return { label: "Provider decides", tone: "sim" as const };
  if (!isCurrent) return null;
  const active = snap.members.filter((m) => m.state === "joined");
  const contesting = active.filter((m) => (m.agentStatus === "change_request" || m.agentStatus === "reject_hard") && m.agentTerm === key);
  if (contesting.length) return { label: `Contested by ${contesting.length}`, tone: "warn" as const };
  if (active.length && active.every((m) => m.agentStatus === "accepted")) return { label: "Agreed by all", tone: "accent" as const };
  if (p.changed.includes(key)) return { label: "Just changed", tone: "neutral" as const };
  return { label: "Pending", tone: "neutral" as const };
}

function TermRow({ k, value, state, changedLine, flash }: { k: string; value: string; state: ReturnType<typeof termState>; changedLine?: string; flash: boolean }) {
  return (
    <div className={cx("grid grid-cols-[130px_1fr_auto] items-start gap-3 px-5 py-3", flash && "flash")}>
      <div className="pt-0.5 text-[13px] text-muted">{TERM_LABELS[k] ?? k.replace(/_/g, " ")}</div>
      <div className="min-w-0">
        <div className="num font-medium">{value}</div>
        {changedLine && <div className="num mt-0.5 text-[12px] text-muted">{changedLine}</div>}
      </div>
      {state && <Chip tone={state.tone}>{state.label}</Chip>}
    </div>
  );
}

export function PlanCard({ snap, providerName }: { snap: DealSnapshot; providerName: (id: string) => string }) {
  const proposals = snap.proposals;
  const [view, setView] = useState<number | null>(null);
  const current = proposals[proposals.length - 1];
  const p = view !== null ? proposals.find((x) => x.version === view) ?? current : current;
  const allAccepted = snap.members.filter((m) => m.state === "joined").every((m) => m.agentStatus === "accepted");
  useEffect(() => setView(null), [current?.version]);

  if (!current) {
    return (
      <Card>
        <CardHeader title="Current plan" />
        <div className="flex flex-col items-center gap-2 px-5 py-14 text-center">
          <CircleDashed className="text-muted" />
          <div className="font-medium">No plan yet</div>
          <div className="max-w-sm text-[13px] text-muted">
            {snap.deal.status === "GROUP_FORMING"
              ? `Waiting for members' agents to join (${snap.members.filter((m) => m.state === "joined").length} of ${snap.members.length}).`
              : "The mediator is preparing an opening plan."}
          </div>
        </div>
      </Card>
    );
  }
  const prev = proposals.find((x) => x.version === p.version - 1);
  const isCurrent = p.version === current.version;
  const keys = [...orderedTerms(p.terms).map(([k]) => k), "price_per_person"];

  return (
    <Card>
      <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-[20px] font-semibold leading-7">Plan v{p.version}</h2>
          {!isCurrent && <Chip>Earlier version</Chip>}
          {isCurrent && allAccepted && <Chip tone="accent"><Check size={12} /> Everyone accepted</Chip>}
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="Plan versions">
          <button aria-label="Previous version" disabled={p.version <= proposals[0].version} onClick={() => setView(p.version - 1)} className="rounded-[6px] p-1.5 text-muted hover:bg-surface-2 disabled:opacity-30">
            <ChevronLeft size={16} />
          </button>
          <span className="num w-14 text-center font-mono text-[12px] text-muted">{p.version} / {current.version}</span>
          <button aria-label="Next version" disabled={isCurrent} onClick={() => setView(p.version + 1 === current.version ? null : p.version + 1)} className="rounded-[6px] p-1.5 text-muted hover:bg-surface-2 disabled:opacity-30">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
      <div className="divide-y divide-line">
        {keys.map((k) => {
          const raw = k === "price_per_person" ? p.pricePerPerson : p.terms[k];
          const prevRaw = prev ? (k === "price_per_person" ? prev.pricePerPerson : prev.terms[k]) : undefined;
          const changed = prev && prevRaw !== raw;
          const line = changed ? `${termValue(k, prevRaw)} → ${termValue(k, raw)}` : undefined;
          return (
            <TermRow
              key={`${p.version}-${k}`}
              k={k}
              value={termValue(k, raw)}
              state={termState(k, snap, p, isCurrent)}
              changedLine={line}
              flash={!!changed && isCurrent}
            />
          );
        })}
        <div className="grid grid-cols-[130px_1fr] gap-3 px-5 py-3">
          <div className="text-[13px] text-muted">Provider</div>
          <div className="font-medium">{providerName(p.providerId)}</div>
        </div>
      </div>
      {p.rationale.length > 0 && (
        <div className="border-t border-line bg-surface-2/60 px-5 py-3">
          <div className="text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">Why this version</div>
          <ul className="mt-1 space-y-0.5 text-[13px]">
            {p.rationale.map((r) => <li key={r} className="num">{r}</li>)}
          </ul>
        </div>
      )}
    </Card>
  );
}

export function RoundTimeline({ snap }: { snap: DealSnapshot }) {
  const { deal, rounds } = snap;
  const attempt = deal.attempt;
  const these = rounds.filter((r) => r.attempt === attempt);
  const last = these[these.length - 1];
  const slots = Array.from({ length: deal.maxRounds }, (_, i) => these.find((r) => r.number === i + 1));
  const outcomeTone = (o?: string) =>
    o === "all_accept" ? "bg-accent" : o === "revised" ? "bg-warn" : o === "stalled" || o === "exhausted" || o === "timeout" ? "bg-danger" : o === "pending" ? "bg-muted animate-pulse" : "bg-surface-2";
  return (
    <Card className="px-5 py-4">
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Negotiation</div>
        <div className="num text-[13px] text-muted" aria-live="polite">
          {last ? `Round ${last.number} of ${deal.maxRounds} · ${last.accepted || snap.members.filter((m) => m.agentStatus === "accepted").length} of ${last.active || snap.members.filter((m) => m.state === "joined").length} accepted` : "Not started"}
          {attempt > 1 && ` · attempt ${attempt}`}
        </div>
      </div>
      <ol className="mt-3 grid gap-1.5" style={{ gridTemplateColumns: `repeat(${deal.maxRounds}, minmax(0, 1fr))` }}>
        {slots.map((r, i) => (
          <li key={i}>
            <div className={cx("h-1.5 rounded-full transition-colors", outcomeTone(r?.outcome))} />
            <div className="num mt-1.5 text-[11px] text-muted">
              R{i + 1}
              {r && <span className="ml-1">{r.outcome === "pending" ? "…" : r.outcome === "all_accept" ? "agreed" : r.outcome}</span>}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

const EVENT_ICON: Record<string, typeof Bot> = {
  "proposal.sent": Bot,
  "agent.change_request": MessageSquareWarning,
  "agent.reject_hard": ShieldX,
  "member.removed": UserMinus,
  "member.withdrawn": LogOut,
  "quote.received": Receipt,
  "round.closed": Clock,
};

export function ActivityFeed({ events, limit = 40 }: { events: DealEvent[]; limit?: number }) {
  const reduce = useReducedMotion();
  const items = useMemo(() => [...events].reverse().slice(0, limit), [events, limit]);
  return (
    <Card>
      <CardHeader title="Mediator activity" />
      <ol className="max-h-[440px] divide-y divide-line overflow-y-auto" aria-live="polite">
        <AnimatePresence initial={false}>
          {items.map((e) => {
            const Icon = EVENT_ICON[e.type] ?? (e.type.startsWith("deal.") ? ArrowRight : Bot);
            const strong = e.type.startsWith("deal.");
            return (
              <motion.li
                key={e.seq}
                layout={!reduce}
                initial={reduce ? false : { opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.18 }}
                className="flex gap-3 px-5 py-2.5"
              >
                <Icon size={14} strokeWidth={1.75} className={cx("mt-0.5 shrink-0", strong ? "text-accent" : "text-muted")} />
                <div className="min-w-0 flex-1">
                  <div className={cx("text-[13px]", strong && "font-medium")}>{e.summary}</div>
                  <div className="num font-mono text-[11px] text-muted">#{e.seq} · {time(e.at)}</div>
                </div>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ol>
    </Card>
  );
}

export function QuoteMini({ q, chosen }: { q: Quote; chosen: boolean }) {
  return (
    <div className={cx("rounded-[10px] border p-3", chosen ? "border-accent" : "border-line", !q.available && "opacity-60")}>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-medium">{q.providerName}</span>
        <ProvenanceBadge kind={q.provenance} />
      </div>
      {q.available ? (
        <div className="mt-1 flex items-baseline gap-2">
          <span className="num text-[20px] font-semibold">{money(q.pricePerPerson)}</span>
          <span className="num text-[12px] text-muted">pp · {money(q.total)} total</span>
        </div>
      ) : (
        <div className="mt-1 text-[13px] text-muted">Can&apos;t serve this plan</div>
      )}
      <div className="mt-1 text-[12px] text-muted">{chosen ? "Binding quote for the agreed plan" : q.available ? "Price sheet, same plan" : ""}</div>
    </div>
  );
}

export function NextStepBar({ snap, meId }: { snap: DealSnapshot; meId?: string }) {
  const s = snap.deal.status;
  const id = snap.deal.id;
  if (s === "AWAITING_APPROVAL" || s === "COMMITMENT_PENDING") {
    const v = snap.deal.currentProposalVersion;
    const mine = snap.approvals.some((a) => a.userId === meId && a.proposalVersion === v && !a.void);
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-accent bg-accent-soft px-5 py-3">
        <div>
          <div className="font-semibold text-accent">Everyone&apos;s agent accepted plan v{v}.</div>
          <div className="text-[13px] text-ink/80">{mine ? "You approved. Waiting for the others." : "Now each person approves the exact plan and quote."}</div>
        </div>
        <div className="flex gap-2">
          <ButtonLink href={`/deals/${id}/providers`} variant="secondary">Compare quotes</ButtonLink>
          <ButtonLink href={`/deals/${id}/approve`}>Review and approve <ArrowRight size={15} /></ButtonLink>
        </div>
      </div>
    );
  }
  if (s === "PROVIDER_QUOTES_PENDING") {
    const r = snap.deal.vendorReview as { staffName?: string; providerName?: string } | null;
    return (
      <div className="rounded-[10px] border border-line bg-surface px-5 py-3">
        <div className="font-semibold">{r ? `${r.providerName}'s agent drafted a quote` : "Requesting a binding quote"}</div>
        <div className="text-[13px] text-muted">
          {r ? `${r.staffName} is reviewing it in the vendor portal. You can message them in the group chat below.` : "The mediator asked the chosen provider's agent for a binding quote."}
        </div>
      </div>
    );
  }
  if (s === "COMMITTED") {
    const booked = snap.deal.bookingStatus !== "not_booked";
    return (
      <div className="flex items-center justify-between gap-3 rounded-[10px] border border-accent bg-accent-soft px-5 py-3">
        <div className="font-semibold text-accent">
          {booked ? `Booked: confirmed by ${snap.deal.bookedBy}.` : "Committed (simulated). Waiting for the vendor to confirm the booking."}
        </div>
        <ButtonLink href={`/deals/${id}/confirmed`}>See confirmation</ButtonLink>
      </div>
    );
  }
  if (s === "NO_AGREEMENT") {
    return (
      <div className="rounded-[10px] border border-danger/40 bg-danger-soft px-5 py-3">
        <div className="font-semibold text-danger">No plan fits everyone.</div>
        <div className="text-[13px] text-ink/80">{snap.deal.conflicts.join(" · ")}. Choose: someone leaves the group, or start a goal with relaxed terms.</div>
      </div>
    );
  }
  return null;
}

export function DealHeader({ snap }: { snap: DealSnapshot }) {
  const d = snap.deal;
  const deadline = new Date(d.deadlineAt);
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="text-[13px] text-muted">
          <Link href="/" className="hover:text-ink">Goals</Link> / Group room
        </div>
        <h1 className="mt-1 text-[28px] font-semibold leading-[34px] tracking-[-0.01em]">{d.title}</h1>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={d.status} />
        <Chip title="The group expires if not committed by then"><Clock size={12} /> until {deadline.toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit" })}</Chip>
        <Chip tone={snap.provenance.transport === "agentverse" ? "accent" : "sim"} title={snap.provenance.transport === "agentverse" ? "Every member and vendor agent is a registered Fetch.ai uAgent on Agentverse" : "Agent transport in use"}>Agents: {snap.provenance.transport as string}</Chip>
      </div>
    </div>
  );
}

export const dateLabel = day;
