"use client";
import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { BarChart3, TrendingUp, Target, Brain } from "lucide-react";
import { getAccuracy, type AccuracyStats } from "@/lib/api";

function StatCard({ title, value, icon: Icon, color = "text-white" }: {
  title: string; value: string; icon: React.ElementType; color?: string
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex items-center gap-4">
      <div className="bg-slate-700 p-3 rounded-lg">
        <Icon className={`w-6 h-6 ${color}`} />
      </div>
      <div>
        <p className="text-slate-400 text-xs uppercase tracking-wider">{title}</p>
        <p className={`text-2xl font-bold ${color}`}>{value}</p>
      </div>
    </div>
  );
}

export default function AccuracyPage() {
  const [stats, setStats] = useState<AccuracyStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAccuracy().then(setStats).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-slate-400 p-8">กำลังโหลด...</div>;
  if (!stats) return <div className="text-red-400 p-8">ไม่สามารถโหลดข้อมูลได้</div>;

  const tfData = Object.entries(stats.by_timeframe).map(([tf, v]) => ({
    name: tf,
    accuracy: Math.round(v.direction_accuracy * 100),
    score: Math.round(v.avg_accuracy_score * 100),
    total: v.total,
  }));

  const symData = Object.entries(stats.by_symbol).map(([sym, v]) => ({
    name: sym,
    accuracy: Math.round(v.direction_accuracy * 100),
    score: Math.round(v.avg_accuracy_score * 100),
    total: v.total,
  })).sort((a, b) => b.total - a.total).slice(0, 10);

  const accuracyColor = (pct: number) =>
    pct >= 70 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <BarChart3 className="w-8 h-8 text-sky-400" />
          ความแม่นยำของระบบ
        </h1>
        <p className="text-slate-400 mt-1">ติดตามประสิทธิภาพการคาดการณ์ของ AI</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="การคาดการณ์ทั้งหมด" value={String(stats.total)} icon={Brain} />
        <StatCard title="เทียบผลแล้ว" value={String(stats.compared)} icon={Target} />
        <StatCard
          title="ความแม่นยำทิศทาง"
          value={stats.compared ? `${(stats.direction_accuracy * 100).toFixed(1)}%` : "-"}
          icon={TrendingUp}
          color={stats.direction_accuracy >= 0.7 ? "text-emerald-400" : stats.direction_accuracy >= 0.5 ? "text-yellow-400" : "text-red-400"}
        />
        <StatCard
          title="คะแนนเฉลี่ย"
          value={stats.compared ? `${(stats.avg_accuracy_score * 100).toFixed(1)}%` : "-"}
          icon={BarChart3}
          color="text-sky-400"
        />
      </div>

      {stats.compared === 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-8 text-center text-slate-500">
          ยังไม่มีการเทียบผล — ไปที่หน้า <a href="/predictions" className="text-sky-400 hover:underline">ประวัติ</a> แล้วกด "เทียบกับราคาปัจจุบัน"
        </div>
      )}

      {tfData.length > 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-5">ความแม่นยำตาม Timeframe</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={tfData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
              <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} stroke="#64748b" tick={{ fontSize: 12 }} unit="%" />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                labelStyle={{ color: "#f1f5f9" }}
                formatter={(v) => [`${v}%`]}
              />
              <Bar dataKey="accuracy" name="ความแม่นยำทิศทาง" radius={[4, 4, 0, 0]}>
                {tfData.map((entry, i) => (
                  <Cell key={i} fill={accuracyColor(entry.accuracy)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
            {tfData.map((d) => (
              <div key={d.name} className="bg-slate-750 rounded-lg p-3 text-center border border-slate-700">
                <div className="text-slate-400 text-xs">{d.name}</div>
                <div className={`text-xl font-bold ${accuracyColor(d.accuracy) === "#10b981" ? "text-emerald-400" : accuracyColor(d.accuracy) === "#f59e0b" ? "text-yellow-400" : "text-red-400"}`}>
                  {d.accuracy}%
                </div>
                <div className="text-slate-500 text-xs">{d.total} รายการ</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {symData.length > 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-5">ความแม่นยำตาม Symbol (Top 10)</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={symData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
              <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} stroke="#64748b" tick={{ fontSize: 12 }} unit="%" />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                formatter={(v) => [`${v}%`]}
              />
              <Bar dataKey="accuracy" name="ความแม่นยำ" radius={[4, 4, 0, 0]}>
                {symData.map((entry, i) => (
                  <Cell key={i} fill={accuracyColor(entry.accuracy)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
