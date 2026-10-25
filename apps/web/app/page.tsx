"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Anchor, ArrowRight, CornerDownLeft, Plane, User, Users, Waves } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import type { DealSummary, Goal } from "@/lib/types";
import { Button, Callout, Card, Skeleton, cx } from "@/components/ui/primitives";
import { StatusPill } from "@/components/rally/shell";
import { AsiOneCard, VendorSearch } from "@/components/rally/platform";
import { MODE_KEY, type Mode } from "@/lib/mode";

const EXAMPLES = [
  { label: "Scuba in Monterey", icon: Anchor, text: "I want to go scuba diving in Monterey next month for under $300. I am Open Water certified." },
  { label: "Skydiving, Santa Cruz", icon: Plane, text: "I want to go skydiving near Santa Cruz next month for under $400, first jump." },
  { label: "Sea kayaking", icon: Waves, text: "Sea kayaking in Monterey next month, under $120 per person." },
];


const MODES: Record<Mode, { label: string; icon: typeof Users; line: string; cta: string }> = {
  group: {
    label: "With others", icon: Users, cta: "Find my people",
    line: "Your agent finds people who want the same trip. Everyone's agent then agrees on one plan and one price with the shop.",
  },
  solo: {
    label: "Just me", icon: User, cta: "Find my deal",
    line: "Your agent negotiates with every shop directly and looks for trips already running that you can join at the group rate.",
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
      <section className="chart-field relative overflow-hidden rounded-[24px] border border-line px-5 pb-8 pt-10 sm:px-10 sm:pb-10 sm:pt-14">
        <h1 className="buoy-rise max-w-[15ch] text-[44px] font-semibold leading-[46px] tracking-[-0.035em] sm:text-[60px] sm:leading-[60px]">
          Tell your agent where you want to go.
        </h1>
        <p className="mt-4 max-w-[56ch] text-[16px] leading-6 text-muted">
          It finds the people and negotiates with the shops&apos; agents, so you get a group price whether you bring
          friends or go on your own. Nothing is booked until you approve it.
        </p>

        <div role="radiogroup" aria-label="Who is going" className="mt-8 inline-flex rounded-[12px] border border-line bg-surface p-1">
          {(Object.keys(MODES) as Mode[]).map((m) => {
            const M = MODES[m];
            return (
              <button
                key={m}
                role="radio"
                aria-checked={mode === m}
                onClick={() => setMode(m)}
                className={cx(
                  "inline-flex h-9 items-center gap-2 rounded-[9px] px-4 text-[14px] font-medium transition-colors",
                  mode === m ? "bg-ink text-bg" : "text-muted hover:text-ink",
                )}
              >
                <M.icon size={15} strokeWidth={1.9} /> {M.label}
              </button>
            );
          })}
        </div>
        <p className="mt-3 max-w-[60ch] text-[14px] text-ink/80">{MODES[mode].line}</p>

        <Card className="mt-5 p-2 shadow-[0_1px_0_var(--line)] focus-within:border-accent">
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
            className="w-full resize-none bg-transparent px-3 py-2.5 text-[17px] leading-7 no-ring outline-none placeholder:text-muted/70"
            maxLength={1000}
          />
          <div className="flex items-center justify-between gap-3 px-2 pb-1">
            <span className="hidden items-center gap-1 text-[12px] text-muted sm:flex">
              <kbd className="rounded border border-line px-1 font-mono text-[11px]">⌘</kbd>
              <CornerDownLeft size={12} /> to send
            </span>
            <Button onClick={submit} disabled={!text.trim() || busy || !me} className="h-10 px-5">
              {busy ? "Reading your goal…" : MODES[mode].cta}
              <ArrowRight size={16} strokeWidth={1.75} />
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
        <div className="mt-4 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              onClick={() => setText(ex.text)}
              className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-muted hover:border-ink hover:text-ink"
            >
              <ex.icon size={13} strokeWidth={1.9} /> {ex.label}
            </button>
          ))}
        </div>
      </section>

      <aside className="space-y-6">
        <AsiOneCard />
        <Card>
          <div className="border-b border-line px-5 py-3.5 text-[16px] font-semibold display">Your trips</div>
          <ul className="divide-y divide-line">
            {deals === null && (
              <li className="p-5">
                <Skeleton className="h-10" />
              </li>
            )}
            {deals?.length === 0 && <li className="px-5 py-4 text-[13px] text-muted">No trips yet. Describe one on the left.</li>}
            {deals?.map((d) => (
              <li key={d.id}>
                <Link href={`/deals/${d.id}`} className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-surface-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{d.title}</div>
                    <div className="num text-[12px] text-muted">
                      {d.memberCount === 1 ? "Solo" : `${d.memberCount} people`}, round {d.round} of {d.maxRounds}
                    </div>
                  </div>
                  <StatusPill status={d.status} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <div className="border-b border-line px-5 py-3.5 text-[16px] font-semibold display">Your goals</div>
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
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-surface-2"
                >
                  <span className="line-clamp-2 min-w-0 text-[13px]">{g.text}</span>
                  <StatusPill status={g.status} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <VendorSearch />
      </aside>
    </div>
  );
}
