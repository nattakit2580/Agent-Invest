import axios from "axios";

// Dev and Render frontend use /api, which Next.js rewrites to BACKEND_URL.
// Cloudflare/static deployments can set NEXT_PUBLIC_API_URL to call the backend directly.
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "/api",
});

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
}

export interface AgentOutput {
  direction: string;
  confidence: number;
  summary: string;
  key_points: string[];
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
export const getTelegramAnalytics = (params?: Record<string, string | number>) =>
  api.get<TelegramAnalytics>("/telegram/analytics", { params }).then((r) => r.data);

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
