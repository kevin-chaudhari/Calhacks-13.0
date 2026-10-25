"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowRight, Bot, Check, ChevronDown, Store, UserRound, X } from "lucide-react";
import { useMemo, useState } from "react";
import { time } from "@/lib/format";
import type { AgentMessage, Deal } from "@/lib/types";
import { Card, CardHeader, cx } from "@/components/ui/primitives";

const KIND_STYLE: Record<string, string> = {
  mediator: "bg-accent-soft text-accent",
  personal: "bg-surface-2 text-ink",
  provider: "bg-sim-soft text-sim",
  staff: "bg-warn-soft text-warn",
  system: "bg-surface-2 text-muted",
};

function Party({ label, kind }: { label: string; kind: string }) {
  const Icon = kind === "staff" ? UserRound : kind === "provider" ? Store : Bot;
  return (
    <span className={cx("inline-flex h-6 max-w-[200px] items-center gap-1 truncate rounded-full px-2 text-[12px] font-medium", KIND_STYLE[kind])}>
      <Icon size={12} strokeWidth={1.75} className="shrink-0" />
      <span className="truncate">{label}</span>
    </span>
  );
}

const FILTERS: { key: string; label: string; types?: string[] }[] = [
  { key: "all", label: "All" },
  { key: "negotiation", label: "Negotiation", types: ["ProposalMsg", "ResponseMsg"] },
  { key: "vendor", label: "Vendor", types: ["QuoteRequestMsg", "QuoteMsg", "ReviewRequest", "ReviewDecision", "BookingDecision", "FinalAgreementMsg"] },
  { key: "group", label: "Group forming", types: ["InviteMsg", "JoinMsg"] },
];

/** The agent wire, message by message: who sent what to whom. Public fields only. */
export function AgentConversation({ messages, title = "Agent conversation", maxHeight = 520 }: { messages: AgentMessage[]; title?: string; maxHeight?: number }) {
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState<number | null>(null);
  const reduce = useReducedMotion();
  const types = FILTERS.find((f) => f.key === filter)?.types;
  const shown = useMemo(() => [...messages].filter((m) => !types || types.includes(m.type)).reverse(), [messages, types]);
  const parties = useMemo(() => {
    const s = new Map<string, string>();
    messages.forEach((m) => {
      s.set(m.fromLabel, m.fromKind);
      s.set(m.toLabel, m.toKind);
    });
    return [...s.entries()];
  }, [messages]);

  return (
    <Card>
      <CardHeader
        title={title}
        meta={<span className="num">{messages.length} messages between {parties.length} parties</span>}
        action={
          <div className="flex gap-1" role="tablist" aria-label="Message filter">
            {FILTERS.map((f) => (
              <button key={f.key} role="tab" aria-selected={filter === f.key} onClick={() => setFilter(f.key)}
                className={cx("rounded-full px-2.5 py-1 text-[12px] font-medium", filter === f.key ? "bg-surface-2 text-ink" : "text-muted hover:text-ink")}>
                {f.label}
              </button>
            ))}
          </div>
        }
      />
      {parties.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-line px-5 py-2.5">
          {parties.map(([label, kind]) => <Party key={label} label={label} kind={kind} />)}
        </div>
      )}
      <ol className="divide-y divide-line overflow-y-auto" style={{ maxHeight }} aria-live="polite">
        {shown.length === 0 && <li className="px-5 py-8 text-center text-[13px] text-muted">No agent messages yet.</li>}
        <AnimatePresence initial={false}>
          {shown.map((m) => (
            <motion.li key={m.seq} layout={!reduce} initial={reduce ? false : { opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }} className="px-5 py-2.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <Party label={m.fromLabel} kind={m.fromKind} />
                <ArrowRight size={13} className="text-muted" />
                <Party label={m.toLabel} kind={m.toKind} />
                <span className="ml-auto font-mono text-[11px] text-muted">#{m.seq} · {time(m.at)}{m.latencyMs != null && ` · ${m.latencyMs.toFixed(0)} ms`}</span>
              </div>
              <button onClick={() => setOpen(open === m.seq ? null : m.seq)} className="mt-1.5 flex w-full items-start gap-2 text-left" aria-expanded={open === m.seq}>
                <span className="mt-px shrink-0 rounded-[4px] bg-surface-2 px-1.5 font-mono text-[11px] leading-5 text-muted">{m.type}</span>
                <span className="flex-1 text-[13px]">{m.summary}</span>
                {Object.keys(m.payload).length > 0 && <ChevronDown size={14} className={cx("mt-0.5 shrink-0 text-muted transition-transform", open === m.seq && "rotate-180")} />}
              </button>
              {open === m.seq && (
                <pre className="mt-2 max-h-48 overflow-auto rounded-[6px] bg-surface-2 p-2 font-mono text-[11px] leading-4 text-muted">{JSON.stringify(m.payload, null, 2)}</pre>
              )}
            </motion.li>
          ))}
        </AnimatePresence>
      </ol>
    </Card>
  );
}

