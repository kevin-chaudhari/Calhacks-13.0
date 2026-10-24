"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "convex/react";
import { anyApi } from "convex/server";
import { api, ApiError } from "./api";
import { usePersona } from "./persona";
import type { DealSnapshot } from "./types";

export const CONVEX_URL = process.env.NEXT_PUBLIC_CONVEX_URL || "";

/** Convex mode: a live subscription to the snapshot document FastAPI writes. Convex checks the
 *  persona token and the deal's access list, so a guessed deal id shows nothing. */
function useConvexSnapshot(dealId: string): { snap: DealSnapshot | null; error: string | null } {
  const { me } = usePersona();
  const doc = useQuery(anyApi.rally.dealSnapshot, me ? { dealId, token: me.token } : "skip") as DealSnapshot | null | undefined;
  return { snap: doc ?? null, error: doc === null ? "This group doesn't exist or you're not in it." : null };
}

/** Local dev mode (no Convex): poll the API snapshot. Same shape, same components. */
function usePolledSnapshot(dealId: string): { snap: DealSnapshot | null; error: string | null } {
  const { me } = usePersona();
  const [snap, setSnap] = useState<DealSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!me) return;
    let alive = true;
    const tick = async () => {
      try {
        const s = await api<DealSnapshot>(`/v1/deals/${dealId}/snapshot`);
        if (alive) {
          setSnap(s);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e instanceof ApiError ? e.message : "Lost connection; retrying…");
      }
      if (alive) timer.current = setTimeout(tick, 600);
    };
    tick();
    return () => {
      alive = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [dealId, me]);
  return { snap, error };
}

// The choice is fixed at build time, so hooks are never called conditionally at runtime.
export const useDealSnapshot = CONVEX_URL ? useConvexSnapshot : usePolledSnapshot;
