"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { TrendingUp, TrendingDown, Minus, RefreshCw, ArrowLeft, CheckCircle } from "lucide-react";
import { getPrediction, autoCompare, type Prediction } from "@/lib/api";
import { format } from "date-fns";

function DirectionBadge({ direction }: { direction: string }) {
  const map: Record<string, string> = {
    bullish: "bg-emerald-50 text-emerald-700 border-emerald-200",
    bearish: "bg-red-50 text-red-700 border-red-200",
    neutral: "bg-slate-50 text-slate-600 border-slate-200",
  };
  const Icon = direction === "bullish" ? TrendingUp : direction === "bearish" ? TrendingDown : Minus;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-medium border ${map[direction] ?? map.neutral}`}>
      <Icon className="w-4 h-4" /> {direction}
    </span>
  );
}

function AgentCard({ name, output }: { name: string; output: Record<string, unknown> }) {
  const dir = output.direction as string;
  const conf = (output.confidence as number) || 0;
  const agentNames: Record<string, string> = {
    news: "News Agent", fundamental: "Fundamental Agent",
    technical: "Technical Agent", sentiment: "Sentiment Agent",
  };
  const borderColor =
    dir === "bullish" ? "border-l-emerald-500" :
    dir === "bearish" ? "border-l-red-500" :
    "border-l-slate-300";
  return (
    <div className={`bg-white border border-slate-200 border-l-4 rounded-2xl shadow-sm p-5 ${borderColor}`}>
      <div className="flex justify-between items-center mb-3">
        <span className="text-slate-900 font-semibold text-sm">{agentNames[name] ?? name}</span>
        <div className="flex items-center gap-2">
          <DirectionBadge direction={dir} />
          <span className="text-slate-400 text-xs">{(conf * 100).toFixed(0)}%</span>
        </div>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-1.5 mb-3">
        <div className={`h-1.5 rounded-full ${dir === "bullish" ? "bg-emerald-500" : dir === "bearish" ? "bg-red-500" : "bg-slate-400"}`}
          style={{ width: `${conf * 100}%` }} />
      </div>
      <p className="text-slate-600 text-xs mb-3">{output.summary as string}</p>
      <ul className="space-y-1">
        {((output.key_points as string[]) || []).map((pt, i) => (
          <li key={i} className="text-slate-500 text-xs flex gap-1"><span className="text-blue-600">•</span>{pt}</li>
        ))}
      </ul>
      {Object.entries(output).filter(([k]) => !["direction","confidence","summary","key_points"].includes(k)).length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-200 flex flex-wrap gap-2">
          {Object.entries(output)
            .filter(([k]) => !["direction","confidence","summary","key_points"].includes(k))
            .map(([k, v]) => (
              <span key={k} className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded">
                {k}: <span className="text-slate-700">{String(v)}</span>
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

export default function PredictionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    getPrediction(id).then(setPrediction).finally(() => setLoading(false));
  }, [id]);

  const handleCompare = async () => {
    setComparing(true);
    try {
      const updated = await autoCompare(id);
      setPrediction(updated);
    } catch {
      alert("ไม่สามารถดึงราคาปัจจุบันได้");
    } finally {
      setComparing(false);
    }
  };

  if (loading) return <div className="text-slate-500 p-8">กำลังโหลด...</div>;
  if (!prediction) return <div className="text-red-600 p-8">ไม่พบข้อมูล</div>;

  const p = prediction;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <button onClick={() => router.back()} className="flex items-center gap-2 text-slate-500 hover:text-slate-900 transition-colors text-sm">
        <ArrowLeft className="w-4 h-4" /> กลับ
      </button>

      <div className={`rounded-2xl p-6 border-2 ${
        p.direction === "bullish" ? "bg-emerald-50 border-emerald-200" :
        p.direction === "bearish" ? "bg-red-50 border-red-200" :
        "bg-white border-slate-200"
      }`}>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-3xl font-bold text-slate-900">{p.symbol}</h1>
              <DirectionBadge direction={p.direction} />
              <span className="text-slate-500 text-sm">{p.timeframe}</span>
            </div>
            <p className="text-slate-600 mt-3 leading-relaxed">{p.reasoning}</p>
            <p className="text-slate-400 text-xs mt-2">{format(new Date(p.created_at), "dd MMM yyyy HH:mm")}</p>
          </div>
          <div className="text-right ml-6 flex-shrink-0 space-y-2">
            <div>
              <div className="text-slate-500 text-xs">Confidence</div>
              <div className="text-4xl font-bold text-slate-900">{(p.confidence * 100).toFixed(0)}%</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs">Entry Price</div>
              <div className="text-slate-900 font-semibold text-lg">${p.current_price.toFixed(2)}</div>
            </div>
            {p.target_price && (
              <div>
                <div className="text-slate-500 text-xs">Target</div>
                <div className="text-blue-600 font-semibold">${p.target_price.toFixed(2)}</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {p.status === "compared" && (
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6 border-l-4 border-l-emerald-500">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-emerald-600" /> ผลการเทียบ
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <div className="text-slate-500 text-xs mb-1">ราคาจริง</div>
              <div className="text-slate-900 text-xl font-bold">${p.actual_price?.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-slate-500 text-xs mb-1">ทิศทางจริง</div>
              <DirectionBadge direction={p.actual_direction ?? "neutral"} />
            </div>
            <div className="text-center">
              <div className="text-slate-500 text-xs mb-1">คะแนนความแม่นยำ</div>
              <div className={`text-2xl font-bold ${
                (p.accuracy_score ?? 0) >= 0.7 ? "text-emerald-600" :
                (p.accuracy_score ?? 0) >= 0.4 ? "text-yellow-500" : "text-red-600"
              }`}>
                {((p.accuracy_score ?? 0) * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        </div>
      )}

      {p.status === "pending" && (
        <button
          onClick={handleCompare}
          disabled={comparing}
          className="w-full bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-600 rounded-2xl py-3 flex items-center justify-center gap-2 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${comparing ? "animate-spin" : ""}`} />
          เทียบกับราคาปัจจุบัน
        </button>
      )}

      {p.agent_outputs && (
        <div>
          <h2 className="text-lg font-semibold text-slate-900 mb-3">ผลวิเคราะห์แยก Agent</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(p.agent_outputs).map(([name, output]) => (
              <AgentCard key={name} name={name} output={output as Record<string, unknown>} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
