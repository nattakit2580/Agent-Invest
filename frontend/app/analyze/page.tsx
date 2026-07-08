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

const REGIME_STYLES: Record<string, string> = {
  volatile: "bg-amber-50 text-amber-700 border border-amber-200",
  trending_up: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  trending_down: "bg-red-50 text-red-700 border border-red-200",
  earnings_season: "bg-violet-50 text-violet-700 border border-violet-200",
  news_driven: "bg-blue-50 text-blue-700 border border-blue-200",
  sideways: "bg-slate-50 text-slate-600 border border-slate-200",
};

function RegimeBadge({ regime }: { regime: string }) {
  const style = REGIME_STYLES[regime] ?? "bg-slate-50 text-slate-600 border border-slate-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${style}`}>
      {regime.replace(/_/g, " ")}
    </span>
  );
}

function AgentCard({ name, output }: { name: string; output: Record<string, unknown> }) {
  const dir = (output.direction as string) || "neutral";
  const conf = (output.confidence as number) ?? 0.5;
  const summary = (output.summary as string) || "";
  const keyPoints = (output.key_points as string[]) || [];

  const borderColor =
    dir === "bullish" ? "border-l-emerald-500" :
    dir === "bearish" ? "border-l-red-500" :
    "border-l-slate-300";
  const labelColor =
    dir === "bullish" ? "text-emerald-600" :
    dir === "bearish" ? "text-red-600" :
    "text-slate-500";

  const agentNames: Record<string, string> = {
    news: "News Agent",
    fundamental: "Fundamental Agent",
    technical: "Technical Agent",
    sentiment: "Sentiment Agent",
  };

  return (
    <div className={`bg-white border border-slate-200 border-l-4 rounded-2xl shadow-sm p-5 ${borderColor}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-slate-900 font-semibold text-sm">{agentNames[name] ?? name}</span>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${labelColor}`}>{dir}</span>
          <span className="text-slate-400 text-xs">{(conf * 100).toFixed(0)}%</span>
        </div>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-1 mb-3">
        <div
          className={`h-1 rounded-full ${dir === "bullish" ? "bg-emerald-500" : dir === "bearish" ? "bg-red-500" : "bg-slate-400"}`}
          style={{ width: `${conf * 100}%` }}
        />
      </div>
      <p className="text-slate-600 text-xs leading-relaxed mb-2">{summary}</p>
      <ul className="space-y-1">
        {keyPoints.slice(0, 3).map((pt, i) => (
          <li key={i} className="text-slate-500 text-xs flex items-start gap-1">
            <span className="text-blue-600 mt-0.5">•</span> {pt}
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
      const message = err instanceof Error ? err.message : "วิเคราะห์ไม่สำเร็จ";
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
        <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
          <Brain className="w-8 h-8 text-blue-600" />
          วิเคราะห์การลงทุน
        </h1>
        <p className="text-slate-500 mt-1">ป้อน symbol เพื่อให้ Multi-Agent AI วิเคราะห์</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6 space-y-5">
        <div>
          <label className="block text-sm text-slate-500 mb-2">Symbol</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="เช่น AAPL, BTC-USD, PTT.BK"
            className="w-full bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-400"
          />
          <div className="flex gap-2 mt-2 flex-wrap">
            {QUICK_SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className="text-xs px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-full transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-slate-500 mb-2">ระยะเวลาการคาดการณ์</label>
          <div className="flex gap-2">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setTimeframe(tf.value)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  timeframe === tf.value
                    ? "bg-blue-600 text-white"
                    : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
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
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-100 disabled:text-slate-400 text-white font-semibold rounded-lg py-3 flex items-center justify-center gap-2 transition-colors"
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
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-center gap-3 text-red-600">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div className={`rounded-2xl p-6 border-2 ${
            result.direction === "bullish" ? "bg-emerald-50 border-emerald-200" :
            result.direction === "bearish" ? "bg-red-50 border-red-200" :
            "bg-white border-slate-200"
          }`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={`${result.direction === "bullish" ? "text-emerald-600" : result.direction === "bearish" ? "text-red-600" : "text-slate-500"}`}>
                    {directionIcon(result.direction)}
                  </span>
                  <h2 className="text-2xl font-bold text-slate-900">{result.symbol}</h2>
                  <span className={`text-lg font-semibold capitalize ${
                    result.direction === "bullish" ? "text-emerald-600" :
                    result.direction === "bearish" ? "text-red-600" : "text-slate-500"
                  }`}>{result.direction}</span>
                  {result.market_regime && (
                    <RegimeBadge regime={result.market_regime} />
                  )}
                </div>
                <p className="text-slate-600 mt-3 leading-relaxed text-sm">{result.reasoning}</p>
              </div>
              <div className="text-right ml-6 flex-shrink-0">
                <div className="text-slate-500 text-xs">Confidence</div>
                <div className="text-3xl font-bold text-slate-900">{((result.confidence ?? 0) * 100).toFixed(0)}%</div>
                <div className="text-slate-500 text-xs mt-2">Entry</div>
                <div className="text-slate-900 font-semibold">${(result.current_price ?? 0).toFixed(2)}</div>
                {result.target_price != null && (
                  <>
                    <div className="text-slate-500 text-xs mt-1">Target</div>
                    <div className="text-blue-600 font-semibold">${result.target_price.toFixed(2)}</div>
                  </>
                )}
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-slate-900 mb-3">ผลวิเคราะห์แยก Agent</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.agent_outputs &&
                Object.entries(result.agent_outputs)
                  .filter(([name]) => !name.startsWith("_"))
                  .map(([name, output]) => (
                    <AgentCard key={name} name={name} output={output as Record<string, unknown>} />
                  ))}
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => router.push("/predictions")}
              className="flex-1 bg-white hover:bg-slate-50 border border-slate-200 text-slate-900 py-3 rounded-lg text-sm font-medium transition-colors"
            >
              ดูประวัติทั้งหมด
            </button>
            <button
              onClick={() => { setResult(null); setSymbol(""); }}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg text-sm font-medium transition-colors"
            >
              วิเคราะห์ใหม่
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
