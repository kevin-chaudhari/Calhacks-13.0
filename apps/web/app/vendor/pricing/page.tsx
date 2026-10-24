"use client";

import { Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { day, money, TERM_LABELS, termValue } from "@/lib/format";
import { useVendorApi } from "@/lib/persona";
import type { ProviderConfig, VendorDashboard } from "@/lib/types";
import { useVendorPoll } from "@/lib/useVendor";
import { Button, Callout, Card, CardHeader, Chip, PageTitle, Skeleton, cx } from "@/components/ui/primitives";

const WEEKENDS = ["2026-11-07", "2026-11-08", "2026-11-14", "2026-11-15", "2026-11-21", "2026-11-22", "2026-11-28", "2026-11-29"];

export default function Pricing() {
  const vapi = useVendorApi();
  const { data } = useVendorPoll<VendorDashboard>("/v1/vendor/dashboard", 60_000);
  const [p, setP] = useState<ProviderConfig | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [size, setSize] = useState(4);

  useEffect(() => {
    if (data) setP(structuredClone(data.provider));
  }, [data?.provider.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!p) return <Skeleton className="h-96" />;

  const setTier = (i: number, k: "min" | "max" | "pricePerPerson", v: number) =>
    setP({ ...p, tiers: p.tiers.map((t, j) => (j === i ? { ...t, [k]: v } : t)) });

  async function save() {
    setErr(null);
    setSaved(null);
    try {
      const out = await vapi<ProviderConfig>("/v1/vendor/provider", {
        method: "PATCH",
        body: { autoQuote: p!.autoQuote, tiers: p!.tiers, modifiers: p!.modifiers, availableDates: p!.availableDates },
      });
      setP(structuredClone(out));
      setSaved("Saved. Your agent quotes with these rules from now on.");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message + (e.fields ? " " + Object.values(e.fields).join(" ") : "") : "Save failed.");
    }
  }

  const tier = p.tiers.find((t) => t.min <= size && size <= t.max);

  return (
    <>
      <PageTitle eyebrow={`Vendor portal · ${p.name}`} title="Agent & pricing rules">
        Your Rally agent prices every plan from these rules: the group-size tier, plus or minus option modifiers. It can only
        offer what you list here.
      </PageTitle>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Quoting" />
            <label className="flex items-start gap-3 px-5 py-4">
              <input type="checkbox" checked={p.autoQuote} onChange={(e) => setP({ ...p, autoQuote: e.target.checked })} className="mt-1 accent-[var(--accent)]" />
              <span>
                <span className="block font-medium">Agent sends binding quotes automatically</span>
                <span className="text-[13px] text-muted">Turn off to review every quote yourself before the group sees it.</span>
              </span>
            </label>
          </Card>

          <Card>
            <CardHeader title="Group-size tiers" meta="Base price per person" action={
              <Button variant="secondary" className="h-8" onClick={() => {
                const last = p.tiers[p.tiers.length - 1];
                setP({ ...p, tiers: [...p.tiers, { min: (last?.max ?? 0) + 1, max: (last?.max ?? 0) + 2, pricePerPerson: last?.pricePerPerson ?? 100, includes: last?.includes ?? [] }] });
              }}><Plus size={14} /> Tier</Button>
            } />
            <table className="num w-full text-[14px]">
              <thead className="text-left text-[12px] text-muted"><tr><th className="px-5 py-2 font-normal">From</th><th className="font-normal">To</th><th className="font-normal">Price pp</th><th className="font-normal">Includes</th><th /></tr></thead>
              <tbody>
                {p.tiers.map((t, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="px-5 py-2"><input aria-label="From" type="number" min={1} max={8} value={t.min} onChange={(e) => setTier(i, "min", +e.target.value)} className="h-8 w-16 rounded-[6px] border border-line bg-surface px-2" /></td>
                    <td><input aria-label="To" type="number" min={1} max={8} value={t.max} onChange={(e) => setTier(i, "max", +e.target.value)} className="h-8 w-16 rounded-[6px] border border-line bg-surface px-2" /></td>
                    <td><span className="text-muted">$ </span><input aria-label="Price per person" type="number" min={1} value={t.pricePerPerson} onChange={(e) => setTier(i, "pricePerPerson", +e.target.value)} className="h-8 w-20 rounded-[6px] border border-line bg-surface px-2" /></td>
                    <td className="text-[12px] text-muted">{t.includes.join(", ")}</td>
                    <td className="pr-3 text-right"><button aria-label="Remove tier" onClick={() => setP({ ...p, tiers: p.tiers.filter((_, j) => j !== i) })} className="p-1 text-muted hover:text-danger"><Trash2 size={14} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card>
            <CardHeader title="Options you offer" meta="Modifiers adjust the per-person price" />
            <div className="divide-y divide-line">
              {Object.entries(p.offers).map(([key, values]) => (
                <div key={key} className="grid gap-2 px-5 py-3 sm:grid-cols-[150px_1fr]">
                  <div className="text-[13px] text-muted">{TERM_LABELS[key] ?? key}</div>
                  <div className="flex flex-wrap gap-3">
                    {values.map((v) => {
                      const k = String(v);
                      const mod = p.modifiers[key]?.[k] ?? 0;
                      return (
                        <label key={k} className="flex items-center gap-2 rounded-[8px] border border-line px-2.5 py-1.5 text-[13px]">
                          {termValue(key, v)}
                          <span className="text-muted">±$</span>
                          <input type="number" value={mod} aria-label={`${termValue(key, v)} price modifier`}
                            onChange={(e) => setP({ ...p, modifiers: { ...p.modifiers, [key]: { ...(p.modifiers[key] ?? {}), [k]: +e.target.value } } })}
                            className="num h-7 w-16 rounded-[6px] border border-line bg-surface px-1.5" />
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Available dates" meta="Tap to toggle" />
            <div className="flex flex-wrap gap-2 p-5">
              {WEEKENDS.map((d) => {
                const on = p.availableDates.includes(d);
                return (
                  <button key={d} aria-pressed={on} onClick={() => setP({ ...p, availableDates: on ? p.availableDates.filter((x) => x !== d) : [...p.availableDates, d] })}
                    className={cx("rounded-full border px-3 py-1 text-[13px]", on ? "border-accent bg-accent-soft text-accent" : "border-line text-muted")}>
                    {day(d)}
                  </button>
                );
              })}
            </div>
          </Card>
        </div>

        <div className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <Card className="p-5">
            <div className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Preview</div>
            <label className="mt-3 flex items-center justify-between text-[13px]">
              Group of
              <input type="range" min={1} max={8} value={size} onChange={(e) => setSize(+e.target.value)} className="mx-3 flex-1 accent-[var(--accent)]" aria-label="Group size" />
              <span className="num w-6 font-mono">{size}</span>
            </label>
            <div className="num mt-3 text-[28px] font-semibold">{tier ? money(tier.pricePerPerson) : "—"}</div>
            <div className="text-[12px] text-muted">{tier ? "base per person, before option modifiers" : "No tier covers this group size; your agent won't quote it."}</div>
          </Card>
          {err && <Callout tone="danger" title="Not saved">{err}</Callout>}
          {saved && <Callout tone="accent" title={saved} />}
          <Button className="h-10 w-full" onClick={save}><Save size={15} /> Save rules</Button>
          <p className="text-[12px] text-muted">Rules live in the running API for this prototype; <Chip>reset</Chip> restores the seeded ones.</p>
        </div>
      </div>
    </>
  );
}
