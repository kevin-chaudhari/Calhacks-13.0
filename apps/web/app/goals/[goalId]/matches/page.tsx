"use client";

import { useParams, useRouter } from "next/navigation";
import { ArrowRight, Check, ChevronDown, User, Users } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import type { Goal, MatchCard, MatchResult } from "@/lib/types";
import { readMode } from "@/lib/mode";
import { Avatar, Button, Callout, Card, Chip, FlowSteps, PageTitle, Skeleton, cx } from "@/components/ui/primitives";

function FitBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2" aria-label={`Fit ${Math.round(score * 100)}%`}>
      <span className="text-[12px] text-muted">Fit</span>
      <div className="h-2 w-24 overflow-hidden rounded-full bg-surface-2">
        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(score * 100)}%` }} />
      </div>
      <span className="num font-mono text-[12px] text-muted">{Math.round(score * 100)}%</span>
    </div>
  );
}

function Candidate({ c, picked, toggle }: { c: MatchCard; picked: boolean; toggle: () => void }) {
  return (
    <button
      onClick={toggle}
      aria-pressed={picked}
      className={cx(
        "flex w-full items-start gap-3 rounded-[16px] border bg-surface p-4 text-left shadow-card transition-all",
        picked ? "border-accent ring-1 ring-accent" : "border-line hover:-translate-y-0.5 hover:border-accent/40",
      )}
    >
      <Avatar initials={c.initials} demo={c.isDemoPersona} size={40} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold">{c.name}</span>
          <span className="ml-auto">
            {picked ? (
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-accent text-accent-ink"><Check size={14} strokeWidth={2.5} /></span>
            ) : (
              <span className="inline-flex h-6 w-6 rounded-full border-2 border-line" />
            )}
          </span>
        </div>
        <div className="num mt-0.5 text-[13px] text-muted">{c.reason}</div>
        <p className="mt-2 line-clamp-2 text-[13px]">&ldquo;{c.text}&rdquo;</p>
        <div className="mt-3">
          <FitBar score={c.score} />
        </div>
      </div>
    </button>
  );
}

function SoloCard({ primary, note, busy, onGo }: { primary: boolean; note?: string; busy: boolean; onGo: () => void }) {
  return (
    <Card className={cx("p-5", primary && "border-accent ring-1 ring-accent")}>
      <div className="flex items-center gap-2 text-[13px] font-medium text-muted"><User size={15} /> Just me</div>
      <div className="display mt-1 text-[24px] font-semibold leading-[30px] tracking-[-0.02em]">Go solo</div>
      <p className="mt-1 text-[14px] text-muted">
        Your agent bargains with every shop for you alone, and looks for trips already running that you can join at the group price.
      </p>
      {note && <p className="mt-2 text-[12px] text-muted">{note}</p>}
      <Button className="mt-4 h-11 w-full" variant={primary ? "primary" : "secondary"} onClick={onGo} disabled={busy}>
        {busy && primary ? "Asking the shops…" : "Go solo"} <ArrowRight size={15} />
      </Button>
    </Card>
  );
}

function GroupCard({ primary, picked, max, busy, me, people, onStart }: {
  primary: boolean; picked: number; max: number; busy: boolean;
  me: { initials: string } | null; people: MatchCard[]; onStart: () => void;
}) {
  return (
    <Card className={cx("p-5", primary && "border-accent ring-1 ring-accent")}>
      <div className="flex items-center gap-2 text-[13px] font-medium text-muted"><Users size={15} /> Your group</div>
      <div className="num display mt-1 text-[28px] font-semibold leading-[34px]">{picked + 1} {picked ? "people" : "person"}</div>
      <div className="text-[13px] text-muted">You plus {picked}, up to {max + 1}. Tap people on the left to add them.</div>
      <div className="mt-4 flex -space-x-2">
        {me && <Avatar initials={me.initials} size={36} />}
        {people.map((m) => (
          <Avatar key={m.intentId} initials={m.initials} demo={m.isDemoPersona} size={36} />
        ))}
      </div>
      <Button className="mt-5 h-11 w-full" variant={primary ? "primary" : "secondary"} onClick={onStart} disabled={busy || picked < 1}>
        {busy && primary ? "Inviting agents…" : picked < 1 ? "Pick at least one person" : `Start a group of ${picked + 1}`}
        {picked >= 1 && !busy && <ArrowRight size={15} />}
      </Button>
      <p className="mt-3 text-[12px] text-muted">Each person&apos;s agent decides whether to join, following its owner&apos;s rules.</p>
    </Card>
  );
}

export default function Matches() {
  const { goalId } = useParams<{ goalId: string }>();
  const router = useRouter();
  const { me } = usePersona();
  const [goal, setGoal] = useState<Goal | null>(null);
  const [res, setRes] = useState<MatchResult | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRejected, setShowRejected] = useState(false);
  const dealKey = useRef(newKey());
  const [preferSolo, setPreferSolo] = useState(false);
  useEffect(() => setPreferSolo(readMode() === "solo"), []);

  useEffect(() => {
    if (!me) return;
    (async () => {
      try {
        const g = await api<Goal>(`/v1/goals/${goalId}`);
        setGoal(g);
        if (!g.intentId) throw new ApiError(409, "NOT_PUBLISHED", "Publish this goal first.");
        const m = await api<MatchResult>(`/v1/intents/${g.intentId}/matches`, { body: {} });
        setRes(m);
        const withId = new URLSearchParams(window.location.search).get("with");
        const base = readMode() === "solo" && !withId ? [] : m.selectedIntentIds;
        setPicked(withId && m.matches.some((c) => c.intentId === withId) && !base.includes(withId)
          ? [withId, ...base].slice(0, Math.max(1, (g.draft.groupMax ?? 2) - 1)) : base);
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : "Matching failed.");
      }
    })();
  }, [goalId, me]);

  async function start() {
    if (!goal?.intentId) return;
    setBusy(true);
    try {
      const deal = await api<{ id: string }>(`/v1/deals`, {
        body: { intentId: goal.intentId, candidateIntentIds: picked },
        idempotencyKey: dealKey.current,
      });
      router.push(`/deals/${deal.id}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't start the group.");
      setBusy(false);
    }
  }

  async function goSolo() {
    if (!goal?.intentId) return;
    setBusy(true);
    try {
      const deal = await api<{ id: string }>(`/v1/deals`, {
        body: { intentId: goal.intentId, candidateIntentIds: [], solo: true },
        idempotencyKey: dealKey.current,
      });
      router.push(`/deals/${deal.id}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't start your solo trip.");
      setBusy(false);
    }
  }

  const max = Math.max(1, (goal?.draft.groupMax ?? 5) - 1);
  const nobody = res !== null && res.matches.length === 0;
  const soloFirst = nobody || preferSolo;
  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < max ? [...p, id] : p));

  const solo = (
    <SoloCard
      key="solo"
      primary={soloFirst}
      busy={busy}
      onGo={goSolo}
      note={goal?.draft.groupMax === 1 && !nobody ? "You chose to go alone. To go with the people on the left, set a bigger group size on the previous step." : undefined}
    />
  );
  const group = res && !nobody && (
    <GroupCard
      key="group"
      primary={!soloFirst}
      picked={picked.length}
      max={max}
      busy={busy}
      me={me}
      people={res.matches.filter((m) => picked.includes(m.intentId))}
      onStart={start}
    />
  );

  return (
    <>
      <FlowSteps at={2} />
      <PageTitle title={nobody ? "Nobody fits yet, so go solo" : "People who want the same trip"}>
        {nobody
          ? "No one passed your must-haves this time. Your agent can still bargain with every shop for you alone."
          : "Everyone here passed all your must-haves. Tap the people you'd like to go with."}
      </PageTitle>

      {err && <div className="mb-6"><Callout tone="danger" title="Something's off">{err}</Callout></div>}

      {res && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          {res.hardFilters.map((f) => (
            <Chip key={f} tone="accent"><Check size={12} /> {f}</Chip>
          ))}
          <Chip tone="sim" title={res.rankerNote}>{res.ranker === "local" ? "Ranked locally" : "Ranked by Moss"}</Chip>
        </div>
      )}

      {!res && !err && (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36" />)}
        </div>
      )}

      {res && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div>
            <div className="grid gap-3 md:grid-cols-2">
              {res.matches.map((c) => (
                <Candidate key={c.intentId} c={c} picked={picked.includes(c.intentId)} toggle={() => toggle(c.intentId)} />
              ))}
            </div>
            {nobody && (
              <Callout tone="neutral" title="Want company instead?">Widen your dates, budget or distance and publish again; new people join all the time.</Callout>
            )}

            <Card className="mt-6">
              <button
                onClick={() => setShowRejected((s) => !s)}
                aria-expanded={showRejected}
                className="flex w-full items-center justify-between px-5 py-3.5 text-left"
              >
                <span className="text-[14px] font-semibold text-muted">Not a match ({res.rejections.length}) · see why</span>
                <ChevronDown size={16} className={cx("text-muted transition-transform", showRejected && "rotate-180")} />
              </button>
              {showRejected && (
                <ul className="divide-y divide-line border-t border-line">
                  {res.rejections.map((r) => (
                    <li key={r.intentId} className="flex flex-wrap items-center gap-3 px-5 py-2.5">
                      <Avatar initials={r.initials} demo={r.isDemoPersona} size={28} />
                      <span className="w-16 font-medium">{r.name}</span>
                      <span className="flex-1 text-[13px] text-muted">{r.reason}</span>
                      <Chip tone="danger">{r.failedConstraint}</Chip>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="space-y-4 lg:sticky lg:top-24 lg:self-start">
            {soloFirst ? [solo, group] : [group, solo]}
          </div>
        </div>
      )}
    </>
  );
}
