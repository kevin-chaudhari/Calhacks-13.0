"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./api";
import { usePersona, useVendorApi } from "./persona";

/** Polls a vendor endpoint as the selected staff member. */
export function useVendorPoll<T>(path: string | null, intervalMs = 1200) {
  const { vendor } = usePersona();
  const vapi = useVendorApi();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!vendor || !path) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const run = async () => {
      try {
        const d = await vapi<T>(path);
        if (alive) {
          setData(d);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e instanceof ApiError ? e.message : "Lost connection; retrying…");
      }
      if (alive) timer = setTimeout(run, intervalMs);
    };
    run();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [vendor, path, vapi, intervalMs, tick]);

  useEffect(() => setData(null), [vendor?.id]);
  return { data, error, refresh };
}
