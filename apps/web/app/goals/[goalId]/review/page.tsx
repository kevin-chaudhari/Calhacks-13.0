"use client";

import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ListChecks, Lock, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { shortDay, TERM_LABELS, termValue } from "@/lib/format";
import type { Condition, Goal, MissingField, TermSpec } from "@/lib/types";
import { Button, Callout, Card, CardHeader, Chip, FlowSteps, PageTitle, Skeleton } from "@/components/ui/primitives";
import { readMode } from "@/lib/mode";

const KIND: Record<string, { label: string; tone: "accent" | "neutral" | "warn" | "sim" }> = {
  hard: { label: "Must have", tone: "accent" },
  prefer: { label: "Prefer", tone: "neutral" },
  unknown: { label: "Needs your input", tone: "warn" },
  provider: { label: "Provider decides", tone: "sim" },
};

function MissingInput({ m, onApply }: { m: MissingField; onApply: (patch: Record<string, unknown>) => void }) {
  const [v, setV] = useState("");
  const field = m.field;
  const apply = () => {
    if (!v) return;
    if (field === "groupMax") onApply({ groupMax: Number(v), groupMin: 2 });
    else if (field === "budgetMax") onApply({ budgetMax: Number(v) });
    else if (field === "certification") onApply({ certification: v });
    else if (field === "location") onApply({ place: v.toLowerCase() });
    else if (field === "dates") onApply({ dateFrom: v.split("..")[0], dateTo: v.split("..")[1] });
  };
  const suggestions = (m.suggestions ?? []) as (string | number)[];
  return (
    <div className="flex flex-wrap items-center gap-2 py-1.5">
      <span className="min-w-[220px] text-[13px] font-medium text-ink">{m.question}</span>
      {field === "certification" ? (
        <select aria-label={m.question} value={v} onChange={(e) => setV(e.target.value)} className="h-8 rounded-[6px] border border-line bg-surface px-2 text-[13px]">
          <option value="">Choose…</option>
          {["open_water", "advanced", "rescue", "divemaster"].map((c) => (
            <option key={c} value={c}>{c.replace("_", " ")}</option>
          ))}
        </select>
      ) : field === "dates" ? (
        <select aria-label={m.question} value={v} onChange={(e) => setV(e.target.value)} className="h-8 rounded-[6px] border border-line bg-surface px-2 text-[13px]">
          <option value="">Choose a window…</option>
          <option value="2026-10-31..2026-11-01">This weekend</option>
          <option value="2026-11-01..2026-11-30">Next month</option>
          <option value="2026-12-01..2026-12-31">December</option>
        </select>
      ) : (
        <>
          <input
            aria-label={m.question}
            value={v}
            onChange={(e) => setV(e.target.value)}
            inputMode={field === "location" ? "text" : "numeric"}
            className="h-8 w-28 rounded-[6px] border border-line bg-surface px-2 text-[13px]"
          />
          {field === "groupMax" && (
            <button onClick={() => onApply({ groupMax: 1, groupMin: 1 })} className="rounded-full border border-ink bg-surface px-2.5 py-0.5 text-[12px] font-medium text-ink hover:bg-buoy-soft">
              Just me
            </button>
          )}
          {suggestions.map((s) => (
            <button key={String(s)} onClick={() => setV(String(s))} className="rounded-full border border-line bg-surface px-2 py-0.5 text-[12px] text-muted hover:text-ink">
              {String(s)}
            </button>
          ))}
        </>
      )}
      <Button variant="secondary" className="h-8" onClick={apply} disabled={!v}>
        Apply
      </Button>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] items-start gap-4 px-5 py-3">
      <div className="text-[13px] text-muted">{label}</div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function ConditionRow({ c }: { c: Condition }) {
  const k = KIND[c.kind] ?? KIND.prefer;
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <span className="text-[13px]">
        {c.label || c.key}
        {c.source === "default" && <span className="ml-2 text-[12px] text-muted">default, shown for review</span>}
      </span>
      <Chip tone={k.tone}>{k.label}</Chip>
    </li>
  );
}

