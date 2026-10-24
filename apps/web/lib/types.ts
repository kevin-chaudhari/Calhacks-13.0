// Contract types are generated from Python (packages/contracts/ts). The few response
// shapes below are API envelopes that are plain dicts on the server; keep them in sync
// with services/api/rally/service.py until they get Pydantic models of their own.
export type {
  AgentMessage, ChatMessage, Approval, Commitment, Condition, Deal, DealEvent, DealSnapshot, DealStatus, IntentDraft,
  Member, MissingField, Persona, PrivatePrefs, Proposal, PublicIntent, Quote, Round, TermSpec,
} from "@contracts";

import type { IntentDraft } from "@contracts";

export interface Goal {
  id: string;
  userId: string;
  text: string;
  status: "needs_input" | "ready" | "published";
  compiledBy: "gemini" | "template";
  warnings: string[];
  draft: IntentDraft;
  createdAt: number;
  intentId?: string;
  suggestedPrefs: {
    weights: Record<string, number>;
    best?: Record<string, unknown>;
    ranges?: Record<string, unknown[]>;
    priceWorst?: number | null;
    reservation?: number;
    patience?: number;
  };
}

export interface MatchCard {
  intentId: string;
  userId: string;
  name: string;
  initials: string;
  isDemoPersona: boolean;
  eligible: boolean;
  failedConstraint: string | null;
  reason: string;
  score: number;
  components: { semantic: number; date: number; proximity: number; pref: number } | null;
  text: string;
  dateFrom: string;
  dateTo: string;
  selected: boolean;
}

export interface MatchResult {
  intentId: string;
  ranker: "moss" | "local";
  rankerNote: string;
  matches: MatchCard[];
  rejections: MatchCard[];
  selectedIntentIds: string[];
  hardFilters: string[];
}

export interface DealSummary {
  id: string;
  title: string;
  status: string;
  round: number;
  maxRounds: number;
  memberCount: number;
  acceptedCount: number;
  createdAt: number;
}

export interface Diagnostics {
  agents: { address: string; name: string; kind: string; transport: string; capabilities: string[]; hasPrefs?: boolean; mode?: string }[];
  messages: (import("@contracts").AgentMessage & { dealId: string })[];
  deals: { id: string; title: string; status: string; round: number; version: number }[];
  adapters: Record<string, string>;
}

export type VendorStage = "negotiating" | "needs_review" | "quote_sent" | "confirm_booking" | "booked" | "lost" | "closed";

export interface ProviderConfig {
  id: string;
  name: string;
  activity: string;
  location: { label: string; lat: number; lng: number };
  agentAddress: string;
  autoQuote: boolean;
  offers: Record<string, unknown[]>;
  availableDates: string[];
  tiers: { min: number; max: number; pricePerPerson: number; includes: string[] }[];
  modifiers: Record<string, Record<string, number>>;
}

export interface VendorRequestSummary {
  id: string;
  title: string;
  activityLabel: string;
  status: string;
  stage: VendorStage;
  groupSize: number;
  terms: Record<string, unknown>;
  round: number;
  version: number;
  pricePerPerson: number | null;
  total: number | null;
  draftPricePerPerson: number | null;
  chatCount: number;
  updatedAt: number;
}

export interface VendorDashboard {
  staff: import("@contracts").Persona;
  provider: ProviderConfig;
  stages: Partial<Record<VendorStage, number>>;
  requests: VendorRequestSummary[];
  committedRevenue: number;
  peopleBooked: number;
  agent: { address: string; transport: string; online: boolean; mode: string };
}

export interface VendorRequest {
  deal: import("@contracts").Deal;
  stage: VendorStage;
  provider: ProviderConfig;
  staff: import("@contracts").Persona;
  members: { name: string; initials: string; state: string; agentStatus: string }[];
  proposals: import("@contracts").Proposal[];
  rounds: import("@contracts").Round[];
  termLabels: Record<string, string>;
  quotes: import("@contracts").Quote[];
  review: { providerId: string; providerName: string; staffName: string; draft: import("@contracts").Quote; since: number; version: number } | null;
  agentMessages: import("@contracts").AgentMessage[];
  negotiation: import("@contracts").DealEvent[];
  chat: import("@contracts").ChatMessage[];
  canChat: boolean;
}
