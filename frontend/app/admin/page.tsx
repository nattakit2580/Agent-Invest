"use client";
import { useState, useEffect, useCallback } from "react";
import { Lock, SlidersHorizontal, Loader2, Check, RefreshCw, AlertCircle } from "lucide-react";
import {
  adminLogin,
  getAdminConfig,
  updateAdminConfig,
  type AdminConfig,
  type AgentConfigUpdate,
} from "@/lib/api";

const PW_KEY = "agent_invest_admin_pw";
const CUSTOM = "__custom__";

type RowForm = { model: string; temperature: string; max_tokens: string; custom: boolean };

export default function AdminPage() {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState("");

  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [form, setForm] = useState<Record<string, RowForm>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const hydrate = useCallback((cfg: AdminConfig) => {
    setConfig(cfg);
    const ids = new Set(cfg.models.map((m) => m.id));
    const next: Record<string, RowForm> = {};
    for (const row of cfg.agents) {
      next[row.agent] = {
        model: row.model,
        temperature: row.temperature != null ? String(row.temperature) : "",
        max_tokens: row.max_tokens != null ? String(row.max_tokens) : "",
        custom: row.model !== "" && !ids.has(row.model),
      };
    }
    setForm(next);
  }, []);

  const loadConfig = useCallback(
    async (pw: string) => {
      setLoading(true);
      setError("");
      try {
        const cfg = await getAdminConfig(pw);
        hydrate(cfg);
        setAuthed(true);
        sessionStorage.setItem(PW_KEY, pw);
      } catch {
        sessionStorage.removeItem(PW_KEY);
        setAuthed(false);
      } finally {
        setLoading(false);
      }
    },
    [hydrate]
  );

  // Resume an existing admin session on refresh.
  useEffect(() => {
    const saved = sessionStorage.getItem(PW_KEY);
    if (saved) {
      setPassword(saved);
      loadConfig(saved);
    }
  }, [loadConfig]);

  const handleLogin = async () => {
    if (!password.trim()) return;
    setLoggingIn(true);
    setLoginError("");
    try {
      await adminLogin(password);
      await loadConfig(password);
    } catch {
      setLoginError("รหัสผ่านไม่ถูกต้อง");
    } finally {
      setLoggingIn(false);
    }
  };

  const setRow = (agent: string, patch: Partial<RowForm>) =>
    setForm((prev) => ({ ...prev, [agent]: { ...prev[agent], ...patch } }));

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setSaved(false);
    setError("");
    const updates: AgentConfigUpdate[] = config.agents.map((row) => {
      const f = form[row.agent];
      const temp = f.temperature.trim();
      const maxTok = f.max_tokens.trim();
      return {
        agent: row.agent,
        model: f.model.trim(),
        temperature: temp === "" ? null : Number(temp),
        max_tokens: maxTok === "" ? null : Number(maxTok),
      };
    });
    try {
      const cfg = await updateAdminConfig(password, updates);
      hydrate(cfg);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("บันทึกไม่สำเร็จ");
    } finally {
      setSaving(false);
    }
  };

  // ---- Login gate ----
  if (!authed) {
    return (
      <div className="max-w-md mx-auto mt-16">
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-sky-900/50 border border-sky-700 rounded-lg p-2">
              <Lock className="w-5 h-5 text-sky-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Admin</h1>
              <p className="text-xs text-slate-400">ตั้งค่าโมเดลของแต่ละ Agent</p>
            </div>
          </div>
          <label className="block text-sm text-slate-400 mb-2">รหัสผ่าน</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            placeholder="ใส่รหัสผ่านผู้ดูแล"
            className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-sky-500"
          />
          {loginError && (
            <p className="text-red-400 text-xs mt-2 flex items-center gap-1.5">
              <AlertCircle className="w-3.5 h-3.5" /> {loginError}
            </p>
          )}
          <button
            onClick={handleLogin}
            disabled={loggingIn || !password.trim()}
            className="mt-4 w-full bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-semibold rounded-lg py-3 flex items-center justify-center gap-2 transition-colors"
          >
            {loggingIn ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
            เข้าสู่ระบบ
          </button>
        </div>
      </div>
    );
  }

  // ---- Config editor ----
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <SlidersHorizontal className="w-8 h-8 text-sky-400" />
            ตั้งค่าโมเดล Agent
          </h1>
          <p className="text-slate-400 mt-1">
            เลือก LLM ให้แต่ละ Agent · ค่าเริ่มต้นทั่วระบบ:{" "}
            <span className="font-mono text-slate-300">{config?.global_default}</span>
          </p>
        </div>
        <button
          onClick={() => loadConfig(password)}
          disabled={loading}
          className="shrink-0 inline-flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white text-sm px-4 py-2.5 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          โหลดใหม่
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      <div className="space-y-3">
        {config?.agents.map((row) => {
          const f = form[row.agent];
          if (!f) return null;
          return (
            <div key={row.agent} className="bg-slate-800 border border-slate-700 rounded-xl p-5">
              <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                <span className="text-white font-semibold">{row.label}</span>
                <span className="text-[11px] text-slate-500">
                  ใช้อยู่: <span className="font-mono text-sky-300">{row.resolved_model}</span>
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="sm:col-span-2">
                  <label className="block text-xs text-slate-400 mb-1">โมเดล</label>
                  <select
                    value={f.custom ? CUSTOM : f.model}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === CUSTOM) setRow(row.agent, { custom: true, model: "" });
                      else setRow(row.agent, { custom: false, model: v });
                    }}
                    className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-sky-500"
                  >
                    <option value="">(ใช้ค่าเริ่มต้น: {row.env_default || config.global_default})</option>
                    <optgroup label="ฟรี (ไม่มีค่าใช้จ่าย)">
                      {config.models.filter((m) => m.free).map((m) => (
                        <option key={m.id} value={m.id}>{m.label}</option>
                      ))}
                    </optgroup>
                    <optgroup label="เสียเงิน (ใช้เครดิต OpenRouter)">
                      {config.models.filter((m) => !m.free).map((m) => (
                        <option key={m.id} value={m.id}>{m.label}</option>
                      ))}
                    </optgroup>
                    <option value={CUSTOM}>กำหนดเอง…</option>
                  </select>
                  {f.custom && (
                    <input
                      value={f.model}
                      onChange={(e) => setRow(row.agent, { model: e.target.value })}
                      placeholder="เช่น provider/model-id"
                      className="mt-2 w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-sky-500"
                    />
                  )}
                </div>

                <div>
                  <label className="block text-xs text-slate-400 mb-1">Temperature (ว่าง = ค่าเริ่มต้น)</label>
                  <input
                    value={f.temperature}
                    onChange={(e) => setRow(row.agent, { temperature: e.target.value })}
                    inputMode="decimal"
                    placeholder="เช่น 0.4"
                    className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Max tokens (ว่าง = ค่าเริ่มต้น)</label>
                  <input
                    value={f.max_tokens}
                    onChange={(e) => setRow(row.agent, { max_tokens: e.target.value })}
                    inputMode="numeric"
                    placeholder="เช่น 1200"
                    className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="sticky bottom-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 text-white font-semibold rounded-lg py-3 flex items-center justify-center gap-2 transition-colors shadow-lg"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : saved ? (
            <Check className="w-4 h-4" />
          ) : null}
          {saved ? "บันทึกแล้ว" : "บันทึกการตั้งค่า"}
        </button>
      </div>

      <p className="text-xs text-slate-600 text-center">
        การเปลี่ยนแปลงมีผลกับการวิเคราะห์ครั้งถัดไปทันที และถูกเก็บถาวรในฐานข้อมูล
      </p>
    </div>
  );
}