const STEPS = [
  { key: "goal", label: "Goal compiled", who: "Gemini / compiler" },
  { key: "group", label: "Agents join", who: "Personal agents" },
  { key: "negotiate", label: "Agents negotiate", who: "Mediator ↔ agents" },
  { key: "quote", label: "Vendor quote", who: "Provider agent + staff" },
  { key: "approve", label: "Everyone approves", who: "People" },
  { key: "commit", label: "Committed", who: "Ledger (simulated)" },
  { key: "book", label: "Vendor books", who: "Vendor staff" },
];

const SOLO_LABEL: Record<string, string> = { group: "Your agent ready", negotiate: "Agent vs shops", approve: "You approve" };

export function stepIndex(deal: Deal): { at: number; failed: boolean } {
  const s = deal.status;
  if (s === "GROUP_FORMING") return { at: 1, failed: false };
  if (s === "NEGOTIATING") return { at: 2, failed: false };
  if (s === "PROVIDER_QUOTES_PENDING") return { at: 3, failed: false };
  if (s === "AWAITING_APPROVAL" || s === "COMMITMENT_PENDING") return { at: 4, failed: false };
  if (s === "COMMITTED") return { at: deal.bookingStatus === "not_booked" ? 6 : 7, failed: false };
  if (s === "NO_AGREEMENT") return { at: deal.conflicts.some((c) => c.includes("declined")) ? 3 : 2, failed: true };
  return { at: 2, failed: true };
}

/** End-to-end workflow, driven only by real deal state. */
export function WorkflowStepper({ deal, reviewBy }: { deal: Deal; reviewBy?: string | null }) {
  const { at, failed } = stepIndex(deal);
  const label = (i: number) => (deal.solo ? SOLO_LABEL[STEPS[i].key] ?? STEPS[i].label : STEPS[i].label);
  const shown = Math.min(at, STEPS.length - 1);
  const who = STEPS[shown].key === "quote" && reviewBy ? `${reviewBy} reviewing` : STEPS[shown].who;
  return (
    <div className="rounded-[16px] border border-line bg-surface px-5 py-4 shadow-card">
      {/* Phones: one line and a bar. */}
      <div className="flex items-center justify-between gap-3 md:hidden">
        <div className="min-w-0">
          <div className="text-[12px] text-muted">Step {Math.min(at + 1, STEPS.length)} of {STEPS.length}</div>
          <div className={cx("truncate font-semibold", failed && "text-danger")}>{at === STEPS.length ? "All done" : label(shown)}</div>
        </div>
        <span className="truncate text-[12px] text-muted">{who}</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-2 md:hidden">
        <div className={cx("h-full rounded-full", failed ? "bg-danger" : "bg-accent")} style={{ width: `${(Math.min(at + 1, STEPS.length) / STEPS.length) * 100}%` }} />
      </div>
      {/* Wider screens: every step on one connected line. */}
      <ol className="hidden grid-cols-7 md:grid" aria-label="Workflow">
        {STEPS.map((step, i) => {
          const done = i < at || (i === at && at === 7);
          const current = i === at && !done;
          return (
            <li key={step.key} className="relative flex flex-col items-center text-center" aria-current={current ? "step" : undefined}>
              {i > 0 && <span className={cx("absolute right-1/2 top-3.5 h-0.5 w-full -translate-y-1/2", i <= at ? "bg-accent" : "bg-line")} aria-hidden />}
              <span className={cx("relative z-[1] inline-flex h-7 w-7 items-center justify-center rounded-full text-[12px] font-semibold ring-4 ring-surface",
                done ? "bg-accent text-accent-ink" : current ? (failed ? "bg-danger text-accent-ink" : "bg-accent-soft text-accent ring-accent/25") : "bg-surface-2 text-muted")}>
                {done ? <Check size={14} strokeWidth={2.5} /> : current && failed ? <X size={14} /> : i + 1}
              </span>
              <span className={cx("mt-2 px-1 text-[12px] font-medium leading-4", current ? (failed ? "text-danger" : "text-ink") : done ? "text-ink" : "text-muted")}>{label(i)}</span>
              <span className="mt-0.5 hidden px-1 text-[11px] leading-4 text-muted lg:block">
                {current && step.key === "quote" && reviewBy ? `${reviewBy} reviewing` : step.who}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
