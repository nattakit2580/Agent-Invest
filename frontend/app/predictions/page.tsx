"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { TrendingUp, TrendingDown, Minus, RefreshCw, CheckCircle, Clock } from "lucide-react";
import { getPredictions, autoCompare, type Prediction } from "@/lib/api";
import { format } from "date-fns";

function DirectionBadge({ direction }: { direction: string }) {
  const map: Record<string, string> = {
    bullish: "bg-emerald-50 text-emerald-700 border-emerald-200",
    bearish: "bg-red-50 text-red-700 border-red-200",
    neutral: "bg-slate-50 text-slate-600 border-slate-200",
  };
  const Icon = direction === "bullish" ? TrendingUp : direction === "bearish" ? TrendingDown : Minus;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${map[direction] ?? map.neutral}`}>
      <Icon className="w-3 h-3" /> {direction}
    </span>
  );
}

function AccuracyBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 bg-slate-100 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-500">{pct}%</span>
    </div>
  );
}

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState<string | null>(null);
  const [filter, setFilter] = useState({ symbol: "", timeframe: "", status: "" });

  const load = () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (filter.symbol) params.symbol = filter.symbol;
    if (filter.timeframe) params.timeframe = filter.timeframe;
    if (filter.status) params.status = filter.status;
    getPredictions(params).then(setPredictions).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [filter]);

  const handleAutoCompare = async (id: string) => {
    setComparing(id);
    try {
      const updated = await autoCompare(id);
      setPredictions((prev) => prev.map((p) => (p.id === id ? updated : p)));
    } catch {
      alert("ไม่สามารถดึงราคาปัจจุบันได้");
    } finally {
      setComparing(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-slate-900">ประวัติการคาดการณ์</h1>
        <span className="text-slate-500 text-sm">{predictions.length} รายการ</span>
      </div>

      <div className="flex gap-3 flex-wrap">
        <input
          placeholder="กรอง Symbol..."
          value={filter.symbol}
          onChange={(e) => setFilter((f) => ({ ...f, symbol: e.target.value }))}
          className="bg-white border border-slate-200 text-slate-900 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-400"
        />
        <select
          value={filter.timeframe}
          onChange={(e) => setFilter((f) => ({ ...f, timeframe: e.target.value }))}
          className="bg-white border border-slate-200 text-slate-900 rounded-lg px-3 py-2 text-sm focus:outline-none"
        >
          <option value="">ทุก Timeframe</option>
          <option value="1d">1 วัน</option>
          <option value="1w">1 สัปดาห์</option>
          <option value="1m">1 เดือน</option>
          <option value="3m">3 เดือน</option>
        </select>
        <select
          value={filter.status}
          onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
          className="bg-white border border-slate-200 text-slate-900 rounded-lg px-3 py-2 text-sm focus:outline-none"
        >
          <option value="">ทุก Status</option>
          <option value="pending">รอเทียบผล</option>
          <option value="compared">เทียบแล้ว</option>
        </select>
      </div>

      {loading ? (
        <div className="text-slate-500">กำลังโหลด...</div>
      ) : predictions.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <p>ยังไม่มีการคาดการณ์</p>
          <Link href="/analyze" className="text-blue-600 hover:underline text-sm mt-2 inline-block">เริ่มวิเคราะห์เลย →</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {predictions.map((p) => (
            <div key={p.id} className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5 hover:border-slate-300 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <Link href={`/predictions/${p.id}`} className="text-slate-900 font-bold text-lg hover:text-blue-600 transition-colors">
                      {p.symbol}
                    </Link>
                    <DirectionBadge direction={p.direction} />
                    <span className="text-slate-500 text-xs bg-slate-100 px-2 py-0.5 rounded">{p.timeframe}</span>
                    {p.status === "compared" ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-600 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                        <CheckCircle className="w-3 h-3" /> เทียบแล้ว
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                        <Clock className="w-3 h-3" /> รอเทียบผล
                      </span>
                    )}
                  </div>
                  <p className="text-slate-500 text-xs mt-2 line-clamp-2">{p.reasoning}</p>
                </div>

                <div className="text-right flex-shrink-0 space-y-1">
                  <div className="text-slate-900 font-semibold">${p.current_price.toFixed(2)}</div>
                  {p.target_price && (
                    <div className="text-blue-600 text-xs">→ ${p.target_price.toFixed(2)}</div>
                  )}
                  <div className="text-slate-500 text-xs">conf: {(p.confidence * 100).toFixed(0)}%</div>
                  <div className="text-slate-400 text-xs">{format(new Date(p.created_at), "dd/MM/yy HH:mm")}</div>
                </div>
              </div>

              {p.status === "compared" && p.accuracy_score !== null && (
                <div className="mt-3 pt-3 border-t border-slate-200 flex items-center gap-6 flex-wrap">
                  <div>
                    <div className="text-slate-500 text-xs mb-1">ราคาจริง</div>
                    <div className="text-slate-900 text-sm font-medium">${p.actual_price?.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-slate-500 text-xs mb-1">ทิศทางจริง</div>
                    <DirectionBadge direction={p.actual_direction ?? "neutral"} />
                  </div>
                  <div>
                    <div className="text-slate-500 text-xs mb-1">คะแนนความแม่นยำ</div>
                    <AccuracyBar score={p.accuracy_score} />
                  </div>
                </div>
              )}

              {p.status === "pending" && (
                <div className="mt-3 pt-3 border-t border-slate-200">
                  <button
                    onClick={() => handleAutoCompare(p.id)}
                    disabled={comparing === p.id}
                    className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3 h-3 ${comparing === p.id ? "animate-spin" : ""}`} />
                    เทียบกับราคาปัจจุบัน
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
