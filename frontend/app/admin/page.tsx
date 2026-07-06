"use client";
import { useEffect, useState } from "react";
import { Settings, Eye, EyeOff, CheckCircle, XCircle } from "lucide-react";
import { getAdminConfig } from "@/lib/api";

interface ApiKeyRow {
  label: string;
  key: string;
}

const API_KEY_ROWS: ApiKeyRow[] = [
  { label: "OpenRouter", key: "openrouter_api_key" },
  { label: "NewsAPI", key: "news_api_key" },
  { label: "Alpha Vantage", key: "alpha_vantage_api_key" },
  { label: "Finnhub", key: "finnhub_api_key" },
  { label: "Embedding (Jina AI)", key: "jina_api_key" },
];

const FREE_MODELS = [
  "meta-llama/llama-3.3-70b-instruct:free",
  "google/gemma-3-27b-it:free",
  "mistralai/mistral-7b-instruct:free",
  "qwen/qwen3-235b-a22b:free",
  "deepseek/deepseek-r1:free",
];

const GROQ_MODELS = [
  "llama-3.3-70b-versatile via groq",
  "llama-3.1-8b-instant via groq",
];

const PAID_MODELS = [
  "anthropic/claude-sonnet-4-6",
  "openai/gpt-4o",
  "google/gemini-2.0-flash",
];

function MaskedKeyInput({ value, hasValue }: { value: string; hasValue: boolean }) {
  const [show, setShow] = useState(false);
  return (
    <div className="flex items-center gap-2 flex-1">
      <input
        readOnly
        type={show ? "text" : "password"}
        value={hasValue ? (show ? value : "••••••••••••••••") : ""}
        placeholder="ยังไม่ตั้งค่า"
        className="flex-1 bg-slate-50 border border-slate-200 text-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none font-mono"
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="text-slate-400 hover:text-slate-600 transition-colors"
        aria-label={show ? "ซ่อน" : "แสดง"}
      >
        {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );
}

interface AgentModelRow {
  agent: string;
  model: string;
  tier: string;
}

export default function AdminPage() {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [agentModels, setAgentModels] = useState<AgentModelRow[]>([]);
  const [configLoading, setConfigLoading] = useState(true);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState<string>("");

  useEffect(() => {
    getAdminConfig()
      .then((data: Record<string, string>) => {
        setConfig(data);
        if (data.current_model) setSelectedModel(data.current_model);
      })
      .catch(() => setConfig({}))
      .finally(() => setConfigLoading(false));

    fetch("/api/admin/agents")
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setAgentModels(data);
        } else if (data && typeof data === "object") {
          const rows: AgentModelRow[] = Object.entries(data).map(([agent, model]) => ({
            agent,
            model: String(model),
            tier: String(model).includes(":free") || String(model).includes("via groq") ? "Free" : "Paid",
          }));
          setAgentModels(rows);
        }
      })
      .catch(() => setAgentModels([]))
      .finally(() => setAgentsLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
          <Settings className="w-8 h-8 text-blue-600" />
          Admin Settings
        </h1>
        <p className="text-slate-500 mt-1">ตั้งค่า API Keys และโมเดล AI ของระบบ</p>
      </div>

      {/* Section 1: API Keys */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-5">API Keys</h2>
        {configLoading ? (
          <div className="text-slate-500 text-sm">กำลังโหลด...</div>
        ) : (
          <div className="space-y-4">
            {API_KEY_ROWS.map(({ label, key }) => {
              const value = config[key] ?? "";
              const hasValue = Boolean(value);
              return (
                <div key={key} className="flex items-center gap-4">
                  <div className="w-40 text-sm font-medium text-slate-700 flex-shrink-0">{label}</div>
                  <MaskedKeyInput value={value} hasValue={hasValue} />
                  <div className="flex-shrink-0">
                    {hasValue ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded-full">
                        <CheckCircle className="w-3 h-3" /> ตั้งค่าแล้ว
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-slate-500 bg-slate-100 border border-slate-200 px-2 py-1 rounded-full">
                        <XCircle className="w-3 h-3" /> ยังไม่ตั้งค่า
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Section 2: Free Models */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-5">Free Models (OpenRouter)</h2>
        <div className="space-y-4">
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Free Tier</p>
            <div className="flex flex-wrap gap-2">
              {FREE_MODELS.map((m) => (
                <span
                  key={m}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono border transition-colors ${
                    selectedModel === m
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-emerald-50 text-emerald-700 border-emerald-200"
                  }`}
                >
                  {selectedModel !== m && <span className="text-emerald-500 font-bold">Free ✓</span>}
                  {m}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Groq (Free)</p>
            <div className="flex flex-wrap gap-2">
              {GROQ_MODELS.map((m) => (
                <span
                  key={m}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono border transition-colors ${
                    selectedModel === m
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-emerald-50 text-emerald-700 border-emerald-200"
                  }`}
                >
                  {selectedModel !== m && <span className="text-emerald-500 font-bold">Free ✓</span>}
                  {m}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Paid</p>
            <div className="flex flex-wrap gap-2">
              {PAID_MODELS.map((m) => (
                <span
                  key={m}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono border transition-colors ${
                    selectedModel === m
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-slate-50 text-slate-600 border-slate-200"
                  }`}
                >
                  {m}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Section 3: Current Agent Models */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-5">Current Agent Models</h2>
        {agentsLoading ? (
          <div className="text-slate-500 text-sm">กำลังโหลด...</div>
        ) : agentModels.length === 0 ? (
          <div className="text-slate-400 text-sm">ไม่สามารถโหลดข้อมูล agents ได้ — endpoint อาจยังไม่พร้อม</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-3 pr-6 font-medium">Agent</th>
                  <th className="py-3 pr-6 font-medium">Model</th>
                  <th className="py-3 font-medium">Tier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {agentModels.map((row) => (
                  <tr key={row.agent} className="text-slate-700">
                    <td className="py-3 pr-6 font-medium capitalize">{row.agent}</td>
                    <td className="py-3 pr-6 font-mono text-xs text-slate-600">{row.model}</td>
                    <td className="py-3">
                      {row.tier === "Free" ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                          <CheckCircle className="w-3 h-3" /> Free
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-xs text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
                          Paid
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
