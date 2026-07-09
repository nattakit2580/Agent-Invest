"use client";
import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Database, Target, CheckCircle2, Download, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { getDatasetStats, type DatasetStats } from "@/lib/api";

function StatCard({ title, value, sub, icon: Icon, color = "text-slate-900" }: {
  title: string; value: string | number; sub?: string; icon: React.ElementType; color?: string
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5 flex items-center gap-4">
      <div className="bg-slate-100 p-3 rounded-lg">
        <Icon className={`w-6 h-6 ${color}`} />
      </div>
      <div>
        <p className="text-slate-500 text-xs uppercase tracking-wider">{title}</p>
        <p className={`text-2xl font-bold ${color}`}>{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

const DIRECTION_META: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  bullish: { label: "Bullish", color: "#10b981", icon: TrendingUp },
  bearish: { label: "Bearish", color: "#ef4444", icon: TrendingDown },
  neutral: { label: "Neutral", color: "#94a3b8", icon: Minus },
};

export default function DatasetPage() {
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDatasetStats().then(setStats).catch(() => setStats(null)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-slate-500 p-8">กำลังโหลด...</div>;
  if (!stats) return <div className="text-red-600 p-8">ไม่สามารถโหลดข้อมูล dataset ได้</div>;

  const progressPct = Math.min(stats.progress_pct, 100);
  const dirTotal = Object.values(stats.direction_distribution).reduce((a, b) => a + b, 0);

  const scoreData = Object.entries(stats.accuracy_score_buckets)
    .map(([bucket, count]) => ({ bucket, count }))
    .sort((a, b) => parseFloat(a.bucket) - parseFloat(b.bucket));

  const tfData = Object.entries(stats.timeframe_distribution).map(([tf, count]) => ({ name: tf, count }));

  const scoreColor = (bucket: string) => {
    const v = parseFloat(bucket);
    return v >= 0.7 ? "#10b981" : v >= 0.4 ? "#f59e0b" : "#ef4444";
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
          <Database className="w-8 h-8 text-blue-600" />
          Dataset Collection
        </h1>
        <p className="text-slate-500 mt-1">ความคืบหน้าการสะสมข้อมูลสำหรับ fine-tune โมเดล (Phase 4 → 5)</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="การคาดการณ์ทั้งหมด" value={stats.total_predictions} icon={Database} />
        <StatCard title="เทียบผลแล้ว" value={stats.compared} sub="มี actual outcome" icon={CheckCircle2} color="text-blue-600" />
        <StatCard
          title="พร้อม Export"
          value={stats.export_ready}
          sub="มี accuracy score ครบ"
          icon={Download}
          color="text-emerald-600"
        />
      </div>

      {/* Progress toward next target */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Target className="w-5 h-5 text-blue-600" />
            เป้าหมายถัดไป: {stats.next_target.toLocaleString()} เคส
          </h2>
          <span className="text-2xl font-bold text-blue-600">{progressPct.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-4 overflow-hidden">
          <div
            className="h-4 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all"
            style={{ width: `${Math.max(progressPct, 2)}%` }}
          />
        </div>
        <div className="flex justify-between mt-3">
          {stats.targets.map((t) => (
            <div key={t} className={`text-center ${stats.export_ready >= t ? "text-emerald-600" : "text-slate-400"}`}>
              <div className="text-sm font-semibold">{t.toLocaleString()}</div>
              <div className="text-xs">{stats.export_ready >= t ? "ผ่านแล้ว ✓" : "เป้าหมาย"}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-4">
          Phase 5 (fine-tune) เริ่มได้เมื่อมีเคสพร้อม export ≥ 500 — ตอนนี้มี {stats.export_ready} เคส
          {stats.export_ready < 500 && ` (ขาดอีก ${500 - stats.export_ready})`}
        </p>
      </div>

      {/* Direction balance */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">สมดุล Direction (เฉพาะเคสที่เทียบผลแล้ว)</h2>
        {dirTotal === 0 ? (
          <p className="text-slate-500 text-sm">ยังไม่มีเคสที่เทียบผลแล้ว</p>
        ) : (
          <div className="space-y-3">
            {Object.entries(DIRECTION_META).map(([dir, meta]) => {
              const count = stats.direction_distribution[dir] ?? 0;
              const pct = dirTotal ? (count / dirTotal) * 100 : 0;
              const Icon = meta.icon;
              return (
                <div key={dir}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="flex items-center gap-2 text-slate-700">
                      <Icon className="w-4 h-4" style={{ color: meta.color }} />
                      {meta.label}
                    </span>
                    <span className="text-slate-500 tabular-nums">{count} ({pct.toFixed(1)}%)</span>
                  </div>
                  <div className="h-2.5 rounded bg-slate-100 overflow-hidden">
                    <div className="h-full rounded" style={{ width: `${Math.max(pct, 1)}%`, backgroundColor: meta.color }} />
                  </div>
                </div>
              );
            })}
            {dirTotal > 0 && (() => {
              const counts = Object.values(stats.direction_distribution);
              const maxC = Math.max(...counts);
              const minC = Math.min(...counts.filter((c) => c > 0));
              const imbalanced = counts.filter((c) => c > 0).length >= 2 && maxC / minC > 3;
              return imbalanced ? (
                <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
                  ⚠️ Class ไม่สมดุล (ต่างกันเกิน 3 เท่า) — ตอน export ควรใช้ --balance เพื่อ downsample
                </p>
              ) : null;
            })()}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Accuracy score histogram */}
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">การกระจาย Accuracy Score</h2>
          {scoreData.length === 0 ? (
            <p className="text-slate-500 text-sm">ยังไม่มีข้อมูล</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={scoreData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis dataKey="bucket" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8 }}
                  labelStyle={{ color: "#0f172a" }}
                />
                <Bar dataKey="count" name="จำนวนเคส" radius={[4, 4, 0, 0]}>
                  {scoreData.map((entry, i) => (
                    <Cell key={i} fill={scoreColor(entry.bucket)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          <p className="text-xs text-slate-400 mt-2">แนะนำ export เฉพาะเคส score ≥ 0.5 (คุณภาพ &gt; ปริมาณ)</p>
        </div>

        {/* Timeframe distribution */}
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">การกระจาย Timeframe</h2>
          {tfData.length === 0 ? (
            <p className="text-slate-500 text-sm">ยังไม่มีข้อมูล</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={tfData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8 }}
                  labelStyle={{ color: "#0f172a" }}
                />
                <Bar dataKey="count" name="จำนวนเคส" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Export shortcuts */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Export Dataset</h2>
        <div className="flex flex-wrap gap-3">
          <a
            href="/api/dataset/export?format=jsonl&min_score=0.5"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Download className="w-4 h-4" /> JSONL (score ≥ 0.5)
          </a>
          <a
            href="/api/dataset/export?format=jsonl"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-lg text-sm font-medium transition-colors"
          >
            <Download className="w-4 h-4" /> JSONL (ทั้งหมด)
          </a>
          <a
            href="/api/dataset/export?format=csv"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-lg text-sm font-medium transition-colors"
          >
            <Download className="w-4 h-4" /> CSV
          </a>
        </div>
        <p className="text-xs text-slate-400 mt-3">
          สำหรับ fine-tune ใช้: <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">python scripts/export_training_data.py --min-score 0.5 --balance</code>
        </p>
      </div>
    </div>
  );
}
