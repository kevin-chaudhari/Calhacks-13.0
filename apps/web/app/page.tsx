"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Anchor, ArrowRight, CircleCheckBig, CornerDownLeft, Handshake, Luggage, MessageSquareText, Plane, Sparkles, Target, User, Users, Waves,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import type { DealSummary, Goal } from "@/lib/types";
import { Button, Callout, Card, CardHeader, Skeleton, cx } from "@/components/ui/primitives";
import { StatusPill } from "@/components/rally/shell";
import { AsiOneCard, VendorSearch } from "@/components/rally/platform";
import { MODE_KEY, type Mode } from "@/lib/mode";

const EXAMPLES = [
  { label: "Scuba in Monterey", hint: "Certified diver, under $300", icon: Anchor, text: "I want to go scuba diving in Monterey next month for under $300. I am Open Water certified." },
  { label: "Skydiving, Santa Cruz", hint: "First jump, under $400", icon: Plane, text: "I want to go skydiving near Santa Cruz next month for under $400, first jump." },
  { label: "Sea kayaking", hint: "Monterey, under $120", icon: Waves, text: "Sea kayaking in Monterey next month, under $120 per person." },
];

const HOW = [
  { icon: MessageSquareText, title: "Say what you want", text: "One sentence is enough: the activity, the place, roughly when, and your budget." },
  { icon: Handshake, title: "Agents do the talking", text: "Your agent finds people who fit and bargains with the shops' agents. Your private wishes stay private." },
  { icon: CircleCheckBig, title: "You say yes", text: "You see the final plan and price. Nothing is booked or paid until every person approves." },
];

const MODES: Record<Mode, { label: string; icon: typeof Users; line: string; cta: string }> = {
  group: {
    label: "With others", icon: Users, cta: "Find my people",
    line: "Your agent finds people who want the same trip. Everyone's agent then agrees on one plan and one price with the shop.",
  },
  solo: {
    label: "Just me", icon: User, cta: "Find my deal",
    line: "Your agent bargains with every shop directly and looks for trips already running that you can join at the group price.",
  },
};

