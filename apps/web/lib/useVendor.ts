"use client";

import { useCallback, useEffect, useState } from "react";
import { useQuery } from "convex/react";
import { anyApi } from "convex/server";
import { ApiError } from "./api";
import { usePersona, useVendorApi } from "./persona";
import { CONVEX_URL } from "./useDeal";

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

/** A vendor screen's data. With Convex: a live subscription to the view FastAPI mirrors for this
 *  provider (access = its staff). Without: polling the API. Chosen at build time, never per render. */
function useVendorConvex<T>(rid: (providerId: string) => string): { data: T | null; error: string | null; refresh: () => void } {
  const { vendor } = usePersona();
  const pid = vendor?.providerId;
  const doc = useQuery(anyApi.rally.row, vendor && pid ? { table: "vendor", rid: rid(pid), token: vendor.token } : "skip") as T | null | undefined;
  return { data: doc ?? null, error: doc === null ? "Nothing here yet for your shop." : null, refresh: () => {} };
}

export function useVendorDashboard<T>(pollMs = 1500) {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return CONVEX_URL ? useVendorConvex<T>((pid) => `${pid}:dashboard`) : useVendorPoll<T>("/v1/vendor/dashboard", pollMs);
}

export function useVendorRequest<T>(dealId: string) {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return CONVEX_URL ? useVendorConvex<T>((pid) => `${pid}:${dealId}`) : useVendorPoll<T>(`/v1/vendor/requests/${dealId}`, 900);
}
