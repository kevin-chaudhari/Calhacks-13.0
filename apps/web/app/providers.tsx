"use client";

import { ConvexProvider, ConvexReactClient } from "convex/react";
import { useState } from "react";
import { PersonaProvider } from "@/lib/persona";
import { CONVEX_URL } from "@/lib/useDeal";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => (CONVEX_URL ? new ConvexReactClient(CONVEX_URL) : null));
  const inner = <PersonaProvider>{children}</PersonaProvider>;
  return client ? <ConvexProvider client={client}>{inner}</ConvexProvider> : inner;
}
