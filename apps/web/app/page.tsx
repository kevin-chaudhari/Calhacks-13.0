"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, CornerDownLeft, Waves } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import type { DealSummary, Goal } from "@/lib/types";
import { Button, Callout, Card, Skeleton } from "@/components/ui/primitives";
import { StatusPill } from "@/components/rally/shell";

const EXAMPLES = [
  { label: "Scuba trip in Monterey", text: "I want to go scuba diving in Monterey next month for under $300. I am Open Water certified." },
  { label: "Skydiving near Santa Cruz", text: "I want to go skydiving near Santa Cruz next month for under $400, first jump." },
  { label: "Sea kayaking in Monterey", text: "Sea kayaking in Monterey next month, under $120 per person." },
  { label: "Tennis partner this week", text: "Tennis partner, 3.5 level, weekday evenings near Berkeley." },
];

export default function Home() {
  const router = useRouter();
  const { me } = usePersona();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [deals, setDeals] = useState<DealSummary[] | null>(null);
  const keyRef = useRef(newKey());

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
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div>
        <h1 className="max-w-xl text-[34px] font-semibold leading-[40px] tracking-[-0.02em]">
          Tell Rally what you want to do.
          <span className="block text-muted">Your agent finds your people.</span>
        </h1>
        <p className="mt-3 max-w-xl text-muted">
          Agents find compatible people, agree on one plan without exposing anyone&apos;s private preferences, and get a group
          price. Nothing is booked or paid until every person approves.
        </p>

        <Card className="mt-8 p-2 focus-within:border-accent">
          <label htmlFor="goal" className="sr-only">
            Your goal
          </label>
          <textarea
            id="goal"
            autoFocus
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
            }}
            placeholder="I want to go scuba diving in Monterey next month for under $300…"
            className="w-full resize-none bg-transparent px-3 py-2.5 text-[16px] leading-6 outline-none placeholder:text-muted/70"
            maxLength={1000}
          />
          <div className="flex items-center justify-between gap-3 px-2 pb-1">
            <span className="hidden items-center gap-1 text-[12px] text-muted sm:flex">
              <kbd className="rounded border border-line px-1 font-mono text-[11px]">⌘</kbd>
              <CornerDownLeft size={12} /> to compile
            </span>
            <Button onClick={submit} disabled={!text.trim() || busy || !me}>
              {busy ? "Compiling…" : "Find my people"}
              <ArrowRight size={16} strokeWidth={1.75} />
            </Button>
          </div>
        </Card>
        {err && (
          <div className="mt-3">
            <Callout tone="danger" title="Couldn't compile that goal">
              {err} <button className="underline" onClick={submit}>Try again</button>
            </Callout>
          </div>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              onClick={() => setText(ex.text)}
              className="rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-muted hover:border-accent hover:text-ink"
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <aside className="space-y-6">
        <Card>
          <div className="border-b border-line px-5 py-3 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Your deals</div>
          <ul className="divide-y divide-line">
            {deals === null && (
              <li className="p-5">
                <Skeleton className="h-10" />
              </li>
            )}
            {deals?.length === 0 && <li className="px-5 py-4 text-[13px] text-muted">No deals yet. Publish a goal and start a group.</li>}
            {deals?.map((d) => (
              <li key={d.id}>
                <Link href={`/deals/${d.id}`} className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-surface-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{d.title}</div>
                    <div className="num text-[12px] text-muted">
                      {d.memberCount} people · round {d.round} of {d.maxRounds}
                    </div>
                  </div>
                  <StatusPill status={d.status} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <div className="border-b border-line px-5 py-3 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Your goals</div>
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
      </aside>
    </div>
  );
}
