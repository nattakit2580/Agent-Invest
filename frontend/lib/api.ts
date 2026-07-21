import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

// Where to send API calls.
//  - Explicit NEXT_PUBLIC_API_URL always wins (Cloudflare/static deployments).
//  - On the deployed Render frontend, call the backend DIRECTLY (CORS is configured).
//    Analysis can take ~45s, which exceeds the Next.js rewrite-proxy timeout (~30s)
//    and surfaces as a 500; going direct removes that middle hop.
//  - Everywhere else (local dev) use "/api", which Next.js rewrites to BACKEND_URL.
function resolveBaseURL(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined" && window.location.hostname.endsWith(".onrender.com")) {
    return "https://agent-invest-backend.onrender.com";
  }
  return "/api";
}

export const api = axios.create({
  baseURL: resolveBaseURL(),
});

// Render's free tier spins the backend down after ~15 min idle. The first request
// then hits a cold start (~20-60s) and Render's proxy returns 502/503 before the app
// is ready. Retry those transient gateway errors so users don't see a hard failure
// while the server wakes up. 502/503 (and no-response) mean the request never reached
// the app, so retrying is safe and won't create duplicates.
const RETRY_STATUSES = [502, 503, 504];
const MAX_RETRIES = 6;
const RETRY_DELAY_MS = 5000;

type RetryConfig = InternalAxiosRequestConfig & { _retryCount?: number };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined;
    if (!config) return Promise.reject(error);

    const status = error.response?.status;
    const isColdStart = status === undefined || RETRY_STATUSES.includes(status);
    config._retryCount = config._retryCount ?? 0;

    if (isColdStart && config._retryCount < MAX_RETRIES) {
      config._retryCount += 1;
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
      return api(config);
    }
    return Promise.reject(error);
  }
);

// Ping the backend to trigger a cold-start wake-up ahead of a real request.
// Fire-and-forget; the retry interceptor handles the actual analyze call.
export const wakeBackend = () => api.get("/health").catch(() => undefined);

export interface Prediction {
  id: string;
  symbol: string;
  created_at: string;
  timeframe: string;
  direction: "bullish" | "bearish" | "neutral";
  current_price: number;
  target_price: number | null;
  confidence: number;
  reasoning: string;
  agent_outputs: Record<string, AgentOutput> | null;
  actual_price: number | null;
  actual_direction: string | null;
  accuracy_score: number | null;
  compared_at: string | null;
  status: "pending" | "compared";
  market_regime?: string | null;
}

export interface AgentOutput {
  direction: string;
  confidence: number;
  summary: string;
  key_points: string[];
  reasoning_trace?: string;
  [key: string]: unknown;
}

export interface AccuracyStats {
  total: number;
  compared: number;
  direction_accuracy: number;
  avg_confidence: number;
  avg_accuracy_score: number;
  by_timeframe: Record<string, { total: number; direction_accuracy: number; avg_accuracy_score: number }>;
  by_symbol: Record<string, { total: number; direction_accuracy: number; avg_accuracy_score: number }>;
}


export interface TelegramCountItem {
  name: string;
  count: number;
}

export interface TelegramDailyMessageCount {
  date: string;
  total: number;
  private: number;
  group: number;
}

export interface TelegramRecentMessage {
  created_at: string;
  chat_id: string;
  chat_type: string;
  user_id: string | null;
  display_name: string | null;
  text: string | null;
  intent: string;
  topic: string;
}

export interface TelegramAnalytics {
  days: number;
  total_messages: number;
  private_messages: number;
  group_messages: number;
  unique_users: number;
  active_chats: number;
  top_topics: TelegramCountItem[];
  top_intents: TelegramCountItem[];
  top_keywords: TelegramCountItem[];
  daily_messages: TelegramDailyMessageCount[];
  recent_messages: TelegramRecentMessage[];
}
export interface EconomicIndicator {
  series_id: string;
  label: string;
  value: number | null;
  previous_value: number | null;
  change: number | null;
  change_pct: number | null;
  unit: string | null;
  observation_date: string | null;
  updated_at: string | null;
}

export interface EconomicResponse {
  configured: boolean;
  count: number;
  indicators: EconomicIndicator[];
}

export interface CalendarEvent {
  event_type: "earnings" | "dividend" | "ipo" | "economic";
  symbol: string | null;
  title: string;
  event_date: string;
  days_until: number;
  source: string | null;
  notified_at: string | null;
}

export interface CalendarResponse {
  count: number;
  days_ahead: number;
  events: CalendarEvent[];
}

