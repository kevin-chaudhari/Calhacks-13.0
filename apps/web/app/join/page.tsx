"use client";

// Landing for a QR seat. ?d=<deal>&t=<persona token> takes a member's seat; ?d=<deal>&v=<vendor id>
// takes the vendor staff seat. The token is the same demo persona token the persona switcher uses.

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { usePersona } from "@/lib/persona";
import { Callout, Skeleton } from "@/components/ui/primitives";

function Join() {
  const q = useSearchParams();
  const router = useRouter();
  const { personas, choose, chooseVendor, error } = usePersona();
  const [problem, setProblem] = useState<string | null>(null);
  const d = q.get("d");
  const t = q.get("t");
  const v = q.get("v");

  useEffect(() => {
    if (!personas.length || !d) return;
    if (v) {
      if (!personas.some((p) => p.id === v && p.role === "vendor")) return setProblem("That vendor seat isn't valid any more.");
      chooseVendor(v);
      router.replace(`/vendor/requests/${d}`);
      return;
    }
    const p = personas.find((x) => x.token === t);
    if (!p) return setProblem("This seat expired. Ask the presenter for a fresh code.");
    choose(p.id);
    router.replace(`/deals/${d}/approve`);
  }, [personas, d, t, v, choose, chooseVendor, router]);

  if (!d) return <Callout tone="danger" title="Incomplete link">Scan the code again.</Callout>;
  if (error || problem) return <Callout tone="danger" title="Can't take this seat">{problem ?? error}</Callout>;
  return (
    <div className="space-y-3">
      <p className="text-[14px] text-muted">Taking your seat…</p>
      <Skeleton className="h-40" />
    </div>
  );
}

export default function JoinPage() {
  return (
    <Suspense fallback={<Skeleton className="h-40" />}>
      <Join />
    </Suspense>
  );
}
