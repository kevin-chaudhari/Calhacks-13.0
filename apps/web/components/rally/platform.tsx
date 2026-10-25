"use client";

// Platform (Kevin) components: QR seats, teammate-feature cards, negotiation replay, live metrics,
// adapter lights, deposit status, calendar + share. Every one renders only from real state; a feature
// whose backend isn't there yet hides itself instead of showing a fake.

import Link from "next/link";
import {
  CalendarPlus, ChevronLeft, Search, ChevronRight, ExternalLink, Pause, Play, QrCode as QrIcon, Share2, Sparkles, TrendingDown, UserPlus,
} from "lucide-react";
import QRCode from "qrcode";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { day, money, orderedTerms, TERM_LABELS, termValue } from "@/lib/format";
import { usePersona } from "@/lib/persona";
import type { Commitment, DealEvent, DealSnapshot } from "@/lib/types";
import { Avatar, Button, Callout, Card, CardHeader, Chip, cx } from "@/components/ui/primitives";

// ----------------------------------------------------------------------------- QR

export function QrCode({ value, size = 148, label }: { value: string; size?: number; label: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    // Dark on white in both themes: phone cameras need the contrast.
    QRCode.toString(value, { type: "svg", margin: 1, errorCorrectionLevel: "M", color: { dark: "#0F1A1F", light: "#FFFFFF" } })
      .then(setSvg)
      .catch(() => setSvg(null));
  }, [value]);
  return (
    <div
      role="img"
      aria-label={label}
      style={{ width: size, height: size }}
      className="overflow-hidden rounded-[8px] bg-white p-1.5 [&>svg]:h-full [&>svg]:w-full"
      dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
    />
  );
}

interface Seat { userId: string; name: string; role: "member" | "vendor"; state: string; url: string }

/** Judges scan a code and act in that member's seat (or the vendor's) on their own phone. */
export function SeatsPanel({ dealId, compact = false }: { dealId: string; compact?: boolean }) {
  const [seats, setSeats] = useState<Seat[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      api<Seat[]>(`/v1/demo/seats/${dealId}`)
        .then((s) => alive && (setSeats(s), setErr(null)))
        .catch((e) => alive && setErr(e instanceof ApiError ? e.message : "Couldn't load seats."));
    load();
    const t = setInterval(load, 4000);         // the vendor seat appears once a vendor is quoting
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [dealId]);
  if (err) return <Callout tone="neutral" title="Seats unavailable">{err}</Callout>;
  if (!seats) return null;
  return (
    <Card>
      <CardHeader
        title={<span className="flex items-center gap-1.5"><QrIcon size={13} /> Take a seat from your phone</span>}
        meta="Scan to act as that member, or as the vendor's staff. Approvals and chat are live on both screens."
      />
      <ul className={cx("grid gap-4 p-4", compact ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6")}>
        {seats.map((s) => (
          <li key={s.userId} className="flex flex-col items-center gap-2 text-center">
            <QrCode value={s.url} size={compact ? 112 : 132} label={`Seat for ${s.name}`} />
            <div>
              <div className="text-[13px] font-semibold">{s.name}</div>
              <div className="text-[11px] text-muted">{s.role === "vendor" ? "vendor staff" : s.state === "joined" ? "member" : s.state}</div>
            </div>
            <a href={s.url} target="_blank" rel="noreferrer" className="text-[11px] text-muted underline">open link</a>
          </li>
        ))}
      </ul>
    </Card>
  );
}

// ------------------------------------------------------------ teammate features

/** Parikshit's group-size nudge: a vendor agent's offer, shown only when the deal carries one. */
export function NudgeCard({ snap, meId }: { snap: DealSnapshot; meId?: string }) {
  const n = snap.deal.nudge;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!n || n.status !== "open") return null;
  const isOrganizer = meId === snap.deal.createdBy;
  async function accept() {
    setBusy(true);
    setErr(null);
    try {
      await api(`/v1/deals/${snap.deal.id}/nudge/accept`, { body: {} });
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 404 ? "Inviting from a nudge isn't available on this server yet." : e instanceof Error ? e.message : "Failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-accent/40 bg-accent-soft px-5 py-4">
      <div className="flex items-start gap-3">
        <TrendingDown size={18} className="mt-0.5 shrink-0 text-accent" />
        <div>
          <div className="font-semibold">
            {n.providerName || snap.providerNames[n.providerId] || "The vendor"}&apos;s agent: {n.extraPeople} more {n.extraPeople === 1 ? "person drops" : "people drop"} everyone to {money(n.newPricePerPerson)}
          </div>
          <div className="num text-[13px] text-ink/80">
            {money(n.currentPricePerPerson)} → {money(n.newPricePerPerson)} per person, {money(n.savingPerPerson)} less each.
            {n.candidateName && <> Next eligible match: {n.candidateName}.</>}
          </div>
          {err && <div className="mt-1 text-[12px] text-danger">{err}</div>}
        </div>
      </div>
      {isOrganizer ? (
        <Button onClick={accept} disabled={busy}><UserPlus size={14} /> {busy ? "Inviting…" : n.candidateName ? `Invite ${n.candidateName}` : "Invite one more"}</Button>
      ) : (
        <span className="text-[13px] text-muted">The organizer can invite one more.</span>
      )}
    </div>
  );
}

/** Dev's "why this plan works for you": private to the viewer, never in the shared snapshot. */
export function ExplanationCard({ dealId, version }: { dealId: string; version: number }) {
  const { me } = usePersona();
  const [data, setData] = useState<{ text: string; generatedBy: string } | null>(null);
  useEffect(() => {
    if (!me || version < 1) return;
    let alive = true;
    api<{ text: string; generatedBy: string }>(`/v1/deals/${dealId}/explanation`)
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null));       // 404 until Dev's endpoint lands: hide, don't fake
    return () => {
      alive = false;
    };
  }, [dealId, version, me]);
  if (!data?.text) return null;
  return (
    <Card className="border-accent/40">
      <div className="flex items-start gap-3 px-5 py-4">
        <Sparkles size={16} className="mt-0.5 shrink-0 text-accent" />
        <div>
          <div className="text-[13px] font-semibold text-muted">Why this plan works for you</div>
          <p className="mt-1 text-[14px] leading-6">{data.text}</p>
          <div className="mt-1 text-[11px] text-muted">Only you see this · {data.generatedBy === "gemini" ? "written by Gemini from your agent's scoring" : "from your agent's scoring"}</div>
        </div>
      </div>
    </Card>
  );
}

