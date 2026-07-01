import axios from "axios";

// เนเธเน /api เธเธถเนเธ Next.js เธเธฐ proxy เนเธเธซเธฒ backend เนเธ”เธขเธญเธฑเธ•เนเธเธกเธฑเธ•เธด
// เธงเธดเธเธตเธเธตเนเธ—เธณเนเธซเนเนเธเน Cloudflare Tunnel เนเธ”เนเนเธ”เธขเนเธกเนเธ•เนเธญเธ expose backend port
export const api = axios.create({
  baseURL: "/api",
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