export interface AgentAccuracyItem {
  agent: string;
  total: number;
  hits: number;
  direction_accuracy: number;
}

export interface DynamicWeights {
  total_evals: number;
  dynamic_weights_active: boolean;
  weights: Record<string, number>;
  accuracies: Record<string, number>;
  prompt_section: string;
}

// Static base weights the system starts from (before it has enough evaluations).
export const BASE_WEIGHTS: Record<string, number> = {
  news: 0.2,
  fundamental: 0.3,
  technical: 0.3,
  sentiment: 0.2,
};
export const MIN_EVALS_FOR_DYNAMIC = 20;

export const analyzeSymbol = (symbol: string, timeframe: string) =>
  api.post<Prediction>("/analyze", { symbol, timeframe }).then((r) => r.data);

export const getPredictions = (params?: Record<string, string | number>) =>
  api.get<Prediction[]>("/predictions", { params }).then((r) => r.data);

export const getPrediction = (id: string) =>
  api.get<Prediction>(`/predictions/${id}`).then((r) => r.data);

export const autoCompare = (id: string) =>
  api.post<Prediction>(`/predictions/${id}/auto-compare`).then((r) => r.data);

export const getAccuracy = (params?: Record<string, string>) =>
  api.get<AccuracyStats>("/accuracy", { params }).then((r) => r.data);

export const getMarketData = (symbol: string) =>
  api.get(`/analyze/market/${symbol}`).then((r) => r.data);
// Requires the admin password (same secret as the /admin page) — the analytics
// payload contains private message text, usernames and Telegram user ids.
export const getTelegramAnalytics = (password: string, params?: Record<string, string | number>) =>
  api
    .get<TelegramAnalytics>("/telegram/analytics", {
      params,
      headers: { "X-Admin-Password": password },
    })
    .then((r) => r.data);

export interface AiChatStats {
  days: number;
  total_chats: number;
  rated: number;
  thumbs_up: number;
  thumbs_down: number;
  satisfaction_pct: number | null;
  with_symbol_context: number;
  top_symbols: { symbol: string; count: number }[];
  recent_low_rated: { question: string; answer: string; symbol: string | null; created_at: string }[];
}

// AI-chat feedback statistics (admin password) — used to improve chat logic.
export const getAiChatStats = (password: string, days = 30) =>
  api
    .get<AiChatStats>("/telegram/ai-stats", {
      params: { days },
      headers: { "X-Admin-Password": password },
    })
    .then((r) => r.data);

export interface TgUser {
  telegram_user_id: string;
  name: string;
  username: string | null;
  tier: string;
  usage: Record<"analyze" | "graph" | "chat", { used: number; limit: number }>;
  message_count: number;
  last_seen: string | null;
}
export interface TgUsersResponse {
  users: TgUser[];
  count: number;
  tiers: string[];
}

// Admin user management (admin password)
export const getTgUsers = (password: string, params?: { search?: string; limit?: number }) =>
  api
    .get<TgUsersResponse>("/telegram/users", { params, headers: { "X-Admin-Password": password } })
    .then((r) => r.data);

export const setTgUserTier = (password: string, userId: string, tier: string) =>
  api
    .post(`/telegram/users/${userId}/tier`, { tier }, { headers: { "X-Admin-Password": password } })
    .then((r) => r.data);

export const resetTgUserUsage = (password: string, userId: string, feature?: string) =>
  api
    .post(`/telegram/users/${userId}/reset-usage`, null, {
      params: feature ? { feature } : undefined,
      headers: { "X-Admin-Password": password },
    })
    .then((r) => r.data);

export const getEconomicIndicators = () =>
  api.get<EconomicResponse>("/economic/indicators").then((r) => r.data);

export const refreshEconomicIndicators = () =>
  api.post<{ count: number; indicators: EconomicIndicator[] }>("/economic/refresh").then((r) => r.data);

export const getCalendarEvents = (daysAhead = 14) =>
  api.get<CalendarResponse>("/calendar/events", { params: { days_ahead: daysAhead } }).then((r) => r.data);

export const refreshCalendar = () =>
  api.post<{ touched: number; events: CalendarEvent[] }>("/calendar/refresh").then((r) => r.data);

export const getAgentAccuracyList = () =>
  api.get<AgentAccuracyItem[]>("/accuracy/agents").then((r) => r.data);

export const getDynamicWeights = () =>
  api.get<DynamicWeights>("/accuracy/weights").then((r) => r.data);

