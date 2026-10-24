"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import type { Diagnostics } from "@/lib/types";
import { Callout, Card, CardHeader, Chip, PageTitle, Skeleton } from "@/components/ui/primitives";
import { AgentConversation } from "@/components/rally/agents";

export default function DiagnosticsPage() {
  const { me } = usePersona();
  const [d, setD] = useState<Diagnostics | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!me) return;
    let alive = true;
    const tick = () =>
      api<Diagnostics>("/v1/diagnostics")
        .then((x) => alive && setD(x))
        .catch((e) => alive && setErr(e instanceof ApiError ? e.message : "API unreachable"));
    tick();
    const t = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [me]);

  return (
    <>
      <PageTitle title="Agents">Every agent, every message they exchanged, and which adapters are live or in fallback.</PageTitle>
      {err && <Callout tone="danger" title="Diagnostics unavailable">{err}</Callout>}
      {!d && !err && <Skeleton className="h-64" />}
      {d && (
        <div className="space-y-6 font-mono text-[12px]">
          <Card>
            <CardHeader title="Adapters" />
            <div className="flex flex-wrap gap-2 p-4">
              {Object.entries(d.adapters).map(([k, v]) => (
                <Chip key={k} tone={["template", "local", "inproc", "seeded", "simulated", "memory"].includes(v) ? "sim" : "accent"}>
                  {k}: {v}
                </Chip>
              ))}
            </div>
          </Card>
          <Card>
            <CardHeader title={`Agents (${d.agents.length})`} />
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="text-left text-muted"><tr><th className="px-4 py-2 font-normal">name</th><th className="font-normal">kind</th><th className="font-normal">address</th><th className="font-normal">transport</th><th className="font-normal">mode</th><th className="font-normal">capabilities</th></tr></thead>
                <tbody>
                  {d.agents.map((a) => (
                    <tr key={a.address} className="border-t border-line">
                      <td className="px-4 py-1.5">{a.name}</td><td>{a.kind}</td><td className="text-muted">{a.address}</td><td>{a.transport}</td><td>{a.mode ?? ""}</td><td className="text-muted">{a.capabilities.join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader title="Deals" />
              <ul className="divide-y divide-line">
                {d.deals.map((x) => <li key={x.id} className="flex justify-between px-4 py-1.5"><span>{x.id} · {x.title}</span><span>{x.status} · r{x.round} · v{x.version}</span></li>)}
                {d.deals.length === 0 && <li className="px-4 py-3 text-muted">none</li>}
              </ul>
            </Card>
            <Card>
              <CardHeader title="Agents in this deployment" meta="Personal agents hold their owner's private preferences; provider agents hold vendor price rules." />
              <ul className="divide-y divide-line">
                {(["mediator", "personal", "provider"] as const).map((k) => (
                  <li key={k} className="flex justify-between px-4 py-1.5"><span>{k}</span><span>{d.agents.filter((a) => a.kind === k).length}</span></li>
                ))}
              </ul>
            </Card>
          </div>
          <div className="font-sans">
            <AgentConversation messages={d.messages} title="Every agent message, all deals" maxHeight={640} />
          </div>
        </div>
      )}
    </>
  );
}
