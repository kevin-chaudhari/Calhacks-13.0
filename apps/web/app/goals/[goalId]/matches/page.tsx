"use client";

import { useParams, useRouter } from "next/navigation";
import { Check, ChevronDown, Users } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import type { Goal, MatchCard, MatchResult } from "@/lib/types";
import { Avatar, Button, Callout, Card, Chip, PageTitle, Skeleton, cx } from "@/components/ui/primitives";

function FitBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2" aria-label={`Fit ${Math.round(score * 100)}%`}>
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-2">
        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(score * 100)}%` }} />
      </div>
      <span className="num font-mono text-[12px] text-muted">{Math.round(score * 100)}</span>
    </div>
  );
}

function Candidate({ c, picked, toggle }: { c: MatchCard; picked: boolean; toggle: () => void }) {
  return (
    <button
      onClick={toggle}
      aria-pressed={picked}
      className={cx(
        "flex w-full items-start gap-3 rounded-[10px] border bg-surface p-4 text-left transition-colors",
        picked ? "border-accent" : "border-line hover:border-muted/50",
      )}
    >
      <Avatar initials={c.initials} demo={c.isDemoPersona} size={36} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold">{c.name}</span>
          <span className="ml-auto">
            {picked ? (
              <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-accent text-accent-ink"><Check size={13} /></span>
            ) : (
              <span className="inline-flex h-5 w-5 rounded-full border border-line" />
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

  useEffect(() => {
    if (!me) return;
    (async () => {
      try {
        const g = await api<Goal>(`/v1/goals/${goalId}`);
        setGoal(g);
        if (!g.intentId) throw new ApiError(409, "NOT_PUBLISHED", "Publish this goal first.");
        const m = await api<MatchResult>(`/v1/intents/${g.intentId}/matches`, { body: {} });
        setRes(m);
        setPicked(m.selectedIntentIds);
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

  const max = (goal?.draft.groupMax ?? 5) - 1;
  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < max ? [...p, id] : p));

  return (
    <>
      <PageTitle eyebrow="Step 2 of 4 · Find your people" title="Compatible people">
        Everyone below passed every hard condition. Ranking only reorders them; it can never admit someone who failed one.
      </PageTitle>

      {err && <div className="mb-6"><Callout tone="danger" title="Something's off">{err}</Callout></div>}

      {res && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          {res.hardFilters.map((f) => (
            <Chip key={f} tone="accent">{f}</Chip>
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
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div>
            <div className="grid gap-3 md:grid-cols-2">
              {res.matches.map((c) => (
                <Candidate key={c.intentId} c={c} picked={picked.includes(c.intentId)} toggle={() => toggle(c.intentId)} />
              ))}
            </div>
            {res.matches.length === 0 && <Callout tone="neutral" title="No one fits yet">Widen your dates or radius and publish again.</Callout>}

            <Card className="mt-6">
              <button
                onClick={() => setShowRejected((s) => !s)}
                aria-expanded={showRejected}
                className="flex w-full items-center justify-between px-5 py-3 text-left"
              >
                <span className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Not a match ({res.rejections.length})</span>
                <ChevronDown size={16} className={cx("text-muted transition-transform", showRejected && "rotate-180")} />
              </button>
              {showRejected && (
                <ul className="divide-y divide-line border-t border-line">
                  {res.rejections.map((r) => (
                    <li key={r.intentId} className="flex items-center gap-3 px-5 py-2.5">
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

          <div className="lg:sticky lg:top-20 lg:self-start">
            <Card className="p-5">
              <div className="flex items-center gap-2 text-[13px] text-muted"><Users size={14} /> Your group</div>
              <div className="num mt-1 text-[28px] font-semibold leading-[34px]">{picked.length + 1} people</div>
              <div className="text-[13px] text-muted">You plus {picked.length} · max {max + 1}</div>
              <div className="mt-4 flex -space-x-2">
                {me && <Avatar initials={me.initials} />}
                {res.matches.filter((m) => picked.includes(m.intentId)).map((m) => (
                  <Avatar key={m.intentId} initials={m.initials} demo={m.isDemoPersona} />
                ))}
              </div>
              <Button className="mt-5 h-10 w-full" onClick={start} disabled={busy || picked.length < 1}>
                {busy ? "Inviting agents…" : `Start group with ${picked.length}`}
              </Button>
              <p className="mt-3 text-[12px] text-muted">Each person&apos;s agent decides whether to join under its owner&apos;s rules.</p>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
