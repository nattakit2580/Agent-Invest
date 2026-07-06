"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Brain, TrendingUp, TrendingDown, Minus, AlertCircle, Loader2 } from "lucide-react";
import { analyzeSymbol, type Prediction } from "@/lib/api";

const TIMEFRAMES = [
  { value: "1d", label: "1 วัน" },
  { value: "1w", label: "1 สัปดาห์" },
  { value: "1m", label: "1 เดือน" },
  { value: "3m", label: "3 เดือน" },
];

const QUICK_SYMBOLS = ["AAPL", "TSLA", "NVDA", "BTC-USD", "ETH-USD", "PTT.BK", "AOT.BK"];

type ApiError = {
  response?: { data?: { detail?: string } };
  message?: string;
};

function AgentCard({ name, output }: { name: string; output: Record<string, unknown> }) {
  const isCritic = name === "_critic";
  const dir = (isCritic ? output.revised_direction : output.direction) as string || "neutral";
  const conf = typeof output.confidence === "number" ? output.confidence as number : 0;
  const summary = (isCritic ? output.critique : output.summary) as string || "";
  const keyPoints = ((isCritic ? output.counter_points : output.key_points) as string[]) || [];

  const borderColor = dir === "bullish" ? "border-emerald-700" : dir === "bearish" ? "border-red-700" : "border-slate-600";
  const labelColor = dir === "bullish" ? "text-emerald-400" : dir === "bearish" ? "text-red-400" : "text-slate-400";

  const agentNames: Record<string, string> = {
    news: "News Agent",
    fundamental: "Fundamental Agent",
    technical: "Technical Agent",
    sentiment: "Sentiment Agent",
    _critic: "Risk Critic",
  };

  return (
    <div className={`bg-slate-800 border rounded-xl p-5 ${borderColor}`}>
      <div className="flex items-center justify-between mb-3 gap-3">
        <span className="text-white font-semibold text-sm">{agentNames[name] ?? name}</span>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs font-medium ${labelColor}`}>{dir}</span>
          {!isCritic && <span className="text-slate-500 text-xs">{(conf * 100).toFixed(0)}%</span>}
        </div>
      </div>
      {!isCritic && (
        <div className="w-full bg-slate-700 rounded-full h-1 mb-3">
          <div
            className={`h-1 rounded-full ${dir === "bullish" ? "bg-emerald-500" : dir === "bearish" ? "bg-red-500" : "bg-slate-500"}`}
            style={{ width: `${Math.max(0, Math.min(conf, 1)) * 100}%` }}
          />
        </div>
      )}
      {summary && <p className="text-slate-300 text-xs leading-relaxed mb-2">{summary}</p>}
      <ul className="space-y-1">
        {keyPoints.slice(0, 3).map((pt, i) => (
          <li key={i} className="text-slate-500 text-xs flex items-start gap-1">
            <span className="text-sky-500 mt-0.5">•</span> {pt}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AnalyzePage() {
  const router = useRouter();
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("1w");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Prediction | null>(null);

  const handleAnalyze = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await analyzeSymbol(symbol.trim().toUpperCase(), timeframe);
      setResult(data);
    } catch (err: unknown) {
      const apiError = err as ApiError;
      const message = apiError.response?.data?.detail || apiError.message || "วิเคราะห์ไม่สำเร็จ";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const directionIcon = (d: string) =>
    d === "bullish" ? <TrendingUp className="w-6 h-6" /> : d === "bearish" ? <TrendingDown className="w-6 h-6" /> : <Minus className="w-6 h-6" />;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Brain className="w-8 h-8 text-sky-400" />
          วิเคราะห์การลงทุน
        </h1>
        <p className="text-slate-400 mt-1">ป้อน symbol เพื่อให้ Multi-Agent AI วิเคราะห์</p>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-5">
        <div>
          <label className="block text-sm text-slate-400 mb-2">Symbol</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="เช่น AAPL, BTC-USD, PTT.BK"
            className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-sky-500"
          />
          <div className="flex gap-2 mt-2 flex-wrap">
            {QUICK_SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className="text-xs px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-full transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">ระยะเวลาการคาดการณ์</label>
          <div className="flex gap-2 flex-wrap">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setTimeframe(tf.value)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  timeframe === tf.value
                    ? "bg-sky-600 text-white"
                    : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={loading || !symbol.trim()}
          className="w-full bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-semibold rounded-lg py-3 flex items-center justify-center gap-2 transition-colors"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              กำลังวิเคราะห์ด้วย 4 Agents...
            </>
          ) : (
            <>
              <Brain className="w-4 h-4" />
              วิเคราะห์เลย
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 flex items-center gap-3 text-red-400">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div className={`rounded-xl p-6 border-2 ${
            result.direction === "bullish" ? "bg-emerald-900/20 border-emerald-600" :
            result.direction === "bearish" ? "bg-red-900/20 border-red-600" :
            "bg-slate-800 border-slate-600"
          }`}>
            <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={`${result.direction === "bullish" ? "text-emerald-400" : result.direction === "bearish" ? "text-red-400" : "text-slate-400"}`}>
                    {directionIcon(result.direction)}
                  </span>
                  <h2 className="text-2xl font-bold text-white">{result.symbol}</h2>
                  <span className={`text-lg font-semibold capitalize ${
                    result.direction === "bullish" ? "text-emerald-400" :
                    result.direction === "bearish" ? "text-red-400" : "text-slate-400"
                  }`}>{result.direction}</span>
                </div>
                <p className="text-slate-300 mt-3 leading-relaxed text-sm">{result.reasoning}</p>
              </div>
              <div className="text-left md:text-right shrink-0">
                <div className="text-slate-400 text-xs">Confidence</div>
                <div className="text-3xl font-bold text-white">{(result.confidence * 100).toFixed(0)}%</div>
                <div className="text-slate-400 text-xs mt-2">Entry</div>
                <div className="text-white font-semibold">${result.current_price.toFixed(2)}</div>
                {result.target_price && (
                  <>
                    <div className="text-slate-400 text-xs mt-1">Target</div>
                    <div className="text-sky-400 font-semibold">${result.target_price.toFixed(2)}</div>
                  </>
                )}
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-white mb-3">ผลวิเคราะห์แยก Agent</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.agent_outputs &&
                Object.entries(result.agent_outputs).map(([name, output]) => (
                  <AgentCard key={name} name={name} output={output as Record<string, unknown>} />
                ))}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={() => router.push("/predictions")}
              className="flex-1 bg-slate-700 hover:bg-slate-600 text-white py-3 rounded-lg text-sm font-medium transition-colors"
            >
              ดูประวัติทั้งหมด
            </button>
            <button
              onClick={() => { setResult(null); setSymbol(""); }}
              className="flex-1 bg-sky-600 hover:bg-sky-500 text-white py-3 rounded-lg text-sm font-medium transition-colors"
            >
              วิเคราะห์ใหม่
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