export default function Home() {
  const router = useRouter();
  const { me } = usePersona();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [deals, setDeals] = useState<DealSummary[] | null>(null);
  const keyRef = useRef(newKey());
  const [mode, setModeState] = useState<Mode>("group");
  useEffect(() => {
    try {
      if (localStorage.getItem(MODE_KEY) === "solo") setModeState("solo");
    } catch {}
  }, []);
  const setMode = (m: Mode) => {
    setModeState(m);
    try {
      localStorage.setItem(MODE_KEY, m);
    } catch {}
  };

  useEffect(() => {
    if (!me) return;
    setGoals(null);
    setDeals(null);
    api<Goal[]>("/v1/goals").then(setGoals).catch(() => setGoals([]));
    api<DealSummary[]>("/v1/deals").then(setDeals).catch(() => setDeals([]));
  }, [me]);

  async function submit() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const g = await api<Goal>("/v1/goals:compile", {
        body: { text, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
        idempotencyKey: keyRef.current,
      });
      keyRef.current = newKey();
      router.push(`/goals/${g.id}/review`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-6">
        <section className="chart-field relative overflow-hidden rounded-[28px] border border-line px-5 pb-8 pt-9 shadow-card sm:px-10 sm:pb-10 sm:pt-12">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-buoy-soft px-3 py-1 text-[12px] font-semibold text-[#7a5200]">
            <Sparkles size={13} /> Your own AI travel agent
          </span>
          <h1 className="buoy-rise mt-4 max-w-[16ch] text-[40px] font-semibold leading-[44px] tracking-[-0.035em] sm:text-[56px] sm:leading-[58px]">
            Tell your agent where you want to go.
          </h1>
          <p className="mt-4 max-w-[56ch] text-[17px] leading-7 text-muted">
            It finds people to go with and bargains with the shops for you, so you get a group price even on your own.
            Nothing is booked until you say yes.
          </p>

          <div role="radiogroup" aria-label="Who is going" className="mt-8 inline-flex rounded-full border border-line bg-surface p-1 shadow-card">
            {(Object.keys(MODES) as Mode[]).map((m) => {
              const M = MODES[m];
              return (
                <button
                  key={m}
                  role="radio"
                  aria-checked={mode === m}
                  onClick={() => setMode(m)}
                  className={cx(
                    "inline-flex h-10 items-center gap-2 rounded-full px-5 text-[14px] font-medium transition-colors",
                    mode === m ? "bg-accent text-accent-ink" : "text-muted hover:text-ink",
                  )}
                >
                  <M.icon size={16} strokeWidth={1.9} /> {M.label}
                </button>
              );
            })}
          </div>
          <p className="mt-3 max-w-[60ch] text-[14px] text-ink/75">{MODES[mode].line}</p>

          <Card className="mt-5 p-2 shadow-pop transition-colors focus-within:border-accent">
            <label htmlFor="goal" className="sr-only">Your goal</label>
            <textarea
              id="goal"
              autoFocus
              rows={3}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
              }}
              placeholder="Scuba diving in Monterey next month, under $300. I'm Open Water certified."
              className="w-full resize-none bg-transparent px-3 py-2.5 text-[17px] leading-7 no-ring outline-none placeholder:text-muted/60"
              maxLength={1000}
            />
            <div className="flex items-center justify-between gap-3 px-2 pb-1">
              <span className="hidden items-center gap-1 text-[12px] text-muted sm:flex">
                <kbd className="rounded border border-line bg-surface-2 px-1 font-mono text-[11px]">Ctrl</kbd>
                <span>+</span>
                <CornerDownLeft size={12} /> to send
              </span>
              <Button onClick={submit} disabled={!text.trim() || busy || !me} className="h-11 px-6 text-[15px]">
                {busy ? "Reading your goal…" : MODES[mode].cta}
                <ArrowRight size={16} strokeWidth={2} />
              </Button>
            </div>
          </Card>
          {err && (
            <div className="mt-3">
              <Callout tone="danger" title="Couldn't read that goal">
                {err} <button className="underline" onClick={submit}>Try again</button>
              </Callout>
            </div>
          )}

          <div className="mt-6 text-[13px] font-medium text-muted">Not sure what to write? Tap one:</div>
          <div className="mt-2 grid gap-2 sm:grid-cols-3">
            {EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                onClick={() => setText(ex.text)}
                className={cx(
                  "flex items-start gap-3 rounded-[14px] border bg-surface p-3 text-left transition-all hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-card",
                  text === ex.text ? "border-accent ring-1 ring-accent" : "border-line",
                )}
              >
                <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-accent-soft text-accent">
                  <ex.icon size={17} strokeWidth={1.9} />
                </span>
                <span className="min-w-0">
                  <span className="block text-[14px] font-semibold">{ex.label}</span>
                  <span className="block text-[12px] leading-[17px] text-muted">{ex.hint}</span>
                </span>
              </button>
            ))}
          </div>
        </section>

        <section aria-labelledby="how" className="rounded-[24px] border border-line bg-surface p-5 shadow-card sm:p-7">
          <h2 id="how" className="text-[20px] font-semibold tracking-[-0.01em]">How it works</h2>
          <ol className="mt-4 grid gap-5 sm:grid-cols-3">
            {HOW.map((h, i) => (
              <li key={h.title} className="flex gap-3">
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
                  <h.icon size={18} strokeWidth={1.9} />
                </span>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Step {i + 1}</div>
                  <div className="font-semibold">{h.title}</div>
                  <p className="mt-0.5 text-[13px] leading-5 text-muted">{h.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <aside className="space-y-6">
        <Card>
          <CardHeader icon={<Luggage size={16} />} title="Your trips" meta={deals?.length ? `${deals.length} so far` : undefined} />
          <ul className="divide-y divide-line">
            {deals === null && (
              <li className="p-5">
                <Skeleton className="h-10" />
              </li>
            )}
            {deals?.length === 0 && <li className="px-5 py-5 text-[14px] text-muted">No trips yet. Describe one and your agent gets to work.</li>}
            {deals?.map((d) => (
              <li key={d.id}>
                <Link href={`/deals/${d.id}`} className="group flex items-center justify-between gap-3 px-5 py-3.5 transition-colors hover:bg-accent-soft/40">
                  <div className="min-w-0">
                    <div className="truncate font-medium group-hover:text-accent">{d.title}</div>
                    <div className="num text-[12px] text-muted">
                      {d.memberCount === 1 ? "Solo" : `${d.memberCount} people`} · round {d.round} of {d.maxRounds}
                    </div>
                  </div>
                  <StatusPill status={d.status} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader icon={<Target size={16} />} title="Your goals" />
          <ul className="divide-y divide-line">
            {goals === null && (
              <li className="p-5">
                <Skeleton className="h-10" />
              </li>
            )}
            {goals?.length === 0 && (
              <li className="px-5 py-4">
                <button onClick={() => setText(EXAMPLES[0].text)} className="flex w-full items-center gap-3 text-left">
                  <span className="rounded-full bg-accent-soft p-2 text-accent">
                    <Waves size={16} strokeWidth={1.75} />
                  </span>
                  <span>
                    <span className="block font-medium">Try the scuba demo</span>
                    <span className="text-[13px] text-muted">Five divers, two shops, one plan.</span>
                  </span>
                </button>
              </li>
            )}
            {goals?.map((g) => (
              <li key={g.id}>
                <Link
                  href={g.status === "published" ? `/goals/${g.id}/matches` : `/goals/${g.id}/review`}
                  className="flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-accent-soft/40"
                >
                  <span className="line-clamp-2 min-w-0 text-[13px]">{g.text}</span>
                  <StatusPill status={g.status} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <AsiOneCard />
        <VendorSearch />
      </aside>
    </div>
  );
}
