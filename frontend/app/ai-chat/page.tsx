"use client";

import { useCallback, useEffect, useState } from "react";
import { format } from "date-fns";
import { Lock, MessagesSquare, ThumbsUp, ThumbsDown, Gauge, RefreshCw } from "lucide-react";
import { getAiChatStats, adminLogin, type AiChatStats } from "@/lib/api";

// Same sessionStorage key as /admin & /telegram — one admin login unlocks all.
const PW_KEY = "agent_invest_admin_pw";

function StatCard({ title, value, sub, icon, color = "text-slate-900" }: {
  title: string; value: string | number; sub?: string; icon: React.ReactNode; color?: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-500 uppercase tracking-wider">{title}</p>
        <div className={color}>{icon}</div>
      </div>
      <p className={`text-3xl font-bold mt-2 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function AiChatPage() {
  const [days, setDays] = useState(30);
  const [stats, setStats] = useState<AiChatStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState("");

  const load = useCallback((pw: string, windowDays: number) => {
    setLoading(true);
    setError(null);
    getAiChatStats(pw, windowDays)
      .then(setStats)
      .catch((err) => {
        if (err?.response?.status === 401) {
          sessionStorage.removeItem(PW_KEY);
          setAuthed(false);
          setStats(null);
        } else {
          setError(err?.response?.data?.detail || err?.message || "โหลดสถิติไม่สำเร็จ");
        }
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const saved = sessionStorage.getItem(PW_KEY);
    if (saved) { setPassword(saved); setAuthed(true); }
  }, []);

  useEffect(() => {
    if (authed && password) load(password, days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed, days]);

  const handleLogin = async () => {
    if (!password.trim()) return;
    setLoggingIn(true);
    setLoginError("");
    try {
      await adminLogin(password);
      sessionStorage.setItem(PW_KEY, password);
      setAuthed(true);
    } catch {
      setLoginError("รหัสผ่านไม่ถูกต้อง");
    } finally {
      setLoggingIn(false);
    }
  };

  if (!authed) {
    return (
      <div className="max-w-sm mx-auto mt-24">
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6 space-y-4">
          <div className="flex items-center gap-2 text-slate-900">
            <Lock className="w-5 h-5 text-blue-600" />
            <h1 className="text-lg font-semibold">AI Chat Feedback</h1>
          </div>
          <p className="text-sm text-slate-500">สถิติการให้คะแนนบทสนทนา AI — ต้องใส่รหัสผ่านผู้ดูแลระบบ</p>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            placeholder="รหัสผ่านผู้ดูแลระบบ"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {loginError && <p className="text-sm text-red-600">{loginError}</p>}
          <button
            type="button"
            onClick={handleLogin}
            disabled={loggingIn}
            className="w-full rounded-lg bg-blue-600 text-white py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
          >
            {loggingIn ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่ระบบ"}
          </button>
        </div>
      </div>
    );
  }

  const maxTop = Math.max(...(stats?.top_symbols.map((s) => s.count) ?? [1]), 1);
  const satisfaction = stats?.satisfaction_pct;
  const satColor = satisfaction == null ? "text-slate-400"
    : satisfaction >= 70 ? "text-emerald-600" : satisfaction >= 40 ? "text-amber-600" : "text-red-600";

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
            <MessagesSquare className="w-8 h-8 text-blue-600" />
            AI Chat Feedback
          </h1>
          <p className="text-slate-500 mt-1">คะแนน 👍/👎 จากผู้ใช้ ใช้ปรับปรุงโลจิกและ prompt ของ AI</p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90].map((v) => (
            <button
              key={v}
              onClick={() => setDays(v)}
              className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                days === v ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {v}d
            </button>
          ))}
          <button
            onClick={() => load(password, days)}
            className="h-10 w-10 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 flex items-center justify-center"
            aria-label="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl p-4 text-sm">{error}</div>}

      {loading ? (
        <div className="text-slate-500">กำลังโหลด...</div>
      ) : stats ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard title="บทสนทนา" value={stats.total_chats} sub={`${stats.days} วันล่าสุด`} icon={<MessagesSquare className="w-5 h-5" />} color="text-blue-600" />
            <StatCard title="ความพึงพอใจ" value={satisfaction == null ? "—" : `${satisfaction}%`} sub={`ให้คะแนนแล้ว ${stats.rated} ครั้ง`} icon={<Gauge className="w-5 h-5" />} color={satColor} />
            <StatCard title="👍 ตรงใจ" value={stats.thumbs_up} icon={<ThumbsUp className="w-5 h-5" />} color="text-emerald-600" />
            <StatCard title="👎 ยังไม่ใช่" value={stats.thumbs_down} icon={<ThumbsDown className="w-5 h-5" />} color="text-red-600" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Top symbols */}
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">หัวข้อยอดฮิต (หุ้นที่ถูกถามบ่อย)</h2>
              {stats.top_symbols.length === 0 ? (
                <p className="text-sm text-slate-500">ยังไม่มีข้อมูล</p>
              ) : (
                <div className="space-y-3">
                  {stats.top_symbols.map((s) => (
                    <div key={s.symbol}>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="font-medium text-slate-700">{s.symbol}</span>
                        <span className="text-slate-500 tabular-nums">{s.count}</span>
                      </div>
                      <div className="h-2 rounded bg-slate-100 overflow-hidden">
                        <div className="h-full bg-blue-500" style={{ width: `${Math.max((s.count / maxTop) * 100, 6)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Coverage */}
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">ภาพรวม</h2>
              <ul className="space-y-2 text-sm text-slate-600">
                <li className="flex justify-between"><span>บทสนทนาที่มีบริบทหุ้น</span><span className="tabular-nums font-medium text-slate-800">{stats.with_symbol_context}</span></li>
                <li className="flex justify-between"><span>ให้คะแนนแล้ว</span><span className="tabular-nums font-medium text-slate-800">{stats.rated} / {stats.total_chats}</span></li>
                <li className="flex justify-between"><span>อัตราการให้คะแนน</span><span className="tabular-nums font-medium text-slate-800">{stats.total_chats ? Math.round((stats.rated / stats.total_chats) * 100) : 0}%</span></li>
              </ul>
              <p className="text-xs text-slate-400 mt-4">
                คำตอบที่ได้ 👍 จะถูกดึงไปเป็นตัวอย่าง (few-shot) ให้ AI เรียนรู้น้ำเสียง/รูปแบบที่ผู้ใช้ชอบโดยอัตโนมัติ
              </p>
            </div>
          </div>

          {/* Low-rated answers to improve */}
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">คำตอบที่ต้องปรับปรุง (ได้ 👎 ล่าสุด)</h2>
            {stats.recent_low_rated.length === 0 ? (
              <p className="text-sm text-slate-500">ยังไม่มีคำตอบที่ถูกให้ 👎 — เยี่ยมมาก 🎉</p>
            ) : (
              <div className="space-y-4">
                {stats.recent_low_rated.map((r, i) => (
                  <div key={i} className="border border-slate-100 rounded-xl p-4 bg-slate-50/60">
                    <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                      {r.symbol && <span className="rounded bg-blue-100 text-blue-700 px-2 py-0.5 font-medium">{r.symbol}</span>}
                      <span>{r.created_at ? format(new Date(r.created_at), "dd/MM/yy HH:mm") : ""}</span>
                    </div>
                    <p className="text-sm text-slate-800"><span className="text-slate-400">ถาม: </span>{r.question}</p>
                    <p className="text-sm text-slate-600 mt-1"><span className="text-slate-400">ตอบ: </span>{r.answer}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
