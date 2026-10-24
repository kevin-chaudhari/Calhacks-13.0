"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import type { Persona } from "./types";

// Two identities can be active in one browser: a customer (main app) and vendor staff
// (vendor portal). Each keeps its own token, so a laptop can show both sides side by side.

interface PersonaCtx {
  personas: Persona[];
  me: Persona | null;
  vendor: Persona | null;
  choose: (id: string) => void;
  chooseVendor: (id: string) => void;
  error: string | null;
}

const Ctx = createContext<PersonaCtx>({
  personas: [], me: null, vendor: null, choose: () => {}, chooseVendor: () => {}, error: null,
});

const VENDOR_KEY = "rally.vendor.id";

function loadVendorId(): string | null {
  try {
    return window.localStorage.getItem(VENDOR_KEY);
  } catch {
    return null;
  }
}

export function PersonaProvider({ children }: { children: React.ReactNode }) {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [me, setMe] = useState<Persona | null>(null);
  const [vendor, setVendor] = useState<Persona | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Persona[]>("/v1/demo/personas", { token: null })
      .then((list) => {
        setPersonas(list);
        const customers = list.filter((p) => p.role === "customer");
        const current = getToken();
        const found = customers.find((p) => p.token === current) ?? customers.find((p) => p.id === "u_kevin") ?? customers[0];
        if (found) {
          setToken(found.token);
          setMe(found);
        }
        const vendors = list.filter((p) => p.role === "vendor");
        const vid = loadVendorId();
        setVendor(vendors.find((v) => v.id === vid) ?? vendors.find((v) => v.id === "v_marcus") ?? vendors[0] ?? null);
      })
      .catch((e) => setError(e.message));
  }, []);

  const choose = useCallback(
    (id: string) => {
      const p = personas.find((x) => x.id === id);
      if (p) {
        setToken(p.token);
        setMe(p);
      }
    },
    [personas],
  );

  const chooseVendor = useCallback(
    (id: string) => {
      const p = personas.find((x) => x.id === id);
      if (p) {
        setVendor(p);
        try {
          window.localStorage.setItem(VENDOR_KEY, id);
        } catch {
          /* storage unavailable: keep it in memory */
        }
      }
    },
    [personas],
  );

  return <Ctx.Provider value={{ personas, me, vendor, choose, chooseVendor, error }}>{children}</Ctx.Provider>;
}

export const usePersona = () => useContext(Ctx);

/** Calls the API as the selected vendor staff member. */
export function useVendorApi() {
  const { vendor } = usePersona();
  return useCallback(
    <T,>(path: string, init: { method?: string; body?: unknown } = {}) => api<T>(path, { ...init, token: vendor?.token ?? null }),
    [vendor],
  );
}
