"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, TrendingUp, TrendingDown, Minus, Target, BarChart3, Clock } from "lucide-react";
import { getPredictions, getAccuracy, type Prediction, type AccuracyStats } from "@/lib/api";
import { format } from "date-fns";

function DirectionBadge({ direction }: { direction: string }) {
  const styles: Record<string, string> = {
    bullish: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    bearish: "bg-red-50 text-red-700 border border-red-200",
    neutral: "bg-slate-50 text-slate-600 border border-slate-200",
  };
  const icons: Record<string, React.ReactNode> = {
    bullish: <TrendingUp className="w-3 h-3" />,
    bearish: <TrendingDown className="w-3 h-3" />,
    neutral: <Minus className="w-3 h-3" />,
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${styles[direction] ?? styles.neutral}`}>
      {icons[direction]} {direction}
    </span>
  );
}

function StatCard({ title, value, sub }: { title: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
      <p className="text-xs text-slate-500 uppercase tracking-wider">{title}</p>
      <p className="text-3xl font-bold text-slate-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const [recent, setRecent] = useState<Prediction[]>([]);
  const [stats, setStats] = useState<AccuracyStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getPredictions({ limit: 5 }), getAccuracy()])
      .then(([preds, acc]) => {
        setRecent(preds);
        setStats(acc);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
          <Brain className="w-8 h-8 text-blue-600" />
          Agent Invest Dashboard
        </h1>
        <p className="text-slate-500 mt-1">ระบบวิเคราะห์การลงทุนด้วย Multi-Agent AI</p>
      </div>

      {loading ? (
        <div className="text-slate-500">กำลังโหลด...</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="การคาดการณ์ทั้งหมด" value={stats?.total ?? 0} />
            <StatCard title="เทียบผลแล้ว" value={stats?.compared ?? 0} />
            <StatCard
              title="ความแม่นยำทิศทาง"
              value={stats?.compared ? `${(stats.direction_accuracy * 100).toFixed(1)}%` : "-"}
            />
            <StatCard
              title="คะแนนเฉลี่ย"
              value={stats?.compared ? `${(stats.avg_accuracy_score * 100).toFixed(1)}%` : "-"}
            />
          </div>

          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <Clock className="w-5 h-5 text-blue-600" />
                การคาดการณ์ล่าสุด
              </h2>
              <Link href="/predictions" className="text-blue-600 text-sm hover:underline">ดูทั้งหมด →</Link>
            </div>
            {recent.length === 0 ? (
              <p className="text-slate-500 text-sm">ยังไม่มีการคาดการณ์ — <Link href="/analyze" className="text-blue-600 hover:underline">เริ่มวิเคราะห์เลย</Link></p>
            ) : (
              <div className="space-y-3">
                {recent.map((p) => (
                  <Link
                    key={p.id}
                    href={`/predictions/${p.id}`}
                    className="flex items-center justify-between p-4 hover:bg-slate-50 rounded-lg border border-slate-200 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <span className="text-slate-900 font-semibold w-20">{p.symbol}</span>
                      <DirectionBadge direction={p.direction} />
                      <span className="text-slate-500 text-xs">{p.timeframe}</span>
                      <span className="text-slate-500 text-xs">conf: {(p.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="text-right">
                      <div className="text-slate-900 text-sm">${p.current_price.toFixed(2)}</div>
                      <div className="text-slate-400 text-xs">{format(new Date(p.created_at), "dd/MM/yy HH:mm")}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Link href="/analyze" className="bg-blue-600 hover:bg-blue-700 text-white rounded-2xl p-6 flex items-center gap-4 transition-colors">
              <Brain className="w-8 h-8" />
              <div>
                <div className="font-semibold text-lg">วิเคราะห์ใหม่</div>
                <div className="text-blue-200 text-sm">ป้อน symbol เพื่อให้ AI วิเคราะห์</div>
              </div>
            </Link>
            <Link href="/accuracy" className="bg-white hover:bg-slate-50 border border-slate-200 text-slate-900 rounded-2xl p-6 flex items-center gap-4 transition-colors shadow-sm">
              <BarChart3 className="w-8 h-8 text-blue-600" />
              <div>
                <div className="font-semibold text-lg">ดูความแม่นยำ</div>
                <div className="text-slate-500 text-sm">วิเคราะห์ประสิทธิภาพ AI</div>
              </div>
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