// ---------------------------------------------------------------------------
// Streaming analysis (NDJSON) — reveals each agent as it finishes.
// ---------------------------------------------------------------------------
export type AnalyzeStreamEvent =
  | { type: "status"; stage: string; message?: string }
  | { type: "agent"; name: string; output: Record<string, unknown> }
  | {
      type: "synthesis";
      direction: string;
      confidence: number;
      current_price: number;
      target_price: number | null;
      reasoning: string;
      key_risks: string[];
      catalysts: string[];
      recommendation: string;
    }
  | { type: "critic"; output: Record<string, unknown> }
  | { type: "final"; prediction: Prediction }
  | { type: "error"; detail: string };

const COLD_START_STATUS = new Set([502, 503, 504]);

export async function analyzeStream(
  symbol: string,
  timeframe: string,
  onEvent: (ev: AnalyzeStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const base = api.defaults.baseURL || "/api";
  const url = `${base}/analyze/stream`;

  // Open the stream, retrying the initial connection through Render cold starts.
  let res: Response | null = null;
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe }),
        signal,
      });
    } catch (e) {
      if (signal?.aborted) throw e;
      await new Promise((r) => setTimeout(r, 5000));
      continue;
    }
    if (res.ok) break;
    if (COLD_START_STATUS.has(res.status) && attempt < 5) {
      await new Promise((r) => setTimeout(r, 5000));
      res = null;
      continue;
    }
    break;
  }

  if (!res || !res.ok || !res.body) {
    onEvent({ type: "error", detail: `เชื่อมต่อไม่สำเร็จ (${res?.status ?? "network"})` });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const flushLine = (line: string) => {
    const t = line.trim();
    if (!t) return;
    try {
      onEvent(JSON.parse(t) as AnalyzeStreamEvent);
    } catch {
      /* ignore partial/non-JSON lines */
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n")) >= 0) {
      flushLine(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 1);
    }
  }
  flushLine(buffer);
}

// ---------------------------------------------------------------------------
// Admin — per-agent model configuration (password verified server-side).
// ---------------------------------------------------------------------------
export interface ModelCatalogItem {
  id: string;
  label: string;
  tier: string;
  free?: boolean;
}

export interface AgentConfigRow {
  agent: string;
  label: string;
  model: string; // "" = using default
  resolved_model: string;
  env_default: string;
  temperature: number | null;
  max_tokens: number | null;
}

export interface AdminConfig {
  agents: AgentConfigRow[];
  models: ModelCatalogItem[];
  global_default: string;
}

export interface AgentConfigUpdate {
  agent: string;
  model?: string;
  temperature?: number | null;
  max_tokens?: number | null;
}

export const adminLogin = (password: string) =>
  api.post<{ ok: boolean }>("/admin/login", { password }).then((r) => r.data);

export const getAdminConfig = (password: string) =>
  api
    .get<AdminConfig>("/admin/config", { headers: { "X-Admin-Password": password } })
    .then((r) => r.data);

export const updateAdminConfig = (password: string, agents: AgentConfigUpdate[]) =>
  api
    .put<AdminConfig>(
      "/admin/config",
      { agents },
      { headers: { "X-Admin-Password": password } }
    )
    .then((r) => r.data);

// ── Deep Research (KG-RAG pipeline) ──
export interface DeepResearchRequest {
  symbol: string;
  timeframe?: string;
  max_papers?: number;
  max_filings?: number;
}

export interface DeepResearchResult extends Prediction {
  deep_research: {
    papers_found: number;
    filings_found: number;
    new_docs_indexed: number;
    highlights: string[];
  };
  elapsed_seconds: number;
}

export interface KnowledgeStats {
  knowledge_docs: Record<string, number>;
  knowledge_graph: {
    entities: Record<string, number>;
    relationships: number;
  };
}

export const deepResearch = (req: DeepResearchRequest) =>
  api.post<DeepResearchResult>("/deep-research", req).then((r) => r.data);

export const getKnowledgeStats = () =>
  api.get<KnowledgeStats>("/deep-research/knowledge/stats").then((r) => r.data);

export const seedKnowledgeGraph = () =>
  api.post("/deep-research/knowledge/seed-graph").then((r) => r.data);

export interface DatasetStats {
  total_predictions: number;
  compared: number;
  export_ready: number;
  next_target: number;
  progress_pct: number;
  direction_distribution: Record<string, number>;
  timeframe_distribution: Record<string, number>;
  accuracy_score_buckets: Record<string, number>;
  targets: number[];
}

export const getDatasetStats = () =>
  api.get<DatasetStats>("/dataset/stats").then((r) => r.data);
