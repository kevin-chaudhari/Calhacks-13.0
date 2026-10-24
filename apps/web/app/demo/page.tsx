"use client";

// Control room: what the presenter drives on the big screen. Adapter lights, one-click scenarios,
// live measured metrics, and QR seats so judges act from their own phones.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Anchor, Mountain, Plane, RotateCcw, Waves } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Button, Callout, Card, CardHeader, Chip, PageTitle, Skeleton } from "@/components/ui/primitives";
import { AdapterLights, MetricsGrid, SeatsPanel, useMetrics } from "@/components/rally/platform";

interface Health {
  ok: boolean;
  adapters: Record<string, string>;
  convex: { enabled: boolean; errors?: number; writes?: number; pending?: number };
  restored: boolean;
  payments: { mode: string; network?: string; settled?: number; failures?: number; wallets?: string[] };
  agents: { personal: number; providers: number };
}

const SCENARIOS = [
  { id: "scuba", title: "Scuba in Monterey", blurb: "Five divers, certification and budget limits, a dive shop's binding quote.", icon: Anchor },
  { id: "skydiving", title: "Skydiving, Santa Cruz", blurb: "First jumps: weight limits and weather windows decide the date.", icon: Plane },
  { id: "kayaking", title: "Sea kayaking", blurb: "A cheaper trip where group size changes the price most.", icon: Waves },
] as const;

export default function ControlRoom() {
  const router = useRouter();
  const { me } = usePersona();
  const metrics = useMetrics();
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lastDeal, setLastDeal] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      api<Health>("/v1/health", { token: null })
        .then((h) => alive && (setHealth(h), setDown(false)))
        .catch(() => alive && setDown(true));
    tick();
    const t = setInterval(tick, 3000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  async function launch(scenario: string) {
    setBusy(scenario);
    setErr(null);
    try {
      const r = await api<{ dealId: string }>("/v1/demo/launch", { body: { scenario, autoNegotiate: true } });
      setLastDeal(r.dealId);
      router.push(`/deals/${r.dealId}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Launch failed.");
    } finally {
      setBusy(null);
    }
  }

  async function reset() {
    setBusy("reset");
    setErr(null);
    try {
      await api("/v1/demo/reset", { body: { scenario: "scuba" }, token: null });
      setLastDeal(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Reset failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageTitle title="Control room">Start a group in one click, watch the agents work, and hand judges a seat on their own phone.</PageTitle>
      {down && <div className="mb-4"><Callout tone="danger" title="API unreachable">Check the API server, then this page reconnects by itself.</Callout></div>}
      {err && <div className="mb-4"><Callout tone="danger" title="Didn't work">{err}</Callout></div>}

      <section className="mb-6">
        <h2 className="mb-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Sponsor tech, live or fallback</h2>
        {health ? (
          <>
            <AdapterLights adapters={{ ...health.adapters, payments: health.payments.mode }} convexErrors={health.convex.errors} />
            <div className="mt-2 flex flex-wrap gap-2 text-[12px]">
              <Chip>{health.agents.personal} personal agents · {health.agents.providers} vendor agents</Chip>
              {health.convex.enabled ? <Chip tone="accent">Convex: {health.convex.writes ?? 0} writes, {health.convex.pending ?? 0} queued</Chip> : <Chip tone="warn">Convex off: in-memory store</Chip>}
              {health.restored && <Chip tone="accent">State restored after restart</Chip>}
              {health.payments.mode === "x402_testnet" && <Chip tone="sim">x402 · {health.payments.network} · {health.payments.settled ?? 0} settled</Chip>}
            </div>
          </>
        ) : (
          <Skeleton className="h-16" />
        )}
      </section>

      <section className="mb-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Launch a scenario as {me?.name ?? "…"}</h2>
          <Button variant="secondary" onClick={reset} disabled={busy !== null}><RotateCcw size={14} /> {busy === "reset" ? "Resetting…" : "Reset everything"}</Button>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          {SCENARIOS.map((s) => (
            <Card key={s.id}>
              <div className="flex h-full flex-col gap-3 p-4">
                <div className="flex items-center gap-2 font-semibold"><s.icon size={16} className="text-accent" /> {s.title}</div>
                <p className="flex-1 text-[13px] text-muted">{s.blurb}</p>
                <Button onClick={() => launch(s.id)} disabled={busy !== null || !me}>{busy === s.id ? "Agents matching…" : "Launch"}</Button>
              </div>
            </Card>
          ))}
        </div>
        <p className="mt-2 text-[12px] text-muted">Launch compiles the goal, matches people, invites their agents and starts the negotiation. Every step is the real pipeline.</p>
      </section>

      <section className="mb-6">
        <h2 className="mb-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Measured live</h2>
        {metrics ? <MetricsGrid m={metrics} /> : <Skeleton className="h-24" />}
      </section>

      {lastDeal && (
        <section className="mb-6">
          <SeatsPanel dealId={lastDeal} />
          <div className="mt-2"><Link href={`/deals/${lastDeal}`} className="text-[13px] text-accent underline">Open the group room</Link></div>
        </section>
      )}

      <Card>
        <CardHeader title={<span className="flex items-center gap-1.5"><Mountain size={13} /> Judge script</span>} />
        <ol className="list-decimal space-y-1 px-9 py-4 text-[14px]">
          <li>Launch scuba. The room fills as five personal agents accept the invite.</li>
          <li>Hand a judge a phone seat from the room (QR button). They approve or ask for a change as that member.</li>
          <li>Hand another judge the vendor seat. They approve the binding quote from the vendor portal.</li>
          <li>Everyone approves; deposits commit and the plan goes to calendars.</li>
          <li>Scrub the replay to show why each version changed. Point at zero hard-constraint violations above.</li>
        </ol>
      </Card>
    </>
  );
}
