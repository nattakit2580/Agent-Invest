"use client";

import { useCallback, useEffect, useState } from "react";
import { format } from "date-fns";
import { Lock, Users, RefreshCw, Search, Check } from "lucide-react";
import { adminLogin, getTgUsers, setTgUserTier, resetTgUserUsage, type TgUser } from "@/lib/api";

const PW_KEY = "agent_invest_admin_pw";

const TIER_STYLE: Record<string, string> = {
  free: "bg-slate-100 text-slate-600",
  pro: "bg-blue-100 text-blue-700",
  vip: "bg-amber-100 text-amber-700",
};

function UsageCell({ u }: { u: { used: number; limit: number } }) {
  if (u.limit <= 0) return <span className="text-emerald-600 text-xs">ไม่จำกัด</span>;
  const over = u.used >= u.limit;
  return (
    <span className={`tabular-nums text-xs ${over ? "text-red-600 font-semibold" : "text-slate-600"}`}>
      {u.used}/{u.limit}
    </span>
  );
}

export default function UsersPage() {
  const [users, setUsers] = useState<TgUser[]>([]);
  const [tiers, setTiers] = useState<string[]>(["free", "pro", "vip"]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState("");

  const load = useCallback((pw: string, q?: string) => {
    setLoading(true);
    setError(null);
    getTgUsers(pw, { search: q || undefined, limit: 100 })
      .then((d) => { setUsers(d.users); setTiers(d.tiers); })
      .catch((err) => {
        if (err?.response?.status === 401) { sessionStorage.removeItem(PW_KEY); setAuthed(false); }
        else setError(err?.response?.data?.detail || err?.message || "โหลดรายชื่อผู้ใช้ไม่สำเร็จ");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const saved = sessionStorage.getItem(PW_KEY);
    if (saved) { setPassword(saved); setAuthed(true); }
  }, []);
  useEffect(() => {
    if (authed && password) load(password);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed]);

  const handleLogin = async () => {
    if (!password.trim()) return;
    setLoggingIn(true); setLoginError("");
    try {
      await adminLogin(password);
      sessionStorage.setItem(PW_KEY, password);
      setAuthed(true);
    } catch { setLoginError("รหัสผ่านไม่ถูกต้อง"); }
    finally { setLoggingIn(false); }
  };

  const showFlash = (msg: string) => { setFlash(msg); setTimeout(() => setFlash(null), 2500); };

  const changeTier = async (u: TgUser, tier: string) => {
    setUsers((prev) => prev.map((x) => x.telegram_user_id === u.telegram_user_id ? { ...x, tier } : x));
    try {
      await setTgUserTier(password, u.telegram_user_id, tier);
      showFlash(`ตั้ง ${u.name} เป็นแพ็กเกจ ${tier} แล้ว`);
      load(password, search);
    } catch { setError("ตั้งแพ็กเกจไม่สำเร็จ"); }
  };

  const resetUsage = async (u: TgUser) => {
    try {
      await resetTgUserUsage(password, u.telegram_user_id);
      showFlash(`รีเซ็ตโควตาวันนี้ให้ ${u.name} แล้ว`);
      load(password, search);
    } catch { setError("รีเซ็ตโควตาไม่สำเร็จ"); }
  };

  if (!authed) {
    return (
      <div className="max-w-sm mx-auto mt-24">
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6 space-y-4">
          <div className="flex items-center gap-2 text-slate-900">
            <Lock className="w-5 h-5 text-blue-600" />
            <h1 className="text-lg font-semibold">จัดการผู้ใช้</h1>
          </div>
          <p className="text-sm text-slate-500">ตั้งแพ็กเกจและโควตาของผู้ใช้ — ต้องใส่รหัสผ่านผู้ดูแลระบบ</p>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            placeholder="รหัสผ่านผู้ดูแลระบบ"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {loginError && <p className="text-sm text-red-600">{loginError}</p>}
          <button type="button" onClick={handleLogin} disabled={loggingIn}
            className="w-full rounded-lg bg-blue-600 text-white py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-60">
            {loggingIn ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่ระบบ"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
            <Users className="w-8 h-8 text-blue-600" />
            จัดการผู้ใช้
          </h1>
          <p className="text-slate-500 mt-1">ตั้งแพ็กเกจ (free/pro/vip) และเพิ่ม/รีเซ็ตโควตาวันนี้ให้ผู้ใช้รายคน</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load(password, search)}
              placeholder="ค้นหา ชื่อ/username/id"
              className="pl-9 pr-3 py-2 rounded-lg border border-slate-200 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button onClick={() => load(password, search)}
            className="h-10 w-10 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 flex items-center justify-center" aria-label="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {flash && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-xl p-3 text-sm flex items-center gap-2">
          <Check className="w-4 h-4" /> {flash}
        </div>
      )}
      {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl p-3 text-sm">{error}</div>}

      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-6 text-slate-500">กำลังโหลด...</div>
        ) : users.length === 0 ? (
          <div className="p-6 text-slate-500 text-sm">ยังไม่มีผู้ใช้</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500 border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="py-3 px-4 font-medium">ผู้ใช้</th>
                  <th className="py-3 px-4 font-medium">แพ็กเกจ</th>
                  <th className="py-3 px-3 font-medium">วิเคราะห์</th>
                  <th className="py-3 px-3 font-medium">กราฟ</th>
                  <th className="py-3 px-3 font-medium">แชท</th>
                  <th className="py-3 px-4 font-medium">ล่าสุด</th>
                  <th className="py-3 px-4 font-medium text-right">จัดการ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.telegram_user_id} className="text-slate-700 hover:bg-slate-50/60">
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900">{u.name}</div>
                      <div className="text-xs text-slate-400">id: {u.telegram_user_id}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TIER_STYLE[u.tier] || TIER_STYLE.free}`}>
                        {u.tier}
                      </span>
                    </td>
                    <td className="py-3 px-3"><UsageCell u={u.usage.analyze} /></td>
                    <td className="py-3 px-3"><UsageCell u={u.usage.graph} /></td>
                    <td className="py-3 px-3"><UsageCell u={u.usage.chat} /></td>
                    <td className="py-3 px-4 text-xs text-slate-400 whitespace-nowrap">
                      {u.last_seen ? format(new Date(u.last_seen), "dd/MM/yy HH:mm") : "-"}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2 justify-end">
                        <select
                          value={u.tier}
                          onChange={(e) => changeTier(u, e.target.value)}
                          className="rounded-lg border border-slate-200 text-xs px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          {tiers.map((t) => <option key={t} value={t}>{t}</option>)}
                        </select>
                        <button
                          onClick={() => resetUsage(u)}
                          className="rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1.5 whitespace-nowrap"
                        >
                          รีเซ็ตโควตาวันนี้
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="text-xs text-slate-400">
        แพ็กเกจ: <b>free</b> = โควตาพื้นฐาน · <b>pro</b> = 10 เท่า · <b>vip</b> = ไม่จำกัด ·
        &nbsp;"รีเซ็ตโควตาวันนี้" = ล้างจำนวนการใช้ของวันนี้ให้เริ่มใหม่ (เพิ่มสิทธิ์เฉพาะวันนี้)
      </p>
    </div>
  );
}
