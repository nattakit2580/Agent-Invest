"use client";

import { useEffect, useState, type ReactNode } from "react";
import { format } from "date-fns";
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bot, Hash, MessageCircle, RefreshCw, Send, Users } from "lucide-react";
import { getTelegramAnalytics, type TelegramAnalytics, type TelegramCountItem } from "@/lib/api";

function StatCard({ title, value, sub, icon }: { title: string; value: string | number; sub?: string; icon: ReactNode }) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-400 uppercase tracking-wider">{title}</p>
        <div className="text-sky-400">{icon}</div>
      </div>
      <p className="text-3xl font-bold text-white mt-2">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

function CountList({ title, items }: { title: string; items: TelegramCountItem[] }) {
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 min-h-[260px]">
      <h2 className="text-lg font-semibold text-white mb-4">{title}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">No data yet.</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.name}>
              <div className="flex items-center justify-between gap-3 text-sm mb-1">
                <span className="text-slate-200 truncate">{item.name}</span>
                <span className="text-slate-400 tabular-nums">{item.count}</span>
              </div>
              <div className="h-2 rounded bg-slate-700 overflow-hidden">
                <div className="h-full bg-sky-500" style={{ width: `${Math.max((item.count / max) * 100, 8)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DayButton({ active, children, onClick }: { active: boolean; children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-2 rounded-lg text-sm transition-colors ${
        active ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

export default function TelegramDashboardPage() {
  const [days, setDays] = useState(7);
  const [analytics, setAnalytics] = useState<TelegramAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    getTelegramAnalytics({ days, limit: 12 })
      .then(setAnalytics)
      .catch((err) => setError(err?.response?.data?.detail || err?.message || "Failed to load Telegram analytics"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <MessageCircle className="w-8 h-8 text-sky-400" />
            Telegram Bot Dashboard
          </h1>
          <p className="text-slate-400 mt-1">Private chat and community message analytics.</p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 14, 30].map((value) => (
            <DayButton key={value} active={days === value} onClick={() => setDays(value)}>
              {value}d
            </DayButton>
          ))}
          <button
            type="button"
            onClick={load}
            className="h-10 w-10 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 flex items-center justify-center"
            aria-label="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && <div className="bg-red-950/50 border border-red-800 text-red-200 rounded-xl p-4 text-sm">{error}</div>}

      {loading ? (
        <div className="text-slate-400">Loading Telegram analytics...</div>
      ) : analytics ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard title="Messages" value={analytics.total_messages} sub={`${analytics.days} day window`} icon={<MessageCircle className="w-5 h-5" />} />
            <StatCard title="Private" value={analytics.private_messages} sub="1:1 bot chats" icon={<Bot className="w-5 h-5" />} />
            <StatCard title="Community" value={analytics.group_messages} sub="group messages" icon={<Users className="w-5 h-5" />} />
            <StatCard title="Users" value={analytics.unique_users} sub={`${analytics.active_chats} active chats`} icon={<Send className="w-5 h-5" />} />
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
            <h2 className="text-lg font-semibold text-white mb-4">Message Trend</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.daily_messages} margin={{ left: -20, right: 8, top: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickFormatter={(value) => String(value).slice(5)} />
                  <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }}
                    labelStyle={{ color: "#f8fafc" }}
                  />
                  <Bar dataKey="private" stackId="messages" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="group" stackId="messages" fill="#22c55e" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <CountList title="Top Topics" items={analytics.top_topics} />
            <CountList title="Top Intents" items={analytics.top_intents} />
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 min-h-[260px]">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Hash className="w-5 h-5 text-sky-400" />
                Top Keywords
              </h2>
              {analytics.top_keywords.length === 0 ? (
                <p className="text-sm text-slate-500">No keywords yet.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {analytics.top_keywords.map((item) => (
                    <span key={item.name} className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200">
                      {item.name} <span className="text-slate-500">{item.count}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
            <h2 className="text-lg font-semibold text-white mb-4">Recent Messages</h2>
            {analytics.recent_messages.length === 0 ? (
              <p className="text-sm text-slate-500">No messages received yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-slate-400 border-b border-slate-700">
                    <tr>
                      <th className="py-3 pr-4 font-medium">Time</th>
                      <th className="py-3 pr-4 font-medium">Chat</th>
                      <th className="py-3 pr-4 font-medium">User</th>
                      <th className="py-3 pr-4 font-medium">Topic</th>
                      <th className="py-3 pr-4 font-medium">Message</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {analytics.recent_messages.map((row, index) => (
                      <tr key={`${row.created_at}-${index}`} className="text-slate-300 align-top">
                        <td className="py-3 pr-4 whitespace-nowrap text-slate-500">{format(new Date(row.created_at), "dd/MM/yy HH:mm")}</td>
                        <td className="py-3 pr-4 whitespace-nowrap">{row.chat_type}</td>
                        <td className="py-3 pr-4 whitespace-nowrap">{row.display_name || row.user_id || "-"}</td>
                        <td className="py-3 pr-4 whitespace-nowrap">
                          <span className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-200">{row.topic}</span>
                        </td>
                        <td className="py-3 pr-4 min-w-[260px] text-slate-300">{row.text || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