/** Parikshit's auto-replace: who left and who took their place. */
export function ReplacementNotes({ snap }: { snap: DealSnapshot }) {
  const reps = snap.deal.replacements ?? [];
  if (!reps.length) return null;
  const name = (id: string, fallback?: string) => fallback || snap.members.find((m) => m.userId === id)?.name || id;
  return (
    <ul className="space-y-1">
      {reps.map((r) => (
        <li key={`${r.leftUserId}-${r.at}`} className="flex items-center gap-2 text-[13px]">
          <UserPlus size={13} className="text-accent" />
          <span><strong className="font-medium">{name(r.invitedUserId, r.invitedName)}</strong> joined in place of {name(r.leftUserId, r.leftName)}</span>
        </li>
      ))}
    </ul>
  );
}

// ------------------------------------------------------------- negotiation replay

const KIND_LABEL: Record<string, string> = {
  accept: "accepted",
  change_request: "asked to change",
  reject_hard: "can't do",
  withdraw: "left",
};

/** Step through every plan version: what was proposed, how each agent answered, why it changed. */
export function NegotiationReplay({ snap }: { snap: DealSnapshot }) {
  const steps = snap.proposals;
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const names = useMemo(() => Object.fromEntries(snap.members.map((m) => [m.userId, m.name])), [snap.members]);
  const last = steps.length - 1;
  useEffect(() => {
    if (!playing) return;
    if (i >= last) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setI((x) => Math.min(last, x + 1)), 1600);
    return () => clearTimeout(t);
  }, [playing, i, last]);
  useEffect(() => setI((x) => Math.min(x, Math.max(0, last))), [last]);
  if (steps.length === 0) return null;
  const p = steps[i];
  const prev = i > 0 ? steps[i - 1] : null;
  const round = snap.rounds.find((r) => r.proposalVersion === p.version);
  const next = steps[i + 1];
  return (
    <Card>
      <CardHeader
        title="Replay the negotiation"
        meta={<span className="num">Plan v{p.version} · round {p.round}{round ? ` · ${round.accepted} of ${round.active} accepted` : ""}</span>}
        action={
          <div className="flex items-center gap-1">
            <button aria-label="Previous version" onClick={() => { setPlaying(false); setI(Math.max(0, i - 1)); }} disabled={i === 0} className="rounded-[6px] p-1.5 text-muted hover:bg-surface-2 disabled:opacity-30"><ChevronLeft size={16} /></button>
            <button aria-label={playing ? "Pause" : "Play"} onClick={() => { if (i >= last) setI(0); setPlaying(!playing); }} className="rounded-[6px] p-1.5 text-accent hover:bg-surface-2">{playing ? <Pause size={16} /> : <Play size={16} />}</button>
            <button aria-label="Next version" onClick={() => { setPlaying(false); setI(Math.min(last, i + 1)); }} disabled={i >= last} className="rounded-[6px] p-1.5 text-muted hover:bg-surface-2 disabled:opacity-30"><ChevronRight size={16} /></button>
          </div>
        }
      />
      <div className="px-5 pt-3">
        <input type="range" min={0} max={last} value={i} onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }} className="w-full accent-[var(--accent)]" aria-label="Plan version" />
      </div>
      <div className="grid gap-4 px-5 pb-4 pt-2 md:grid-cols-2">
        <div>
          <div className="mb-1 text-[12px] font-semibold text-muted">Proposed</div>
          <dl className="space-y-1 text-[13px]">
            {orderedTerms(p.terms).map(([k, v]) => {
              const changed = prev && prev.terms[k] !== v;
              return (
                <div key={k} className={cx("flex justify-between gap-3 rounded-[6px] px-2 py-1", changed && "bg-accent-soft")}>
                  <dt className="text-muted">{TERM_LABELS[k] ?? snap.termLabels[k] ?? k}</dt>
                  <dd className="text-right font-medium">{termValue(k, v)}</dd>
                </div>
              );
            })}
            <div className={cx("flex justify-between gap-3 rounded-[6px] px-2 py-1", prev && prev.pricePerPerson !== p.pricePerPerson && "bg-accent-soft")}>
              <dt className="text-muted">Price · {snap.providerNames[p.providerId] ?? p.providerId}</dt>
              <dd className="num font-medium">{money(p.pricePerPerson)}</dd>
            </div>
          </dl>
        </div>
        <div>
          <div className="mb-1 text-[12px] font-semibold text-muted">How each agent answered</div>
          {round?.responses.length ? (
            <ul className="space-y-1 text-[13px]">
              {round.responses.map((r) => (
                <li key={r.memberId} className="flex items-center justify-between gap-2 rounded-[6px] px-2 py-1">
                  <span>{names[r.memberId] ?? r.memberId}</span>
                  <Chip tone={r.kind === "accept" ? "accent" : r.kind === "reject_hard" ? "danger" : "warn"}>
                    {KIND_LABEL[r.kind] ?? r.kind}{r.term ? ` ${(TERM_LABELS[r.term] ?? r.term).toLowerCase()}` : ""}
                  </Chip>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-[13px] text-muted">Waiting for answers…</div>
          )}
        </div>
      </div>
      <div className="border-t border-line bg-surface-2/60 px-5 py-2.5 text-[13px]">
        {next ? (
          <><span className="font-medium">Next, v{next.version}: </span>{next.rationale.join(" ") || "revised toward the requests above."}</>
        ) : round?.outcome === "all_accept" ? (
          <span className="font-medium text-accent">Every agent accepted this version.</span>
        ) : (
          <span className="text-muted">Latest version.</span>
        )}
      </div>
    </Card>
  );
}

// ------------------------------------------------------------ metrics & adapters

export interface Metrics {
  deals: number; agreed: number; committed: number; booked: number; peopleCommitted: number;
  agentMessages: number; chatMessages: number; meanRounds: number | null; meanSecondsToAgreement: number | null;
  proposalsChecked: number; hardConstraintViolations: number; groupSavingsUsd: number; x402Settled: number; agentsOnline: number;
}

export function useMetrics(intervalMs = 2000) {
  const [m, setM] = useState<Metrics | null>(null);
  useEffect(() => {
    let alive = true;
    const tick = () => api<Metrics>("/v1/metrics", { token: null }).then((x) => alive && setM(x)).catch(() => {});
    tick();
    const t = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [intervalMs]);
  return m;
}

export function MetricsGrid({ m }: { m: Metrics }) {
  const items: [string, string, string?][] = [
    ["Hard-constraint violations", String(m.hardConstraintViolations), `${m.proposalsChecked} proposal checks, re-run live`],
    ["Agent messages", String(m.agentMessages), `${m.agentsOnline} agents online`],
    ["Groups agreed", `${m.agreed} / ${m.deals}`, m.meanRounds != null ? `${m.meanRounds} rounds on average` : undefined],
    ["Time to agreement", m.meanSecondsToAgreement != null ? `${m.meanSecondsToAgreement}s` : "—", "measured, includes demo pacing"],
    ["People committed", String(m.peopleCommitted), `${m.booked} bookings confirmed by vendors`],
    ["Group savings", money(m.groupSavingsUsd), "vs the same vendor's solo price (simulated quotes)"],
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {items.map(([label, value, hint]) => (
        <div key={label} className="rounded-[16px] border border-line bg-surface shadow-card px-4 py-3">
          <dt className="text-[12px] text-muted">{label}</dt>
          <dd className={cx("num mt-0.5 text-[24px] font-semibold leading-8", label.startsWith("Hard") && value === "0" && "text-accent")}>{value}</dd>
          {hint && <div className="text-[11px] text-muted">{hint}</div>}
        </div>
      ))}
    </dl>
  );
}

const LIVE: Record<string, string[]> = {
  compiler: ["gemini"], ranker: ["moss"], transport: ["agentverse", "bureau"], store: ["convex"],
  payments: ["x402_testnet"], providers: ["agents", "seeded+apify"], gear: ["brightdata"],
};
const SPONSOR: Record<string, string> = {
  compiler: "Gemini", ranker: "Moss", transport: "Fetch.ai uAgents", store: "Convex", payments: "x402", providers: "Apify", gear: "Bright Data",
};

export function AdapterLights({ adapters, convexErrors }: { adapters: Record<string, string>; convexErrors?: number }) {
  return (
    <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
      {Object.keys(SPONSOR).map((k) => {
        const mode = adapters[k] ?? "—";
        const live = (LIVE[k] ?? []).includes(mode) && !(k === "store" && (convexErrors ?? 0) > 0);
        return (
          <li key={k} className="flex items-center gap-2.5 rounded-[16px] border border-line bg-surface shadow-card px-3 py-2.5">
            <span className={cx("h-2.5 w-2.5 shrink-0 rounded-full", live ? "bg-accent" : "bg-warn")} aria-hidden />
            <div className="min-w-0">
              <div className="text-[13px] font-medium">{SPONSOR[k]}</div>
              <div className="truncate font-mono text-[11px] text-muted">{live ? "live" : "fallback"} · {mode}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// -------------------------------------------------------------------- payments

function latestFor(events: DealEvent[], userId: string) {
  return [...events].reverse().find((e) => e.actor === userId && e.type.startsWith("commitment."));
}

export function DepositStatus({ c, events, name }: { c: Commitment; events: DealEvent[]; name: string }) {
  if (c.state === "committed") {
    return c.explorerUrl ? (
      <a href={c.explorerUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-mono text-[11px] text-accent underline">
        {c.txRef?.slice(0, 10)}… <ExternalLink size={11} />
      </a>
    ) : (
      <span className="font-mono text-[11px] text-muted">{c.txRef}</span>
    );
  }
  const last = latestFor(events, c.userId);
  if (last?.type === "commitment.paying") return <Chip tone="sim">Paying deposit…</Chip>;
  if (last?.type === "commitment.failed") return <Chip tone="danger" title={last.summary}>Deposit failed</Chip>;
  return <Chip>{c.state === "pending" ? `Waiting for ${name}` : c.state}</Chip>;
}

// ------------------------------------------------------------ calendar & share

function icsDate(iso: string) {
  return iso.replace(/-/g, "");
}

export function CalendarAndShare({ snap }: { snap: DealSnapshot }) {
  const [copied, setCopied] = useState(false);
  const plan = snap.proposals[snap.proposals.length - 1];
  const quote = snap.quotes.find((q) => q.id === snap.deal.chosenQuoteId);
  const date = typeof plan?.terms.date === "string" ? plan.terms.date : null;
  const summary = useMemo(() => {
    if (!plan) return "";
    const people = snap.members.filter((m) => m.state === "joined").map((m) => m.name).join(", ");
    const terms = orderedTerms(plan.terms).map(([k, v]) => `${TERM_LABELS[k] ?? k}: ${termValue(k, v)}`).join("\n");
    return `${snap.deal.title}\n${terms}\n${quote ? `${quote.providerName} · ${money(quote.pricePerPerson)} per person` : ""}\nWith ${people}\nPlanned by our agents on Parley`;
  }, [plan, quote, snap]);

  const downloadIcs = useCallback(() => {
    if (!date) return;
    const next = new Date(date + "T12:00:00Z");
    next.setUTCDate(next.getUTCDate() + 1);
    const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/,/g, "\\,").replace(/;/g, "\\;").replace(/\n/g, "\\n");
    const ics = [
      "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Parley//Group plan//EN", "BEGIN:VEVENT",
      `UID:${snap.deal.id}@rally`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`,
      `DTSTART;VALUE=DATE:${icsDate(date)}`, `DTEND;VALUE=DATE:${icsDate(next.toISOString().slice(0, 10))}`,
      `SUMMARY:${esc(snap.deal.title)}`, `LOCATION:${esc(quote?.providerName ?? "")}`, `DESCRIPTION:${esc(summary)}`,
      "END:VEVENT", "END:VCALENDAR",
    ].join("\r\n");
    const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `rally-${snap.deal.id}.ics`;
    a.click();
    URL.revokeObjectURL(url);
  }, [date, snap.deal.id, snap.deal.title, quote, summary]);

  async function share() {
    const url = typeof window !== "undefined" ? window.location.href : "";
    try {
      if (navigator.share) await navigator.share({ title: snap.deal.title, text: summary, url });
      else {
        await navigator.clipboard.writeText(`${summary}\n${url}`);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      }
    } catch {
      /* the person closed the share sheet */
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {date && <Button variant="secondary" onClick={downloadIcs}><CalendarPlus size={14} /> Add to calendar · {day(date)}</Button>}
      <Button variant="secondary" onClick={share}><Share2 size={14} /> {copied ? "Copied" : "Share plan"}</Button>
    </div>
  );
}

// ----------------------------------------------------------------- ASI:One card

const AGENT = process.env.NEXT_PUBLIC_RALLY_AGENT_ADDRESS || "";

/** Shown once Parikshit's concierge is registered (NEXT_PUBLIC_RALLY_AGENT_ADDRESS). */
export function AsiOneCard() {
  if (!AGENT) return null;
  return (
    <Card>
      <div className="flex items-start gap-3 px-5 py-4">
        <Avatar initials="AI" size={32} />
        <div className="min-w-0">
          <div className="font-semibold">Also on ASI:One</div>
          <p className="text-[13px] text-muted">Type the same goal in ASI:One chat; Parley&apos;s concierge agent finds your people and replies with the plan.</p>
          <div className="mt-2 flex flex-wrap gap-3 text-[13px]">
            <a className="inline-flex items-center gap-1 text-accent underline" href="https://asi1.ai" target="_blank" rel="noreferrer">Open ASI:One <ExternalLink size={12} /></a>
            <a className="inline-flex items-center gap-1 text-muted underline" href={`https://agentverse.ai/agents/details/${AGENT}/profile`} target="_blank" rel="noreferrer">Agent on Agentverse <ExternalLink size={12} /></a>
          </div>
          <div className="mt-1 truncate font-mono text-[11px] text-muted">{AGENT}</div>
        </div>
      </div>
    </Card>
  );
}

export function Hint({ children, href }: { children: React.ReactNode; href?: string }) {
  return href ? <Link href={href} className="text-[12px] text-muted underline">{children}</Link> : <span className="text-[12px] text-muted">{children}</span>;
}

// --------------------------------------------------------------- vendor search

interface SearchHit { providerId: string; name: string; activity: string; score: number }

/** Dev's semantic vendor search (Moss). Hidden until the endpoint answers. */
export function VendorSearch() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<{ results: SearchHit[]; ranker: string } | null>(null);
  const [available, setAvailable] = useState<boolean | null>(null);
  useEffect(() => {
    api<{ results: SearchHit[]; ranker: string }>("/v1/providers/search?q=dive", { token: null })
      .then(() => setAvailable(true))
      .catch(() => setAvailable(false));
  }, []);
  useEffect(() => {
    if (!available || q.trim().length < 2) return setRes(null);
    let alive = true;
    const t = setTimeout(() => {
      api<{ results: SearchHit[]; ranker: string }>(`/v1/providers/search?q=${encodeURIComponent(q.trim())}`, { token: null })
        .then((r) => alive && setRes(r))
        .catch(() => alive && setRes(null));
    }, 250);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q, available]);
  if (!available) return null;
  return (
    <Card>
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <span className="text-[13px] font-semibold text-muted">Find a vendor</span>
        {res && <Chip tone="sim">{res.ranker === "moss" ? "Ranked by Moss" : "Ranked locally"}</Chip>}
      </div>
      <div className="p-3">
        <label className="flex items-center gap-2 rounded-[8px] border border-line px-3 py-2 focus-within:border-accent">
          <Search size={14} className="text-muted" />
          <span className="sr-only">Search vendors</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="calm boat dive for beginners" className="w-full bg-transparent text-[14px] outline-none" />
        </label>
        {res && (
          <ul className="mt-2 divide-y divide-line">
            {res.results.length === 0 && <li className="py-2 text-[13px] text-muted">No vendors match.</li>}
            {res.results.slice(0, 5).map((r) => (
              <li key={r.providerId} className="flex items-center justify-between gap-3 py-2 text-[13px]">
                <span><span className="font-medium">{r.name}</span> <span className="text-muted">· {r.activity}</span></span>
                <span className="num text-[11px] text-muted">{r.score.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
