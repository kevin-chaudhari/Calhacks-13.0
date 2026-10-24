"use client";

import type { VendorStage } from "@/lib/types";
import { Chip } from "@/components/ui/primitives";

export const STAGE: Record<VendorStage, { label: string; tone: "accent" | "warn" | "danger" | "neutral" | "sim"; order: number }> = {
  needs_review: { label: "Quote needs your review", tone: "warn", order: 0 },
  confirm_booking: { label: "Confirm booking", tone: "warn", order: 1 },
  quote_sent: { label: "Quote sent", tone: "sim", order: 2 },
  negotiating: { label: "Group negotiating", tone: "neutral", order: 3 },
  booked: { label: "Booked", tone: "accent", order: 4 },
  lost: { label: "Chose another vendor", tone: "neutral", order: 5 },
  closed: { label: "Closed", tone: "neutral", order: 6 },
};

export function StagePill({ stage }: { stage: VendorStage }) {
  const s = STAGE[stage] ?? STAGE.closed;
  return <Chip tone={s.tone}>{s.label}</Chip>;
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-[10px] border border-line bg-surface px-4 py-3">
      <div className="text-[12px] text-muted">{label}</div>
      <div className="num mt-0.5 text-[24px] font-semibold leading-8">{value}</div>
      {hint && <div className="text-[11px] text-muted">{hint}</div>}
    </div>
  );
}