export default function Review() {
  const { goalId } = useParams<{ goalId: string }>();
  const router = useRouter();
  const { me } = usePersona();
  const [goal, setGoal] = useState<Goal | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [best, setBest] = useState<Record<string, unknown>>({});
  const pubKey = useRef(newKey());

  useEffect(() => {
    if (!me) return;
    api<Goal>(`/v1/goals/${goalId}`)
      .then(async (g) => {
        // "Just me" on the home page answers the group-size question for you
        if (readMode() === "solo" && g.status !== "published" && g.draft.missing.some((m) => m.field === "groupMax")) {
          g = await api<Goal>(`/v1/goals/${goalId}`, { method: "PATCH", body: { groupMax: 1, groupMin: 1 } });
        }
        setGoal(g);
        setWeights(g.suggestedPrefs.weights ?? {});
        setBest(g.suggestedPrefs.best ?? {});
      })
      .catch((e) => setErr(e.message));
  }, [goalId, me]);

  const terms: TermSpec[] = useMemo(() => goal?.draft.negotiableTerms ?? [], [goal]);
  const total = Object.values(weights).reduce((a, b) => a + b, 0) || 1;

  async function patch(p: Record<string, unknown>) {
    setErr(null);
    try {
      setGoal(await api<Goal>(`/v1/goals/${goalId}`, { method: "PATCH", body: p }));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message + (e.fields ? " " + Object.values(e.fields).join(" ") : "") : "Update failed.");
    }
  }

  async function publish() {
    if (!goal) return;
    setBusy(true);
    setErr(null);
    try {
      await api(`/v1/intents`, {
        body: { goalId, privatePrefs: { ...goal.suggestedPrefs, weights, best } },
        idempotencyKey: pubKey.current,
      });
      router.push(`/goals/${goalId}/matches`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Publish failed.");
      setBusy(false);
    }
  }

  if (err && !goal) return <Callout tone="danger" title="Couldn't load this goal">{err}</Callout>;
  if (!goal)
    return (
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <Skeleton className="h-[480px]" />
        <Skeleton className="h-[320px]" />
      </div>
    );

  const d = goal.draft;
  const missing = d.missing ?? [];
  const published = goal.status === "published";

  return (
    <>
      <FlowSteps at={1} />
      <PageTitle
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            Here&apos;s what your agent understood
            {goal.compiledBy === "gemini" ? (
              <Chip tone="accent"><Sparkles size={12} /> Compiled by Gemini</Chip>
            ) : (
              <Chip tone="sim" title="Rule-based template compiler (Gemini not configured or unavailable)">Compiled offline</Chip>
            )}
            {d.limitedSupport && <Chip tone="warn">Limited support</Chip>}
          </span>
        }
        title={d.activity.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())}
      >
        Check it looks right. &ldquo;Must have&rdquo; items are never traded away, and the sliders on the right stay secret between you and your agent.
      </PageTitle>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <blockquote className="rounded-[14px] border-l-4 border-accent bg-surface px-5 py-4 text-[16px] leading-6 shadow-card">
            <div className="mb-1 text-[12px] font-semibold uppercase tracking-wider text-muted">You said</div>
            &ldquo;{goal.text}&rdquo;
          </blockquote>

          {missing.length > 0 && (
            <div className="rounded-[14px] border border-warn/30 bg-warn-soft px-4 py-3">
              <div className="mb-1 flex items-center gap-2 text-[13px] font-semibold text-warn">
                <AlertTriangle size={14} /> {missing.length} {missing.length === 1 ? "thing" : "things"} to confirm before publishing
              </div>
              {missing.map((m) => (
                <MissingInput key={m.field} m={m} onApply={patch} />
              ))}
            </div>
          )}
          {goal.warnings?.map((w) => (
            <Callout key={w} tone="neutral" title={w} />
          ))}

          <Card>
            <CardHeader icon={<ListChecks size={16} />} title="Your trip details" meta={`Template: ${d.templateId.replace("_", " ")} · shape: ${d.shape.replace("_", " + ")}`} />
            <div className="divide-y divide-line">
              <Row label="Activity">
                <div className="flex flex-wrap gap-1.5">
                  <Chip tone="accent">{d.activity.replace(/_/g, " ")}</Chip>
                  {d.tags.map((t) => (
                    <Chip key={t}>{t}</Chip>
                  ))}
                </div>
              </Row>
              <Row label="Where">
                {d.location ? (
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-medium">{d.location.label}</span>
                    {d.radiusKm != null && (
                      <label className="flex items-center gap-2 text-[13px] text-muted">
                        within
                        <input
                          type="range" min={5} max={100} step={5} defaultValue={d.radiusKm}
                          disabled={published}
                          onMouseUp={(e) => patch({ radiusKm: Number((e.target as HTMLInputElement).value) })}
                          onKeyUp={(e) => patch({ radiusKm: Number((e.target as HTMLInputElement).value) })}
                          className="accent-[var(--accent)]" aria-label="Radius in km"
                        />
                        <span className="num font-mono">{d.radiusKm} km</span>
                      </label>
                    )}
                  </div>
                ) : <span className="text-muted">Not set</span>}
              </Row>
              <Row label="When">
                {d.dateFrom ? <span className="num font-medium">{shortDay(d.dateFrom)} – {shortDay(d.dateTo!)}</span> : <span className="text-muted">Not set</span>}
              </Row>
              <Row label="Budget">
                {d.budgetMax ? <span className="num font-medium">Up to ${d.budgetMax.amount.toFixed(0)} per person</span> : <span className="text-muted">Not set</span>}
              </Row>
              <Row label="Group size">
                {d.groupMax ? (
                  <span className="num font-medium">{d.groupMax === 1 ? "Just you, solo" : `${d.groupMin ?? 2} to ${d.groupMax} people, including you`}</span>
                ) : <span className="text-muted">Not set</span>}
              </Row>
              <Row label="Conditions">
                <ul className="divide-y divide-line/60">
                  {d.conditions.map((c, i) => (
                    <ConditionRow key={c.key + i} c={c} />
                  ))}
                </ul>
              </Row>
              <Row label="Negotiable">
                <div className="flex flex-wrap gap-1.5">
                  {terms.map((t) => (
                    <Chip key={t.key}>{t.label || TERM_LABELS[t.key] || t.key}</Chip>
                  ))}
                </div>
              </Row>
            </div>
          </Card>
        </div>

        <div className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <Card>
            <CardHeader
              icon={<Lock size={15} />}
              title="What matters most to you"
              meta="Secret: only your agent sees this. Slide up what you care about."
            />
            <div className="space-y-4 px-5 py-4">
              {terms.map((t) => {
                const w = weights[t.key] ?? 0;
                return (
                  <div key={t.key}>
                    <div className="flex items-baseline justify-between">
                      <label htmlFor={`w-${t.key}`} className="text-[13px] font-medium">{t.label || TERM_LABELS[t.key] || t.key}</label>
                      <span className="num font-mono text-[12px] text-muted">{Math.round((w / total) * 100)}%</span>
                    </div>
                    <input
                      id={`w-${t.key}`} type="range" min={0} max={1} step={0.05} value={w}
                      disabled={published}
                      onChange={(e) => setWeights({ ...weights, [t.key]: Number(e.target.value) })}
                      className="mt-1 w-full accent-[var(--accent)]"
                    />
                    {t.type !== "numeric" && t.options.length > 0 && (
                      <select
                        aria-label={`Preferred ${t.label || t.key}`}
                        value={String(best[t.key] ?? "")}
                        disabled={published}
                        onChange={(e) => {
                          const raw = e.target.value;
                          const val = raw === "true" ? true : raw === "false" ? false : raw;
                          setBest({ ...best, [t.key]: raw === "" ? undefined : val });
                        }}
                        className="mt-1 h-8 w-full rounded-[6px] border border-line bg-surface px-2 text-[13px]"
                      >
                        <option value="">No preference</option>
                        {t.options.map((o) => (
                          <option key={String(o)} value={String(o)}>Prefer {termValue(t.key, o)}</option>
                        ))}
                      </select>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>
          {err && <Callout tone="danger" title="Not saved">{err}</Callout>}
          <Button className="h-12 w-full text-[15px]" onClick={publish} disabled={busy || missing.length > 0 || published}>
            {published ? "Published" : busy ? "Publishing…" : missing.length ? `Answer ${missing.length} question${missing.length > 1 ? "s" : ""} to publish` : d.groupMax === 1 ? "Publish and ask the shops" : "Publish and find people"}
          </Button>
          {published && (
            <Button variant="secondary" className="w-full" onClick={() => router.push(`/goals/${goalId}/matches`)}>
              See matches
            </Button>
          )}
          <p className="text-[12px] text-muted">
            Publishing lists your public intent (activity, dates, area, budget cap, certification) on the board.
          </p>
        </div>
      </div>
    </>
  );
}
